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
terms sanction. No API key is required.

The key-gated `api.sam.gov/opportunities/v2/search` was verified on 21 September
2026 to return an empty-bodied 404 to every request — with no key, a bad key, an
`X-Api-Key` header, a browser user agent and a second HTTP client. **Keyed access
is untested and its assigned quota is unknown**: the
[official documentation](https://open.gsa.gov/api/get-opportunities-public-api/)
requires `api_key` and date bounds, documents `limit` up to 1000 per request, and
states no rate limit at all. An earlier revision of this file asserted a 10
requests/day quota taken from unspecified sibling SAM material and concluded the
API could not serve this pipeline; **both claims are withdrawn** — a quota for
another API or account class does not establish this one's. The keyless extract
remains the right choice on its own merits. See
[`north-america-sources-2026-09-21.md`](north-america-sources-2026-09-21.md) §2.

## Waiting on written permission

Each of these has a working, free, technically adequate route that is withheld by
licensing rather than by technology. The prerequisite is an email from the
repository owner, not engineering work. Assessed 21 September 2026; full detail in
[`north-america-sources-2026-09-21.md`](north-america-sources-2026-09-21.md).

| Source | Coverage to add | Who to ask | Why it is blocked |
| --- | --- | --- | --- |
| Mercell annonsdatabas | The widest Swedish below-threshold coverage, ~361 IT notices a year against ~203 from TED | Mercell | `robots.txt` allows everything and a nightly notice sitemap exists, but Terms of Use §2.5 forbids crawling and automated downloading. Konkurrensverket dnr 880/2024 enforces free access for people, not machines — a strong basis for the request |
| Kommers Annons | ~70 Swedish IT notices a year, the smallest of the three Swedish routes | Antirio System AB | [eLite terms](https://www.kommersannons.se/elite/Info/TermsOfUse.aspx) §3.4 require prior written approval for systematic automated extraction unless expressly permitted via an API or designated interface. §3.3 permits passing public information to third parties free of charge but forbids resale without approval, and §5.4 governs attribution |
| SaskTenders | 58,014 Saskatchewan competitions including 23,201 awards with vendor and value | SaskBuilds and Procurement | No licence grant exists anywhere on the site, so Crown copyright applies by default. There is no prohibition either — only an absence |
| Texas ESBD | ~62,000 Texas state records via a keyless JSON search | Texas Comptroller of Public Accounts | `robots.txt` disallows everything |
| Virginia eVA | ~292,000 documents with a genuine `lastupdatedate` cursor | Virginia Department of General Services | `robots.txt` disallows everything |
| bids&tenders | ~1,000 open opportunities, much of it the Ontario municipal volume Ontario's own portal withholds | bids&tenders (GHD) | Terms clause 13 prohibits automated extraction for commercial purposes. A commercial data agreement, not a permission email |

Two sources **withhold automated access from this client specifically**:
`www.merx.com` and `www.gov.mb.ca` both name `anthropic-ai`, `ClaudeBot` and
`Claude-Web` under `Disallow: /`, and MERX also closes `/ws/`, its SOAP interface,
to every agent. Manitoba tenders exist only on MERX.

That settles what not to crawl, and nothing more.
[RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html#section-2.2.1) matches
robots rules by crawler identity and path and distinguishes them from access
authorisation, and MERX's terms were deliberately not read. **Whether an
authorised route exists — a documented API, a separately licensed distribution or
a written agreement — is unresolved**, so Manitoba is an open question for anyone
who wants that coverage rather than a closed one. An earlier revision of this file
described these as refusals that should not be revisited; that overstated the
evidence and is withdrawn.

## Conventions when any of these resumes

Keep keys in the local `.env` and in GitHub repository secrets, never in the
frontend or in committed data. Validate lifecycle changes, participation
restrictions, pagination and assigned request limits before enabling publication.
Where a source carries native classification codes, add a selection rule for that
scheme rather than mapping them onto CPV prefixes — the schemes are inverted, not
merely different, and the detail is in
[`north-america-sources-2026-09-21.md`](north-america-sources-2026-09-21.md) §1.
