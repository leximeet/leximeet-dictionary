"""生成和核验可独立下载的浏览器核心词包。"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

from .builder import SCHEMA, VERSION, file_hash


CORE_SCHEMA = "leximeet.core.v1"
CORE_LIMIT_BYTES = 64 * 1024 * 1024


def create_core_manifest(root: Path, manifest: dict) -> list[str]:
    """从完整词包中选出核心词条和随包必需的许可材料。"""
    included = ["core.jsonl.gz", "DATA-LICENSE.md"] + sorted(
        name for name in manifest["outputs"] if name.startswith("notices/")
    )
    files = {name: manifest["outputs"][name] for name in included}
    parent_size, parent_sha = file_hash(root / "manifest.json")
    core_count = 0
    seen: set[str] = set()
    with gzip.open(root / "core.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            entry_id = entry.get("entry_id")
            if entry.get("schema_version") != SCHEMA or not isinstance(entry_id, str) or entry_id in seen:
                raise ValueError("核心词条 schema 或 entry_id 无效")
            seen.add(entry_id)
            core_count += 1
    if not 0 < core_count <= manifest["core_limit"]:
        raise ValueError("核心词条数量与完整清单不符")
    core_manifest = {
        "schema_version": CORE_SCHEMA,
        "dictionary_version": VERSION,
        "entry_schema": SCHEMA,
        "release_status": manifest["release_status"],
        "entry_count": core_count,
        "parent_manifest": {"file": "manifest.json", "bytes": parent_size, "sha256": parent_sha},
        "files": files,
    }
    (root / "core-manifest.json").write_text(
        json.dumps(core_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return ["core-manifest.json", "manifest.json", *included]


def verify_core_archive(path: Path, expected_sha256: str | None = None) -> dict:
    """在内存中检查归档路径、文件哈希和逐行词条，不向文件系统解包。"""
    if expected_sha256 is not None and file_hash(path)[1] != expected_sha256:
        raise ValueError("核心资产外层 SHA-256 不匹配")
    members: dict[str, bytes] = {}
    prefix = f"leximeet-dictionary-{VERSION}-core/"
    with tarfile.open(path, "r:gz") as archive:
        for item in archive:
            if len(members) >= 32:
                raise ValueError("核心资产成员数量超过限制")
            if not item.isfile() or not item.name.startswith(prefix):
                raise ValueError("核心资产含非普通文件或非法路径")
            name = item.name[len(prefix):]
            if (not name or name.startswith("/") or "\\" in name or
                    name != Path(name).as_posix() or ".." in Path(name).parts or name in members):
                raise ValueError("核心资产含重复或非法路径")
            if item.size > CORE_LIMIT_BYTES:
                raise ValueError("核心资产成员超过大小限制")
            stream = archive.extractfile(item)
            if stream is None:
                raise ValueError("核心资产成员不可读取")
            payload = stream.read(CORE_LIMIT_BYTES + 1)
            if len(payload) != item.size:
                raise ValueError("核心资产成员长度不符")
            members[name] = payload
    if "core-manifest.json" not in members or "manifest.json" not in members:
        raise ValueError("核心资产缺少清单")
    core = json.loads(members["core-manifest.json"])
    parent = json.loads(members["manifest.json"])
    if (core.get("schema_version"), core.get("entry_schema"), core.get("dictionary_version")) != (
        CORE_SCHEMA, SCHEMA, VERSION
    ):
        raise ValueError("核心资产 schema/version 不兼容")
    if (parent.get("schema_version"), parent.get("entry_schema"), parent.get("dictionary_version")) != (
        "leximeet.manifest.v1", SCHEMA, VERSION
    ):
        raise ValueError("完整词典清单 schema/version 不兼容")
    required = {"core-manifest.json", "manifest.json", *core["files"]}
    if set(members) != required:
        raise ValueError("核心资产成员与清单不符")
    parent_meta = core["parent_manifest"]
    if (len(members["manifest.json"]), hashlib.sha256(members["manifest.json"]).hexdigest()) != (
        parent_meta["bytes"], parent_meta["sha256"]
    ):
        raise ValueError("完整词典清单哈希不符")
    if core["release_status"] != parent["release_status"]:
        raise ValueError("核心资产发布状态与完整清单不符")
    required_files = {"core.jsonl.gz", "DATA-LICENSE.md"} | {
        name for name in parent["outputs"] if name.startswith("notices/")
    }
    if set(core["files"]) != required_files:
        raise ValueError("核心资产缺少词条或许可声明")
    for name, expected in core["files"].items():
        data = members[name]
        if (len(data), hashlib.sha256(data).hexdigest()) != (expected["bytes"], expected["sha256"]):
            raise ValueError(f"核心资产文件损坏：{name}")
        if parent["outputs"].get(name) != expected:
            raise ValueError(f"核心资产与完整词典清单不一致：{name}")
    seen: set[str] = set()
    with gzip.open(io.BytesIO(members["core.jsonl.gz"]), "rt", encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            entry_id = entry.get("entry_id")
            if entry.get("schema_version") != SCHEMA or not isinstance(entry_id, str) or entry_id in seen:
                raise ValueError("核心资产词条 schema 或 entry_id 无效")
            seen.add(entry_id)
    if len(seen) != core["entry_count"] or not 0 < len(seen) <= parent["core_limit"]:
        raise ValueError("核心资产词条数量不符")
    return core
