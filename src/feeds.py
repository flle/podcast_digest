from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

import feedparser
import yaml
from dateutil import parser as dtparser


@dataclass(frozen=True)
class FeedConfig:
    id: str
    url: str


def load_feeds_config(repo_root: Path) -> List[FeedConfig]:
    cfg_path = repo_root / "config" / "feeds.yml"
    raw = cfg_path.read_text(encoding="utf-8").strip()
    if not raw:
        raise RuntimeError("config/feeds.yml is empty. Please add at least one feed.")
    cfg = yaml.safe_load(raw)
    feeds = cfg.get("feeds", [])
    if not isinstance(feeds, list) or not feeds:
        raise RuntimeError("config/feeds.yml must contain a non-empty 'feeds:' list.")

    out: List[FeedConfig] = []
    for item in feeds:
        if not isinstance(item, dict) or "id" not in item or "url" not in item:
            raise RuntimeError("Each feed must be an object with 'id' and 'url'.")
        out.append(FeedConfig(id=str(item["id"]), url=str(item["url"])))
    return out


def _stable_episode_key(entry: Any) -> str:
    """
    Prefer GUID; fallback to link; then enclosure URL; finally title+published (worst case).
    We hash the chosen key to get a safe, filesystem-friendly episode_id.
    """
    guid = getattr(entry, "id", None) or entry.get("id")
    link = getattr(entry, "link", None) or entry.get("link")
    enclosure_url = None

    enclosures = entry.get("enclosures") or []
    if enclosures and isinstance(enclosures, list):
        enclosure_url = enclosures[0].get("href")

    title = getattr(entry, "title", None) or entry.get("title")
    published = getattr(entry, "published", None) or entry.get("published")

    key = guid or link or enclosure_url or f"{title}|{published}"
    key_bytes = (key or "").encode("utf-8")
    return hashlib.sha256(key_bytes).hexdigest()


def _parse_published_utc(entry: Any) -> Optional[str]:
    # feedparser gives multiple fields; published is most common
    published = entry.get("published") or entry.get("updated")
    if not published:
        return None
    try:
        dt = dtparser.parse(published)
        if dt.tzinfo is None:
            # treat as UTC if timezone missing (rare)
            return dt.replace(tzinfo=dtparser.tz.UTC).astimezone(dtparser.tz.UTC).isoformat()
        return dt.astimezone(dtparser.tz.UTC).isoformat()
    except Exception:
        return None


def fetch_feed(url: str) -> feedparser.FeedParserDict:
    parsed = feedparser.parse(url)
    # feedparser sets bozo when parsing fails; still might have partial entries
    return parsed


def normalize_entry(feed_id: str, entry: Any) -> Dict[str, Any]:
    enclosures = entry.get("enclosures") or []
    enclosure_url = None
    if enclosures and isinstance(enclosures, list):
        enclosure_url = enclosures[0].get("href")

    episode_id = _stable_episode_key(entry)
    payload: Dict[str, Any] = {
        "episode_id": episode_id,
        "feed_id": feed_id,
        "guid": entry.get("id"),
        "title": entry.get("title"),
        "link": entry.get("link"),
        "published_utc": _parse_published_utc(entry),
        "summary": entry.get("summary"),
        "enclosure_url": enclosure_url,
    }
    return payload


def discover_new_episodes(
    repo_root: Path,
    state: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (new_episodes, updated_state)
    """
    feeds = load_feeds_config(repo_root)
    episodes_seen: Dict[str, Any] = state.get("episodes_seen", {})
    new_eps: List[Dict[str, Any]] = []

    for f in feeds:
        parsed = fetch_feed(f.url)
        entries = parsed.get("entries") or []
        for e in entries:
            ep = normalize_entry(f.id, e)
            eid = ep["episode_id"]
            if eid in episodes_seen:
                continue
            new_eps.append(ep)

    # Sort deterministically: by published_utc then episode_id
    def sort_key(ep: Dict[str, Any]) -> tuple:
        return (ep.get("published_utc") or "", ep["episode_id"])

    new_eps.sort(key=sort_key)

    # Update state
    for ep in new_eps:
        episodes_seen[ep["episode_id"]] = {
            "feed_id": ep["feed_id"],
            "title": ep.get("title"),
            "link": ep.get("link"),
            "published_utc": ep.get("published_utc"),
        }

    state["episodes_seen"] = episodes_seen
    return new_eps, state
