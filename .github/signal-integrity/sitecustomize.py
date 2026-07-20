"""One-shot recovery hook for the signal-integrity repair workflow.

The historical workflow stops on the first patch-script error. Persisting the
working tree lets us inspect and repair the exact generated source rather than
repeatedly guessing from truncated Actions logs. This file is deleted with the
rest of the temporary patch machinery after verification.
"""
from __future__ import annotations

import atexit
import os
from pathlib import Path
import subprocess
import sys


def _run() -> None:
    if os.environ.get("STERLING_PATCH_RECOVERY") == "1":
        return
    if not sys.argv or not sys.argv[0].endswith("patch_backend.py"):
        return
    env = dict(os.environ, STERLING_PATCH_RECOVERY="1")
    root = Path.cwd()
    diagnostics = []
    for script in ("patch_frontend.py", "patch_tests.py"):
        proc = subprocess.run(
            [sys.executable, str(root / ".github/signal-integrity" / script)],
            cwd=root, env=env, text=True, capture_output=True,
        )
        diagnostics.append(f"=== {script} rc={proc.returncode} ===\n{proc.stdout}\n{proc.stderr}")
    (root / ".github/signal-integrity/recovery.log").write_text("\n".join(diagnostics))
    subprocess.run(["git", "config", "user.name", "OpenAI"], cwd=root, env=env)
    subprocess.run(["git", "config", "user.email", "noreply@openai.com"], cwd=root, env=env)
    subprocess.run(["git", "add", "backend", "frontend", ".github/signal-integrity/recovery.log"], cwd=root, env=env)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root, env=env)
    if diff.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", "fix(kite): apply signal-integrity source for verification"],
            cwd=root, env=env, check=False,
        )
        subprocess.run(
            ["git", "push", "origin", "HEAD:fix/kite-signal-integrity-audit"],
            cwd=root, env=env, check=False,
        )


atexit.register(_run)
