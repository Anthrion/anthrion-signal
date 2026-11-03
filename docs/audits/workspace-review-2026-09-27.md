# Workspace PR #31: independent review

Reviewed `ca08d40ff80705dfb191d2f4f2cb2e3dd0e604bc` against current main. All requested
UI features remain: light/dark themes, compact header and filters, six refiners,
workspace preferences and backup, source coverage map, motion, mobile save, keyboard
shortcuts, per-record language switching and the unified record/history scroll.

## Repairs

- A notice with only a questions deadline lost that deadline when Full details was
  folded into the record. Only an ordinary response deadline already shown in the
  header is now omitted from Key dates. Lot-specific, conflicting and superseded
  dates remain available with their provenance and calendar actions.
- H and S fired through open sort/search menus, hiding one record and saving the
  next one. Shortcuts now respect modal and popover menus, editable content and
  composition input. Independent browser probes reproduced the original failure.
- Filter source choices now follow all collected provenance, including a retired
  secondary source on a merged award, rather than only each record's primary source.
- Opening history obeys reduced motion. The coverage map labels the research figures
  as estimated source reach before collection limits and relevance filtering; these
  are planning estimates, not measured feed completeness. The original country
  research, map and estimates are retained.

## Verification

- 142 frontend unit tests passed; production build passed, including CSP-compatible
  theme boot at the GitHub Pages base path.
- Complete fixture-backed desktop/mobile suite: 171 passed, 3 existing skips.
  Accessibility coverage was expanded to both themes, with no reported violations.
- The suite covers language persistence, reviewed guidance, search modes, all
  refiners, hidden/saved records, historical navigation, document revisions, source
  links, keyboard use, responsive layouts, exports and blocked/malformed storage.
- Visual inspection of the production preview in both themes retained the design.
- No collector, canonical record, translation cache, review ledger, public-data
  schema, deployment workflow or repository protection is changed by this PR.

The build's fixture export verifies UI compilation and browser behavior. It does
not stand in for the existing full-data validation required before publication.
