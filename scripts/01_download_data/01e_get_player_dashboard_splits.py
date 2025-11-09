"""Download player dashboard splits for each player and season."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List

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
list_player_ids = tools.list_player_ids

LOGGER = logging.getLogger("01e_get_player_dashboard_splits")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download player dashboard by game splits using nba_api.")
    parser.add_argument("--seasons", required=True, help="Comma-separated list of seasons.")
    parser.add_argument("--player-ids", default="", help="Comma-separated list of player IDs. Empty for active players.")
    parser.add_argument("--include-playoffs", action="store_true", help="Include playoff data.")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="Sleep between requests.")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retries per request.")
    return parser


def slugify(value: str) -> str:
    return value.lower().replace(" ", "_").replace("/", "-")


def parse_player_ids(value: str) -> List[int]:
    if value and value.strip():
        ids: List[int] = []
        for item in value.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                ids.append(int(item))
            except ValueError:
                LOGGER.warning("Ignoring invalid player id: %s", item)
        return ids
    LOGGER.info("Loading active player IDs from nba_api static endpoint.")
    return list_player_ids(active_only=True)


def iter_datasets(df) -> Iterable[tuple[str, object]]:
    if df.empty:
        yield "overall", df
        return
    if "dataset" in df.columns:
        for dataset_name, dataset_df in df.groupby("dataset", dropna=False):
            yield str(dataset_name or "unknown"), dataset_df
    else:
        yield "PlayerDashboardByGameSplits", df


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    seasons = parse_seasons_arg(args.seasons)
    if not seasons:
        LOGGER.error("No valid seasons provided.")
        return 1

    player_ids = parse_player_ids(args.player_ids)
    if not player_ids:
        LOGGER.warning("No player IDs to process.")
        return 1

    summary: Dict[str, int] = {"new": 0, "existing": 0, "empty": 0, "errors": 0}

    for season in seasons:
        for season_type in season_types(args.include_playoffs):
            LOGGER.info("Processing %s - %s (%d players)", season, season_type, len(player_ids))
            for idx, player_id in enumerate(player_ids, start=1):
                if idx % 25 == 0:
                    LOGGER.info("Progress %s/%s players for %s %s", idx, len(player_ids), season, season_type)
                base_dir = output_root() / "player_dashboard_by_game_splits" / season / season_type

                try:
                    df = with_retries(
                        fetch_endpoint_to_df,
                        "PlayerDashboardByGameSplits",
                        max_retries=args.max_retries,
                        base_sleep=args.sleep,
                        PlayerID=player_id,
                        Season=season,
                        SeasonType=season_type,
                    )

                    dataset_saved = False
                    for dataset_name, dataset_df in iter_datasets(df):
                        dataset_slug = slugify(str(dataset_name))
                        output_dir = base_dir / dataset_slug
                        output_file = output_dir / f"player_dash_splits__{player_id}__{dataset_slug}.parquet"

                        if output_file.exists():
                            summary["existing"] += 1
                            continue

                        result = save_parquet(
                            dataset_df,
                            output_file,
                            season=season,
                            season_type=season_type,
                            endpoint="PlayerDashboardByGameSplits",
                            player_id=player_id,
                            dataset=str(dataset_name),
                        )
                        dataset_saved = True
                        if result["empty"]:
                            summary["empty"] += 1
                        else:
                            summary["new"] += 1

                    if not dataset_saved and df.empty:
                        summary["empty"] += 1
                except Exception as exc:  # pragma: no cover
                    LOGGER.exception("Error fetching dashboard for player %s (%s %s): %s", player_id, season, season_type, exc)
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
