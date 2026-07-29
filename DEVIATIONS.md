# Deviations and clarifications log

This file records any deviation from, or clarification of, the pre-registered plan,
in the order they occur, each with the date it was logged. Per §7 of the registration,
deviations are logged as they happen and reported in the manuscript; none is omitted
as minor. The git commit history is the authoritative timestamp for each entry.

---

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

**Why logged before archive.** This entry is recorded during the registration's
pending window, before the seed set's use and before any harvest, so that the
characterization of the recall instrument is transparent from the outset rather than
raised retrospectively.

<!--
Template for future entries — copy below and fill in:

## YYYY-MM-DD — <short title>

**Registration reference:** <section>
**What the registration says.** <...>
**Deviation / clarification.** <...>
**Consequence for interpretation.** <...>
-->
