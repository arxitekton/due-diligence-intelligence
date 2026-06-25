# Sanctions Screening

## Goal
Screen the entity graph against official sanctions, export-control, and watchlists; assess
sanctioned-country and region exposure; characterise Russia/Belarus operations status; and
identify PEP and serious adverse-media signals among key principals. Write every finding as an
`extracted_artifact` with full lineage. Obey all anti-hallucination constraints — a sanctions
hit requires an exact official list entry; "no match" is never "clean".

## Inputs
`company_slug`, `run_id`, the entity graph constructed in
`prompts/corporate_structure_extraction.md` (company, legal entities, subsidiaries, ≥50%-owned
affiliates, key principals/beneficial owners), raw source files in
`output/companies/{slug}/runs/{run_id}/raw_sources/`, `source_registry.jsonl`,
`references/sanctions_screening_rules.md`, and `references/anti_hallucination_rules.md`.

## Procedure

### A. List Screening

1. **Enumerate the entity graph.** Only assert an entity or ownership link that comes from a
   filing, company registry record, or court filing. Do not infer subsidiaries from brand
   similarity, shared address, or executive overlap without a registered source.
   Apply the OFAC 50% rule: any entity ≥50%-owned (directly or indirectly) by a designated
   person or entity is treated as effectively designated, even if not listed by name — screen
   all such entities. Ownership percentages must derive from a filed source; estimated or
   inferred percentages are `[INFERENCE]`.
   To corroborate entity identity and surface direct/ultimate parent links, the
   `cdd.extract.gleif` helper (`search_by_name`) resolves legal names to LEI records
   (canonical legal name, jurisdiction, status) and GLEIF L1/L2 parent relationships — use it
   to confirm/normalise names before screening. It does NOT establish ownership percentages;
   those still require a filed source.

2. **Screen each entity** against every list in the authoritative set. The
   `cdd.extract.sanctions` helper (installed with the `extract` extra) now **fetches, parses,
   and name-matches all of these** via `fetch_and_screen(name, list_id=...)` — this is the
   PREFERRED mechanism. **Set `CDD_HTTP_USER_AGENT` to a real org + contact first** (gov
   endpoints reject requests without it). Supported `list_id`s and their live sources:
   - `OFAC-SDN` — OFAC Specially Designated Nationals
   - `EU-CONSOLIDATED` — EU Consolidated Financial Sanctions File (European Commission)
   - `UK-FCDO` — UK Sanctions List (FCDO). **The OFSI consolidated list was withdrawn
     2026-01-28 — do not use the old `assets.publishing.service.gov.uk` CSV.**
   - `UN-CONSOLIDATED` — UN Security Council Consolidated List (1267/1989/2253 & related).
     **Ingest-to-screen ONLY: UN terms forbid redistribution — screen, then do NOT warehouse
     the raw bytes** (`LIST_METADATA["UN-CONSOLIDATED"]["retention_policy"] == "session_only"`).
   - `BIS-CSL` — BIS Entity List + Consolidated Screening List (needs a free ITA API key for
     the REST endpoint; `CDD_BIS_API_KEY` if configured).

   Also screen **OFAC Consolidated (non-SDN)** (`https://www.treasury.gov/ofac/downloads/consolidated.csv`)
   directly — it is not yet in the helper.

   Screen each entity using its legal name AND all known aliases/transliterations. NOTE the
   matcher's guard: a single-token query (e.g. a bare surname) only produces `exact` matches;
   `partial` (token-subset) matching requires ≥2 tokens — so pass FULL names, not lone words,
   or real hits listed under a longer official name will be missed. The helper is an aid: if it
   is unavailable for a list, the agent MUST screen directly from that list's official portal /
   downloadable file. Its absence never excuses skipping a list.

3. **Record every list screened** — list name, URL or portal used, and the as-of/publication
   date of the list version consulted. This is mandatory even when no match is found.

4. **Record every hit** with:
   - `list`: e.g. `"OFAC-SDN"`
   - `programme`: sanction programme name (e.g. `"RUSSIA-EO14024"`)
   - `entry_id`: the list's own identifier
   - `matched_entity`: the entity name from the entity graph that triggered the hit
   - `match_type`: `"exact"` or `"partial"` (per `screen_name` semantics)
   - `confidence`: float 0–1 (exact primary-name match → high; partial/transliteration → lower)
   - `list_as_of`: ISO8601 date of the list version consulted

5. **Disambiguation.** Common names, transliterated names, and names with multiple variants
   produce `partial` matches that are candidates for manual review, NOT confirmed hits.
   A `partial` match must carry: the basis for the match, the specific list entry, and an
   explicit note that it is unconfirmed. Never assert a hit from a partial match alone or from
   secondary media coverage without a corresponding official list entry.

6. **"No match" reporting.** Absence of a match must be reported as:
   `"no match on [OFAC-SDN, OFAC-Consolidated, EU-Consolidated, UK-FCDO, UN-Consolidated,
   BIS-CSL] as of [date]"`. It must NEVER be rendered as "clean," "not sanctioned,"
   or "clear." Sanctions lists are updated frequently; no-match status is point-in-time only.

