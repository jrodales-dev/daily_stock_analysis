# AGENTS.md

This file is used to constrain the default development workflow in this repository. The goal is to reduce repetitive communication, minimize rework, and keep changes consistent with the current project structure.

If this file is inconsistent with the scripts, workflows, or current code state in the repository, the actual executable content takes precedence. Please fix the documentation along with relevant changes to prevent further rule drift.

## 1. Hard Rules

- Follow existing directory boundaries:
  - Backend logic should preferably be placed in `src/`, `data_provider/`, `api/`, `bot/`.
  - Web frontend changes go in `apps/dsa-web/`.
  - Desktop app changes go in `apps/dsa-desktop/`.
  - Deployment and pipeline changes go in `scripts/`, `.github/workflows/`, `docker/`.
- Do not execute `git commit`, `git tag`, or `git push` without explicit confirmation.
- Use English for commit messages, and do not add `Co-Authored-By`.
- Do not hardcode secrets, accounts, paths, model names, ports, or environment-specific logic.
- Prefer reusing existing modules, configuration entries, scripts, and tests. Do not add parallel implementations.
- Stability is prioritized over "casual optimizations" by default; refrain from refactoring, abstraction, and infrastructure migration that are not directly required by the current task.
- When adding configuration items, you must synchronously update `.env.example` and related documentation.
- When changing user-visible capabilities, CLI/API behavior, deployment methods, notification methods, or report structure, you must synchronously update related documentation and `docs/CHANGELOG.md`.
- The `[Unreleased]` section of `docs/CHANGELOG.md` must use a **flat format**: each item on an independent line, formatted as `- [Type] Description`. Allowed types: `feat`/`improve`/`fix`/`docs`/`test`/`chore`. **Do not add new `### Category Headings` within `[Unreleased]`** to reduce merge conflicts in concurrent PRs. When releasing, the maintainer will aggregate and format them with headings.
- `README.md` is strictly for project positioning, core capability overview, quick start, primary entry points, sponsorship/cooperation, and other homepage-level info. Do not update README unnecessarily to prevent it from bloating.
- For finer module behaviors, UI interactions, specific configurations, troubleshooting, field contracts, implementation semantics, and boundary conditions, prioritize updating corresponding `docs/*.md` or specific documentation instead of the README.
- When modifying one of the bilingual documents (Chinese/English), evaluate whether the other needs to be synchronized; if not synced, state the reason in the delivery notes.
- Comments, docstrings, and log texts should be clear and accurate. English is not strictly required but should be consistent with the context of the file.

## 1.1 PR Title Guidelines (Non-blocking suggestions)

- It is recommended to use `<type>: <description>` for PR titles, e.g., `fix: fix the loss of historical market analysis records`. Preferred types are `fix`/`feat`/`refactor`/`docs`/`chore`/`test`/`ci`.
- Titles should describe the actual changes. Avoid adding tool/agent source prefixes like `[codex]`, `codex`, `autocode`, `copilot`, etc.
- This guideline is only for collaboration readability and consistency prompts and should not be used as a standalone review process blocker.

## 2. AI Collaboration Asset Governance

- `AGENTS.md` is the single source of truth for AI collaboration rules in the repository.
- `CLAUDE.md` must be a symlink pointing to `AGENTS.md` for compatibility with the Claude ecosystem.
- `.github/copilot-instructions.md` and `.github/instructions/*.instructions.md` are mirrors or layered supplements for GitHub Copilot / Coding Agents; if they conflict with this file, `AGENTS.md` prevails.
- Repository collaboration skills are stored in `.claude/skills/`, and analysis artifacts are stored in `.claude/reviews/`; the former can be committed, the latter is treated as a local artifact by default.
- The root `SKILL.md` and `docs/openclaw-skill-integration.md` are product or external integration descriptions, not the source of truth for repository collaboration rules.
- If `.agents/skills/` or other agent-specific directories are added in the future, a single source of truth must be clearly established first, then synced via scripts or mirrors; manually maintaining multiple synonymous contents long-term is prohibited.
- When modifying AI collaboration governance assets, execute:

```bash
python scripts/check_ai_assets.py
```

## 3. Repository Quick Glance

- Project Positioning: Intelligent stock analysis system covering A-shares, Hong Kong stocks, and US stocks.
- Main Workflow: Fetch Data -> Technical Analysis/News Retrieval -> LLM Analysis -> Generate Report -> Push Notification.
- Key Entry Points:
  - `main.py`: Main entry for analysis tasks
  - `server.py`: FastAPI service entry
  - `apps/dsa-web/`: Web Frontend
  - `apps/dsa-desktop/`: Electron Desktop App
  - `.github/workflows/`: CI, Release, Daily Tasks
