# Brand assets

The Anthrion dot mark uses the original paths and colours from
`app/public/assets/anthrion-logo.svg`: cyan `#109cd8` and blue `#253f8e`.

Record integration logos are stored locally in `app/public/assets/integrations/`.
They identify the corresponding services; no third-party assets are fetched when
a record opens. Sources checked on 17 September 2026:

| Service | Official source | Asset |
| --- | --- | --- |
| Gmail | [Google Workspace](https://workspace.google.com/products/gmail/) | [Google's Gmail SVG](https://www.gstatic.com/images/branding/productlogos/gmail_2026/v2/web/192px.svg) |
| Salesforce | [Salesforce](https://www.salesforce.com/uk/) | [Salesforce logo SVG](https://wp.sfdcdigital.com/en-us/wp-content/uploads/sites/4/2024/11/logo-salesforce.svg) |
| Slack | [Slack media kit](https://slack.com/media-kit) | [Slack icon PNG](https://a.slack-edge.com/80588/marketing/img/meta/slack_hash_256.png) |

Gmail sharing uses a compose link with no recipient and does not require an API
key or account connection. Salesforce and Slack have no connection or write
capability yet.

The calendar control uses Google's documented
[prefilled event link](https://developers.google.com/workspace/calendar/api/concepts/inviting-attendees-to-events#provide_a_link_for_users_to_add_the_event).
It opens a new tab without saving an event or inviting anyone. Published times are
preserved as UTC instants, with a 15-minute calendar entry starting at the deadline;
date-only deadlines become all-day entries. Users choose the calendar and reminders
before saving in Google Calendar. Saved entries do not automatically track later
changes to a tender's deadline.
