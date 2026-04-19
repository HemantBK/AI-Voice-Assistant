# Contributing

Thanks for considering a contribution. This project is small and opinionated — here's what we expect.

## Ground rules

1. **Design doc before code for non-trivial changes.** Anything that changes a WS protocol, adds a phase, or introduces a new service: start with a design doc in `docs/design/<slug>.md` using [`docs/design-doc-template.md`](docs/design-doc-template.md). Open the doc as a PR first, get review, then write code.
2. **Every perf/quality claim ships with numbers.** If your PR says "faster" or "more accurate," the description must include before/after output from the eval harness.
3. **Small, reversible commits.** Each phase in this repo is independently revertible. Keep that property.
4. **Tests pass, lint clean.** See [Local checks](#local-checks).
5. **No pointless abstractions.** Don't introduce a base class for one implementation.

## Setting up locally

```bash
git clone <this repo>
cd <repo>

# Backend
cd backend
python -m venv .venv && . .venv/Scripts/activate    # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Frontend
cd ../frontend
npm ci

# Ollama (one-time)
ollama pull qwen2.5:3b
```

## Local checks

Before opening a PR, run:

```bash
# Backend
cd backend
ruff check .
pytest tests -q

# Frontend
cd frontend
npx eslint src
npm run build

# Eval harness self-test (stdlib only)
cd ..
python -m eval.runners.eval_llm --limit 3
```

CI will run the same matrix on Linux Python 3.11 + 3.12 and Node 20.

## Commit messages

Conventional Commits. Examples:

- `feat(streaming): add sentence-level TTS streaming`
- `fix(vad): avoid false speech_start on 40ms bursts`
- `docs(adr): add 0003 for observability migration`
- `refactor(llm): split providers into llm/ package`
- `test(splitter): cover abbreviation edge cases`
- `chore(ci): add coverage reporting`

Breaking changes: include `BREAKING CHANGE:` in the body + note in PR description.

## PR checklist

- [ ] Linked issue or design doc.
- [ ] Tests added or updated.
- [ ] Eval harness numbers included if relevant.
- [ ] CHANGELOG entry in the `## Unreleased` section.
- [ ] README / ARCHITECTURE / phase-notes updated if behavior changed.
- [ ] Ran locally — CI is a safety net, not a test driver.

## Scope of PRs we'll say yes to

- Bug fixes with reproduction steps.
- A new LLM or TTS provider with a working eval run.
- Smaller, measurable latency wins in the streaming pipeline.
- Docs that fix ambiguity or add missing context.
- New language fixtures for the STT eval.

## Scope we'll push back on

- Rewrites without a design doc.
- Adding a heavy dependency (LangChain, Transformers, etc.) without strong justification.
- New features without tests or eval numbers.
- Cosmetic-only style changes; run `ruff format` in a separate PR.

## Code of conduct

Be kind. Assume good faith. No harassment, slurs, or bad-faith arguments. Maintainers may close/lock PRs that don't follow this without further discussion.

## Questions

Open a GitHub Discussion or Issue with the `question` label. For security issues, see [SECURITY.md](SECURITY.md) — do **not** file a public issue.