- Core Responsibilities:
  - `src/core/`: Main workflow orchestration
  - `src/services/`: Business service layer
  - `src/repositories/`: Data access layer
  - `src/reports/`: Report generation
  - `src/schemas/`: Schema / Data structures
  - `data_provider/`: Multi-datasource adaptation and fallback
  - `api/`: FastAPI API
  - `bot/`: Bot integration
  - `scripts/`: Local scripts
  - `.github/scripts/`: GitHub automation scripts
  - `tests/`: pytest tests
  - `docs/`: Documentation and instructions

## 4. Common Commands

### Run Application

```bash
python main.py
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Backend Verification

```bash
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh
python -m pytest -m "not network"
python -m py_compile <changed_python_files>
```

### Web / Desktop

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build

cd ../dsa-desktop
npm install
npm run build
```

### PR / CI Evidence

```bash
gh pr view <pr_number>
gh pr checks <pr_number>
gh run view <run_id> --log-failed
```

## 5. Default Workflow

1. First, determine the task type: `fix / feat / refactor / docs / chore / test / review`
2. Read existing implementations, configurations, tests, scripts, workflows, and documentation before making changes.
3. Identify change boundaries: Backend / API / Web / Desktop / Workflow / Docs / AI Collaboration Assets.
4. First, determine if it hits high-risk areas: Configuration semantics, API / Schema, datasource fallback, report structure, authentication, scheduling, release process, desktop startup chain.
5. Only make the minimal changes directly related to the current task. Do not sneak in unrelated refactorings.
6. If you find discrepancies between documentation, scripts, and workflows, trust the actual code and workflows first, then decide whether to conveniently fix the documentation.
7. After making changes, execute checks according to the verification matrix below.
8. Final delivery must state by default:
   - What was changed
   - Why it was changed
   - Verification status
   - Unverified items
   - Risk points
   - Rollback method

## 6. Verification Matrix

### CI Coverage Principles

The current repository CI mainly includes:

| Check Item | Source | Description | Blocking |
| --- | --- | --- | --- |
| `ai-governance` | `.github/workflows/ci.yml` | Validate `AGENTS.md` / `CLAUDE.md` / `.github` instructions / `.claude/skills` relationships | Yes |
| `backend-gate` | `.github/workflows/ci.yml` | Execute `./scripts/ci_gate.sh` | Yes |
| `docker-build` | `.github/workflows/ci.yml` | Docker build and key module import smoke test | Yes |
| `web-gate` | `.github/workflows/ci.yml` | Execute `npm run lint` + `npm run build` when frontend changes | Yes (when triggered) |
| `network-smoke` | `.github/workflows/network-smoke.yml` | `pytest -m network` + `scripts/test.sh quick` | No, observational |
| `pr-review` | `.github/workflows/pr-review.yml` | PR static check + AI review + auto labeling | No, supplementary |

If CI results already exist on the PR, you can directly reference the CI conclusion. If CI does not cover the change surface, or the local environment differs significantly from the CI environment, you need to supplement the explanation with local verification and gaps.

### Execute by Change Surface

- Python Backend Changes:
  - Scope: `main.py`, `src/`, `data_provider/`, `api/`, `bot/`, `tests/`
  - Priority execution: `./scripts/ci_gate.sh`
  - Minimum requirement: `python -m py_compile <changed_python_files>`
  - If affecting API, task orchestration, report generation, notification sending, datasource fallback, authentication, or scheduling, the delivery notes must state whether the corresponding paths were covered.

- Web Frontend Changes:
  - Scope: `apps/dsa-web/`
  - Default execution: `cd apps/dsa-web && npm ci && npm run lint && npm run build`
  - If involving API integration, routing, state management, Markdown/chart rendering, or authentication state, delivery notes must explicitly state the linkage surface and uncovered risks.

- Desktop App Changes:
  - Scope: `apps/dsa-desktop/`, `scripts/run-desktop.ps1`, `scripts/build-desktop*.ps1`, `scripts/build-*.sh`, `docs/desktop-package.md`
  - Default execution: Build Web first, then build Desktop
  - If unable to fully verify due to platform restrictions, explicitly state whether Web build artifacts, Electron builds, and Release workflow impacts were verified.

- API / Schema / Authentication Linkage Changes:
  - Scope: `api/**`, `src/schemas/**`, `src/services/**`, `apps/dsa-web/**`, `apps/dsa-desktop/**`
  - At least cover corresponding backend verification + affected client build verification.
  - If involving login, Cookie, session, polling state, field addition/deletion, or enum changes, compatibility impacts must be explicitly stated.

