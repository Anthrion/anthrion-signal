# Deferred API Integrations

These integrations are deliberately disabled and none is counted as active
coverage. No credentials are needed for the current release.

## Waiting on a key or an account

| Source | Coverage to add | Prerequisite | Status |
| --- | --- | --- | --- |
| Hilma AVP-Read | Finnish national procurement notices beyond TED coverage | Free AVP-Read subscription key from the Hilma developer portal | Deferred at the user's request, 12 September 2026 |

- [Hilma developer portal](https://hns-hilma-prod-apim.developer.azure-api.net/)

**SAM.gov no longer belongs here.** US federal opportunities are collected through
the keyless public extract at `s3.amazonaws.com/falextracts/…/ContractOpportunitiesFullCSV.csv`,
which needs no account and is one of the two automated-access routes SAM's own
terms sanction. No API key is required, and the key-gated
`api.sam.gov/opportunities/v2/search` was verified on 21 September 2026 to return
an empty-bodied 404 to every request — with no key, a bad key, an `X-Api-Key`
header, a browser user agent and a second HTTP client. Whether a valid key changes
that is unverified. Its documented quota for a non-federal account is 10 requests
a day, which could not serve this pipeline in any case. See
[`north-america-sources-2026-09-21.md`](north-america-sources-2026-09-21.md) §2.

## Waiting on written permission

Each of these has a working, free, technically adequate route that is withheld by
licensing rather than by technology. The prerequisite is an email from the
repository owner, not engineering work. Assessed 21 September 2026; full detail in
[`north-america-sources-2026-09-21.md`](north-america-sources-2026-09-21.md).

| Source | Coverage to add | Who to ask | Why it is blocked |
| --- | --- | --- | --- |
| Mercell annonsdatabas | The widest Swedish below-threshold coverage, ~361 IT notices a year against ~203 from TED | Mercell | `robots.txt` allows everything and a nightly notice sitemap exists, but Terms of Use §2.5 forbids crawling and automated downloading. Konkurrensverket dnr 880/2024 enforces free access for people, not machines — a strong basis for the request |
| SaskTenders | 58,014 Saskatchewan competitions including 23,201 awards with vendor and value | SaskBuilds and Procurement | No licence grant exists anywhere on the site, so Crown copyright applies by default. There is no prohibition either — only an absence |
| Texas ESBD | ~62,000 Texas state records via a keyless JSON search | Texas Comptroller of Public Accounts | `robots.txt` disallows everything |
| Virginia eVA | ~292,000 documents with a genuine `lastupdatedate` cursor | Virginia Department of General Services | `robots.txt` disallows everything |
| bids&tenders | ~1,000 open opportunities, much of it the Ontario municipal volume Ontario's own portal withholds | bids&tenders (GHD) | Terms clause 13 prohibits automated extraction for commercial purposes. A commercial data agreement, not a permission email |

Two sources are **refusals rather than gaps** and should not be revisited as
engineering problems: `www.merx.com` and `www.gov.mb.ca` both name `anthropic-ai`,
`ClaudeBot` and `Claude-Web` under `Disallow: /`. MERX also closes `/ws/`, its SOAP
interface, to every agent. Manitoba tenders exist only on MERX, so Manitoba has no
legitimate automated route.

## Conventions when any of these resumes

Keep keys in the local `.env` and in GitHub repository secrets, never in the
frontend or in committed data. Validate lifecycle changes, participation
restrictions, pagination and assigned request limits before enabling publication.
Where a source carries native classification codes, add a selection rule for that
scheme rather than mapping them onto CPV prefixes — the schemes are inverted, not
merely different, and the detail is in
[`north-america-sources-2026-09-21.md`](north-america-sources-2026-09-21.md) §1.
