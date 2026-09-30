"""0.0.3 分层词包：完整词卡只存一次，音频按词量分层，lite 按体积选词。"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from .builder import canonical, file_hash, lookup_key
from .compressed import COMPRESSION, check_compressor, json_lines, write_record, writer
from .entry_v2 import SCHEMA as ENTRY_SCHEMA, compose_entry
from .release_v2 import verify_core_release

SCHEMA = "leximeet.release.v3"
VERSION = "0.0.3"
LITE_CAP_BYTES = 100_000_000  # MB 使用十进制；不是安装后占用上限。
SHARD_BYTES = 256 * 1024 * 1024
FULL_RAW_SHARD_BYTES = 64 * 1024 * 1024
EDITION_LAYERS = {
    "lite-text": (["lite-entries"], []),
    "lite-audio": (["lite-entries"], ["lite-audio"]),
    "core-text": (["lite-entries", "core-entries"], []),
    "core-audio": (["lite-entries", "core-entries"], ["lite-audio", "core-audio"]),
    "full-text": (["lite-entries", "core-entries", "full-entries"], []),
}


def asset_path(root: Path, name: str) -> Path:
    """发布文件必须是平铺文件；拒绝路径穿越、符号链接和清单注入。"""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise ValueError("非法资产路径")
    target = root / name
    if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("资产不能是符号链接或指向目录外")
    return target


def _json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def _register(out: Path, name: str, kind: str, assets: dict, limit: int) -> None:
    size, sha = file_hash(asset_path(out, name))
    if size > limit:
        raise ValueError(f"资产超过分片上限：{name}")
    assets[name] = {"bytes": size, "sha256": sha, "kind": kind}


def write_manifest(out: Path, manifest: dict) -> dict:
    """把清单自身也计入下载量；只对大小求固定点，不把清单自身哈希写入自身。"""
    manifest["manifest_bytes"] = 0
    for _ in range(10):
        for edition in manifest["editions"].values():
            edition["download_bytes"] = manifest["manifest_bytes"] + sum(
                manifest["assets"][name]["bytes"] for name in edition["assets"])
        raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
        if len(raw) == manifest["manifest_bytes"]:
            if any(manifest["editions"][key]["download_bytes"] >= manifest["lite_cap_bytes"]
                   for key in ("lite-text", "lite-audio")):
                raise ValueError("最终 lite 下载量超过预算")
            (out / "release.json").write_bytes(raw)
            return manifest
        manifest["manifest_bytes"] = len(raw)
    raise ValueError("下载清单大小未收敛")


def _read_gzip(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def _load_core(base: Path, db: sqlite3.Connection, functions: set[str]) -> dict:
    """工作数据库只用于构建；发布包不再重复携带学习数据库中的词卡内容。"""
    manifest = json.loads((base / "release.json").read_text(encoding="utf-8"))
    edition = manifest["editions"]["core"]
    db.execute("""CREATE TABLE core(
        entry_id TEXT PRIMARY KEY, seq INTEGER UNIQUE, lookup_key TEXT,
        required INTEGER, rank INTEGER, priority INTEGER, mnemonic INTEGER,
        payload TEXT NOT NULL)""")
    with closing(sqlite3.connect(
            f"file:{asset_path(base, edition['learning_db']).resolve()}?mode=ro", uri=True)) as learning:
        methods = {(row[0], row[1]): row[2] for row in learning.execute(
            "SELECT entry_id,catalog_id,match_method FROM members")}
        catalogs = [dict(zip(("catalog_id", "title_zh", "category", "source", "method", "entry_count"), row))
                    for row in learning.execute(
                        """SELECT c.catalog_id,c.title_zh,c.category,c.source,c.method,count(m.entry_id)
                           FROM catalogs c LEFT JOIN members m USING(catalog_id)
                           GROUP BY c.catalog_id ORDER BY c.catalog_id""")]
        metadata = dict(learning.execute("SELECT key,value FROM metadata"))
    optional = []
    required_ids, found_functions = set(), set()
    for seq, entry in enumerate(_read_gzip(asset_path(base, edition["entries"]))):
        entry_id, key = entry["entry_id"], entry["lookup_key"]
        # 旧版词卡未导出匹配方法；补入这个可选字段，安装时可还原完整成员索引。
        for membership in entry["learning"]["collections"]:
            membership["match_method"] = methods[(entry_id, membership["catalog_id"])]
        required = bool(entry["learning"]["collections"]) or key in functions
        if required:
            required_ids.add(entry_id)
        if key in functions:
            found_functions.add(key)
        ranks = entry["ecdict"]["frequency_ranks"]
        rank = ranks.get("frq") or ranks.get("bnc") or 10**12
        if not required:
            optional.append((rank, key, entry_id))
        db.execute("INSERT INTO core VALUES (?,?,?,?,?,?,?,?)", (
            entry_id, seq, key, int(required), rank, -1,
            int(bool(entry["learning"]["mnemonics"])), canonical(entry)))
    missing = functions - found_functions
    if missing:
        raise ValueError(f"核心词缺少固定功能词：{sorted(missing)}")
    optional.sort()
    db.executemany("UPDATE core SET priority=? WHERE entry_id=?",
                   [(position, item[2]) for position, item in enumerate(optional)])
    db.execute("CREATE INDEX core_by_priority ON core(required,priority)")
    db.commit()
    return {"catalogs": catalogs, "base_learning_metadata": metadata,
            "required_ids": required_ids, "optional": optional,
            "function_words": sorted(functions)}


def _selected_ids(db: sqlite3.Connection, prefix: int) -> set[str]:
    return {row[0] for row in db.execute(
        "SELECT entry_id FROM core WHERE required=1 OR priority<?", (prefix,))}


def _write_core_entries(db: sqlite3.Connection, prefix: int, lite: bool, target: Path) -> dict:
    condition = "(required=1 OR priority<?)" if lite else "(required=0 AND priority>=?)"
    count = notes = 0
    with writer(target) as stream:
        for payload, mnemonic in db.execute(
                f"SELECT payload,mnemonic FROM core WHERE {condition} ORDER BY seq", (prefix,)):
            stream.write(payload.encode() + b"\n")
            count += 1
            notes += mnemonic
    return {"kind": "entries", "assets": [target.name], "entry_count": count,
            "mnemonic_covered_entry_count": notes}


def _audio_layer(base: Path, records: list[dict], selected: set[str], name: str,
                 out: Path, shard_bytes: int, pack: bool) -> dict:
    """重排索引和分片；测算时只写索引，打包时读取已核验的源录音，不重新合成。"""
    index_name = f"audio-{name}.index.jsonl.zst"
    parts, offset, number, seen = {}, 0, 1, set()
    streams = {}
    target = None
    try:
        with writer(out / index_name) as index:
            for original in records:
                if original["entry_id"] not in selected:
                    continue
                if original["entry_id"] in seen or original["bytes"] > shard_bytes:
                    raise ValueError("录音重复或单词录音超过分片上限")
                if offset and offset + original["bytes"] > shard_bytes:
                    if target:
                        target.close()
                        target = None
                    number += 1
                    offset = 0
                shard = f"audio-{name}-{number:04}.pack"
                if pack:
                    if target is None:
                        target = asset_path(out, shard).open("wb")
                    source_name = original["shard"]
                    if source_name not in streams:
                        streams[source_name] = asset_path(base, source_name).open("rb")
                    source = streams[source_name]
                    source.seek(original["offset"])
                    payload = source.read(original["bytes"])
                    if (len(payload) != original["bytes"]
                            or hashlib.sha256(payload).hexdigest() != original["sha256"]):
                        raise ValueError("源录音片段损坏")
                    target.write(payload)
                updated = {**original, "shard": shard, "offset": offset}
                write_record(index, updated)
                offset += original["bytes"]
                parts[shard] = offset
                seen.add(original["entry_id"])
    finally:
        if target:
            target.close()
        for stream in streams.values():
            stream.close()
    if seen != selected:
        raise ValueError("所选词缺少离线音频")
    return {"kind": "audio", "assets": [index_name] + list(parts), "index": index_name,
            "audio_covered_entry_count": len(seen), "pack_bytes": sum(parts.values())}


def _full_delta(full_entries: Path, db: sqlite3.Connection, scratch: Path,
                out: Path, assets: dict, shard_bytes: int) -> dict:
    """先计算非核心词的实际字节量，再均衡切片；不会发布重复的完整核心词卡。"""
    core_ids = {row[0] for row in db.execute("SELECT entry_id FROM core")}
    seen, core_seen = set(), set()
    spool = scratch / "full-delta.jsonl"
    count = 0
    with spool.open("wb") as target:
        for entry in _read_gzip(full_entries):
            entry_id = entry["entry_id"]
            if entry_id in seen:
                raise ValueError("完整版输入包含重复 entry_id")
            seen.add(entry_id)
            if entry_id in core_ids:
                core_seen.add(entry_id)
                payload = json.loads(db.execute(
                    "SELECT payload FROM core WHERE entry_id=?", (entry_id,)).fetchone()[0])
                for key in ("learning", "base_entry_schema"):
                    payload.pop(key)
                payload["schema_version"] = "leximeet.entry.v1"
                if payload != entry:
                    raise ValueError("完整版与核心版的基础词卡不同")
                continue
            upgraded = compose_entry(entry, {"entry_id": entry_id, "catalogs": [], "mnemonics": []})
            target.write((canonical(upgraded) + "\n").encode())
            count += 1
    if core_seen != core_ids:
        raise ValueError("完整版输入没有包含全部核心词")
    # 按未压缩字节均衡；压缩后仍须逐片满足硬性上限。一个词卡不能跨片。
    total = spool.stat().st_size
    part_count = max(1, math.ceil(total / min(FULL_RAW_SHARD_BYTES, shard_bytes)))
    target_bytes = max(1, math.ceil(total / part_count))
    names = []
    with spool.open("rb") as source:
        pending = source.readline()
        while pending:
            name = f"entries-full-delta-{len(names) + 1:04}.jsonl.zst"
            written = 0
            with writer(out / name) as target:
                while pending and (written < target_bytes or len(names) == part_count - 1):
                    target.write(pending)
                    written += len(pending)
                    pending = source.readline()
            names.append(name)
            _register(out, name, "entries", assets, shard_bytes)
    return {"kind": "entries", "assets": names, "entry_count": count,
            "mnemonic_covered_entry_count": 0}


def build_layered_release(base: Path, full_entries: Path, source_lock: Path, out: Path,
                          function_words: Path, lite_cap_bytes: int = LITE_CAP_BYTES,
                          shard_bytes: int = SHARD_BYTES) -> dict:
    """固定官方输入，二分选词，再由实际发布清单检查两个 lite 包的完整下载预算。"""
    check_compressor()
    if not 0 < lite_cap_bytes <= LITE_CAP_BYTES or not 0 < shard_bytes <= SHARD_BYTES:
        raise ValueError("lite 预算或分片大小不符合 0.0.3 上限")
    lock = json.loads(source_lock.read_text(encoding="utf-8"))
    if (lock.get("schema_version") != "leximeet.package-sources.v1"
            or file_hash(base / "release.json")[1] != lock["core"]["manifest_sha256"]
            or file_hash(full_entries) != (lock["full"]["bytes"], lock["full"]["sha256"])
            or file_hash(function_words)[1] != lock["function_words_sha256"]
            or lock.get("compression") != COMPRESSION):
        raise ValueError("0.0.3 输入与固定来源锁不一致")
    quality = verify_core_release(base, deep=True)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("0.0.3 发布目录必须为空")
    out.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads((base / "release.json").read_text(encoding="utf-8"))
    source_edition = source_manifest["editions"]["core"]
    repository = Path(__file__).resolve().parent.parent
    functions = {lookup_key(item["word"]) for item in _read_gzip(function_words)} if (
        function_words.suffix == ".gz") else {
            lookup_key(json.loads(line)["word"])
            for line in function_words.read_text(encoding="utf-8").splitlines() if line}
    assets, layers = {}, {}
    common, audio_common = [], []
    for name in source_edition["assets"]:
        if name in ("audio-sources.json", "audio-tools.lock.json"):
            destination = audio_common
        elif name in ("LICENSE", "DATA-LICENSE.md", "learning-sources.lock.json") or name.startswith("notice-"):
            destination = common
        else:
            continue
        source = repository / name if name in ("LICENSE", "DATA-LICENSE.md") else asset_path(base, name)
        shutil.copyfile(source, out / name)
        _register(out, name, "metadata", assets, shard_bytes)
        destination.append(name)
    shutil.copyfile(source_lock, out / "package-sources.lock.json")
    _register(out, "package-sources.lock.json", "metadata", assets, shard_bytes)
    common.append("package-sources.lock.json")
    with tempfile.TemporaryDirectory(prefix="leximeet-v3-") as temporary:
        scratch = Path(temporary)
        with closing(sqlite3.connect(scratch / "core.sqlite")) as db:
            prepared = _load_core(base, db, functions)
            _json(out / "catalogs.json", {"schema_version": "leximeet.catalogs.v1",
                  "catalogs": prepared["catalogs"],
                  "base_learning_metadata": prepared["base_learning_metadata"]})
            _register(out, "catalogs.json", "metadata", assets, shard_bytes)
            common.append("catalogs.json")
            layers["full-entries"] = _full_delta(full_entries, db, scratch, out, assets, shard_bytes)
            records = list(_read_gzip(asset_path(base, source_edition["audio_index"])))
            if {item["entry_id"] for item in records} != {
                    row[0] for row in db.execute("SELECT entry_id FROM core")}:
                raise ValueError("核心音频与词卡覆盖不一致")
            # 给清单和选词报告预留 64 KiB。最终仍以真实字节数验收，不把估算当发布证据。
            reserve = 65_536
            budget = lite_cap_bytes - sum(assets[name]["bytes"] for name in common + audio_common) - reserve
            measurements = {}

            def measure(prefix: int) -> int:
                if prefix not in measurements:
                    selected = _selected_ids(db, prefix)
                    _write_core_entries(db, prefix, True, scratch / "entries-lite.jsonl.zst")
                    audio = _audio_layer(base, records, selected, "lite", scratch, shard_bytes, False)
                    measurements[prefix] = (scratch / "entries-lite.jsonl.zst").stat().st_size + (
                        scratch / audio["index"]).stat().st_size + audio["pack_bytes"]
                return measurements[prefix]

            if measure(0) >= budget:
                raise ValueError("必选词、音频及清单预留已超过 lite 预算，不能静默删减词书成员")
            low, high = 0, len(prepared["optional"])
            while low < high:
                middle = (low + high + 1) // 2
                if measure(middle) < budget:
                    low = middle
                else:
                    high = middle - 1
            selected = _selected_ids(db, low)
            for lite, layer, name in (
                    (True, "lite-entries", "entries-lite.jsonl.zst"),
                    (False, "core-entries", "entries-core-delta.jsonl.zst")):
                layers[layer] = _write_core_entries(db, low, lite, out / name)
                _register(out, name, "entries", assets, shard_bytes)
            all_ids = {row[0] for row in db.execute("SELECT entry_id FROM core")}
            for ids, layer, name in (
                    (selected, "lite-audio", "lite"),
                    (all_ids - selected, "core-audio", "core-delta")):
                layers[layer] = _audio_layer(base, records, ids, name, out, shard_bytes, True)
                layers[layer].pop("pack_bytes")
                for asset in layers[layer]["assets"]:
                    kind = "audio-index" if asset == layers[layer]["index"] else "audio-pack"
                    _register(out, asset, kind, assets, shard_bytes)
            _json(out / "selection.json", {
                "schema_version": "leximeet.lite-selection.v1",
                "lite_cap_bytes": lite_cap_bytes, "manifest_reserve_bytes": reserve,
                "required_entry_count": len(prepared["required_ids"]),
                "ranked_prefix_count": low, "selected_entry_count": len(selected),
                "required_function_words": prepared["function_words"],
                "catalog_count": len(prepared["catalogs"]),
                "method": "catalog-members + function-words; frq-or-bnc, lookup_key, entry_id",
                "selected_ids_sha256": hashlib.sha256(
                    ("\n".join(sorted(selected)) + "\n").encode()).hexdigest(),
            })
            _register(out, "selection.json", "metadata", assets, shard_bytes)
            common.append("selection.json")
    editions = {}
    for edition_name, (entry_layers, audio_layers) in EDITION_LAYERS.items():
        names = list(common)
        if audio_layers:
            names += audio_common
        for layer in entry_layers + audio_layers:
            names += layers[layer]["assets"]
        editions[edition_name] = {
            "entry_layers": list(entry_layers), "audio_layers": list(audio_layers), "assets": sorted(names),
            "entry_count": sum(layers[key]["entry_count"] for key in entry_layers),
            "mnemonic_covered_entry_count": sum(
                layers[key]["mnemonic_covered_entry_count"] for key in entry_layers),
            "audio_covered_entry_count": sum(
                layers[key]["audio_covered_entry_count"] for key in audio_layers),
        }
    if editions["core-text"]["entry_count"] != quality["entry_count"]:
        raise ValueError("核心词卡构建时丢失")
    if editions["full-text"]["entry_count"] != lock["full"]["entry_count"]:
        raise ValueError("完整版词量与来源锁不同")
    return write_manifest(out, {
        "schema_version": SCHEMA, "dictionary_version": VERSION, "entry_schema": ENTRY_SCHEMA,
        "compression": dict(COMPRESSION), "shard_max_bytes": shard_bytes, "lite_cap_bytes": lite_cap_bytes,
        "common_assets": sorted(common), "audio_common_assets": sorted(audio_common),
        "layers": layers, "assets": assets, "editions": editions,
    })


def validate_manifest(manifest: dict, manifest_bytes: int) -> None:
    """不依赖已下载数据的协议检查，客户端下载任何资产之前先执行。"""
    if (manifest.get("schema_version") != SCHEMA or manifest.get("dictionary_version") != VERSION
            or manifest.get("entry_schema") != ENTRY_SCHEMA
            or manifest.get("manifest_bytes") != manifest_bytes
            or set(manifest.get("editions", {})) != set(EDITION_LAYERS)
            or set(manifest.get("layers", {})) != {
                key for parts in EDITION_LAYERS.values() for group in parts for key in group}
            or not 0 < manifest.get("lite_cap_bytes", 0) <= LITE_CAP_BYTES
            or not 0 < manifest.get("shard_max_bytes", 0) <= SHARD_BYTES
            or manifest.get("compression") != COMPRESSION):
        raise ValueError("0.0.3 清单结构、版本或大小无效")
    assets = manifest["assets"]
    used = set(manifest["common_assets"] + manifest["audio_common_assets"])
    for name, meta in assets.items():
        asset_path(Path("."), name)
        if (not isinstance(meta.get("bytes"), int) or isinstance(meta["bytes"], bool)
                or not 0 <= meta["bytes"] <= manifest["shard_max_bytes"]
                or not re.fullmatch(r"[0-9a-f]{64}", meta.get("sha256", ""))
                or meta.get("kind") not in ("metadata", "entries", "audio-index", "audio-pack")):
            raise ValueError("资产元数据无效")
    for name, layer in manifest["layers"].items():
        if not isinstance(layer.get("assets"), list) or len(layer["assets"]) != len(set(layer["assets"])):
            raise ValueError("分层资产重复")
        used.update(layer["assets"])
        if layer.get("kind") == "entries":
            if (not all(assets.get(key, {}).get("kind") == "entries" for key in layer["assets"])
                    or not 0 <= layer.get("mnemonic_covered_entry_count", -1) <= layer.get("entry_count", -1)):
                raise ValueError("词卡层结构无效")
        elif layer.get("kind") == "audio":
            if (layer.get("index") not in layer["assets"]
                    or assets.get(layer["index"], {}).get("kind") != "audio-index"
                    or not all(assets.get(key, {}).get("kind") == "audio-pack"
                               for key in layer["assets"] if key != layer["index"])
                    or layer.get("audio_covered_entry_count", -1) < 0):
                raise ValueError("音频层结构无效")
        else:
            raise ValueError("未知分层类型")
    if used != set(assets):
        raise ValueError("资产清单有未引用或缺失文件")
    for name, (entry_layers, audio_layers) in EDITION_LAYERS.items():
        edition = manifest["editions"][name]
        expected = set(manifest["common_assets"])
        if audio_layers:
            expected.update(manifest["audio_common_assets"])
        for layer in entry_layers + audio_layers:
            expected.update(manifest["layers"][layer]["assets"])
        if (edition.get("entry_layers") != entry_layers or edition.get("audio_layers") != audio_layers
                or set(edition["assets"]) != expected or len(edition["assets"]) != len(expected)
                or edition.get("download_bytes") != manifest_bytes + sum(assets[key]["bytes"] for key in expected)
                or edition.get("entry_count") != sum(
                    manifest["layers"][key]["entry_count"] for key in entry_layers)
                or edition.get("mnemonic_covered_entry_count") != sum(
                    manifest["layers"][key]["mnemonic_covered_entry_count"] for key in entry_layers)
                or edition.get("audio_covered_entry_count") != sum(
                    manifest["layers"][key]["audio_covered_entry_count"] for key in audio_layers)):
            raise ValueError("组合资产或覆盖数无效")
        if audio_layers and edition["audio_covered_entry_count"] != edition["entry_count"]:
            raise ValueError("有声组合未逐词覆盖")
        if name.startswith("lite-") and edition["download_bytes"] >= manifest["lite_cap_bytes"]:
            raise ValueError("lite 超过下载预算")


def read_manifest(root: Path) -> dict:
    raw = (root / "release.json").read_bytes()
    manifest = json.loads(raw)
    validate_manifest(manifest, len(raw))
    return manifest


def verify_layered_release(root: Path, edition: str | None = None, deep: bool = False) -> dict:
    """全量发布核验只扫描每层一次；也能核验只下载了某个组合的客户端目录。"""
    manifest = read_manifest(root)
    chosen = list(manifest["editions"]) if edition is None else [edition]
    if not set(chosen).issubset(manifest["editions"]):
        raise ValueError("该组合尚未发布")
    required = {name for key in chosen for name in manifest["editions"][key]["assets"]}
    if edition is None and {path.name for path in root.iterdir() if path.is_file()} != required | {"release.json"}:
        raise ValueError("发布目录存在缺少或多余资产")
    for name in required:
        meta = manifest["assets"][name]
        if file_hash(asset_path(root, name)) != (meta["bytes"], meta["sha256"]):
            raise ValueError(f"0.0.3 资产损坏：{name}")
    result = {"dictionary_version": VERSION, "deep": deep,
              "editions": {key: manifest["editions"][key] for key in chosen}}
    if not deep:
        return result
    selection = json.loads((root / "selection.json").read_text(encoding="utf-8"))
    catalogs = json.loads((root / "catalogs.json").read_text(encoding="utf-8"))["catalogs"]
    catalog_map = {item["catalog_id"]: item for item in catalogs}
    layer_ids, keys, catalog_counts = {}, {}, {}
    entry_layers = {layer for key in chosen for layer in manifest["editions"][key]["entry_layers"]}
    all_ids = set()
    for layer_name in entry_layers:
        layer = manifest["layers"][layer_name]
        ids, lookup_keys, notes = set(), set(), 0
        for name in layer["assets"]:
            for entry in json_lines(asset_path(root, name)):
                eid = entry["entry_id"]
                card = entry["learning"]
                if (eid in all_ids or entry.get("schema_version") != ENTRY_SCHEMA
                        or card.get("schema_version") != "leximeet.learning-card.v1"
                        or card["audio"]["offline_index_entry_id"] != eid
                        or any(not isinstance(card["lexical"].get(key), list) for key in
                               ("synonyms", "antonyms", "related_words", "phrases"))
                        or not isinstance(card["practice"].get("questions"), list)
                        or not isinstance(card["practice"].get("attested_examples"), list)):
                    raise ValueError("词卡结构或分层去重无效")
                senses = {sense["sense_id"] for sense in entry["senses"]}
                memberships = set()
                for member in card["collections"]:
                    cid = member["catalog_id"]
                    if (cid not in catalog_map or cid in memberships or layer_name != "lite-entries"
                            or member["position"] < 1 or not isinstance(member.get("match_method"), str)
                            or member["category"] != catalog_map[cid]["category"]
                            or member["source"] != catalog_map[cid]["source"]
                            or not set(member["sense_ids"]).issubset(senses)):
                        raise ValueError("词书成员缺失或引用无效")
                    memberships.add(cid)
                    catalog_counts[cid] = catalog_counts.get(cid, 0) + 1
                ids.add(eid)
                lookup_keys.add(entry["lookup_key"])
                all_ids.add(eid)
                notes += bool(card["mnemonics"])
        if len(ids) != layer["entry_count"] or notes != layer["mnemonic_covered_entry_count"]:
            raise ValueError("词卡层覆盖数不一致")
        layer_ids[layer_name], keys[layer_name] = ids, lookup_keys
    lite_ids = layer_ids["lite-entries"]
    if (len(lite_ids) != selection["selected_entry_count"]
            or hashlib.sha256(("\n".join(sorted(lite_ids)) + "\n").encode()).hexdigest()
            != selection["selected_ids_sha256"]
            or not set(selection["required_function_words"]).issubset(keys["lite-entries"])
            or len(catalog_map) != selection["catalog_count"]):
        raise ValueError("lite 名单、功能词或学习目录缺失")
    if any(catalog_counts.get(cid, 0) != item["entry_count"] for cid, item in catalog_map.items()):
        raise ValueError("lite 缺少词书成员")
    audio_layers = {layer for key in chosen for layer in manifest["editions"][key]["audio_layers"]}
    for layer_name in audio_layers:
        layer = manifest["layers"][layer_name]
        entry_layer = "lite-entries" if layer_name == "lite-audio" else "core-entries"
        seen, offsets, streams = set(), {}, {}
        try:
            for item in json_lines(asset_path(root, layer["index"])):
                eid, shard = item["entry_id"], item["shard"]
                if (eid in seen or eid not in layer_ids[entry_layer] or shard not in layer["assets"]
                        or not isinstance(item["offset"], int) or not isinstance(item["bytes"], int)
                        or item["offset"] != offsets.get(shard, 0) or item["bytes"] < 1
                        or item["offset"] + item["bytes"] > manifest["assets"][shard]["bytes"]):
                    raise ValueError("音频索引引用无效")
                if shard not in streams:
                    streams[shard] = asset_path(root, shard).open("rb")
                streams[shard].seek(item["offset"])
                data = streams[shard].read(item["bytes"])
                if (len(data) != item["bytes"] or not data.startswith(b"OggS")
                        or hashlib.sha256(data).hexdigest() != item["sha256"]):
                    raise ValueError("离线录音损坏")
                seen.add(eid)
                offsets[shard] = item["offset"] + item["bytes"]
        finally:
            for stream in streams.values():
                stream.close()
        packs = set(layer["assets"]) - {layer["index"]}
        if (seen != layer_ids[entry_layer] or set(offsets) != packs
                or any(offsets[name] != manifest["assets"][name]["bytes"] for name in packs)):
            raise ValueError("音频层覆盖不完整")
    result["catalog_member_counts"] = catalog_counts
    return result
