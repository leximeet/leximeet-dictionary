"""从已下载的 Kaikki 逐词原始记录生成固定的高频功能词补充数据。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

# 只补 open-dictionary v2.0 的策展规则排除的常见词性；不推断跨快照义项等同。
ARTICLE_WORDS = ("a", "an", "the")
CONJUNCTION_WORDS = (
    "after", "although", "and", "as", "because", "before", "both", "but",
    "either", "for", "if", "lest", "neither", "nor", "once", "or", "provided",
    "since", "so", "than", "that", "though", "unless", "until", "when",
    "whenever", "where", "wherever", "whether", "while", "yet",
)
WORDS = {**{word: "article" for word in ARTICLE_WORDS},
         **{word: "conj" for word in CONJUNCTION_WORDS}}


def prepare(raw_dir: Path, out: Path) -> dict[str, int]:
    """只复制定义和义项标签，避免把原始记录中的历史引文带进公开包。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    sense_count = 0
    with out.open("w", encoding="utf-8", newline="\n") as target:
        for word, wanted_pos in sorted(WORDS.items()):
            data = (raw_dir / f"{word}.jsonl").read_bytes()
            groups = []
            for record_index, line in enumerate(data.splitlines()):
                record = json.loads(line)
                if (record.get("word"), record.get("lang_code"), record.get("pos")) != (word, "en", wanted_pos):
                    continue
                senses = []
                for sense_index, sense in enumerate(record.get("senses", [])):
                    glosses = sense.get("glosses") or []
                    if not glosses or not all(isinstance(gloss, str) and gloss for gloss in glosses):
                        raise ValueError(f"{word} 缺少可用英文释义")
                    senses.append({"sense_index": sense_index, "glosses": glosses,
                                   "tags": sense.get("tags") or [], "topics": sense.get("topics") or []})
                if senses:
                    groups.append({"pos": wanted_pos, "record_index": record_index,
                                   "etymology_number": record.get("etymology_number"), "senses": senses})
                    sense_count += len(senses)
            if not groups:
                raise ValueError(f"{word} 没有 {wanted_pos} 记录")
            url = f"https://kaikki.org/dictionary/English/meaning/{word[0]}/{word[:2]}/{word}.jsonl"
            item = {"word": word, "source": {"url": url, "raw_sha256": hashlib.sha256(data).hexdigest(),
                    "raw_bytes": len(data), "wiktionary_dump": "2026-09-02",
                    "kaikki_extraction": "2026-09-25"}, "groups": groups}
            target.write(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return {"words": len(WORDS), "senses": sense_count}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.raw_dir, args.out), ensure_ascii=False))
