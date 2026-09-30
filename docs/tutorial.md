# verify-cite: a tutorial with experiments

`verify-cite` is a command-line tool that extracts the bibliography from a research PDF (or an arXiv paper), checks each reference against public academic databases, scores how solid the citation looks, and optionally downloads open-access PDFs.

This article is a guided tour of **what the package does today (v0.1.0)**, what happened when we ran it on three well-known papers **without changing the matching logic**, and what is next.

Install:

```bash
pip install verify-cite
```

The Python import is `verify_cite` (underscores). The console command is `verify-cite` (hyphen). PyPI treats those as the same project name.

First run (no PDF downloads):

```bash
verify-cite 1706.03762 --no-download
```

That downloads the Transformer paper from arXiv, parses the references section, verifies each citation, prints a Rich table, and writes nothing to disk unless you also pass `--output` / enable downloads.

---

## What the pipeline does

```text
PDF or arXiv id
    → extract references (pdfplumber + regex)
    → verify each citation (CrossRef, arXiv, Semantic Scholar, OpenAlex)
    → score 0–100 across six heuristics
    → optional open-PDF download (arXiv → Unpaywall → Semantic Scholar)
    → print table / JSON / Markdown / BibTeX
```

### Extraction

[`verify_cite/extractor.py`](../verify_cite/extractor.py) pulls text with **pdfplumber**, finds a block headed `References` / `Bibliography` / similar, splits numbered entries (`[1]`, `1.`, …), and regex-parses title, authors, year, DOI, and arXiv id.

It already includes a lot of PDF cleanup: hyphenated line breaks, concatenated phrases like `asa` → `as a`, Unicode author names, and venue delimiters such as `In International Conference…`. There is an explicit TODO for **GROBID**; until then, extraction quality is the main bottleneck.

### Verification

[`verify_cite/verifier.py`](../verify_cite/verifier.py) tries, in order:

1. DOI → CrossRef (confidence 1.0 if found)
2. arXiv id → arXiv API (confidence 1.0 if found)
3. Parallel title search across CrossRef, Semantic Scholar, arXiv, and OpenAlex

Title similarity uses `difflib` plus a **prefix match** (short citation title vs full database title → 0.95). Default CLI threshold is **0.7**. Similarity **≥ 0.75** is marked `verified`; between the threshold and 0.75 is `partial`. If the main title fails, the verifier may retry the subtitle after a colon, or title plus venue words.

Results are cached in SQLite under `~/.verify_cite/` (7-day TTL) unless you pass `--no-cache`.

### Scoring

[`verify_cite/scorer.py`](../verify_cite/scorer.py) assigns up to 100 points:

| Dimension       | Max |
|-----------------|-----|
| Verification    | 25  |
| Peer review     | 20  |
| Recency         | 15  |
| Citation impact | 15  |
| Accessibility   | 15  |
| Venue           | 10  |

Venue is a keyword list (Nature, NeurIPS, EMNLP, …), not a curated ranking database. Citation impact currently reads Semantic Scholar’s `citationCount`; if the winning match came from arXiv/CrossRef/OpenAlex alone, impact often scores as zero even when OpenAlex returned `cited_by_count`.

### Downloads

[`verify_cite/downloader.py`](../verify_cite/downloader.py) tries arXiv, then Unpaywall (needs `UNPAYWALL_EMAIL`), then Semantic Scholar open-access PDF URLs. See `.env.example`.

---

## Experiments (as-is)

We measured the **current** extractor + verifier + scorer on three arXiv PDFs. Cache was off. Cited PDFs were **not** downloaded. The harness is [`experiments/benchmark.py`](../experiments/benchmark.py); raw JSON lives in [`experiments/results/`](../experiments/results/).

| arXiv id   | Paper                         | Extracted | Verified | Partial | Unverified | Mean quality | Wall time |
|------------|-------------------------------|-----------|----------|---------|------------|--------------|-----------|
| 1706.03762 | Attention Is All You Need     | 40        | 30 (75%) | 0       | 10         | 47.98        | 359 s     |
| 1810.04805 | BERT                          | **0**     | —        | —       | —          | —            | 2.4 s     |
| 1406.2661  | Generative Adversarial Nets   | 31        | 9 (29%)  | 1       | 21         | 30.52        | 377 s     |

Source: [`experiments/results/summary.json`](../experiments/results/summary.json).

### Reading the table

**Transformer (tuned paper).** February development work focused on this bibliography. Fresh run: **30/40 verified (75%)**, zero partials, mean quality ~48. Extraction found titles for 39/40 entries and arXiv ids for 22/40. No DOIs were parsed from the PDF text (common for this style of arXiv reference list).

