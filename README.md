<p align="center">
  <img src="docs/assets/images/logo.svg" width="72" height="72" alt="Photo Geometry arXiv Daily logo">
</p>

<h1 align="center">Photo Geometry arXiv Daily</h1>

<p align="center">
  Daily-updated arXiv papers on <strong>photo geometry</strong>: camera models, intrinsic and extrinsic
  calibration, generalized cameras, multi-view geometry, pose estimation and 3D reconstruction.
</p>

<p align="center">
  <a href="../../actions/workflows/daily-arxiv.yml"><img alt="Daily arXiv update" src="../../actions/workflows/daily-arxiv.yml/badge.svg"></a>
  <a href="../../actions/workflows/tests.yml"><img alt="Tests" src="../../actions/workflows/tests.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
</p>

---

## What it does

Every day a GitHub Actions workflow queries the [arXiv API](https://info.arxiv.org/help/api/index.html) for new papers in 20 photo-geometry topics, merges them into a JSON archive, finds code and project links, and publishes a fast, searchable website with GitHub Pages:

- **Home** — statistics, the date range covered, the 20 research topics and the 60 most recent papers, with an instant filter.
- **Topic pages** — the newest papers of each topic (up to 300; the Explorer has the rest), their date range and the exact arXiv query that defines the topic.
- **Paper Explorer** — search the whole archive by title, author, arXiv ID, venue, topic and code availability; filters are kept in the URL.
- **JSON archive** — `docs/photo-geometry-arxiv-daily.json`, one record per paper.

## Research topics

| Camera models and calibration | Views, pose and estimation | Reconstruction and motion | Photometry, rendering and geo |
|:--|:--|:--|:--|
| Camera Calibration & Intrinsics | Single-View & Projective Geometry | Structure from Motion & Bundle Adjustment | Photometric Stereo & Shape-from-X |
| Extrinsic & Multi-Sensor Calibration | Epipolar Geometry & Relative Pose | Feed-Forward 3D Reconstruction | Neural Rendering & Novel View Synthesis |
| Generalized & Non-Central Camera Models | Minimal Solvers & Robust Estimation | Stereo & Multi-View Stereo | Photogrammetry & Satellite Geometry |
| Omnidirectional, Fisheye & Panoramic Imaging | Absolute Pose & Visual Localization | SLAM & Visual Odometry | Geo-Localization & Place Recognition |
| | Feature Matching & Correspondence | Optical Flow, Scene Flow & Ego-Motion | |
| | | Monocular Depth & Surface Normals | |
| | | Point Cloud Registration | |

The taxonomy follows the classical structure of multiple-view geometry, with dedicated topics for **generalized cameras** (a camera, or a whole camera network, described as a set of rays in Plücker coordinates) and for **calibrating cameras with other sensors and natural cues** (camera–range-sensor extrinsics, geolocating static cameras, calibration from shadows and the sky).

### How a topic is matched

Each topic in [`config.yaml`](config.yaml) has `title_keywords` (must appear in the title) and `keywords` (specific phrases that may appear in the title or abstract), optionally `exclude_title_keywords`, and every query is restricted to the categories **cs.CV, cs.RO, cs.GR and eess.IV**. arXiv's search is case-insensitive, treats hyphens as spaces and stems words, so the phrases were chosen and tested against the live arXiv API to avoid ambiguous stems (for example *generalized* also matches *generation*). Every topic page shows its exact query with a link that runs it on arXiv.

## Quick start

```bash
pip install -r requirements.txt
python test_local.py --mode check   # validate config.yaml and print every arXiv query
python test_local.py --mode quick   # 2 topics x 5 papers into ./_local_test/ (docs/ untouched)
python daily_arxiv.py               # full update of docs/ (same as the daily workflow)
```

| Command | Purpose |
|:--|:--|
| `python daily_arxiv.py` | Fetch new papers, update the archive and rebuild the site |
| `python daily_arxiv.py --update-links` | Re-check recent papers without code (Hugging Face Papers API) |
| `python daily_arxiv.py --render-only` | Rebuild the site from the archive, offline |
| `--topics SLUG ...`, `--max-results N`, `--no-hf`, `--config PATH` | Limit topics, override the result count, skip link lookups, use another config |
| `python -m pytest -q` | Offline test suite (install `requirements-dev.txt`) |

Requires Python 3.10 or newer (tested on 3.10 to 3.14); the workflows use Python 3.12.

## Deploy on GitHub

1. Push this repository to GitHub.
2. *Settings → Actions → General → Workflow permissions*: **Read and write permissions**.
3. *Settings → Pages*: **Deploy from a branch**, your default branch, folder **`/docs`**.
4. *Actions → Daily arXiv update → Run workflow* for the first update.

The site address is detected automatically, so nothing has to be edited when the repository is renamed.

| Workflow | Schedule (UTC) | Purpose |
|:--|:--|:--|
| [`daily-arxiv.yml`](.github/workflows/daily-arxiv.yml) | daily 03:17 | Fetch new papers, rebuild `docs/`, commit only when something changed |
| [`update-code-links.yml`](.github/workflows/update-code-links.yml) | Mondays 05:23 | Re-check recent papers that had no code link |
| [`tests.yml`](.github/workflows/tests.yml) | push / pull request | Validate the config and run the tests on Python 3.10, 3.12, 3.13 and 3.14 |

## Project layout

```
config.yaml                 topics, arXiv settings and output options
daily_arxiv.py              fetch -> archive -> code links -> website generator
test_local.py               local helper (check / quick / full / links / render)
tests/                      offline tests with a recorded arXiv API response
.github/workflows/          daily update, weekly link refresh, tests
.github/scripts/            commit-and-push helper used by the two data workflows
docs/                       GitHub Pages site (Jekyll + Just the Docs)
  photo-geometry-arxiv-daily.json   the archive (generated)
  index.html, explorer.html, topics/ generated pages (do not edit by hand)
  about.md, setup.md                 hand-written pages
  assets/css/photogeo.css, assets/js/photogeo.js   site styles and script
```

## Data notes

- Dates are arXiv first-version (v1) submission dates, in UTC. arXiv announces new papers Sunday to Thursday at 20:00 US Eastern time, so new papers normally appear with the runs from Monday to Friday (UTC).
- Code and project links come from the paper's arXiv abstract or comments, otherwise from the [Hugging Face Papers API](https://huggingface.co/papers) (the Papers with Code service and API were retired in July 2025).
- Titles, author names and comments are converted from TeX to readable text (`$360^\circ$` → 360°).

## License and acknowledgements

The code is released under the [MIT License](LICENSE). Thank you to arXiv for use of its open access interoperability; each paper remains subject to the license chosen by its authors. The website uses the [Just the Docs](https://just-the-docs.com/) theme.
