"""命令行入口；所有输入路径显式指定，避免意外使用浮动上游版本。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .builder import build, lookup, verify_package, wordnet_candidates


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m leximeet_dictionary")
    commands = root.add_subparsers(dest="command", required=True)
    build_cmd = commands.add_parser("build", help="生成 0.0.1 无音频公共词典与候选目录")
    build_cmd.add_argument("--distribution", type=Path, required=True)
    build_cmd.add_argument("--audit", type=Path, required=True)
    build_cmd.add_argument("--ecdict", type=Path, required=True)
    build_cmd.add_argument("--cmudict", type=Path, required=True)
    build_cmd.add_argument("--wordnet", type=Path, required=True)
    build_cmd.add_argument("--function-words", type=Path, default=Path("sources/function-words.jsonl"))
    build_cmd.add_argument("--editorial", type=Path, default=Path("editorial/corrections.json"))
    build_cmd.add_argument("--lock", type=Path, default=Path("sources.lock.json"))
    build_cmd.add_argument("--out", type=Path, required=True)
    build_cmd.add_argument("--core-size", type=int, default=5000)
    lookup_cmd = commands.add_parser("lookup", help="本地只读查询")
    lookup_cmd.add_argument("--db", type=Path, required=True)
    lookup_cmd.add_argument("word")
    lookup_cmd.add_argument("--wordnet", action="store_true", help="同时展示未对齐的 WordNet 候选概念")
    verify_cmd = commands.add_parser("verify", help="核对所有产物的哈希和 SQLite 完整性")
    verify_cmd.add_argument("directory", type=Path)
    verify_cmd.add_argument("--deep", action="store_true", help="逐行比对 SQLite、JSONL、核心包及引用关系")
    audio_cmd = commands.add_parser("audio-pack", help="对高频词逐文件核权并生成离线录音增量包")
    audio_cmd.add_argument("--db", type=Path, required=True)
    audio_cmd.add_argument("--out", type=Path, required=True)
    audio_cmd.add_argument("--limit", type=int, default=500)
    locked_audio_cmd = commands.add_parser("audio-pack-locked", help="从固定录音清单与文件哈希重建带发音版")
    locked_audio_cmd.add_argument("--db", type=Path, required=True)
    locked_audio_cmd.add_argument("--out", type=Path, required=True)
    locked_audio_cmd.add_argument("--audio-lock", type=Path, default=Path("audio.lock.json"))
    locked_audio_cmd.add_argument("--sources-lock", type=Path, default=Path("sources.lock.json"))
    locked_audio_cmd.add_argument("--source-dir", type=Path, help="本地已缓存、且逐文件通过哈希校验的录音目录")
    cache_cmd = commands.add_parser("cache-audio", help="模拟用户点击朗读后的 Commons 按需缓存")
    cache_cmd.add_argument("--db", type=Path, required=True)
    cache_cmd.add_argument("--cache", type=Path, required=True)
    cache_cmd.add_argument("word")
    cache_cmd.add_argument("--region", default="en-US", choices=("en-US", "en-GB"))
    verify_audio_cmd = commands.add_parser("verify-audio", help="核对带发音版录音哈希和署名")
    verify_audio_cmd.add_argument("directory", type=Path)
    audio_review_cmd = commands.add_parser("audio-review-sheet", help="生成分层录音人工复核工作表")
    audio_review_cmd.add_argument("--audio-manifest", type=Path, required=True)
    audio_review_cmd.add_argument("--out", type=Path, required=True)
    audio_review_cmd.add_argument("--minimum", type=int, default=40)
    report_cmd = commands.add_parser("report", help="生成覆盖率、200 条分层复核样本和查询基线")
    report_cmd.add_argument("--db", type=Path, required=True)
    report_cmd.add_argument("--out", type=Path, required=True)
    package_cmd = commands.add_parser("package", help="生成双版本确定性 tar.gz 候选归档")
    package_cmd.add_argument("--root", type=Path, required=True)
    package_cmd.add_argument("--out", type=Path, required=True)
    core_verify_cmd = commands.add_parser("verify-core", help="核验独立核心资产的 SHA-256、清单与词条")
    core_verify_cmd.add_argument("archive", type=Path)
    core_verify_cmd.add_argument("--sha256", help="从固定版本 Release 清单取得的外层哈希")
    archive_verify_cmd = commands.add_parser("verify-archive", help="流式核验完整无音频/带发音归档")
    archive_verify_cmd.add_argument("archive", type=Path)
    archive_verify_cmd.add_argument("--sha256", help="从固定版本 Release 清单取得的外层哈希")
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "build":
        if args.core_size < 1:
            parser().error("--core-size 必须为正整数")
        inputs = {
            "open-dictionary-v2-distribution-jsonl-gz": args.distribution,
            "open-dictionary-v2-audit-jsonl-gz": args.audit,
            "ecdict-csv": args.ecdict,
            "cmudict-dict": args.cmudict,
            "english-wordnet-2025-core": args.wordnet,
            "wiktextract-function-words": args.function_words,
        }
        result = build(inputs, args.lock, args.out, args.core_size, args.editorial)
    elif args.command == "lookup":
        result = {"entries": lookup(args.db, args.word)}
        if args.wordnet:
            result["wordnet_candidates"] = wordnet_candidates(args.db, args.word)
    elif args.command == "verify":
        result = verify_package(args.directory)
        if args.deep:
            from .integrity import verify_content
            result = {"manifest": result, "content": verify_content(args.directory)}
    elif args.command == "report":
        from .quality import report
        result = report(args.db, args.out)
    elif args.command == "package":
        from .package import package
        result = package(args.root, args.out)
    elif args.command == "verify-core":
        from .core import verify_core_archive
        result = verify_core_archive(args.archive, args.sha256)
    elif args.command == "verify-archive":
        from .package import verify_archive
        result = verify_archive(args.archive, args.sha256)
    else:
        from .audio import build_audio, cache_on_demand, install_locked_audio, verify_audio, write_audio_review_sheet
        if args.command == "audio-pack":
            result = build_audio(args.db, args.out, args.limit)
        elif args.command == "audio-pack-locked":
            result = install_locked_audio(args.db, args.out, args.audio_lock, args.sources_lock, args.source_dir)
        elif args.command == "cache-audio":
            result = cache_on_demand(args.db, args.word, args.cache, args.region)
        elif args.command == "audio-review-sheet":
            result = write_audio_review_sheet(args.audio_manifest, args.out, args.minimum)
        else:
            result = verify_audio(args.directory)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
