from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent-orchestrator"))
from agent_orchestrator.load_test import run_validation_load


parser = argparse.ArgumentParser(description="Exercise the Magrify reliability ledger with synthetic concurrent traffic.")
parser.add_argument("--db", default="agent-orchestrator-load-test.sqlite3")
parser.add_argument("--runs", type=int, default=100)
args = parser.parse_args()

print(json.dumps(run_validation_load(Path(args.db), runs=args.runs), indent=2))
