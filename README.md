# Agent Trace Auditor

A deterministic audit trail, regression bisector, and test-debt
tracker for a tool-using coding agent.

Most agentic coding tools focus on making the agent *better* at fixing
bugs. This one asks a different question: once an agent has acted, can
you trust and inspect what it did? Every action — plan, edit, test run
— is logged as a structured event, not summarized by the LLM after the
fact. Two tools sit on top of that log:

- **Bisector** — given a regression, walks the trace backward to find
  the exact step that caused it. Same principle as `git bisect`,
  applied to an agent's action log instead of commits.
- **Test debt tracker** — diffs before/after code against real
  `coverage.py` data to report what fraction of *changed statements*
  (not docstrings/comments) have no test coverage.

Both are deterministic by construction: no LLM judgment decides what
counts as a regression or as debt, only recorded facts do.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set a [Groq](https://console.groq.com) API key (free tier, used by the agent loop):

```bash
export GROQ_API_KEY="gsk_..."   # PowerShell: $env:GROQ_API_KEY = "gsk_..."
```

## Components

**`toy_repo/`** — inventory-management library used for the debt-tracker
demo. Includes `apply_bulk_discount()`, a method kept intentionally
untested to show the tracker catching real debt.
```bash
cd toy_repo && python -m pytest tests/ -v && cd ..
```

**`sample_tasks/fix_inventory_bugs/`** — a fresh, reproducible buggy
baseline (3 planted bugs) the agent actually fixes each run, isolated
from `toy_repo/` so results stay reproducible.
```bash
cd sample_tasks/fix_inventory_bugs && python -m pytest tests/ -v && cd ../..
# expect 3 failed, 3 passed
```

**`storage/`** — append-only SQLite trace store. Every step (plan,
edit, test run, success/give-up) is a `TraceEvent`: reasoning, diff,
test results, failing test names, timestamp.
```bash
python storage_test.py
```

**`agent/`** — real plan → edit → test → retry loop against Groq
(`openai/gpt-oss-20b`). The LLM decides *what* to change; a real
`pytest` subprocess is the only source of truth for whether it worked.
```bash
python agent/loop.py
```
*Verified:* fixed all 3 planted bugs in one attempt, full trace logged.

**`audit/bisector.py`** — compares consecutive test runs in a trace;
any newly-failing test gets traced back to the edit step(s) between
the two runs.
```bash
python audit/bisector.py <session_id>
```
*Verified:* correctly isolated a planted regression (an agent "cleaning up"
an unrelated check while fixing a real bug, breaking a different test)
to the exact step, diff, and reasoning — out of a 6-step trace.

**`audit/test_debt.py`** — diffs a before/after file pair against
`coverage.py` execution data; reports the fraction of changed
statements with no test coverage.
```bash
python audit/test_debt.py <before_file> <after_file> <test_dir>
```
*Verified both directions:* 0% debt on a properly-tested fix, 85.7%
debt on `apply_bulk_discount()`'s untested addition.

**`dashboard/app.py`** — Streamlit UI: browse any session's trace,
run the bisector live, run the debt checker against any file pair.
```bash
streamlit run dashboard/app.py
```

## Design principles

- **The executor is the source of truth.** The agent's own claims are
  never trusted directly — every claim is checked against a real
  `pytest` run.
- **Deterministic where it counts.** Regression and debt verdicts come
  from comparing recorded facts, never from LLM judgment.
- **Append-only.** Trace events are never edited, only appended — the
  log reflects what happened, in order.
