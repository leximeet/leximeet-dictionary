"""Commons 素材筛选和缓存键的回归测试。"""

import unittest
import sqlite3
import tempfile
import hashlib
import json
import tarfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from leximeet_dictionary.audio import (cache_key, cache_on_demand, file_title, install_locked_audio,
                                       review, title_matches_word, verify_audio, write_audio_review_sheet)


class AudioTests(unittest.TestCase):
    def test_commons_title_and_part_of_speech(self):
        url = "https://upload.wikimedia.org/wikipedia/commons/f/f3/En-us-record-noun.ogg"
        self.assertEqual(file_title(url), "File:En-us-record-noun.ogg")
        self.assertTrue(title_matches_word("File:En-us-record-noun.ogg", "record", "noun"))
        self.assertFalse(title_matches_word("File:En-us-record-noun.ogg", "record", "verb"))
        self.assertIsNone(file_title("https://example.com/En-us-record-noun.ogg"))

    def test_license_metadata_requires_author_and_allowlisted_license(self):
        base = {"url": "https://upload.wikimedia.org/wikipedia/commons/4/4d/En-us-bank.ogg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:En-us-bank.ogg",
                "size": 11137, "mime": "application/ogg",
                "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 3.0"},
                                "LicenseUrl": {"value": "http://creativecommons.org/licenses/by-sa/3.0/"},
                                "Artist": {"value": "<a>Dvortygirl</a>"}}}
        approved, reason = review(base)
        self.assertIsNone(reason)
        self.assertEqual(approved["artist"], "Dvortygirl")
        self.assertTrue(approved["license_url"].startswith("https://"))
        base["extmetadata"]["Artist"]["value"] = ""
        self.assertEqual(review(base)[1], "missing-artist-or-license-url")
        base["extmetadata"]["Artist"]["value"] = "No machine-readable author provided. Someone assumed (based on copyright claims)."
        self.assertEqual(review(base)[1], "missing-artist-or-license-url")

    def test_cache_key_distinguishes_voice_speed_provider(self):
        a = cache_key("read", "en-US", "commons", "human", "1", "2025")
        b = cache_key("read", "en-US", "device-tts", "human", "1", "2025")
        self.assertNotEqual(a, b)

    def test_online_failure_returns_no_audio_without_changing_dictionary(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "dictionary.sqlite"
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("CREATE TABLE entries(entry_id TEXT,headword TEXT,lookup_key TEXT)")
                db.execute("CREATE TABLE audio_candidates(entry_id TEXT,headword TEXT,pos TEXT,url TEXT)")
                db.execute("INSERT INTO entries VALUES ('bank-id','bank','bank')")
                db.execute("INSERT INTO audio_candidates VALUES ('bank-id','bank','noun',?)",
                           ("https://upload.wikimedia.org/wikipedia/commons/4/4d/En-us-bank.ogg",))
                db.commit()
            with patch("leximeet_dictionary.audio.commons_info", side_effect=OSError("offline")):
                self.assertIsNone(cache_on_demand(db_path, "bank", Path(temp) / "cache"))
            with closing(sqlite3.connect(db_path)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM entries").fetchone()[0], 1)

    def test_checked_in_commons_snapshot_matches_audio_lock(self):
        """固定来源快照必须与逐文件署名清单一致，CI 不依赖 Commons 高频请求。"""
        root = Path(__file__).resolve().parents[1]
        lock = json.loads((root / "audio.lock.json").read_text(encoding="utf-8"))
        archive_path = root / "sources/commons-audio-v0.0.1.tar.gz"
        checksum = (root / "sources/commons-audio-v0.0.1.sha256").read_text().split()[0]
        self.assertEqual(hashlib.sha256(archive_path.read_bytes()).hexdigest(), checksum)
        expected = {asset["path"]: asset for asset in lock["assets"]}
        self.assertEqual(len(expected), 436)
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            self.assertEqual({member.name for member in members}, set(expected))
            for member in members:
                self.assertTrue(member.isfile())
                payload = archive.extractfile(member).read()
                asset = expected[member.name]
                self.assertEqual(len(payload), asset["bytes"])
                self.assertEqual(hashlib.sha256(payload).hexdigest(), asset["sha256"])

    def test_locked_audio_reuses_only_matching_file_and_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = b"OggSfixture"
            url = "https://upload.wikimedia.org/wikipedia/commons/f/f3/En-us-bank.ogg"
            candidate = {"entry_id": "bank-id", "headword": "bank", "rank": 1,
                         "pos": "noun", "candidate_url": url, "title": "File:En-us-bank.ogg"}
            asset = {**candidate, "url": url, "path": "files/bank-id.ogg", "bytes": len(audio),
                     "sha256": hashlib.sha256(audio).hexdigest(), "artist": "Fixture",
                     "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                     "source_page": "https://commons.wikimedia.org/wiki/File:En-us-bank.ogg",
                     "attribution": "Fixture · CC BY-SA 4.0"}
            locked = {"schema_version": "leximeet.audio.v1", "dictionary_version": "0.0.1",
                      "requested": 1, "selected_candidates": 1, "offline_asset_count": 1,
                      "assets": [asset], "skipped": []}
            lock_path = root / "audio.lock.json"
            lock_path.write_text(json.dumps(locked), encoding="utf-8")
            source_lock = root / "sources.lock.json"
            source_lock.write_text(json.dumps({"artifacts": [{"id": "audio-commons-0.0.1-lock",
                "bytes": lock_path.stat().st_size, "sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest()}]}))
            source = root / "cached"
            (source / "files").mkdir(parents=True)
            (source / asset["path"]).write_bytes(audio)
            (root / "manifest.json").write_text("{}", encoding="utf-8")
            with patch("leximeet_dictionary.audio.selected_candidates", return_value=[candidate]):
                result = install_locked_audio(root / "dictionary.sqlite", root / "audio", lock_path,
                                              source_lock, source)
            self.assertEqual(result["offline_asset_count"], 1)
            self.assertEqual(verify_audio(root / "audio")["assets"][0]["sha256"], asset["sha256"])
            sheet = write_audio_review_sheet(root / "audio/manifest.json", root / "review.csv")
            self.assertEqual(sheet["sample_size"], 1)
            self.assertIn("pending", (root / "review.csv").read_text())
            (source / asset["path"]).write_bytes(b"changed")
            with patch("leximeet_dictionary.audio.selected_candidates", return_value=[candidate]):
                with self.assertRaisesRegex(ValueError, "固定录音文件损坏"):
                    install_locked_audio(root / "dictionary.sqlite", root / "bad-audio", lock_path,
                                         source_lock, source)


if __name__ == "__main__":
    unittest.main()
