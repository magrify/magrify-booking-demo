from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent-orchestrator"))
from agent_orchestrator.incident_replay import replay_stalled_approval


parser = argparse.ArgumentParser(description="Replay and recover a stalled approval through the Magrify event ledger.")
parser.add_argument("--db", default="agent-orchestrator-incident-replay.sqlite3")
args = parser.parse_args()

print(json.dumps(replay_stalled_approval(Path(args.db)), indent=2))
