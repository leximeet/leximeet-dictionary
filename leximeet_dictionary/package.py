"""将同一词典核心封装成可下载的无音频版和带发音版候选包。"""

from __future__ import annotations

import gzip
import hashlib
import json
import tarfile
from pathlib import Path

from .audio import verify_audio
from .builder import file_hash, verify_package
from .core import create_core_manifest, verify_core_archive


def _archive(root: Path, output: Path, names: list[str], prefix: str, edition: str) -> dict:
    """固定 tar 元数据和 gzip 时间戳，使归档字节可重复。"""
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as tar:
                for name in sorted(names):
                    path = root / name
                    info = tar.gettarinfo(str(path), arcname=f"{prefix}/{name}")
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    with path.open("rb") as stream:
                        tar.addfile(info, stream)
    size, sha256 = file_hash(output)
    return {"file": output.name, "bytes": size, "sha256": sha256, "edition": edition}


def package(root: Path, out: Path) -> dict:
    manifest = verify_package(root)
    audio = verify_audio(root / "audio")
    if audio["offline_asset_count"] == 0:
        raise ValueError("带发音版没有通过核验的离线录音")
    if out.resolve().is_relative_to(root.resolve()):
        raise ValueError("归档目录不能位于被打包的词典目录内")
    out.mkdir(parents=True, exist_ok=True)
    core = ["manifest.json", *manifest["outputs"].keys()]
    no_audio = core + ["edition.no-audio.json"]
    with_audio = core + ["edition.with-audio.json", "audio/manifest.json"] + [
        "audio/" + asset["path"] for asset in audio["assets"]
    ]
    results = []
    core_names = create_core_manifest(root, manifest)
    core_result = _archive(root, out / "leximeet-dictionary-0.0.1-core.tar.gz",
                           core_names, "leximeet-dictionary-0.0.1-core", "core")
    verify_core_archive(out / core_result["file"], core_result["sha256"])
    results.append(core_result)
    for edition, names in (("no-audio", no_audio), ("with-audio", with_audio)):
        results.append(_archive(root, out / f"leximeet-dictionary-0.0.1-{edition}.tar.gz",
                                names, f"leximeet-dictionary-0.0.1-{edition}", edition))
    result = {"dictionary_version": "0.0.1", "release_status": manifest["release_status"],
              "generator": manifest["generator"],
              "artifacts": results, "audio_assets": audio["offline_asset_count"]}
    (out / "release-candidate.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def verify_archive(path: Path, expected_sha256: str | None = None) -> dict:
    """流式核验完整归档的成员与哈希；客户端仍应在解包后检查 SQLite。"""
    if expected_sha256 is not None and file_hash(path)[1] != expected_sha256:
        raise ValueError("完整资产外层 SHA-256 不匹配")
    edition_name = "with-audio" if path.name.endswith("-with-audio.tar.gz") else "no-audio"
    if not path.name.endswith(f"-{edition_name}.tar.gz"):
        raise ValueError("完整资产文件名不是支持的 edition")
    prefix = f"leximeet-dictionary-0.0.1-{edition_name}/"
    hashes: dict[str, tuple[int, str]] = {}
    metadata: dict[str, bytes] = {}
    with tarfile.open(path, "r|gz") as archive:
        for item in archive:
            if not item.isfile() or not item.name.startswith(prefix):
                raise ValueError("完整资产含非普通文件或非法路径")
            name = item.name[len(prefix):]
            if (not name or name.startswith("/") or "\\" in name or
                    name != Path(name).as_posix() or ".." in Path(name).parts or name in hashes):
                raise ValueError("完整资产含重复或非法路径")
            source = archive.extractfile(item)
            if source is None:
                raise ValueError("完整资产成员不可读取")
            digest = hashlib.sha256()
            size = 0
            small = bytearray()
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
                if name in ("manifest.json", f"edition.{edition_name}.json", "audio/manifest.json"):
                    if len(small) + len(chunk) > 2 * 1024 * 1024:
                        raise ValueError("完整资产清单超过大小限制")
                    small.extend(chunk)
            if size != item.size:
                raise ValueError(f"完整资产成员长度不符：{name}")
            hashes[name] = (size, digest.hexdigest())
            if small:
                metadata[name] = bytes(small)
    manifest = json.loads(metadata["manifest.json"])
    edition = json.loads(metadata[f"edition.{edition_name}.json"])
    if (manifest.get("schema_version"), manifest.get("entry_schema"), manifest.get("dictionary_version")) != (
        "leximeet.manifest.v1", "leximeet.entry.v1", "0.0.1"
    ) or edition.get("schema_version") != "leximeet.edition.v1":
        raise ValueError("完整资产 schema/version 不兼容")
    expected_files = set(manifest["outputs"]) | {"manifest.json", f"edition.{edition_name}.json"}
    if edition.get("edition") != edition_name or hashes["manifest.json"] != (
        edition["dictionary_manifest_bytes"], edition["dictionary_manifest_sha256"]
    ):
        raise ValueError("完整资产 edition 清单不匹配")
    for name, expected in manifest["outputs"].items():
        if hashes.get(name) != (expected["bytes"], expected["sha256"]):
            raise ValueError(f"完整资产文件损坏：{name}")
    if edition_name == "with-audio":
        audio = json.loads(metadata["audio/manifest.json"])
        expected_files.add("audio/manifest.json")
        if hashes["audio/manifest.json"] != (edition["audio_manifest_bytes"], edition["audio_manifest_sha256"]):
            raise ValueError("完整资产音频清单不匹配")
        if audio["offline_asset_count"] != len(audio["assets"]):
            raise ValueError("完整资产音频数量不符")
        for asset in audio["assets"]:
            name = "audio/" + asset["path"]
            expected_files.add(name)
            if hashes.get(name) != (asset["bytes"], asset["sha256"]):
                raise ValueError(f"完整资产录音损坏：{name}")
            if not all(asset.get(field) for field in ("artist", "license", "license_url", "source_page")):
                raise ValueError(f"完整资产录音缺少署名：{name}")
    if set(hashes) != expected_files:
        raise ValueError("完整资产成员与清单不符")
    return {"edition": edition_name, "dictionary_version": manifest["dictionary_version"],
            "release_status": manifest["release_status"], "files": len(hashes)}
