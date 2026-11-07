# Publication failure investigation, 7 November 2026

The three failed production runs since the repository migration have two causes.
The retained data and Git repository remain below their storage warning thresholds.

| Run | Failed operation | Evidence |
| --- | --- | --- |
| [7 November](https://github.com/Anthrion/anthrion-signal/actions/runs/42365131214) | Pages deployment | Collection, validation, 182 frontend tests and ten published-data browser tests passed. Pages remained in `syncing_files` until the action canceled it after ten minutes. |
| [6 November](https://github.com/Anthrion/anthrion-signal/actions/runs/42256009749) | Pages deployment | The same tests passed. Pages remained in `deployment_queued` until the ten-minute cancellation. |
| [5 November](https://github.com/Anthrion/anthrion-signal/actions/runs/42121112297) | Create durable public-export Release | The GitHub CLI returned `unexpected end of JSON input` while creating the content-addressed Release. The snapshot pointer was not published. Subsequent scheduled runs succeeded. |

GitHub enforces a [ten-minute Pages deployment limit](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).
The [official action also caps its timeout at ten minutes](https://github.com/actions/deploy-pages/blob/v4/src/internal/deployment.js).
Increasing the input timeout cannot repair a slow queue or file sync.

## Repair

Pages retries the same already-tested artifact once, after a one-minute pause.
The existing publication lock covers both attempts. No collection, translation,
build or browser check is repeated by that retry. An exhausted retry fails the
job. Publication bookkeeping and its scoped credential are created only after
one deployment succeeds; the environment URL uses the successful attempt.

Release reads retry truncated or empty JSON responses, including the CLI error
observed in production. An uncertain Release creation is reconciled by reading
its content-addressed tag. A matching existing Release is reused. Creation can
be retried only after a confirmed 404, with at most three creation attempts.
An ambiguous lookup stops further writes. Permission failures stop immediately;
a 422 is accepted only if the subsequent lookup finds the Release. Existing
ownership, size, checksum, immutable-attachment and accepted-pointer checks remain.
Other mutations are not automatically repeated.

These changes handle transient service failures; they cannot guarantee delivery
during an extended GitHub outage. A failed final attempt remains visible.

## Other source health

The latest collection also reported Caribbean Development Bank HTTP 403 and
Dominican DGCP HTTP 500 responses, plus a Saint Lucia notice without sufficient
public title/scope. Other partial results mostly reflect resumable budgets or
existing source fallbacks. These source results did not fail the workflow. Their
previous records remain retained; this publication repair does not claim complete
or healthy coverage of those sources.

## Verification

Targeted snapshot, release and refresh tests: 85 passed, one Windows symlink test
skipped. Ruff and Git whitespace checks passed. Regression cases cover both
applied and unapplied lost creation responses, malformed/empty success bodies,
timeouts, concurrent-creation conflicts, permission failures, failed reconciliation
reads, bounded retries and publication receipt gating. Broader verification is
recorded with the repair's pull request.
