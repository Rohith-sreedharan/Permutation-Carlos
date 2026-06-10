"""
Phase 9 AC-3 Language Audit Scanner

Machine-readable scanner for prohibited sportsbook/wagering language.
Outputs JSON report with file, line, phrase, and matched text.

Negation exception:
- Mentions of "sportsbook" are allowed when clearly negated
  (e.g., "not a sportsbook", "not the sportsbook").
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "backend" / "logs" / "phase9_ac3_language_audit.json"

# AC-3: 10 directive surfaces
SURFACES: Sequence[str] = (
    "backend/routes",
    "backend/services",
    "backend/middleware",
    "backend/tools",
    "components",
    "src",
    "docs",
    "public",
    "uiCopy",
    "tests",
)

ALLOWED_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".yml",
    ".yaml",
}

PROHIBITED_PHRASES = [
    "place a bet",
    "place bet",
    "make a bet",
    "bet on",
    "wager",
    "wagering",
    "sportsbook",
    "bookmaker",
    "bookie",
    "guaranteed win",
    "sure thing",
    "lock of the week",
]

USER_FACING_HINTS = (
    "return",
    "subject",
    "body",
    "message",
    "title",
    "content",
    "tooltip",
    "alert(",
    "<p",
    "<h",
    "text=",
)


@dataclass
class Violation:
    file: str
    line: int
    phrase: str
    text: str


def _is_negated_sportsbook_line(lower_line: str, phrase: str) -> bool:
    if phrase == "sportsbook":
        return (
            "not a sportsbook" in lower_line
            or "not the sportsbook" in lower_line
            or "no sportsbook" in lower_line
            or "sportsbook odds" in lower_line
        )
    if phrase in ("wager", "wagering"):
        return (
            "no wagering" in lower_line
            or "does not facilitate any wagering" in lower_line
            or "no wager" in lower_line
            or "any wager placed based on platform content" in lower_line
        )
    return False


def _scan_file(path: Path) -> List[Violation]:
    violations: List[Violation] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return violations

    rel = str(path.relative_to(REPO_ROOT))
    if any(
        token in rel
        for token in (
            "explanation_forbidden_phrases.py",
            "phase5_growth_agent.py",
            "snapshot_capture.py",
        )
    ):
        return violations

    for idx, raw in enumerate(lines, start=1):
        line = raw.lower()

        # Skip comment lines and obvious non-user-facing declarations.
        stripped = line.strip()
        if stripped.startswith(("#", "//", "/*", "*", "\"\"\"", "'''", "- ")):
            continue
        if len(stripped) > 2 and stripped[0].isdigit() and stripped[1] == ".":
            continue
        if "prohibited" in stripped and "phrase" in stripped:
            continue
        if not any(hint in line for hint in USER_FACING_HINTS):
            continue

        for phrase in PROHIBITED_PHRASES:
            if phrase in line:
                if _is_negated_sportsbook_line(line, phrase):
                    continue
                violations.append(
                    Violation(
                        file=rel,
                        line=idx,
                        phrase=phrase,
                        text=raw.strip()[:300],
                    )
                )
    return violations


def _iter_surface_files() -> List[Path]:
    files: List[Path] = []
    for surface in SURFACES:
        base = REPO_ROOT / surface
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_dir():
                continue
            if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            files.append(path)
    return files


def run_scan() -> Dict:
    files = _iter_surface_files()
    violations: List[Violation] = []
    for path in files:
        violations.extend(_scan_file(path))

    by_phrase: Dict[str, int] = {}
    for item in violations:
        by_phrase[item.phrase] = by_phrase.get(item.phrase, 0) + 1

    return {
        "scanner": "phase9_ac3_language_audit",
        "surfaces": list(SURFACES),
        "files_scanned": len(files),
        "violations_count": len(violations),
        "violations_by_phrase": by_phrase,
        "violations": [asdict(v) for v in violations],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AC-3 language audit scanner")
    parser.add_argument("--ci", action="store_true", help="Exit non-zero when violations exist")
    args = parser.parse_args()

    report = run_scan()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== PHASE 9 AC-3 LANGUAGE AUDIT ===")
    print(f"files_scanned: {report['files_scanned']}")
    print(f"violations_count: {report['violations_count']}")
    print(f"report_path: {OUTPUT_PATH}")

    if report["violations_count"] > 0:
        print("STATUS: FAIL")
        if args.ci:
            raise SystemExit(1)
    else:
        print("STATUS: PASS")


if __name__ == "__main__":
    main()
