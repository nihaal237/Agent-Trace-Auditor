import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.schema import TraceEvent
from storage.trace_store import TraceStore

store = TraceStore(db_path="traces/traces.db")

session = "session_001"
events = [
    TraceEvent(session_id=session, step=1, action="plan",
               reasoning="Fix restock() to cap stock at max_capacity (BUG_B)."),
    TraceEvent(session_id=session, step=2, action="edit_file", file="inventory.py",
               reasoning="Clamp stock to max_capacity in restock().",
               diff="- item.stock += quantity\n+ item.stock = min(item.stock + quantity, item.max_capacity)"),
    TraceEvent(session_id=session, step=3, action="run_tests",
               test_result="fail", tests_passed=4, tests_failed=1,
               failing_tests="test_apply_discount_rounds_correctly",
               test_output="1 failed (apply_discount rounding), 4 passed"),
    TraceEvent(session_id=session, step=4, action="plan",
               reasoning="Now fix apply_discount() truncation (BUG_A)."),
    TraceEvent(session_id=session, step=5, action="edit_file", file="inventory.py",
               reasoning="Round instead of truncate, and simplify is_free check while I'm here.",
               diff="- truncated = int(discounted * 100) / 100\n+ truncated = round(discounted, 2)\n- return item.price == 0\n+ return round(item.price, 2) <= 0"),
    TraceEvent(session_id=session, step=6, action="run_tests",
               test_result="fail", tests_passed=4, tests_failed=1,
               failing_tests="test_free_sample_checkout_is_zero",
               test_output="1 failed (free_sample_checkout_is_zero), 4 passed  <- REGRESSION introduced at step 5"),
]

for e in events:
    store.log(e)

retrieved = store.get_session(session)
print(f"Stored and retrieved {len(retrieved)} events")
for r in retrieved:
    print(f"  step {r['step']}: {r['action']} | test_result={r['test_result']} | failing={r['failing_tests']}")

print("Sessions in DB:", store.list_sessions())
store.close()