# Seed set — recall check (pre-registered §4.6)

## Purpose

This file (`seed_set.csv`) is the **recall seed set** for the pre-registered study
*Large Language Models in Clinical Medicine: Evidence Maturity and Geographic
Distribution of the Research Literature (2019–2026)*.

After the OpenAlex corpus is harvested, the fraction of these known works that the
query successfully retrieves is reported as the study's **recall estimate**. Because
the seed set and the query share the authors' familiarity with the literature, this
recall figure is interpreted as an **upper bound**, not an unbiased estimate.

## Provenance and timing

The seed set was assembled by both authors from prior familiarity with the published
clinical-LLM literature and from the reference lists of published reviews, **before
any OpenAlex query was run** and before the registration archived. The git commit
date of this file establishes that ordering: seed set committed → registration
archived → corpus harvested. No record from the OpenAlex pipeline informed the
construction of this set.

Both authors contributed independently. Where both independently recalled the same
work, the two rows are retained and share a single `distinct_work_id`; recall is
computed over distinct works, not over rows.

## Scope of the authors' familiarity (see DEVIATIONS.md)

The set reflects the authors' familiarity with the **recent, English-language**
clinical-LLM literature. It contains 63 distinct works (66 rows, including 3
cross-coder duplicate pairs). Languages: predominantly English, with limited
non-English representation. The recall estimate derived from this set therefore
characterizes retrieval of recent English-language work more reliably than it
characterizes retrieval of non-Anglophone or older work. This limitation is recorded
in `DEVIATIONS.md` and is carried into the manuscript's interpretation of recall.

## Columns

| column | meaning |
|---|---|
| `distinct_work_id` | unique per distinct work; shared across cross-coder duplicate rows |
| `row_id` | unique per row |
| `title` | work title |
| `doi` | DOI (or identifier); verify each resolves to the stated work |
| `year` | publication year |
| `provenance` | `memory` (recalled directly) or `reference_list` (pearled from a review) |
| `language` | language of the work |
| `medline_status` | `medline` / `non-medline`, verified against the NLM Catalog |
| `review_source` | for `reference_list` rows: the review whose reference list supplied the work |
| `added_by` | author who contributed the row (KSV / MM) |

## Counts (at commit)

- Distinct works: 63 (target ≥60 met)
- Rows: 66 (includes 3 cross-coder duplicate pairs)
- `reference_list` rows: 24, each naming its source review
- Non-MEDLINE works: present and counted (satisfies the ≥10 non-English-OR-non-MEDLINE requirement)
- Non-English works: limited (see DEVIATIONS.md)

## Reproducibility

`seed_set.csv` is committed as plain text so that its contents, and any later change,
are visible in the git diff. The committed version is the artifact of record; any
local spreadsheet copy is a working convenience only.
