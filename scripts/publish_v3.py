"""仅供 tag 工作流调用：补齐草稿资产，核验 GitHub 摘要，再发布。"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from leximeet_dictionary.builder import file_hash
from leximeet_dictionary.release_v3 import read_manifest


def expected_assets(root: Path) -> dict:
    manifest = read_manifest(root)
    result = {key: {"bytes": value["bytes"], "sha256": value["sha256"]}
              for key, value in manifest["assets"].items()}
    size, sha = file_hash(root / "release.json")
    result["release.json"] = {"bytes": size, "sha256": sha}
    return result


def mismatches(expected: dict, remote: dict) -> list[str]:
    """未知的额外资产和已发布包的修改都不自动处理；发布版本保持不可变。"""
    actual = {item["name"]: item for item in remote["assets"]}
    if len(actual) != len(remote["assets"]) or set(actual) - set(expected):
        raise ValueError("远端 Release 存在重复或额外资产，请维护者核对")
    pending = [name for name, meta in expected.items()
               if name not in actual or actual[name]["size"] != meta["bytes"]
               or actual[name].get("digest") != "sha256:" + meta["sha256"]]
    if pending and not remote["isDraft"]:
        raise ValueError("已发布资产与构建不同，禁止覆盖已有版本")
    return pending


def publish(root: Path, repo: str, notes: Path) -> None:
    expected = expected_assets(root)
    tag = "v0.0.3"

    def gh(*args: str) -> str:
        return subprocess.check_output(["gh", *args, "--repo", repo], text=True)

    def view() -> dict:
        return json.loads(gh("release", "view", tag, "--json", "isDraft,assets"))

    probe = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo, "--json", "isDraft,assets"],
        text=True, capture_output=True)
    if probe.returncode:
        if "release not found" not in probe.stderr.lower():
            raise RuntimeError(probe.stderr.strip())
        gh("release", "create", tag, "--draft", "--verify-tag", "--title",
           "LexiMeet Dictionary 0.0.3", "--notes-file", str(notes))
    remote = view()
    for name in mismatches(expected, remote):
        # 仅草稿允许补齐/替换；每片独立上传，中断后重跑可复用已正确上传的片。
        gh("release", "upload", tag, str(root / name), "--clobber")
    remote = view()
    if mismatches(expected, remote):
        raise ValueError("上传后的 GitHub 资产大小或 SHA-256 不匹配")
    if remote["isDraft"]:
        gh("release", "edit", tag, "--draft=false")
    published = view()
    if published["isDraft"] or mismatches(expected, published):
        raise ValueError("Release 未成功发布或发布时资产发生改变")
    print(json.dumps({"tag": tag, "asset_count": len(expected), "published": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--notes", type=Path, required=True)
    options = parser.parse_args()
    publish(options.root, options.repo, options.notes)
