"""Locating the `bhl.proj` directory the language server should use as its root."""
from __future__ import annotations

import os
from typing import List, Optional

PROJECT_FILE = "bhl.proj"

# Directories that never hold a BHL project but can be huge (e.g. in Unity projects).
_SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "Library", "Temp", "Logs", "obj"}
_MAX_DEPTH = 6
_MAX_DIRS = 20000


def find_upwards(start_dir: str) -> Optional[str]:
    """Nearest ancestor of `start_dir` (inclusive) containing a bhl.proj."""
    current = os.path.abspath(start_dir)
    while True:
        if os.path.isfile(os.path.join(current, PROJECT_FILE)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def find_in_folders(folders: List[str]) -> List[str]:
    """Every directory under `folders` containing a bhl.proj (bounded search)."""
    found: List[str] = []
    visited = 0
    for folder in folders:
        base_depth = os.path.abspath(folder).count(os.sep)
        for root, dirs, files in os.walk(folder):
            visited += 1
            if PROJECT_FILE in files and root not in found:
                found.append(root)
            if visited >= _MAX_DIRS or root.count(os.sep) - base_depth >= _MAX_DEPTH:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            if visited >= _MAX_DIRS:
                break
    return found


def resolve(file_name: Optional[str], folders: List[str]) -> Optional[str]:
    """
    The project directory for the file being opened: the nearest bhl.proj above it, otherwise the
    only bhl.proj found under the open folders. None if there is none, or if several are found
    (can't be disambiguated without asking).
    """
    if file_name:
        found = find_upwards(os.path.dirname(file_name))
        if found:
            return found
    candidates = find_in_folders(folders)
    return candidates[0] if len(candidates) == 1 else None
