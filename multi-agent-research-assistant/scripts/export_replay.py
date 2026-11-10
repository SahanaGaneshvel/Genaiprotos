"""Export a saved run (outputs/run_*.json) as the replay file the website plays back.

    python scripts/export_replay.py outputs/run_20261110_183912.json

Keeps only what the page needs (question, model, timings, the recorded events and the
report) and drops the bulky page texts, so the file stays small.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "web" / "public" / "recorded-run.json"


def export(run_file: Path) -> dict:
    run = json.loads(run_file.read_text(encoding="utf-8"))
    if not run.get("events"):
        raise SystemExit(f"{run_file.name} has no recorded events — it was made before event recording existed.")
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
    data = export(Path(sys.argv[1]))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {TARGET} ({TARGET.stat().st_size // 1024} KB, {len(data['events'])} events)")
