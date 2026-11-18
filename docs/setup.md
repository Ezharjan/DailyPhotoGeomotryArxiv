---
layout: default
title: Setup Guide
nav_order: 5
description: "Run Photo Geometry arXiv Daily locally, customize its topics and deploy it with GitHub Actions and GitHub Pages."
---

# Setup Guide
{: .no_toc }

1. TOC
{:toc}

## Run it locally

Requirements: Python 3.10 or newer (3.12 recommended) and internet access to `export.arxiv.org` and `huggingface.co`.

```bash
git clone https://github.com/<your-account>/<your-repository>.git
cd <your-repository>
pip install -r requirements.txt

python test_local.py --mode check   # validate config.yaml and print every arXiv query
python test_local.py --mode quick   # 2 topics x 5 papers into ./_local_test/ (docs/ untouched)
python daily_arxiv.py               # full update of docs/ (same as the daily workflow)
```

`python test_local.py` without arguments opens an interactive menu with the same options.

### Command reference

| Command | What it does |
|:--|:--|
| `python daily_arxiv.py` | Fetch the newest papers for every topic, update the JSON archive and rebuild the site |
| `python daily_arxiv.py --update-links` | Re-check recent papers without a code link on the Hugging Face Papers API |
| `python daily_arxiv.py --render-only` | Rebuild the pages from the JSON archive without network access |
| `--topics SLUG [SLUG ...]` | Only fetch the given topics, e.g. `--topics camera-calibration generalized-cameras` |
| `--max-results N` | Papers requested per topic for this run |
| `--no-hf` | Skip Hugging Face code-link lookups |
| `--config PATH` | Use another configuration file (paths inside it are relative to its folder) |

Exit codes: `0` success (some topics may have failed with a warning), `1` invalid configuration, `2` invalid command-line arguments, or every arXiv query failed (nothing was written).

### Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The tests run offline: they replay a recorded arXiv API response and check fetching, merging, link extraction, TeX cleaning, HTML escaping and page generation.

## Configure topics

Everything is configured in `config.yaml`:

| Key | Meaning |
|:--|:--|
| `arxiv.categories` | arXiv categories searched (a paper matches if any of its categories is listed) |
| `arxiv.max_results_per_topic` | Newest papers requested per topic and run |
| `arxiv.request_delay_seconds` | Pause between arXiv requests (at least 3 s, as the arXiv API terms require) |
| `code_links.*` | Hugging Face lookups: on/off, budget per run, re-check window in days |
| `output.data_file` | The JSON archive (must be inside `output.site_dir`) |
| `output.home_latest_papers` | Papers listed on the home page |
| `output.topic_page_max_papers` | Papers listed on each topic page (the Explorer always searches everything) |

Each entry under `topics:` defines one topic:

```yaml
  - slug: camera-calibration                 # stable identifier, used in URLs and the archive
    name: "Camera Calibration & Intrinsics"
    description: "Intrinsic calibration, lens distortion models, ..."
    title_keywords: ["camera calibration", "focal length"]   # must appear in the title
    keywords: ["radial distortion", "lens distortion"]       # may appear in the title or abstract
    exclude_title_keywords: ["tomography"]                  # optional: drop papers with these in the title
```

Tips for accurate topics:

- Put generic phrases that are often mentioned in passing (for example "optical flow" or "camera pose") in `title_keywords`, and reserve `keywords` for specific technical phrases.
- arXiv search is case-insensitive, treats hyphens as spaces and stems words: *calibrated* matches *calibration*, *projective* matches *projection* and *generalized* matches *generation*. Avoid phrases whose stems are ambiguous.
- Phrases must not contain `"`, `(`, `)`, `:` or `\`.
- Check a topic before committing it: `python test_local.py --mode check` prints a link that runs the query on the arXiv API, and every topic page has a "Run on the arXiv API" link.
- Keep slugs stable. Removing a topic removes the papers that belong only to that topic from the archive (they stay in the git history).

## Deploy on GitHub

1. **Create a repository** and push this project to it.
2. **Allow the workflows to commit:** *Settings → Actions → General → Workflow permissions → Read and write permissions*.
3. **Enable GitHub Pages:** *Settings → Pages → Build and deployment → Deploy from a branch*, then choose your default branch and the `/docs` folder.
4. **Run the first update:** *Actions → Daily arXiv update → Run workflow*. The site is published at `https://<your-account>.github.io/<your-repository>/` a few minutes later.

