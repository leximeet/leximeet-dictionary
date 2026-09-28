"""为固定词库逐词生成可续跑的离线音频缓存。"""

from __future__ import annotations

import array
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unicodedata
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .audio import verify_audio
from .builder import file_hash


AUDIO_SCHEMA = "leximeet.offline-audio.v1"
CORE_WHERE = ("origin='curated' OR rank IS NOT NULL OR "
              "json_array_length(json_extract(payload,'$.ecdict.exam_tags'))>0")
VOICE = "en-us"
SPEED = 160
BITRATE = 16
COMPLEXITY = 5


def ordered_entries(db: sqlite3.Connection, core: bool):
    """核心词在前；完整版只需在其后追加非核心词，不重复制作录音。"""
    where = CORE_WHERE if core else f"NOT ({CORE_WHERE})"
    order = "rank IS NULL,rank,headword,entry_id" if core else "headword,entry_id"
    yield from db.execute(f"SELECT entry_id,headword FROM entries WHERE {where} ORDER BY {order}")


def _tool_version(command: str) -> str:
    binary = shutil.which(command)
    if binary is None:
        raise FileNotFoundError(f"缺少音频工具：{command}")
    option = "--version" if command == "espeak-ng" else "--version"
    run = subprocess.run([binary, option], capture_output=True, text=True, check=True)
    return (run.stdout or run.stderr).splitlines()[0].split("  Data at:", 1)[0]


def synthesis_lock() -> dict:
    """锁定实际参与生成的工具和参数，防止续跑时混入另一种声音。"""
    actual = {"schema_version": AUDIO_SCHEMA, "engine": _tool_version("espeak-ng"),
              "encoder": _tool_version("opusenc"), "voice": VOICE, "speed": SPEED,
              "bitrate_kbps": BITRATE, "complexity": COMPLEXITY, "format": "Ogg Opus"}
    expected = json.loads((Path(__file__).resolve().parent.parent / "audio-tools.lock.json").read_text())
    if actual != expected:
        raise ValueError("音频工具或参数与 audio-tools.lock.json 不一致")
    return actual


def _audible(wav_bytes: bytes) -> bool:
    try:
        with wave.open(io.BytesIO(wav_bytes)) as stream:
            if stream.getsampwidth() != 2 or stream.getnchannels() != 1:
                return False
            samples = array.array("h", stream.readframes(stream.getnframes()))
            if not samples:
                return False
            # 音频不能只有容器头或静音；短词也至少需要 0.08 秒的实际声波。
            active = sum(abs(sample) > 100 for sample in samples)
            return active >= int(stream.getframerate() * 0.08)
    except (EOFError, ValueError, wave.Error):
        return False


def _fallback_text(headword: str) -> str:
    """原词头发不出声时读出字符名称，并在清单中明确标记为拼读。"""
    parts = []
    for char in headword[:100]:
        if char.isascii() and char.isalnum():
            parts.append(char)
        elif not char.isspace():
            parts.append(unicodedata.name(char, "symbol").lower())
    return " ".join(parts) or "unpronounceable symbol"


def _synthesize(item: tuple[str, str]) -> tuple[str, str, bytes, str]:
    entry_id, headword = item
    spoken_text = headword
    style = "headword"
    for attempt in range(2):
        run = subprocess.run(["espeak-ng", "--stdout", "-v", VOICE, "-s", str(SPEED),
                              "-z", "-D", "--stdin"], input=(spoken_text + "\n").encode("utf-8"),
                             capture_output=True, timeout=30, check=True)
        if _audible(run.stdout):
            break
        if attempt:
            raise ValueError(f"词头无法生成有效音频：{headword!r}")
        spoken_text, style = _fallback_text(headword), "spelled-characters"
    # 固定 Ogg 流 serial，避免编码器的随机编号让重建哈希不稳定。
    serial = int.from_bytes(hashlib.sha256(entry_id.encode("utf-8")).digest()[:4], "big")
    encoded = subprocess.run(["opusenc", "--quiet", "--speech", "--bitrate", str(BITRATE),
                              "--comp", str(COMPLEXITY), "--padding", "0", "--serial",
                              str(serial), "-", "-"], input=run.stdout, capture_output=True,
                             timeout=30, check=True).stdout
    if not encoded.startswith(b"OggS") or b"OpusHead" not in encoded[:256]:
        raise ValueError(f"编码器没有生成 Ogg Opus：{headword!r}")
    return entry_id, headword, encoded, style


def _open_cache(path: Path, fingerprint: dict) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    db.execute("""CREATE TABLE IF NOT EXISTS clips(
        entry_id TEXT PRIMARY KEY,headword TEXT NOT NULL,path TEXT NOT NULL,
        bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,kind TEXT NOT NULL,
        style TEXT NOT NULL,source_ref TEXT)""")
    value = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    previous = db.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
    if previous and previous[0] != value:
        db.close()
        raise ValueError("音频缓存输入或工具版本已变化；请使用新目录重新构建")
    db.execute("INSERT OR REPLACE INTO metadata VALUES ('fingerprint',?)", (value,))
    db.commit()
    return db


