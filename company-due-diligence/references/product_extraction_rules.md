# Product Extraction Rules

## Preservation-First Principle

Extract the company's product taxonomy exactly as the source presents it before applying any normalization or rationalization. Companies name their offerings idiosyncratically; imposing external structure during extraction destroys the evidentiary record. The source-native representation is the artifact; a normalized view is an optional derived layer.

---

## Entity Types

The `product_artifact` models a hierarchy of product entities. Each entity has an `entity_type` drawn from the enum:

| `entity_type` | Meaning |
|---|---|
| `product` | A standalone, separately marketed offering (e.g. "Salesforce Sales Cloud") |
| `service` | A service offering billed separately or delivered distinctly (e.g. "Professional Services") |
| `tier` | A pricing or capability tier within a product (e.g. "Enterprise", "Business", "Starter") |
| `bundle` | A packaged combination of other entities (e.g. a suite that includes multiple products) |
| `feature` | A discrete capability within a product or tier, mentioned in the source as a named feature |
| `platform` | A base platform on which other products or modules run |
| `module` | An add-on or extension to a platform or product |

Use the type that best matches how the source presents the entity. When ambiguous, use the type that preserves the most information (prefer `product` over `feature` when the source markets it as a separate offering). Record your reasoning in the entity's `description_quote` or `notes`.

---

## Source-Native Fields (Extract First)

**`source_native_name`** — the name of the entity exactly as it appears in the source. Do not normalize capitalization, abbreviations, or brand suffixes. If a product is called "ServiceNow IT Service Management" in the source, record that string verbatim.

**`aliases`** — other names for the same entity found in the same or related sources (e.g. abbreviated names, ticker-era brand names, sub-brand names). Populate from the source; do not invent aliases.

**`source_native_category_path`** — the category hierarchy as the source presents it. For a product listed under "Platform > Workflow Automation > Finance" on the company's product page, record `["Platform", "Workflow Automation", "Finance"]`. Preserve the source's category labels exactly; do not map to an external taxonomy at extraction time.

**`parent_entity_id`** — the `entity_id` of the parent entity within this artifact, if the source presents the entity as a child (e.g. a tier as a child of a product, a module as a child of a platform). `null` for top-level entities.

**`display_order`** — the ordinal position of the entity within its parent as presented in the source (1-indexed). Preserves the source's ordering, which often signals commercial priority.

**`description_quote`** — a verbatim excerpt from the source describing the entity. Prefer the source's own marketing description over a paraphrase. Null if no description is available.

**`lifecycle_status`** — the product's current lifecycle state as stated or implied by the source. Use source language where possible (e.g. `"generally available"`, `"beta"`, `"preview"`, `"deprecated"`, `"end-of-life"`, `"sunset"`). Set `null` if the source does not indicate lifecycle state. Do not infer lifecycle from the absence of a product in a newer source; absence requires a separate comparison run to confirm discontinuation.

**`geography_scope`** — array of geographic regions or countries for which the source indicates availability. Populate from explicit source statements only (e.g. "available in North America and EMEA"). Empty array if the source does not restrict geography. Do not infer global availability from the absence of a restriction.

---

## Pricing Observations

Pricing is extracted as `pricing_observations[]`, a list of point-in-time pricing data points. Each observation captures:

- `price_raw` — the price as printed in the source (e.g. `"$25/user/month"`, `"Contact sales"`, `"Starting at €99"`). Verbatim.
- `currency_reported` — the ISO 4217 currency code if determinable from the source (e.g. `"USD"`, `"EUR"`). `null` if the source does not specify.
- `billing_interval` — the billing cadence as stated (e.g. `"monthly"`, `"annually"`, `"per seat per month"`, `"one-time"`). `null` if not stated.
- `locator` — the source location of this price observation (page, section, element selector, etc.). Required and non-empty.

Pricing observations are point-in-time. The `retrieved_at` timestamp of the source provides the observation date. Treat pricing pages as volatile (stale after 90 days) and always note that prices are subject to change. Never derive a current price from a cached observation without checking for updates.

When a source lists multiple pricing tiers under a product, extract each tier as a separate entity of type `tier`, and attach the tier-specific pricing observation to that tier entity.

---

## Attributes

`attributes[]` captures named product properties beyond pricing. Each attribute has:

- `name_native` — the attribute name as labeled in the source (e.g. `"Max users"`, `"SLA uptime"`, `"Integrations"`, `"API rate limit"`).
- `value_native` — the attribute value as stated in the source. `null` if the source lists the attribute without a value.
- `locator` — source location of the attribute. Required and non-empty.

Do not normalize attribute names to a standard vocabulary at extraction time. Normalization is a post-extraction step.

---

## `normalized_candidate`

Each entity may carry a `normalized_candidate: {"family": "<product_family>", "confidence": 0.0–1.0}` block. This maps the source-native entity to a standard product family label for cross-run and cross-company analysis. Set `null` if no confident mapping exists. A `confidence < 0.7` indicates a tentative mapping that requires human review.

---

## Lifecycle Handling

Do not infer lifecycle changes from within a single extraction run. Do not mark a product `deprecated` or `end-of-life` because it appears on an archived page or is absent from a current page unless the source explicitly states the status. Lifecycle inference across runs is the responsibility of the `compare_runs` analysis, not the extraction step.

When a source explicitly marks a product as deprecated, end-of-life, or sunset, record that status in `lifecycle_status` and quote the source language in `description_quote`.

---

## Geography Handling

Do not infer geographic availability from pricing currency, UI language, or domain suffix. Record only explicit geography statements from the source. When a product is listed as globally available, record `geography_scope: ["global"]` only if the source uses that language.

When a product is available in some regions and not others, or when availability changes by tier, extract a separate entity for each tier and attach the geography restrictions to that tier entity.

---

## Lineage Requirement

Every `product_artifact` must carry a complete `lineage` block: `source_snapshot_id`, `content_path`, `locator`, `snippet`, and `extraction_prompt.name` + `extraction_prompt.version`. The `locator` must identify the specific section of the source document from which the product data was extracted (e.g. the product page URL section, the annual report page and section name). A product artifact without a locatable source is not admissible as evidence.
