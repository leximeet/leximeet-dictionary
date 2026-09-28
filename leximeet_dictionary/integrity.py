"""对发布词包做比文件哈希更深入的结构与跨格式一致性检查。"""

from __future__ import annotations

import gzip
import json
import sqlite3
from contextlib import closing
from itertools import zip_longest
from pathlib import Path

from .builder import SCHEMA, canonical, lookup_key, verify_package
from .editorial import SOURCE as EDITORIAL_SOURCE, load_corrections
from .function_words import SOURCE as FUNCTION_SOURCE


def verify_content(root: Path) -> dict:
    """逐行比对 JSONL 与 SQLite，并确认核心分片和引用关系；不修改词包。"""
    manifest = verify_package(root)
    editorial_file = root / "editorial" / "corrections.json"
    corrections = load_corrections(editorial_file) if editorial_file.exists() else {}
    counts = {"entries": 0, "curated": 0, "fallback": 0, "senses": 0, "core": 0,
              "function_word_entries": 0, "function_word_senses": 0,
              "audio_candidates": 0, "editorial_entries": 0, "editorial_revisions": 0}
    sense_ids: set[str] = set()
    with closing(sqlite3.connect(f"file:{root / 'dictionary.sqlite'}?mode=ro", uri=True)) as db:
        rows = db.execute("SELECT payload FROM entries ORDER BY lookup_key,headword,entry_id")
        with gzip.open(root / "entries.jsonl.gz", "rt", encoding="utf-8") as source:
            for source_line, db_row in zip_longest(source, rows):
                if source_line is None or db_row is None or source_line.rstrip("\n") != db_row[0]:
                    raise ValueError("完整 JSONL 与 SQLite 词条不一致")
                entry = json.loads(source_line)
                if (entry.get("schema_version") != SCHEMA or not entry.get("entry_id") or
                        not entry.get("headword") or entry.get("lookup_key") != lookup_key(entry["headword"])):
                    raise ValueError(f"词条基础字段无效：{entry.get('entry_id')}")
                correction = corrections.get(entry["headword"])
                editorial = entry.get("editorial")
                if correction:
                    if (not editorial or editorial.get("source") != EDITORIAL_SOURCE or
                            editorial.get("correction_id") != correction["id"] or
                            editorial.get("display_zh") != correction.get("display_zh") or
                            editorial.get("evidence") != correction["evidence"] or
                            entry["entry_id"] != correction["entry_id"]):
                        raise ValueError(f"词遇审校记录与词条不一致：{entry['headword']}")
                    revisions = editorial.get("revisions", [])
                    if len(revisions) != len(correction.get("revisions", [])):
                        raise ValueError(f"词遇审校修订数不一致：{entry['headword']}")
                    for actual, expected_revision in zip(revisions, correction.get("revisions", [])):
                        target = entry if expected_revision["target"] == "entry" else next(
                            (sense for sense in entry["senses"] if sense["sense_id"] == expected_revision["sense_id"]), None)
                        if (target is None or actual.get("target") != expected_revision["target"] or
                                actual.get("field") != expected_revision["field"] or
                                actual.get("sense_id") != expected_revision.get("sense_id") or
                                actual.get("original") != expected_revision["expected"] or
                                actual.get("replacement") != expected_revision["value"] or
                                target.get(expected_revision["field"]) != expected_revision["value"]):
                            raise ValueError(f"词遇审校字段与证据不一致：{entry['headword']}")
                    counts["editorial_entries"] += 1
                    counts["editorial_revisions"] += len(revisions)
                elif editorial:
                    raise ValueError(f"词条含未登记的审校信息：{entry['headword']}")
                origin = entry.get("origin")
                if origin == "curated":
                    counts["curated"] += 1
                elif origin == "ecdict-fallback":
                    counts["fallback"] += 1
                    if any(sense["source_ref"].get("source") != FUNCTION_SOURCE for sense in entry["senses"]):
                        raise ValueError("ECDICT 回退词条不能伪造已对齐义项")
                else:
                    raise ValueError(f"未知词条来源：{origin}")
                senses = entry["senses"]
                counts["function_word_entries"] += any(sense["source_ref"].get("source") == FUNCTION_SOURCE for sense in senses)
                orders = [sense.get("display_order") for sense in senses]
                if not all(isinstance(order, int) for order in orders) or sorted(orders) != list(range(len(senses))):
                    raise ValueError(f"义项展示顺序无效：{entry['headword']}")
                for sense in senses:
                    identifier = sense.get("sense_id")
                    if not identifier or identifier in sense_ids:
                        raise ValueError(f"重复或缺少义项 ID：{entry['headword']}")
                    sense_ids.add(identifier)
                    source_ref = sense["source_ref"]
                    if source_ref.get("source") == FUNCTION_SOURCE:
                        if (source_ref.get("word") != entry["headword"] or
                                source_ref.get("cross_snapshot_alignment") != "not-attempted" or
                                not source_ref.get("raw_sha256") or not source_ref.get("source_url")):
                            raise ValueError(f"功能词来源引用无效：{entry['headword']}")
                        counts["function_word_senses"] += 1
                    elif source_ref.get("entry_id") != entry["source_entry_id"]:
                        raise ValueError(f"义项来源引用无效：{entry['headword']}")
                    if sense.get("english_gloss") and not sense.get("english_gloss_source"):
                        raise ValueError(f"义项来源引用无效：{entry['headword']}")
                counts["entries"] += 1
                counts["senses"] += len(senses)
        core_rows = db.execute("SELECT payload FROM entries WHERE rank IS NOT NULL "
                               "ORDER BY rank,headword,entry_id LIMIT ?", (manifest["core_limit"],))
        with gzip.open(root / "core.jsonl.gz", "rt", encoding="utf-8") as source:
            for source_line, db_row in zip_longest(source, core_rows):
                if source_line is None or db_row is None or source_line.rstrip("\n") != db_row[0]:
                    raise ValueError("核心 JSONL 与 SQLite 高频选择不一致")
                counts["core"] += 1
        candidate_rows = db.execute("SELECT * FROM audio_candidates ORDER BY headword,pos,url")
        names = ("entry_id", "headword", "pos", "url", "format", "status", "source")
        with gzip.open(root / "audio-candidates.jsonl.gz", "rt", encoding="utf-8") as source:
            for source_line, db_row in zip_longest(source, candidate_rows):
                if source_line is None or db_row is None or source_line.rstrip("\n") != canonical(dict(zip(names, db_row))):
                    raise ValueError("音频候选 JSONL 与 SQLite 不一致")
                counts["audio_candidates"] += 1
        if db.execute("SELECT count(*) FROM forms f LEFT JOIN entries e ON e.entry_id=f.entry_id "
                      "WHERE e.entry_id IS NULL").fetchone()[0]:
            raise ValueError("词形索引引用了不存在的词条")
        if db.execute("SELECT count(*) FROM wordnet_lemmas l LEFT JOIN wordnet_synsets s "
                      "ON s.synset_id=l.synset_id WHERE s.synset_id IS NULL").fetchone()[0]:
            raise ValueError("WordNet lemma 引用了不存在的 synset")
    expected = manifest["counts"]
    if (counts["entries"], counts["curated"], counts["fallback"], counts["senses"],
            counts["audio_candidates"], counts["function_word_entries"], counts["function_word_senses"]) != (
        expected["total_entries"], expected["curated_entries"], expected["ecdict_only_entries"],
        expected["senses"], expected["audio_candidates"], expected["function_word_entries"],
        expected["function_word_senses"]
    ):
        raise ValueError("深度校验计数与清单不符")
    if (counts["editorial_entries"], counts["editorial_revisions"]) != (
        expected.get("editorial_entries", 0), expected.get("editorial_revisions", 0)) or counts["editorial_entries"] != len(corrections):
        raise ValueError("词遇审校修订数量与清单不符")
    return counts
