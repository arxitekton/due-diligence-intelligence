# Anti-Hallucination Rules

## Core Principle

Every output claim must trace to a preserved source artifact or must be explicitly flagged as inference. The research engine is an evidence-preservation and structuring system, not a synthesis oracle. When evidence is absent, the correct output is `null` or `unknown`, not a plausible-sounding estimate.

---

## Null and Unknown Policy

- If a fact is not present in any retrieved source for this run, set the field to `null` (for structured artifacts) or record `"unknown"` (in prose dossier claims) and add the gap to `known_gaps`.
- Do not carry forward values from a prior run without re-verifying them in the current run. A value that was true in a prior run may have changed; absence of current evidence is not the same as continuity of prior evidence.
- `known_gaps` in the dossier is a first-class field, not an afterthought. Populate it honestly; an incomplete dossier with accurate gaps is more valuable than a complete-looking dossier with invented values.

---

## Fact vs. Evidence vs. Inference

Every dossier claim carries a `kind` field with one of three values:

**`fact`** — a discrete, verifiable datum extracted directly from a primary source with no interpretation required. Examples: a revenue figure from a 10-K, a founding date from a company registry filing, a patent number from the USPTO database. A `fact` claim must cite at least one `artifact_id` that contains the supporting evidence at the referenced `locator`.

**`evidence`** — a curated excerpt or derived observation that requires minimal interpretation but draws on a source rather than stating a single datum. Examples: a quote from an earnings transcript describing strategy, a table of product tiers extracted from a pricing page, a paragraph from an annual report describing market position. An `evidence` claim must cite at least one `artifact_id`.

**`inference`** — a conclusion the research agent draws from combining multiple pieces of evidence, applying external domain knowledge, or reasoning about implications. Inferences may be well-founded but are not directly supported by a single cited passage. Inferences must be tagged `[INFERENCE]` in the dossier prose and may optionally cite the artifacts that support the reasoning chain.

Never elevate an `inference` to a `fact` or `evidence` claim. Never silently demote a `fact` to `inference` to avoid citing a source.

---

## Citation Rule

Every claim of kind `fact` or `evidence` in `final_dossier.json` must include at least one entry in its `citations` array. The citation must be a valid `artifact_id` (pattern `^art_[0-9a-f]{16}$`) that exists in the current run's artifact set. The `referential_integrity` gate will fail if any citation references an unknown `artifact_id`. The `lineage_complete` gate will fail if any `fact` or `evidence` claim has an empty `citations` array.

Acceptable citation form in dossier prose: `[art_<hex16>, §<section>, p.<page>]` or equivalent using the `locator` fields from the artifact's lineage block. Citing page and section is strongly preferred over artifact ID alone.

---

## Do Not Infer Without Explicit Evidence

The following classes of assertion require explicit, cited evidence from a primary or secondary source. They must never be inferred from indirect signals alone:

- **Ownership and corporate structure:** parent company, subsidiaries, beneficial ownership percentage, holding company structure. Do not infer from brand similarity, shared address, or executive overlap without a filing or registry record.
- **Revenue, ARR, GMV, and other financial metrics:** do not estimate from headcount, funding rounds, or market share claims. Record only figures that appear in a primary source (filing, earnings release) or a named secondary source. Always note whether a figure is GAAP or non-GAAP.
- **Customer identity and counts:** do not name specific customers unless cited in a primary or secondary source (case study, press release, filing). "Thousands of customers" from a job posting is a signal, not a fact.
- **Employee headcount:** use only figures from filings, press releases, or named secondary sources. LinkedIn profile counts are a signal, not a headcount fact.
- **Funding amounts and valuations:** use only closed, announced rounds cited in press releases, filings, or named secondary sources. Do not infer valuation from comparable companies.
- **Market share and competitive position:** use only cited analyst reports or company-stated figures. Never compute from first principles without disclosing the methodology as an `[INFERENCE]`.
- **Profitability and margins:** non-disclosed private company financials must remain `null`. Do not back-calculate from pricing, headcount, or funding.

---

## Conflict Preservation

When two or more extracted artifacts assert different values for the same metric (same company, same period, same scope), always emit a `conflict_set` with the appropriate `reason_code`. Never:

- Silently prefer one source over another without recording the discrepancy.
- Average conflicting values.
- Suppress a conflict because one source is "clearly wrong" — record both and let the `reason_code` (e.g. `restatement`, `gaap_vs_nongaap`) document why they differ.

The `conflict_visibility` gate enforces this: if `merge_financials` surfaces conflicts, they must appear in the `data_quality_report.conflicts` array. A run where known conflicts are absent from that array does not pass.

Conflict resolution is the responsibility of the analyst reading the dossier, not the extraction engine.
