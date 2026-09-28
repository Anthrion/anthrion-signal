# Salesforce Lead prefill

The live site opens an unsaved Salesforce **New Lead: Tenders** form in the AI Tender sandbox, as requested for the initial rollout. The user reviews it and presses Save. Clicking the link does not create a Lead or send a message. No Salesforce credentials or API token are embedded in Signal.

The verified sandbox origin and record type are public routing configuration in `app/src/salesforce.ts`. The button and tooltip identify the sandbox. A production-org rollout must verify its own fields, record type, picklists and effective access; changing just the domain is insufficient.

## Field mapping

| Signal value | Existing Salesforce field | Behaviour |
| --- | --- | --- |
| Project, amount, buyer | `Lead_Name__c` | Example: `Workflow management system, $450000, WM5G LIMITED`. No ID. Fits the existing unique Text(80) field by shortening project and buyer; retains all three parts. Unknown values, ranges and framework ceilings remain explicit. Full facts remain in Description. |
| Project title | `Title` | Selected English/Original title, bounded to the existing 128-character field. |
| Industry and Sector | `Industry__c`, `Sector__c` | Existing dependent values `Technology` and `Software and Services`. |
| Buyer | `Company` | Uses the published buyer name. |
| Published contact | `LastName`, `Email` | Uses an unambiguous single contact. The source has no structured given/family names, so the full published name is preserved in Last Name. Published roles remain in Description. |
| No named contact | `FirstName`, `LastName` | First Name is `AI tender`; Last Name is buyer plus the complete Signal ID. Only the buyer portion is shortened when necessary. |
| Origin | `LeadSource` | Existing value `Anthrion Signal`. |
| Lead lifecycle | `Status` | Existing default `New`. |
| Notice country | `Market__c` | Uses existing market values. Nordic countries use the API value `NORD`; other countries without a named existing market use `New Markets`. Mixed markets remain for review. |
| Lead currency | `CurrencyIsoCode` | Reuses published GBP, EUR, SEK or USD. Unsupported or unpublished currencies default to USD, as requested. Original published currency and amounts remain in Description and Lead Name; unsupported currencies include an explicit note that no conversion was applied. Other is never sent as an ISO code. No contract-value-to-company-revenue mapping. |
| Original notice | `Procurement_Publication__c` | Source URL when it fits the existing 255-character URL field; also retained in Description. |
| Reviewed recommended approach | `Technology__c` | Reuses the displayed English/Original guidance, including relevant lots. No new model call. |
| Notice facts and problems | `Description` | Full title, buyer, notice country, published amount **above Notice type**, deadline precision, lots, contacts, links and reviewed problems. Includes a labelled notice-text excerpt when required for a usable URL. |

A notice's place of performance does not establish the buyer's address or headquarters, so those fields are not guessed. The full amount and original currency remain in Description when the org does not support that currency.

The sandbox has these additional public-data fields:

- `Anthrion_Signal_ID__c`: Text(80), Unique, External ID. Editable by design. Uniqueness rejects another Lead carrying the same current ID; editing or removing the ID can defeat that protection. No validation rule prevents changes.
- `Anthrion_Signal_URL__c`: link back to the public Signal record.

The existing Dynamic Form shows these fields and Technology only when Lead Source is Anthrion Signal. Field access uses the existing narrowly scoped permission set. There is no separate Tender Currency field, no added org currency and no exchange-rate change. No object, record, application, API or additional-user access is granted. Org backups, receipts and conversion analysis stay private outside this repository.

The sandbox's **AI Tenders** Lead list view filters on Lead Source = Anthrion Signal and shows Lead Name first, then Company, Lead Status, Market, Created Date and Owner. It omits the standard contact Name column and does not impose a status filter. A shared list view respects each user's existing record access.

## Conversion considerations

Industry, Sector and Market already map to Opportunities in the inspected sandbox. Industry and Sector also map to Accounts: the requested classifications describe the proposed work and may not describe the buyer's industry. Salesforce normally maps Lead Title to Contact Title; a project title is not a person's job title. These choices need review before routine conversion. This release does not change conversion automation or convert Leads.

Lead Name is also unique: different notices with identical or identically shortened names can need a distinguishing human-readable name. Signal ID supplies a separate identity check. Public contract value is not assumed to be Anthrion's revenue, and the response deadline is not an Opportunity close date.

## Verification and limits

The draft uses Salesforce's `recordTypeId` page parameter and individually encoded `defaultFieldValues`. Encoding has been checked in the actual Tenders form with commas, equals signs, ampersands, accented names and multiline text. Tests cover field boundaries, names, site-only action visibility, translations, deadline precision and unsupported currencies.

The site shows the Salesforce action only on available opportunities; awarded/historical records retain their existing sharing actions. This is a site display rule, not a Salesforce restriction, and the URL builder does not enforce lifecycle eligibility. Essential facts, guidance and problems are never silently trimmed to fit a link; a record that cannot fit the bounded URL does not generate a draft. The selected language is reused from cached content.

Desktop Lightning is the verified target. Salesforce documents that this default-field-values navigation is not supported in its native mobile app. A production rollout requires the production org's actual record type, fields, picklists and access to be checked separately.

References: [Salesforce navigation defaults](https://developer.salesforce.com/docs/platform/lwc/guide/use-navigate-default), [default field values and supported environments](https://developer.salesforce.com/docs/platform/lightning-component-reference/guide/lightning-page-reference-utils.html).
