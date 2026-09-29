"""核心版学习索引：将词书、专业义项和助记材料与 0.0.1 词卡分层保存。"""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from .builder import canonical, lookup_key

SCHEMA = "leximeet.learning.v1"
BOOKS = (
    ("CET4_T", "四级词汇", "exam"),
    ("CET6_T", "六级词汇", "exam"),
    ("KaoYan_3_T", "考研词汇", "exam"),
    ("IELTS_3_T", "雅思词汇", "exam"),
    ("TOEFL_3_T", "托福词汇", "exam"),
    ("GRE_3_T", "GRE 词汇", "exam"),
    ("itVocabulary", "计算机专业英语", "subject"),
    ("BIOmedical", "生物医学专业英语", "subject"),
)
EXAMS = {
    "zk": "中考", "gk": "高考", "cet4": "四级", "cet6": "六级",
    "ky": "考研", "ielts": "雅思", "toefl": "托福", "gre": "GRE",
}
# 只选来源已经标到义项的领域；这里的组合是词遇的展示分类，不改写源标签。
SUBJECTS = {
    "computing": ("计算机", ("computing",)),
    "biology": ("生物", ("biology", "biochemistry", "microbiology")),
    "medicine": ("医学", ("medicine",)),
    "law": ("法律", ("law",)),
    "finance": ("金融", ("finance",)),
}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_lock(path: Path, expected: str) -> None:
    if not path.is_file() or _hash(path) != expected:
        raise ValueError(f"学习输入缺失或 SHA-256 不符：{path}")


