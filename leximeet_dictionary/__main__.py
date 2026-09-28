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
    build_cmd.add_argument("--lock", type=Path, default=Path("sources.lock.json"))
    build_cmd.add_argument("--out", type=Path, required=True)
    build_cmd.add_argument("--core-size", type=int, default=5000)
    lookup_cmd = commands.add_parser("lookup", help="本地只读查询")
    lookup_cmd.add_argument("--db", type=Path, required=True)
    lookup_cmd.add_argument("word")
    lookup_cmd.add_argument("--wordnet", action="store_true", help="同时展示未对齐的 WordNet 候选概念")
    verify_cmd = commands.add_parser("verify", help="核对所有产物的哈希和 SQLite 完整性")
    verify_cmd.add_argument("directory", type=Path)
    audio_cmd = commands.add_parser("audio-pack", help="对高频词逐文件核权并生成离线录音增量包")
    audio_cmd.add_argument("--db", type=Path, required=True)
    audio_cmd.add_argument("--out", type=Path, required=True)
    audio_cmd.add_argument("--limit", type=int, default=500)
    cache_cmd = commands.add_parser("cache-audio", help="模拟用户点击朗读后的 Commons 按需缓存")
    cache_cmd.add_argument("--db", type=Path, required=True)
    cache_cmd.add_argument("--cache", type=Path, required=True)
    cache_cmd.add_argument("word")
    cache_cmd.add_argument("--region", default="en-US", choices=("en-US", "en-GB"))
    verify_audio_cmd = commands.add_parser("verify-audio", help="核对带发音版录音哈希和署名")
    verify_audio_cmd.add_argument("directory", type=Path)
    report_cmd = commands.add_parser("report", help="生成覆盖率、200 条分层复核样本和查询基线")
    report_cmd.add_argument("--db", type=Path, required=True)
    report_cmd.add_argument("--out", type=Path, required=True)
    package_cmd = commands.add_parser("package", help="生成双版本确定性 tar.gz 候选归档")
    package_cmd.add_argument("--root", type=Path, required=True)
    package_cmd.add_argument("--out", type=Path, required=True)
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
        }
        result = build(inputs, args.lock, args.out, args.core_size)
    elif args.command == "lookup":
        result = {"entries": lookup(args.db, args.word)}
        if args.wordnet:
            result["wordnet_candidates"] = wordnet_candidates(args.db, args.word)
    elif args.command == "verify":
        result = verify_package(args.directory)
    elif args.command == "report":
        from .quality import report
        result = report(args.db, args.out)
    elif args.command == "package":
        from .package import package
        result = package(args.root, args.out)
    else:
        from .audio import build_audio, cache_on_demand, verify_audio
        if args.command == "audio-pack":
            result = build_audio(args.db, args.out, args.limit)
        elif args.command == "cache-audio":
            result = cache_on_demand(args.db, args.word, args.cache, args.region)
        else:
            result = verify_audio(args.directory)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