def _store_clip(root: Path, db: sqlite3.Connection, entry_id: str, headword: str,
                payload: bytes, kind: str, style: str, source_ref: str | None) -> None:
    # 缓存文件名只取散列，词条 ID 即使含路径字符也不能逃出输出目录。
    key = hashlib.sha256(entry_id.encode("utf-8")).hexdigest()
    relative = f"files/{key[:2]}/{key}.ogg"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        stream.write(payload)
        temp_path = Path(stream.name)
    os.replace(temp_path, target)
    db.execute("INSERT OR REPLACE INTO clips VALUES (?,?,?,?,?,?,?,?)", (
        entry_id, headword, relative, len(payload), hashlib.sha256(payload).hexdigest(),
        kind, style, source_ref))


def _cached(root: Path, db: sqlite3.Connection, entry_id: str, headword: str) -> bool:
    row = db.execute("SELECT headword,path,bytes,sha256 FROM clips WHERE entry_id=?", (entry_id,)).fetchone()
    if not row or row[0] != headword:
        return False
    path = root / row[1]
    if not path.is_file():
        return False
    return file_hash(path) == (row[2], row[3])


def build_offline_audio(source_db: Path, out: Path, human_dir: Path | None = None,
                        workers: int = 8, batch_size: int = 256,
                        max_entries: int | None = None, all_entries: bool = False) -> dict:
    """默认只生成核心词音频；扩展实验可续跑全量词头。"""
    if workers < 1 or batch_size < 1 or (max_entries is not None and max_entries < 1):
        raise ValueError("并发数、批量大小和最大词条数必须为正整数")
    lock = synthesis_lock()
    human_assets: dict[str, dict] = {}
    if human_dir is not None:
        human = verify_audio(human_dir)
        human_assets = {asset["entry_id"]: asset for asset in human["assets"]}
        human_hash = file_hash(human_dir / "manifest.json")[1]
    else:
        human_hash = None
    source_hash = file_hash(source_db)[1]
    fingerprint = {"source_db_sha256": source_hash, "human_manifest_sha256": human_hash,
                   "synthesis": lock}
    cache = _open_cache(out / "clips.sqlite", fingerprint)
    source = sqlite3.connect(f"file:{source_db.resolve()}?mode=ro", uri=True)
    processed = generated = reused = 0
    last_report_bucket = 0
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for core in ((True, False) if all_entries else (True,)):
                cursor = ordered_entries(source, core)
                try:
                    while True:
                        batch = [next(cursor, None) for _ in range(batch_size)]
                        batch = [item for item in batch if item is not None]
                        if not batch:
                            break
                        if max_entries is not None:
                            batch = batch[:max_entries - processed]
                        pending = []
                        for entry_id, headword in batch:
                            if _cached(out, cache, entry_id, headword):
                                reused += 1
                                continue
                            human = human_assets.get(entry_id)
                            if human and human["headword"] == headword:
                                payload = (human_dir / human["path"]).read_bytes()
                                _store_clip(out, cache, entry_id, headword, payload,
                                            "human", "headword", human["source_page"])
                            else:
                                pending.append((entry_id, headword))
                        for entry_id, headword, payload, style in pool.map(_synthesize, pending):
                            _store_clip(out, cache, entry_id, headword, payload,
                                        "synthetic", style, "espeak-ng/en-us")
                            generated += 1
                        cache.commit()
                        processed += len(batch)
                        report_bucket = processed // (batch_size * 20)
                        if report_bucket > last_report_bucket:
                            print(json.dumps({"processed": processed, "generated": generated,
                                              "reused": reused}, ensure_ascii=False), flush=True)
                            last_report_bucket = report_bucket
                        if max_entries is not None and processed >= max_entries:
                            break
                finally:
                    cursor.close()
                if max_entries is not None and processed >= max_entries:
                    break
        total = source.execute("SELECT count(*) FROM entries").fetchone()[0]
        covered = cache.execute("SELECT count(*) FROM clips").fetchone()[0]
        core_total = source.execute(f"SELECT count(*) FROM entries WHERE {CORE_WHERE}").fetchone()[0]
        # 缓存可含扩展实验的非核心音频，完成度只按本次目标计算。
        source.execute("ATTACH DATABASE ? AS audio_cache", (str((out / "clips.sqlite").resolve()),))
        covered_core = source.execute(
            f"SELECT count(*) FROM entries e JOIN audio_cache.clips c ON c.entry_id=e.entry_id "
            f"WHERE {CORE_WHERE}").fetchone()[0]
        target = total if all_entries else core_total
        result = {"schema_version": AUDIO_SCHEMA, "source_entries": total,
                  "target_entries": target, "cached_entries": covered,
                  "covered_core_entries": covered_core,
                  "complete": (covered == total if all_entries else covered_core == core_total),
                  "processed_this_run": processed, "generated_this_run": generated,
                  "reused_this_run": reused, "fingerprint": fingerprint}
        (out / "build-result.json").write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result
    finally:
        source.close()
        cache.close()