def _create(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE catalogs(
        catalog_id TEXT PRIMARY KEY, title_zh TEXT NOT NULL,
        category TEXT NOT NULL, source TEXT NOT NULL,
        method TEXT NOT NULL, rights_status TEXT NOT NULL
    );
    CREATE TABLE members(
        catalog_id TEXT NOT NULL, entry_id TEXT NOT NULL,
        position INTEGER NOT NULL, sense_ids TEXT NOT NULL,
        match_method TEXT NOT NULL,
        PRIMARY KEY(catalog_id, entry_id),
        FOREIGN KEY(catalog_id) REFERENCES catalogs(catalog_id)
    );
    CREATE INDEX members_by_position ON members(catalog_id, position);
    CREATE INDEX members_by_entry ON members(entry_id);
    CREATE TABLE mnemonics(
        entry_id TEXT NOT NULL, source TEXT NOT NULL,
        kind TEXT NOT NULL, format TEXT NOT NULL,
        content TEXT NOT NULL, review_status TEXT NOT NULL,
        provenance TEXT NOT NULL,
        PRIMARY KEY(entry_id, source)
    );
    CREATE INDEX mnemonics_by_entry ON mnemonics(entry_id);
    """)


def build_learning(core: Path, out: Path, lock_path: Path,
                   qwerty_root: Path | None = None, gpt_file: Path | None = None) -> dict:
    """只读 0.0.1 核心包；输出独立 SQLite，绝不改动既有词条或完整版。"""
    if out.exists():
        raise FileExistsError(f"输出已存在，请指定新路径：{out}")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != "leximeet.learning-sources.v1":
        raise ValueError("学习来源锁版本不支持")
    if qwerty_root:
        for book_id, _, _ in BOOKS:
            _check_lock(qwerty_root / f"{book_id}.json", lock["qwerty"][book_id]["sha256"])
    if gpt_file:
        _check_lock(gpt_file, lock["dictionary_by_gpt4"]["sha256"])
    if not core.is_file():
        raise FileNotFoundError(core)

    entries = []
    exact = {}
    seen_ids = set()
    folded = defaultdict(list)
    with gzip.open(core, "rt", encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            if entry.get("schema_version") != "leximeet.entry.v1":
                raise ValueError("需要 0.0.1 的 leximeet.entry.v1 核心词卡")
            if entry["entry_id"] in seen_ids or entry["headword"] in exact:
                raise ValueError(f"核心词包存在重复词头或词条 ID：{entry['headword']}")
            seen_ids.add(entry["entry_id"])
            entries.append(entry)
            exact[entry["headword"]] = entry["entry_id"]
            folded[lookup_key(entry["headword"])].append(entry["entry_id"])

    def match(word: str) -> tuple[str | None, str]:
        # 先精确匹配；大小写折叠仅允许唯一结果，避免 May/may 一类同形歧义。
        if word in exact:
            return exact[word], "exact"
        candidates = folded.get(lookup_key(word), ())
        if len(candidates) == 1:
            return candidates[0], "unique-casefold"
        return None, "ambiguous" if candidates else "unmatched"

    out.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(out)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        _create(db)
        db.execute("INSERT INTO metadata VALUES (?,?)", ("schema_version", SCHEMA))
        db.execute("INSERT INTO metadata VALUES (?,?)", ("base_entry_schema", "leximeet.entry.v1"))
        db.execute("INSERT INTO metadata VALUES (?,?)", ("base_core_sha256", _hash(core)))
        db.execute("INSERT INTO metadata VALUES (?,?)", ("source_lock_sha256", _hash(lock_path)))
        counters = defaultdict(int)
        audit = {"qwerty_skipped": [], "gpt_skipped": []}
        by_exam = defaultdict(list)
        by_subject = defaultdict(list)

        for entry in entries:
            entry_id = entry["entry_id"]
            hook = entry.get("memory_hook_zh")
            if hook:
                db.execute("INSERT INTO mnemonics VALUES (?,?,?,?,?,?,?)",
                           (entry_id, "open-dictionary:v2.0", "memory-hook", "plain", hook,
                            "source-published", canonical({
                                "source_entry_id": entry.get("source_entry_id"),
                                "source_field": "memory_hook_zh",
                            })))
                counters["curated_hook_entries"] += 1
            for tag in entry["ecdict"]["exam_tags"]:
                if tag["code"] in EXAMS:
                    by_exam[tag["code"]].append(entry)
            for subject, (_, topic_codes) in SUBJECTS.items():
                sense_ids = [sense["sense_id"] for sense in entry["senses"]
                             if any(topic["code"] in topic_codes for topic in sense["topics"])]
                if sense_ids:
                    by_subject[subject].append((entry, sense_ids))

        for code, title in EXAMS.items():
            catalog_id = f"exam:ecdict:{code}"
            db.execute("INSERT INTO catalogs VALUES (?,?,?,?,?,?)",
                       (catalog_id, f"{title} · ECDICT 标签", "exam", "ecdict:bc015ed2",
                        "词条级 tag；按历史词频、词头排序，非原版教材顺序", "source-published"))
            ordered = sorted(by_exam[code], key=lambda item: (
                item["ecdict"]["frequency_ranks"].get("frq")
                or item["ecdict"]["frequency_ranks"].get("bnc") or 10**12,
                item["lookup_key"], item["entry_id"]))
            for pos, entry in enumerate(ordered, 1):
                db.execute("INSERT INTO members VALUES (?,?,?,?,?)",
                           (catalog_id, entry["entry_id"], pos, "[]", "source-tag"))
            counters["ecdict_members"] += len(ordered)

        for subject, (title, topic_codes) in SUBJECTS.items():
            catalog_id = f"subject:topic:{subject}"
            db.execute("INSERT INTO catalogs VALUES (?,?,?,?,?,?)",
                       (catalog_id, f"{title} · 义项领域", "subject", "open-dictionary:v2.0",
                        "义项 topics：" + ", ".join(topic_codes), "source-published"))
            ordered = sorted(by_subject[subject], key=lambda pair: (
                pair[0]["ecdict"]["frequency_ranks"].get("frq")
                or pair[0]["ecdict"]["frequency_ranks"].get("bnc") or 10**12,
                pair[0]["lookup_key"], pair[0]["entry_id"]))
            for pos, (entry, sense_ids) in enumerate(ordered, 1):
                db.execute("INSERT INTO members VALUES (?,?,?,?,?)",
                           (catalog_id, entry["entry_id"], pos, canonical(sense_ids), "sense-topic"))
            counters["subject_members"] += len(ordered)

        if qwerty_root:
            for book_id, title, category in BOOKS:
                catalog_id = f"book:qwerty:{book_id}"
                db.execute("INSERT INTO catalogs VALUES (?,?,?,?,?,?)",
                           (catalog_id, title, category, f"qwerty-learner:{lock['qwerty_commit']}:{book_id}",
                            "保留词表原顺序；只导入词头与归属，不导入翻译和音标",
                            "candidate-upstream-rights-unverified"))
                words = json.loads((qwerty_root / f"{book_id}.json").read_text(encoding="utf-8"))
                seen = set()
                for source_pos, record in enumerate(words, 1):
                    word = record.get("name")
                    if not isinstance(word, str) or not word:
                        counters["qwerty_invalid"] += 1
                        audit["qwerty_skipped"].append({
                            "book_id": book_id, "position": source_pos,
                            "word": word, "reason": "invalid-word",
                        })
                        continue
                    entry_id, method = match(word)
                    if not entry_id:
                        counters[f"qwerty_{method}"] += 1
                        audit["qwerty_skipped"].append({
                            "book_id": book_id, "position": source_pos,
                            "word": word, "reason": method,
                        })
                        continue
                    if entry_id in seen:
                        counters["qwerty_duplicate"] += 1
                        audit["qwerty_skipped"].append({
                            "book_id": book_id, "position": source_pos,
                            "word": word, "reason": "duplicate-entry",
                        })
                        continue
                    seen.add(entry_id)
                    db.execute("INSERT INTO members VALUES (?,?,?,?,?)",
                               (catalog_id, entry_id, source_pos, "[]", method))
                    counters["qwerty_members"] += 1

        if gpt_file:
            candidates = defaultdict(list)
            with gpt_file.open(encoding="utf-8") as stream:
                for source_pos, line in enumerate(stream, 1):
                    record = json.loads(line)
                    word, content = record.get("word"), record.get("content")
                    if isinstance(word, str) and isinstance(content, str) and content.strip():
                        candidates[lookup_key(word)].append((word, content))
                    else:
                        counters["gpt_invalid"] += 1
                        audit["gpt_skipped"].append({
                            "position": source_pos, "word": word, "reason": "invalid-content",
                        })
            for records in candidates.values():
                # 同一个规范词头有多篇文章时不随机选择；留给人工消歧。
                if len(records) != 1:
                    counters["gpt_duplicate_keys"] += 1
                    audit["gpt_skipped"].append({
                        "word": records[0][0], "reason": "duplicate-key",
                        "candidate_count": len(records),
                    })
                    continue
                word, content = records[0]
                entry_id, method = match(word)
                if entry_id:
                    db.execute("INSERT INTO mnemonics VALUES (?,?,?,?,?,?,?)",
                               (entry_id, f"DictionaryByGPT4:{lock['dictionary_by_gpt4_commit']}", "learning-article",
                                "markdown", content, "ai-unreviewed", canonical({
                                    "source_word": word,
                                    "source_commit": lock["dictionary_by_gpt4_commit"],
                                    "source_file_sha256": lock["dictionary_by_gpt4"]["sha256"],
                                })))
                    counters["gpt_matched_entries"] += 1
                else:
                    counters[f"gpt_{method}"] += 1
                    audit["gpt_skipped"].append({"word": word, "reason": method})

        db.commit()
        report = dict(counters)
        report["core_entries"] = len(entries)
        report["catalogs"] = db.execute("SELECT count(*) FROM catalogs").fetchone()[0]
        report["mnemonic_source_rows"] = db.execute("SELECT count(*) FROM mnemonics").fetchone()[0]
        report["entries_with_learning_material"] = db.execute(
            "SELECT count(DISTINCT entry_id) FROM mnemonics").fetchone()[0]
        report["entries_without_learning_material"] = len(entries) - report["entries_with_learning_material"]
        report["schema_version"] = SCHEMA
        report["status"] = "development-candidate"
        out.with_suffix(".report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        out.with_suffix(".audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report
    except BaseException:
        db.close()
        out.unlink(missing_ok=True)
        raise
    finally:
        db.close()


def list_catalogs(db_path: Path) -> list[dict]:
    """词书目录：考试词表和专业分类用同一个查询入口。"""
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
        rows = db.execute("""
            SELECT c.catalog_id,c.title_zh,c.category,c.source,c.method,c.rights_status,
                   count(m.entry_id) FROM catalogs c LEFT JOIN members m USING(catalog_id)
            GROUP BY c.catalog_id ORDER BY c.category,c.catalog_id
        """).fetchall()
    return [dict(zip(("catalog_id", "title_zh", "category", "source", "method",
                      "rights_status", "entry_count"), row)) for row in rows]


def list_members(db_path: Path, catalog_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    """按目录顺序翻页；sense_ids 为空表示词条级归属，不表示任意义项均属该领域。"""
    if not 1 <= limit <= 1000 or offset < 0:
        raise ValueError("limit 必须是 1..1000，offset 不得为负数")
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
        rows = db.execute("""SELECT entry_id,position,sense_ids,match_method FROM members
                             WHERE catalog_id=? ORDER BY position LIMIT ? OFFSET ?""",
                          (catalog_id, limit, offset)).fetchall()
    return [{"entry_id": row[0], "position": row[1], "sense_ids": json.loads(row[2]),
             "match_method": row[3]} for row in rows]


def learning_for_entry(db_path: Path, entry_id: str) -> dict:
    """按词条 ID 查询其词书归属和助记候选，供桌面端/插件端整合词卡。"""
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
        memberships = db.execute("""SELECT m.catalog_id,m.position,m.sense_ids,c.category,c.rights_status
                                    FROM members m JOIN catalogs c USING(catalog_id)
                                    WHERE m.entry_id=? ORDER BY m.catalog_id""", (entry_id,)).fetchall()
        notes = db.execute("""SELECT source,kind,format,content,review_status,provenance FROM mnemonics
                              WHERE entry_id=? ORDER BY source""", (entry_id,)).fetchall()
    return {
        "entry_id": entry_id,
        "catalogs": [{"catalog_id": r[0], "position": r[1], "sense_ids": json.loads(r[2]),
                      "category": r[3], "rights_status": r[4]} for r in memberships],
        "mnemonics": [
            {**dict(zip(("source", "kind", "format", "content", "review_status"), r[:5])),
             "provenance": json.loads(r[5])}
            for r in notes
        ],
    }


def export_missing(core: Path, db_path: Path, out: Path) -> dict:
    """导出尚无助记内容的核心词及最小真实释义，供后续 AI 生成与复核。"""
    if out.exists():
        raise FileExistsError(f"输出已存在，请指定新路径：{out}")
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
        expected = db.execute(
            "SELECT value FROM metadata WHERE key='base_core_sha256'").fetchone()
        if not expected or expected[0] != _hash(core):
            raise ValueError("核心词包与学习索引构建输入不一致")
        covered = {row[0] for row in db.execute("SELECT DISTINCT entry_id FROM mnemonics")}
    count = 0
    with gzip.open(core, "rt", encoding="utf-8") as source, out.open("w", encoding="utf-8") as target:
        for line in source:
            entry = json.loads(line)
            if entry["entry_id"] in covered:
                continue
            # 输入只给真实释义及词性，不带假造词根或“真题”。
            context = {
                "schema_version": "leximeet.mnemonic-task.v1",
                "entry_id": entry["entry_id"],
                "headword": entry["headword"],
                "entry_sha256": hashlib.sha256(canonical(entry).encode("utf-8")).hexdigest(),
                "origin": entry["origin"],
                "headword_summary_zh": entry.get("headword_summary_zh"),
                "senses": [
                    {"sense_id": sense["sense_id"], "pos": sense["pos"],
                     "short_gloss": sense.get("short_gloss"),
                     "learner_explanation_zh": sense.get("learner_explanation_zh")}
                    for sense in entry["senses"]
                ],
                "ecdict_zh_fallback": entry["ecdict"].get("zh_fallback"),
                "ecdict_en_fallback": entry["ecdict"].get("en_fallback"),
            }
            target.write(canonical(context) + "\n")
            count += 1
    return {"schema_version": "leximeet.mnemonic-task.v1", "missing_entries": count,
            "output": str(out), "sha256": _hash(out)}
