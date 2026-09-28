"""命令行入口；所有输入路径显式指定，避免意外使用浮动上游版本。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .builder import build, lookup, verify_package, wordnet_candidates


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m leximeet_dictionary")
    commands = root.add_subparsers(dest="command", required=True)
    build_cmd = commands.add_parser("build", help="生成固定来源的 0.0.1 词典数据底座")
    build_cmd.add_argument("--distribution", type=Path, required=True)
    build_cmd.add_argument("--audit", type=Path, required=True)
    build_cmd.add_argument("--ecdict", type=Path, required=True)
    build_cmd.add_argument("--cmudict", type=Path, required=True)
    build_cmd.add_argument("--wordnet", type=Path, required=True)
    build_cmd.add_argument("--function-words", type=Path, default=Path("sources/function-words.jsonl"))
    build_cmd.add_argument("--editorial", type=Path, default=Path("editorial/corrections.json"))
    build_cmd.add_argument("--lock", type=Path, default=Path("sources.lock.json"))
    build_cmd.add_argument("--out", type=Path, required=True)
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
    offline_cmd = commands.add_parser("offline-audio", help="生成可续跑的核心词离线音频缓存")
    offline_cmd.add_argument("--db", type=Path, required=True)
    offline_cmd.add_argument("--out", type=Path, required=True)
    offline_cmd.add_argument("--human-dir", type=Path, help="已核验 Commons 录音目录")
    offline_cmd.add_argument("--workers", type=int, default=8)
    offline_cmd.add_argument("--batch-size", type=int, default=256)
    offline_cmd.add_argument("--max-entries", type=int, help="试产用；部分缓存不能打正式包")
    offline_cmd.add_argument("--all-entries", action="store_true", help="后续版本实验用；0.0.1 只要求核心词")
    release_cmd = commands.add_parser("release-build", help="生成共享核心分片的 core/full 两版资产")
    release_cmd.add_argument("--source", type=Path, required=True)
    release_cmd.add_argument("--audio-cache", type=Path, required=True)
    release_cmd.add_argument("--out", type=Path, required=True)
    release_cmd.add_argument("--shard-mib", type=int, default=256)
    release_verify = commands.add_parser("release-verify", help="校验 core 或 full 的下载资产")
    release_verify.add_argument("directory", type=Path)
    release_verify.add_argument("--edition", choices=("core", "full"), default="full")
    release_verify.add_argument("--deep", action="store_true")
    extract = commands.add_parser("release-audio", help="按 entry_id 从音频分片提取一段供试听")
    extract.add_argument("directory", type=Path)
    extract.add_argument("--edition", choices=("core", "full"), required=True)
    extract.add_argument("--entry-id", required=True)
    extract.add_argument("--out", type=Path, required=True)
    assemble = commands.add_parser("release-assemble", help="校验分片并重组完整版 SQLite")
    assemble.add_argument("directory", type=Path)
    assemble.add_argument("--out", type=Path, required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "build":
        inputs = {
            "open-dictionary-v2-distribution-jsonl-gz": args.distribution,
            "open-dictionary-v2-audit-jsonl-gz": args.audit,
            "ecdict-csv": args.ecdict,
            "cmudict-dict": args.cmudict,
            "english-wordnet-2025-core": args.wordnet,
            "wiktextract-function-words": args.function_words,
        }
        result = build(inputs, args.lock, args.out, editorial_path=args.editorial)
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
    elif args.command == "offline-audio":
        from .offline_audio import build_offline_audio
        result = build_offline_audio(args.db, args.out, args.human_dir,
                                     args.workers, args.batch_size, args.max_entries,
                                     args.all_entries)
    elif args.command == "release-build":
        from .release import build_release
        result = build_release(args.source, args.audio_cache, args.out,
                               args.shard_mib * 1024 * 1024)
    elif args.command == "release-verify":
        from .release import verify_release
        result = verify_release(args.directory, args.edition, args.deep)
    elif args.command == "release-audio":
        from .release import extract_audio
        result = extract_audio(args.directory, args.edition, args.entry_id, args.out)
    elif args.command == "release-assemble":
        from .release import assemble_sqlite
        result = assemble_sqlite(args.directory, args.out)
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
    if args.command in ("audio-pack", "audio-pack-locked", "verify-audio"):
        result = {"offline_asset_count": result["offline_asset_count"],
                  "manifest": str((args.out if hasattr(args, "out") else args.directory) / "manifest.json")}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
