# Financial Extraction Rules

## Preservation-First Principle

The first obligation of financial extraction is preservation, not normalization. Capture the source document exactly as it appears before applying any transformation. Every native line item, period label, currency denomination, unit scale, footnote, and page reference must be recorded in the `financial_artifact` before any derived or normalized layer is computed.

A normalized figure without its source-native counterpart is unverifiable and unauditable. Normalization is a separate, explicitly labelled layer that sits alongside the source-native data, never replacing it.

---

## Source-Native Fields (Extract First)

These fields capture what the document actually says. They must be populated directly from the source without inference or transformation:

**`periods[]`:**
- `source_native_label` — the period label as printed in the document (e.g. "FY2023", "Q2 2024", "Six months ended 30 June 2023"). Never infer or standardize this field.
- `period_start` / `period_end` — ISO 8601 dates derived from the label, or `null` if the document does not provide sufficient information to compute them unambiguously.
- `period_type` — one of `FY`, `Q`, `TTM`, `LTM`, `YTD`. If ambiguous, record `null` and note in `notes`.
- `currency_reported` — the currency stated in the table header, footnote, or document header (e.g. `"USD"`, `"EUR"`, `"JPY"`). Never default; if absent from the document, set `null`.
- `unit_scale` — the scale stated in the document (e.g. "in thousands", "$ millions"). Map to the enum: `ones`, `thousands`, `millions`, `billions`. If ambiguous, record the source text in `notes` and apply your best mapping with a reduced confidence score.
- `restated` — `true` if the document explicitly labels this period as restated or revised; `false` otherwise.

**`line_items[]`:**
- `source_native_label` — the row label as it appears in the source (e.g. "Total revenues", "Gross profit (loss)", "Adjusted EBITDA"). Do not normalize to a standard taxonomy at this stage.
- `source_native_path` — the indentation or nesting path of the row within the table (e.g. `["Revenue", "Product revenue", "Software"]`). Record hierarchy as presented.
- `scope` — one of `consolidated`, `segment`, `subsidiary`, `non_gaap`. This is the most critical classification. When a table contains both consolidated and segment rows, extract them separately with the correct scope. When a page contains both GAAP and non-GAAP measures, extract both and set `non_gaap` for adjusted/non-GAAP rows.
- `value_raw` — the cell value as printed, including parentheses for negatives (e.g. `"(1,234)"`, `"—"`, `"NM"`). Preserve exactly.
- `value_numeric` — the numeric interpretation of `value_raw`, applying the period's `unit_scale` and `sign_convention`. `null` if the cell is `"—"`, `"NM"`, `"N/A"`, or otherwise non-numeric.
- `sign_convention` — `positive` if a positive `value_numeric` represents an income/asset/inflow, `negative` if it represents an expense/liability/outflow (as printed; e.g., cost of revenue rows in some formats are positive numbers representing costs), `as_reported` when the convention is ambiguous.
- `cell_locator` — a non-empty object identifying the cell's location in the source (e.g. `{"page": 42, "table_id": "t3", "row": 5, "col": 2}` for PDFs, or `{"sheet": "Income Statement", "cell": "C12"}` for spreadsheets). Required; extraction fails `financial_usability` without it.
- `footnote_refs` — array of footnote identifiers referenced in the cell, as printed (e.g. `["(1)", "a"]`).

**`footnotes[]`:** Capture every footnote that applies to the extracted table. Record `footnote_id` as printed, `text` verbatim, and `locator` pointing to the footnote position in the source.

**`source_context`:** Document title, section path, `source_native_statement_name` (e.g. "Consolidated Statements of Operations"), `table_id`, and page number. All fields that are determinable from the document should be non-null.

---

## Normalization as a Derived Layer

The `normalization` block is populated after all source-native fields are complete. It records the parameters used to produce normalized versions of the financial data and is intentionally separate from the line-item data itself.

- `fx_source` — the source of the exchange rate used for currency conversion (e.g. `"ECB"`, `"Federal Reserve H.10"`, `"Bloomberg"`). Required if `target_currency` differs from `currency_reported`.
- `fx_date` — the date of the exchange rate used (ISO 8601).
- `target_currency` — the normalized currency (e.g. `"USD"`). Set only when an FX conversion has been applied; `null` otherwise.
- `fiscal_to_calendar` — mapping from fiscal period labels to calendar periods, when the company uses a non-calendar fiscal year.

Normalization is never applied in-place. If you need a normalized value, compute it using `normalization` parameters and the source-native `value_numeric`; do not overwrite `value_numeric` with a converted figure.

---

## `normalized_candidate` on Line Items

Each `line_item` carries an optional `normalized_candidate` block: `{"taxonomy_key": "<standard_taxonomy_item>", "confidence": 0.0–1.0}`. This maps the `source_native_label` to a standard financial taxonomy (e.g. a company-specific taxonomy or GAAP line item name) with a confidence score.

This is a candidate, not a resolved mapping. It is produced by the extraction agent and subject to human review. A `confidence < 0.7` should be treated as tentative. If no mapping is confident, set `normalized_candidate: null`.

---

## Restatement Handling

When a document presents both an original and a restated figure for the same period:
1. Extract both as separate `period` entries: one with `restated: false` (original), one with `restated: true` (restated).
2. The restated period supersedes the original for analysis, but both must be preserved.
3. Emit a `conflict_set` with `reason_code: "restatement"` in `merge_financials` so the dossier reader sees the history.
4. Never silently replace the original figure with the restated one without recording the original.

---

## GAAP vs. Non-GAAP Handling

Non-GAAP measures (Adjusted EBITDA, non-GAAP operating income, free cash flow as defined by management, etc.) must be extracted with `scope: "non_gaap"`. They must never be merged with, or used as a substitute for, GAAP figures of the same period without explicit labelling.

When a source document presents both GAAP and non-GAAP figures in the same table, extract both sets of rows and assign scope accordingly. Emit a `conflict_set` with `reason_code: "gaap_vs_nongaap"` if any dossier section would present both figures for the same metric. The dossier reader must always know which figure is GAAP and which is adjusted.

---

## Conflict Reason Codes for Financials

| `reason_code` | When to use |
|---|---|
| `restatement` | Two figures for the same period and line item, one of which is a restatement of the other |
| `currency_mismatch` | Same metric from two sources, reported in different currencies, not reconciled |
| `period_mismatch` | Two figures claimed for the same period but period boundaries differ (e.g. fiscal vs. calendar year) |
| `scope_mismatch` | One figure is consolidated, another is segment or subsidiary; both attributed to the same company total |
| `gaap_vs_nongaap` | One figure is GAAP, another is a non-GAAP adjustment of the same metric |
| `source_authority_conflict` | Two primary-tier sources report materially different figures for the same period and scope with no restatement or currency explanation |

Emit a `conflict_set` for every detected conflict. Never resolve a conflict by silently choosing one figure.
