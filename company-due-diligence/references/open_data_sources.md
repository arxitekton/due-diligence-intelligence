# Open Data Sources for DD / KYC / Market Research — Consensus Catalog

**As-of:** 2026-06-21
**Method:** Two independent research arms (Claude, web-verified against primary pages · Codex, knowledge + partial web) per `docs/superpowers/specs/2026-06-21-open-data-sources-design.md`, then reconciled. Each row carries an `agreement` marker: `both` (both arms surfaced it), `claude` / `codex` (one arm only).
**Verdict legend:** ✅ wire now (clean licence, ingest + store + redistribute extracted data) · ⚠️ conditional (usable, but attribution / paid licence / no-redistribution / no-automation caveat — read the row) · ❌ avoid (no redistributable/automatable access).

> **Field names deliberately mirror `references/legal_and_tos.md`** (`access_basis`, `retention_policy`, redistribution) so this catalog drops straight into the skill's `source_inventory` metadata model. A "redistribution = no/conditional" row maps to `retention_policy: session_only` (ingest-to-screen, don't warehouse).

---

## 1. Reconciliation of disagreements

The arms diverged on five verdicts. Each resolved by preferring the **web-verified** basis and reading the caveat narrowly:

| Source | Claude | Codex | Resolution | Basis |
|---|---|---|---|---|
| **GDELT** | ✅ | ⚠️ (licence unclear in live view) | **✅** | Claude fetched the About page: *"unlimited, unrestricted use… redistribute, rehost, republish, mirror"* with citation. It's a self-declared grant (not a standard licence) — note that, but it permits exactly what we need. |
| **EDINET (JP)** | ✅ | ⚠️ (doc-level reuse unconfirmed) | **✅** | Claude verified **Public Data License v1.0** → commercial reuse + redistribution with attribution. Caveat: ~10-yr retention window on the API. |
| **UK Sanctions List** | ⚠️ (migration) | wire-now | **✅ (new FCDO list)** | Both confirmed OFSI list **withdrawn 2026-01-28**. Licence (OGL v3.0) is clean → ✅; the ⚠️ was only about repointing URL + Group-ID→Unique-ID schema. Action = migrate, then wire. |
| **WIPO PATENTSCOPE** | ⚠️ | ❌ (terms ban automation/bulk) | **❌ free tier / ⚠️ paid** | Agreement: free UI terms forbid automated/bulk/store. So **avoid for our pipeline**; redistributable programmatic use needs the **paid** PCT Webservice. Use USPTO/EPO instead for automated patent data. |
| **OECD** | ⚠️ (rate limits) | wire-now | **✅ w/ caveats** | CC BY 4.0 (content from 2024-07-01) is redistributable with attribution → ✅; enforce the **60 downloads/hr** limit and clear third-party-owned series. |

**Complementary coverage** (one arm caught what the other missed, both folded in):
- **Codex added** (Claude missed): US Census, US BEA, BLS (all US-gov public domain, ✅ — fills the US market-data gap), FATF high-risk jurisdictions, WIPO Global Brand Database (❌), PACER, UNCTADstat, Statistics Canada.
- **Claude added** (Codex missed): Wikidata, OpenAlex, USPTO ODP, EPO OPS (the automatable patent path), OpenSanctions PEPs (granular), FinCEN BOI (❌, now non-public by law), FRED, EUIPO, and the full national-registry long tail (DE/FR/IT/ES/NL/BE/DK/NO/SE/FI/CH/AT/IE/PL/CZ/EE/BR/ZA/CN/KR + DART/Bundesanzeiger).

---

## 2. Deep-vetted sources (Tiers A + B)

### 2a. Sanctions / export-control / watchlists / PEP / adverse-media (KYC-AML)

