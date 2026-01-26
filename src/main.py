from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from src.storage import Paths, load_state, save_state, write_episode_artifact
from src.feeds import discover_new_episodes


def cmd_ingest(repo_root: Path) -> int:
    paths = Paths(repo_root=repo_root)
    state = load_state(paths)

    new_eps, state = discover_new_episodes(repo_root=repo_root, state=state)

    # Persist per-episode artifacts (MVP: only new ones)
    for ep in new_eps:
        write_episode_artifact(paths, ep["episode_id"], ep)

    state["last_run_utc"] = datetime.now(timezone.utc).isoformat()
    save_state(paths, state)

    print(f"New episodes: {len(new_eps)}")
    for ep in new_eps:
        print(f"- {ep['episode_id']} | {ep.get('feed_id')} | {ep.get('title')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="podcast-digest")
    sub = p.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest", help="Fetch RSS feeds, dedupe, update repo state.")
    ingest.add_argument("--repo-root", default=".", help="Path to repo root.")
    return p


def main() -> int:
    p = build_parser()
    args = p.parse_args()
    repo_root = Path(args.repo_root).resolve()

    if args.cmd == "ingest":
        return cmd_ingest(repo_root)

    raise RuntimeError("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
