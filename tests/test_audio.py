"""Commons 素材筛选和缓存键的回归测试。"""

import unittest
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from leximeet_dictionary.audio import cache_key, cache_on_demand, file_title, review, title_matches_word


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


if __name__ == "__main__":
    unittest.main()