| name | agree | tier | geo | access | auth | rate limit | licence | redistribution | retention | verdict | basis_url |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OFAC SDN + Consolidated | both | A | US-admin, global | bulk (XML/CSV) + SLS API | none | none on bulk; no scraping the search UI | CC0 / US-gov PD | yes — unrestricted | indefinite | ✅ wire now | ofac.treasury.gov/sanctions-list-service |
| EU Consolidated Financial Sanctions (FSF) | both | A | EU-admin, global | bulk (CSV/XML, fixed public token) + RSS | none | none published | EC reuse, Decision 2011/833/EU | conditional — free reuse incl. commercial w/ acknowledgment | per_license | ✅ wire now (attribute) | webgate.ec.europa.eu/fsd/fsf/public/rss |
| UN Security Council Consolidated | both | A | UN-admin, global | bulk (XML/XSD) | none | ~1h SAS token/request | UN Terms of Use (all rights reserved) | **no** — personal/non-commercial; redistribution needs UNSD written permission | session_only | ⚠️ ingest-to-screen only | scsanctions.un.org/resources/xml/en/consolidated.xml |
| UK Sanctions List (FCDO) | both | A | UK-admin, global | bulk (CSV/XML/ODS…) | none | none published | OGL v3.0 | yes — redistribute/commercial w/ attribution | indefinite | ✅ wire now | sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv |
| BIS Entity List + Consolidated Screening List (CSL) | both | A | US-admin, global | CSL REST API + bulk (CSV/JSON) | free key (REST only) | per-API throttle | US-gov PD / ITA Open Data | yes — "for public use and dissemination" | per_license | ✅ wire now | trade.gov/consolidated-screening-list |
| OpenSanctions | both | A | global aggregate | bulk (CSV/FtM) + Match API; self-host yente | none (NC bulk) / paid (commercial) | metered | CC-BY-NC 4.0 + paid commercial | conditional — **commercial DD needs paid licence** | per_license | ⚠️ conditional | opensanctions.org/licensing |
| OpenSanctions PEPs | claude | A | global (263 countries) | bulk + match API | free key | per tier | CC-BY-NC 4.0 | conditional — commercial needs licence | per_license | ⚠️ conditional | opensanctions.org/datasets/peps |
| GDELT 2.0 | both | A | global, 100+ langs | bulk (CSV) + BigQuery + APIs | none | none (BigQuery billed) | self-declared "unlimited unrestricted use" | yes — redistribute/rehost w/ citation | indefinite | ✅ wire now | gdeltproject.org/about.html |
| FATF High-Risk / Increased-Monitoring | codex | A | global jurisdiction-risk | manual (publication) | none | n/a | FATF site terms (unverified) | conditional | per_license | ⚠️ country-risk overlay (not an entity list) | fatf-gafi.org/.../High-risk-and-other-monitored-jurisdictions |
| Canada Consolidated Autonomous Sanctions (CACSL) | both | B | Canada | bulk (XML/HTML/PDF) | none | none published | **GC standard terms — NOT OGL-Canada** (verified 2026-06-21) | **no (commercial)** — non-commercial reproduction free w/ attribution; commercial redistribution **and any normalization/adaptation/translation** need prior written GC permission | session_only | ⚠️ ingest-to-screen only; commercial redistribution / normalized republication needs GC permission | canada.ca/en/transparency/terms.html ; international.gc.ca/.../sanctions/consolidated-consolide |
| Australia DFAT Consolidated List | both | B | Australia | bulk (XML/CSV) | none | none published | **CC BY 4.0** (except Coat of Arms / 3rd-party; verified 2026-06-21) | yes — redistribute w/ attribution | indefinite | ✅ wire now (attribute "DFAT — www.dfat.gov.au") | dfat.gov.au/about-us/about-this-website/copyright |
| FinCEN Beneficial Ownership (BOI) | claude | A | US | none (non-public) | n/a | n/a | CTA Access & Safeguards Rule | **no** — non-public by law | n/a | ❌ avoid (domestic data no longer collected since 2025) | fincen.gov/boi-faqs |

### 2b. Company registries / LEI / beneficial ownership

