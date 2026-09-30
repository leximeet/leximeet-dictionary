"""小型真实组合测试：目录完整、无损词卡、预算、增量安装及损坏后的回退。"""

import gzip
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from leximeet_dictionary.builder import canonical, file_hash, lookup
from leximeet_dictionary.compressed import COMPRESSION, json_lines, write_record, writer
from leximeet_dictionary.install import extract_installed_audio, install_package, plan_upgrade
from leximeet_dictionary.learning import build_learning, list_members
from leximeet_dictionary.release import build_release
from leximeet_dictionary.release_v2 import build_core_release
from leximeet_dictionary.release_v3 import (
    EDITION_LAYERS, build_layered_release, verify_layered_release, write_manifest,
)
from test_release import fixture
from scripts.publish_v3 import mismatches


def package_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    source, cache = fixture(root)
    # 一个可选词的录音足够大，确保 lite 只选必选词，core 存在真实差量。
    data = b"OggS-OpusHead-beta" + b"x" * 80_000
    (cache / "files/beta.ogg").write_bytes(data)
    with closing(sqlite3.connect(cache / "clips.sqlite")) as db, db:
        db.execute("UPDATE clips SET bytes=?,sha256=? WHERE entry_id='beta'",
                   (len(data), hashlib.sha256(data).hexdigest()))
    base = root / "v1"
    build_release(source, cache, base)
    learning_lock = root / "learning-sources.lock.json"
    learning_lock.write_text(canonical({
        "schema_version": "leximeet.learning-sources.v1",
        "base_release_manifest_sha256": file_hash(base / "release.json")[1]}))
    learning = root / "learning.sqlite"
    build_learning(base / "core.entries.jsonl.gz", learning, learning_lock)
    with closing(sqlite3.connect(learning)) as db, db:
        db.execute("INSERT INTO catalogs VALUES (?,?,?,?,?)",
                   ("exam:fixture", "测试词书", "exam", "ecdict", "source-tag"))
        db.execute("INSERT INTO members VALUES (?,?,?,?,?,?)", (
            "exam:fixture", "alpha", 1, '["sense-alpha"]', "exact",
            '{"source_word":"alpha"}'))
    core = root / "v2"
    build_core_release(base, learning, learning_lock, core)
    functions = root / "functions.jsonl"
    functions.write_text('{"word":"alpha"}\n', encoding="utf-8")
    full = source / "entries.jsonl.gz"
    lock = root / "package-sources.lock.json"
    lock.write_text(canonical({
        "schema_version": "leximeet.package-sources.v1",
        "core": {"version": "0.0.2", "manifest_sha256": file_hash(core / "release.json")[1]},
        "full": {"version": "0.0.1", "bytes": file_hash(full)[0],
                 "sha256": file_hash(full)[1], "entry_count": 3},
        "function_words_sha256": file_hash(functions)[1], "compression": COMPRESSION}))
    return core, full, lock, functions