- Documentation and Governance File Changes:
  - Scope: `README.md`, `docs/**`, `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/**`, `.claude/skills/**`
  - Code tests are not mandatory.
  - Must confirm commands, configuration items, filenames, and workflow names are consistent with the actual repository.
  - When modifying AI collaboration governance assets, execute `python scripts/check_ai_assets.py`.

- Workflow / Scripts / Docker Changes:
  - Scope: `.github/**`, `scripts/**`, `docker/**`
  - Run the local verification closest to the change surface.
  - On delivery, state which pipeline, release path, or deployment path was affected.
  - If Docker / GitHub Actions related verifications were not executed, explicitly state the reason and potential risks.

- Network or Third-Party Dependency Changes:
  - Run offline or deterministic checks first.
  - Priority confirm whether timeout, retry, fallback, exception messages, and degradation paths still hold.
  - If online verification was not executed, the reason must be explicitly stated.

## 7. Stability Guardrails

- Configuration and Run Entries:
  - When modifying `.env` semantics, default values, CLI parameters, service startup methods, or scheduling semantics, simultaneously evaluate the impact on local runs, Docker, GitHub Actions, API, Web, and Desktop.
  - New configurations should preferably be "runnable without configuration, enhanced capability with configuration", avoiding stacked switches and mutually exclusive modes.

- Data Sources and Fallback:
  - When modifying `data_provider/`, pay attention to datasource priorities, failure degradation, field standardization, caching, and timeout strategies.
  - A single datasource failure should not drag down the entire analysis process unless the requirement explicitly demands fail-fast.

- API / Web / Desktop Compatibility:
  - When modifying API / Schema / Authentication / Report payloads, simultaneously check the compatibility of backend, Web, and Desktop.
  - Default to appending fields, keeping old fields, or providing a compatibility layer, avoiding silently breaking existing clients.

- Reports / Prompts / Notifications:
  - When modifying report structures, Prompts, extractors, notification templates, or bot links, check if upstream inputs and downstream consumers are still compatible.
  - A single notification channel failure should not drag down the entire main analysis process unless the requirement explicitly demands fail-fast.
  - When modifying `EXTRACT_PROMPT` in `src/services/image_stock_extractor.py`, attach the complete new prompt in the PR description.

- Workflows / Release / Packaging:
  - When modifying auto-tag, Release, Docker publishing, daily analysis, or desktop packaging processes, evaluate trigger conditions, artifact paths, permission boundaries, and rollback methods.
  - Auto-tagging remains opt-in by default: only when the commit title contains `#patch`, `#minor`, or `#major` will it trigger a version number update, unless requirements explicitly demand a change in release strategy.

## 8. Issue / PR / Skill Workflow

- The repository already has the following skills, prioritize reusing them:
  - `.claude/skills/analyze-issue/SKILL.md`
  - `.claude/skills/analyze-pr/SKILL.md`
  - `.claude/skills/fix-issue/SKILL.md`
- If the task is explicitly issue analysis, PR review, or issue fixing, prioritize executing according to the corresponding skill and save artifacts to `.claude/reviews/`.
- Commands, templates, verification sequences, and delivery structures in skills must remain consistent with `AGENTS.md`.
- Skills default to prioritizing reading CI / workflow evidence before deciding whether to supplement with local verification.
- Skills must not default to executing `git pull`, `git push`, `git tag`, `gh pr create` or operations that change the remote or current branch state; these operations require user confirmation.
- Default PR review sequence:
  1. Necessity
  2. Relevance
  3. Title suggestion (`<type>: <description>`, no tool/agent prefix; not a hard blocking item)
  4. Description completeness (against `.github/PULL_REQUEST_TEMPLATE.md`)
  5. Verification evidence
  6. Implementation correctness
  7. Merge determination
- For `fix` PRs, must state: original problem, root cause, fix point, regression risk.
- Merge blocking conditions:
  - Correctness or safety issues
  - Blocking CI failed
  - PR description substantively contradicts actual changes
  - Missing rollback plan

## 9. Delivery and Release

- Default delivery structure:
  - `What was changed`
  - `Why it was changed`
  - `Verification status`
  - `Unverified items`
  - `Risk points`
  - `Rollback method`
- If it's a `docs` task, you can directly write: `Docs only, tests not run`, but still need to state whether commands and filenames were checked.
- Auto-tag does not trigger by default; only commit titles containing `#patch`, `#minor`, or `#major` will trigger version number updates.
- Manual tagging must use annotated tags.
- User-visible changes should preferably be merged via PR, supplementing labels and verification notes.
