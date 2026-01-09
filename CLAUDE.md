# CLAUDE.md

## Always Search the web for relevant information (it mostly is useful)

## Change Documentation (required)

For every change that modifies behavior, adds/removes features, changes dependencies, alters configuration, or impacts performance/security:
- Create **one** new Markdown file under `docs/stories/` in the **same PR/commit** as the code change.

### Filename format
- `docs/stories/YYYYMMddHHmmss-topic-of-the-code-change.md`
- `YYYYMMddHHmmss` is a **14-digit timestamp** (recommend **UTC** to avoid timezone ambiguity).
- `topic-of-the-code-change` is a short **kebab-case** slug (ASCII, no spaces, no underscores).

**Examples**
- `docs/stories/20251228143005-fix-dedup-merge-logic.md`
- `docs/stories/20251228160219-add-address-normalization-step.md`

### Minimum required contents
Each story file must include these sections:

#### Summary
1–3 sentences describing the change.

#### Context / Problem
Why this change is needed (bug, requirement, refactor driver).

#### What Changed
Bulleted list of key implementation changes (include modules/components touched).

#### How to Test
Exact commands and/or manual steps to validate.

#### Risk / Rollback Notes
What could go wrong, and how to revert/mitigate.

### When a story is NOT required
- Pure formatting (whitespace), typo fixes in comments/docs, or non-functional refactors that do not change behavior.
  - If in doubt, create a story.