class PackageTests(unittest.TestCase):
    def test_five_combinations_preserve_content_and_keep_lite_under_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = package_fixture(root)
            out = root / "release"
            manifest = build_layered_release(*args[:3], out, args[3], lite_cap_bytes=160_000)
            again = build_layered_release(*args[:3], root / "again", args[3], lite_cap_bytes=160_000)
            self.assertEqual(manifest, again)
            self.assertEqual(set(manifest["editions"]), set(EDITION_LAYERS))
            self.assertNotIn("full-audio", manifest["editions"])
            self.assertEqual(manifest["editions"]["lite-audio"]["entry_count"], 1)
            self.assertEqual(manifest["editions"]["core-audio"]["entry_count"], 2)
            self.assertEqual(manifest["editions"]["full-text"]["entry_count"], 3)
            for name in ("lite-text", "lite-audio"):
                edition = manifest["editions"][name]
                self.assertLess(edition["download_bytes"], 160_000)
                self.assertEqual(edition["download_bytes"],
                                 (out / "release.json").stat().st_size + sum(
                                     (out / asset).stat().st_size for asset in edition["assets"]))
            for name in ("lite-text", "core-text", "full-text"):
                self.assertFalse(any(asset.endswith(".pack") for asset in manifest["editions"][name]["assets"]))
            with gzip.open(args[0] / "core.entries.v2.jsonl.gz", "rt") as stream:
                original = {item["entry_id"]: item for item in map(json.loads, stream)}
            actual = {item["entry_id"]: item for key in ("lite-entries", "core-entries")
                      for name in manifest["layers"][key]["assets"] for item in json_lines(out / name)}
            for eid, entry in actual.items():
                for member in entry["learning"]["collections"]:
                    self.assertEqual(member.pop("match_method"), "exact")
                self.assertEqual(entry, original[eid])
            report = verify_layered_release(out, deep=True)
            self.assertEqual(report["catalog_member_counts"], {"exam:fixture": 1})
            for edition in EDITION_LAYERS:
                verify_layered_release(out, edition, deep=True)

    def test_incremental_install_indexes_lookup_and_rolls_back_on_bad_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = package_fixture(root)
            out, cache, installation = root / "release", root / "objects", root / "installation"
            manifest = build_layered_release(*args[:3], out, args[3], lite_cap_bytes=160_000)
            user_data = root / "user-notebook.json"
            user_data.write_text('{"progress":42}')
            lite = install_package(out, cache, installation, "lite-text", source=out)
            self.assertEqual(lookup(Path(lite["package_path"]) / "dictionary.sqlite", "ALPHA")[0]["headword"], "alpha")
            self.assertEqual(list_members(Path(lite["package_path"]) / "dictionary.sqlite", "exam:fixture")[0]["match_method"], "exact")
            lite_audio_plan = plan_upgrade(out, cache, "lite-audio")
            self.assertNotIn("entries-lite.jsonl.zst", lite_audio_plan["download"])
            audio = install_package(out, cache, installation, "lite-audio", source=out)
            extract_installed_audio(Path(audio["package_path"]), "alpha", root / "alpha.ogg")
            core_plan = plan_upgrade(out, cache, "core-audio")
            difference = set(manifest["editions"]["core-audio"]["assets"]) - set(
                manifest["editions"]["lite-audio"]["assets"])
            self.assertEqual(set(core_plan["download"]), difference)
            text = install_package(out, cache, installation, "core-text", source=out)
            self.assertEqual(text["audio_covered_entry_count"], 0)
            core = install_package(out, cache, installation, "core-audio", source=out)
            self.assertTrue(lookup(Path(core["package_path"]) / "dictionary.sqlite", "beta")[0]["learning"]["mnemonics"])
            full_plan = plan_upgrade(out, cache, "full-text")
            self.assertEqual(set(full_plan["download"]), set(manifest["layers"]["full-entries"]["assets"]))
            before = (installation / "current.json").read_bytes()
            broken = root / "broken"
            broken.mkdir()
            damaged = full_plan["download"][0]
            (broken / damaged).write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "哈希|大小"):
                install_package(out, cache, installation, "full-text", source=broken)
            self.assertEqual((installation / "current.json").read_bytes(), before)
            # 下载已成功、开始导入索引后发生错误，也不能切换当前词包。
            with patch("leximeet_dictionary.install.build_index",
                       side_effect=ValueError("索引构建失败")):
                with self.assertRaisesRegex(ValueError, "索引构建失败"):
                    install_package(out, cache, installation, "full-text", source=out)
            self.assertEqual((installation / "current.json").read_bytes(), before)
            full = install_package(out, cache, installation, "full-text", source=out)
            self.assertEqual(lookup(Path(full["package_path"]) / "dictionary.sqlite", "gamma")[0]["headword"], "gamma")
            with self.assertRaises(KeyError):
                extract_installed_audio(Path(full["package_path"]), "gamma", root / "gamma.ogg")
            blob = cache / manifest["assets"]["entries-lite.jsonl.zst"]["sha256"]
            blob.write_bytes(b"damaged cache")
            self.assertIn("entries-lite.jsonl.zst", plan_upgrade(out, cache, "lite-text")["download"])
            self.assertEqual(user_data.read_text(), '{"progress":42}')
            self.assertTrue(Path(lite["package_path"]).is_dir())

    def test_source_lock_budget_and_protocol_corruption_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = package_fixture(root)
            with self.assertRaisesRegex(ValueError, "必选"):
                build_layered_release(*args[:3], root / "too-small", args[3], lite_cap_bytes=35_000)
            out = root / "release"
            manifest = build_layered_release(*args[:3], out, args[3], lite_cap_bytes=160_000)
            original_manifest = (out / "release.json").read_bytes()
            too_large = json.loads(canonical(manifest))
            too_large["lite_cap_bytes"] = 1
            with self.assertRaisesRegex(ValueError, "最终 lite"):
                write_manifest(out, too_large)
            self.assertEqual((out / "release.json").read_bytes(), original_manifest)
            index = manifest["layers"]["lite-audio"]["index"]
            items = list(json_lines(out / index))
            items[0]["offset"] += 1
            with writer(out / index) as target:
                for item in items:
                    write_record(target, item)
            size, sha = file_hash(out / index)
            manifest["assets"][index].update(bytes=size, sha256=sha)
            write_manifest(out, manifest)
            with self.assertRaisesRegex(ValueError, "音频索引"):
                verify_layered_release(out, deep=True)
            manifest["assets"]["../secret"] = dict(manifest["assets"]["LICENSE"])
            write_manifest(out, manifest)
            with self.assertRaisesRegex(ValueError, "非法资产路径"):
                verify_layered_release(out)
            args[3].write_text('{"word":"changed"}\n')
            with self.assertRaisesRegex(ValueError, "固定来源"):
                build_layered_release(*args[:3], root / "bad-source", args[3])

    def test_publisher_resumes_drafts_and_does_not_overwrite_published_assets(self):
        expected = {"a": {"bytes": 3, "sha256": "1" * 64}}
        valid = {"isDraft": True, "assets": [{"name": "a", "size": 3, "digest": "sha256:" + "1" * 64}]}
        self.assertEqual(mismatches(expected, valid), [])
        self.assertEqual(mismatches(expected, {"isDraft": True, "assets": []}), ["a"])
        valid["assets"][0]["digest"] = None
        self.assertEqual(mismatches(expected, valid), ["a"])
        valid["isDraft"] = False
        with self.assertRaisesRegex(ValueError, "禁止覆盖"):
            mismatches(expected, valid)
        with self.assertRaisesRegex(ValueError, "额外"):
            mismatches(expected, {"isDraft": True, "assets": [
                {"name": "unexpected", "size": 3, "digest": "sha256:" + "1" * 64}]})


if __name__ == "__main__":
    unittest.main()
