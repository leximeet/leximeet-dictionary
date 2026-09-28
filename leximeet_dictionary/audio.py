"""Commons 录音的逐文件元数据核验、离线包生成与按需缓存。"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path

from .builder import canonical, file_hash, lookup_key

API = "https://commons.wikimedia.org/w/api.php"
COMMONS_PREFIX = "https://upload.wikimedia.org/wikipedia/commons/"
USER_AGENT = "LexiMeetDictionary/0.0.1 (https://github.com/leximeet/leximeet-dictionary)"
ALLOWED_LICENSES = {"CC0", "CC BY 2.0", "CC BY 2.5", "CC BY 3.0", "CC BY 4.0",
                    "CC BY-SA 2.0", "CC BY-SA 2.5", "CC BY-SA 3.0", "CC BY-SA 4.0"}
POS_NAMES = {"noun", "verb", "adjective", "adverb", "adj", "adv"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(markup: str) -> str:
    parser = _Text()
    parser.feed(markup)
    return " ".join("".join(parser.parts).split())


def file_title(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "upload.wikimedia.org":
        return None
    if not parsed.path.startswith("/wikipedia/commons/") or "/transcoded/" in parsed.path:
        return None
    name = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1])
    if not name.lower().endswith((".ogg", ".oga", ".mp3", ".wav")):
        return None
    return "File:" + name


def title_matches_word(title: str, word: str, pos: str | None) -> bool:
    """保守筛选文件名，防止 record-noun 被误贴到 verb。"""
    stem = title.removeprefix("File:").rsplit(".", 1)[0].casefold().replace("_", "-")
    normalized = re.sub(r"\s+", "-", word.casefold())
    expected = (f"en-us-{normalized}", f"en-uk-{normalized}", f"en-gb-{normalized}")
    if stem in expected:
        return True
    for region in ("en-us", "en-uk", "en-gb"):
        prefix = f"{region}-{normalized}-"
        if stem.startswith(prefix):
            suffix = stem[len(prefix):]
            return suffix in POS_NAMES and (pos == suffix or (pos == "adj" and suffix == "adjective"))
    return False


def selected_candidates(db_path: Path, limit: int) -> list[dict]:
    selected: list[dict] = []
    seen = set()
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as db:
        rows = db.execute("""
            SELECT e.entry_id,e.headword,e.rank,c.pos,c.url
            FROM entries e JOIN audio_candidates c ON c.entry_id=e.entry_id
            WHERE e.rank IS NOT NULL
            ORDER BY e.rank,e.headword,CASE WHEN c.url LIKE '%En-us-%' THEN 0 ELSE 1 END,c.url
        """)
        for entry_id, word, rank, pos, url in rows:
            if entry_id in seen:
                continue
            title = file_title(url)
            if title and title_matches_word(title, word, pos):
                selected.append({"entry_id": entry_id, "headword": word, "rank": rank,
                                 "pos": pos, "candidate_url": url, "title": title})
                seen.add(entry_id)
                if len(selected) >= limit:
                    break
    return selected


def _request_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def commons_info(titles: list[str]) -> dict[str, dict]:
    query = urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2", "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "titles": "|".join(titles),
        "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|Credit|AttributionRequired|Restrictions",
    })
    pages = _request_json(f"{API}?{query}").get("query", {}).get("pages", [])
    return {page["title"]: page["imageinfo"][0] for page in pages if page.get("imageinfo")}


def review(info: dict) -> tuple[dict | None, str | None]:
    meta = {key: value.get("value", "") for key, value in info.get("extmetadata", {}).items()}
    license_name = plain_text(meta.get("LicenseShortName", ""))
    artist = plain_text(meta.get("Artist", ""))
    license_url = meta.get("LicenseUrl", "").replace("http://creativecommons.org/", "https://creativecommons.org/")
    media_url = info.get("url", "")
    if license_name not in ALLOWED_LICENSES:
        return None, "license-not-allowlisted"
    if not artist or not license_url:
        return None, "missing-artist-or-license-url"
    license_parts = urllib.parse.urlparse(license_url)
    if license_parts.scheme != "https" or license_parts.netloc != "creativecommons.org":
        return None, "untrusted-license-url"
    if plain_text(meta.get("Restrictions", "")):
        return None, "restricted"
    if info.get("mime") not in ("application/ogg", "audio/ogg", "audio/mpeg", "audio/wav", "audio/x-wav"):
        return None, "unsupported-media-type"
    if not isinstance(info.get("size"), int) or info["size"] > 1024 * 1024:
        return None, "file-too-large-or-missing-size"
    if not media_url.startswith(COMMONS_PREFIX):
        return None, "non-commons-media-url"
    return {"license": license_name, "license_url": license_url, "artist": artist,
            "credit": plain_text(meta.get("Credit", "")), "url": media_url,
            "source_page": info.get("descriptionurl"), "mime_type": info["mime"],
            "expected_bytes": info["size"]}, None


def _download(url: str, path: Path, max_bytes: int) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response, path.open("wb") as output:
                if response.url.split("?", 1)[0].startswith(COMMONS_PREFIX) is False:
                    raise ValueError("录音重定向到非 Commons 域名")
                size = 0
                while chunk := response.read(65536):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("录音超过允许大小")
                    output.write(chunk)
            return file_hash(path)
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def build_audio(db_path: Path, out: Path, limit: int = 500) -> dict:
    """只为匹配文件名且元数据完整的高频词收录录音。"""
    if limit < 1:
        raise ValueError("limit 必须为正整数")
    out.mkdir(parents=True, exist_ok=True)
    audio_dir = out / "files"
    audio_dir.mkdir(exist_ok=True)
    candidates = selected_candidates(db_path, limit)
    selected = []
    skipped = []
    for offset in range(0, len(candidates), 20):
        batch = candidates[offset:offset + 20]
        try:
            info_by_title = commons_info([item["title"] for item in batch])
        except (OSError, ValueError) as error:
            for item in batch:
                skipped.append({"headword": item["headword"], "title": item["title"],
                                "reason": f"commons-api-unavailable: {error}"})
            continue
        for item in batch:
            title = item["title"]
            info = info_by_title.get(title)
            if not info:
                skipped.append({"headword": item["headword"], "title": title, "reason": "commons-file-not-found"})
                continue
            approved, reason = review(info)
            if reason:
                skipped.append({"headword": item["headword"], "title": title, "reason": reason})
                continue
            suffix = Path(urllib.parse.urlparse(approved["url"]).path).suffix.lower()
            asset_id = item["entry_id"] + suffix
            destination = audio_dir / asset_id
            try:
                size, sha256 = _download(approved["url"], destination, approved["expected_bytes"] + 1024)
                if size != approved["expected_bytes"]:
                    raise ValueError("文件字节数与 Commons 元数据不符")
            except (OSError, ValueError) as error:
                destination.unlink(missing_ok=True)
                skipped.append({"headword": item["headword"], "title": title, "reason": str(error)})
                continue
            selected.append({**item, **approved, "path": f"files/{asset_id}",
                             "bytes": size, "sha256": sha256,
                             "attribution": f"{approved['artist']} · {title} · {approved['license']} ({approved['license_url']}) · {approved['source_page']}"})
    manifest = {"schema_version": "leximeet.audio.v1", "dictionary_version": "0.0.1",
                "selection": "ECDICT frq/bnc rank, conservative Commons filename match",
                "requested": limit, "selected_candidates": len(candidates),
                "offline_asset_count": len(selected), "assets": selected, "skipped": skipped,
                "review_level": "automated-metadata-review; human-sample-review-pending"}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    dictionary_dir = db_path.parent
    dictionary_manifest_size, dictionary_manifest_sha = file_hash(dictionary_dir / "manifest.json")
    audio_manifest_size, audio_manifest_sha = file_hash(out / "manifest.json")
    edition = {"schema_version": "leximeet.edition.v1", "dictionary_version": "0.0.1",
               "edition": "with-audio", "dictionary_manifest": "manifest.json",
               "dictionary_manifest_bytes": dictionary_manifest_size,
               "dictionary_manifest_sha256": dictionary_manifest_sha,
               "audio_manifest": str((out / "manifest.json").relative_to(dictionary_dir)),
               "audio_manifest_bytes": audio_manifest_size, "audio_manifest_sha256": audio_manifest_sha,
               "offline_audio_assets": len(selected),
               "remaining_audio": "on-demand Commons cache; optional device TTS"}
    (dictionary_dir / "edition.with-audio.json").write_text(
        json.dumps(edition, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def cache_on_demand(db_path: Path, word: str, cache_dir: Path, region: str = "en-US") -> dict | None:
    """用户点击朗读时获取并核验一个 Commons 录音；无候选时返回 None。"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as db:
        candidates = db.execute("""
            SELECT c.entry_id,c.headword,c.pos,c.url FROM audio_candidates c
            JOIN entries e ON e.entry_id=c.entry_id WHERE e.lookup_key=?
            ORDER BY CASE WHEN e.headword=? THEN 0 ELSE 1 END,c.url
        """, (lookup_key(word), word)).fetchall()
    prefix = "En-us-" if region == "en-US" else "En-uk-"
    for entry_id, headword, pos, url in candidates:
        title = file_title(url)
        if not title or not title_matches_word(title, headword, pos):
            continue
        if not title.removeprefix("File:").casefold().startswith(prefix.casefold()):
            continue
        key = cache_key(headword, region, "commons", title, "1", "0.0.1")
        destination = cache_dir / (key + Path(title).suffix.lower())
        metadata_path = cache_dir / (key + ".json")
        if destination.is_file() and metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if file_hash(destination) == (metadata["bytes"], metadata["sha256"]):
                    return metadata
            except (OSError, ValueError, KeyError):
                pass
        try:
            info = commons_info([title]).get(title)
        except (OSError, ValueError):
            return None
        if not info:
            continue
        approved, reason = review(info)
        if reason:
            continue
        try:
            size, sha256 = _download(approved["url"], destination, approved["expected_bytes"] + 1024)
            if size != approved["expected_bytes"]:
                raise ValueError("文件字节数与 Commons 元数据不符")
        except (OSError, ValueError):
            destination.unlink(missing_ok=True)
            continue
        metadata = {"entry_id": entry_id, "headword": headword, "region": region,
                    "path": str(destination), "bytes": size, "sha256": sha256,
                    "provider": "commons", "title": title, **approved}
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return metadata
    return None


