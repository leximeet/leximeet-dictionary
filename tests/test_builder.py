"""词源对齐、大小写、失败回退和包校验的关键回归测试。"""

import csv
import gzip
import hashlib
import json
import tempfile
import tarfile
import unittest
import zipfile
from pathlib import Path

from leximeet_dictionary.builder import build, file_hash, lookup, make_entry, verify_package, wordnet_candidates
from leximeet_dictionary.package import package


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
                for word, rank in (("May", ""), ("may", "10"), ("fallback", "20")):
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
            lock = root / "lock.json"
            lock.write_text(json.dumps({"artifacts": [{"id": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                                        "bytes": path.stat().st_size} for name, path in paths.items()]}))
            output = root / "out"
            manifest = build(paths, lock, output, core_size=2)
            second = build(paths, lock, root / "out-again", core_size=2)
            self.assertEqual(manifest["outputs"], second["outputs"])
            self.assertEqual(manifest["counts"]["total_entries"], 3)
            self.assertEqual(manifest["counts"]["audit_aligned"], 2)
            self.assertEqual(len(lookup(output / "dictionary.sqlite", "May")), 2)
            self.assertEqual(lookup(output / "dictionary.sqlite", "fallback")[0]["origin"], "ecdict-fallback")
            self.assertEqual(lookup(output / "dictionary.sqlite", "mays")[0]["headword"], "may")
            self.assertEqual(wordnet_candidates(output / "dictionary.sqlite", "may")[0]["mapping_status"], "unmapped-headword-candidate")
            verify_package(output)
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
            (output / "edition.with-audio.json").write_text(json.dumps({"edition": "with-audio",
                "dictionary_manifest_bytes": core_size, "dictionary_manifest_sha256": core_sha,
                "audio_manifest_bytes": audio_size, "audio_manifest_sha256": audio_sha}))
            first_packages = package(output, root / "dist-one")
            second_packages = package(output, root / "dist-two")
            self.assertEqual(first_packages["artifacts"], second_packages["artifacts"])
            with tarfile.open(root / "dist-one" / "leximeet-dictionary-0.0.1-no-audio.tar.gz", "r:gz") as archive:
                self.assertFalse(any("/audio/files/" in name for name in archive.getnames()))
            with tarfile.open(root / "dist-one" / "leximeet-dictionary-0.0.1-with-audio.tar.gz", "r:gz") as archive:
                self.assertTrue(any("/audio/files/" in name for name in archive.getnames()))
            with (output / "core.jsonl.gz").open("ab") as stream:
                stream.write(b"damage")
            with self.assertRaisesRegex(ValueError, "词包损坏"):
                verify_package(output)


if __name__ == "__main__":
    unittest.main()
