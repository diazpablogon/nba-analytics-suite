"""Download league team stats for specified seasons."""
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
season_types = tools.season_types
fetch_endpoint_to_df = tools.fetch_endpoint_to_df
save_parquet = tools.save_parquet
output_root = tools.output_root
with_retries = tools.with_retries
ensure_nba_api = tools.ensure_nba_api

LOGGER = logging.getLogger("01c_get_league_team_stats")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download league team stats using nba_api.")
    parser.add_argument("--seasons", required=True, help="Comma-separated list of seasons.")
    parser.add_argument("--include-playoffs", action="store_true", help="Include playoff data.")
    parser.add_argument("--per-mode", choices=["PerGame", "Totals", "Per36"], default="PerGame")
    parser.add_argument(
        "--measure-type",
        choices=["Base", "Advanced", "Four Factors", "Scoring", "Misc", "Usage"],
        default="Advanced",
    )
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="Sleep between requests.")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retries per request.")
    return parser


def slugify(value: str) -> str:
    return value.replace(" ", "_").replace("/", "-")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        ensure_nba_api()
    except ModuleNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 1

    seasons = parse_seasons_arg(args.seasons)
    if not seasons:
        LOGGER.error("No valid seasons provided.")
        return 1

    summary: Dict[str, int] = {"new": 0, "existing": 0, "empty": 0, "errors": 0}

    for season in seasons:
        for season_type in season_types(args.include_playoffs):
            dataset_name = f"{args.measure_type}_{args.per_mode}"
            output_dir = output_root() / "league_dash_team_stats" / season / season_type
            output_file = output_dir / f"league_dash_team_stats__{slugify(args.measure_type)}__{slugify(args.per_mode)}.parquet"

            if output_file.exists():
                LOGGER.info("Skip (exists): %s", output_file)
                summary["existing"] += 1
                continue

            params = {
                "Season": season,
                "SeasonType": season_type,
                "PerMode": args.per_mode,
                "MeasureType": args.measure_type,
            }

            try:
                df = with_retries(
                    fetch_endpoint_to_df,
                    "LeagueDashTeamStats",
                    max_retries=args.max_retries,
                    base_sleep=args.sleep,
                    **params,
                )
                result = save_parquet(
                    df,
                    output_file,
                    season=season,
                    season_type=season_type,
                    endpoint="LeagueDashTeamStats",
                    dataset=dataset_name,
                )
                if result["empty"]:
                    summary["empty"] += 1
                else:
                    summary["new"] += 1
            except Exception as exc:  # pragma: no cover - external dependency handling
                LOGGER.exception("Error fetching %s %s: %s", season, season_type, exc)
                summary["errors"] += 1
            finally:
                time.sleep(max(args.sleep, 0))

    LOGGER.info(
        "Summary -> new: %s | existing: %s | empty: %s | errors: %s",
        summary["new"],
        summary["existing"],
        summary["empty"],
        summary["errors"],
    )
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