| name | agree | tier | geo | access | auth | rate limit | licence | redistribution | retention | verdict | basis_url |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GLEIF LEI | both | A | global (~2.7M LEIs) | REST API + Golden Copy bulk | none | fair-use | CC0 1.0 | yes — freely | indefinite | ✅ wire now | gleif.org/.../lei-data-terms-of-use |
| OpenCorporates | both | A | ~140 jurisdictions | API + bulk (contract) | free key (share-alike) / paid | tiered | ODbL 1.0 | conditional — free use forces ODbL share-alike + attribution; commercial needs paid; **no scraping** | per_license | ⚠️ conditional | opencorporates.com/terms-of-use-2 |
| Open Ownership (BODS) | both | A | UK PSC/ROE + GLEIF L1/L2 | bulk (CSV/SQLite/Parquet) + BigQuery | none | none | CC0 1.0 | yes | indefinite | ⚠️ CC0 but Register decommissioned 2024-11; snapshots only | bods-data.openownership.org |
| UK Companies House | both | B | UK | REST + Streaming + bulk | free key | 600 req / 5 min | OGL v3.0 | yes — redistribute/commercial w/ attribution (mind UK GDPR on PSC PII) | indefinite | ✅ wire now | developer.company-information.service.gov.uk |
| EU BRIS | both | B | EU-27 + EEA | manual (e-Justice portal; **no API/bulk**) | none | none | federated national-register terms | conditional | session_only | ⚠️ authoritative index, web-only | e-justice.europa.eu/legal-notice_en |
| India MCA (MCA21) | both | B | India | data.gov.in OGD bulk/API + V3 portal | free key (OGD) / login | portal: 5 cos/txn | GODL-India (OGD) | conditional — GODL redistributable **minus PII**; portal docs copyright-restricted | per_license | ⚠️ use GODL dataset, not portal scrape | data.gov.in/catalog/company-master-data |

### 2c. Securities filings / exchanges

