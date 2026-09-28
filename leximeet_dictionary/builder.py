"""从固定来源流式生成词遇 0.0.1 公共词典。"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import shutil
import subprocess
import sqlite3
import unicodedata
import uuid
import zipfile
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

from .editorial import apply_correction, load_corrections
from .function_words import SOURCE as FUNCTION_SOURCE, append_missing_pos, load_supplement

SCHEMA = "leximeet.entry.v1"
VERSION = "0.0.1"
NAMESPACE = uuid.UUID("b5589b13-658b-420d-96b0-3938d50fefc1")
OPEN_SOURCE = "open-dictionary:v2.0"
AUDIT_SOURCE = "open-dictionary:v2.0:audit:wiktionary:2025-10-23"
ECDICT_SOURCE = "ecdict:bc015ed2"
CMU_SOURCE = "cmudict:74790861"


def canonical(value: object) -> str:
    """JSON 字节固定，避免输入字典键顺序影响产物哈希。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def lookup_key(word: str) -> str:
    # NFC 保留拼写形态；casefold 仅用于查找，不用于合并 May/may。
    return unicodedata.normalize("NFC", word).casefold()


def stable_id(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "\x1f".join(parts)))


def file_hash(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def generator_state(repository_root: Path) -> dict:
    """记录最近一次改变构建内容的提交，文档合并不应改变词包字节。"""
    content_paths = ["leximeet_dictionary", "sources", "editorial", "scripts", "DATA-LICENSE.md",
                     "notices", "sources.lock.json", "audio.lock.json"]
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(repository_root), "rev-list", "-1", "HEAD", "--", *content_paths],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        changes = subprocess.check_output(
            ["git", "-C", str(repository_root), "status", "--porcelain", "--untracked-files=all",
             "--", *content_paths],
            text=True, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": True}
    return {"commit": commit or None, "dirty": bool(changes.strip()) or not commit}


def verify_inputs(paths: dict[str, Path], lock_path: Path) -> dict[str, dict]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    expected = {item["id"]: item for item in lock["artifacts"]}
    result = {}
    for source_id, path in paths.items():
        item = expected[source_id]
        if not path.is_file() or not item.get("sha256"):
            raise ValueError(f"输入未锁定或不存在：{source_id}: {path}")
        size, sha256 = file_hash(path)
        if sha256 != item["sha256"] or (item.get("bytes") and size != item["bytes"]):
            raise ValueError(f"输入 SHA-256/大小不符：{source_id}: {path}")
        result[source_id] = {"bytes": size, "sha256": sha256, "url": item.get("url"), "license": item.get("license")}
    return result


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=DELETE")
    db.execute("PRAGMA synchronous=FULL")
    return db


def stage_ecdict(db: sqlite3.Connection, path: Path) -> int:
    db.execute("CREATE TABLE ecdict(word TEXT PRIMARY KEY, payload TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0)")
    count = 0
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            # 历史字段原样保留，不把旧音标或 rank 自动转成 IPA/频率。
            item = {key: row[key] for key in ("translation", "definition", "phonetic", "tag", "bnc", "frq", "collins", "oxford", "exchange")}
            db.execute("INSERT INTO ecdict(word,payload) VALUES (?,?)", (row["word"], canonical(item)))
            count += 1
            if count % 10000 == 0:
                db.commit()
    db.commit()
    return count


def stage_audit(db: sqlite3.Connection, path: Path) -> int:
    db.execute("CREATE TABLE audit(entry_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    count = 0
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            source = item["entries"]
            # 引文可能有第三方版权；首版只选短原义、义项标签、IPA 与音频线索。
            groups = []
            for group in source.get("pos_groups", []):
                groups.append({
                    "pos": group.get("pos"),
                    "etymology_id": group.get("etymology_id"),
                    "senses": [{key: sense.get(key) for key in ("sense_id", "gloss", "raw_gloss", "tags", "topics", "qualifier")} for sense in group.get("senses", [])],
                    "pronunciations": [{key: pron.get(key) for key in ("ipa", "tags", "audio_url", "audio_format")} for pron in group.get("pronunciations", []) if pron.get("ipa") or pron.get("audio_url")],
                })
            audit = {"groups": groups, "raw_record_refs": source.get("source_summary", {}).get("raw_record_refs", [])}
            db.execute("INSERT INTO audit VALUES (?,?)", (item["entry_id"], canonical(audit)))
            count += 1
            if count % 5000 == 0:
                db.commit()
    db.commit()
    return count


def load_cmu(path: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line or line.startswith(";;; ") or line.startswith("#"):
                continue
            parts = line.strip().split()
            if len(parts) > 1:
                word = parts[0].split("(", 1)[0]
                phonemes = " ".join(parts[1:])
                if phonemes not in result[word]:
                    result[word].append(phonemes)
    return result


def ecdict_fields(payload: str | None) -> dict:
    if payload is None:
        return {"zh_fallback": None, "en_fallback": None, "exam_tags": [], "frequency_ranks": {}, "legacy_phonetic": None, "source_fields": {}}
    data = json.loads(payload)
    return {
        "zh_fallback": data["translation"] or None,
        "en_fallback": data["definition"] or None,
        "exam_tags": [{"code": tag, "scope": "entry", "status": "source-asserted", "source": ECDICT_SOURCE} for tag in data["tag"].split() if tag],
        "frequency_ranks": {key: int(data[key]) for key in ("bnc", "frq") if data[key].isdigit() and int(data[key]) > 0},
        "legacy_phonetic": data["phonetic"] or None,
        "source_fields": {key: data[key] for key in ("collins", "oxford", "exchange") if data[key]},
    }


def region_from_tags(tags: list[str]) -> str | None:
    if "US" in tags or "General-American" in tags:
        return "en-US"
    if "UK" in tags or "Received-Pronunciation" in tags:
        return "en-GB"
    return None


def make_entry(curated: dict | None, audit: dict | None, word: str, ecdict_payload: str | None,
               cmu: dict[str, list[str]], function_supplement: dict | None = None) -> tuple[dict, list[dict]]:
    source_entry_id = curated["entry_id"] if curated else None
    entry_id = stable_id("open", source_entry_id) if curated else stable_id("ecdict", word)
    ecdict = ecdict_fields(ecdict_payload)
    senses = []
    forms = []
    pronunciations = []
    audio_candidates = []
    seen_pron = set()
    seen_audio = set()
    audit_groups = audit.get("groups", []) if audit else []
    groups = curated.get("pos_groups", []) if curated else []
    audit_aligned = audit is not None and len(groups) == len(audit_groups) and all(
        (a.get("pos"), a.get("etymology_id"), len(a.get("meanings", []))) ==
        (b.get("pos"), b.get("etymology_id"), len(b.get("senses", [])))
        for a, b in zip(groups, audit_groups)
    )
    for gi, group in enumerate(groups):
        pos = group.get("pos")
        etymology = group.get("etymology_id")
        raw = audit_groups[gi] if audit_aligned else {}
        for form in group.get("forms", []):
            if form.get("text"):
                forms.append({"text": form["text"], "tags": form.get("tags", []), "source": OPEN_SOURCE})
        for si, sense in enumerate(group.get("meanings", [])):
            origin = raw.get("senses", [])[si] if raw else {}
            senses.append({
                "sense_id": stable_id("sense", source_entry_id, str(gi), str(si)),
                "source_ref": {"source": OPEN_SOURCE, "entry_id": source_entry_id, "pos": pos, "etymology_id": etymology, "sense_id": sense.get("sense_id"), "group_index": gi},
                "pos": pos,
                "etymology_id": etymology,
                "short_gloss": sense.get("short_gloss"),
                "learner_explanation_zh": sense.get("learner_explanation"),
                "english_gloss": origin.get("gloss"),
                "english_gloss_source": AUDIT_SOURCE if origin.get("gloss") else None,
                "examples": [{"text": ex.get("text"), "translation": ex.get("translation"), "source": OPEN_SOURCE} for ex in sense.get("examples", [])],
                "priority": sense.get("priority"),
                "usage_note_zh": sense.get("usage_note"),
                "labels": [{"code": label, "scope": "sense", "source": OPEN_SOURCE} for label in dict.fromkeys((sense.get("labels") or []) + (origin.get("tags") or []))],
                "topics": [{"code": topic, "scope": "sense", "source": OPEN_SOURCE} for topic in dict.fromkeys((sense.get("topics") or []) + (origin.get("topics") or []))],
            })
        for origin_name, prons in ((OPEN_SOURCE, group.get("pronunciations", [])), (AUDIT_SOURCE, raw.get("pronunciations", []))):
            for pron in prons:
                tags = pron.get("tags") or []
                region = region_from_tags(tags)
                ipa = pron.get("ipa")
                if ipa:
                    key = (pos, etymology, ipa, region)
                    if key not in seen_pron:
                        pronunciations.append({"notation": "IPA", "text": ipa, "region": region, "pos": pos, "etymology_id": etymology, "tags": tags, "source": origin_name})
                        seen_pron.add(key)
                url = pron.get("audio_url")
                if url and url.startswith("https://upload.wikimedia.org/wikipedia/commons/"):
                    key = (url, pos)
                    if key not in seen_audio:
                        audio_candidates.append({"entry_id": entry_id, "headword": word, "pos": pos, "url": url, "format": pron.get("audio_format"), "status": "license-unverified", "source": AUDIT_SOURCE})
                        seen_audio.add(key)
    for phonemes in cmu.get(word.casefold(), []):
        pronunciations.append({"notation": "ARPABET", "text": phonemes, "region": "en-US", "pos": None, "etymology_id": None, "tags": [], "source": CMU_SOURCE})
    result = {
        "schema_version": SCHEMA,
        "entry_id": entry_id,
        "headword": word,
        "lookup_key": lookup_key(word),
        "headword_language": "en",
        "definition_language": "zh-Hans",
        "origin": "curated" if curated else "ecdict-fallback",
        "source_entry_id": source_entry_id,
        "headword_summary_zh": curated.get("headword_summary") if curated else None,
        "memory_hook_zh": curated.get("memory_hook") if curated else None,
        "study_notes_zh": curated.get("study_notes", []) if curated else [],
        "forms": forms,
        "pronunciations": pronunciations,
        "senses": senses,
        "ecdict": ecdict,
        "audit_status": "aligned" if curated and audit_aligned else ("missing-or-unaligned" if curated else "not-applicable"),
        "audio_ids": [],
    }
    append_missing_pos(result, function_supplement, stable_id)
    # 先露出功能词前两个源义项；其余仍可展开。此排序不声称它们来自主词源的 core 评级。
    priority_order = {"core": 0, "common": 1, "rare": 3}
    display_indices = sorted(range(len(result["senses"])), key=lambda index: (
        -1 if result["senses"][index]["source_ref"]["source"] == FUNCTION_SOURCE
              and result["senses"][index]["source_ref"]["sense_index"] < 2
        else 2 if result["senses"][index]["source_ref"]["source"] == FUNCTION_SOURCE
        else priority_order.get(result["senses"][index]["priority"], 4),
        result["senses"][index]["pos"] == "name", index
    ))
    for display_order, index in enumerate(display_indices):
        result["senses"][index]["display_order"] = display_order
    return result, audio_candidates


def init_dictionary(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE entries(entry_id TEXT PRIMARY KEY, headword TEXT NOT NULL, lookup_key TEXT NOT NULL,
        origin TEXT NOT NULL, rank INTEGER, payload TEXT NOT NULL);
    CREATE INDEX entries_lookup ON entries(lookup_key, headword);
    CREATE TABLE forms(form_key TEXT NOT NULL, form_text TEXT NOT NULL, entry_id TEXT NOT NULL,
        PRIMARY KEY(form_key, form_text, entry_id));
    CREATE TABLE audio_candidates(entry_id TEXT NOT NULL, headword TEXT NOT NULL, pos TEXT,
        url TEXT NOT NULL, format TEXT, status TEXT NOT NULL, source TEXT NOT NULL,
        PRIMARY KEY(entry_id, pos, url));
    CREATE INDEX audio_candidates_word ON audio_candidates(headword);
    CREATE TABLE wordnet_synsets(synset_id TEXT PRIMARY KEY, pos TEXT NOT NULL,
        definition TEXT NOT NULL, relations TEXT NOT NULL);
    CREATE TABLE wordnet_lemmas(lemma_key TEXT NOT NULL, lemma TEXT NOT NULL,
        pos TEXT NOT NULL, synset_id TEXT NOT NULL, sense_key TEXT NOT NULL,
        PRIMARY KEY(lemma,pos,synset_id,sense_key));
    CREATE INDEX wordnet_lemmas_lookup ON wordnet_lemmas(lemma_key);
    """)
    db.execute("INSERT INTO metadata VALUES (?,?)", ("schema_version", SCHEMA))
    db.execute("INSERT INTO metadata VALUES (?,?)", ("dictionary_version", VERSION))


def add_entry(db: sqlite3.Connection, entry: dict, audio: list[dict]) -> None:
    ranks = entry["ecdict"]["frequency_ranks"]
    rank = ranks.get("frq") or ranks.get("bnc")
    db.execute("INSERT INTO entries VALUES (?,?,?,?,?,?)", (entry["entry_id"], entry["headword"], entry["lookup_key"], entry["origin"], rank, canonical(entry)))
    for form in entry["forms"]:
        db.execute("INSERT OR IGNORE INTO forms VALUES (?,?,?)", (lookup_key(form["text"]), form["text"], entry["entry_id"]))
    for item in audio:
        db.execute("INSERT OR IGNORE INTO audio_candidates VALUES (?,?,?,?,?,?,?)", (item["entry_id"], item["headword"], item["pos"], item["url"], item["format"], item["status"], item["source"]))


def write_gzip_lines(path: Path, lines) -> tuple[int, str]:
    # gzip mtime=0 且固定文件名字段，保证相同输入的压缩字节可重复。
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as stream:
            for line in lines:
                stream.write(line.encode("utf-8"))
                stream.write(b"\n")
    return file_hash(path)


def add_wordnet(db: sqlite3.Connection, archive_path: Path) -> tuple[int, int]:
    """概念网络单独入表，不把同词头 synset 冒充已对齐义项。"""
    synsets = 0
    lemmas = 0
    with zipfile.ZipFile(archive_path) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith("entries-") and name.endswith(".json"):
                entries = json.loads(archive.read(name))
                for lemma, parts in entries.items():
                    for pos, entry in parts.items():
                        for sense in entry.get("sense", []):
                            db.execute("INSERT OR IGNORE INTO wordnet_lemmas VALUES (?,?,?,?,?)", (
                                lookup_key(lemma), lemma, pos, sense["synset"], sense["id"]))
                            lemmas += 1
            elif name.endswith(".json") and name not in ("frames.json",):
                concepts = json.loads(archive.read(name))
                for synset_id, value in concepts.items():
                    # 仅提取有向关系 ID；完整原始概念数据仍由固定 ZIP 提供。
                    relations = {key: targets for key, targets in value.items()
                                 if key not in ("definition", "members", "partOfSpeech", "ili", "examples")
                                 and isinstance(targets, list) and all(isinstance(item, str) for item in targets)}
                    db.execute("INSERT OR IGNORE INTO wordnet_synsets VALUES (?,?,?,?)", (
                        synset_id, value.get("partOfSpeech", ""), canonical(value.get("definition", [])), canonical(relations)))
                    synsets += 1
            db.commit()
    return synsets, lemmas


def build(paths: dict[str, Path], lock_path: Path, out: Path, core_size: int = 5000,
          editorial_path: Path | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    inputs = verify_inputs(paths, lock_path)
    corrections = load_corrections(editorial_path) if editorial_path else {}
    if editorial_path:
        size, sha256 = file_hash(editorial_path)
        inputs["leximeet-editorial-0.0.1"] = {"bytes": size, "sha256": sha256,
                                                "url": None, "license": "CC BY-SA 4.0"}
    applied_corrections: set[str] = set()
    function_words = load_supplement(paths["wiktextract-function-words"])
    scratch_path = out / "scratch.sqlite"
    db_path = out / "dictionary.sqlite"
    if scratch_path.exists() or db_path.exists():
        raise FileExistsError("输出目录已有数据库；请选择新的空目录，避免覆盖先前构建")
    scratch = connect(scratch_path)
    dictionary = connect(db_path)
    counts = Counter()
    try:
        counts["ecdict_rows"] = stage_ecdict(scratch, paths["ecdict-csv"])
        counts["audit_rows"] = stage_audit(scratch, paths["open-dictionary-v2-audit-jsonl-gz"])
        cmu = load_cmu(paths["cmudict-dict"])
        init_dictionary(dictionary)
        with gzip.open(paths["open-dictionary-v2-distribution-jsonl-gz"], "rt", encoding="utf-8") as stream:
            for line in stream:
                curated = json.loads(line)
                word = curated["headword"]
                source_id = curated["entry_id"]
                audit_row = scratch.execute("SELECT payload FROM audit WHERE entry_id=?", (source_id,)).fetchone()
                ecdict_row = scratch.execute("SELECT payload FROM ecdict WHERE word=?", (word,)).fetchone()
                if ecdict_row:
                    scratch.execute("UPDATE ecdict SET used=1 WHERE word=?", (word,))
                    counts["curated_with_ecdict"] += 1
                entry, audio = make_entry(curated, json.loads(audit_row[0]) if audit_row else None,
                                          word, ecdict_row[0] if ecdict_row else None, cmu,
                                          function_words.get(word))
                if word in corrections:
                    counts["editorial_revisions"] += apply_correction(entry, corrections[word])
                    counts["editorial_entries"] += 1
                    applied_corrections.add(word)
                add_entry(dictionary, entry, audio)
                counts["curated_entries"] += 1
                added = sum(sense["source_ref"]["source"] == FUNCTION_SOURCE for sense in entry["senses"])
                counts["function_word_senses"] += added
                counts["function_word_entries"] += bool(added)
                if entry["audit_status"] == "aligned":
                    counts["audit_aligned"] += 1
                if counts["curated_entries"] % 5000 == 0:
                    dictionary.commit()
                    scratch.commit()
        scratch.commit()
        for word, payload in scratch.execute("SELECT word,payload FROM ecdict WHERE used=0 ORDER BY word"):
            entry, _ = make_entry(None, None, word, payload, cmu, function_words.get(word))
            if word in corrections:
                counts["editorial_revisions"] += apply_correction(entry, corrections[word])
                counts["editorial_entries"] += 1
                applied_corrections.add(word)
            add_entry(dictionary, entry, [])
            counts["ecdict_only_entries"] += 1
            added = sum(sense["source_ref"]["source"] == FUNCTION_SOURCE for sense in entry["senses"])
            counts["function_word_senses"] += added
            counts["function_word_entries"] += bool(added)
            if counts["ecdict_only_entries"] % 10000 == 0:
                dictionary.commit()
        dictionary.commit()
        if applied_corrections != set(corrections):
            raise ValueError(f"词遇审校目标词条缺失：{sorted(set(corrections) - applied_corrections)}")
        counts["wordnet_synsets"], counts["wordnet_lemma_senses"] = add_wordnet(dictionary, paths["english-wordnet-2025-core"])
        counts["total_entries"] = counts["curated_entries"] + counts["ecdict_only_entries"]
        counts["audio_candidates"] = dictionary.execute("SELECT count(*) FROM audio_candidates").fetchone()[0]
        counts["senses"] = sum(len(json.loads(row[0])["senses"]) for row in dictionary.execute("SELECT payload FROM entries"))
        files = {}
        files["entries.jsonl.gz"] = write_gzip_lines(out / "entries.jsonl.gz", (row[0] for row in dictionary.execute("SELECT payload FROM entries ORDER BY lookup_key,headword,entry_id")))
        files["core.jsonl.gz"] = write_gzip_lines(out / "core.jsonl.gz", (row[0] for row in dictionary.execute("SELECT payload FROM entries WHERE rank IS NOT NULL ORDER BY rank,headword,entry_id LIMIT ?", (core_size,))))
        files["audio-candidates.jsonl.gz"] = write_gzip_lines(out / "audio-candidates.jsonl.gz", (canonical(dict(zip(("entry_id", "headword", "pos", "url", "format", "status", "source"), row))) for row in dictionary.execute("SELECT * FROM audio_candidates ORDER BY headword,pos,url")))
    finally:
        dictionary.close()
        scratch.close()
    # 临时表只服务于构建，不进入发布目录；删除的都是本次生成的 scratch 文件。
    scratch_path.unlink()
    files["dictionary.sqlite"] = file_hash(db_path)
    # 词包单独下载时仍需附带每层数据的完整许可证与署名依据。
    repository_root = Path(__file__).resolve().parent.parent
    notices_out = out / "notices"
    notices_out.mkdir(exist_ok=True)
    for source in sorted((repository_root / "notices").iterdir()):
        if source.is_file():
            destination = notices_out / source.name
            shutil.copyfile(source, destination)
            files[f"notices/{source.name}"] = file_hash(destination)
    if editorial_path:
        editorial_out = out / "editorial"
        editorial_out.mkdir(exist_ok=True)
        shutil.copyfile(editorial_path, editorial_out / "corrections.json")
        files["editorial/corrections.json"] = file_hash(editorial_out / "corrections.json")
    shutil.copyfile(repository_root / "DATA-LICENSE.md", out / "DATA-LICENSE.md")
    files["DATA-LICENSE.md"] = file_hash(out / "DATA-LICENSE.md")
    manifest = {
        "schema_version": "leximeet.manifest.v1",
        "dictionary_version": VERSION,
        "entry_schema": SCHEMA,
        "generator": generator_state(repository_root),
        "counts": dict(counts),
        "inputs": inputs,
        "outputs": {name: {"bytes": size, "sha256": sha} for name, (size, sha) in files.items()},
        "core_limit": core_size,
        "data_license": "CC BY-SA 4.0 for Wiktionary/open-dictionary derived content; see DATA-LICENSE.md",
        # ECDICT 采用署名与权利通知处理策略；候选状态继续等待人工词义和端侧验收。
        "release_status": "candidate-needs-human-review",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest_size, manifest_sha = file_hash(out / "manifest.json")
    edition = {
        "schema_version": "leximeet.edition.v1", "dictionary_version": VERSION,
        "edition": "no-audio", "dictionary_manifest": "manifest.json",
        "dictionary_manifest_bytes": manifest_size, "dictionary_manifest_sha256": manifest_sha,
        "offline_audio_assets": 0,
        "online_audio": {"provider": "Wikimedia Commons Action API", "trigger": "user-click",
                         "cache_key_fields": ["text", "region", "provider", "voice", "speed", "version"],
                         "candidate_catalog": "audio-candidates.jsonl.gz"},
    }
    (out / "edition.no-audio.json").write_text(json.dumps(edition, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def lookup(db_path: Path, word: str) -> list[dict]:
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as db:
        rows = db.execute("SELECT payload FROM entries WHERE lookup_key=? ORDER BY CASE WHEN headword=? THEN 0 ELSE 1 END,headword", (lookup_key(word), word)).fetchall()
        if not rows:
            rows = db.execute("SELECT e.payload FROM forms f JOIN entries e USING(entry_id) WHERE f.form_key=? ORDER BY CASE WHEN f.form_text=? THEN 0 ELSE 1 END,e.headword", (lookup_key(word), word)).fetchall()
    return [json.loads(row[0]) for row in rows]


def wordnet_candidates(db_path: Path, word: str) -> list[dict]:
    """独立候选概念；调用者不得将其直接当成词卡义项映射。"""
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as db:
        rows = db.execute("""
            SELECT l.lemma,l.pos,l.sense_key,s.synset_id,s.definition,s.relations
            FROM wordnet_lemmas l JOIN wordnet_synsets s ON s.synset_id=l.synset_id
            WHERE l.lemma_key=? ORDER BY l.lemma,l.pos,s.synset_id
        """, (lookup_key(word),)).fetchall()
    return [{"lemma": r[0], "pos": r[1], "sense_key": r[2], "synset_id": r[3],
             "definition": json.loads(r[4]), "relations": json.loads(r[5]),
             "mapping_status": "unmapped-headword-candidate", "source": "english-wordnet:2025"} for r in rows]


def verify_package(out: Path) -> dict:
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("entry_schema") != SCHEMA or manifest.get("dictionary_version") != VERSION:
        raise ValueError("不兼容的词典 schema/version")
    for name, expected in manifest["outputs"].items():
        size, sha = file_hash(out / name)
        if (size, sha) != (expected["bytes"], expected["sha256"]):
            raise ValueError(f"词包损坏：{name}")
    # 完整无音频版与带发音版各自可单独安装；构建目录则允许同时存在两个 edition。
    editions = [out / f"edition.{name}.json" for name in ("no-audio", "with-audio")]
    if not any(path.is_file() for path in editions):
        raise ValueError("词包缺少 edition 清单")
    for edition_path in editions:
        if not edition_path.is_file():
            continue
        edition = json.loads(edition_path.read_text(encoding="utf-8"))
        name = edition_path.name.removeprefix("edition.").removesuffix(".json")
        if edition.get("edition") != name or file_hash(out / "manifest.json") != (
            edition["dictionary_manifest_bytes"], edition["dictionary_manifest_sha256"]
        ):
            raise ValueError(f"{name} 清单不匹配")
        if name == "with-audio":
            from .audio import verify_audio
            verify_audio(out / "audio")
    with closing(sqlite3.connect(f"file:{out / 'dictionary.sqlite'}?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite 完整性检查失败")
        count = db.execute("SELECT count(*) FROM entries").fetchone()[0]
        if count != manifest["counts"]["total_entries"]:
            raise ValueError("词条数量与清单不符")
    return manifest
