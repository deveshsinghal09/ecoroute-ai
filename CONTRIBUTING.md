# Shared-laptop collaboration

One repository: deveshsinghal09/ecoroute-ai. Collaborators requested: Mayank2142 and DEVESH859.
Inviting collaborators does not make them commit authors or immediately populate GitHub's
Contributors graph. Each person must accept the invitation and make actual contributions.

Use separate OS accounts where possible. Before each work session, set repository-local identity:

```powershell
.\scripts\set-author.ps1 -Name 'Your actual name' -Email 'Your verified GitHub or noreply email'
git switch -c feat/short-description
```

Find the correct noreply address in GitHub Settings → Emails; do not guess numeric IDs.
Git author identity and authenticated push identity are distinct. Do not impersonate a friend
to manufacture contributions. Use Co-authored-by trailers only for actual joint work, with each
person's confirmed name/email. This session uses the already-configured Devesh identity.

Commit after meaningful units: design decision, tested feature, fix, validation. Review
`git diff --cached`, run tests and `python scripts/check_repo.py`, then commit a descriptive
message. Avoid empty/churn commits and avoid secrets/real trip data. Prefer pull requests for
later work, no force-push over teammates' commits. CI contains no AWS credentials or deployment.
GitHub Actions private-repository minutes have limits; check Billing before extending CI usage.