| name | agree | tier | geo | access | auth | rate limit | licence | redistribution | retention | verdict | basis_url |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SEC EDGAR | both | B | US | full-text (EFTS) + data.sec.gov JSON + bulk | none | **10 req/s**, descriptive User-Agent required | US-gov PD | yes (don't imply SEC affiliation; watch filer-supplied copyrighted exhibits) | indefinite | ✅ wire now | sec.gov/.../accessing-edgar-data |
| EDINET (Japan FSA) | both | B | Japan | REST API v2 + UI | free key | not published | Public Data License v1.0 | yes — commercial reuse + redistribution w/ attribution | per_license (~10 yr) | ✅ wire now | disclosure2dl.edinet-fsa.go.jp |
| SEDAR+ (Canada) | both | B | Canada | manual portal (**no API**; 30 docs/batch) | none | ToU **bans automation/scraping** | SEDAR+ ToU | no — limited unaltered extracts only | per_license | ⚠️ primary but no automated/bulk path | sedarplus.ca |
| ASX | both | B | Australia | portal; paid feed | none / paid | ToU bans spiders | ASX ToU | no — personal/non-commercial; redistribution = paid MarketSource | session_only | ❌ avoid | asx.com.au/legals/terms-of-use |
| SGX | both | B | Singapore | portal; paid feed | none / licence | unknown | SGX Market Data Policy | conditional — store/redistribute needs SGX Redistributor licence | per_license | ⚠️ read free, licence to store | sgx.com/securities/company-announcements |
| HKEXnews | both | B | Hong Kong | portal; paid feed | none | ToU bans automation + TDM | HKEX T&C | no — reproduction/distribution barred | per_license | ❌ avoid | hkexnews.hk |

### 2d. Patents / trademarks / courts

| name | agree | tier | geo | access | auth | rate limit | licence | redistribution | retention | verdict | basis_url |
|---|---|---|---|---|---|---|---|---|---|---|---|
| USPTO Open Data Portal | claude | A | US | REST/JSON + bulk; PatentsView | free key (ID.me) | ~4–15 req/s | US-gov PD | yes — freely distributable | indefinite | ✅ wire now | data.uspto.gov/apis/getting-started |
| EPO Open Patent Services (OPS) | claude | A | global (DOCDB/INPADOC) | REST API (OAuth) | free key | 3.5 GB/week free | OPS T&C + Fair Use Charter | conditional — within Fair Use Charter; confirm per dataset | per_license | ✅ wire now | epo.org/.../web-services/ops |
| WIPO PATENTSCOPE | both | A | global | free UI (manual) / paid PCT Webservice | none / paid | >10 actions/min = excessive; no automation | WIPO DB Terms | no (free) — bulk/store/redistribute banned | session_only | ❌ free tier / ⚠️ paid only | wipo.int/.../terms_patentscope |
| WIPO Global Brand Database | codex | A | global trademarks | free UI (manual) | none | service-managed | WIPO GBDB terms | no (at scale) | session_only | ❌ avoid (use EUIPO/USPTO TM) | wipo.int/.../global-brand-database/terms |
| CourtListener / RECAP | both | A | US fed + many state | REST API v4 + bulk CSV | free key | 5/min, 50/hr, 125/day | CC BY-ND 4.0 | conditional — verbatim w/ attribution OK; **BY-ND forbids redistributing derived/normalized** | per_license | ⚠️ trap for parsed dockets | courtlistener.com/help/api |

### 2e. Market research / economic / trade statistics

| name | agree | tier | geo | access | auth | rate limit | licence | redistribution | retention | verdict | basis_url |
|---|---|---|---|---|---|---|---|---|---|---|---|
| World Bank Open Data / WDI | both | A | global | REST API + bulk | none | fair-use | CC BY 4.0 | conditional — incl. commercial w/ attribution; clear third-party indicators | per_license | ✅ wire now | datacatalog.worldbank.org/public-licenses |
| OECD Data / SDMX | both | A | OECD + partners | SDMX REST + Data Explorer | none | **60 downloads/hr**; >20 q/min blocked | CC BY 4.0 (from 2024-07-01) | conditional — w/ citation; clear third-party data | per_license | ✅ wire now (enforce limits) | oecd.org/.../terms-conditions |
| IMF Data | both | A | global | SDMX REST (v3 keyed / legacy keyless) | free key (v3) | APIM throttle | IMF Copyright & Terms | **no/conditional** — no resell/derivative; commercial needs written permission | per_license | ⚠️ authoritative, redistribution restricted | imf.org/en/about/copyright-and-terms |
| UN Comtrade | both | A | global (~200 reporters) | REST API + bulk | free key (full) | ~500 calls/day free | UN Comtrade Licence | **no/conditional** — internal use; redistribution needs UNSD permission (may carry fees) | per_license | ⚠️ free tier OK, no redistribution | comtrade.un.org/licenseagreement |
| Eurostat | both | A | EU | REST API + bulk | none | none published | EC reuse / CC BY-equiv | yes | indefinite | ✅ wire now | ec.europa.eu/eurostat |
| data.europa.eu | both | A | EU portal | API + SPARQL + bulk | none | none published | dataset-specific | conditional — per-dataset rights | per_license | ⚠️ discovery layer | data.europa.eu |
| US Census Bureau APIs | codex | B | US | REST API + bulk | optional key | ~500 q/IP/day no key | US-gov PD | yes | indefinite | ✅ wire now | census.gov/data/developers.html |
| US BEA API | codex | B | US | REST API | free key | none published | US-gov PD | yes | indefinite | ✅ wire now | bea.gov/API/signup |
| BLS Public Data API | codex | B | US | REST API | optional key | 25/day no key, 500/day keyed | US-gov PD | yes | indefinite | ✅ wire now | bls.gov/developers |
| UK ONS API | both | B | UK | REST API + bulk | none | none published | **OGL v3.0** (verified 2026-06-21) | yes | indefinite | ✅ wire now | ons.gov.uk/help/termsandconditions |
| FRED (St. Louis Fed) | claude | B | US/global | REST API | free key | fair-use | FRED Services T&C | conditional — attribution; some series carry provider terms | per_license | ✅ wire now (attribute) | fred.stlouisfed.org |

### 2f. Signals / knowledge graphs

| name | agree | tier | geo | access | auth | rate limit | licence | redistribution | retention | verdict | basis_url |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Wikidata | claude | A | global | SPARQL/REST + dumps | none (UA expected) | 60 s query/min | CC0 (structured) | yes | indefinite | ✅ wire now (verify accuracy) | wikidata.org/wiki/Wikidata:Licensing |
| OpenAlex | claude | A | global scholarly/org | REST API + S3 bulk | **free key (since 2026-02-13)** | ~100 req/s, budget model | CC0 | yes | indefinite | ✅ wire now (provision key) | developers.openalex.org |

---

## 3. Tier C — pointers (catalogued, not deep-vetted)

National company registries: **Handelsregister/Unternehmensregister** (DE), **Bundesanzeiger** (DE, financials), **INPI RNE** (FR, open), **Infogreffe** (FR), **Registro Imprese** (IT), **Registradores** (ES), **KVK** (NL), **KBO/BCE** (BE, open), **CVR/Virk** (DK, open), **Brønnøysund** (NO, open REST), **Bolagsverket** (SE), **PRH/avoindata** (FI, open), **LBR** (LU), **Zefix** (CH, open REST), **Firmenbuch** (AT), **CRO** (IE), **KRS** (PL, open), **ARES** (CZ, open), **e-Business Register** (EE, open), **Receita Federal CNPJ** (BR, open bulk), **CIPC** (ZA), **GSXT** (CN, captcha), Korea **DART** (open API).

Exchanges / disclosure: **Euronext**, **Deutsche Börse/Xetra**, **LSE RNS**, **Borsa Italiana**, **B3** (BR), **JPX/TDnet** (JP, open), **KRX/KIND** (KR), **TWSE MOPS** (TW, open), **Bursa Malaysia**, **IDX** (ID), **Tadawul** (SA).

Sanctions/watchlists: **Switzerland SECO**, **Japan METI/MOF + End-User List**, **INTERPOL Red Notices**, **World Bank Debarred Firms**.

Courts: **PACER** (US, paid dockets).

Market/econ/IP: **EU TED** (procurement, open API), **FRED** (promoted to §2e), **UK ONS** (promoted), **Japan e-Stat** (open, key), **Statistics Canada** (open), **UNCTADstat** (trade/FDI), **US data.gov / UK data.gov.uk** (portals), **EUIPO** (TM/designs, open API), **Lens.org** (patents, tiered), **Google Patents Public Data** (BigQuery), **JPO J-PlatPat** (JP).

---

## 4. Proposed new `source_class` values

To add to `references/source_priority_rules.md` when connectors land (all Tier 1 PRIMARY except `adverse_media_event`/`knowledge_graph` = signal, `economic_indicator`/`trade_statistics` = secondary):

- `lei_registry` — legal-entity-identifier registries (GLEIF). Identity/relationship graph keyed on LEI, distinct from `company_registry`.
- `ubo_register` — beneficial-ownership registers (Open Ownership, FinCEN BOI).
- `pep_list` — politically-exposed-persons lists (OpenSanctions PEPs); distinct from `sanctions_list`/`watchlist`.
- `adverse_media_event` — structured news/event databases for adverse-media screening (GDELT); distinct from `financial_media`.
- `economic_indicator` — macro/development series (World Bank, OECD, IMF, FRED, Census/BEA/BLS, Eurostat).
- `trade_statistics` — bilateral trade flows (UN Comtrade, UNCTADstat).
- `knowledge_graph` — open entity/relationship graphs (Wikidata, OpenAlex).

---

## 5. Connector plan (ranked: coverage × ease × verdict)

The skill wires only **SEC EDGAR** (`cdd/extract/edgar.py`) and **OFAC SDN** (`cdd/extract/sanctions.py`) today. Ranked backlog for `cdd/extract/`:

### Priority 1 — clean licence, easy API, high coverage (build first) — ✓ WIRED 2026-06-22
1. **Sanctions multi-list parsers** — ✓ wired (`cdd/extract/sanctions.py`): **EU FSF**, **UK FCDO** (*replaces the dead OFSI list*), **BIS CSL** (REST), **UN Consolidated** (tagged `retention_policy: session_only` in `LIST_METADATA` — screen, don't warehouse). Closes the "only OFAC parses today" gap.
2. **GLEIF LEI** — ✓ wired (`cdd/extract/gleif.py`): REST `api.gleif.org/api/v1/lei-records`, JSON, no auth, CC0.
3. **UK Companies House** — ✓ wired (`cdd/extract/companies_house.py`): REST + free key (HTTP Basic via `CDD_COMPANIES_HOUSE_KEY`), OGL.
4. **GDELT** — ✓ wired (`cdd/extract/gdelt.py`): DOC 2.0 artlist JSON, adverse-media screening (`adverse_media_event`).

### Priority 2 — high value, minor friction
5. **US econ pack** — `extract/econ.py`: Census + BEA + BLS + FRED (+ World Bank, OECD-SDMX, Eurostat). All public-domain/CC-BY. Powers `market_intelligence.md`. *Effort: M (shared SDMX/REST client).*
   - ✓ **BLS + World Bank wired & live-smoked** (keyless, public-domain/CC-BY). Pending sub-batches: **FRED/BEA/Census** (require free API keys to live-verify — Census now key-gated too), **OECD/Eurostat** (SDMX/JSON-stat, keyless but heavier parsers).
6. **Patents** — `extract/patents.py`: USPTO ODP + EPO OPS (OAuth). Public-domain/Fair-Use; **skip WIPO PATENTSCOPE** (terms ban automation). *Effort: M.*
7. **EDINET (JP)** — REST v2 + key, PDL 1.0. Natural given the Takeda e2e baseline. *Effort: S–M.*
8. **Wikidata / OpenAlex** — CC0 enrichment for entity disambiguation. *Effort: S each.*

### Priority 3 — conditional (gate behind licence/config)
9. **OpenSanctions / OpenSanctions PEPs** — best screening graph, but CC-BY-NC → **requires a paid licence for commercial DD**. Wire as an *optional, key-gated* backend; do not store/redistribute under the free NC tier. *Effort: M.*
10. **OpenCorporates** — 140-jurisdiction registry coverage, but ODbL share-alike or paid; no scraping. Optional/key-gated. *Effort: M.*

### Do NOT build (catalogued as ❌ / no automated path)
ASX, HKEXnews (scraping + redistribution barred), SEDAR+ (ToU bans automation — use a licensed feed or manual), WIPO PATENTSCOPE/Global Brand Database (free-tier terms forbid bulk/store), FinCEN BOI (non-public by law). For these, record `retrieval_status: unavailable` per the existing legal/ToS rules rather than attempting retrieval.

---

## 6. Standing caveats (re-check on each run)

1. **Licences drift** — every row carries an as-of date (2026-06-21); re-verify before a build.
2. **Aggregator ≠ primary** — OpenCorporates/OpenSanctions/Open Ownership impose their *own* (often stricter) licence atop public upstream data. The aggregator's terms govern what you may store/redistribute.
3. **"Public domain" is not uniform** — OFAC/BIS/UK/US-gov = redistributable; **UN Consolidated, UN Comtrade, IMF, and Canada CACSL = all-rights-reserved / permission-gated**, ingest-to-screen only.
4. **Stale-pointer actions** — UK OFSI list withdrawn 2026-01-28 → FCDO; BIS CSL REST now needs a free key; OpenAlex now key-gated.
5. **Derived-data traps** — CourtListener is **BY-ND** (rehost verbatim only, no parsed/normalized redistribution); **Canada CACSL** GC terms require written permission for *any* normalization/adaptation as well as commercial redistribution. A DD pipeline that parses these into structured artifacts for a client deliverable trips both.
6. **Verification status (2026-06-21 pass)** — UK ONS (OGL v3.0) and DFAT (CC BY 4.0) **confirmed** against primary pages; Canada CACSL **corrected** to GC standard terms (not OGL-Canada) per canada.ca/en/transparency/terms.html. Government sites that blocked automated fetch (GAC, dfat.gov.au page body) were corroborated via the departments' whole-of-government licensing statements. Residual unverified items: a few Codex-arm rate-limit figures (marked in-row) — low risk, confirm at connector-build time.
