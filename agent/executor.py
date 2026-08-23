"""
Executor: runs the test suite for a task directory and parses results.

No LLM involvement here - this is what makes test_result data in the
trace trustworthy. It's real subprocess/pytest output, not a
self-report from the agent.
"""

import subprocess
import re
import os
import sys


def run_tests(task_dir: str, timeout: int = 60) -> dict:
    task_dir = os.path.abspath(task_dir)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-v"],
        cwd=task_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = proc.stdout + proc.stderr

    failing_raw = re.findall(r"FAILED\s+(\S+::\S+)", output)
    failing_short = [f.split("::")[-1] if "::" in f else f for f in failing_raw]

    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)
    tests_passed = int(passed_match.group(1)) if passed_match else 0
    tests_failed = int(failed_match.group(1)) if failed_match else 0

    all_pass = tests_failed == 0 and proc.returncode == 0

    return {
        "output": output[-4000:],
        "failing_tests": failing_short,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "all_pass": all_pass,
        "returncode": proc.returncode,
    }