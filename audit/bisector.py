"""
Bisector: walks a trace backward to find which step introduced a
regression - i.e. caused a test that was previously passing to start
failing.

This is deterministic by construction: it only compares recorded
failing_tests sets between consecutive run_tests events. No LLM
judgment is involved in locating the culprit step, only in explaining
it afterward (optional).
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.trace_store import TraceStore


def find_regressions(session_events: list) -> list:
    """
    Compare consecutive run_tests events. For each newly-failing test
    (present in the later event's failing set but not the earlier
    one's), record which edit_file step(s) happened between the two
    run_tests events - those are the suspects.

    Returns a list of dicts, one per detected regression.
    """
    run_test_events = [e for e in session_events if e["action"] == "run_tests"]
    regressions = []

    for i in range(1, len(run_test_events)):
        prev_run = run_test_events[i - 1]
        curr_run = run_test_events[i]

        prev_failing = set(
            t.strip() for t in (prev_run["failing_tests"] or "").split(",") if t.strip()
        )
        curr_failing = set(
            t.strip() for t in (curr_run["failing_tests"] or "").split(",") if t.strip()
        )

        newly_failing = curr_failing - prev_failing
        if not newly_failing:
            continue

        # find edit_file steps strictly between prev_run['step'] and curr_run['step']
        suspects = [
            e for e in session_events
            if e["action"] == "edit_file"
            and prev_run["step"] < e["step"] < curr_run["step"]
        ]

        regressions.append({
            "newly_failing_tests": sorted(newly_failing),
            "detected_between_steps": [prev_run["step"], curr_run["step"]],
            "suspect_steps": [
                {
                    "step": s["step"],
                    "file": s["file"],
                    "reasoning": s["reasoning"],
                    "diff": s["diff"],
                }
                for s in suspects
            ],
        })

    return regressions


def bisect_session(session_id: str, db_path: str = "traces/traces.db") -> dict:
    store = TraceStore(db_path=db_path)
    events = store.get_session(session_id)
    store.close()

    if not events:
        return {"session_id": session_id, "error": "no events found for this session"}

    regressions = find_regressions(events)

    result = {
        "session_id": session_id,
        "total_steps": len(events),
        "regressions_found": len(regressions),
        "regressions": regressions,
    }
    return result


def print_report(result: dict):
    print(f"\n=== Bisector report: session '{result['session_id']}' ===")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return

    print(f"Total steps in trace: {result['total_steps']}")
    print(f"Regressions found: {result['regressions_found']}\n")

    for idx, reg in enumerate(result["regressions"], start=1):
        print(f"--- Regression #{idx} ---")
        print(f"  Newly failing test(s): {', '.join(reg['newly_failing_tests'])}")
        lo, hi = reg["detected_between_steps"]
        print(f"  Detected between run_tests at step {lo} and step {hi}")
        if not reg["suspect_steps"]:
            print("  No edit_file step found in that window (inconclusive).")
        for s in reg["suspect_steps"]:
            print(f"  SUSPECT -> step {s['step']} (file: {s['file']})")
            print(f"    reasoning at the time: {s['reasoning']}")
            if s["diff"]:
                print(f"    diff:\n{_indent(s['diff'])}")
        print()


def _indent(text: str, spaces: int = 6) -> str:
    pad = " " * spaces
    return "\n".join(pad + line for line in text.splitlines())


if __name__ == "__main__":
    session_id = sys.argv[1] if len(sys.argv) > 1 else "session_001"
    result = bisect_session(session_id)
    print_report(result)

    # also dump structured JSON, for the dashboard later
    out_path = f"traces/{session_id}_bisector_report.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Structured report written to {out_path}")