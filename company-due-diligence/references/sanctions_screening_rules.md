# Sanctions Screening Rules

Companion reference to `prompts/sanctions_screening.md`. These rules are binding — every
constraint here overrides an agent's default behaviour when the two conflict.

---

## 1. Official Lists and Authoritative Sources

Screen against all six lists on every run. Record the URL or portal used and the
as-of/publication date for each list consulted.

| List | Issuer | Authoritative source URL / portal |
|---|---|---|
| OFAC Specially Designated Nationals (SDN) | US Treasury OFAC | `https://www.treasury.gov/ofac/downloads/sdn.csv` (CSV) · `https://sanctionssearch.ofac.treas.gov/` (search portal) |
| OFAC Consolidated (non-SDN) | US Treasury OFAC | `https://www.treasury.gov/ofac/downloads/consolidated.csv` (CSV) |
| EU Consolidated Sanctions List | European Commission | `https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/content` (Financial Sanctions Files portal, requires token) |
| UK OFSI Consolidated List | UK HM Treasury / OFSI | `https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/consolidated-list.csv` (CSV) · `https://www.gov.uk/guidance/financial-sanctions-consolidated-list-of-targets` (portal) |
| UN Consolidated List | UN Security Council | `https://www.un.org/securitycouncil/content/un-sc-consolidated-list` (1267/1989/2253 committees and related) |
| BIS Entity List (export-control) | US Commerce BIS | `https://www.bis.doc.gov/index.php/policy-guidance/lists-of-parties-of-concern/entity-list` · `https://efts.bis.doc.gov/complete-search-of-existing-actions?searchOptions=Y&sEntry=entity-list` |

Additional lists that may be relevant for specific industries or jurisdictions (e.g. OFAC
Sectoral Sanctions, BIS Denied Persons List, BIS Unverified List) should be consulted when
the company's sector or geography warrants it; note them in `known_gaps` if not screened.

---

## 2. Sanctioned-Country and Region Set

The following jurisdictions and territories are subject to comprehensive or broad US/EU/UK
sanctions programmes. Assess exposure for all of them in every screening run:

| Jurisdiction | Programme examples |
|---|---|
| Russia | OFAC Russia-related EOs (EO14024, EO13662 etc.); EU Russia sanctions; UK OFSI |
| Belarus | OFAC Belarus programme; EU Belarus sanctions |
| Iran | OFAC Iran programme (ITSR); EU Iran sanctions |
| North Korea | OFAC North Korea programme (DPRK EOs); UN DPRK committee |
| Syria | OFAC Syria programme (SYSR); EU Syria sanctions |
| Cuba | OFAC Cuba programme (CACR) |
| Crimea (Ukraine) | OFAC Crimea directive; EU Crimea measures |
| Donetsk People's Republic (DNR) | OFAC Ukraine/Russia-related executive orders |
| Luhansk People's Republic (LNR) | OFAC Ukraine/Russia-related executive orders |

This list reflects the current major programmes. Check for newly designated regions or
expanded programmes at each run; note any changes in `notes`.

---

## 3. The OFAC 50% Rule (Ownership-Aggregation)

Any entity that is **50% or more owned** — directly or indirectly — by one or more SDN-listed
persons or entities is treated as effectively designated by operation of law, even if its name
does not appear on the SDN list.

Operational rules:
- Screen not just the top-level company but every identified entity in the corporate structure.
- Aggregate ownership across all paths: two 30%-owning SDN designees together reach 60% →
  the entity is blocked.
- If the ownership percentage is unknown or cannot be established from a filed source, record
  the gap in `notes` and flag the entity for manual review (`[INFERENCE]` on any ownership
  percentage that is not sourced from a filing or registry record).
- Do not assert beneficial ownership or aggregated control without a filed source
  (annual report, subsidiary schedule, company registry filing, court record).

---

## 4. Screening Methodology

### Entity graph construction
Screen: the company itself, all identified legal entities, subsidiaries, ≥50%-owned affiliates
(OFAC 50% rule), and key principals/beneficial owners. Only include entities and ownership
links that derive from a filing, registry record, or court filing.

### Name matching
Use the legal name and all known aliases, trade names, and transliterations for each entity.
The `cdd.extract.sanctions.screen_name` function implements two match types:

| `match_type` | Semantics | Evidentiary weight |
|---|---|---|
| `exact` | Normalized query equals normalized list entry (or alias) | High — record as candidate hit; verify entry_id, programme, and as-of date |
| `partial` | All tokens of the normalized query appear in the normalized list entry | Low — record as candidate for manual review; NOT a confirmed hit |

