"""
Test debt tracker.

Deterministic by construction: uses coverage.py's real line-execution
data, not an LLM judgment call. For a given file, compares a "before"
and "after" snapshot to find changed lines, then checks how many of
those changed lines are actually exercised by the test suite.

Only lines coverage.py treats as real statements are judged - this
excludes docstrings, comments, and blank lines, which are never
"statements" and would otherwise be falsely counted as debt.

debt_ratio = uncovered_changed_statements / total_changed_statements
"""

import sys
import os
import json
import difflib
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def changed_line_numbers(before_path: str, after_path: str) -> set:
    """Return the set of 1-indexed line numbers in `after` that are new
    or modified relative to `before`."""
    with open(before_path) as f:
        before_lines = f.readlines()
    with open(after_path) as f:
        after_lines = f.readlines()

    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    changed = set()
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "insert"):
            for line_no in range(j1 + 1, j2 + 1):
                changed.add(line_no)
    return changed


def get_covered_lines(module_path: str, test_dir: str) -> dict:
    """
    Run coverage.py against test_dir targeting module_path.
    Returns {"executed": set(...), "measurable": set(...)} where
    measurable = executed + missed (every line coverage.py actually
    considers a real statement).
    """
    module_path = os.path.abspath(module_path)
    test_dir = os.path.abspath(test_dir)
    module_dir = os.path.dirname(module_path)
    module_name = os.path.splitext(os.path.basename(module_path))[0]

    coverage_data_file = os.path.join(module_dir, ".coverage_test_debt")
    if os.path.exists(coverage_data_file):
        os.remove(coverage_data_file)

    subprocess.run(
        [
            sys.executable, "-m", "coverage", "run",
            f"--data-file={coverage_data_file}",
            f"--source={module_name}",
            "-m", "pytest", test_dir,
        ],
        cwd=module_dir,
        capture_output=True,
        text=True,
    )

    json_out = os.path.join(module_dir, "_coverage_test_debt.json")
    if os.path.exists(json_out):
        os.remove(json_out)

    subprocess.run(
        [
            sys.executable, "-m", "coverage", "json",
            f"--data-file={coverage_data_file}",
            "-o", json_out,
        ],
        cwd=module_dir,
        capture_output=True,
        text=True,
    )

    if not os.path.exists(json_out):
        return {"executed": set(), "measurable": set()}

    with open(json_out) as f:
        cov_data = json.load(f)

    executed, missing = set(), set()
    for file_key, file_data in cov_data.get("files", {}).items():
        if os.path.basename(file_key) == os.path.basename(module_path):
            executed = set(file_data["executed_lines"])
            missing = set(file_data.get("missing_lines", []))
            break

    os.remove(json_out)
    if os.path.exists(coverage_data_file):
        os.remove(coverage_data_file)

    return {"executed": executed, "measurable": executed | missing}


def compute_test_debt(before_path: str, after_path: str, test_dir: str) -> dict:
    changed = changed_line_numbers(before_path, after_path)
    cov = get_covered_lines(after_path, test_dir)

    changed_statements = changed & cov["measurable"]
    covered_changed = changed_statements & cov["executed"]
    uncovered_changed = changed_statements - cov["executed"]
    non_statement_changed = changed - cov["measurable"]

    total = len(changed_statements)
    debt_ratio = (len(uncovered_changed) / total) if total > 0 else 0.0

    return {
        "file": after_path,
        "total_changed_lines_raw": len(changed),
        "total_changed_statements": total,
        "non_statement_changed_lines": sorted(non_statement_changed),
        "covered_changed_lines": sorted(covered_changed),
        "uncovered_changed_lines": sorted(uncovered_changed),
        "debt_ratio": round(debt_ratio, 3),
    }


def print_report(result: dict):
    print(f"\n=== Test debt report: {result['file']} ===")
    print(f"Raw changed lines (incl. docstrings/comments): {result['total_changed_lines_raw']}")
    print(f"  of which non-statement (ignored): {result['non_statement_changed_lines']}")
    print(f"Real changed statements: {result['total_changed_statements']}")
    print(f"Covered: {len(result['covered_changed_lines'])} -> {result['covered_changed_lines']}")
    print(f"UNCOVERED (debt): {len(result['uncovered_changed_lines'])} -> {result['uncovered_changed_lines']}")
    print(f"Debt ratio: {result['debt_ratio']*100:.1f}% of changed *statements* have no test coverage")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python audit/test_debt.py <before_file> <after_file> <test_dir>")
        sys.exit(1)

    before_path, after_path, test_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    result = compute_test_debt(before_path, after_path, test_dir)
    print_report(result)

    out_path = "traces/test_debt_report.json"
    os.makedirs("traces", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nStructured report written to {out_path}")