#!/usr/bin/env python3
"""
harvest.py — OpenAlex retrieval for the clinical-LLM scientometrics study.

Authors: Krishna Sai Vasireddy and Monika Rao Mandava
Part of: clinical-llm-scientometrics (see repository README and OSF registration).

Implements the pre-registered retrieval (§3.1) and ambiguous-term routing (§3.2),
using local term matching so the matching logic is fully specified by this file
and reproducible independently of OpenAlex's internal search parsing:

  - Server-side OpenAlex filters handle the unambiguous work: publication-date
    window and work type (article|review|preprint).
  - The both-term rule (an LLM term AND a clinical term in title or abstract),
    case-insensitive with hyphen/space normalization, is applied locally.

Outputs (under data/):
  data/raw/openalex_page_*.json   raw API responses, archived verbatim
  data/raw/query_manifest.json    params, filters, snapshot date, term lists, counts
  data/processed/harvest.csv      one row per candidate work with match/flag columns

This script retrieves, matches terms, flags ambiguous-only hits, and archives.
It does not decide eligibility — that is human screening (§3.3).

Run only after the seed set is committed and the registration is archived.
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests



# Unambiguous LLM terms: presence of any one of these satisfies the LLM condition
# on its own (no manual screening needed on LLM grounds).
LLM_TERMS_UNAMBIGUOUS = [
    "large language model", "large language models",
    "gpt-3", "gpt-3.5", "gpt-4", "gpt-4o",
    "chatgpt", "med-palm", "biogpt", "clinicalbert",
    "generative pre-trained", "generative pretrained",
    "foundation model", "generative ai",
]

# Ambiguous LLM terms: also occur in unrelated contexts (GPT = liver enzyme;
# Gemini/Claude = trial/person names; etc.). A work matched ONLY by these, with
# no unambiguous LLM term present, is routed to manual screening (§3.2) — not
# auto-included, not auto-excluded.
LLM_TERMS_AMBIGUOUS = [
    "gpt", "llm", "palm", "gemini", "claude", "llama", "mistral",
]

CLINICAL_TERMS = [
    "clinical", "clinician", "medical", "medicine", "patient", "physician",
    "diagnosis", "diagnostic", "healthcare", "hospital", "nursing", "surgery",
    "radiology", "pathology", "psychiatry", "oncology", "primary care",
    "electronic health record", "ehr", "medical education", "triage", "prognosis",
]

# ----------------------------------------------------------------------------
# Retrieval configuration (registration §2, §3.1)
# ----------------------------------------------------------------------------
OPENALEX_WORKS = "https://api.openalex.org/works"
DATE_FROM = "2019-01-01"
DATE_TO = "2026-03-31"
WORK_TYPES = ["article", "review", "preprint"]   # OpenAlex 'type' values
PER_PAGE = 200                                    # OpenAlex max page size


# ----------------------------------------------------------------------------
# Text normalization + matching (the reproducible core)
# ----------------------------------------------------------------------------
def normalize(text: str) -> str:
    """Lowercase; collapse hyphens/underscores/slashes and whitespace to single
    spaces, so 'GPT-4', 'GPT 4', 'gpt_4' all normalize to 'gpt 4'. Applied to both
    source text and search terms."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"[-_/]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _term_pattern(term: str) -> re.Pattern:
    """Word-boundary regex for a normalized term, so 'llm' does not match inside
    'skillful' and 'ehr' does not match inside 'adhere'. Multiword terms match
    across one or more spaces."""
    norm = normalize(term)
    parts = [re.escape(p) for p in norm.split(" ")]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


# Pre-compile once
_PAT_UNAMBIG = [(t, _term_pattern(t)) for t in LLM_TERMS_UNAMBIGUOUS]
_PAT_AMBIG = [(t, _term_pattern(t)) for t in LLM_TERMS_AMBIGUOUS]
_PAT_CLIN = [(t, _term_pattern(t)) for t in CLINICAL_TERMS]


def find_terms(text_norm: str, patterns) -> list[str]:
    """Return the list of terms whose pattern is found in the normalized text."""
    return [term for term, pat in patterns if pat.search(text_norm)]


