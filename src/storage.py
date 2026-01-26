from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class Paths:
    repo_root: Path

    @property
    def state_file(self) -> Path:
        return self.repo_root / "state" / "state.json"

    @property
    def episodes_dir(self) -> Path:
        return self.repo_root / "artifacts" / "episodes"


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """
    Atomic write to avoid partial state on runner interruptions.
    """
    ensure_parent_dir(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    return json.loads(raw)


def load_state(paths: Paths) -> Dict[str, Any]:
    default = {"version": 1, "episodes_seen": {}, "last_run_utc": None}
    state = read_json(paths.state_file, default=default)

    # Minimal schema hygiene
    state.setdefault("version", 1)
    state.setdefault("episodes_seen", {})
    state.setdefault("last_run_utc", None)

    return state


def save_state(paths: Paths, state: Dict[str, Any]) -> None:
    atomic_write_json(paths.state_file, state)


def write_episode_artifact(paths: Paths, episode_id: str, payload: Dict[str, Any]) -> None:
    paths.episodes_dir.mkdir(parents=True, exist_ok=True)
    out = paths.episodes_dir / f"{episode_id}.json"
    atomic_write_json(out, payload)
