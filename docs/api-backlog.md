# Deferred API Integrations

These integrations are deliberately disabled. No credentials are needed for the
current release, and neither service is counted as active coverage.

| Source | Coverage to add | Prerequisite | Status |
| --- | --- | --- | --- |
| SAM.gov Opportunities | US federal solicitations, pre-solicitations and sources sought | Free SAM.gov account and an API key; verify the quota assigned to the account | Deferred at the user's request |
| Hilma AVP-Read | Finnish national procurement notices beyond TED coverage | Free AVP-Read subscription key from the Hilma developer portal | Deferred at the user's request, 12 September 2026 |

- [SAM.gov API documentation](https://open.gsa.gov/api/get-opportunities-public-api/)
- [Hilma developer portal](https://hns-hilma-prod-apim.developer.azure-api.net/)

When resumed, keep keys in the local `.env` and GitHub repository secrets, never
in the frontend or committed data. Validate lifecycle changes, participation
restrictions, pagination and assigned request limits before enabling publication.
