# CLAUDE.md

## Always Search the web for relevant information (if useful)

## Use Context7 for Up-to-Date Documentation

When working with external libraries, frameworks, or APIs, add **"use context7"** to your prompt to fetch current documentation. This ensures code examples and API usage are accurate and not outdated.

**When to use:**
- Working with ccxt, pandas, numpy, or any trading/data libraries
- Using React, Next.js, or rapidly evolving frameworks
- Unsure about current API syntax or deprecated methods
- Need version-specific code examples

**Example prompts:**
- "How do I fetch OHLCV data with ccxt? use context7"
- "Show me pandas DataFrame filtering syntax use context7"

**When NOT needed:**
- General Python/TypeScript questions
- Working with your own codebase
- Stable, well-documented concepts

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
