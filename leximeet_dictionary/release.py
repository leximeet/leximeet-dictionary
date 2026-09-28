"""将固定词库与逐词音频交付为可分片下载的两个版本。"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from .builder import file_hash, verify_package
from .offline_audio import AUDIO_SCHEMA, CORE_WHERE, ordered_entries


RELEASE_SCHEMA = "leximeet.release.v1"
INDEX_SCHEMA = "leximeet.audio-index.v1"
MAX_ASSET_BYTES = 2_000_000_000  # GitHub Release 的单资产限制为 2 GiB，留出余量。
DEFAULT_SHARD_BYTES = 256 * 1024 * 1024


def _json_file(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_line(stream, value: dict) -> None:
    stream.write((json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")) + "\n").encode("utf-8"))


def _copy_asset(source: Path, out: Path, name: str, assets: dict) -> None:
    target = out / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    size, sha = file_hash(target)
    if size >= MAX_ASSET_BYTES:
        raise ValueError(f"发布资产超过 GitHub Release 单文件限制：{name}")
    assets[name] = {"bytes": size, "sha256": sha}


def _asset_path(root: Path, name: str) -> Path:
    """拒绝下载清单中的路径穿越和指向词包外部的符号链接。"""
    if (not isinstance(name, str) or not name or Path(name).is_absolute()
            or ".." in Path(name).parts or "\\" in name
            or name != Path(name).as_posix()):
        raise ValueError("Release 包含非法资产路径")
    target = root / name
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Release 资产指向词包目录之外")
    return target


def _split_asset(source: Path, out: Path, name: str, limit: int, assets: dict) -> dict:
    """大文件按固定字节数切片；客户端按 parts 顺序拼接后校验总哈希。"""
    parts = []
    with source.open("rb") as stream:
        number = 0
        while chunk := stream.read(limit):
            number += 1
            part = f"{name}.part-{number:04}"
            target = out / part
            target.write_bytes(chunk)
            size, sha = file_hash(target)
            assets[part] = {"bytes": size, "sha256": sha}
            parts.append(part)
    if not parts:
        raise ValueError(f"不允许发布空文件：{name}")
    size, sha = file_hash(source)
    return {"path": name, "parts": parts, "bytes": size, "sha256": sha}


def _assemble_parts(root: Path, spec: dict, out: Path) -> None:
    """流式重组并核对整个 SQLite；不要求把大文件一次装入内存。"""
    if out.exists():
        raise FileExistsError(f"重组输出已存在：{out}")
    digest = hashlib.sha256()
    size = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as target:
        for name in spec["parts"]:
            with _asset_path(root, name).open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
    if (size, digest.hexdigest()) != (spec["bytes"], spec["sha256"]):
        out.unlink()
        raise ValueError("重组后的 SQLite 与清单哈希不一致")


def assemble_sqlite(root: Path, out: Path) -> dict:
    """供桌面端、插件端参考：先验片，再重组完整版查询库。"""
    verify_release(root, "full")
    manifest = json.loads((root / "release.json").read_text(encoding="utf-8"))
    spec = manifest["editions"]["full"]["sqlite"]
    _assemble_parts(root, spec, out)
    return {"file": str(out), "bytes": spec["bytes"], "sha256": spec["sha256"]}


class _ShardWriter:
    """音频原样串接；索引记录字节范围，客户端无需先解压整片。"""

    def __init__(self, out: Path, group: str, limit: int):
        self.out = out
        self.group = group
        self.limit = limit
        self.number = 0
        self.stream = None
        self.name = None
        self.size = 0
        self.names: list[str] = []

    def add(self, payload: bytes) -> tuple[str, int]:
        if len(payload) > self.limit:
            raise ValueError("单条录音超过分片上限")
        if self.stream is None or self.size + len(payload) > self.limit:
            self.close()
            self.number += 1
            self.name = f"audio-{self.group}-{self.number:04}.pack"
            self.stream = (self.out / self.name).open("wb")
            self.names.append(self.name)
            self.size = 0
        offset = self.size
        self.stream.write(payload)
        self.size += len(payload)
        return self.name, offset

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def _clip(cache: sqlite3.Connection, cache_dir: Path, entry_id: str, headword: str) -> tuple[bytes, dict]:
    row = cache.execute("SELECT headword,path,bytes,sha256,kind,style,source_ref "
                        "FROM clips WHERE entry_id=?", (entry_id,)).fetchone()
    if row is None or row[0] != headword:
        raise ValueError(f"词条缺少已生成录音：{headword} ({entry_id})")
    path = cache_dir / row[1]
    if (Path(row[1]).is_absolute() or ".." in Path(row[1]).parts or
            not path.resolve().is_relative_to(cache_dir.resolve()) or not path.is_file()):
        raise ValueError(f"录音路径无效：{entry_id}")
    payload = path.read_bytes()
    if (len(payload), hashlib.sha256(payload).hexdigest()) != (row[2], row[3]):
        raise ValueError(f"录音文件损坏：{entry_id}")
    if not payload.startswith(b"OggS"):
        raise ValueError(f"录音不是 Ogg 文件：{entry_id}")
    if row[4] == "synthetic" and b"OpusHead" not in payload[:256]:
        raise ValueError(f"合成录音不是 Ogg Opus：{entry_id}")
    return payload, {"sha256": row[3], "kind": row[4], "style": row[5],
                     "source_ref": row[6], "format": "audio/ogg"}


def _write_core_entries(source: sqlite3.Connection, path: Path) -> int:
    count = 0
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as stream:
            for (payload,) in source.execute(
                    f"SELECT payload FROM entries WHERE {CORE_WHERE} "
                    "ORDER BY lookup_key,headword,entry_id"):
                stream.write(payload.encode("utf-8") + b"\n")
                count += 1
    return count


def build_release(source_root: Path, cache_dir: Path, out: Path,
                  shard_bytes: int = DEFAULT_SHARD_BYTES) -> dict:
    """构建两个 edition；完整版含全部词条并共享核心词音频。"""
    if shard_bytes < 1024 or shard_bytes >= MAX_ASSET_BYTES:
        raise ValueError("分片大小必须介于 1 KiB 与 2 GB 之间")
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("发布目录必须为空，避免混入旧版本文件")
    out.mkdir(parents=True, exist_ok=True)
    source_manifest = verify_package(source_root)
    source_db = source_root / "dictionary.sqlite"
    source = sqlite3.connect(f"file:{source_db.resolve()}?mode=ro", uri=True)
    cache = sqlite3.connect(f"file:{(cache_dir / 'clips.sqlite').resolve()}?mode=ro", uri=True)
    assets: dict[str, dict] = {}
    try:
        fingerprint_row = cache.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
        if fingerprint_row is None:
            raise ValueError("音频缓存缺少生成指纹")
        fingerprint = json.loads(fingerprint_row[0])
        if fingerprint["source_db_sha256"] != file_hash(source_db)[1]:
            raise ValueError("音频缓存与词典数据库不是同一个固定输入")
        total = source.execute("SELECT count(*) FROM entries").fetchone()[0]
        core_count = source.execute(f"SELECT count(*) FROM entries WHERE {CORE_WHERE}").fetchone()[0]
        cache.execute("ATTACH DATABASE ? AS source_data", (str(source_db.resolve()),))
        missing_core = cache.execute(
            f"SELECT count(*) FROM source_data.entries e LEFT JOIN clips c ON c.entry_id=e.entry_id "
            f"WHERE ({CORE_WHERE}) AND c.entry_id IS NULL").fetchone()[0]
        if missing_core:
            raise ValueError(f"核心词离线音频缺少 {missing_core} 条")
        core_entries = "core.entries.jsonl.gz"
        if _write_core_entries(source, out / core_entries) != core_count:
            raise ValueError("核心词条数量变化")
        for name in (core_entries,):
            assets[name] = dict(zip(("bytes", "sha256"), file_hash(out / name)))
        repository_root = Path(__file__).resolve().parent.parent
        sqlite_spec = _split_asset(source_db, out, "full.dictionary.sqlite", shard_bytes, assets)
        for name, origin in (("full.entries.jsonl.gz", source_root / "entries.jsonl.gz"),
                             ("LICENSE", repository_root / "LICENSE"),
                             ("DATA-LICENSE.md", repository_root / "DATA-LICENSE.md"),
                             ("audio-tools.lock.json", repository_root / "audio-tools.lock.json")):
            _copy_asset(origin, out, name, assets)
        for notice in sorted((repository_root / "notices").iterdir()):
            if notice.is_file():
                # GitHub Release 资产名不包含目录，发布包也使用平铺文件名。
                _copy_asset(notice, out, f"notice-{notice.name}", assets)
        audio_sources = {"schema_version": AUDIO_SCHEMA, "synthesis": fingerprint["synthesis"],
                         "human_manifest_sha256": fingerprint["human_manifest_sha256"],
                         "human_attribution": json.loads((source_root / "audio/manifest.json").read_text())
                         if fingerprint["human_manifest_sha256"] else None}
        _json_file(out / "audio-sources.json", audio_sources)
        assets["audio-sources.json"] = dict(zip(("bytes", "sha256"), file_hash(out / "audio-sources.json")))

        core_shards = _ShardWriter(out, "core", shard_bytes)
        core_index = "core.audio-index.jsonl.gz"
        written_core = 0
        with (out / core_index).open("wb") as core_raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=core_raw, mtime=0) as core_stream:
                for entry_id, headword in ordered_entries(source, True):
                    payload, clip_meta = _clip(cache, cache_dir, entry_id, headword)
                    shard, offset = core_shards.add(payload)
                    record = {"entry_id": entry_id, "shard": shard, "offset": offset,
                              "bytes": len(payload), **clip_meta}
                    _write_line(core_stream, record)
                    written_core += 1
        core_shards.close()
        if written_core != core_count:
            raise ValueError("核心音频索引覆盖数与词条数不一致")
        for name in (core_index, *core_shards.names):
            size, sha = file_hash(out / name)
            if size >= MAX_ASSET_BYTES:
                raise ValueError(f"发布资产超过 2 GB：{name}")
            assets[name] = {"bytes": size, "sha256": sha}
        common = ["LICENSE", "DATA-LICENSE.md", "audio-tools.lock.json", "audio-sources.json", *sorted(name for name in assets
                  if name.startswith("notice-"))]
        core_assets = [core_entries, core_index, *core_shards.names, *common]
        full_assets = [core_entries, core_index, "full.entries.jsonl.gz", *sqlite_spec["parts"],
                       *core_shards.names, *common]
        release = {"schema_version": RELEASE_SCHEMA, "dictionary_version": "0.0.1",
                   "entry_schema": "leximeet.entry.v1", "audio_index_schema": INDEX_SCHEMA,
                   "source_dictionary_manifest_sha256": file_hash(source_root / "manifest.json")[1],
                   "source_inputs": source_manifest["inputs"], "audio_synthesis": fingerprint["synthesis"],
                   "shard_max_bytes": shard_bytes, "assets": assets,
                   "editions": {
                       "core": {"entry_count": core_count, "audio_covered_entry_count": written_core,
                                "entries": core_entries, "audio_index": core_index, "assets": core_assets},
                       "full": {"entry_count": total, "audio_covered_entry_count": written_core,
                                "entries": "full.entries.jsonl.gz", "sqlite": sqlite_spec,
                                "audio_index": core_index, "assets": full_assets},
                   }}
        _json_file(out / "release.json", release)
        return release
    finally:
        source.close()
        cache.close()


def _read_entries(path: Path) -> set[str]:
    ids: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            entry_id = entry["entry_id"]
            if entry.get("schema_version") != "leximeet.entry.v1" or entry_id in ids:
                raise ValueError("词条 schema 错误或 entry_id 重复")
            ids.add(entry_id)
    return ids


def _verify_full_sqlite(root: Path, manifest: dict, ids: set[str]) -> None:
    """从真实下载分片重组 SQLite，并证明核心完整词卡未被裁剪。"""
    full = manifest["editions"]["full"]
    core = manifest["editions"]["core"]
    with tempfile.TemporaryDirectory(prefix="leximeet-verify-") as temp:
        assembled = Path(temp) / "dictionary.sqlite"
        _assemble_parts(root, full["sqlite"], assembled)
        with closing(sqlite3.connect(f"file:{assembled.resolve()}?mode=ro", uri=True)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite 完整性校验失败")
            db_ids = {row[0] for row in db.execute("SELECT entry_id FROM entries")}
            if db_ids != ids:
                raise ValueError("SQLite 与 JSONL 词条不一致")
            core_ids = set()
            with gzip.open(_asset_path(root, core["entries"]), "rt", encoding="utf-8") as stream:
                for line in stream:
                    item = json.loads(line)
                    entry_id = item["entry_id"]
                    if entry_id in core_ids or db.execute(
                            "SELECT payload FROM entries WHERE entry_id=?", (entry_id,)).fetchone() != (
                            line.rstrip("\n"),):
                        raise ValueError("核心版词卡与完整版内容不一致")
                    core_ids.add(entry_id)
            if len(core_ids) != core["entry_count"] or not core_ids.issubset(ids):
                raise ValueError("核心版词条不是完整版子集")


def verify_release(root: Path, edition: str = "full", deep: bool = False) -> dict:
    """先校验下载文件；深检再核对逐词关联与每段音频的字节范围。"""
    manifest = json.loads((root / "release.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version"), manifest.get("dictionary_version"),
            manifest.get("entry_schema")) != (RELEASE_SCHEMA, "0.0.1", "leximeet.entry.v1"):
        raise ValueError("Release schema 或版本不兼容")
    if edition not in ("core", "full"):
        raise ValueError("只能核验 core 或 full")
    selected = manifest["editions"][edition]
    required = selected["assets"]
    if len(required) != len(set(required)):
        raise ValueError("Release 资产重复")
    if edition == "full" and not set(manifest["editions"]["core"]["assets"]).issubset(required):
        raise ValueError("完整版缺少核心版共享资产")
    if edition == "full":
        sqlite_spec = selected["sqlite"]
        if (sqlite_spec["path"] != "full.dictionary.sqlite" or not sqlite_spec["parts"]
                or any(name not in required for name in sqlite_spec["parts"])):
            raise ValueError("完整版 SQLite 分片清单无效")
    for name in required:
        target = _asset_path(root, name)
        meta = manifest["assets"][name]
        if file_hash(target) != (meta["bytes"], meta["sha256"]):
            raise ValueError(f"Release 资产损坏：{name}")
        if meta["bytes"] >= MAX_ASSET_BYTES:
            raise ValueError(f"Release 单个资产过大：{name}")
    core_edition = manifest["editions"]["core"]
    if (core_edition["entry_count"] != core_edition["audio_covered_entry_count"]
            or selected["audio_covered_entry_count"] != core_edition["entry_count"]
            or manifest["editions"]["full"]["audio_index"] != core_edition["audio_index"]):
        raise ValueError("核心词离线音频覆盖数不正确")
    result = {"edition": edition, "entry_count": selected["entry_count"],
              "audio_covered_entry_count": selected["audio_covered_entry_count"],
              "assets": len(required), "deep": deep}
    if not deep:
        return result
    referenced = [selected["entries"], selected["audio_index"]]
    if edition == "full":
        referenced.extend((*sqlite_spec["parts"], manifest["editions"]["core"]["entries"],
                           manifest["editions"]["core"]["audio_index"]))
    if any(name not in required for name in referenced):
        raise ValueError("Release 索引引用了本版以外的文件")
    ids = _read_entries(_asset_path(root, selected["entries"]))
    if len(ids) != selected["entry_count"]:
        raise ValueError("词条文件数量与清单不符")
    audio_ids = ids if edition == "core" else _read_entries(_asset_path(root, core_edition["entries"]))
    if len(audio_ids) != selected["audio_covered_entry_count"] or not audio_ids.issubset(ids):
        raise ValueError("音频覆盖的核心词条与清单不符")
    seen: set[str] = set()
    end_offsets: dict[str, int] = {}
    streams = {}
    try:
        with gzip.open(_asset_path(root, selected["audio_index"]), "rt", encoding="utf-8") as stream:
            for line in stream:
                item = json.loads(line)
                entry_id, shard = item["entry_id"], item["shard"]
                if entry_id not in ids or entry_id in seen or shard not in required:
                    raise ValueError("音频索引词条重复、缺失或引用了非本版分片")
                if item["offset"] != end_offsets.get(shard, 0) or item["bytes"] < 1:
                    raise ValueError("音频分片字节范围不连续")
                if shard not in streams:
                    streams[shard] = _asset_path(root, shard).open("rb")
                target = streams[shard]
                target.seek(item["offset"])
                payload = target.read(item["bytes"])
                if (len(payload) != item["bytes"] or
                        hashlib.sha256(payload).hexdigest() != item["sha256"] or
                        not payload.startswith(b"OggS")):
                    raise ValueError(f"音频片段损坏：{entry_id}")
                seen.add(entry_id)
                end_offsets[shard] = item["offset"] + item["bytes"]
        if seen != audio_ids:
            raise ValueError("核心词条未全部获得离线音频")
        for shard, end in end_offsets.items():
            if end != manifest["assets"][shard]["bytes"]:
                raise ValueError(f"音频分片存在未索引字节：{shard}")
        if edition == "full":
            _verify_full_sqlite(root, manifest, ids)
    finally:
        for stream in streams.values():
            stream.close()
    return result


def extract_audio(root: Path, edition: str, entry_id: str, out: Path) -> dict:
    """参考读取器：按索引从分片截取一段 Ogg，方便端侧接入与抽听。"""
    manifest = json.loads((root / "release.json").read_text(encoding="utf-8"))
    if edition not in ("core", "full") or not entry_id:
        raise ValueError("edition 或 entry_id 无效")
    selected = manifest["editions"][edition]
    if selected["audio_index"] not in selected["assets"]:
        raise ValueError("音频索引不属于本版资产")
    item = None
    with gzip.open(_asset_path(root, selected["audio_index"]), "rt", encoding="utf-8") as stream:
        for line in stream:
            current = json.loads(line)
            if current["entry_id"] == entry_id:
                item = current
                break
    if item is None or item["shard"] not in selected["assets"]:
        raise KeyError(f"没有找到本版词条音频：{entry_id}")
    shard = _asset_path(root, item["shard"])
    if file_hash(shard) != (manifest["assets"][item["shard"]]["bytes"],
                            manifest["assets"][item["shard"]]["sha256"]):
        raise ValueError("音频分片哈希不匹配")
    with shard.open("rb") as stream:
        stream.seek(item["offset"])
        payload = stream.read(item["bytes"])
    if hashlib.sha256(payload).hexdigest() != item["sha256"] or not payload.startswith(b"OggS"):
        raise ValueError("音频片段哈希或格式不匹配")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    return {"entry_id": entry_id, "file": str(out), "bytes": len(payload),
            "kind": item["kind"], "style": item["style"], "source_ref": item["source_ref"]}
