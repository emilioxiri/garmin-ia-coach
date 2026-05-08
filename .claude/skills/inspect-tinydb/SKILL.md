---
name: inspect-tinydb
description: Quick inspection of the runtime TinyDB at /data/garmin_coach.json (or local path). Lists tables, counts rows, peeks records by date / activityId / table without loading the whole JSON. Use when debugging "why does the bot say X about my data" or sanity-checking sync results.
disable-model-invocation: true
---

# inspect-tinydb

Inspect-only access to the production TinyDB. **Never edits.** Useful for:

- "What activities are in DB right now?"
- "Why didn't my latest run get synced?"
- "Show me the latest fitness_metrics record"
- "How many sleep records survived the last purge?"

## When to use

User invokes `/inspect-tinydb` with a sub-command, or asks something like:
- "peek at the database"
- "what's in the activities table"
- "show me the record for activity 12345"
- "count rows per table"

Do NOT use this to mutate state. The block-secrets hook will refuse Edit/Write to `data/garmin_coach.json` anyway.

## Sub-commands

The companion script `scripts/peek.py` accepts these forms:

```bash
# List tables + row counts.
python .claude/skills/inspect-tinydb/scripts/peek.py tables

# Last N records of a table (ordered by date / startTimeLocal desc).
python .claude/skills/inspect-tinydb/scripts/peek.py recent <table> [N]

# One record by id (only `activities` table has ids).
python .claude/skills/inspect-tinydb/scripts/peek.py id <activityId>

# Records on a specific date (YYYY-MM-DD). Activities match startTimeLocal[:10],
# wellness tables match `date` field.
python .claude/skills/inspect-tinydb/scripts/peek.py date <table> <YYYY-MM-DD>

# Latest record across `fitness_metrics`, `race_predictions`, `lactate_threshold`,
# `endurance_score`.
python .claude/skills/inspect-tinydb/scripts/peek.py snapshot
```

## DB path resolution

Default path: `/data/garmin_coach.json` (Docker volume).
If running outside Docker, set `GARMIN_COACH_DB_PATH=./data/garmin_coach.json` before invoking.

## Output format

JSON-pretty per record by default. For the `tables` sub-command, prints `name: count` lines.

When showing slim activity, drop the noisy fields (`splits`, `hrZones`, `summaryDTO`) from output — those bloat the terminal and aren't usually what the user is debugging.

## Anti-patterns

- Don't paste raw record dumps into chat without trimming. Use `slim_activity` from `garmin_coach.context_builder` if the user wants a coach-eye view.
- Don't suggest writes via this skill. If the user needs to fix data, point them to `db.purge_old_data`, `db.save_memory`, or the next sync run.
