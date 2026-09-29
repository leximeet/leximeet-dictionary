"""0.0.2 核心版发布包：学习词卡与既有离线音频组成独立可校验资产。"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from .builder import file_hash
from .entry_v2 import SCHEMA as ENTRY_SCHEMA, export_core
from .learning import SCHEMA as LEARNING_SCHEMA, _learning_for_entry_db
from .learning_verify import verify_learning
from .release import MAX_ASSET_BYTES, _asset_path, verify_release

SCHEMA = "leximeet.release.v2"
VERSION = "0.0.2"


def _copy(source: Path, out: Path, name: str, assets: dict) -> None:
    target = _asset_path(out, name)
    shutil.copyfile(source, target)
    size, sha256 = file_hash(target)
    if size >= MAX_ASSET_BYTES:
        raise ValueError(f"发布资产超过单文件限制：{name}")
    assets[name] = {"bytes": size, "sha256": sha256}


def build_core_release(base: Path, db_path: Path, source_lock: Path, out: Path) -> dict:
    """从已发布的 0.0.1 核心资产升级；助记覆盖数如实写入清单。"""
    base_manifest_sha256 = file_hash(base / "release.json")[1]
    lock = json.loads(source_lock.read_text(encoding="utf-8"))
    if lock.get("base_release_manifest_sha256") != base_manifest_sha256:
        raise ValueError("0.0.1 基础 Release 与固定来源锁不一致")
    base_manifest = json.loads((base / "release.json").read_text(encoding="utf-8"))
    core_file = _asset_path(base, base_manifest["editions"]["core"]["entries"])
    quality = verify_learning(core_file, db_path)
    verify_release(base, "core", deep=True)
    with closing(sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)) as db:
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
    if metadata.get("source_lock_sha256") != file_hash(source_lock)[1]:
        raise ValueError("学习索引与来源锁文件哈希不一致")
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("0.0.2 发布目录必须为空")
    out.mkdir(parents=True, exist_ok=True)
    repository = Path(__file__).resolve().parent.parent
    assets: dict[str, dict] = {}
    # 保留同名音频资产和字节哈希；端侧升级时可以直接复用已安装的分片。
    inherited = [name for name in base_manifest["editions"]["core"]["assets"]
                 if name.startswith(("audio-core-", "core.audio-index", "audio-tools.",
                                     "audio-sources.", "notice-"))]
    for name in inherited:
        _copy(_asset_path(base, name), out, name, assets)
    for name, source in (
            ("core.entries.v2.jsonl.gz", None),
            ("core.learning.sqlite", db_path),
            ("learning-sources.lock.json", source_lock),
            ("LICENSE", repository / "LICENSE"),
            ("DATA-LICENSE.md", repository / "DATA-LICENSE.md")):
        if source is None:
            exported = export_core(core_file, db_path, out / name)
            assets[name] = {"bytes": exported["bytes"], "sha256": exported["sha256"]}
        else:
            _copy(source, out, name, assets)
    for notice_name in ("DICTIONARYBYGPT4-LICENSE.md", "QWERTY-LEARNER-LICENSE.md"):
        target_name = "notice-" + notice_name
        if target_name not in assets:
            _copy(repository / "notices" / "v0.0.2" / notice_name, out, target_name, assets)
    names = sorted(assets)
    manifest = {
        "schema_version": SCHEMA, "dictionary_version": VERSION,
        "entry_schema": ENTRY_SCHEMA, "learning_schema": LEARNING_SCHEMA,
        "base_release": {"version": "0.0.1",
                         "manifest_sha256": base_manifest_sha256,
                         "core_entries_sha256": file_hash(core_file)[1]},
        "assets": assets,
        "editions": {"core": {
            "entry_count": quality["core_entries"],
            "mnemonic_covered_entry_count": quality["mnemonic_covered_entries"],
            "audio_covered_entry_count": quality["core_entries"],
            "entries": "core.entries.v2.jsonl.gz",
            "learning_db": "core.learning.sqlite",
            "audio_index": base_manifest["editions"]["core"]["audio_index"],
            "assets": names,
        }},
    }
    # release.json 最后写入；没有它的中断目录不能被误认为完整词包。
    (out / "release.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return manifest


def verify_core_release(root: Path, deep: bool = False) -> dict:
    """先核对所有资产哈希；深检再检查词卡、词书、助记与音频逐词关联。"""
    manifest = json.loads((root / "release.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version"), manifest.get("dictionary_version"),
            manifest.get("entry_schema"), manifest.get("learning_schema")) != (
                SCHEMA, VERSION, ENTRY_SCHEMA, LEARNING_SCHEMA):
        raise ValueError("0.0.2 Release 结构或版本不兼容")
    if set(manifest.get("editions", {})) != {"core"}:
        raise ValueError("0.0.2 只交付核心版")
    edition = manifest["editions"]["core"]
    names = edition["assets"]
    assets = manifest["assets"]
    if (len(names) != len(set(names)) or set(names) != set(assets)
            or {item.name for item in root.iterdir() if item.is_file()}
            != set(names) | {"release.json"}):
        raise ValueError("0.0.2 Release 资产清单不完整或有多余文件")
    for name in names:
        meta = assets[name]
        if (file_hash(_asset_path(root, name)) != (meta["bytes"], meta["sha256"])
                or meta["bytes"] >= MAX_ASSET_BYTES):
            raise ValueError(f"0.0.2 Release 资产损坏：{name}")
    required = {edition["entries"], edition["learning_db"], edition["audio_index"],
                "learning-sources.lock.json", "LICENSE", "DATA-LICENSE.md",
                "audio-tools.lock.json", "audio-sources.json",
                "notice-DICTIONARYBYGPT4-LICENSE.md", "notice-QWERTY-LEARNER-LICENSE.md"}
    if (not required.issubset(names) or not any(name.startswith("audio-core-")
                                                and name.endswith(".pack") for name in names)):
        raise ValueError("0.0.2 Release 缺少必要资产")
    source_lock = json.loads(_asset_path(root, "learning-sources.lock.json").read_text(encoding="utf-8"))
    if source_lock.get("base_release_manifest_sha256") != manifest["base_release"]["manifest_sha256"]:
        raise ValueError("0.0.2 与固定的基础 Release 不一致")
    if (edition["entry_count"] < 1
            or not 0 <= edition["mnemonic_covered_entry_count"] <= edition["entry_count"]
            or edition["entry_count"] != edition["audio_covered_entry_count"]):
        raise ValueError("0.0.2 核心词、助记及音频覆盖数无效")
    result = {"edition": "core", "entry_count": edition["entry_count"],
              "mnemonic_covered_entry_count": edition["mnemonic_covered_entry_count"],
              "audio_covered_entry_count": edition["audio_covered_entry_count"],
              "assets": len(names), "deep": deep}
    if not deep:
        return result

    db_path = _asset_path(root, edition["learning_db"])
    with closing(sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("学习索引 SQLite 损坏")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("学习索引目录外键无效")
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
        if (metadata.get("schema_version") != LEARNING_SCHEMA
                or metadata.get("source_lock_sha256")
                != assets["learning-sources.lock.json"]["sha256"]
                or metadata.get("base_core_sha256")
                != manifest["base_release"]["core_entries_sha256"]):
            raise ValueError("学习索引与来源清单不一致")
        seen: set[str] = set()
        with gzip.open(_asset_path(root, edition["entries"]), "rt", encoding="utf-8") as stream:
            for line in stream:
                entry = json.loads(line)
                entry_id = entry["entry_id"]
                card = entry["learning"]
                if (entry.get("schema_version") != ENTRY_SCHEMA or entry_id in seen
                        or card.get("schema_version") != "leximeet.learning-card.v1"
                        or card["audio"]["offline_index_entry_id"] != entry_id
                        or not isinstance(card["lexical"], dict)
                        or not all(isinstance(card["lexical"].get(key), list) for key in (
                            "synonyms", "antonyms", "related_words", "phrases"))
                        or not isinstance(card["practice"].get("questions"), list)
                        or not isinstance(card["practice"].get("attested_examples"), list)
                        or not isinstance(card.get("illustrations"), list)
                        or not isinstance(card.get("source_signals"), list)
                        or not isinstance(card["audio"].get("alternate_candidates"), list)):
                    raise ValueError("核心词条结构、助记或音频引用无效")
                learning = _learning_for_entry_db(db, entry_id)
                if (entry["learning"]["collections"] != learning["catalogs"]
                        or entry["learning"]["mnemonics"] != learning["mnemonics"]):
                    raise ValueError("词卡与学习索引内容不一致")
                senses = {sense["sense_id"] for sense in entry["senses"]}
                if any(not set(item["sense_ids"]).issubset(senses)
                       for item in learning["catalogs"]):
                    raise ValueError("词书成员引用了无效义项")
                seen.add(entry_id)
        if (len(seen) != edition["entry_count"]
                or db.execute("SELECT count(DISTINCT entry_id) FROM mnemonics").fetchone()[0]
                != edition["mnemonic_covered_entry_count"]):
            raise ValueError("核心词条与学习索引覆盖数不一致")
        # 数据表未对旧版词条建外键；从发布包本身核对，避免遗留孤儿成员。
        for table in ("members", "mnemonics"):
            referenced = {row[0] for row in db.execute(f"SELECT DISTINCT entry_id FROM {table}")}
            if not referenced.issubset(seen):
                raise ValueError("学习索引引用了核心版以外的词条")

    audio_seen: set[str] = set()
    offsets: dict[str, int] = {}
    streams = {}
    try:
        with gzip.open(_asset_path(root, edition["audio_index"]), "rt", encoding="utf-8") as stream:
            for line in stream:
                item = json.loads(line)
                entry_id, shard = item["entry_id"], item["shard"]
                if (entry_id not in seen or entry_id in audio_seen or shard not in names
                        or item["offset"] != offsets.get(shard, 0) or item["bytes"] < 1):
                    raise ValueError("离线音频索引引用无效")
                if shard not in streams:
                    streams[shard] = _asset_path(root, shard).open("rb")
                audio = streams[shard]
                audio.seek(item["offset"])
                payload = audio.read(item["bytes"])
                if (len(payload) != item["bytes"]
                        or hashlib.sha256(payload).hexdigest() != item["sha256"]
                        or not payload.startswith(b"OggS")):
                    raise ValueError("离线音频片段损坏")
                audio_seen.add(entry_id)
                offsets[shard] = item["offset"] + item["bytes"]
    finally:
        for stream in streams.values():
            stream.close()
    if (audio_seen != seen or any(offsets[shard] != assets[shard]["bytes"]
                                  for shard in offsets)
            or len(audio_seen) != edition["audio_covered_entry_count"]):
        raise ValueError("逐词音频覆盖不完整")
    return result