**BERT (held-out, same conference era).** Extraction **failed entirely**. In the pdfplumber text, the header is glued to the first citation on one line:

```text
References KevinClark,Minh-ThangLuong,...
```

The references-section regex requires `References` on its own line (`\nReferences\n`), so the tool never enters the bibliography. The error message still suggests `--interactive`, but that flag is not implemented. This is the clearest “as-is” failure mode: **if the section header is not isolated, verify-cite cannot start.**

**GANs (older, different texture).** **9/31 verified (~29%)**, 1 partial, 21 unverified. Only three arXiv ids were extracted. Older conference/journal strings and author-year layouts confuse the regex more; CrossRef and OpenAlex recover some titles, but many rows never get a usable title (for example, author fragments mistaken for titles).

Runtime is dominated by **sequential** API calls (one citation after another), roughly six minutes for a ~40-item bibliography with cache disabled.

### Spot-check (Transformer)

We manually reviewed ten rows from [`1706_03762.json`](../experiments/results/1706_03762.json) (five verified, five unverified). Notes are in [`spot_check.json`](../experiments/results/spot_check.json).

**Verified does not mean clean text.** Examples:

| #  | Extracted title (messy) | Matched database title | OK? |
|----|-------------------------|------------------------|-----|
| 1  | `Layernormalization` | Layer Normalization | Yes — via arXiv id |
| 2  | `…byjointly learning toalign…` | Neural Machine Translation by Jointly Learning to Align and Translate | Yes — via arXiv id |
| 6  | Xception: Deep learning with depthwise separable convolutions | same (casing) | Yes |
| 8  | Recurrent neural network grammars | Recurrent Neural Network Grammars | Yes |
| 37 | `Grammar asa foreign language` | Grammar as a Foreign Language | Yes — `clean_title` helps |

**Unverified often still means a real paper.** Four of five unchecked failures had a valid extracted arXiv id (`1703.10722`, `1508.04025`, `1508.07909`, `1609.08144`) but still landed as unverified: the arXiv id path did not confirm during the long run (rate limiting is a plausible cause), and the concatenated title failed the 0.7 similarity bar. Only citation **#25** is a pure parse failure — the title became `Computationallinguistics,19(2):313–330` (journal metadata) instead of the Penn Treebank title.

So the headline “75% verified” understates recall of *real* references and overstates extraction quality. A fairer mental model: **identity lookup often works when an arXiv id survives; titles from pdfplumber still look broken.**

---

## Useful CLI flags

```bash
verify-cite paper.pdf --verbose          # why each citation failed
verify-cite paper.pdf --threshold 0.6    # looser title match
verify-cite paper.pdf --no-download      # verify + score only
verify-cite paper.pdf --format json
verify-cite paper.pdf --export-bibtex refs.bib
verify-cite paper.pdf --clear-cache
```

---

## Roadmap (grounded in the code)

1. **Bibliography parsing** — glued `References` headers are detected; two-column ACL layouts (e.g. BERT) still scramble citation text under pdfplumber. **GROBID** remains the real fix.
2. **Retry / backoff on arXiv 429** — implemented for ID lookups; keep watching title-search rate limits under parallel verify.
3. **Parallel verification** — CLI now verifies with a concurrency limit of 5 (was strictly sequential).
4. **Wire OpenAlex `cited_by_count` into the scorer** — impact should not depend only on Semantic Scholar’s field name.
5. **Real venue ranking** instead of the keyword list in the scorer.
6. **Config file + batch mode** — thresholds, Unpaywall email, cache TTL, and a directory of PDFs without retyping flags.
7. **Stronger tests** — unit coverage today focuses on utils/extractor string cases; scorer, cache, formatter, and CLI need fixtures; live API tests should not treat `ERROR` as success.

---

## How this differs from other `citeverify` tools

The PyPI name `citeverify` is already taken by a different project that checks bibliography *text files* with almost no dependencies. `verify-cite` focuses on **PDF/arXiv extraction**, multi-source verification including Semantic Scholar and OpenAlex, quality scoring, and optional PDF download. Install this package as `verify-cite` to avoid that clash.

---

## Reproduce the experiments

```bash
git clone https://github.com/panchambanerjee/cite_verify_cli.git
cd cite_verify_cli
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
PYTHONUNBUFFERED=1 python experiments/benchmark.py
```

Expect several minutes per paper and possible arXiv rate limits; the harness downloads PDFs over HTTPS and sleeps between papers. Results are written under `experiments/results/`.