def reconstruct_abstract(inv_index: dict | None) -> str:
    """Rebuild plain-text abstract from OpenAlex's inverted-index format.

    OpenAlex stores abstracts as {word: [positions]}. Returns '' when the field
    is absent or unreconstructable (those works are flagged downstream).
    """
    if not inv_index:
        return ""
    try:
        positions: list[tuple[int, str]] = []
        for word, idxs in inv_index.items():
            for i in idxs:
                positions.append((i, word))
        positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in positions)
    except Exception:
        return ""


# ----------------------------------------------------------------------------
# OpenAlex paging (cursor-based; polite pool)
# ----------------------------------------------------------------------------

# Server-side search terms: OR-ed into a title_and_abstract.search query to
# narrow OpenAlex to a candidate pool of plausibly-LLM works BEFORE local
# matching. This is a recall net, not the final filter — the precise both-term
# and ambiguous-routing rules are re-applied locally in classify_record().
#
# Included: unambiguous LLM terms + the ambiguous short terms that, when they
# appear in a title/abstract, are still worth pulling for local screening.
# The local matcher decides what actually counts; this only decides what to
# fetch. The exact query is recorded in query_manifest.json.
SEARCH_TERMS = [
    "large language model", "large language models",
    "chatgpt", "gpt-4", "gpt-3", "gpt-3.5", "gpt-4o",
    "med-palm", "biogpt", "clinicalbert",
    "generative pre-trained", "generative pretrained",
    "generative ai", "foundation model",
    "gpt", "llm", "llama", "mistral", "gemini", "claude", "palm",
]


def build_search() -> str:
    """Build an OpenAlex title/abstract search: quoted phrases joined by OR.

    OpenAlex supports uppercase boolean operators (AND/OR/NOT) in the search
    value, with double-quoted phrases for exact matching. This is a recall net;
    the precise both-term and ambiguous-routing rules are re-applied locally in
    classify_record(). Note OpenAlex applies stemming and drops stop-words, so
    the returned pool is a superset that local matching then filters exactly.
    """
    return " OR ".join(f'"{t}"' for t in SEARCH_TERMS)


def build_filter(search_value: str) -> str:
    return ",".join([
        f"from_publication_date:{DATE_FROM}",
        f"to_publication_date:{DATE_TO}",
        f"type:{'|'.join(WORK_TYPES)}",
        f"title_and_abstract.search:{search_value}",
    ])


