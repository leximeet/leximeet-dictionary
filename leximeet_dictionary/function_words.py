"""把独立快照的高频功能词义项作为独立来源补齐，而不跨版猜配原义。"""

from __future__ import annotations

import json
from pathlib import Path

SOURCE = "kaikki:wiktextract:enwiktionary-2026-09-02:extract-2026-09-25"


def load_supplement(path: Path) -> dict[str, dict]:
    """固定的小型 JSONL 在构建前已通过 sources.lock.json 的字节哈希检查。"""
    result = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            word = item.get("word")
            if not word or word in result or not item.get("groups"):
                raise ValueError(f"功能词补充数据重复或缺少词头：{word}")
            result[word] = item
    return result


def append_missing_pos(entry: dict, supplement: dict | None, stable_id) -> int:
    """只增加词条缺失的词性；新快照义项不会伪装成旧策展义项的对齐结果。"""
    if supplement is None:
        return 0
    word = entry["headword"]
    if supplement.get("word") != word:
        raise ValueError(f"功能词补充数据与词头不符：{word}")
    source = supplement["source"]
    present_pos = {sense["pos"] for sense in entry["senses"]}
    count = 0
    for group in supplement["groups"]:
        pos = group["pos"]
        if pos not in ("article", "conj", "particle"):
            raise ValueError(f"功能词补充数据含意外词性：{word}:{pos}")
        if pos in present_pos:
            continue
        for sense in group["senses"]:
            index = sense["sense_index"]
            glosses = sense["glosses"]
            if not glosses or not all(isinstance(gloss, str) and gloss for gloss in glosses):
                raise ValueError(f"功能词补充义项缺少释义：{word}:{pos}:{index}")
            entry["senses"].append({
                "sense_id": stable_id("kaikki-function", word, source["raw_sha256"],
                                      str(group["record_index"]), str(index)),
                "source_ref": {"source": SOURCE, "word": word, "pos": pos,
                               "record_index": group["record_index"], "sense_index": index,
                               "source_url": source["url"], "raw_sha256": source["raw_sha256"],
                               "wiktionary_dump": source["wiktionary_dump"],
                               "kaikki_extraction": source["kaikki_extraction"],
                               "cross_snapshot_alignment": "not-attempted"},
                "pos": pos,
                "etymology_id": f"kaikki-{group.get('etymology_number') or 0}",
                "short_gloss": None,
                "learner_explanation_zh": None,
                "english_gloss": " ".join(glosses),
                "english_gloss_source": SOURCE,
                "examples": [],
                "priority": None,
                "usage_note_zh": None,
                "labels": [{"code": tag, "scope": "sense", "source": SOURCE}
                           for tag in dict.fromkeys(sense.get("tags") or [])],
                "topics": [{"code": topic, "scope": "sense", "source": SOURCE}
                           for topic in dict.fromkeys(sense.get("topics") or [])],
            })
            count += 1
    return count
