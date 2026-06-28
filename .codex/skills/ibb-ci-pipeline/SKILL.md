---
name: ibb-ci-pipeline
description: Defines CI checks for IBB Insurance Portal. Use when editing GitHub Actions, Docker, backend/frontend build scripts, tests, linting, dependency checks, or pre-merge validation.
---

# IBB CI Pipeline Skill

## Purpose

Use this skill to keep the IBB Insurance Portal codebase protected from basic regressions.

CI must run before merge and must fail if lint, tests, build, or secret scanning fails.

The goal is not to create a complex enterprise CI system. The goal is to ensure that MVP code cannot be merged if it is broken, unsafe, or contains secrets.

## Required Knowledge Base

Before changing CI checks for this repo, read `docs/knowledge-base/index.md` and keep automated checks aligned with the project safety rules documented there.

## Required backend checks

For the FastAPI backend, CI must run:

```bash
ruff check .
pytest
docker build -t ibb-backend-test .
```

If configured, also run one of:

```bash
mypy .
```

or:

```bash
pyright
```

## Required frontend checks

For the Next.js frontend, CI must run:

```bash
npm run lint
npm run typecheck
npm run build
```

If frontend tests exist, run:

```bash
npm test
```

or:

```bash
npm run test
```

## Secret scanning

CI must run a secret scan.

Recommended tool:

```bash
gitleaks detect --source .
```

CI must fail if real secrets are found.

Forbidden in repository:

- `.env`;
- Bitrix24 webhook URL;
- Bitrix24 access token;
- database password;
- Redis password;
- JWT secret;
- SMTP password;
- cookie secret;
- reset token;
- one-time login token;
- private keys.

Allowed:

- `.env.example` with placeholder values only.

## Dependency checks

Recommended but not always blocking for MVP:

Backend:

```bash
pip-audit
```

or equivalent.

Frontend:

```bash
npm audit --audit-level=high
```

If dependency audit creates too many false positives, document exceptions explicitly.

## CI workflow minimum

A minimal CI pipeline must include:

1. checkout repository;
2. install backend dependencies;
3. run backend lint;
4. run backend tests;
5. build backend Docker image;
6. install frontend dependencies;
7. run frontend lint;
8. run frontend typecheck;
9. run frontend build;
10. run secret scanning.

## Merge rule

Do not merge if:

- backend lint fails;
- backend tests fail;
- backend build fails;
- frontend lint fails;
- frontend typecheck fails;
- frontend build fails;
- secret scan finds secrets.

## Pull request checks

Every pull request must show:

- CI status;
- failed step, if any;
- no secrets detected;
- no unsafe `.env` files committed.

## Anti-patterns

Do not disable failing checks just to merge.

Do not commit real `.env`.

Do not skip frontend build because "only backend changed" unless path-based CI is already reliable.

Do not treat secret scanning as optional.

Do not put tokens into workflow files.

Use GitHub Actions secrets or the equivalent secure CI secret storage.

## Acceptance criteria

This skill is satisfied when:

- CI runs on pull requests;
- backend lint/test/build are checked;
- frontend lint/typecheck/build are checked;
- secret scanning is enabled;
- real secrets are not stored in repository;
- CI fails on unsafe or broken code.
