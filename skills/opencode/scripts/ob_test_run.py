#!/usr/bin/env python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _find_project() -> Path:
    env_hint = os.getenv("OB_TEST_INTEL_HOME")
    if env_hint:
        p = Path(env_hint)
        if (p / "scripts" / "ob_test_run.py").exists():
            return p

    file_parent = Path(__file__).resolve().parent
    if (file_parent / "scripts" / "ob_test_run.py").exists():
        return file_parent

    for candidate_name in ["ob-test-intelligence"]:
        for search in [Path.home() / "repos", Path.home() / "projects", Path("/repos")]:
            p = search / candidate_name
            if (p / "scripts" / "ob_test_run.py").exists():
                return p

    print("ERROR: ob-test-intelligence project not found.")
    print("Set OB_TEST_INTEL_HOME env var to the project root directory.")
    print("Example: set OB_TEST_INTEL_HOME=C:\\Users\\you\\repos\\ob-test-intelligence")
    sys.exit(1)


_PROJECT_DIR = _find_project()


def main():
    python = sys.executable
    main_script = _PROJECT_DIR / "scripts" / "ob_test_run.py"
    result = subprocess.run(
        [python, str(main_script)] + sys.argv[1:],
        cwd=str(_PROJECT_DIR),
        env={
            **os.environ,
            "PYTHONPATH": str(_PROJECT_DIR / "src"),
            "OB_TEST_INTEL_HOME": str(_PROJECT_DIR),
        },
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
