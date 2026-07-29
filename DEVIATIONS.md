# Deviations and clarifications log

This file records any deviation from, or clarification of, the pre-registered plan,
in the order they occur, each with the date it was logged. Per §7 of the registration,
deviations are logged as they happen and reported in the manuscript; none is omitted
as minor. The git commit history is the authoritative timestamp for each entry.

\---

## 2026-07-28 — Seed set reflects recent English-language literature

**Registration reference:** §4.6 (recall check); §7 (prior familiarity stated as a
precondition).

**What the registration says.** The recall seed set is assembled from the authors'
prior familiarity with the published clinical-LLM literature, and recall is reported
as an upper bound "since the seed set and query share the authors' familiarity."

**Clarification / deviation.** In assembling the seed set, the authors' familiarity is
concentrated in the **recent (roughly 2023–2026), English-language** clinical-LLM
literature. The committed seed set is predominantly English (with limited non-English
representation) and skews recent. The registration's ">=10 non-English or non-MEDLINE"
requirement is satisfied through non-MEDLINE works; non-English representation is
limited.

**Consequence for interpretation.** The recall estimate derived from this seed set
characterizes retrieval of recent English-language clinical-LLM work more reliably
than it characterizes retrieval of non-Anglophone or pre-2023 work. Because H2
(geographic concentration) concerns precisely the representation of non-high-income,
often non-Anglophone research, the recall check does **not** independently validate
the pipeline's retrieval of that stratum. This is stated as a limitation; it is not
corrected, and recall is reported as a within-stratum upper bound accordingly.

**Why logged now.** This entry is recorded before the seed set's use and before any
harvest, so that the characterization of the recall instrument is transparent from the
outset rather than raised retrospectively. (See the timing entry below regarding the
order of registration archival and seed-set commit.)

\---

## 2026-07-28 — Seed set committed after registration archived; no data observed in between

**Registration reference:** §5 (identifiers / archived seed set); §7 (data availability
at registration — "no query has been run, no records retrieved").

**Registered ordering.** The plan describes the intended sequence as: recall seed set
committed with a git timestamp → registration archived → OpenAlex query run. The
seed-before-registration commit was intended as timestamp evidence that the seed set
predated any observation of data.

**What actually happened.** The registration was registered (archived, DOI issued) on
**13 July 2026**, and the recall seed set was committed to the repository on **28 July
2026** — 15 days later. The seed set was therefore committed *after* the registration
archived, inverting the registered seed → registration order.

**Why this does not compromise the recall check.** The substantive guarantee the
registration protects is that the seed set was assembled from the authors' prior
familiarity, blind to any corpus data. That guarantee holds: **no OpenAlex query of any
kind — including test or count queries — had been run at the time the seed set was
committed, and none had been run at the time of this entry.** No corpus record informed
the seed set's construction. The inverted commit order affects only the form of the
timestamp evidence, not the fact that the seed set predates any data observation.

**Consequence for interpretation.** Recall is reported as pre-registered. The seed set
remains a valid prior-knowledge instrument. Readers relying on git timestamps should
note that the seed-set commit date postdates the registration archival date, for the
reason recorded here; the "no data observed before seed-set construction" condition is
nonetheless met.

