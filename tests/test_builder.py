"""词源对齐、大小写、失败回退和包校验的关键回归测试。"""

import csv
import gzip
import hashlib
import json
import subprocess
import tempfile
import tarfile
import unittest
import zipfile
from pathlib import Path

from leximeet_dictionary.builder import build, file_hash, generator_state, lookup, make_entry, verify_package, wordnet_candidates
from leximeet_dictionary.function_words import SOURCE as FUNCTION_SOURCE
from leximeet_dictionary.core import verify_core_archive
from leximeet_dictionary.integrity import verify_content
from leximeet_dictionary.package import package, verify_archive
from leximeet_dictionary.quality import report


def curated(word, entry_id, pos="noun"):
    return {"entry_id": entry_id, "headword": word, "headword_summary": "学习者摘要",
            "memory_hook": None, "study_notes": [],
            "pos_groups": [{"pos": pos, "etymology_id": "et1", "forms": [{"text": word + "s", "tags": ["plural"]}],
                            "pronunciations": [{"ipa": "/test/", "tags": ["US"]}],
                            "meanings": [{"sense_id": "s1", "short_gloss": "短释义",
                                          "learner_explanation": "中文解释", "examples": [],
                                          "priority": "core", "labels": ["countable"], "topics": []}]}]}


def audit(word, entry_id, pos="noun"):
    return {"entry_id": entry_id, "entries": {"pos_groups": [{"pos": pos, "etymology_id": "et1",
            "senses": [{"sense_id": "s1", "gloss": "English meaning", "raw_gloss": None,
                        "tags": ["countable"], "topics": ["finance"], "qualifier": None}],
            "pronunciations": [{"ipa": "/test/", "tags": ["US"], "audio_url": None,
                                  "audio_format": None}]}], "source_summary": {"raw_record_refs": []}}}


