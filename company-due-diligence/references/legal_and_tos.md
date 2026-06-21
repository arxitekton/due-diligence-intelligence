# Legal and Terms of Service Rules

## Core Rule

Respect site Terms of Service and robots directives. Do not bypass paywalls, authentication gates, or access controls. Do not circumvent rate limits. Record the access basis for every source at retrieval time. These are not soft guidelines; they are hard constraints on what the engine is permitted to retrieve and retain.

---

## Per-Source Access Metadata

Every entry in `source_inventory.sources` must record the following access metadata fields at retrieval time:

**`access_basis`** — the legal or contractual basis under which the source was accessed. Use one of:
- `"public_web"` — freely accessible without authentication on the open web, and the site's ToS permits programmatic access or research use.
- `"regulatory_database"` — a public regulatory database (SEC EDGAR, Companies House, USPTO, etc.) where public access is explicitly provided by the regulator.
- `"licensed_subscription"` — accessed under a subscription or data license held by the user or organization (e.g. Bloomberg terminal, PitchBook, analyst research platform). The specific license or contract reference must be recorded in `license_or_terms_ref`.
- `"company_published_ir"` — investor relations materials published by the company for public access (earnings releases, annual report PDFs linked from the IR page, earnings call replays).
- `"app_store_listing"` — app store listings accessed via the public app store browsing interface.
- `"government_record"` — government databases, court records, or patent offices where public search is provided by statute.

**`license_or_terms_ref`** — the specific ToS URL, license agreement identifier, or subscription tier that governs the access. For `public_web` sources, this is the ToS URL of the site (e.g. `"https://example.com/terms"`). For `licensed_subscription` sources, the license or account identifier. For regulatory databases, the regulator's data use policy URL. Set `null` only when `access_basis` is `"regulatory_database"` or `"government_record"` and no specific terms document is applicable.

**`robots_observed`** — boolean. `true` if the agent checked `robots.txt` before retrieval and the target path was not disallowed. `false` if `robots.txt` was not checked. For regulatory databases and licensed platforms that do not publish `robots.txt`, record `true` with a note. Never set `false` and proceed with retrieval; if `robots.txt` disallows crawling, the source must not be retrieved.

**`retention_policy`** — the retention policy governing the stored copy. One of:
- `"indefinite"` — no retention restriction from the source's ToS; raw bytes may be stored for the research record.
- `"session_only"` — the source's ToS restricts retention; raw bytes must not be persisted beyond the research session. Extract structured data immediately; do not retain the raw bytes.
- `"per_license"` — retention is governed by the subscription license; follow the license terms.
- `null` — retention policy not determined; default to conservative (`session_only`) treatment.

**`export_restrictions`** — free-text field for any geographic, sectoral, or persona-based export restrictions that apply to the data. For example, some licensed financial databases restrict redistribution to third parties. Record the restriction text or `null` if none applies.

---

## PII and Sensitivity Classification

Extracted artifacts must carry a `sensitivity_class` when the source or the extracted data contains personal data or commercially sensitive information:

| `sensitivity_class` | Content type | Handling |
|---|---|---|
| `public` | Company-level data with no PII, from publicly accessible sources | No restrictions |
| `personal_data` | Includes names, contact details, employment records, or other personal information about individuals | Must be redacted before export to third parties; retain only what is necessary for the research purpose |
| `commercially_sensitive` | Non-public commercial data accessed under license (e.g. premium analyst reports, licensed databases) | Do not redistribute; citation is permitted but verbatim excerpt redistribution may violate the license |
| `restricted_export` | Subject to export control regulations or cross-border data transfer restrictions | Consult legal before storing or transmitting |

When extracting from secondary sources such as analyst reports or licensed databases, classify extracted content as `commercially_sensitive` unless the license explicitly permits unrestricted redistribution.

---

## Safe-Export (Redaction) Modes

Before exporting any artifact or dossier to a third party:

1. Check `sensitivity_class` for every artifact cited.
2. If any artifact is `personal_data`: redact the personal data fields in the export copy. Do not redact the stored artifact; redact only the export view.
3. If any artifact is `commercially_sensitive`: verify that the applicable license permits redistribution of the extracted content. If it does not, replace verbatim excerpts with paraphrases and cite the source without reproducing licensed text.
4. If any artifact is `restricted_export`: halt and seek legal guidance before exporting.

The safe-export step is a publishing concern, not an extraction concern. The stored artifact must always contain the full evidence. The export view applies redactions on output.

---

## Robots and Rate Limits

Before retrieving any source via HTTP:

1. Fetch `robots.txt` from the root of the domain. Cache the result for the duration of the run.
2. Check whether the target path is disallowed for the user-agent. If disallowed, record the source in the inventory with `retrieval_status: "unavailable"`, `notes: "robots.txt disallowed"`, and do not fetch.
3. Observe the `Crawl-delay` directive if present. Do not retrieve sources at a rate that exceeds one request per crawl-delay interval for the same domain.
4. Do not use rotating proxies, user-agent spoofing, or other techniques to circumvent rate limits or access controls.

SEC EDGAR provides a dedicated bulk data API and specifies a rate limit of 10 requests per second for automated access. Use the EDGAR full-text search API or bulk download endpoints rather than scraping the HTML interface. **SEC also rejects requests without a descriptive User-Agent that includes a contact** — set `CDD_HTTP_USER_AGENT` to a real value (e.g. `"Acme Diligence admin@acme.com"`) before fetching, or pass `user_agent=` to `cdd.extract.fetch.get`; otherwise EDGAR returns HTTP 403 and the source is recorded `unavailable`.

---

## What Not to Do

- Do not attempt to access content behind a login wall without a valid, licensed credential.
- Do not cache or retain content whose ToS prohibits storage beyond a session.
- Do not redistribute licensed database content (analyst reports, PitchBook data, Bloomberg data) in artifact form to parties who do not hold the same license.
- Do not treat paywall bypass or cached/mirrored copies as equivalent to legitimate source access; the `access_basis` must reflect how the content was actually obtained.
- Do not record a source as `access_basis: "public_web"` if the site's ToS explicitly prohibits automated or research scraping.
