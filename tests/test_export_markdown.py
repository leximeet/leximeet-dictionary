"""全量 Markdown 导出最容易出错的范围与转义契约。"""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from tools.export_markdown import export


class ExportMarkdownTests(unittest.TestCase):
    def test_all_entries_and_all_senses_keep_ecdict_at_entry_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "dictionary.sqlite"
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT)")
                db.execute("INSERT INTO metadata VALUES ('dictionary_version', '0.0.1')")
                db.execute("CREATE TABLE entries(entry_id TEXT PRIMARY KEY, headword TEXT, lookup_key TEXT, payload TEXT)")
                curated = {"entry_id": "id-1", "headword": "A|B", "origin": "curated",
                           "headword_summary_zh": "总览", "editorial": {"display_zh": "审校词义"},
                           "ecdict": {"zh_fallback": "词条级\n中文", "en_fallback": ""},
                           "senses": [
                               {"display_order": 1, "pos": "verb", "english_gloss": "second",
                                "short_gloss": "第二", "learner_explanation_zh": "第二解释"},
                               {"display_order": 0, "pos": "noun", "english_gloss": "first | <literal>",
                                "short_gloss": "第一", "learner_explanation_zh": "第一解释"}]}
                fallback = {"entry_id": "id-2", "headword": "blank", "origin": "ecdict-fallback",
                            "headword_summary_zh": None, "ecdict": {"zh_fallback": None, "en_fallback": None},
                            "senses": []}
                for entry in (curated, fallback):
                    db.execute("INSERT INTO entries VALUES (?,?,?,?)", (entry["entry_id"], entry["headword"],
                               entry["headword"].casefold(), json.dumps(entry)))
                db.commit()
            out = Path(temp) / "details.md"
            result = export(db_path, out)
            content = out.read_text(encoding="utf-8")
            self.assertEqual(result["counts"], {"entries": 2, "curated": 1, "senses": 2,
                                                "ecdict-fallback": 1, "entries_without_written_definition": 1})
            self.assertEqual(sum(line.startswith("| ") for line in content.splitlines()), 4)
            self.assertIn("A&#124;B", content)
            self.assertIn("first &#124; &lt;literal&gt;", content)
            self.assertLess(content.index("1. noun"), content.index("2. verb"))
            self.assertIn("词条级<br>中文", content)
            self.assertIn("| 审校词义 | 词条级<br>中文 |", content)
            self.assertIn("id-2", content)
            self.assertTrue(out.with_suffix(".stats.json").is_file())


if __name__ == "__main__":
    unittest.main()
