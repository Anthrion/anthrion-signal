# Deferred API integrations

Disabled candidates do not count as collected coverage. The current collectors
need no new credentials for these proposed integrations.

## Already collected

SAM.gov federal opportunities use the public GSA CSV through `sam_csv`, without
an API key or account. The
[Get Opportunities API](https://open.gsa.gov/api/get-opportunities-public-api/)
is a separate keyed alternative: authenticated access and the assigned account
quota have not been tested here. No quota or availability conclusion is inferred
from missing/invalid-key requests.

CanadaBuys federal new/open notices and fiscal-year tenders/awards are also
collected. Provincial coverage would require additional sources.

## Candidates and prerequisites

| Source | Coverage to evaluate | Next step |
| --- | --- | --- |
| Hilma AVP-Read | Finnish national notices beyond TED | A free subscription key from the [Hilma developer portal](https://hns-hilma-prod-apim.developer.azure-api.net/), plus current interface/terms verification. Deferred at the user's request, 12 September 2026. |
| SEAO (Quebec) | Provincial and municipal notices/history | Evaluate the [official CC-BY-labelled distribution](https://www.donneesquebec.ca/recherche/dataset/systeme-electronique-dappel-doffres-seao), update semantics, descriptions and French translation demand. |
| BZP (Poland) | National notices | Evaluate the [documented read API](https://ezamowienia.gov.pl/pl/integracja/), complete pagination, lifecycle and republication scope. |
| eTenders (Ireland) | National notices and history | Separate the licensed catalogue file from the live website export; verify actual freshness and the latter's applicable terms. |
| Kommers Annons | Swedish notice coverage | [eLite terms](https://www.kommersannons.se/elite/Info/TermsOfUse.aspx), section 3.4, require approval for systematic extraction unless a designated interface expressly permits it. |
| Mercell / e-Avrop | Swedish notice coverage | Establish a supported bulk route and applicable reuse permission; free public reading does not establish either. |
| SaskTenders / Texas ESBD / Virginia eVA | Provincial or state notices/history | Verify supported access and reuse with the relevant operator. No permission request has been sent by this review. |
| bids&tenders / MERX | Municipal and other Canadian coverage | Establish an authorized data-supply route and actual republication rights. A subscription is not automatically a data licence. |

Other provincial and Mexican candidates remain disabled and unresolved. A failed
endpoint, a crawler restriction or a catalogue search does not establish that no
authorized source for a whole market exists.

The [reviewed source follow-up](north-america-sources-2026-09-21.md) records the
code findings, official references and implementation checks. In particular,
native NAICS/PSC/UNSPSC/GSIN must stay separate from CPV, and relevance changes need
a full classifier evaluation rather than a single keyword-list hit rate.

Keep any future keys in the local `.env` and GitHub repository secrets. Verify
lifecycle changes, participation restrictions, pagination, assigned request limits,
update/cancellation handling and the selected distribution's terms before enabling
publication.
