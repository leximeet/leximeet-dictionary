"""分层词包的参考安装器：复用哈希缓存，构建查询索引，成功后原子切换。"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import tempfile
import urllib.parse
import urllib.request
from contextlib import closing
from pathlib import Path

from .builder import canonical, file_hash, lookup_key
from .compressed import json_lines
from .learning import _create as create_learning_tables
from .release_v3 import VERSION, asset_path, read_manifest, verify_layered_release


def _blob_path(cache: Path, meta: dict) -> Path:
    return asset_path(cache, meta["sha256"])


def plan_upgrade(manifest_root: Path, cache: Path, edition: str) -> dict:
    """按目标文件哈希规划；同名旧文件不代表可以复用，损坏缓存也必须重下。"""
    manifest = read_manifest(manifest_root)
    if edition not in manifest["editions"]:
        raise ValueError("该组合尚未发布")
    download, reuse = [], []
    for name in manifest["editions"][edition]["assets"]:
        meta = manifest["assets"][name]
        path = _blob_path(cache, meta)
        valid = path.is_file() and file_hash(path) == (meta["bytes"], meta["sha256"])
        (reuse if valid else download).append(name)
    return {"edition": edition, "download": download, "reuse": reuse,
            "remaining_download_bytes": sum(manifest["assets"][key]["bytes"] for key in download),
            "reused_bytes": sum(manifest["assets"][key]["bytes"] for key in reuse),
            "target_download_bytes": manifest["editions"][edition]["download_bytes"]}


def download_assets(manifest_root: Path, cache: Path, edition: str,
                    source: Path | None = None, url: str | None = None) -> dict:
    """每片独立保存为哈希对象；失败重试或再次运行时无需重下已校验的其他片。"""
    if (source is None) == (url is None):
        raise ValueError("必须且只能指定本地 source 或下载 url")
    if url is not None and urllib.parse.urlsplit(url).scheme not in ("https", "http"):
        raise ValueError("下载地址必须是 HTTP(S)")
    manifest = read_manifest(manifest_root)
    cache.mkdir(parents=True, exist_ok=True)
    plan = plan_upgrade(manifest_root, cache, edition)
    for name in plan["download"]:
        meta = manifest["assets"][name]
        last_error = None
        for _ in range(3):
            # 临时文件由安装器创建，校验成功才替换缓存；旧安装不会引用这个临时文件。
            with tempfile.NamedTemporaryFile(prefix=".download-", dir=cache, delete=False) as target:
                temporary = Path(target.name)
                try:
                    stream = asset_path(source, name).open("rb") if source is not None else (
                        urllib.request.urlopen(url.rstrip("/") + "/" + urllib.parse.quote(name), timeout=60))
                    size, digest = 0, hashlib.sha256()
                    with stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            size += len(block)
                            if size > meta["bytes"]:
                                raise ValueError(f"下载文件超出声明大小：{name}")
                            target.write(block)
                            digest.update(block)
                    if (size, digest.hexdigest()) != (meta["bytes"], meta["sha256"]):
                        raise ValueError(f"下载文件哈希不符：{name}")
                    target.flush()
                    os.fsync(target.fileno())
                except (OSError, ValueError) as error:
                    last_error = error
            if last_error is None:
                os.replace(temporary, _blob_path(cache, meta))
                break
            temporary.unlink(missing_ok=True)
            if source is not None:
                raise last_error
            if _ == 2:
                raise last_error
            last_error = None
    return plan


def build_index(package: Path, edition: str) -> dict:
    """从无损词卡还原词头、词形、目录、助记、音频索引；不依赖在线查询。"""
    manifest = read_manifest(package)
    selected = manifest["editions"][edition]
    target = package / "dictionary.sqlite"
    if target.exists():
        raise FileExistsError("索引输出已存在")
    catalogs = json.loads((package / "catalogs.json").read_text(encoding="utf-8"))["catalogs"]
    with closing(sqlite3.connect(target)) as db:
        create_learning_tables(db)
        db.executescript("""
            CREATE TABLE entries(entry_id TEXT PRIMARY KEY, headword TEXT NOT NULL,
                lookup_key TEXT NOT NULL, origin TEXT NOT NULL, rank INTEGER, payload TEXT NOT NULL);
            CREATE INDEX entries_lookup ON entries(lookup_key,headword);
            CREATE TABLE forms(form_key TEXT NOT NULL,form_text TEXT NOT NULL,entry_id TEXT NOT NULL,
                PRIMARY KEY(form_key,form_text,entry_id));
            CREATE TABLE offline_audio(entry_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        """)
        db.execute("PRAGMA foreign_keys=ON")
        db.executemany("INSERT INTO catalogs VALUES (?,?,?,?,?)", [
            tuple(item[key] for key in ("catalog_id", "title_zh", "category", "source", "method"))
            for item in catalogs])
        db.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("schema_version", "leximeet.learning.v2"), ("dictionary_version", VERSION),
            ("edition", edition), ("release_manifest_sha256", file_hash(package / "release.json")[1])])
        for layer in selected["entry_layers"]:
            for name in manifest["layers"][layer]["assets"]:
                for entry in json_lines(asset_path(package, name)):
                    eid = entry["entry_id"]
                    ranks = entry["ecdict"]["frequency_ranks"]
                    db.execute("INSERT INTO entries VALUES (?,?,?,?,?,?)", (
                        eid, entry["headword"], entry["lookup_key"], entry["origin"],
                        ranks.get("frq") or ranks.get("bnc"), canonical(entry)))
                    for form in entry.get("forms", []):
                        db.execute("INSERT OR IGNORE INTO forms VALUES (?,?,?)",
                                   (lookup_key(form["text"]), form["text"], eid))
                    for member in entry["learning"]["collections"]:
                        db.execute("INSERT INTO members VALUES (?,?,?,?,?,?)", (
                            member["catalog_id"], eid, member["position"], canonical(member["sense_ids"]),
                            member["match_method"], canonical(member["source_payload"])))
                    for note in entry["learning"]["mnemonics"]:
                        db.execute("INSERT INTO mnemonics VALUES (?,?,?,?,?,?,?)", (
                            eid, note["source"], note["kind"], note["format"], note["content"],
                            note["review_status"], canonical(note["provenance"])))
        for layer in selected["audio_layers"]:
            for item in json_lines(asset_path(package, manifest["layers"][layer]["index"])):
                db.execute("INSERT INTO offline_audio VALUES (?,?)", (item["entry_id"], canonical(item)))
        count = db.execute("SELECT count(*) FROM entries").fetchone()[0]
        audio_count = db.execute("SELECT count(*) FROM offline_audio").fetchone()[0]
        if count != selected["entry_count"] or audio_count != selected["audio_covered_entry_count"]:
            raise ValueError("安装索引覆盖数不一致")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("安装索引目录外键无效")
        db.commit()
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("安装索引 SQLite 损坏")
    size, sha = file_hash(target)
    return {"entry_count": count, "audio_covered_entry_count": audio_count,
            "database": {"bytes": size, "sha256": sha}}


def install_package(manifest_root: Path, cache: Path, installation: Path, edition: str,
                    source: Path | None = None, url: str | None = None) -> dict:
    """先完成下载和新索引，再原子替换 current.json；从不修改用户单词本和学习进度。"""
    manifest = read_manifest(manifest_root)
    plan = download_assets(manifest_root, cache, edition, source, url)
    versions = installation / "packages"
    versions.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".install-", dir=versions) as temporary:
        stage = Path(temporary)
        for name in manifest["editions"][edition]["assets"]:
            original = _blob_path(cache, manifest["assets"][name])
            try:
                os.link(original, stage / name)
            except OSError:
                shutil.copyfile(original, stage / name)
        (stage / "release.json").write_bytes((manifest_root / "release.json").read_bytes())
        verify_layered_release(stage, edition, deep=True)
        indexed = build_index(stage, edition)
        receipt = {**indexed, "edition": edition,
                   "manifest_sha256": file_hash(stage / "release.json")[1]}
        (stage / "receipt.json").write_text(canonical(receipt) + "\n", encoding="utf-8")
        name = f"{VERSION}-{edition}-{receipt['manifest_sha256'][:12]}-{secrets.token_hex(4)}"
        destination = versions / name
        os.replace(stage, destination)
    # 旧版本目录仍然保留。即使索引生成、下载或验证失败，当前指针也不会改变。
    with tempfile.NamedTemporaryFile(prefix=".current-", dir=installation, delete=False) as stream:
        current = Path(stream.name)
        stream.write((canonical({"edition": edition, "package": f"packages/{name}",
                                 "manifest_sha256": receipt["manifest_sha256"]}) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(current, installation / "current.json")
    return {**receipt, "package_path": str(destination), "download_plan": plan}


def extract_installed_audio(package: Path, entry_id: str, out: Path) -> dict:
    """按本地索引定点读取 Ogg；text 包中的音标不会被误当作离线录音。"""
    with closing(sqlite3.connect(f"file:{(package / 'dictionary.sqlite').resolve()}?mode=ro", uri=True)) as db:
        row = db.execute("SELECT payload FROM offline_audio WHERE entry_id=?", (entry_id,)).fetchone()
    if row is None:
        raise KeyError("该组合没有此词的离线音频")
    item = json.loads(row[0])
    with asset_path(package, item["shard"]).open("rb") as stream:
        stream.seek(item["offset"])
        data = stream.read(item["bytes"])
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("本地录音损坏")
    if out.exists():
        raise FileExistsError("试听输出已存在")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return {"entry_id": entry_id, "bytes": len(data), "sha256": item["sha256"]}
