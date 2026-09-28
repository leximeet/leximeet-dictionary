"""词遇自有的少量审校修订；上游原字段与每次替换前的值均可追溯。"""

from __future__ import annotations

import json
from pathlib import Path


SOURCE = "leximeet:editorial:0.0.1"
ENTRY_FIELDS = {"headword_summary_zh"}
SENSE_FIELDS = {"learner_explanation_zh"}


def load_corrections(path: Path) -> dict[str, dict]:
    """按精确词头索引修订，并拒绝重复、无证据或不支持的目标字段。"""
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "leximeet.editorial.v1":
        raise ValueError("词遇审校文件 schema 不兼容")
    result: dict[str, dict] = {}
    ids: set[str] = set()
    for item in document.get("corrections", []):
        word, identifier = item.get("headword"), item.get("id")
        if not isinstance(word, str) or not word or word in result or not identifier or identifier in ids:
            raise ValueError(f"词遇审校词头或 ID 重复/缺失：{word}")
        if not isinstance(item.get("entry_id"), str) or not item["entry_id"]:
            raise ValueError(f"词遇审校缺少词条 ID：{word}")
        if not item.get("evidence") or not all(isinstance(url, str) and url.startswith("https://")
                                                for url in item["evidence"]):
            raise ValueError(f"词遇审校缺少可核对的 HTTPS 证据：{word}")
        if not item.get("display_zh") and not item.get("revisions"):
            raise ValueError(f"词遇审校无实际修订：{word}")
        for revision in item.get("revisions", []):
            target, field = revision.get("target"), revision.get("field")
            allowed = ENTRY_FIELDS if target == "entry" else SENSE_FIELDS if target == "sense" else set()
            if field not in allowed or "expected" not in revision or not isinstance(revision.get("value"), str):
                raise ValueError(f"词遇审校字段不受支持：{word}: {target}.{field}")
            if target == "sense" and not revision.get("sense_id"):
                raise ValueError(f"词遇审校缺少义项 ID：{word}")
        result[word] = item
        ids.add(identifier)
    if not result:
        raise ValueError("词遇审校文件为空")
    return result


def apply_correction(entry: dict, correction: dict) -> int:
    """只在目标 ID 与旧值完全匹配时修订；源内容变化时要求重新审校。"""
    if (entry["entry_id"], entry["headword"]) != (correction["entry_id"], correction["headword"]):
        raise ValueError(f"词遇审校词条身份变化：{correction['headword']}")
    revisions = []
    for change in correction.get("revisions", []):
        target = entry
        if change["target"] == "sense":
            matched = [sense for sense in entry["senses"] if sense["sense_id"] == change["sense_id"]]
            if len(matched) != 1:
                raise ValueError(f"词遇审校义项身份变化：{entry['headword']}")
            target = matched[0]
        field = change["field"]
        original = target.get(field)
        if original != change["expected"]:
            raise ValueError(f"词遇审校原字段变化：{entry['headword']}: {field}")
        target[field] = change["value"]
        revisions.append({"target": change["target"], "field": field,
                          "sense_id": change.get("sense_id"), "original": original,
                          "replacement": change["value"]})
    # source_ref 始终指原义项；中文审校与来源证据显式单列，不冒称源库原文。
    entry["editorial"] = {"source": SOURCE, "correction_id": correction["id"],
                          "display_zh": correction.get("display_zh"),
                          "evidence": correction["evidence"], "revisions": revisions}
    return len(revisions)
