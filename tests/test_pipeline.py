"""Offline tests for daily_arxiv.py (no network access required)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import daily_arxiv as da  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "arxiv_camera_calibration.xml"


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------


def write_config(tmp_path: Path, topics: list[dict], **output) -> Path:
    cfg = {
        "arxiv": {"categories": ["cs.CV", "cs.RO"], "max_results_per_topic": 10},
        "code_links": {"huggingface_lookup": True, "max_lookups_per_run": 5, "recheck_days": 30},
        "output": {"data_file": "docs/data.json", "site_dir": "docs", **output},
        "topics": topics,
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def make_paper(arxiv_id: str, published: str, **extra) -> dict:
    paper = {
        "id": arxiv_id,
        "title": f"Paper {arxiv_id}",
        "authors": ["Ada Lovelace", "Alan Turing", "Grace Hopper", "Edsger Dijkstra"],
        "n_authors": 4,
        "published": published,
        "updated": published,
        "primary_category": "cs.CV",
        "categories": ["cs.CV"],
        "comment": "",
        "journal_ref": "",
        "code": "",
        "project": "",
    }
    paper.update(extra)
    return paper


class FakeResponse:
    def __init__(self, status: int = 200, body: bytes | str = b"", json_data=None):
        self.status_code = status
        self.content = body.encode("utf-8") if isinstance(body, str) else body
        self.text = self.content.decode("utf-8", "replace")
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


# -----------------------------------------------------------------------------
# configuration
# -----------------------------------------------------------------------------


def test_repository_config_is_valid():
    cfg = da.load_config(ROOT / "config.yaml")
    assert len(cfg.topics) == 20
    assert len({t.slug for t in cfg.topics}) == 20
    assert cfg.categories == ("cs.CV", "cs.RO", "cs.GR", "eess.IV")
    assert cfg.data_file == (ROOT / "docs" / "photo-geometry-arxiv-daily.json").resolve()
    for topic in cfg.topics:
        assert topic.description, topic.slug
        query = da.build_query(topic, cfg.categories)
        # keep URLs comfortably short for the arXiv API
        assert len(query) < 1500, (topic.slug, len(query))
        assert query.count("(") == query.count(")")
        assert query.count('"') % 2 == 0


def test_config_rejects_bad_phrases_and_slugs(tmp_path):
    bad = [
        ({"name": "A", "keywords": ['bad "quote"']}, "must not contain"),
        ({"name": "A", "slug": "Bad Slug", "keywords": ["x"]}, "slug"),
        ({"name": "A", "keywords": []}, "needs at least one"),
        ({"name": "A", "keywords": ["ti:raw"]}, "must not contain"),
    ]
    for topic, message in bad:
        with pytest.raises(da.ConfigError, match=message):
            da.load_config(write_config(tmp_path, [topic]))
    with pytest.raises(da.ConfigError, match="duplicate topic slug"):
        da.load_config(write_config(tmp_path, [{"name": "A", "slug": "a", "keywords": ["x"]},
                                               {"name": "B", "slug": "a", "keywords": ["y"]}]))
    with pytest.raises(da.ConfigError, match="inside output.site_dir"):
        da.load_config(write_config(tmp_path, [{"name": "A", "keywords": ["x"]}], data_file="data.json"))
    with pytest.raises(da.ConfigError, match="must not start with"):
        da.load_config(write_config(tmp_path, [{"name": "A", "keywords": ["x"]}], data_file="docs/_data/x.json"))


def test_request_delay_must_respect_arxiv_terms(tmp_path):
    path = write_config(tmp_path, [{"name": "A", "keywords": ["x"]}])
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["arxiv"]["request_delay_seconds"] = 1
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(da.ConfigError, match="request_delay_seconds"):
        da.load_config(path)


def test_legacy_keywords_format_is_converted(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "output: {data_file: docs/d.json, site_dir: docs}\n"
        "keywords:\n  \"Camera Calibration\":\n    filters: [\"camera calibration\", \"lens distortion\"]\n",
        encoding="utf-8",
    )
    cfg = da.load_config(path)
    assert cfg.topics[0].slug == "camera-calibration"
    assert cfg.topics[0].keywords == ("camera calibration", "lens distortion")


# -----------------------------------------------------------------------------
# query construction
# -----------------------------------------------------------------------------


def test_build_query_title_abstract_categories_and_exclusions():
    topic = da.Topic(
        slug="t", name="T", description="",
        title_keywords=("single view metrology", "Fisheye"),
        keywords=("single-view metrology", "vanishing point"),
        exclude_title_keywords=("CT",),
    )
    query = da.build_query(topic, ["cs.CV", "eess.IV"])
    assert query == (
        '((ti:"single view metrology" OR ti:"Fisheye" OR ti:"vanishing point" OR '
        'abs:"single-view metrology" OR abs:"vanishing point") AND (cat:cs.CV OR cat:eess.IV)) '
        'ANDNOT (ti:"CT")'
    )


def test_dedupe_phrases_is_case_and_hyphen_insensitive():
    assert da.dedupe_phrases(["Self-Calibration", "self calibration", "SELF  calibration", "x"]) == (
        "Self-Calibration", "x")


def test_prune_subsumed_phrases():
    phrases = ("focal length", "focal length estimation", "pushbroom camera", "pushbroom",
               "multi-view stereo", "stereo", "length focal")
    assert da.prune_subsumed(phrases) == ("focal length", "pushbroom", "stereo", "length focal")
    topic = da.Topic(slug="t", name="T", description="", title_keywords=("focal length",),
                     keywords=("focal length estimation", "radial distortion"))
    assert da.build_query(topic, []) == (
        '(ti:"focal length" OR ti:"radial distortion" OR abs:"focal length estimation" OR abs:"radial distortion")')


def test_arxiv_api_url_encodes_query():
    url = da.arxiv_api_url('(ti:"a b") AND (cat:cs.CV)')
    assert url.startswith("https://export.arxiv.org/api/query?search_query=%28ti%3A%22a%20b%22%29")
    assert "sortBy=submittedDate" in url and "sortOrder=descending" in url


# -----------------------------------------------------------------------------
# text cleaning and identifiers
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("Plain   title\n with  spaces", "Plain title with spaces"),
    (r"Efficient $360^\circ$ Depth", "Efficient 360° Depth"),
    (r"An $\mathcal{L}_1$ Adaptive Optimizer", "An L₁ Adaptive Optimizer"),
    (r"Pl\"ucker lines and M\"{u}ller {\"o} \v{C}ech \c c \'\i", "Plücker lines and Müller ö Čech ç í"),
    (r"Water--Land --- ``quoted''", "Water–Land — “quoted”"),
    (r"$SE(3)$, $\mathbb{R}^3$, $10^{-3}$, $x^{T}$, $^{\dagger}$", "SE(3), R³, 10⁻³, x^T, †"),
    (r"Cost \& Speed: 50\% on $\sim$100 \textbf{Bold \emph{nested}}", "Cost & Speed: 50% on ∼100 Bold nested"),
    ("Under $100 budget", "Under $100 budget"),
    (r"\LaTeX{} keeps SAM_2 and x^2 outside math", "LaTeX keeps SAM_2 and x^2 outside math"),
    (r"$\alpha$-expansion, $\ell_1$, $\pi^3$", "α-expansion, ℓ₁, π³"),
])
def test_tex_to_text(raw, expected):
    assert da.tex_to_text(raw) == expected


def test_strip_version_and_truncate():
    assert da.strip_version("2611.04822v12") == "2611.04822"
    assert da.strip_version("math/0211159v1") == "math/0211159"
    assert da.strip_version("2611.04822") == "2611.04822"
    assert da.truncate("one two three four", 9) == "one two…"
    assert len(da.truncate("x" * 50, 10)) == 10


# -----------------------------------------------------------------------------
# links
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("text, code, project", [
    ("Code: https://github.com/foo/Bar.git). Project: https://foo.github.io/bar/.",
     "https://github.com/foo/Bar", "https://foo.github.io/bar/"),
    ("Code at github.com/acme/vision-tool, page acme.github.io/proj.",
     "https://github.com/acme/vision-tool", "https://acme.github.io/proj"),
    (r"\url{https://gitlab.com/grp/sub/repo/-/tree/main}", "https://gitlab.com/grp/sub/repo", ""),
    ("https://github.com/foo/bar/tree/main/src and https://www.github.com/x/y",
     "https://github.com/foo/bar", ""),
    ("Data at https://huggingface.co/datasets/x/y and https://doi.org/10.1/abc", "", ""),
    ("see https://github.com/orgs/foo and (https://example.org/proj).", "", "https://example.org/proj"),
    ("Licence https://creativecommons.org/licenses/by/4.0/", "", ""),
    ("", "", ""),
])
def test_extract_links(text, code, project):
    assert da.extract_links(text) == (code, project)


def test_normalize_code_url_rejects_non_repositories():
    assert da.normalize_code_url("https://github.com/foo") == ""
    assert da.normalize_code_url("https://github.com/features/actions") == ""
    assert da.normalize_code_url("https://example.com/foo/bar") == ""
    assert da.normalize_code_url("https://github.com/Foo-Bar/repo.name.git") == "https://github.com/Foo-Bar/repo.name"


# -----------------------------------------------------------------------------
# Hugging Face lookups
# -----------------------------------------------------------------------------


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_hf_resolver_parses_links_and_handles_404():
    session = FakeSession([
        FakeResponse(200, json_data={"githubRepo": "https://github.com/facebookresearch/vggt",
                                     "projectPage": "https://vgg-t.github.io/"}),
        FakeResponse(404),
    ])
    resolver = da.HFLinkResolver(session=session, max_lookups=10, sleep=lambda s: None)
    assert resolver.lookup("2503.11651") == ("https://github.com/facebookresearch/vggt", "https://vgg-t.github.io/")
    assert resolver.lookup("2611.04822") == ("", "")
    assert resolver.lookup("math/0211159") == ("", "")  # old-style IDs are not looked up
    assert len(session.calls) == 2


def test_hf_resolver_budget_rate_limit_and_errors():
    resolver = da.HFLinkResolver(session=FakeSession([FakeResponse(429)]), max_lookups=10, sleep=lambda s: None)
    assert resolver.lookup("2501.00001") is None and resolver.disabled
    errors = [requests.ConnectionError("boom")] * 3
    resolver = da.HFLinkResolver(session=FakeSession(errors), max_lookups=10, max_consecutive_errors=3,
                                 sleep=lambda s: None)
    assert [resolver.lookup("2501.00001") for _ in range(3)] == [None, None, None]
    assert resolver.disabled
    resolver = da.HFLinkResolver(session=FakeSession([FakeResponse(404)] * 2), max_lookups=1, sleep=lambda s: None)
    assert resolver.lookup("2501.00001") == ("", "")
    assert resolver.lookup("2501.00002") is None


# -----------------------------------------------------------------------------
# archive
# -----------------------------------------------------------------------------


def test_arxiv_client_requests_have_a_timeout():
    """The arxiv package sends requests without a timeout; make_arxiv_client adds one."""
    import arxiv
    from requests.adapters import HTTPAdapter

    seen = []

    class RecordingAdapter(HTTPAdapter):
        def send(self, request, **kwargs):
            seen.append(kwargs.get("timeout"))
            response = requests.Response()
            response.status_code = 200
            response._content = FIXTURE.read_bytes()
            response.url = request.url
            response.request = request
            return response

    client = da.make_arxiv_client(da.load_config(ROOT / "config.yaml"))
    client.delay_seconds = 0
    for prefix in ("https://", "http://"):
        client._session.mount(prefix, RecordingAdapter())
    results = list(client.results(arxiv.Search(query='ti:"camera calibration"', max_results=3)))
    assert len(results) == 3
    assert seen and all(timeout == (15.0, 90.0) for timeout in seen)


def test_merge_paper_inserts_updates_and_keeps_links():
    papers: dict = {}
    assert da.merge_paper(papers, make_paper("2611.00001", "2026-11-02", code="https://github.com/a/b",
                                             comment="CVPR 2026"), "t1", "2026-11-03")
    record = papers["2611.00001"]
    assert record["topics"] == ["t1"] and record["first_seen"] == "2026-11-03"
    update = make_paper("2611.00001", "2026-11-02", title="New title", updated="2026-11-05", code="", comment="")
    assert da.merge_paper(papers, update, "t2", "2026-11-06")
    assert record["title"] == "New title" and record["updated"] == "2026-11-05"
    assert record["code"] == "https://github.com/a/b"  # never dropped
    assert record["comment"] == ""                        # authoritative latest metadata
    assert record["topics"] == ["t1", "t2"] and record["first_seen"] == "2026-11-03"
    assert not da.merge_paper(papers, update, "t2", "2026-11-07")


def test_normalize_topics_orders_and_prunes(tmp_path):
    cfg = da.load_config(write_config(tmp_path, [
        {"name": "A", "slug": "a", "keywords": ["x"]}, {"name": "B", "slug": "b", "keywords": ["y"]}]))
    papers = {
        "1": {**make_paper("1", "2026-01-01"), "topics": ["b", "gone", "a"]},
        "2": {**make_paper("2", "2026-01-02"), "topics": ["gone"]},
    }
    assert da.normalize_topics(papers, cfg) == 1
    assert papers["1"]["topics"] == ["a", "b"] and "2" not in papers


def test_serialize_and_load_roundtrip(tmp_path):
    archive = da.empty_archive()
    archive["updated_at"] = "2026-11-17T03:17:44Z"
    archive["topics"] = [{"slug": "a", "name": "A & B", "description": "Ünïcode"}]
    for arxiv_id, date in [("2611.00002", "2026-11-02"), ("2611.00010", "2026-11-02"), ("2610.00001", "2026-10-30")]:
        archive["papers"][arxiv_id] = {**make_paper(arxiv_id, date), "topics": ["a"], "first_seen": date,
                                       "links_checked": ""}
    text = da.serialize_archive(archive)
    data = json.loads(text)
    assert list(data["papers"]) == ["2611.00010", "2611.00002", "2610.00001"]  # newest first
    assert "Ünïcode" in text and text.endswith("}\n") and "\r" not in text
    path = tmp_path / "a.json"
    assert da.write_if_changed(path, text) and not da.write_if_changed(path, text)
    assert path.read_bytes().count(b"\r") == 0
    loaded = da.load_archive(path)
    assert loaded["papers"] == data["papers"] and loaded["updated_at"] == "2026-11-17T03:17:44Z"


def test_load_archive_handles_missing_empty_legacy_and_malformed(tmp_path):
    assert da.load_archive(tmp_path / "missing.json")["papers"] == {}
    (tmp_path / "empty.json").write_text("", encoding="utf-8")
    assert da.load_archive(tmp_path / "empty.json")["papers"] == {}
    legacy = {"Topic": {"2601.00001": "|**2026-01-01**|**T**|A et.al.|[2601.00001](http://arxiv.org/abs/2601.00001)||\n"}}
    (tmp_path / "legacy.json").write_text(json.dumps(legacy), encoding="utf-8")
    assert da.load_archive(tmp_path / "legacy.json")["papers"] == {}
    bad = {"schema_version": 2, "papers": {"x": {"id": "x"}, "y": make_paper("y", "2026-01-01")}}
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    assert list(da.load_archive(tmp_path / "bad.json")["papers"]) == ["y"]


# -----------------------------------------------------------------------------
# rendering
# -----------------------------------------------------------------------------


def split_front_matter(page: str) -> tuple[dict, str]:
    assert page.startswith("---\n")
    _, fm, body = page.split("---\n", 2)
    return yaml.safe_load(fm), body


def test_render_escapes_html_and_liquid(tmp_path):
    cfg = da.load_config(write_config(tmp_path, [{"name": "Calib & Co", "slug": "calib", "keywords": ["x"]}]))
    evil = make_paper(
        "2611.00001", "2026-11-02",
        title="<script>alert(1)</script> {{ site.title }} {% include x %} a|b & c",
        authors=['O"Neil {{x}}'], n_authors=1, comment="{% raw %} <b>", journal_ref="J & K",
        code="https://github.com/a/b", project="https://a.github.io/b?x=1&y=2",
    )
    archive = da.empty_archive()
    archive["papers"][evil["id"]] = {**evil, "topics": ["calib"], "first_seen": "2026-11-02", "links_checked": ""}
    pages = da.render_site(archive, cfg)
    for path, page in pages.items():
        fm, body = split_front_matter(page)
        assert fm["layout"] == "default"
        assert "<script>" not in body
        liquid = body.replace("{{ '/data.json' | relative_url }}", "").replace("{{ '/topics/' | relative_url }}", "")
        assert "{{" not in liquid and "{%" not in liquid, path
    home = pages[cfg.site_dir / "index.html"]
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &#123;&#123; site.title &#125;&#125;" in home
    assert 'href="https://a.github.io/b?x=1&amp;y=2"' in home
    assert 'rel="noopener"' in home and "a|b &amp; c" in home


def test_render_site_structure_caps_and_stale_pages(tmp_path):
    cfg = da.load_config(write_config(
        tmp_path,
        [{"name": "Alpha", "slug": "alpha", "keywords": ["x"]}, {"name": "Beta", "slug": "beta", "keywords": ["y"]}],
        home_latest_papers=3, topic_page_max_papers=2,
    ))
    archive = da.empty_archive()
    archive["updated_at"] = "2026-11-17T03:17:44Z"
    for i in range(5):
        pid = f"2611.0000{i}"
        archive["papers"][pid] = {**make_paper(pid, f"2026-11-0{i + 1}"), "topics": ["alpha", "beta"] if i % 2 else ["alpha"],
                                  "first_seen": "2026-11-17", "links_checked": ""}
    pages = da.render_site(archive, cfg)
    names = sorted(p.relative_to(cfg.site_dir).as_posix() for p in pages)
    assert names == ["explorer.html", "index.html", "topics/alpha.html", "topics/beta.html", "topics/index.html"]
    home = pages[cfg.site_dir / "index.html"]
    assert home.count("<tr data-code=") == 3 and "2611.00004" in home and "2611.00001" not in home
    alpha = pages[cfg.site_dir / "topics" / "alpha.html"]
    fm, body = split_front_matter(alpha)
    assert fm == {"layout": "default", "title": "Alpha", "parent": "Topics", "nav_order": 1, "description": "Alpha"}
    assert body.count("<tr data-code=") == 2 and "Showing the 2 most recent of 5 papers" in body
    assert "../explorer.html?topic=alpha" in body and "Also in:" in body
    topics_fm, _ = split_front_matter(pages[cfg.site_dir / "topics" / "index.html"])
    assert topics_fm["has_children"] is True and topics_fm["has_toc"] is False and topics_fm["title"] == "Topics"
    assert 'datetime="2026-11-17T03:17:44Z"' in home
    # stale generated pages are removed, hand-written ones are kept
    (cfg.site_dir / "topics").mkdir(parents=True)
    (cfg.site_dir / "topics" / "old.html").write_text(f"---\n# {da.GENERATED_MARKER}\n---\n", encoding="utf-8")
    (cfg.site_dir / "topics" / "mine.html").write_text("<p>hand written</p>", encoding="utf-8")
    written = da.write_outputs(archive, cfg, data_changed=False)
    assert written == 7  # data file + 5 pages + 1 stale page removed
    assert not (cfg.site_dir / "topics" / "old.html").exists() and (cfg.site_dir / "topics" / "mine.html").exists()
    assert da.write_outputs(archive, cfg, data_changed=False) == 0  # idempotent


def test_render_empty_archive(tmp_path):
    cfg = da.load_config(write_config(tmp_path, [{"name": "Alpha", "slug": "alpha", "keywords": ["x"]}]))
    pages = da.render_site(da.empty_archive(), cfg)
    home = pages[cfg.site_dir / "index.html"]
    assert "Not updated yet" in home
    assert "most recent" not in home and "submitted from" not in home and "Papers submitted" not in home
    assert "No papers in this topic yet." in pages[cfg.site_dir / "topics" / "alpha.html"]


def test_render_date_ranges(tmp_path):
    cfg = da.load_config(write_config(
        tmp_path,
        [{"name": "Alpha", "slug": "alpha", "keywords": ["x"]}, {"name": "Beta", "slug": "beta", "keywords": ["y"]}],
        topic_page_max_papers=2,
    ))
    archive = da.empty_archive()
    archive["updated_at"] = "2026-11-17T03:17:44Z"
    for pid, day, topics in [("2611.00001", "2026-11-01", ["alpha"]), ("2611.00003", "2026-11-03", ["alpha", "beta"]),
                             ("2611.00005", "2026-11-05", ["alpha"])]:
        archive["papers"][pid] = {**make_paper(pid, day), "topics": topics, "first_seen": "2026-11-17", "links_checked": ""}
    pages = da.render_site(archive, cfg)

    def t(day: str) -> str:
        return f'<time datetime="{day}">{day}</time>'

    home = pages[cfg.site_dir / "index.html"]
    assert f"2026-11-17 03:17 UTC</time> · Papers submitted from {t('2026-11-01')} to {t('2026-11-05')}" in home
    assert f"The 3 most recent papers across all topics, submitted from {t('2026-11-01')} to {t('2026-11-05')}" in home
    # topic cards: count, then the date range (a single date is not shown as a range)
    assert f'3 papers</span> <span class="pg-topic-range">{t("2026-11-01")} to {t("2026-11-05")}</span>' in home
    assert f'1 paper</span> <span class="pg-topic-range">{t("2026-11-03")}</span>' in home
    alpha = pages[cfg.site_dir / "topics" / "alpha.html"]
    assert f"3 papers submitted from {t('2026-11-01')} to {t('2026-11-05')} · 0 with code · Last updated" in alpha
    assert f"Showing the 2 most recent of 3 papers (submitted from {t('2026-11-03')} to {t('2026-11-05')})" in alpha
    beta = pages[cfg.site_dir / "topics" / "beta.html"]
    assert f"1 paper submitted on {t('2026-11-03')} · 0 with code · Last updated" in beta
    index = pages[cfg.site_dir / "topics" / "index.html"]
    assert (f'data-label="Oldest">{t("2026-11-01")}</td><td class="pg-col-date" data-label="Newest">{t("2026-11-05")}'
            in index)
    assert f'data-label="Oldest">{t("2026-11-03")}</td><td class="pg-col-date" data-label="Newest">{t("2026-11-03")}' in index


# -----------------------------------------------------------------------------
# end to end with a real arXiv API response (network mocked)
# -----------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    import arxiv

    monkeypatch.setattr(da, "make_arxiv_client",
                        lambda cfg: arxiv.Client(page_size=100, delay_seconds=0, num_retries=0))
    calls = {"arxiv": 0, "hf": 0}
    xml = FIXTURE.read_bytes()

    def fake_get(self, url, *args, **kwargs):
        if "export.arxiv.org" in url:
            calls["arxiv"] += 1
            return FakeResponse(200, xml)
        if "huggingface.co/api/papers/2610.27547" in url:
            calls["hf"] += 1
            return FakeResponse(200, json_data={"githubRepo": "https://github.com/example/syncalib"})
        if "huggingface.co" in url:
            calls["hf"] += 1
            return FakeResponse(404)
        raise AssertionError(f"unexpected request {url}")

    monkeypatch.setattr(requests.Session, "get", fake_get)
    monkeypatch.setattr(da.time, "sleep", lambda s: None)
    return tmp_path, calls


def test_end_to_end_fetch_render_and_idempotence(project):
    root, calls = project
    args = ["--config", str(root / "config.yaml"), "--topics", "camera-calibration", "extrinsic-calibration"]
    assert da.main(args) == 0
    assert calls["arxiv"] == 2
    data = json.loads((root / "docs" / "photo-geometry-arxiv-daily.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 2 and data["updated_at"].endswith("Z")
    assert len(data["topics"]) == 20
    assert list(data["papers"]) == ["2611.04822", "2610.28791", "2610.27547"]
    first = data["papers"]["2611.04822"]
    assert first["title"].startswith("Radial distortion homography estimation")
    assert first["authors"] == ["Marcus Valtonen Örnhag", "Stefan Adalbjörnsson"]
    assert first["published"] == "2026-11-03" and first["journal_ref"] == "ICPR 2026"
    assert first["primary_category"] == "cs.CV" and first["topics"] == ["camera-calibration", "extrinsic-calibration"]
    veri = data["papers"]["2610.28791"]
    assert veri["n_authors"] == 11 and len(veri["authors"]) == 10 and veri["comment"] == "35 pages, 20 figures, 13 tables"
    assert data["papers"]["2610.27547"]["code"] == "https://github.com/example/syncalib"
    assert calls["hf"] == 3
    docs = root / "docs"
    for name in ["index.html", "explorer.html", "topics/index.html", "topics/camera-calibration.html",
                 "topics/geo-localization.html"]:
        assert (docs / name).is_file(), name
    home = (docs / "index.html").read_text(encoding="utf-8")
    assert "Marcus Valtonen Örnhag, Stefan Adalbjörnsson" in home and "ICPR 2026" in home
    stamp = data["updated_at"]

    # A second identical run changes nothing (no spurious daily commits).
    before = {p: p.read_bytes() for p in docs.rglob("*") if p.is_file()}
    assert da.main(args + ["--no-hf"]) == 0
    after = {p: p.read_bytes() for p in docs.rglob("*") if p.is_file()}
    assert before == after
    assert json.loads((docs / "photo-geometry-arxiv-daily.json").read_text(encoding="utf-8"))["updated_at"] == stamp


def test_all_topics_failing_leaves_files_untouched(project, monkeypatch):
    root, _ = project

    def broken_get(self, url, *args, **kwargs):
        raise requests.ConnectionError("arXiv down")

    monkeypatch.setattr(requests.Session, "get", broken_get)
    assert da.main(["--config", str(root / "config.yaml"), "--topics", "camera-calibration"]) == 2
    assert not (root / "docs").exists()


def test_rate_limit_backs_off_then_succeeds(project, monkeypatch):
    root, _ = project
    xml = FIXTURE.read_bytes()
    sleeps: list[float] = []
    monkeypatch.setattr(da.time, "sleep", sleeps.append)
    requested = []

    def flaky_get(self, url, *args, **kwargs):
        requested.append(url)
        return FakeResponse(429) if len(requested) == 1 else FakeResponse(200, xml)

    monkeypatch.setattr(requests.Session, "get", flaky_get)
    assert da.main(["--config", str(root / "config.yaml"), "--topics", "camera-calibration", "--no-hf"]) == 0
    assert len(requested) == 2 and da.RATE_LIMIT_BACKOFF_SECONDS[0] in sleeps
    data = json.loads((root / "docs" / "photo-geometry-arxiv-daily.json").read_text(encoding="utf-8"))
    assert len(data["papers"]) == 3


def test_persistent_rate_limit_stops_the_run(project, monkeypatch):
    root, _ = project
    sleeps: list[float] = []
    monkeypatch.setattr(da.time, "sleep", sleeps.append)
    requested = []

    def limited_get(self, url, *args, **kwargs):
        requested.append(url)
        return FakeResponse(429)

    monkeypatch.setattr(requests.Session, "get", limited_get)
    args = ["--config", str(root / "config.yaml"), "--topics", "camera-calibration", "extrinsic-calibration", "--no-hf"]
    assert da.main(args) == 2  # every topic failed, so nothing is written
    assert not (root / "docs").exists()
    # one topic: first try + one try per back-off; the second topic is never requested
    assert len(requested) == 1 + len(da.RATE_LIMIT_BACKOFF_SECONDS)
    assert [s for s in sleeps if s >= 30] == list(da.RATE_LIMIT_BACKOFF_SECONDS)


def test_render_only_and_update_links(project):
    root, calls = project
    config = str(root / "config.yaml")
    assert da.main(["--config", config, "--render-only"]) == 0
    assert (root / "docs" / "index.html").is_file()
    assert "Not updated yet" in (root / "docs" / "index.html").read_text(encoding="utf-8")
    assert da.main(["--config", config, "--topics", "camera-calibration", "--no-hf"]) == 0
    assert calls["hf"] == 0
    data_path = root / "docs" / "photo-geometry-arxiv-daily.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    # make the papers "recent" so --update-links re-checks them
    for record in data["papers"].values():
        record["published"] = da.utc_now().date().isoformat()
    data_path.write_text(json.dumps(data), encoding="utf-8")
    assert da.main(["--config", config, "--update-links"]) == 0
    data = json.loads(data_path.read_text(encoding="utf-8"))
    assert data["papers"]["2610.27547"]["code"] == "https://github.com/example/syncalib"
    assert all(r["links_checked"] == da.utc_now().date().isoformat() for r in data["papers"].values())
