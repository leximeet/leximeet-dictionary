"""产物覆盖率、抽样复核清单和只读查询基线。"""

from __future__ import annotations

import csv
import json
import platform
import sqlite3
import statistics
import time
from collections import Counter
from contextlib import closing
from pathlib import Path

from .function_words import SOURCE as FUNCTION_SOURCE


def report(db_path: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    samples: list[dict] = []
    unaligned: list[dict] = []
    seen = set()
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as db:
        # UUIDv5 排序提供固定的分层随机样本；频率样本另外按原 rank 抽取。
        strata = [
            ("function-word-supplement", "headword IN ('the','and','a','an','or','but','if','because','although','nor')", "headword,entry_id", 10),
            ("curated-ranked", "origin='curated' AND rank IS NOT NULL", "rank,entry_id", 40),
            ("curated-unranked", "origin='curated' AND rank IS NULL", "entry_id", 40),
            ("fallback-ranked", "origin='ecdict-fallback' AND rank IS NOT NULL", "rank,entry_id", 40),
            ("fallback-unranked", "origin='ecdict-fallback' AND rank IS NULL", "entry_id", 40),
            ("case-sensitive", "headword GLOB '*[A-Z]*'", "entry_id", 20),
            ("audio-candidate", "entry_id IN (SELECT entry_id FROM audio_candidates)", "entry_id", 20),
        ]
        for name, where, ordering, wanted in strata:
            for entry_id, payload in db.execute(f"SELECT entry_id,payload FROM entries WHERE {where} ORDER BY {ordering} LIMIT ?", (wanted * 5,)):
                if entry_id in seen:
                    continue
                item = json.loads(payload)
                first_senses = sorted(item["senses"], key=lambda sense: sense["display_order"])[:2]
                ipa = [p["text"] for p in item["pronunciations"] if p["notation"] == "IPA"][:3]
                samples.append({"stratum": name, "entry_id": entry_id, "headword": item["headword"],
                                "origin": item["origin"], "source_entry_id": item["source_entry_id"],
                                "sense_count": len(item["senses"]),
                                "english_gloss_preview": " | ".join((s["english_gloss"] or "")[:180] for s in first_senses),
                                "learner_zh_preview": " | ".join((s["learner_explanation_zh"] or "")[:180] for s in first_senses),
                                "zh_fallback": (item["ecdict"]["zh_fallback"] or "")[:180],
                                "editorial_display_zh": (item.get("editorial") or {}).get("display_zh") or "",
                                "ipa_preview": " | ".join(ipa),
                                "labels_topics_preview": " | ".join(
                                    ",".join(label["code"] for label in s["labels"] + s["topics"])[:120]
                                    for s in first_senses),
                                "review_status": "pending", "meaning_match": "", "tag_scope": "",
                                "pronunciation_match": "", "review_notes": ""})
                seen.add(entry_id)
                if sum(x["stratum"] == name for x in samples) >= wanted:
                    break
        with (out / "review-sample.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(samples[0]))
            writer.writeheader()
            writer.writerows(samples)
        for (payload,) in db.execute("SELECT payload FROM entries"):
            item = json.loads(payload)
            counts["entries"] += 1
            counts[item["origin"]] += 1
            if item["senses"]:
                curated_senses = [sense for sense in item["senses"] if sense["source_ref"]["source"] != FUNCTION_SOURCE]
                function_senses = [sense for sense in item["senses"] if sense["source_ref"]["source"] == FUNCTION_SOURCE]
                counts["entries_with_curated_senses"] += bool(curated_senses)
                counts["curated_senses"] += len(curated_senses)
                counts["entries_with_function_senses"] += bool(function_senses)
                counts["function_senses"] += len(function_senses)
                counts["senses_with_english_gloss"] += sum(bool(s["english_gloss"]) for s in item["senses"])
                counts["senses_with_topics"] += sum(bool(s["topics"]) for s in item["senses"])
            if item["audit_status"] == "missing-or-unaligned":
                unaligned.append({"entry_id": item["entry_id"], "headword": item["headword"],
                                  "source_entry_id": item["source_entry_id"], "sense_count": len(item["senses"])})
            if item["ecdict"]["zh_fallback"]:
                counts["entries_with_ecdict_zh"] += 1
            if item.get("editorial"):
                counts["entries_with_editorial"] += 1
            if item["ecdict"]["exam_tags"]:
                counts["entries_with_exam_assertion"] += 1
            if any(p["notation"] == "IPA" for p in item["pronunciations"]):
                counts["entries_with_ipa"] += 1
            if any(p["notation"] == "ARPABET" for p in item["pronunciations"]):
                counts["entries_with_arpabet"] += 1
        counts["wordnet_synsets"] = db.execute("SELECT count(*) FROM wordnet_synsets").fetchone()[0]
        counts["wordnet_lemma_senses"] = db.execute("SELECT count(*) FROM wordnet_lemmas").fetchone()[0]
        counts["audio_candidates_unverified"] = db.execute("SELECT count(*) FROM audio_candidates").fetchone()[0]
        counts["wordnet_dangling_lemma_senses"] = db.execute("""
            SELECT count(*) FROM wordnet_lemmas l LEFT JOIN wordnet_synsets s
            ON s.synset_id=l.synset_id WHERE s.synset_id IS NULL
        """).fetchone()[0]
        timings = []
        for item in samples:
            start = time.perf_counter_ns()
            db.execute("SELECT payload FROM entries WHERE lookup_key=?", (item["headword"].casefold(),)).fetchall()
            timings.append((time.perf_counter_ns() - start) / 1_000_000)
    timings.sort()
    result = {
        "counts": dict(counts),
        "sample_size": len(samples),
        "sample_review_status": "pending-human-review",
        "benchmark": {"queries": len(timings), "p50_ms": round(statistics.median(timings), 3),
                      "p95_ms": round(timings[int(0.95 * (len(timings) - 1))], 3),
                      "environment": platform.platform(),
                      "method": "warm-cache SQLite exact lookup in one Python process"},
        "scope": "Automatic coverage and source checks only; counts do not establish semantic accuracy, licensing, or native-client performance.",
    }
    (out / "audit-unaligned.json").write_text(json.dumps(unaligned, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (out / "quality-report.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result
