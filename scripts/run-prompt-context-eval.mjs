import { spawnSync } from "node:child_process";

const python = process.env.PYTHON ?? "python";
const result = spawnSync(
  python,
  ["-c", "import json; from agent_orchestrator.prompt_eval import optimize_prompt_context; print(json.dumps(optimize_prompt_context(), indent=2))"],
  { cwd: new URL("../agent-orchestrator/", import.meta.url), encoding: "utf8" },
);

if (result.error) throw result.error;
process.stdout.write(result.stdout);
process.stderr.write(result.stderr);
process.exit(result.status ?? 1);
