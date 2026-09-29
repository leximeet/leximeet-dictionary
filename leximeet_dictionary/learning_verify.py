"""核验核心学习索引与原词卡、目录、助记之间的真实关联。"""

from __future__ import annotations

import gzip
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .builder import file_hash
from .learning import SCHEMA


def verify_learning(core: Path, db_path: Path) -> dict:
    """检查所有引用，报告实际助记覆盖数；允许尚无助记的词卡。"""
    entries: dict[str, set[str]] = {}
    with gzip.open(core, "rt", encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            if entry.get("schema_version") != "leximeet.entry.v1":
                raise ValueError("核心词卡结构版本错误")
            entry_id = entry["entry_id"]
            if entry_id in entries:
                raise ValueError("核心词卡存在重复 ID")
            entries[entry_id] = {item["sense_id"] for item in entry["senses"]}

    with closing(sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("学习索引 SQLite 损坏")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("学习索引目录外键无效")
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
        if (metadata.get("schema_version") != SCHEMA
                or metadata.get("base_core_sha256") != file_hash(core)[1]):
            raise ValueError("学习索引与核心词包版本或哈希不一致")
        catalogs = {row[0]: row[1] for row in db.execute(
            "SELECT catalog_id,category FROM catalogs")}
        members = 0
        scoped = 0
        positions: set[tuple[str, int]] = set()
        for catalog_id, entry_id, position, raw_senses, raw_payload in db.execute(
                "SELECT catalog_id,entry_id,position,sense_ids,source_payload FROM members"):
            if catalog_id not in catalogs or entry_id not in entries or position < 1:
                raise ValueError("词书成员引用或位置无效")
            if (catalog_id, position) in positions:
                raise ValueError("同一目录出现重复顺序")
            positions.add((catalog_id, position))
            senses = json.loads(raw_senses)
            payload = json.loads(raw_payload)
            if (not isinstance(senses, list) or not set(senses).issubset(entries[entry_id])
                    or not isinstance(payload, dict)):
                raise ValueError("词书成员义项或来源数据无效")
            if catalog_id.startswith("subject:topic:"):
                if catalogs[catalog_id] != "subject" or not senses:
                    raise ValueError("义项领域目录缺少对应义项")
                scoped += 1
            members += 1
        covered: set[str] = set()
        mnemonic_rows = 0
        for entry_id, content, raw_provenance in db.execute(
                "SELECT entry_id,content,provenance FROM mnemonics"):
            if entry_id not in entries or not content.strip():
                raise ValueError("助记引用或内容无效")
            if not isinstance(json.loads(raw_provenance), dict):
                raise ValueError("助记来源数据无效")
            covered.add(entry_id)
            mnemonic_rows += 1
    missing = len(entries) - len(covered)
    return {"schema_version": SCHEMA, "core_entries": len(entries),
            "catalogs": len(catalogs), "members": members,
            "sense_scoped_members": scoped, "mnemonic_rows": mnemonic_rows,
            "mnemonic_covered_entries": len(covered), "missing_mnemonics": missing}
