# Signal: company GitHub setup and operating guide

Updated 17 September 2026. Signal is now public at
[`Anthrion/anthrion-signal`](https://github.com/Anthrion/anthrion-signal); timestamp
evidence is stored separately in private `Anthrion/Timestamps`.

**Configuration, App data saves, tested deployment and private timestamp verification are complete.**
The three approved company changes are applied: the Signal-only exception to the older
combined rule, the Steven-only team, and the App installed only on Signal. Other projects'
protections, company billing, archive secret scope and other people's notifications were
not changed. AI reviews remain deferred.

Local verification before rollout: 659 Python tests passed, Ruff passed, workflow YAML
parsed and whitespace checks passed. Tests use an offline timestamp authority; a live
receipt and real App writes also passed the live checks linked below.

## Agreed behaviour

| Actor / change | Configured behaviour |
| --- | --- |
| Steven (`stevostar1234`) | Signed direct pushes to main and self-merges without another reviewer. Existing deployment tests still run. |
| Other contributors | Feature-branch pushes are allowed; reaching main needs a PR, passing `test`, and Steven's approval. |
| Signal's collection bot | Data-only checkpoints and publication records are saved without a PR, human review, or personal signing key. |
| Deployment | Only trusted main is published after successful validation; no extra environment approval. |
| Timestamping | Relevant main pushes, including Steven's direct pushes, create private evidence. Data-only pushes are excluded. |

## Costs: no mandatory new GitHub hosting subscription, not unlimited service

| Item | Cost boundary |
| --- | --- |
| Public Signal's standard Ubuntu Actions jobs | Standard GitHub-hosted runner use in public repositories is free. Keep `ubuntu-latest`; do not select larger runners. |
| GitHub Pages | Included for public repositories, subject to usage and acceptable-use limits. Published sites have a 1 GB limit and a soft 100 GB monthly bandwidth limit. There is no unlimited-hosting promise. |
| Public-only outside collaborators | No extra Team seat for that access. Invite them as outside collaborators, not organization members. Do not give them private Timestamps access merely to contribute. |
| Organization members and private-repository collaborators | Consume paid Team seats. The existing membership bill is separate from this transfer. |
| Private timestamp archive | Ordinary private Git storage is included subject to repository limits. The new job runs in public Signal, not in the private archive. Check that archive pushes do not launch additional private workflows. |
| Actions artifacts/cache | Retain short artifact lifetimes and the included cache limit. Review metered-storage settings; free runner time is not a promise of unlimited storage. |
| Gemini translation | Both selected models have free tiers, but the API key's Google project determines billing. Existing code quotas limit calls, not invoices. Steven confirmed the project's free tier; its confirmation variable is enabled. No billing plan was changed. |
| Timestamp authority | Steven confirmed and approved Sectigo's qualified timestamp service and terms. No paid fallback or new subscription is configured; this is not an unlimited-service promise. |
| Automatic AI PR review | Optional; not enabled here. Codex uses the applicable ChatGPT/Codex allowance and may need credits beyond it. GitHub Team does not include unlimited AI review. |
| Custom domains / other services | No new domain, server, subscription, LFS, or paid Marketplace App is introduced. Existing external charges remain separate. |

For an independent billing check, an owner can open **Anthrion → Settings → Billing and licensing
→ Budgets and alerts**, inspect existing budgets, and set the permitted additional
spend for Signal to **$0** with **Stop usage when budget limit is reached** where
supported. An alert-only budget does not stop charges. Avoid changing organization-wide
budgets used by other projects. Keep paid cache expansion and paid optional services off.
A spending stop may pause affected work; it cannot provide unlimited work for free or
erase charges already incurred. Verify the live billing settings before claiming a cap.

Sources: [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
[GitHub seats](https://docs.github.com/en/billing/reference/github-license-users),
[public-only collaborators](https://docs.github.com/en/billing/how-tos/manage-plan-and-licenses/manage-user-licenses),
[Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits),
[budgets](https://docs.github.com/en/billing/how-tos/set-up-budgets),
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing),
[Sectigo service](https://www.sectigo.com/resource-library/time-stamping-server),
[Codex usage](https://learn.chatgpt.com/docs/pricing).

## Implementation

- `.github/workflows/ingest-and-deploy.yml`: company App authentication in both writer
  jobs, actual App bot identity, data-only commit checks, and a free-tier confirmation
  switch for translation after transfer. The personal repository retains its existing
  GITHUB_TOKEN and translation behaviour until transfer.
- `scripts/automation_git_guard.py`: checks staged paths and every unpushed commit;
  rejects code changes hidden by a later revert as well as moves out of data/.
- `scripts/translate_records.py`: uses the configured bot identity and applies the
  guard before committing/pushing its quota reservation. It still reserves remotely
  before any Gemini request.
- `.github/workflows/timestamp-manifest.yml` and `scripts/timestamp_source.py`: standalone
  public-repository workflow writing only to private Timestamps. Enabled only by the explicit timestamp variable below.
- `.github/CODEOWNERS`: requests Steven's review. The GitHub rule must enforce this;
  the file alone does not block a merge.
- `AGENTS.md`: durable Signal-specific instructions for future reviewers. No AI service
  subscription or automatic review was activated.
- Regression tests cover data-only writes, actual offline RFC 3161 verification,
  tampering, nonce mismatch, pinned root checks, direct pushes, private-archive enforcement,
  safe reruns and concurrent archive updates.

## Completed configuration and remaining checks

| Item | Status | Where / example |
| --- | --- | --- |
| Transfer and local remote | Complete | Public `Anthrion/anthrion-signal`; origin points to the company repository. |
| Review rule | Active, ID 23605431 | **Signal → Settings → Rules → Rulesets → signal-review**. One approval, Code Owner review, stale approval dismissal and `test` required. |
| Steven-only team | Complete | **Anthrion → Teams → Signal maintainer** contains only `stevostar1234`, with Signal Write access and an Always-allow review bypass. |
| Human signatures | Active, ID 23605432 | **signal-signatures** has only the App bypass. Steven still signs. |
| History protection | Active, ID 23605434 | **signal-history** blocks force pushes and deletion, without bypass. |
| Combined company rule exception | Complete | Signal is excluded from `default-branch-protection` after replacement rules were created. **Keep the exclusion**; do not reapply the conflicting combined rule. Other projects retain their existing rules. |
| Merge methods | Complete, per Steven's latest choice | **Settings → General → Pull Requests**: merge, squash and rebase all enabled. Signed-commit rules still apply. |
| Automation App | Installed, credential saved | **Anthrion → Settings → Developer settings → GitHub Apps → Anthrion Signal automation**. Contents write + Metadata read, installed only on Signal, no webhook. |
| App credential | Complete | Client ID variable and encrypted private-key secret saved in Signal. Existing Gemini secret retained. |
| Pages / deployment environment | Complete | **Settings → Pages → GitHub Actions**; **Environments → github-pages** permits only main, no reviewers. |
| Gemini and Sectigo decisions | Confirmed by Steven | Free-tier confirmation enabled; approved endpoint and independently verified root configured. |
| Windows personal signing | Configured; local signing check passed | PC signing public key registered. Mac configuration is not verified. |
| First App deployment | Passed | Both App writer jobs succeeded and Pages deployed after validation. See verification links below. |
| First private timestamp | Passed | Receipt verified against the pinned root and archived privately; rerun verified and reused it without another TSA request. |

The App is an identity for the existing Actions jobs: it needs no extra server, paid human
bot account or personal SSH key. The downloaded `.pem` is a valid local private key; a
`SHA256:...` fingerprint cannot authenticate it. Private key files are ignored by Git.

The production schedule stayed active during setup. Once the workflow files are pushed,
code changes trigger validation and deployment. The new Pages address is
https://anthrion.github.io/anthrion-signal/ . Update shared links: GitHub redirects the old
Git repository, but not the old Pages address. Browser-saved preferences belong to the
site origin and do not automatically move to the new address.

### Actions values

Use repository scope for the App credential. An organization archive secret should be
available only to the selected source repositories that genuinely need it.

| Name | Location / value | Required when |
| --- | --- | --- |
| `ANTHRION_APP_CLIENT_ID` | Actions **Variables**; company App Client ID | Configured |
| `ANTHRION_APP_PRIVATE_KEY` | Actions **Secrets**; the downloaded App private key | Configured |
| `GEMINI_API_KEY` | Existing Actions **Secret**, from the verified free-tier Google project | To create new English translations |
| `SIGNAL_GEMINI_FREE_TIER_CONFIRMED` | Actions **Variable**; `true` only after checking the Google project | Otherwise new translation calls are skipped after transfer; existing cached translations remain |
| `TIMESTAMPS_WRITE_TOKEN` | Existing organization Actions **Secret**; Contents read/write to private `Anthrion/Timestamps` | Configured and verified live |
| `TIMESTAMP_TSA_URL` | Actions **Variable**; default `https://timestamp.sectigo.com/qualified` | Change only for the agreed provider |
| `TIMESTAMP_TSA_ROOT_PEM` | Actions **Variable**; exactly one approved public root certificate in PEM text | Configured and verified live |
| `TIMESTAMP_TSA_ROOT_SHA256` | Actions **Variable**; independently approved SHA-256 fingerprint of that certificate's DER encoding | Configured and verified live |
| `TIMESTAMP_TSA_CHAIN_PEM` | Optional Actions **Variable**; supporting intermediate certificates if absent from the response | Only if verification needs them; these are not trust anchors |
| `SIGNAL_TIMESTAMPING_ENABLED` | Actions **Variable**; `true` after the preceding checks | Set to true; baseline and rerun verified |

The free-tier confirmation is an operational switch, not a billing API or guaranteed
spending cap. Recheck it if the Google project's billing tier changes. Keep the
provider's own free-tier restrictions in place. No paid fallback model is configured.

The approved **Sectigo Qualified Time Stamping Root R45** was obtained independently
from [Sectigo's official certificates](https://www.sectigo.com/eidascps). Its DER SHA-256 is
`F871F8976B4068D700D5F281084B4A29EAF4B8F35743330BA062FAB46F58C2ED`.
Its identity was cross-checked against Sectigo's published policy. Do not use the response's own root as
the sole proof that it is trustworthy. Public certificate bytes are not private SSH keys.

### Signal-only rules

At **Signal → Settings → Rules → Rulesets**, the following three active rules target **main**. Organization-level equivalents restricted to Signal also work.
All other applicable rules still apply; a permissive repository rule cannot override them.

| Rule | Requirements | Bypass |
| --- | --- | --- |
| `signal-review` | PR required; **1 approval**; **Code Owner review required**; existing `test` status check required; merge, squash and rebase allowed; dismiss stale approvals when reviewable changes are pushed | Dedicated non-secret organization team containing **only Steven**, and the installed Signal App; both **Always allow** |
| `signal-signatures` | Require signed commits | Signal App only; **Always allow**. Steven and other humans still sign. |
| `signal-history` | Restrict deletions and block force pushes | Empty |

Create the dedicated team under **Anthrion → Teams → New team**, add only
`stevostar1234`, grant it appropriate Signal access, and avoid nesting teams beneath it.
This uses Steven's existing organization membership; do not add a new paid human bot
account. Do not use an all-admins or all-writers bypass. Give ordinary contributors
Write access rather than policy-administration access. Organization owners can still
change settings; these rules do not remove owner authority.

Leave required up-to-date branches/merge queues and an additional deployment-review gate
off initially. Frequent data updates should not force contributors to continually refresh
their branch. Review-bypass also covers Steven's direct pushes where PR checks cannot
run beforehand; existing production validation still runs before deployment.

App bypass is not restricted to data/ by GitHub. The workflow's data-only checks enforce
that operating convention; the credential itself has repository Contents write permission.
Human signing normally uses SSH, but GitHub's native verified-signature requirement also
accepts its other supported signing methods.

[Bypass configuration](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository),
[rule layering](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets),
[CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).

## How the private timestamp works

Normal merges preserve original signed commit objects. Squash and rebase create new
commit objects, so the original signatures do not carry over. Timestamping still records
the resulting accepted main version. GitHub may block a particular merge operation if
it cannot produce commits satisfying the signed-commit rule. In particular, GitHub's
web **Rebase and merge** does not sign the rewritten commits. Steven can instead rebase
and sign locally before a permitted push; other contributors can rebase/sign their feature
branch and use an approved normal merge. Keeping the menu option enabled does not bypass
signing. See [GitHub's explanation](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification#signature-verification-for-rebase-and-merge).
Other company repositories keep zero required
approvals until the team chooses to change them.

`timestamp-manifest.yml` contains the automation instructions; `manifest.json` is the
small record it creates. The timestamp authority's signed response supplies the trusted time.

| Change | Timestamp? | Example |
| --- | --- | --- |
| Source, configuration or workflow change reaching main | Yes | Steven pushes a signed parser fix, or merges Alice's approved PR. |
| Only `data/` changes | No | New notices, translation checkpoints, quota reservations and publication records. |
| Code and data together | Yes | Updating a collector and its generated records. |
| Repeat deployment without a source push | No automatic new source timestamp | Rebuilding the same version. |
| Bot changes code | Not exempt by actor | The data-only guard should reject that push; actor names alone do not skip timestamps. |


The public workflow runs only for the company repository's main branch, after explicit
enablement. Source pushes touching anything outside data/ trigger it; a manual run can
name a complete SHA already in main history. A direct push is valid without a PR.

It makes a manifest containing the source commit/tree hashes and optional matched merged
PR metadata. It hashes the exact manifest bytes, sends an RFC 3161 request to the authority,
then verifies the response twice: against the manifest and against the nonce-bearing request.
Only the approved, fingerprint-checked root is trusted. The Git committer date is labelled
as a Git date, and the authority's time is in the signed receipt.

It verifies that Timestamps is private, then appends the record atomically through GitHub's
Git API, without printing the manifest, receipt or private API bodies. There is no public
artifact upload or PR comment exposing the record. Public workflow code and success/failure
status remain visible. Failed timestamping leaves deployment unaffected.

Record path:

```text
records/Anthrion_anthrion-signal/<full-source-commit-sha>/
  manifest.json
  request.tsq
  token.tsr
  chain.txt
  trusted-root.crt
  receipt.txt
```

Valid existing evidence is verified and reused without another timestamp request. Invalid
or incomplete existing records fail rather than being overwritten. Archive races retry
normal append operations; no force push is used. The serial Signal queue and a short delay
respect spacing within this repository; other projects still need coordinated provider limits.

This records source existence by the authority's receipt time; it does not prove first
creation, ownership or the exact deployed artifact. It intentionally does not timestamp
every routine data refresh. Back up the private evidence and source Git objects using the
company's existing backup. A later ordinary Git commit can still delete records, so branch
force-push protection alone is not immutable storage.

## SSH key passphrases

A passphrase is optional but recommended for each personal signing key. Use the SSH agent
on Windows and the SSH agent/macOS Keychain on Mac so you do not type it for every commit.
Separate keys for PC and Mac are recommended so one device can be revoked independently;
GitHub does not require a different key per operating system.

If creating a new key, choose a fresh filename with `ssh-keygen -t ed25519`; enter the
passphrase at its interactive prompt. Do not overwrite an existing key. Add the contents
of its **.pub** file at **GitHub personal Settings → SSH and GPG keys → New SSH key →
Key type: Signing Key**. Configure Git's SSH signing format and signing key for the repo.
If using the same key for SSH push authentication, add that public key separately with
**Authentication Key** type as well. Authentication and signing registrations have different roles.

Keep the private key and passphrase on the device/password manager. The production bot uses
its App credential and does not need your personal SSH private key or passphrase.
[GitHub passphrase guidance](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/working-with-ssh-key-passphrases).

## Failure notifications

Steven's **personal Settings → Notifications → Actions** already has **Email**,
**On GitHub**, and **Send notifications for failed workflows only**, with his company
address as the default notification email. No team mentions, custom mail service or
failure issues have been added. The Watch setting was not broadened.

GitHub chooses native recipients from the workflow actor and individual subscriptions.
There is no repository switch that overrides everyone else with “only email Steven”.
Other people who subscribe may still receive notifications; they control their own settings.
See [GitHub's notification settings](https://docs.github.com/en/account-and-profile/managing-subscriptions-and-notifications-on-github/setting-up-notifications/configuring-notifications).

Handled source outages and translation warnings can leave a run successful while preserving
previous data. They do not produce a failed-workflow email. Validation, build and deployment
failures do fail the workflow. Use the run summary to inspect partial collection; dedicated
per-source email alerts would be an optional separate addition.

## Remaining responsibilities

**Codex setup complete:** signed direct push, App data saves, production deployment,
private timestamping and safe rerun are verified. No automatic AI reviews are enabled.

### Live verification, 17 September 2026

- [Signed setup commit](https://github.com/Anthrion/anthrion-signal/commit/1fa88b41c1c9b3f7a9af2d230710891306b71ffa): GitHub reports Verified; Steven's direct push used only the review/check bypass.
- [Required tests](https://github.com/Anthrion/anthrion-signal/actions/runs/35237337536): 659 Python tests and 32 frontend tests passed, plus Ruff and the frontend build.
- [Production deployment](https://github.com/Anthrion/anthrion-signal/actions/runs/35237337608): App authentication, data checkpoint, 107 passing browser checks, Pages deployment and publication record succeeded.
- [Private baseline timestamp](https://github.com/Anthrion/anthrion-signal/actions/runs/35237388066): verified against the approved root and archived as six files. Repository, source SHA and tree SHA were independently compared with the saved manifest.
- [Safe rerun](https://github.com/Anthrion/anthrion-signal/actions/runs/35237694891): existing private receipt verified and reused; no replacement record or new TSA request.
- [Private evidence folder](https://github.com/Anthrion/Timestamps/tree/main/records/Anthrion_anthrion-signal/1fa88b41c1c9b3f7a9af2d230710891306b71ffa): requires archive access. Data-only App commits did not create automatic timestamp runs.

The verification runs use GitHub's current Ubuntu/OpenSSL. This PC's older bundled
OpenSSL 1.1.1 could not verify the real provider's signing-certificate attributes; use
current OpenSSL when verifying downloaded evidence locally. No trust check was disabled.


**Steven/team:** set up the Mac's personal signing key when needed; other developers add
their own public signing keys. A passphrase is optional but recommended, and separate
keys per device let you revoke one device independently. Keep the App private key secure.
No more keys or paid accounts are required for this setup.

**Company owner:** arrange a backup of source history and private timestamp evidence,
name its maintainer, and independently check existing budgets if a hard spending cap is
required. Reducing the existing organization archive secret's broad availability is a
separate company decision; it was not changed as part of the Signal exception.

Contributor rejection and force-push tests should use a disposable repository, not
production. The active rules and bypass lists can be inspected without attempting
destructive writes. GitHub permits verified GPG/S/MIME signatures as well as SSH; the
chosen human workflow uses SSH, but the built-in rule does not enforce SSH exclusively.

## Direct links to inspect the setup

| Setting / file | Link | Change made |
| --- | --- | --- |
| Signal review rule | [signal-review](https://github.com/Anthrion/anthrion-signal/rules/23605431) | One approval, CODEOWNER and test; Steven/team and App bypass |
| Signal signing rule | [signal-signatures](https://github.com/Anthrion/anthrion-signal/rules/23605432) | Human signatures required; App bypass only |
| Signal history rule | [signal-history](https://github.com/Anthrion/anthrion-signal/rules/23605434) | No force pushes/deletion; no bypass |
| Combined company rule | [default-branch-protection](https://github.com/organizations/Anthrion/settings/rules/22175216) | Only added Signal to exclusions; other projects' approval counts unchanged |
| Steven's team | [Signal maintainer](https://github.com/orgs/Anthrion/teams/signal-maintainer) | Created with Steven only; Write access to Signal |
| App registration | [Anthrion Signal automation](https://github.com/organizations/Anthrion/settings/apps/anthrion-signal-automation) | Created company App, Contents write, no webhook |
| App installation | [Selected repository access](https://github.com/organizations/Anthrion/settings/installations/162505472) | Installed only on Signal |
| Merge buttons | [Signal General settings](https://github.com/Anthrion/anthrion-signal/settings) | Merge, squash and rebase all enabled |
| Actions secrets | [Secrets](https://github.com/Anthrion/anthrion-signal/settings/secrets/actions) | Added App private key; existing Gemini/archive credentials retained |
| Actions variables | [Variables](https://github.com/Anthrion/anthrion-signal/settings/variables/actions) | Added App Client ID, free-tier confirmation and timestamp configuration |
| Deployment settings | [Pages](https://github.com/Anthrion/anthrion-signal/settings/pages), [Environments](https://github.com/Anthrion/anthrion-signal/settings/environments) | Verified existing Actions/main-only setup; no reviewer added |
| Automation code | [Workflow files](https://github.com/Anthrion/anthrion-signal/tree/main/.github/workflows), [CODEOWNERS](https://github.com/Anthrion/anthrion-signal/blob/main/.github/CODEOWNERS) | App authentication, data-only guard, private timestamp workflow and Steven's ownership |
| Personal notifications | [Notification preferences](https://github.com/settings/notifications) | Verified failure-only Actions email; no change to anyone else's preferences |