def harvest(api_key: str | None, raw_dir: Path, max_pages: int | None) -> list[dict]:
    """Page through all matching works; archive each raw page; return all records.

    Resumable: the next cursor and page number are checkpointed after every page
    to raw_dir/_checkpoint.json. If the run is interrupted (including by hitting a
    daily credit cap), re-running resumes from the last saved cursor and reloads
    already-archived pages from disk rather than re-fetching them.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "clinical-llm-scientometrics"})

    search_value = build_search()
    filt = build_filter(search_value)
    checkpoint = raw_dir / "_checkpoint.json"

    all_records: list[dict] = []
    cursor = "*"
    page = 0
    total_reported = None

    # --- resume from checkpoint if present ---
    if checkpoint.exists():
        try:
            cp = json.loads(checkpoint.read_text(encoding="utf-8"))
            cursor = cp.get("next_cursor", "*")
            page = cp.get("page", 0)
            total_reported = cp.get("total_reported")
            print(f"Resuming from checkpoint: page {page}, "
                  f"cursor {'set' if cursor and cursor != '*' else 'start'}.")
            # reload already-archived pages so counts and CSV are complete
            for pf in sorted(raw_dir.glob("openalex_page_*.json")):
                try:
                    d = json.loads(pf.read_text(encoding="utf-8"))
                    all_records.extend(d.get("results", []))
                except Exception as e:
                    print(f"    warning: could not reload {pf.name}: {e}")
            print(f"  reloaded {len(all_records)} records from {page} archived pages.")
        except Exception as e:
            print(f"    checkpoint unreadable ({e}); starting fresh.")
            cursor, page, all_records = "*", 0, []

    select_fields = ",".join([
        "id", "doi", "title", "display_name", "publication_year",
        "publication_date", "type", "language", "abstract_inverted_index",
        "authorships", "primary_location", "locations",
        "cited_by_count", "referenced_works", "topics", "concepts",
        "is_retracted", "open_access", "ids",
    ])

    while True:
        params = {
            "filter": filt,
            "per-page": PER_PAGE,
            "cursor": cursor,
            "select": select_fields,
        }
        if api_key:
            params["api_key"] = api_key
        url = f"{OPENALEX_WORKS}?{urlencode(params)}"
        resp = _get_with_retry(session, url)
        data = resp.json()

        if total_reported is None:
            total_reported = data.get("meta", {}).get("count")
            print(f"OpenAlex reports {total_reported} works match the server-side filter.")

        results = data.get("results", [])
        if not results:
            break

        page += 1
        (raw_dir / f"openalex_page_{page:04d}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        all_records.extend(results)

        cursor = data.get("meta", {}).get("next_cursor")

        # checkpoint AFTER archiving the page and reading the next cursor
        checkpoint.write_text(json.dumps({
            "page": page,
            "next_cursor": cursor,
            "total_reported": total_reported,
        }), encoding="utf-8")

        if page % 25 == 0 or page <= 3:
            print(f"  page {page}: +{len(results)} (running total {len(all_records)})")

        if not cursor:
            break
        if max_pages and page >= max_pages:
            print(f"Stopping early at max_pages={max_pages} (DRY/partial run).")
            break
        time.sleep(0.5)  # be polite; keep well under the rate limit

    return all_records, total_reported


def _get_with_retry(session, url, tries=8):
    """GET with backoff. Rate-limits (429) get long, patient waits because
    OpenAlex cooldowns clear over minutes, not seconds; a Retry-After header,
    if present, is respected. Other transient errors get shorter backoff."""
    for attempt in range(1, tries + 1):
        try:
            r = session.get(url, timeout=90)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                # honor Retry-After if given, else escalate: 60,120,180,... capped
                ra = r.headers.get("Retry-After")
                if ra and ra.isdigit():
                    wait = int(ra)
                else:
                    wait = min(60 * attempt, 300)
                print(f"    HTTP 429 (rate limited); waiting {wait}s "
                      f"[retry {attempt}/{tries}]")
                time.sleep(wait)
                continue
            if r.status_code in (500, 502, 503, 504):
                wait = min(10 * attempt, 120)
                print(f"    HTTP {r.status_code}; retry {attempt}/{tries} in {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            wait = min(10 * attempt, 120)
            print(f"    {type(e).__name__}: {e}; retry {attempt}/{tries} in {wait}s")
            time.sleep(wait)
    raise RuntimeError(
        f"Failed after {tries} attempts. If these were 429 rate-limit errors, "
        f"WAIT 30-60 MINUTES before re-running — the IP is in a cooldown that more "
        f"retries won't clear. The checkpoint is saved; re-running resumes from the "
        f"last good page.\nURL: {url}"
    )


# ----------------------------------------------------------------------------
# Apply the pre-registered term logic locally
# ----------------------------------------------------------------------------
def classify_record(rec: dict) -> dict:
    title = rec.get("title") or rec.get("display_name") or ""
    abstract = reconstruct_abstract(rec.get("abstract_inverted_index"))
    have_abstract = bool(abstract)
    blob = normalize(f"{title} . {abstract}")

    unambig = find_terms(blob, _PAT_UNAMBIG)
    ambig = find_terms(blob, _PAT_AMBIG)
    clinical = find_terms(blob, _PAT_CLIN)

    has_llm_unambig = len(unambig) > 0
    has_llm_ambig = len(ambig) > 0
    has_clinical = len(clinical) > 0

    # both-term rule: (unambiguous OR ambiguous LLM term) AND clinical term
    both_term_hit = (has_llm_unambig or has_llm_ambig) and has_clinical

    # §3.2: matched on LLM grounds ONLY by ambiguous term(s) -> manual screening
    ambiguous_only = both_term_hit and (not has_llm_unambig) and has_llm_ambig

    # country extraction for later H2 (not eligibility) — recorded, not filtered
    countries = sorted({
        c
        for a in (rec.get("authorships") or [])
        for c in (a.get("countries") or [])
    })

    return {
        "openalex_id": rec.get("id"),
        "doi": rec.get("doi"),
        "title": title,
        "year": rec.get("publication_year"),
        "date": rec.get("publication_date"),
        "type": rec.get("type"),
        "language": rec.get("language"),
        "has_abstract": have_abstract,
        "llm_terms_unambiguous": "|".join(unambig),
        "llm_terms_ambiguous": "|".join(ambig),
        "clinical_terms": "|".join(clinical),
        "both_term_hit": both_term_hit,
        "ambiguous_only_needs_screening": ambiguous_only,
        "is_retracted": rec.get("is_retracted"),
        "cited_by_count": rec.get("cited_by_count"),
        "author_countries": "|".join(countries),
        "n_referenced_works": len(rec.get("referenced_works") or []),
    }


def write_csv(rows: list[dict], path: Path):
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        print("No rows to write.")
        return
    cols = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {path}")


def resolve_api_key(cli_value: str | None, base: Path) -> str | None:
    """Resolve the OpenAlex API key from, in order: --api-key flag,
    OPENALEX_API_KEY env var, or a local .openalex_key file (repo root).
    Returns None if none found (caller warns)."""
    import os
    if cli_value:
        return cli_value.strip()
    env = os.environ.get("OPENALEX_API_KEY")
    if env:
        return env.strip()
    key_file = Path(".openalex_key")
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    return None


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="OpenAlex harvest for clinical-LLM study.")
    ap.add_argument("--api-key", default=None,
                    help="OpenAlex API key. If omitted, reads OPENALEX_API_KEY "
                         "env var, then a local .openalex_key file.")
    ap.add_argument("--out", default="data", help="Output base dir (default: data).")
    ap.add_argument("--max-pages", type=int, default=None,
                    help="Cap pages for a dry/partial test run. Omit for full harvest.")
    args = ap.parse_args()

    base = Path(args.out)
    raw_dir = base / "raw"
    snapshot = datetime.now(timezone.utc).isoformat()

    api_key = resolve_api_key(args.api_key, base)
    if not api_key:
        print("WARNING: no API key found (flag/env/.openalex_key). OpenAlex now "
              "requires a key; without one you'll get limited free credits then "
              "errors. Proceeding anyway in case free credits remain.")

    print("=" * 70)
    print("HARVEST — clinical-LLM scientometrics")
    print(f"  snapshot (UTC): {snapshot}")
    print(f"  date window:    {DATE_FROM} .. {DATE_TO}")
    print(f"  types:          {WORK_TYPES}")
    print(f"  matching:       LOCAL (both-term rule applied in Python)")
    print(f"  api key:        {'present' if api_key else 'MISSING'}")
    print("=" * 70)

    records, total_reported = harvest(api_key, raw_dir, args.max_pages)
    print(f"Retrieved {len(records)} raw records across the server-side filter.")

    rows = [classify_record(r) for r in records]
    hits = [r for r in rows if r["both_term_hit"]]
    ambig_only = [r for r in hits if r["ambiguous_only_needs_screening"]]
    no_abstract = [r for r in rows if not r["has_abstract"]]

    # write full candidate table (all retrieved, with match columns)
    write_csv(rows, base / "processed" / "harvest.csv")

    manifest = {
        "snapshot_utc": snapshot,
        "date_from": DATE_FROM,
        "date_to": DATE_TO,
        "work_types": WORK_TYPES,
        "matching": "local both-term (LLM AND clinical), word-boundary, normalized",
        "openalex_filter": build_filter(build_search()),
        "server_side_search": build_search(),
        "server_side_search_terms": SEARCH_TERMS,
        "llm_terms_unambiguous": LLM_TERMS_UNAMBIGUOUS,
        "llm_terms_ambiguous": LLM_TERMS_AMBIGUOUS,
        "clinical_terms": CLINICAL_TERMS,
        "counts": {
            "server_side_reported": total_reported,
            "records_retrieved": len(records),
            "both_term_hits": len(hits),
            "ambiguous_only_needs_screening": len(ambig_only),
            "retrieved_without_abstract": len(no_abstract),
        },
    }
    (raw_dir / "query_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("-" * 70)
    print(f"  server-side reported:            {total_reported}")
    print(f"  records retrieved:               {len(records)}")
    print(f"  both-term hits (candidates):     {len(hits)}")
    print(f"  ambiguous-only -> screen (§3.2): {len(ambig_only)}")
    print(f"  retrieved w/o abstract:          {len(no_abstract)}")
    print("-" * 70)
    print("Raw pages + manifest archived under data/raw/.")
    print("Next: human eligibility screening (§3.3) on both_term_hit rows;")
    print("      manual screening of ambiguous_only rows (§3.2).")


if __name__ == "__main__":
    main()
