"""0.0.2 核心学习索引的最小真实语义测试。"""

import gzip
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from leximeet_dictionary.entry_v2 import export_core, read_entry
from leximeet_dictionary.learning import (
    BOOKS, build_learning, export_missing, learning_for_entry, list_catalogs, list_members,
)
from leximeet_dictionary.learning_verify import verify_learning


def _write_json(path: Path, value) -> dict:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def _entry(word, entry_id, tags=(), topics=(), hook=None):
    return {
        "schema_version": "leximeet.entry.v1", "entry_id": entry_id, "headword": word,
        "lookup_key": word.casefold(), "memory_hook_zh": hook,
        "origin": "curated" if hook else "ecdict-fallback",
        "ecdict": {
            "exam_tags": [{"code": tag} for tag in tags],
            "frequency_ranks": {"frq": 100} if word == "Photosynthesis" else {},
        },
        "senses": [{
            "sense_id": "sense-" + entry_id, "pos": "noun",
            "topics": [{"code": topic} for topic in topics],
        }],
    }


class LearningTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core = self.root / "core.jsonl.gz"
        self.entries = [
            _entry("Photosynthesis", "photo", ("toefl",), ("biology", "biochemistry"), "阳光工厂"),
            _entry("May", "month"),
            _entry("may", "modal"),
            _entry("algorithm", "algorithm", ("cet4",), ("computing",)),
        ]
        with gzip.open(self.core, "wt", encoding="utf-8") as stream:
            for entry in self.entries:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.dicts = self.root / "dicts"
        self.dicts.mkdir()
        qwerty = {}
        for book_id, _, _ in BOOKS:
            words = [{"name": "photosynthesis", "trans": ["光合作用"], "usphone": "photo-us"},
                     {"name": "Photosynthesis"},
                     {"name": "May"}, {"name": "MAY"}, {"name": "absent"}] if book_id == "CET4_T" else []
            qwerty[book_id] = _write_json(self.dicts / (book_id + ".json"), words)
        self.gpt = self.root / "gptwords.json"
        self.gpt.write_text("\n".join(json.dumps(row) for row in [
            {"word": "Photosynthesis", "content": "AI 学习材料"},
            {"word": "algorithm", "content": "算法助记"},
            {"word": "MAY", "content": "有歧义"},
        ]) + "\n", encoding="utf-8")
        self.lock = self.root / "lock.json"
        _write_json(self.lock, {
            "schema_version": "leximeet.learning-sources.v1",
            "qwerty": qwerty,
            "qwerty_commit": "fixture",
            "dictionary_by_gpt4_commit": "fixture",
            "dictionary_by_gpt4": {
                "sha256": hashlib.sha256(self.gpt.read_bytes()).hexdigest()
            },
        })
        self.out = self.root / "learning.sqlite"

    def test_catalog_scope_order_and_mnemonic_provenance(self):
        report = build_learning(self.core, self.out, self.lock, self.dicts, self.gpt)
        self.assertEqual(report["core_entries"], 4)
        self.assertEqual(report["qwerty_duplicate"], 1)
        self.assertEqual(report["qwerty_unmatched"], 1)
        self.assertEqual(report["gpt_matched_entries"], 2)
        self.assertEqual(report["gpt_ambiguous"], 1)
        self.assertEqual(report["entries_without_learning_material"], 2)
        catalogs = {row["catalog_id"]: row for row in list_catalogs(self.out)}
        self.assertEqual(len(catalogs), len(BOOKS) + 8 + 5)
        self.assertEqual(catalogs["book:qwerty:CET4_T"]["source"],
                         "qwerty-learner:fixture:CET4_T")
        members = list_members(self.out, "book:qwerty:CET4_T")
        self.assertEqual([row["entry_id"] for row in members], ["photo", "month"])
        self.assertEqual(members[0]["position"], 1)
        self.assertEqual(members[0]["source_payload"]["glosses_zh"], ["光合作用"])
        self.assertEqual(members[0]["source_payload"]["pronunciations"][0]["region"], "en-US")
        subject = list_members(self.out, "subject:topic:biology")
        self.assertEqual(subject[0]["sense_ids"], ["sense-photo"])
        self.assertEqual(list_members(self.out, "exam:ecdict:toefl")[0]["sense_ids"], [])
        photo = learning_for_entry(self.out, "photo")
        self.assertEqual(len(photo["mnemonics"]), 2)
        self.assertEqual({m["review_status"] for m in photo["mnemonics"]},
                         {"source-published", "ai-unreviewed"})
        self.assertTrue(all(isinstance(m["provenance"], dict) for m in photo["mnemonics"]))
        missing = self.root / "missing.jsonl"
        exported = export_missing(self.core, self.out, missing)
        self.assertEqual(exported["missing_entries"], 2)
        rows = [json.loads(line) for line in missing.read_text().splitlines()]
        self.assertEqual({row["entry_id"] for row in rows}, {"month", "modal"})
        self.assertTrue(all(row["entry_sha256"] for row in rows))
        self.assertTrue((self.root / "learning.report.json").exists())
        audit = json.loads((self.root / "learning.audit.json").read_text())
        self.assertEqual(len(audit["qwerty_skipped"]), 3)
        self.assertEqual(audit["gpt_skipped"][0]["reason"], "ambiguous")
        with self.assertRaises(FileExistsError):
            build_learning(self.core, self.out, self.lock)

    def test_v2_entry_reserves_learning_fields_and_exports_deterministically(self):
        build_learning(self.core, self.out, self.lock, self.dicts, self.gpt)
        entry = read_entry(self.core, self.out, "Photosynthesis")
        self.assertEqual(entry["schema_version"], "leximeet.entry.v2")
        self.assertEqual(entry["base_entry_schema"], "leximeet.entry.v1")
        self.assertEqual(entry["learning"]["practice"], {
            "questions": [], "attested_examples": [],
        })
        self.assertEqual(set(entry["learning"]["lexical"]),
                         {"synonyms", "antonyms", "related_words", "phrases"})
        self.assertEqual(entry["learning"]["illustrations"], [])
        self.assertEqual(entry["learning"]["source_signals"], [])
        self.assertEqual(entry["learning"]["audio"]["offline_index_entry_id"], "photo")
        book = next(item for item in entry["learning"]["collections"]
                    if item["catalog_id"] == "book:qwerty:CET4_T")
        self.assertEqual(book["source_payload"]["glosses_zh"], ["光合作用"])
        self.assertEqual(book["source_payload"]["source_record_id"], None)
        first = self.root / "core-v2-first.jsonl.gz"
        second = self.root / "core-v2-second.jsonl.gz"
        result = export_core(self.core, self.out, first)
        self.assertEqual(result["entry_count"], 4)
        self.assertEqual(export_core(self.core, self.out, second)["sha256"], result["sha256"])
        with gzip.open(first, "rt", encoding="utf-8") as stream:
            self.assertEqual(sum(1 for _ in stream), 4)
        with self.assertRaises(FileExistsError):
            export_core(self.core, self.out, first)

    def test_duplicate_core_entry_is_rejected(self):
        with gzip.open(self.core, "at", encoding="utf-8") as stream:
            stream.write(json.dumps(self.entries[0]) + "\n")
        with self.assertRaisesRegex(ValueError, "重复词头"):
            build_learning(self.core, self.out, self.lock)
        self.assertFalse(self.out.exists())

    def test_input_hash_mismatch_fails_before_output(self):
        (self.dicts / "CET4_T.json").write_text("[] ", encoding="utf-8")
        with self.assertRaises(ValueError):
            build_learning(self.core, self.out, self.lock, self.dicts, self.gpt)
        self.assertFalse(self.out.exists())

    def test_core_only_catalogues_without_candidates(self):
        report = build_learning(self.core, self.out, self.lock)
        self.assertEqual(report["catalogs"], 13)
        self.assertEqual(report["entries_without_learning_material"], 3)
        with sqlite3.connect(self.out) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM mnemonics").fetchone()[0], 1)

    def test_known_bad_gpt_article_is_excluded_without_dropping_short_hook(self):
        with gzip.open(self.core, "at", encoding="utf-8") as stream:
            stream.write(json.dumps(_entry("will", "will", hook="原有短助记")) + "\n")
        with self.gpt.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"word": "will", "content": "没有名词形式"}) + "\n")
        lock = json.loads(self.lock.read_text())
        lock["dictionary_by_gpt4"]["sha256"] = hashlib.sha256(self.gpt.read_bytes()).hexdigest()
        _write_json(self.lock, lock)
        report = build_learning(self.core, self.out, self.lock, self.dicts, self.gpt)
        self.assertEqual(report["gpt_editorial_excluded"], 1)
        aids = learning_for_entry(self.out, "will")["mnemonics"]
        self.assertEqual(len(aids), 1)
        self.assertEqual(aids[0]["content"], "原有短助记")
        audit = json.loads((self.root / "learning.audit.json").read_text())
        self.assertTrue(any(item["reason"] == "editorial-exclusion"
                            for item in audit["gpt_skipped"]))

    def test_subject_order_uses_matching_sense_priority_before_global_frequency(self):
        self.entries[0]["senses"][0]["priority"] = "rare"
        self.entries[3]["senses"][0]["priority"] = "core"
        self.entries[3]["senses"][0]["topics"] = [{"code": "biology"}]
        with gzip.open(self.core, "wt", encoding="utf-8") as stream:
            for entry in self.entries:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        build_learning(self.core, self.out, self.lock)
        members = list_members(self.out, "subject:topic:biology")
        self.assertEqual([row["entry_id"] for row in members], ["algorithm", "photo"])

    def test_learning_verifier_rejects_missing_content_and_wrong_sense(self):
        build_learning(self.core, self.out, self.lock, self.dicts, self.gpt)
        self.assertEqual(verify_learning(self.core, self.out)["missing_mnemonics"], 2)
        with sqlite3.connect(self.out) as db:
            db.execute("UPDATE members SET sense_ids='[\"unknown-sense\"]' "
                       "WHERE catalog_id='subject:topic:biology'")
        with self.assertRaisesRegex(ValueError, "成员义项"):
            verify_learning(self.core, self.out)


if __name__ == "__main__":
    unittest.main()
