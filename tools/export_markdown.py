"""从已校验的只读 SQLite 流式导出全量词条 Markdown 索引。"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sqlite3
import tempfile
from collections import Counter
from contextlib import closing
from pathlib import Path


def cell(value: object) -> str:
    """转义 Markdown 表格控制字符，并保留原释义中的换行。"""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return html.escape(text, quote=False).replace("|", "&#124;").replace("\t", " ").replace("\n", "<br>")


def senses_cell(senses: list[dict]) -> str:
    """逐义项标出词性、英文原义和中文学习解释，不借用词条级回退冒充逐义翻译。"""
    parts = []
    for number, sense in enumerate(sorted(senses, key=lambda item: item["display_order"]), 1):
        glosses = [f"{number}. {cell(sense.get('pos') or '未标词性')}"]
        for label, field in (("英文原义", "english_gloss"), ("中文短释", "short_gloss"),
                             ("中文解释", "learner_explanation_zh")):
            if sense.get(field):
                glosses.append(f"{label}：{cell(sense[field])}")
        if len(glosses) == 1:
            glosses.append("原来源未提供文字释义")
        parts.append("；".join(glosses))
    return "<br><br>".join(parts)


def export(db_path: Path, out_path: Path) -> dict:
    """一行词条对应一行表格，边读 SQLite 边写文件，避免把 81 万词加载到内存。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    temp_path: Path | None = None
    try:
        with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            version = db.execute("SELECT value FROM metadata WHERE key='dictionary_version'").fetchone()[0]
            expected = db.execute("SELECT count(*) FROM entries").fetchone()[0]
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=out_path.parent,
                                             prefix=".leximeet-details-", suffix=".tmp", delete=False) as stream:
                temp_path = Path(stream.name)
                stream.write(f"# LexiMeet {cell(version)} 全量词条与释义\n\n")
                stream.write("本表由已生成的 `dictionary.sqlite` 导出；同形异义词分别保留词条 ID。")
                stream.write("逐义项列中的中英文仅按源字段呈现；ECDICT 中文/英文是**词条级回退**，")
                stream.write("并未与左侧义项自动对齐。空白表示该来源没有提供，不表示该词无意义。")
                stream.write("本文件很大，阅读或检索时建议分块打开；客户端请使用 SQLite 或 JSONL 包。\n\n")
                stream.write("| 序号 | 词头 | 来源层 | 逐义项释义 | ECDICT 中文回退 | ECDICT 英文回退 | 学习者总览 | 词条 ID |\n")
                stream.write("| ---: | --- | --- | --- | --- | --- | --- | --- |\n")
                cursor = db.execute("SELECT payload FROM entries ORDER BY lookup_key, headword, entry_id")
                for (payload,) in cursor:
                    entry = json.loads(payload)
                    ecdict = entry["ecdict"]
                    senses = entry["senses"]
                    stats["entries"] += 1
                    stats[entry["origin"]] += 1
                    stats["senses"] += len(senses)
                    if not senses and not ecdict.get("zh_fallback") and not ecdict.get("en_fallback"):
                        stats["entries_without_written_definition"] += 1
                    row = (stats["entries"], entry["headword"], entry["origin"], senses_cell(senses),
                           ecdict.get("zh_fallback"), ecdict.get("en_fallback"),
                           entry.get("headword_summary_zh"), entry["entry_id"])
                    stream.write("| " + " | ".join(cell(value) if index != 3 else value
                                                   for index, value in enumerate(row)) + " |\n")
        if stats["entries"] != expected:
            raise ValueError(f"导出行数不符：{stats['entries']} != {expected}")
        os.replace(temp_path, out_path)
        digest = hashlib.sha256()
        with out_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result = {"dictionary_version": version, "source_db": str(db_path), "file": str(out_path),
                  "bytes": out_path.stat().st_size, "sha256": digest.hexdigest(), "counts": dict(stats)}
        out_path.with_suffix(".stats.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(export(arguments.db, arguments.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
