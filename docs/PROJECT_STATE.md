# Project state — Phase 0

As of 2026-10-08, India time. Architecture, credential checklist, diagnostics and secure scaffold
are complete. **Stop at Phase 0.** Domain APIs, real data ingestion, trained ML, AWS infrastructure
and wearable integrations remain unimplemented. No paid AWS resource or AWS Budget was created.

## Confirmed user decisions

- One repository under deveshsinghal09, meaningful regular commits from this shared laptop.
- Target city Delhi; nearby region selected as Mumbai ap-south-1 based on service support.
- Free Tier account for this hackathon with **US$100 credits**, user-reported; account balance
  not independently verified. Credit expiry/eligibility, spending approval and cash-spend tolerance
  remain unconfirmed. AWS-native architecture remains the target; no paid provisioning authorized.
- Reported watch: “noie pro 3 alpha”, provisionally Noise ColorFit Pro 3 Alpha; exact hardware/app
  and export capability still need confirmation.
- Collaborators Mayank2142 and DEVESH859; invitations sent with write access. DEVESH859 accepted
  during this session; Mayank2142 pending at last check. Commit authorship must reflect actual work.

## Deliverables / files created

| Group | Files |
|---|---|
| Required living docs | docs/PROJECT_STATE.md, AWS_SERVICES.md, CREDENTIALS_CHECKLIST.md, ARCHITECTURE.md, API_CONTRACT.md |
| Supporting docs | README.md, CONTRIBUTING.md, docs/COSTS_AND_BUDGET.md, docs/VERIFIED_SOURCES.md, ml/README.md |
| Secure config and packages | .gitignore, .gitattributes, .env.example (names only/empty values), pyproject.toml, requirements.lock, package.json, package-lock.json |
| App | src/ecoroute/__init__.py, config.py, main.py |
| Infrastructure scaffold | infra/app.py, cdk.json; no stacks/resources |
| Diagnostics/team scripts | scripts/__init__.py, diagnose.py, check_repo.py, smoke_local.py, set-author.ps1 |
| Tests/CI | tests/test_scaffold.py, tests/test_diagnostics.py, .github/workflows/ci.yml |

Virtual environment, node_modules, CDK output and raw diagnostic JSON are ignored local artifacts.
No secret values, observations, models, tokens or personal trip histories are committed.

## Environment assessment

Python 3.11.0; AWS CLI 2.35.4; Node 22.14.0; npm 10.9.2; Git 2.48.1; Docker CLI 29.2.1.
Docker engine unreachable (stopped), optional for this phase. Project-local CDK CLI 2.1145.0;
aws-cdk-lib 2.272.0. Dependency versions locked after installation and compatibility checks.
Existing default AWS profile points to us-east-1. STS returned InvalidClientTokenId. It was not
modified; credentials are not considered usable. Region opt-in, bootstrap, budget and actual
account quotas therefore remain unverified. Expected account ID and a named SSO login are missing.
All selected service SDK metadata lists Mumbai except geo-routes endpoint enumeration, which is
inconclusive in boto3; official Location documentation separately lists Mumbai support and the
installed SDK contains CalculateRoutes. Metadata support is not proof of account permissions.
OpenAQ, weather and wearable environment keys are absent; no external provider request was made.

## Commands executed and results

Commands ran from the repository unless stated otherwise; no secret command values are recorded.

| Commands / operations | Outcome |
|---|---|
| Tool Get-Command and --version checks; docker version/info | Installed tools found; Docker engine warning |
| aws configure list-profiles; aws configure get region; aws sts get-caller-identity | default/us-east-1 found; STS failed InvalidClientTokenId |
| Official AWS/provider docs browsing; PyPI JSON metadata reads | Completed; evidence and limitations in VERIFIED_SOURCES.md |
| python -m venv .venv; venv pip upgrade; pip install -e '.[dev,infra]'; pip freeze to requirements.lock | Passed |
| npm install --ignore-scripts; npm install --package-lock-only --ignore-scripts | Passed; npm reported 0 vulnerabilities for CLI dependency tree |
| python -m pip check | Passed, no broken requirements |
| python -m pytest -q | **10 passed**, one upstream Starlette/httpx deprecation warning |
| python -m ruff check . | Passed after adding explicit check=False to subprocess.run |
| python scripts/check_repo.py | Passed tracked-file heuristic scan; not a comprehensive secret audit |
| python scripts/diagnose.py --region ap-south-1 --json-out work/diagnostics-offline.json | Exit 0, expected Docker/budget/SDK warnings; cloud reads skipped |
| python scripts/diagnose.py --aws --profile default --region ap-south-1 --json-out work/diagnostics-aws.json | Exit 1 as intended on invalid identity; later account checks stopped |
| Initial npm run synth using cdk synth --no-lookups | Failed because empty app has no stacks; first GitHub CI confirmed same failure |
| Updated npm run synth using Python CDK App.synth and zero-stack assertion | Passed; writes empty assembly only, no AWS resources |
| npm run cdk:version | Passed, CLI 2.1145.0 |
| Initial inline loopback test command | Shell quoting SyntaxError; replaced with maintainable smoke_local.py |
| python scripts/smoke_local.py | Passed actual loopback HTTP 200; temporary server stopped |
| git init/add/commit/push; gh repo create --private | Repository created and commits pushed |
| gh api PUT collaborator for both supplied accounts | Both invitations sent; one accepted at last check |

Repository: https://github.com/deveshsinghal09/ecoroute-ai (private).
Meaningful commits so far: e169b91 architecture, 21f164b credential/cost/team runbooks,
759494f scaffold/diagnostics, fbe3c95 empty-CDK and HTTP smoke verification fix.
The final report/diagnostic improvement is recorded in the next commit.

GitHub Actions rerun **passed** on commit fbe3c95 using Ubuntu/Python 3.11.17:
https://github.com/deveshsinghal09/ecoroute-ai/actions/runs/37817587413 .
It verified locked installs, pip check, lint, 10 tests, loopback smoke check, tracked-file scan
and empty CDK synthesis. This is not Lambda deployment validation.

## Blockers and next-phase gates

1. Configure individual SSO/temp profiles locally, confirm expected account, and rerun read-only
   diagnostics. Do not paste secrets. No account changes/SSO instance creation were attempted here.
2. Choose monthly budget amount and recipient; inspect AWS Credits and Free Tier eligibility.
   $10 gross-usage budget is only a proposal. Budget alerts do not cap spend.
3. For real Delhi observations, obtain OpenAQ key locally and audit station coverage/freshness/license.
4. Confirm exact watch/phone/app and actual export/API ability; no public Noise API verified.
5. Complete collaborator acceptance and use each person's verified/noreply email for their work.
6. Before deployment: implement/test adapters and authorization, review full CDK template, deployment
   IAM, Linux packaging, quotas and exact regional costs, then request spending approval.

Offline Phase 1 can proceed with explicitly labeled fixtures without cloud credentials when the
user starts that phase. Phase 0 deliberately contains no route scoring or ML implementation.
