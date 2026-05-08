---
name: add-coach-tool
description: Add a new function-calling tool to garmin_coach/coach_tools.py — wires handler, HANDLERS entry, TOOLS_SPEC schema entry, SYSTEM_PROMPT mention, and a test block. Use when the user wants to extend the LLM's MCP-style toolset.
---

# add-coach-tool

Adds a new tool to the coach's function-calling toolkit. Hitting all five touch points by hand is error-prone — this skill walks through them in order so nothing is forgotten.

## When to use

User says one of:
- "add a tool to the coach"
- "expose <something> to the LLM"
- "let the model query <X>"
- invokes `/add-coach-tool <name>`

## Five touch points (must hit ALL)

A coach tool is fully wired only when it appears in:

1. **Handler function** in `garmin_coach/coach_tools.py` — pure Python, returns JSON-serializable dict/list.
2. **`HANDLERS` registry** in same file — `"name": handler_fn`.
3. **`TOOLS_SPEC` schema** in same file — JSON Schema for Groq.
4. **`SYSTEM_PROMPT` HERRAMIENTAS section** in `garmin_coach/coach.py` — one line telling the model when to use it.
5. **Tests** in `garmin_coach/tests/test_coach_tools.py` — cover happy path, edge cases, registry presence.

If any are missing, the model either can't see the tool, sees it but can't call it, or calls it and gets a runtime error.

## Procedure

### Step 1: Gather inputs

Ask the user (or infer from request):
- Tool name (snake_case, e.g. `get_strength_history`).
- One-sentence description of what it returns.
- Argument names + types (or "no args").
- Source: which TinyDB table, which `slim_*` projection.
- Cap: max records returned (default 25, mirror `MAX_ACTIVITIES_RESULT`).

### Step 2: Write the handler

Add to `garmin_coach/coach_tools.py` near related handlers. Pattern:

```python
def get_strength_history(days: int = DEFAULT_WINDOW_DAYS, limit: int = MAX_ACTIVITIES_RESULT) -> list[dict]:
    cutoff = _cutoff(days)
    Q = Query()
    rows = (
        get_db()
        .table("activities")
        .search(Q.startTimeLocal.test(lambda v: bool(v) and v >= cutoff))
    )
    rows = [a for a in rows if _activity_type_key(a) in {"strength_training", "indoor_strength_training"}]
    rows.sort(key=lambda a: a.get("startTimeLocal", ""), reverse=True)
    cap = max(1, min(int(limit), MAX_ACTIVITIES_RESULT))
    return [slim_activity(a) for a in rows[:cap]]
```

Reuse helpers: `_cutoff(days)`, `_activity_type_key(act)`, `_date_window(table, days, slimmer)`, `_latest(table)`. Import any new `slim_*` from `context_builder`.

### Step 3: Register in `HANDLERS`

```python
HANDLERS: dict[str, Callable[..., Any]] = {
    ...,
    "get_strength_history": get_strength_history,
}
```

### Step 4: Add `TOOLS_SPEC` entry

```python
{
    "type": "function",
    "function": {
        "name": "get_strength_history",
        "description": "Devuelve sesiones de fuerza recientes (strength_training, indoor_strength_training) ordenadas por fecha.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Default 7, max 90."},
                "limit": {"type": "integer", "description": "Cap interno 25."},
            },
        },
    },
},
```

Keep description in Spanish — system prompt is Spanish, model picks up tone.

### Step 5: Mention in `SYSTEM_PROMPT`

In `garmin_coach/coach.py`, inside the "HERRAMIENTAS (function calling)" block, add one bullet:

```
- `get_strength_history` para listar sesiones de fuerza recientes (strength_training, indoor_strength_training).
```

Place near related tools (activity-listing tools together, recovery windows together, etc.).

### Step 6: Tests

Append to `garmin_coach/tests/test_coach_tools.py`. Always include:

- Happy path with realistic fixture.
- Filter edge case (e.g. wrong type ignored).
- Empty DB returns `[]` or `None`.
- Registry presence: `assert "get_strength_history" in ct.HANDLERS` and in `TOOLS_SPEC` names.

```python
def test_strength_history_filters_by_type():
    db_inst = _make_db()
    db_inst.table("activities").insert(_activity("a", start=_today(1), type_key="strength_training"))
    db_inst.table("activities").insert(_activity("b", start=_today(2), type_key="running"))
    with _patch_db(db_inst):
        results = ct.get_strength_history(days=30)
    assert [r["activityId"] for r in results] == ["a"]


def test_strength_history_registered():
    assert "get_strength_history" in ct.HANDLERS
    spec_names = {t["function"]["name"] for t in ct.TOOLS_SPEC}
    assert "get_strength_history" in spec_names
```

### Step 7: Verify

Run:
```bash
source .venv/bin/activate
python -m pytest garmin_coach/tests/test_coach_tools.py -v
ruff check garmin_coach/coach.py garmin_coach/coach_tools.py
```

Confirm cov ≥85%:
```bash
python -m pytest garmin_coach/tests/ --cov=garmin_coach
```

### Step 8: Document

Per CLAUDE.md, every new feature gets a `docs/implementations/<feature>.md`. Either invoke the `docs-implementation-writer` skill or write a short doc covering: motivation, handler signature, schema, prompt change, tests added.

## Defensive defaults

- Always cap inputs (`days`, `limit`) — the LLM may pass huge values.
- Wrap nothing in try/except inside the handler — `dispatch_tool_call` already catches `TypeError` (bad args) and `Exception` (crashes). Crashing is fine.
- Don't return raw TinyDB records — always project through a `slim_*`.
- Fields named in the description must exist in the slim projection. If you reference `pace_min_per_km` in description, slim_activity better produce it.

## Anti-patterns to refuse

- Tool that mutates state (writes to DB). Tools are read-only by convention. If user wants to write, push back.
- Tool that takes arbitrary SQL/JSON-path. LLM will inject. Use named filters.
- Tool that returns >100 records without a cap.
- Tool with overlapping responsibility (e.g. "get_recent_activities_v2"). Extend the existing one with a parameter instead.
