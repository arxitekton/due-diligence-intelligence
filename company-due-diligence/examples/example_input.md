# Example Skill Input — Acme Analytics, Inc.

This block shows the parameters a user passes to the `company-due-diligence` skill
to kick off a full research run on a SaaS analytics company.

---

## Input Parameters

| Field               | Value                                           |
|---------------------|-------------------------------------------------|
| **company_name**    | Acme Analytics, Inc.                            |
| **legal_name**      | Acme Analytics, Inc.                            |
| **company_id**      | acme-analytics                                  |
| **website**         | https://www.acmeanalytics.com                   |
| **ticker**          | ACME                                            |
| **exchange**        | NASDAQ                                          |
| **country**         | US                                              |
| **industry**        | Business Intelligence & Analytics Software      |
| **subsidiaries**    | Acme Data Labs, Acme Cloud Services             |
| **brands**          | AcmeBI, AcmePulse                               |

## Research Focus

- Financial performance: revenue growth, ARR, gross margin, burn rate
- Product portfolio: core BI platform, embedded analytics SDK, data connectors
- Management team: tenure, prior exits, technical depth
- Competitive landscape: Tableau, Looker, Power BI, Metabase
- Recent events: funding rounds, M&A activity, executive changes, layoffs
- Customer base: key verticals (fintech, healthtech), churn indicators, NPS signals

## Run Configuration

| Setting       | Value            |
|---------------|------------------|
| **mode**      | full_refresh     |
| **locale**    | en-US            |
| **model_id**  | claude-opus-4    |

## Notes

> Run date: 2026-06-20
> Analyst: Dmytro Maliarenko
> Purpose: Series B investment due diligence — first-pass research sprint
