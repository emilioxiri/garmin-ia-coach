---
name: docs-implementation-writer
description: Generate a docs/implementations/<feature>.md write-up for a finished change in the garmin-coach repo. Use when the user finishes a feature/bugfix and asks to document it, or invokes /docs-implementation-writer.
---

# docs-implementation-writer

CLAUDE.md mandates documenting every implementation/bugfix under
`docs/implementations/`. This skill produces a consistent write-up.

## When to use

After a feature, bug fix, or refactor lands. Triggered by phrases like
"document this", "escribe el doc", "implementación lista".

## Inputs

- Feature/fix slug (snake_case) → filename `docs/implementations/<slug>.md`.
- Recent diff: derive from `git diff` against the base branch or last commit.

## Output template

```markdown
# <Title>

## Contexto / problema
<Why the change was needed. Reference user-visible symptom, error, or spec.>

## Solución
<High-level approach. One paragraph.>

## Archivos tocados
- `path/file.py` — <what changed>
- ...

## Detalles técnicos
<Key invariants, edge cases, concurrency/threading notes, schema impact.>

## Tests
- `garmin_coach/tests/test_*.py::<test_name>` — <what it covers>
- Coverage delta: <before → after>

## Notas operativas
<Migration steps, env vars, scheduler/Docker impact if any. Omit if none.>
```

## Steps

1. Run `git diff --stat` and `git log -n 5 --oneline` to gather context.
2. Inspect changed files to summarise behaviour, not just surface diffs.
3. Write the document at `docs/implementations/<slug>.md`. Do not overwrite
   existing files without confirmation.
4. If the change updates the active spec list, also update CLAUDE.md's
   `## Implemented` section with a one-line entry pointing at the new doc.
5. Keep it Spanish-first to match existing docs (see other files in
   `docs/implementations/`).

## Constraints

- Never document hypothetical work — only what is actually in the diff.
- No bullet-padding: omit sections that don't apply.
