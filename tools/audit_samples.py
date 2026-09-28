"""复核样本的源字段一致性与录音文件证据；编辑判断另列，绝不冒充人工听辨。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path


# 以下问题来自逐行阅读 210 条抽样预览；只记录可定位的编辑疑点，不自动覆盖上游原文。
EDITORIAL_CONCERNS = {
    "a": "中文回退混合字母名、冠词和计算机缩写；冠词义项没有逐义中文，默认展示须避免整段贴入。",
    "the": "ECDICT 的 art. 那不足以解释定冠词；新增 article 英文义项尚无逐义中文。",
    "hell chicken": "策展中文解释把 Anzu wyliei 写成“阿祖翼龙”；它是兽脚类恐龙，需修正该中文解释。",
    "regressively": "ECDICT 将副词 regressively 译为形容词“回归的”，词性与释义不符。",
    "scrumhalfs": "ECDICT 将 rugby scrum-half 译为“前锋”，需核对位置术语。",
    "Ltd": "ECDICT 仅给“有限的”，公司名称中的 Ltd. 缺少“有限公司”解释。",
    "ii": "ECDICT 本词条只给图像增强缩写，常见罗马数字 II 未覆盖。",
    "UVC": "ECDICT 只给“万能接头”；常见 ultraviolet C/UV-C 用法缺失，需按大小写与领域拆分。",
    "Nussbaum's braceiets": "词头 braceiets 疑似 bracelets 的拼写错误，应回查 ECDICT 原字段。",
}


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("复核工作表为空")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit_meanings(db_path: Path, sample_path: Path) -> tuple[list[dict], Counter]:
    with sample_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    counts = Counter()
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        for row in rows:
            found = db.execute("SELECT payload FROM entries WHERE entry_id=?", (row["entry_id"],)).fetchone()
            if not found:
                raise ValueError(f"抽样词条不存在：{row['entry_id']}")
            item = json.loads(found[0])
            senses = sorted(item["senses"], key=lambda sense: sense["display_order"])
            first = senses[:2]
            expected = {
                "headword": item["headword"], "origin": item["origin"],
                "sense_count": str(len(senses)),
                "english_gloss_preview": " | ".join((s["english_gloss"] or "")[:180] for s in first),
                "learner_zh_preview": " | ".join((s["learner_explanation_zh"] or "")[:180] for s in first),
                "zh_fallback": (item["ecdict"]["zh_fallback"] or "")[:180],
            }
            problems = [name for name, value in expected.items() if row[name] != value]
            if any(label.get("scope") != "sense" for sense in senses for label in sense["labels"] + sense["topics"]):
                problems.append("sense-label-scope")
            if any(tag.get("scope") != "entry" for tag in item["ecdict"]["exam_tags"]):
                problems.append("exam-tag-scope")
            if sorted(sense["display_order"] for sense in senses) != list(range(len(senses))):
                problems.append("display-order")
            if problems:
                raise ValueError(f"抽样与词包不一致：{item['headword']} {problems}")
            counts["source_fields_consistent"] += 1
            counts[item["origin"]] += 1
            if not senses:
                counts["entry_level_fallback_only"] += 1
            concern = EDITORIAL_CONCERNS.get(item["headword"], "")
            if concern:
                counts["editorial_concern"] += 1
            row["machine_consistency"] = "pass"
            row["editorial_triage"] = "needs-correction-or-source-check" if concern else (
                "entry-level-fallback-only" if not senses else "preview-screened")
            row["editorial_observation"] = concern or (
                "仅有 ECDICT 词条级释义，不能检查逐义项中英对应。" if not senses else
                "已检查抽样预览与词包字段；未逐义项对照独立词典。")
            row["human_semantic_decision"] = "pending"
    counts["rows"] = len(rows)
    return rows, counts


def audit_audio(audio_dir: Path, sample_path: Path, asr_path: Path | None = None) -> tuple[list[dict], Counter]:
    with sample_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    counts = Counter()
    transcripts = {}
    if asr_path:
        evidence = json.loads(asr_path.read_text(encoding="utf-8"))
        transcripts = {item["headword"]: item["asr_transcript"] for item in evidence["records"]}
        if len(transcripts) != len(rows):
            raise ValueError("ASR 记录数与音频样本不一致")
    for row in rows:
        audio = audio_dir / row["path"]
        data = audio.read_bytes()
        filename = row["title"].removeprefix("File:")
        normalized_name = filename.casefold().replace("_", "-")
        word = row["headword"].casefold().replace(" ", "-")
        name_matches = normalized_name.startswith((f"en-us-{word}.", f"en-uk-{word}."))
        checks = {
            "file_exists": audio.is_file(), "sha256_matches": hashlib.sha256(data).hexdigest() == row["sha256"],
            "ogg_container": data.startswith(b"OggS"), "filename_matches_headword": name_matches,
            "attribution_fields_present": all(row.get(key) for key in ("artist", "license", "license_url", "source_page")),
            "source_page_matches_title": row["source_page"].endswith(filename),
        }
        if not all(checks.values()):
            raise ValueError(f"音频抽样不一致：{row['headword']} {checks}")
        counts["file_and_metadata_consistent"] += 1
        row.update({"machine_consistency": "pass", "content_listening": "pending",
                    "asr_transcript": transcripts.get(row["headword"], ""), "audio_observation":
                    "文件哈希、OGG 容器、文件名、作者/许可/文件页元数据通过；尚未据此认定读音内容正确。"})
    counts["rows"] = len(rows)
    return rows, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--asr-json", type=Path, help="可选的离线 ASR 原始转写；短词误识别不能代替听辨")
    args = parser.parse_args()
    meaning_rows, meaning_counts = audit_meanings(args.db, args.qa / "review-sample.csv")
    audio_rows, audio_counts = audit_audio(args.audio, args.qa / "audio-review-sample.csv", args.asr_json)
    write_csv(args.qa / "agent-meaning-review.csv", meaning_rows)
    write_csv(args.qa / "agent-audio-review.csv", audio_rows)
    result = {"meaning": dict(meaning_counts), "audio": dict(audio_counts),
              "scope": "结构与原字段一致性及抽样预览阅读；不等于独立词义或真人听辨通过"}
    (args.qa / "agent-review-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
