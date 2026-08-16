"""Keeping a backlog entry honest about the code it describes.

An entry is a claim: "lines 88-104 of auth.rs duplicate users.rs". Two commits
later that claim may be about entirely different code, and nothing noticed. A
backlog whose live entries cannot be told from its rotted ones is one nobody
drains, which is the failure this plugin exists to prevent.

So each entry carries an **anchor** captured at record time — a hash of the
file, and a fingerprint of the code the entry actually points at. Reading the
backlog re-checks both and answers one of:

    current        the code the entry describes is still there
    moved          it is still there, at a different line range
    drifted        it is not there any more; the entry needs a human look
    missing        the file itself is gone
    unverifiable   nothing to check against (a file-level finding, or an entry
                   recorded before anchors existed)

`drifted` is deliberately not `stale`. The code changing is evidence that the
entry may be obsolete, never proof: a rewrite can leave the original smell
exactly where it was. Closing on a fingerprint miss would silently delete real
findings, so nothing here ever closes anything — it reports, and a person or an
agent decides.
"""
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from source_lines import detect_language, read_content, significant_lines

_HASH_CHARS = 16


def _digest(text: str) -> str:
    """A hash that survives leaving the process.

    Python's built-in hash() is randomised per interpreter run, so an anchor
    hashed with it would stop matching the moment it was read back from disk.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_HASH_CHARS]


def _resolve(project_dir: str, todo: Dict) -> Path:
    return Path(project_dir) / str(todo.get("file_path", ""))


def _primary_range(todo: Dict) -> Optional[Tuple[int, int]]:
    """The line range an entry is anchored to.

    A duplication finding carries two locations; the first is where the entry
    is filed, and it is the one worth tracking. Following both would double the
    ways an anchor can go stale without doubling what anyone learns from it.
    """
    locations = todo.get("locations") or []
    if not locations:
        return None
    first = locations[0]
    start, end = first.get("line_start"), first.get("line_end")
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    return (start, end)


def _fingerprint_range(
    content: str, language: str, line_range: Tuple[int, int]
) -> Optional[Tuple[str, int]]:
    """Fingerprint the significant lines inside a range, ignoring blanks and
    comments so reformatting does not read as a rewrite.
    """
    start, end = line_range
    block = [norm for lineno, norm in significant_lines(content, language)
             if start <= lineno <= end]
    if not block:
        return None
    return _digest("\n".join(block)), len(block)


def capture_anchor(project_dir: str, todo: Dict) -> Optional[Dict]:
    """Snapshot what a finding is about, at the moment it is recorded.

    Returns None when there is nothing to snapshot — an unreadable or missing
    file. Recording must never fail because the anchor could not be taken.
    """
    content = read_content(str(_resolve(project_dir, todo)))
    if content is None:
        return None

    anchor: Dict = {"file_hash": _digest(content)}

    line_range = _primary_range(todo)
    if line_range is not None:
        fingerprinted = _fingerprint_range(content, detect_language(
            str(_resolve(project_dir, todo))), line_range)
        if fingerprinted is not None:
            anchor["fingerprint"], anchor["line_count"] = fingerprinted
    return anchor


def _locate(
    content: str, language: str, fingerprint: str, line_count: int
) -> Optional[Dict]:
    """Find the fingerprinted block anywhere in the file, as a line range."""
    lines = significant_lines(content, language)
    if line_count <= 0 or len(lines) < line_count:
        return None

    for i in range(len(lines) - line_count + 1):
        window = lines[i:i + line_count]
        if _digest("\n".join(norm for _, norm in window)) == fingerprint:
            return {"line_start": window[0][0], "line_end": window[-1][0]}
    return None


def check_anchor(project_dir: str, todo: Dict) -> Dict:
    """Whether an entry still describes the code it was recorded against.

    Always returns a dict with a `status`; `moved` additionally carries the
    `locations` the code is at now.
    """
    path = _resolve(project_dir, todo)
    content = read_content(str(path))
    if content is None:
        return {"status": "missing"}

    anchor = todo.get("anchor") or {}
    fingerprint = anchor.get("fingerprint")
    if not anchor or not fingerprint:
        return {"status": "unverifiable"}

    if anchor.get("file_hash") == _digest(content):
        return {"status": "current"}

    located = _locate(
        content, detect_language(str(path)), fingerprint, anchor.get("line_count", 0)
    )
    if located is None:
        return {"status": "drifted"}
    if _primary_range(todo) == (located["line_start"], located["line_end"]):
        return {"status": "current"}
    return {"status": "moved", "locations": [located]}


NEEDS_ATTENTION = ("missing", "drifted")


def annotate(project_dir: str, todos: List[Dict]) -> List[Dict]:
    """Return the entries with their anchor check attached as `anchor_status`
    (and `current_locations` for the ones that moved).
    """
    annotated = []
    for todo in todos:
        result = check_anchor(project_dir, todo)
        entry = {**todo, "anchor_status": result["status"]}
        if "locations" in result:
            entry["current_locations"] = result["locations"]
        annotated.append(entry)
    return annotated
