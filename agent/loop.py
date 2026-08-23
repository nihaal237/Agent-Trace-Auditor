"""
Agent loop: plan -> edit -> test -> retry.

Every action is logged to the TraceStore as it happens - this is the
deterministic audit trail. The LLM only decides *what* to change; the
executor (real pytest subprocess) is the sole source of truth for
whether it worked.
"""

import sys
import os
import json
import difflib
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.schema import TraceEvent
from storage.trace_store import TraceStore
from agent.llm_client import query_llm
from agent.executor import run_tests

SYSTEM_PROMPT = (
    "You are a careful software engineer fixing bugs in a small Python file. "
    "You will be shown the full current file content, the list of currently "
    "failing tests, and the pytest output.\n\n"
    "Respond ONLY with a JSON object, no markdown fences, no text outside the JSON:\n"
    "{\n"
    '  "reasoning": "<one or two sentences on what you changed and why>",\n'
    '  "new_file_content": "<the FULL corrected file content>"\n'
    "}\n\n"
    "Rules:\n"
    "- Return the COMPLETE file content in new_file_content, not a diff or partial snippet.\n"
    "- Make the smallest change that fixes the failing tests.\n"
    "- Do not remove or alter unrelated working code."
)


def build_user_prompt(file_content: str, failing_tests: list, test_output: str) -> str:
    lines = []
    lines.append("Current file content:")
    lines.append("```")
    lines.append(file_content)
    lines.append("```")
    lines.append("")
    lines.append("Failing tests: " + str(failing_tests))
    lines.append("")
    lines.append("Pytest output:")
    lines.append("```")
    lines.append(test_output)
    lines.append("```")
    lines.append("")
    lines.append("Fix the failing tests.")
    return "\n".join(lines)


def parse_llm_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def run_agent_session(task_dir: str, target_file: str, max_attempts: int = 5,
                       model: str = "openai/gpt-oss-20b", db_path: str = "traces/traces.db"):
    session_id = "session_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    store = TraceStore(db_path=db_path)
    target_path = os.path.join(task_dir, target_file)
    step = 1

    print(f"=== Starting session {session_id} ===")

    baseline = run_tests(task_dir)
    store.log(TraceEvent(
        session_id=session_id, step=step, action="run_tests",
        test_result="pass" if baseline["all_pass"] else "fail",
        test_output=baseline["output"][-2000:],
        tests_passed=baseline["tests_passed"], tests_failed=baseline["tests_failed"],
        failing_tests=",".join(baseline["failing_tests"]),
    ))
    print(f"[step {step}] baseline: {baseline['tests_passed']} passed, "
          f"{baseline['tests_failed']} failed -> {baseline['failing_tests']}")
    step += 1

    if baseline["all_pass"]:
        print("Nothing to fix - all tests already pass.")
        store.close()
        return session_id

    last_result = baseline

    for attempt in range(1, max_attempts + 1):
        print(f"\n--- Attempt {attempt}/{max_attempts} ---")

        with open(target_path) as f:
            current_content = f.read()

        user_prompt = build_user_prompt(
            current_content, last_result["failing_tests"], last_result["output"]
        )

        try:
            raw = query_llm(SYSTEM_PROMPT, user_prompt, model=model)
            parsed = parse_llm_response(raw)
            reasoning = parsed["reasoning"]
            new_content = parsed["new_file_content"]
        except Exception as e:
            store.log(TraceEvent(
                session_id=session_id, step=step, action="parse_error",
                reasoning=f"Failed to parse LLM response: {e}",
            ))
            print(f"[step {step}] PARSE ERROR: {e}")
            step += 1
            continue

        store.log(TraceEvent(
            session_id=session_id, step=step, action="plan",
            reasoning=reasoning,
        ))
        print(f"[step {step}] plan: {reasoning}")
        step += 1

        diff_text = "\n".join(difflib.unified_diff(
            current_content.splitlines(), new_content.splitlines(),
            fromfile="before", tofile="after", lineterm=""
        ))

        with open(target_path, "w") as f:
            f.write(new_content)

        store.log(TraceEvent(
            session_id=session_id, step=step, action="edit_file",
            file=target_file, reasoning=reasoning, diff=diff_text,
        ))
        print(f"[step {step}] edit_file: {target_file}")
        step += 1

        result = run_tests(task_dir)
        store.log(TraceEvent(
            session_id=session_id, step=step, action="run_tests",
            test_result="pass" if result["all_pass"] else "fail",
            test_output=result["output"][-2000:],
            tests_passed=result["tests_passed"], tests_failed=result["tests_failed"],
            failing_tests=",".join(result["failing_tests"]),
        ))
        print(f"[step {step}] run_tests: {result['tests_passed']} passed, "
              f"{result['tests_failed']} failed -> {result['failing_tests']}")
        step += 1

        if result["all_pass"]:
            store.log(TraceEvent(
                session_id=session_id, step=step, action="success",
                reasoning=f"All tests passing after {attempt} attempt(s).",
            ))
            print(f"\nSUCCESS after {attempt} attempt(s). Session: {session_id}")
            store.close()
            return session_id

        last_result = result

    store.log(TraceEvent(
        session_id=session_id, step=step, action="give_up",
        reasoning=f"Did not pass all tests within {max_attempts} attempts.",
        failing_tests=",".join(last_result["failing_tests"]),
    ))
    print(f"\nGAVE UP after {max_attempts} attempts. Session: {session_id}")
    store.close()
    return session_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_dir", default="sample_tasks/fix_inventory_bugs")
    parser.add_argument("--target_file", default="inventory.py")
    parser.add_argument("--max_attempts", type=int, default=5)
    parser.add_argument("--model", default="openai/gpt-oss-20b")
    args = parser.parse_args()

    run_agent_session(args.task_dir, args.target_file, args.max_attempts, args.model)