A `partial` match is never asserted as a hit. It must be recorded with: the matched list entry,
the basis for the match, a confidence score below 0.7, and an explicit note that it is
unconfirmed and requires manual disambiguation.

### Disambiguation requirements
Common names, anglicized/transliterated names, and generic corporate suffixes (LLC, JSC,
GmbH) produce false positives. Before recording any hit:
1. Check the list entry's additional identifiers (DOB, nationality, address, registration
   number, tax ID) against known information about the entity.
2. Record the basis for confirmation or non-confirmation in the artifact's `notes`.
3. If disambiguation is incomplete, record the candidate match with `confidence < 0.5` and
   flag it for manual review — do not suppress it.

---

## 5. Checked ≠ Clean: As-Of-Dating Rules

**Core rule:** a screening with no match must be reported as:
> "No match on [OFAC-SDN, OFAC-Consolidated, EU-Consolidated, UK-OFSI, UN-Consolidated,
> BIS-Entity-List] as of [dates]."

It must NEVER be rendered as "clean," "not sanctioned," "cleared," or any equivalent. Reasons:

- Sanctions lists are amended frequently (OFAC publishes updates on business days).
- A no-match result is valid only at the moment the list version was consulted.
- Entities can be added between runs; the prior no-match result does not carry forward.

**As-of dating is mandatory.** Every list entry in `lists_screened` must record the
`as_of` date (the publication or effective date of the list version used, not just the
retrieval date). When a list does not publish an explicit effective date, record the
`retrieved_at` timestamp and note this in `notes`.

**Rescreen every run.** Do not carry forward prior-run screening results. Sanctions lists
update frequently — every `full_refresh` and `incremental_refresh` must rescreen from the
current list versions.

---

## 6. Fact vs. Inference for PEP / Adverse Media

| Claim type | Basis required | Tag |
|---|---|---|
| Confirmed sanctions hit | Exact match in official list entry | `fact` — cite list + entry_id |
| Disclosed country exposure | Primary filing (annual report, segment disclosure) | `fact` — cite filing + locator |
| Russia/Belarus exit status | Primary filing / official press release | `fact` or `evidence` — cite source |
| PEP identification | Primary filing / named secondary source | `evidence` — attribute source |
| Adverse media (concluded action) | Official document or named secondary source | `evidence` — attribute source |
| Adverse media (allegation / investigation) | Named secondary source | `evidence` — attribute; do NOT assert as fact |
| Any synthesis across multiple signals | Agent reasoning | `[INFERENCE]` — tag explicitly |

**Allegations are never facts.** An indictment, investigation announcement, or media report
of alleged wrongdoing must be attributed to its source and qualified: "According to [source],
…". An inference drawn from the allegation (e.g. "likely engaged in") must be additionally
tagged `[INFERENCE]`.

---

## 7. Secondary Trackers: Signal Tier

Databases that track corporate responses to the Russia/Ukraine conflict (e.g. Yale CELI
"Leave Russia" list, Kyiv School of Economics tracker, Moral Rating Agency) are SIGNAL-tier
sources:

- They are curated by third-party researchers, not regulators.
- Their classifications (exited / suspended / continued) may lag or differ from company
  disclosures.
- They must NEVER be the sole or primary basis for asserting Russia exit/continuity status.

Usage rule: cite them as a secondary signal with explicit attribution and date:
`"[SIGNAL — Yale CELI list, retrieved YYYY-MM-DD: classified as 'Withdrawn']"`.
If the tracker classification conflicts with the primary filing, record a `conflict_set` and
flag for manual review.

---

## 8. `cdd/extract/sanctions.py` — Optional Aid

`cdd.extract.sanctions` (`fetch_and_screen` / `parse_sdn_csv` + `screen_name`) is an
optional parsing/matching helper for OFAC-SDN only. Its characteristics:

- Available only when the `[extract]` dependency group is installed.
- Covers OFAC-SDN CSV parsing. EU, UK OFSI, UN, and BIS lists are NOT yet implemented in
  the helper — the agent must screen those directly from the list portals/files.
- Its absence does **not** excuse skipping any list screen. When unavailable, the agent
  screens OFAC-SDN directly from the official CSV or search portal.
- When used, record the helper version in the artifact's `extraction_prompt` metadata.

---

*Linked from `prompts/sanctions_screening.md`. For general evidence rules see
`references/anti_hallucination_rules.md`. For source tier definitions see
`references/source_priority_rules.md`.*
