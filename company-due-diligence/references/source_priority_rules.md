# Source Priority Rules

Sources are assigned to one of three tiers. The tier governs conflict resolution order (primary beats secondary beats signal), staleness thresholds, and trust weight in the dossier. When two sources in the same tier conflict, escalate to a `conflict_set`; do not silently prefer one.

---

## Tier 1 — PRIMARY

Issuer-owned or regulator-filed. Highest evidential weight. Treat as authoritative for the facts they assert; any conflict between a primary and a lower-tier source is resolved in favour of primary unless a restatement or scope mismatch applies (record via `conflict_set`).

**Members:** official company website, product pages, annual reports, quarterly reports, 10-K, 10-Q, 20-F, 6-K, investor relations portal, earnings releases, earnings-call transcripts, exchange filings (SEC EDGAR, Companies House, SEDAR, ASX, etc.), regulatory filings, company registry records, government records, patent filings, trademark registrations, court filings, **sanctions lists** (OFAC SDN, OFAC Consolidated, EU Consolidated, UK OFSI Consolidated, UN Consolidated), **export-control lists** (BIS Entity List), **watchlists** (other regulator-curated risk lists).

**Trust notes:** issuer-affiliated (company-owned content) or regulator-curated (exchange and government filings). Financial statements in 10-K/20-F are audited; earnings releases and transcripts are unaudited but issuer-verified. Court filings and patent records are regulator-curated public records; treat as factual for the claims they assert (not for implied interpretations). Sanctions and export-control lists are government/regulator-curated; treat a named list entry as factual for the listed identifiers — but apply the disambiguation rules in `references/sanctions_screening_rules.md` before asserting a match.

---

## Tier 2 — SECONDARY

Third-party curated or editorially reviewed. High but not issuer-verified weight. Use to corroborate, extend, or provide context for primary evidence. Conflicts with primary sources must be recorded, not silently overwritten.

**Members:** reputable financial media (Bloomberg, Reuters, FT, WSJ, Nikkei, etc.), industry research reports (Gartner, IDC, Forrester, CB Insights, PitchBook, Crunchbase, etc.), analyst commentary (sell-side research, investor letters), press releases (via PR Newswire, Globe Newswire, Business Wire — treat as issuer-proximate but not regulatory-filed), conference materials (earnings day slide decks, investor day presentations), customer case studies published on the company's site or a vendor's site, partner pages and certified partner directories. **Russia/Belarus exit trackers** (Yale CELI "Leave Russia" list, KSE Institute tracker, Moral Rating Agency) are secondary curated sources — use as corroborating signals only; see `references/sanctions_screening_rules.md §7`.

**Trust notes:** not issuer-affiliated (except press releases, which are issued by the company but not filed with a regulator). Not regulatory-status. Analyst estimates and media summaries may differ from filed figures — always note when a secondary figure diverges from a primary filing.

---

## Tier 3 — SIGNAL

Behavioural or indirect evidence. Low direct evidential weight but high value for inferring product direction, hiring priorities, technical stack, and go-to-market signals. Never cite a signal source as authoritative for revenue, headcount, or financial metrics.

**Members:** job postings (LinkedIn, Greenhouse, Lever, company careers pages), developer documentation and API reference portals, app store listings (Apple App Store, Google Play, Microsoft AppSource, Salesforce AppExchange), public GitHub repositories and other OSS hosting, technical blogs and engineering blogs, pricing pages (use with caution — frequently outdated or gated), documentation portals (ReadTheDocs, Zendesk, Intercom, Notion-based docs).

**Trust notes:** not issuer-affiliated in the regulatory sense, though many are company-published. Pricing pages are company-published but not contractually binding and change frequently. Job postings are ephemeral; record `retrieved_at` and treat as point-in-time signals only.

---

## Per-class Reference Table

| `source_class` | `source_priority` | Typical `original_format` | `issuer_affiliated` | `regulatory_status` |
|---|---|---|---|---|
| `annual_report` | primary | PDF, HTML | yes | filed |
| `sec_filing_10k` | primary | HTML/XBRL, PDF | yes | filed (SEC) |
| `sec_filing_10q` | primary | HTML/XBRL, PDF | yes | filed (SEC) |
| `sec_filing_20f` | primary | HTML/XBRL, PDF | yes | filed (SEC) |
| `sec_filing_6k` | primary | HTML, PDF | yes | filed (SEC) |
| `exchange_filing` | primary | PDF, HTML | yes | filed (exchange) |
| `earnings_release` | primary | HTML, PDF | yes | unaudited, issuer |
| `earnings_transcript` | primary | HTML, text | yes | unaudited, issuer |
| `investor_relations` | primary | HTML | yes | unaudited, issuer |
| `company_website` | primary | HTML | yes | unaudited, issuer |
| `product_page` | primary | HTML | yes | unaudited, issuer |
| `regulatory_filing` | primary | PDF, HTML | yes | filed (regulator) |
| `company_registry` | primary | HTML, PDF | no | filed (government) |
| `government_record` | primary | PDF, HTML | no | government |
| `patent` | primary | XML, PDF | yes | filed (patent office) |
| `trademark` | primary | HTML, PDF | yes | filed (trademark office) |
| `court_filing` | primary | PDF | varies | filed (court) |
| `sanctions_list` | primary | CSV, XML, HTML | no | government/regulator |
| `export_control_list` | primary | CSV, HTML | no | government/regulator |
| `watchlist` | primary | CSV, XML, HTML | no | government/regulator |
| `financial_media` | secondary | HTML | no | not filed |
| `industry_report` | secondary | PDF, HTML | no | not filed |
| `analyst_report` | secondary | PDF, HTML | no | not filed |
| `press_release` | secondary | HTML, PDF | yes (issuer) | not filed |
| `conference_material` | secondary | PDF, PPTX | yes | not filed |
| `customer_case_study` | secondary | HTML, PDF | varies | not filed |
| `partner_page` | secondary | HTML | no | not filed |
| `job_posting` | signal | HTML | yes | not filed |
| `developer_docs` | signal | HTML, Markdown | yes | not filed |
| `app_store` | signal | HTML | no | not filed |
| `github_repo` | signal | HTML, code | varies | not filed |
| `technical_blog` | signal | HTML | yes | not filed |
| `pricing_page` | signal | HTML | yes | not filed |
| `documentation_portal` | signal | HTML, Markdown | yes | not filed |
| `russia_exit_tracker` | signal | HTML, CSV | no | not filed |

---

## Conflict Resolution Order

1. Within the same tier: emit `conflict_set` with appropriate `reason_code`.
2. Across tiers: primary supersedes secondary supersedes signal — but only when the data covers the same `scope`, `period`, and measurement definition. A scope or period difference is a `scope_mismatch` or `period_mismatch` conflict, not a clean override.
3. `gaap_vs_nongaap`: always emit a conflict regardless of tier; never merge GAAP and non-GAAP figures.
4. `restatement`: the restated figure supersedes the original; record both and set `restated: true` on the restated period.