def cache_key(text: str, region: str, provider: str, voice: str, speed: str, version: str) -> str:
    """运行时缓存键包含提供方参数，防止跨音色或语速误命中。"""
    import hashlib
    payload = canonical({"text": text, "region": region, "provider": provider,
                         "voice": voice, "speed": speed, "version": version})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_audio(out: Path) -> dict:
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "leximeet.audio.v1":
        raise ValueError("音频包 schema 不兼容")
    if manifest.get("offline_asset_count") != len(manifest["assets"]):
        raise ValueError("音频包资产数量不符")
    for asset in manifest["assets"]:
        path = out / asset["path"]
        if file_hash(path) != (asset["bytes"], asset["sha256"]):
            raise ValueError(f"音频文件损坏：{asset['path']}")
        if not all(asset.get(key) for key in ("artist", "license", "license_url", "source_page", "attribution")):
            raise ValueError(f"音频文件缺少许可与署名：{asset['path']}")
    edition = json.loads((out.parent / "edition.with-audio.json").read_text(encoding="utf-8"))
    if edition.get("edition") != "with-audio" or file_hash(out / "manifest.json") != (
        edition["audio_manifest_bytes"], edition["audio_manifest_sha256"]
    ):
        raise ValueError("带发音版清单不匹配")
    if file_hash(out.parent / "manifest.json") != (
        edition["dictionary_manifest_bytes"], edition["dictionary_manifest_sha256"]
    ):
        raise ValueError("带发音版引用的词典清单不匹配")
    return manifest
