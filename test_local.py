#!/usr/bin/env python3
"""Local helper for Photo Geometry arXiv Daily.

Run without arguments for an interactive menu, or pick a mode directly:

    python test_local.py --mode check    # validate config.yaml and print every arXiv query (offline)
    python test_local.py --mode quick    # 2 topics x 5 papers into ./_local_test/ (docs/ is not touched)
    python test_local.py --mode full     # full update of docs/ (what the daily workflow does)
    python test_local.py --mode links    # refresh code links in docs/ (what the weekly workflow does)
    python test_local.py --mode render   # rebuild the docs/ pages from the JSON archive (offline)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import daily_arxiv as da  # noqa: E402

CONFIG = ROOT / "config.yaml"
SANDBOX = ROOT / "_local_test"
MODES = {
    "1": "check",
    "2": "quick",
    "3": "full",
    "4": "links",
    "5": "render",
}


def check() -> int:
    cfg = da.load_config(CONFIG)
    print(f"config.yaml is valid: {len(cfg.topics)} topics, categories {', '.join(cfg.categories)}\n")
    for index, topic in enumerate(cfg.topics, start=1):
        query = da.build_query(topic, cfg.categories)
        print(f"{index:2d}. {topic.name}  [{topic.slug}]")
        print(f"    query ({len(query)} chars): {query}")
        print(f"    test it: {da.arxiv_api_url(query, max_results=20)}\n")
    return 0


def quick() -> int:
    cfg = da.load_config(CONFIG)
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    SANDBOX.mkdir()
    shutil.copy(CONFIG, SANDBOX / "config.yaml")
    slugs = [t.slug for t in cfg.topics[:2]]
    print(f"Quick test: topics {', '.join(slugs)}, 5 papers each, output in {SANDBOX}\n")
    code = da.main(["--config", str(SANDBOX / "config.yaml"), "--topics", *slugs, "--max-results", "5"])
    if code != 0:
        return code
    sandbox_cfg = da.load_config(SANDBOX / "config.yaml")
    data = json.loads(sandbox_cfg.data_file.read_text(encoding="utf-8"))
    print(f"\n{len(data['papers'])} papers fetched:")
    for paper in data["papers"].values():
        code_note = f"  code: {paper['code']}" if paper.get("code") else ""
        print(f"  {paper['published']}  {paper['id']:<12} {paper['title'][:90]}{code_note}")
    print(f"\nOpen {sandbox_cfg.site_dir / 'index.html'} to inspect the generated page source.")
    print("Your docs/ folder was not modified.")
    return 0


def run(mode: str) -> int:
    if mode == "check":
        return check()
    if mode == "quick":
        return quick()
    if mode == "full":
        return da.main(["--config", str(CONFIG)])
    if mode == "links":
        return da.main(["--config", str(CONFIG), "--update-links"])
    if mode == "render":
        return da.main(["--config", str(CONFIG), "--render-only"])
    raise ValueError(mode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local helper for Photo Geometry arXiv Daily.")
    parser.add_argument("--mode", choices=sorted(set(MODES.values())), help="run a mode without the menu")
    args = parser.parse_args()
    if args.mode:
        return run(args.mode)

    print("=" * 72)
    print("Photo Geometry arXiv Daily - local helper")
    print("=" * 72)
    print("1. Check config.yaml and show the arXiv queries (offline)")
    print("2. Quick test: 2 topics x 5 papers into ./_local_test/ (docs/ untouched)")
    print("3. Full update of docs/ (same as the daily workflow)")
    print("4. Refresh code links in docs/ (same as the weekly workflow)")
    print("5. Rebuild the docs/ pages from the JSON archive (offline)")
    try:
        choice = input("Enter choice (1-5): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return 1
    if choice not in MODES:
        print("Invalid choice.")
        return 1
    return run(MODES[choice])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except da.ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
