"""
Trace event schema.

Every action the agent takes during a session emits one TraceEvent.
This is the deterministic audit trail: no LLM judgment involved in
recording it, just structured facts about what happened.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional
import time
import json


@dataclass
class TraceEvent:
    session_id: str          # groups events into one agent run
    step: int                # 1-indexed order within the session
    action: str               # e.g. "plan", "edit_file", "run_tests", "give_up"
    file: Optional[str] = None        # file touched, if any
    reasoning: Optional[str] = None   # agent's stated reasoning for this step
    diff: Optional[str] = None        # unified diff of the edit, if any
    test_result: Optional[str] = None # "pass" | "fail" | "error" | None
    test_output: Optional[str] = None # captured pytest output (truncated)
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    failing_tests: Optional[str] = None  # comma-separated test node ids, for run_tests events
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def failing_tests_list(self):
        if not self.failing_tests:
            return []
        return [t.strip() for t in self.failing_tests.split(",") if t.strip()]