### B. Sanctioned-Country / Region Exposure

7. **Jurisdictions of concern** (per `references/sanctions_screening_rules.md`):
   Russia, Belarus, Iran, North Korea, Syria, Cuba, and the Ukrainian territories of Crimea,
   Donetsk People's Republic (DNR), and Luhansk People's Republic (LNR).

8. **Source for exposure:** the company's own primary filings only — geographic/segment revenue
   disclosures, risk factors, MD&A, subsidiary and joint-venture lists, supplier/customer
   disclosures, and exchange filings. Do not assert exposure that is not disclosed in a primary
   filing. Quantify only what is disclosed (e.g. "Russia segment revenue: $X, FY202X
   [10-K, §Geographic Segments, p.47]"); use `null` for undisclosed amounts.

9. **Record per jurisdiction:** disclosed revenue, assets, employees, operational entities, key
   suppliers/customers, and the filing section from which each figure derives.

### C. Russia / Belarus Operations Status

10. **Assess exit/continuity status** as disclosed — one of:
    - `"exited"` — company has announced and completed a full exit
    - `"suspended"` — operations paused; assets/entities remain
    - `"scaled_back"` — partial wind-down or material reduction disclosed
    - `"continued"` — operations ongoing with no stated material change
    - `"unclear"` — insufficient disclosure to determine

    The status determination must be anchored to a primary filing (annual report, 8-K, earnings
    call transcript, exchange filing) or a direct company press release. Do not determine status
    from tracker databases or media alone.

11. **Secondary trackers** (e.g. Yale CELI "Leave Russia" list, KSE Institute tracker):
    these are SIGNAL-tier sources. Record their classification as a secondary signal with
    explicit attribution: `"[SIGNAL — Yale CELI list, retrieved YYYY-MM-DD]"`. Never use a
    tracker classification as the primary basis for asserting exited/continued status; it must
    be corroborated by a primary source or clearly marked `[INFERENCE]`.

### D. PEP / Adverse Media

12. **Politically exposed persons (PEPs):** review disclosed owners, directors, and key
    principals for PEP status (current or former senior government official, state-owned-
    enterprise executive, or immediate family/close associate of such a person). Sources:
    primary filings (proxy statements, 20-F related-party disclosures), company registries,
    named secondary sources (Bloomberg, Reuters profiles). PEP status is a risk flag, not a
    sanction; record it as `evidence` with citation, not as an adverse finding per se.

13. **Adverse media:** identify serious adverse-media items — enforcement actions, fraud,
    corruption, financial crime, money laundering, export-control violations — from reputable
    named sources (financial media, government press releases, court filings). Apply strict
    fact-vs-allegation discipline:
    - A concluded enforcement action, conviction, or regulatory order is `evidence` (cite
      the official document or a named secondary source).
    - An allegation, indictment, or investigation in progress is an allegation: attribute it
      explicitly (`"According to [source], …"`) and tag it `[INFERENCE]` if it goes beyond
      the published text. Never assert an allegation as a concluded fact.

    To DISCOVER candidate adverse-media items, the `cdd.extract.gdelt` helper
    (`search_adverse_media(query)`) queries the open GDELT event database. Treat its results as
    **SIGNAL-tier leads only** (`source_class: adverse_media_event`) — never as a finding in
    themselves: follow each lead to the underlying reputable named source and apply the
    fact-vs-allegation discipline above before recording anything. GDELT is rate-limited to
    ~1 request / 5s; on throttle it raises `ExtractorUnavailable` (a rate-limit signal, NOT
    "no adverse media") — back off and retry, do not interpret the error as a clean result.

14. **Separation of fact and inference:** sanctions hits from official lists are `fact` claims
    (cite the list entry). Disclosed operational exposure is `fact` (cite the filing). PEP
    status and adverse media that rest on secondary sources are `evidence`. Any conclusion that
    combines multiple signals or requires interpretive reasoning is `[INFERENCE]`.

### E. Artifact Creation

15. Compose one or more `extracted_artifact` JSON files with:
    - `artifact_id`: `art_` + 16 hex chars
    - `schema_version`: `"1.0"`
    - `company_id`: `{slug}`
    - `run_id`: `{run_id}`
    - `artifact_type`: one of `"sanctions_screening"`, `"sanctioned_country_exposure"`,
      `"export_control_exposure"`, `"pep_adverse_media"`
    - `source_id`: `src_` ID from `source_registry.jsonl` (list URL or filing source)
    - `original_format`: MIME type (e.g. `"text/csv"`, `"application/pdf"`)
    - `retrieved_at` / `extracted_at`: ISO8601 UTC
    - `confidence`: float 0–1
    - `lineage`:
      - `source_snapshot_id`: `event_id` of the `retrieved` event
      - `content_path`: relative path to raw source
      - `locator`: e.g. `{"list": "OFAC-SDN", "as_of": "YYYY-MM-DD"}` or
        `{"section": "Geographic Segments", "item": "7", "page": 47}`
      - `snippet`: verbatim excerpt or CSV row that supports the extraction
      - `extraction_prompt`: `{"name": "sanctions_screening", "version": "1.0"}`
    - `value`: see Output contract below
    - `notes`: gaps, partial matches requiring manual review, missing disclosures, or pending
      information; inferences tagged `[INFERENCE]`

16. Write each artifact to
    `output/companies/{slug}/runs/{run_id}/structured/{artifact_id}.json`.

17. Record an `extracted` event for each artifact:
    ```
    python scripts/update_artifact_registry.py \
      --log output/companies/{slug}/artifact_registry.jsonl \
      --run-id {run_id} --artifact-id {artifact_id} --event-type extracted \
      --event-time {ISO} \
      --payload '{"artifact_type":"...","source_id":"...","content_path":"structured/{artifact_id}.json"}'
    ```

## Output contract

One or more `extracted_artifact` JSON files (artifact types: `sanctions_screening`,
`sanctioned_country_exposure`, `export_control_exposure`, `pep_adverse_media`) in `structured/`,
each validating against the `extracted_artifact` schema with a complete `lineage` block.
Corresponding `extracted` events in `artifact_registry.jsonl`.

### `value` field shapes

**`sanctions_screening`**
```json
{
  "lists_screened": [
    {
      "list": "OFAC-SDN",
      "url": "https://www.treasury.gov/ofac/downloads/sdn.csv",
      "as_of": "YYYY-MM-DD",
      "entities_screened": ["Company Name", "Subsidiary A", "Person B"]
    }
  ],
  "hits": [
    {
      "list": "OFAC-SDN",
      "programme": "RUSSIA-EO14024",
      "entry_id": "12345",
      "matched_entity": "Company Name",
      "match_type": "exact",
      "confidence": 0.95,
      "list_as_of": "YYYY-MM-DD"
    }
  ],
  "no_match_summary": "No match on [list names] as of [date]"
}
```

**`sanctioned_country_exposure`**
```json
{
  "country_exposure": {
    "Russia": {
      "disclosed_revenue": null,
      "disclosed_assets": null,
      "operational_entities": ["Subsidiary RU"],
      "key_suppliers": [],
      "key_customers": [],
      "source_locator": {"section": "Geographic Segments", "page": 47}
    }
  },
  "russia_status": {
    "status": "exited",
    "effective_date": "2022-10-01",
    "source_locator": {"section": "Risk Factors", "page": 22},
    "secondary_signal": "[SIGNAL — Yale CELI list, retrieved YYYY-MM-DD]"
  }
}
```

**`export_control_exposure`**
```json
{
  "bis_hits": [],
  "other_export_control_issues": null,
  "no_match_summary": "No match on BIS Entity List as of YYYY-MM-DD"
}
```

**`pep_adverse_media`**
```json
{
  "pep": [
    {
      "person": "Jane Doe",
      "role": "Director",
      "pep_basis": "Former Deputy Minister of Finance, Country X",
      "source": "secondary/bloomberg-profile",
      "confidence": 0.8
    }
  ],
  "adverse_media": [
    {
      "subject": "Company Name",
      "category": "enforcement",
      "summary": "SEC consent order for …",
      "status": "concluded",
      "source": "primary/sec-release-2023-01-15",
      "citation": "[art_<hex16>]"
    }
  ]
}
```

## Hard rules
- Obey all rules in `references/anti_hallucination_rules.md` and
  `references/sanctions_screening_rules.md`.
- A sanctions or export-control hit requires an exact official list entry. Record: list name,
  programme, entry id, matched entity name, match_type, and the list's as-of date. Never assert
  a hit from secondary media alone.
- "No hit found" ≠ "not sanctioned" / "clean." Report as "no match on [lists] as of [date]."
- Screen the entity graph, not just the top-level company name.
- Separate fact (official list entry / filed disclosure) from inference. Tag inference
  `[INFERENCE]`. Allegations are attributed and tagged, never asserted as fact.
- Missing disclosures → `null`, never estimated.
- `cdd.extract.sanctions` (`fetch_and_screen`) is the preferred aid and covers OFAC-SDN,
  EU-CONSOLIDATED, UK-FCDO, UN-CONSOLIDATED, and BIS-CSL; `cdd.extract.gleif` aids entity
  resolution and `cdd.extract.gdelt` aids adverse-media discovery. These are aids — their
  absence does not excuse skipping any list, and GDELT/GLEIF results are signal-tier leads,
  never findings on their own. UN list data is screen-only — never warehoused or redistributed.

## Hand-off
`evidence_validation.md` validates all artifacts in `structured/`.
`dossier_generation.md` renders the new **Sanctions & Compliance Exposure** section from
`sanctions_screening`, `sanctioned_country_exposure`, `export_control_exposure`, and
`pep_adverse_media` artifacts.
