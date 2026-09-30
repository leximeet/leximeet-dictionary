"""两个版本、共享分片、逐词覆盖及损坏拒绝的最小集成测试。"""

import gzip
import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from leximeet_dictionary.builder import file_hash
from leximeet_dictionary.learning import build_learning
from leximeet_dictionary.offline_audio import _fallback_text, _synthesize, synthesis_lock
from leximeet_dictionary.release import assemble_sqlite, build_release, extract_audio, verify_release
from leximeet_dictionary.release_v2 import build_core_release, verify_core_release


def fixture(root: Path) -> tuple[Path, Path]:
    source = root / "source"
    cache = root / "cache"
    source.mkdir()
    cache.mkdir()
    (source / "notices").mkdir()
    (source / "DATA-LICENSE.md").write_text("fixture license\n", encoding="utf-8")
    rows = []
    for entry_id, headword, origin, rank, tags in (
            ("alpha", "alpha", "curated", None, []),
            ("beta", "beta", "ecdict-fallback", 5, []),
            ("gamma", "gamma", "ecdict-fallback", None, [])):
        payload = {"schema_version": "leximeet.entry.v1", "entry_id": entry_id,
                   "headword": headword, "origin": origin, "ecdict": {"exam_tags": tags},
                   "lookup_key": headword, "memory_hook_zh": "记住 " + headword if rank else None,
                   "senses": [{"sense_id": "sense-" + entry_id,
                               "pos": "noun", "topics": [], "short_gloss": headword}]}
        payload["ecdict"]["frequency_ranks"] = {"frq": rank} if rank else {}
        rows.append((entry_id, headword, headword, origin, rank,
                     json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
    with closing(sqlite3.connect(source / "dictionary.sqlite")) as db, db:
        db.execute("CREATE TABLE entries(entry_id TEXT PRIMARY KEY,headword TEXT,lookup_key TEXT,"
                   "origin TEXT,rank INTEGER,payload TEXT)")
        db.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?)", rows)
    with gzip.open(source / "entries.jsonl.gz", "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(row[5] + "\n")
    outputs = {name: dict(zip(("bytes", "sha256"), file_hash(source / name)))
               for name in ("dictionary.sqlite", "entries.jsonl.gz", "DATA-LICENSE.md")}
    (source / "manifest.json").write_text(json.dumps({
        "dictionary_version": "0.0.1", "entry_schema": "leximeet.entry.v1",
        "counts": {"total_entries": 3}, "inputs": {}, "outputs": outputs}), encoding="utf-8")
    (cache / "files").mkdir()
    with closing(sqlite3.connect(cache / "clips.sqlite")) as db, db:
        db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        db.execute("CREATE TABLE clips(entry_id TEXT PRIMARY KEY,headword TEXT,path TEXT,"
                   "bytes INTEGER,sha256 TEXT,kind TEXT,style TEXT,source_ref TEXT)")
        db.execute("INSERT INTO metadata VALUES ('fingerprint',?)", (json.dumps({
            "source_db_sha256": file_hash(source / "dictionary.sqlite")[1],
            "human_manifest_sha256": None, "synthesis": {"engine": "fixture"}}),))
        for entry_id, headword, *_ in rows:
            audio = b"OggS-OpusHead-" + entry_id.encode() + b"x" * 600
            path = f"files/{entry_id}.ogg"
            (cache / path).write_bytes(audio)
            db.execute("INSERT INTO clips VALUES (?,?,?,?,?,?,?,?)", (
                entry_id, headword, path, len(audio), hashlib.sha256(audio).hexdigest(),
                "synthetic", "headword", "fixture"))
    return source, cache


class ReleaseTests(unittest.TestCase):
    def test_v2_core_release_records_partial_learning_and_preserves_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, cache = fixture(root)
            base = root / "base-release"
            build_release(source, cache, base, shard_bytes=1024)
            core = base / "core.entries.jsonl.gz"
            lock = root / "learning-sources.lock.json"
            lock.write_text(json.dumps({"schema_version": "leximeet.learning-sources.v1",
                                        "base_release_manifest_sha256": file_hash(base / "release.json")[1]}),
                            encoding="utf-8")
            learning_db = root / "learning.sqlite"
            report = build_learning(core, learning_db, lock)
            self.assertEqual(report["entries_without_learning_material"], 1)
            output = root / "v2-release"
            manifest = build_core_release(base, learning_db, lock, output)
            repeated = build_core_release(base, learning_db, lock, root / "v2-release-again")
            self.assertEqual(manifest, repeated)
            self.assertEqual(set(manifest["editions"]), {"core"})
            self.assertEqual(manifest["editions"]["core"]["entry_count"], 2)
            self.assertEqual(manifest["editions"]["core"]["mnemonic_covered_entry_count"], 1)
            self.assertEqual(verify_core_release(output, deep=True)["audio_covered_entry_count"], 2)
            shard = next(name for name in manifest["assets"] if name.endswith(".pack"))
            self.assertEqual(file_hash(output / shard), file_hash(base / shard))
            with (base / "release.json").open("a", encoding="utf-8") as stream:
                stream.write("\n")
            with self.assertRaisesRegex(ValueError, "基础 Release 与固定来源锁不一致"):
                build_core_release(base, learning_db, lock, root / "wrong-base")
            with (output / shard).open("ab") as stream:
                stream.write(b"damage")
            with self.assertRaisesRegex(ValueError, "资产损坏"):
                verify_core_release(output)

    def test_shared_core_shards_and_full_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, cache = fixture(root)
            release = build_release(source, cache, root / "release", shard_bytes=1024)
            repeated = build_release(source, cache, root / "release-again", shard_bytes=1024)
            self.assertEqual(release, repeated)
            self.assertTrue(all("/" not in name for name in release["assets"]))
            self.assertEqual(release["editions"]["core"]["entry_count"], 2)
            self.assertEqual(release["editions"]["full"]["entry_count"], 3)
            core_assets = set(release["editions"]["core"]["assets"])
            core_shards = {name for name in core_assets if name.startswith("audio-core-")}
            self.assertEqual(len(core_shards), 2)
            self.assertLessEqual(core_assets, set(release["editions"]["full"]["assets"]))
            self.assertEqual(verify_release(root / "release", "core", deep=True)["audio_covered_entry_count"], 2)
            self.assertEqual(verify_release(root / "release", "full", deep=True)["audio_covered_entry_count"], 2)
            assembled = root / "assembled.sqlite"
            assemble_sqlite(root / "release", assembled)
            self.assertEqual(file_hash(assembled), file_hash(source / "dictionary.sqlite"))
            result = extract_audio(root / "release", "full", "beta", root / "sample.ogg")
            self.assertEqual(result["bytes"], (root / "sample.ogg").stat().st_size)
            with self.assertRaises(KeyError):
                extract_audio(root / "release", "core", "gamma", root / "missing.ogg")
            with self.assertRaises(KeyError):
                extract_audio(root / "release", "full", "gamma", root / "missing.ogg")

    def test_missing_clip_or_corrupted_shard_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, cache = fixture(root)
            with sqlite3.connect(cache / "clips.sqlite") as db:
                db.execute("DELETE FROM clips WHERE entry_id='beta'")
            with self.assertRaisesRegex(ValueError, "核心词离线音频缺少"):
                build_release(source, cache, root / "incomplete", shard_bytes=1024)
            with sqlite3.connect(cache / "clips.sqlite") as db:
                audio = (cache / "files/beta.ogg").read_bytes()
                db.execute("INSERT INTO clips VALUES (?,?,?,?,?,?,?,?)", (
                    "beta", "beta", "files/beta.ogg", len(audio),
                    hashlib.sha256(audio).hexdigest(), "synthetic", "headword", "fixture"))
            release = build_release(source, cache, root / "release", shard_bytes=1024)
            shard = next(name for name in release["assets"] if name.startswith("audio-core-"))
            with (root / "release" / shard).open("ab") as stream:
                stream.write(b"damage")
            with self.assertRaisesRegex(ValueError, "Release 资产损坏"):
                verify_release(root / "release", "full")

    def test_manifest_cannot_read_outside_release_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, cache = fixture(root)
            build_release(source, cache, root / "release", shard_bytes=1024)
            manifest_path = root / "release/release.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["editions"]["core"]["assets"][0] = "../source/dictionary.sqlite"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "非法资产路径"):
                verify_release(root / "release", "core")

    def test_punctuation_fallback_is_explicit(self):
        self.assertIn("ampersand", _fallback_text("&"))

    @unittest.skipUnless(all(shutil.which(name) for name in ("espeak-ng", "opusenc", "opusdec")),
                         "本机没有固定版本的音频工具")
    def test_real_encoder_is_deterministic_and_decodable(self):
        try:
            synthesis_lock()
        except ValueError as error:
            self.skipTest(str(error))
        for entry_id, headword in (("test-a", "a"), ("test-phrase", "my body, my choice")):
            first = _synthesize((entry_id, headword))[2]
            self.assertEqual(first, _synthesize((entry_id, headword))[2])
            with tempfile.TemporaryDirectory() as temp:
                ogg = Path(temp) / "word.ogg"
                wav = Path(temp) / "word.wav"
                ogg.write_bytes(first)
                subprocess.run(["opusdec", "--quiet", str(ogg), str(wav)], check=True)
                self.assertGreater(wav.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
