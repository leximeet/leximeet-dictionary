"""按 0.0.1 核心词卡与学习索引组装 0.0.2 单词 JSON，不修改旧版资产。"""

from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path

from .builder import canonical, file_hash
from .learning import SCHEMA as LEARNING_SCHEMA, _learning_for_entry_db

SCHEMA = "leximeet.entry.v2"
LEARNING_CARD_SCHEMA = "leximeet.learning-card.v1"


def compose_entry(entry: dict, learning: dict) -> dict:
    """词卡保留已有字段；新增能力各有独立位置，空数组表示尚无内容。"""
    if entry.get("schema_version") != "leximeet.entry.v1":
        raise ValueError("仅支持由 leximeet.entry.v1 核心词卡组装")
    if entry["entry_id"] != learning["entry_id"]:
        raise ValueError("学习内容与词卡 entry_id 不一致")
    result = dict(entry)
    result["schema_version"] = SCHEMA
    result["base_entry_schema"] = "leximeet.entry.v1"
    result["learning"] = {
        "schema_version": LEARNING_CARD_SCHEMA,
        "collections": learning["catalogs"],
        "mnemonics": learning["mnemonics"],
        # 近反义、同根词和短语与义项分开；未来每条可携带 sense_id、来源和审核状态。
        "lexical": {
            "synonyms": [],
            "antonyms": [],
            "related_words": [],
            "phrases": [],
        },
        # 模拟练习与可核查的真实例句分开，避免把 AI 题误标为真题。
        "practice": {"questions": [], "attested_examples": []},
        "illustrations": [],
        "source_signals": [],
        "audio": {
            "offline_index_entry_id": entry["entry_id"],
            "alternate_candidates": [],
        },
    }
    return result


def _check_source(db: sqlite3.Connection, core: Path) -> None:
    metadata = dict(db.execute("SELECT key,value FROM metadata"))
    if metadata.get("schema_version") != LEARNING_SCHEMA:
        raise ValueError("学习索引结构版本不支持")
    if metadata.get("base_core_sha256") != file_hash(core)[1]:
        raise ValueError("核心词包与学习索引的输入哈希不一致")


def read_entry(core: Path, db_path: Path, word: str) -> dict | None:
    """为调试按词头组装一个完整 JSON；正式客户端可从自己的本地索引读取。"""
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
        _check_source(db, core)
        with gzip.open(core, "rt", encoding="utf-8") as stream:
            for line in stream:
                entry = json.loads(line)
                if entry["headword"] == word:
                    return compose_entry(entry, _learning_for_entry_db(db, entry["entry_id"]))
    return None


def export_core(core: Path, db_path: Path, out: Path) -> dict:
    """输出确定性 gzip JSONL：仅核心版，供各消费端快速导入。"""
    if out.exists():
        raise FileExistsError(f"输出已存在，请指定新路径：{out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
            _check_source(db, core)
            with gzip.open(core, "rt", encoding="utf-8") as source, out.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0,
                                   compresslevel=6) as target:
                    for line in source:
                        entry = json.loads(line)
                        merged = compose_entry(entry, _learning_for_entry_db(db, entry["entry_id"]))
                        target.write(canonical(merged).encode("utf-8") + b"\n")
                        count += 1
        size, sha256 = file_hash(out)
        return {"schema_version": SCHEMA, "entry_count": count, "bytes": size, "sha256": sha256}
    except BaseException:
        out.unlink(missing_ok=True)
        raise
