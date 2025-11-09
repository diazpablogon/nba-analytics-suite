"""Placeholder downloader for boxscore endpoints."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict

import importlib.util


def _load_tools_module():
    module_name = "download_tools"
    if module_name in sys.modules:
        return sys.modules[module_name]
    tools_path = Path(__file__).resolve().parent / "01b_function_tools.py"
    spec = importlib.util.spec_from_file_location(module_name, tools_path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError("Unable to import helper utilities")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


tools = _load_tools_module()
DEFAULT_SLEEP = tools.DEFAULT_SLEEP
parse_seasons_arg = tools.parse_seasons_arg
list_game_ids = tools.list_game_ids
output_root = tools.output_root

LOGGER = logging.getLogger("01h_get_boxscores")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download boxscore endpoints (placeholder).")
    parser.add_argument("--seasons", required=True, help="Comma-separated list of seasons.")
    parser.add_argument("--include-playoffs", action="store_true", help="Include playoff data.")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="Sleep between requests.")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retries per request.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    seasons = parse_seasons_arg(args.seasons)
    if not seasons:
        LOGGER.error("No valid seasons provided.")
        return 1

    summary: Dict[str, int] = {"new": 0, "existing": 0, "empty": 0, "errors": 0}

    for season in seasons:
        game_ids = list_game_ids(season, include_playoffs=args.include_playoffs)
        LOGGER.info(
            "TODO: Implement boxscore downloads for %s (%d games) -> %s",
            season,
            len(game_ids),
            output_root() / "boxscore",
        )
        time.sleep(max(args.sleep, 0))

    LOGGER.info(
        "Summary -> new: %s | existing: %s | empty: %s | errors: %s (placeholder)",
        summary["new"],
        summary["existing"],
        summary["empty"],
        summary["errors"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
