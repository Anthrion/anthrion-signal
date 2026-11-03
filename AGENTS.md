# Anthrion Signal

Read README.md and context/README.md for the product and evidence boundaries.
Read docs/github-transfer.md before changing automation, signing, timestamping or deployment.

## Code Review Rules

- Preserve evidence-based procurement results: do not invent eligibility, reference projects,
  certifications, scope or deadlines. Company evidence must keep its correct attribution.
- Preserve original source text and the separate cached English translations. Keep Gemini keys
  and private company material out of frontend code, public datasets, logs and artifacts.
- Scheduled automation may persist only generated data/. Preserve the remote quota reservation
  before any translation API call, validation before publication, and successful-deployment
  recording after publication. A source change needs the normal human review path.
- Keep Signal public and timestamp records private. Timestamp trusted main-history source SHAs,
  verify receipts against an independently pinned root, and never overwrite earlier evidence.
  A timestamp failure must not block the independent collection/deployment workflow.
- Steven may bypass Signal's review gates; other contributors need his approval. Human commit
  signing and protections against force pushes/deletions remain separate. Do not silently expand
  an App bypass, repository access, paid API usage, or public-data scope.

## Local verification

Use the existing virtual environment for pytest and ruff. Use npm test and npm run build in app/
for frontend changes. Tests must not contact Gemini or a live timestamp authority. Do not run a
live collection, deploy, merge, change GitHub settings or generate personal keys unless requested.
