# Shared-laptop collaboration

One repository: deveshsinghal09/ecoroute-ai. Collaborators requested: Mayank2142 and DEVESH859.
Inviting collaborators does not make them commit authors or immediately populate GitHub's
Contributors graph. Each person must accept the invitation and make actual contributions.

Contributor email mapping supplied by the user:

| GitHub account | Git author name | Git author email |
|---|---|---|
| Mayank2142 | Mayank Gupta | mayankcoding73@gmail.com |
| DEVESH859 | Devesh Raj | deveshraj003@gmail.com |

Names and email mappings are confirmed by the user. Email ownership/verification in GitHub has
not been independently checked.
The team aims for approximately balanced meaningful contributions. Attribute each session to
its actual contributor and use co-author trailers for joint work; counts need not match exactly.

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

## Confirmed joint session (2026-10-08)

The user confirms all three teammates are working together on this laptop and in this chat.
New joint Phase 1/2 commits keep the configured primary author and include:

```text
Co-authored-by: Mayank Gupta <mayankcoding73@gmail.com>
Co-authored-by: Devesh Raj <deveshraj003@gmail.com>
```

Earlier history is preserved. Co-author credit does not promise equal primary-author commit
counts or immediate inclusion in every GitHub contributors view. Each teammate must associate
and verify their supplied email in their own GitHub account; nobody needs to share passwords.

For this confirmed joint session, stage and review meaningful changes, then use:

```powershell
.\scripts\commit-joint.ps1 -Title 'docs: record verified pipeline results'
```

The helper keeps both co-author lines in one final trailer paragraph. Separate `git commit -m`
arguments introduce blank paragraphs and can cause GitHub to recognize only the final co-author.
GitHub's authors API detected this in commits 7a3bb17/e70742e: Devesh Raj was recognized, while
Mayank's line was outside the parsed trailer block. Those published commits are not rewritten;
the helper fixes subsequent joint attribution. Credits are verified on the next joint commit.
See [GitHub co-author instructions](https://docs.github.com/en/pull-requests/how-tos/commit-changes/creating-a-commit-with-multiple-authors).