class BuilderTests(unittest.TestCase):
    def test_generator_revision_ignores_docs_only_commits_but_detects_dirty_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "leximeet_dictionary").mkdir()
            (root / "leximeet_dictionary" / "source.py").write_text("version = 1\n")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "leximeet_dictionary/source.py"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "source"], check=True)
            first = generator_state(root)
            self.assertFalse(first["dirty"])
            (root / "README.md").write_text("documentation\n")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "docs"], check=True)
            self.assertEqual(generator_state(root), first)
            (root / "leximeet_dictionary" / "source.py").write_text("version = 2\n")
            self.assertTrue(generator_state(root)["dirty"])

    def test_sense_alignment_requires_matching_group(self):
        source = curated("bank", "b")
        wrong = {"groups": [{"pos": "verb", "etymology_id": "et1", "senses": [{"gloss": "wrong"}],
                             "pronunciations": []}]}
        entry, _ = make_entry(source, wrong, "bank", None, {})
        self.assertEqual(entry["audit_status"], "missing-or-unaligned")
        self.assertIsNone(entry["senses"][0]["english_gloss"])

    def test_ecdict_is_entry_level_and_legacy_phonetic_is_not_ipa(self):
        row = json.dumps({"translation": "银行", "definition": "institution", "phonetic": "bæŋk",
                          "tag": "cet4 ielts", "bnc": "406", "frq": "0", "collins": "4",
                          "oxford": "", "exchange": ""})
        entry, _ = make_entry(curated("bank", "b"), None, "bank", row, {"bank": ["B AE1 NG K"]})
        self.assertEqual(entry["ecdict"]["zh_fallback"], "银行")
        self.assertEqual(entry["ecdict"]["frequency_ranks"], {"bnc": 406})
        self.assertEqual(entry["senses"][0]["learner_explanation_zh"], "中文解释")
        self.assertEqual(entry["ecdict"]["legacy_phonetic"], "bæŋk")
        self.assertIn("ARPABET", [item["notation"] for item in entry["pronunciations"]])
        self.assertEqual([item["code"] for item in entry["ecdict"]["exam_tags"]], ["cet4", "ielts"])

    def test_display_order_preserves_source_order_but_prioritizes_core_common_meanings(self):
        source = curated("apple", "a")
        source["pos_groups"] = [
            {"pos": "name", "etymology_id": "et1", "forms": [], "pronunciations": [],
             "meanings": [{"sense_id": "s1", "priority": "core", "learner_explanation": "纽约昵称"}]},
            {"pos": "noun", "etymology_id": "et2", "forms": [], "pronunciations": [],
             "meanings": [{"sense_id": "s1", "priority": "core", "learner_explanation": "水果"},
                          {"sense_id": "s2", "priority": "rare", "learner_explanation": "罕见义"}]},
        ]
        entry, _ = make_entry(source, None, "apple", None, {})
        self.assertEqual([item["learner_explanation_zh"] for item in entry["senses"]],
                         ["纽约昵称", "水果", "罕见义"])
        self.assertEqual([item["display_order"] for item in entry["senses"]], [1, 0, 2])

    def test_missing_function_pos_has_independent_source_and_keeps_ecdict_at_entry_scope(self):
        supplement = {"word": "the", "source": {"url": "https://kaikki.org/the.jsonl",
            "raw_sha256": "a" * 64, "wiktionary_dump": "2026-09-02",
            "kaikki_extraction": "2026-09-25"}, "groups": [{"pos": "article", "record_index": 0,
            "etymology_number": 1, "senses": [{"sense_index": 0,
                "glosses": ["Definite article", "Before an identifiable noun"],
                "tags": [], "topics": []}]}]}
        row = json.dumps({"translation": "这；那", "definition": "", "phonetic": "", "tag": "",
                          "bnc": "", "frq": "1", "collins": "", "oxford": "", "exchange": ""})
        entry, _ = make_entry(curated("the", "source-the", "adv"), None, "the", row, {}, supplement)
        self.assertEqual([sense["pos"] for sense in entry["senses"]], ["adv", "article"])
        self.assertEqual([sense["display_order"] for sense in entry["senses"]], [1, 0])
        self.assertEqual(entry["senses"][1]["source_ref"]["source"], FUNCTION_SOURCE)
        self.assertEqual(entry["senses"][1]["source_ref"]["cross_snapshot_alignment"], "not-attempted")
        self.assertIsNone(entry["senses"][1]["learner_explanation_zh"])
        self.assertEqual(entry["ecdict"]["zh_fallback"], "这；那")
        fallback, _ = make_entry(None, None, "the", row, {}, supplement)
        self.assertEqual(fallback["origin"], "ecdict-fallback")
        self.assertEqual([sense["pos"] for sense in fallback["senses"]], ["article"])

    def test_full_small_build_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dist = root / "distribution.gz"
            audit_path = root / "audit.gz"
            csv_path = root / "ecdict.csv"
            cmu_path = root / "cmu.txt"
            wn_path = root / "wordnet.zip"
            # 审计包故意逆序，证明按 entry_id 关联而非按行号关联。
            with gzip.open(dist, "wt", encoding="utf-8") as stream:
                for item in (curated("May", "may-name", "name"), curated("may", "may-verb", "verb")):
                    stream.write(json.dumps(item) + "\n")
            with gzip.open(audit_path, "wt", encoding="utf-8") as stream:
                for item in (audit("may", "may-verb", "verb"), audit("May", "may-name", "name")):
                    stream.write(json.dumps(item) + "\n")
            with csv_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["word", "translation", "definition", "phonetic", "tag", "bnc", "frq", "collins", "oxford", "exchange"])
                writer.writeheader()
                for word, rank in (("May", ""), ("may", "10"), ("fallback", "20"), ("the", "5")):
                    writer.writerow({"word": word, "translation": word + "中文", "definition": "", "phonetic": "",
                                     "tag": "cet4", "bnc": "", "frq": rank, "collins": "", "oxford": "", "exchange": ""})
            cmu_path.write_text("may M EY1\nfallback F AO1 L B AE2 K\n", encoding="utf-8")
            with zipfile.ZipFile(wn_path, "w") as archive:
                archive.writestr("entries-m.json", json.dumps({"may": {"v": {"sense": [{"id": "may%2:test", "synset": "1-v"}]}}}))
                archive.writestr("verb.stative.json", json.dumps({"1-v": {"definition": ["have permission"], "partOfSpeech": "v", "hypernym": []}}))
            paths = {"open-dictionary-v2-distribution-jsonl-gz": dist,
                     "open-dictionary-v2-audit-jsonl-gz": audit_path,
                     "ecdict-csv": csv_path, "cmudict-dict": cmu_path,
                     "english-wordnet-2025-core": wn_path}
            supplement_path = root / "function-words.jsonl"
            supplement_path.write_text(json.dumps({"word": "the", "source": {
                "url": "https://kaikki.org/the.jsonl", "raw_sha256": "a" * 64,
                "wiktionary_dump": "2026-09-02", "kaikki_extraction": "2026-09-25"},
                "groups": [{"pos": "article", "record_index": 0, "etymology_number": 1,
                    "senses": [{"sense_index": 0, "glosses": ["The definite article"],
                                "tags": [], "topics": []}]}]}) + "\n", encoding="utf-8")
            paths["wiktextract-function-words"] = supplement_path
            lock = root / "lock.json"
            lock.write_text(json.dumps({"artifacts": [{"id": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                                        "bytes": path.stat().st_size} for name, path in paths.items()]}))
            output = root / "out"
            manifest = build(paths, lock, output, core_size=2)
            second = build(paths, lock, root / "out-again", core_size=2)
            self.assertEqual(manifest["release_status"], "candidate-needs-human-review")
            self.assertEqual(manifest["outputs"], second["outputs"])
            self.assertEqual(manifest["counts"]["total_entries"], 4)
            self.assertEqual(manifest["counts"]["function_word_senses"], 1)
            self.assertEqual(manifest["counts"]["audit_aligned"], 2)
            self.assertEqual(len(lookup(output / "dictionary.sqlite", "May")), 2)
            self.assertEqual(lookup(output / "dictionary.sqlite", "fallback")[0]["origin"], "ecdict-fallback")
            self.assertEqual(lookup(output / "dictionary.sqlite", "the")[0]["senses"][0]["pos"], "article")
            self.assertEqual(lookup(output / "dictionary.sqlite", "mays")[0]["headword"], "may")
            self.assertEqual(wordnet_candidates(output / "dictionary.sqlite", "may")[0]["mapping_status"], "unmapped-headword-candidate")
            verify_package(output)
            self.assertEqual(verify_content(output)["entries"], 4)
            quality = report(output / "dictionary.sqlite", root / "qa")
            self.assertEqual(quality["counts"]["entries"], 4)
            with (root / "qa" / "review-sample.csv").open(newline="", encoding="utf-8") as stream:
                sample = next(csv.DictReader(stream))
            self.assertIn("english_gloss_preview", sample)
            self.assertEqual(sample["review_status"], "pending")
            audio_dir = output / "audio"
            (audio_dir / "files").mkdir(parents=True)
            (audio_dir / "files" / "test.ogg").write_bytes(b"OggSfixture")
            size, sha = file_hash(audio_dir / "files" / "test.ogg")
            audio_manifest = {"schema_version": "leximeet.audio.v1", "offline_asset_count": 1,
                              "assets": [{"path": "files/test.ogg", "bytes": size, "sha256": sha,
                                          "artist": "Fixture", "license": "CC0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                                          "source_page": "https://commons.wikimedia.org/wiki/File:fixture.ogg", "attribution": "Fixture"}]}
            (audio_dir / "manifest.json").write_text(json.dumps(audio_manifest))
            core_size, core_sha = file_hash(output / "manifest.json")
            audio_size, audio_sha = file_hash(audio_dir / "manifest.json")
            (output / "edition.with-audio.json").write_text(json.dumps({"schema_version": "leximeet.edition.v1",
                "edition": "with-audio",
                "dictionary_manifest_bytes": core_size, "dictionary_manifest_sha256": core_sha,
                "audio_manifest_bytes": audio_size, "audio_manifest_sha256": audio_sha}))
            first_packages = package(output, root / "dist-one")
            second_packages = package(output, root / "dist-two")
            self.assertEqual(first_packages["artifacts"], second_packages["artifacts"])
            core_archive = root / "dist-one" / "leximeet-dictionary-0.0.1-core.tar.gz"
            core_asset = next(item for item in first_packages["artifacts"] if item["edition"] == "core")
            core_manifest = verify_core_archive(core_archive, core_asset["sha256"])
            self.assertEqual(core_manifest["entry_count"], 2)
            with tarfile.open(core_archive, "r:gz") as archive:
                self.assertFalse(any(item.name.endswith("dictionary.sqlite") for item in archive))
                self.assertTrue(any(item.name.endswith("DATA-LICENSE.md") for item in archive))
            with self.assertRaisesRegex(ValueError, "外层 SHA-256"):
                verify_core_archive(core_archive, "0" * 64)
            with tarfile.open(root / "dist-one" / "leximeet-dictionary-0.0.1-no-audio.tar.gz", "r:gz") as archive:
                self.assertFalse(any("/audio/files/" in name for name in archive.getnames()))
            with tarfile.open(root / "dist-one" / "leximeet-dictionary-0.0.1-with-audio.tar.gz", "r:gz") as archive:
                self.assertTrue(any("/audio/files/" in name for name in archive.getnames()))
            for asset in first_packages["artifacts"]:
                if asset["edition"] != "core":
                    result = verify_archive(root / "dist-one" / asset["file"], asset["sha256"])
                    self.assertEqual(result["edition"], asset["edition"])
                    with tarfile.open(root / "dist-one" / asset["file"], "r:gz") as archive:
                        archive.extractall(root / "installed", filter="data")
                    installed = root / "installed" / asset["file"].removesuffix(".tar.gz")
                    self.assertEqual(verify_package(installed)["counts"]["total_entries"], 4)
            with (output / "core.jsonl.gz").open("ab") as stream:
                stream.write(b"damage")
            with self.assertRaisesRegex(ValueError, "词包损坏"):
                verify_package(output)


if __name__ == "__main__":
    unittest.main()