The site address is detected automatically, so no URL needs to be edited when the repository is renamed.

### Workflows

| Workflow | Schedule | Purpose |
|:--|:--|:--|
| `daily-arxiv.yml` | daily, 03:17 UTC | Fetch new papers, rebuild `docs/`, commit only when something changed |
| `update-code-links.yml` | Mondays, 05:23 UTC | Re-check recent papers without code |
| `tests.yml` | on push and pull request | Validate `config.yaml` and run the test suite on Python 3.10, 3.12, 3.13 and 3.14 |

Both data workflows share a concurrency group, so they never write at the same time. Change a schedule by editing its `cron` line (times are UTC; see [crontab.guru](https://crontab.guru/)). Automatic commits use the `github-actions[bot]` identity, set by `COMMIT_USER_NAME` and `COMMIT_USER_EMAIL` in the workflow files.

## Preview the website locally

The site uses Jekyll with the [Just the Docs](https://just-the-docs.com/) theme. With Ruby and Bundler installed:

```bash
cd docs
bundle install
bundle exec jekyll serve
```

Then open <http://localhost:4000>. The pages in `docs/index.html`, `docs/explorer.html` and `docs/topics/` are generated by `daily_arxiv.py`; edit the generator or `config.yaml` rather than these files. Styles and scripts live in `docs/assets/css/photogeo.css` and `docs/assets/js/photogeo.js`.

## Troubleshooting

**The site shows "Not updated yet".** The data workflow has not run yet. Start it from the Actions tab, or run `python daily_arxiv.py` locally and commit `docs/`.

**A workflow run failed.** Open the run in the Actions tab. Failed topics are listed as warnings; if every arXiv request failed (arXiv maintenance or an outage), nothing is written and the next scheduled run catches up, because each run requests the newest papers of every topic. If the arXiv API rate-limits the run (HTTP 429 or 503), the query is retried after 30 s and 90 s; if the limit persists, the remaining topics are skipped for that run rather than adding more requests.

**Pages show without styling or with broken links.** Check that GitHub Pages builds from the `/docs` folder. For a custom domain or a non-GitHub host, set `url` and `baseurl` in `docs/_config.yml`.

**Few code links.** Links come from the arXiv metadata and from the Hugging Face Papers API; many papers publish code weeks after submission, which the weekly refresh picks up.

**Start the archive from scratch.** Delete `docs/photo-geometry-arxiv-daily.json` and run `python daily_arxiv.py`.

## Data format

`docs/photo-geometry-arxiv-daily.json` stores one record per paper (newest first, one paper per line for readable diffs):

```json
{
  "schema_version": 2,
  "updated_at": "2026-11-17T03:17:44Z",
  "topics": [{"slug": "camera-calibration", "name": "Camera Calibration & Intrinsics", "description": "..."}],
  "papers": {
    "2611.04822": {"id": "2611.04822", "title": "...", "authors": ["..."], "n_authors": 2,
                   "published": "2026-11-03", "updated": "2026-11-03", "primary_category": "cs.CV",
                   "categories": ["cs.CV"], "comment": "", "journal_ref": "ICPR 2026",
                   "code": "", "project": "", "topics": ["camera-calibration"],
                   "first_seen": "2026-11-17", "links_checked": "2026-11-17"}
  }
}
```

`authors` keeps the first ten names and `n_authors` the full count; `published` and `updated` are arXiv v1 and latest-version dates (UTC); `updated_at` is the time the paper data last changed.
