"""将同一词典核心封装成可下载的无音频版和带发音版候选包。"""

from __future__ import annotations

import gzip
import json
import tarfile
from pathlib import Path

from .audio import verify_audio
from .builder import file_hash, verify_package


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
    core = ["manifest.json", "DATA-LICENSE.md", *manifest["outputs"].keys()]
    no_audio = core + ["edition.no-audio.json"]
    with_audio = core + ["edition.with-audio.json", "audio/manifest.json"] + [
        "audio/" + asset["path"] for asset in audio["assets"]
    ]
    results = []
    for edition, names in (("no-audio", no_audio), ("with-audio", with_audio)):
        results.append(_archive(root, out / f"leximeet-dictionary-0.0.1-{edition}.tar.gz",
                                names, f"leximeet-dictionary-0.0.1-{edition}", edition))
    result = {"dictionary_version": "0.0.1", "release_status": manifest["release_status"],
              "artifacts": results, "audio_assets": audio["offline_asset_count"]}
    (out / "release-candidate.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result
