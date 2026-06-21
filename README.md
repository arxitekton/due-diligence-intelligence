# due-diligence-intelligence

Home of **`company-due-diligence`** — a Claude Code skill for enterprise-grade company
intelligence, due diligence, and market research.

It's a reusable, refreshable, **versioned research-corpus system** (not a one-shot report
generator): it discovers and preserves primary sources, extracts artifacts with full provenance
lineage, validates them against evidentiary gates, and renders a cited dossier — then on every
re-run detects and logs what changed.

## Layout

| Path | What it is |
|------|-----------|
| [`company-due-diligence/`](company-due-diligence/) | The skill: `SKILL.md`, engine (`cdd/`), schemas, prompts, references, CLIs, examples |
| [`company-due-diligence/README.md`](company-due-diligence/README.md) | **Start here** — full documentation, install, workflow, design principles |
| [`docs/superpowers/`](docs/superpowers/) | Design spec and the implementation plans the skill was built from |

## Quick start

```bash
cd company-due-diligence
uv venv && uv pip install -e ".[dev]"
python scripts/install_skill.py --skills-dir ~/.claude/skills   # activate the skill
```

Then **just ask Claude Code** in natural language — the skill auto-activates:

> Do full due diligence on Acme Analytics — corporate structure, financials, products, risks, and sanctions.

See [`company-due-diligence/README.md`](company-due-diligence/README.md) for the full usage guide, run modes, and output layout.
