from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent-orchestrator"))
from agent_orchestrator.model_eval import evaluate_model_context


print(json.dumps(asyncio.run(evaluate_model_context()), indent=2))
