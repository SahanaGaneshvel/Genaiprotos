"""Export a saved run (outputs/run_*.json) as the replay file the website plays back.

    python scripts/export_replay.py outputs/run_20261110_183912.json

Keeps only what the page needs (question, model, timings, the recorded events and the
report) and drops the bulky page texts, so the file stays small.

It also replaces em dashes (U+2014) with ordinary punctuation: a title like "X <dash> model card"
becomes "X (model card)", "**Model** <dash> text" becomes "**Model**: text", and any other
spaced dash becomes a comma. Punctuation only: no word, number or link is changed.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "web" / "public" / "recorded-run.json"


EM_DASH = "\u2014"


def no_em_dashes(value):
    """Recursively replace em dashes in every string of the exported data (punctuation only)."""
    if isinstance(value, str):
        value = value.replace(f" {EM_DASH} model card", " (model card)")
        value = value.replace(f"** {EM_DASH} ", "**: ")
        value = value.replace(f" {EM_DASH} ", ", ")
        return value.replace(EM_DASH, "-")
    if isinstance(value, list):
        return [no_em_dashes(v) for v in value]
    if isinstance(value, dict):
        return {k: no_em_dashes(v) for k, v in value.items()}
    return value


def export(run_file: Path) -> dict:
    run = json.loads(run_file.read_text(encoding="utf-8"))
    if not run.get("events"):
        raise SystemExit(f"{run_file.name} has no recorded events, it was made before event recording existed.")
    stamp = re.search(r"(\d{8}_\d{6})", run_file.name)
    recorded_at = datetime.strptime(stamp.group(1), "%Y%m%d_%H%M%S").isoformat() if stamp else None
    report = run.get("report") or {}
    return {
        "topic": run["topic"],
        "depth": run.get("depth", "basic"),
        "model_name": run.get("model_name"),
        "recorded_at": recorded_at,
        "agent_status": run.get("agent_status", {}),
        "timings": run.get("timings", {}),
        "errors": run.get("errors", []),
        "execution_order": run.get("execution_order", []),
        "events": run["events"],
        "report": {
            "markdown": report.get("markdown", ""),
            "narrative_generated": report.get("narrative_generated", False),
            "removed_citations": report.get("removed_citations", []),
            "removed_claims": report.get("removed_claims", []),
            "citation_check": report.get("citation_check", {}),
            "insufficient_evidence": report.get("insufficient_evidence", False),
        },
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    data = no_em_dashes(export(Path(sys.argv[1])))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {TARGET} ({TARGET.stat().st_size // 1024} KB, {len(data['events'])} events)")
