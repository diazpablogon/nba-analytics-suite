"""Orchestrate the NBA data download subtasks."""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import List

import importlib.util


# ---------------------------------------------------------------------------
# Configuration defaults (editable at the top of the file)
# ---------------------------------------------------------------------------
SEASONS = "2024-25"
INCLUDE_PLAYOFFS = False
SLEEP = 0.8
MAX_RETRIES = 3
PER_MODE = "PerGame"
MEASURE_TYPE = "Advanced"

TASKS = [
    {
        "name": "league_team_stats",
        "script": "01c_get_league_team_stats.py",
        "enabled": True,
        "extra": ["--measure-type", MEASURE_TYPE, "--per-mode", PER_MODE],
    },
    {
        "name": "player_gamelogs",
        "script": "01d_get_player_gamelogs.py",
        "enabled": True,
        "extra": [],
    },
    {
        "name": "player_dash_splits",
        "script": "01e_get_player_dashboard_splits.py",
        "enabled": True,
        "extra": [],
    },
    {
        "name": "teamgamelogs_by_game",
        "script": "01f_get_teamgamelogs_by_game.py",
        "enabled": False,
        "extra": [],
    },
    {
        "name": "team_dashboards",
        "script": "01g_get_team_dashboards.py",
        "enabled": False,
        "extra": [],
    },
    {
        "name": "boxscores",
        "script": "01h_get_boxscores.py",
        "enabled": False,
        "extra": [],
    },
]


# ---------------------------------------------------------------------------
# Helper loader for the shared utilities
# ---------------------------------------------------------------------------
def _load_tools_module():
    module_name = "download_tools"
    if module_name in sys.modules:
        return sys.modules[module_name]

    tools_path = Path(__file__).resolve().parent / "01b_function_tools.py"
    spec = importlib.util.spec_from_file_location(module_name, tools_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError("Unable to locate 01b_function_tools module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


tools = _load_tools_module()
parse_seasons_arg = tools.parse_seasons_arg
repo_root = tools.repo_root


LOGGER = logging.getLogger("01a_downloader_total")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the NBA data download pipeline tasks in sequence.")
    parser.add_argument("--seasons", default=SEASONS, help="Comma-separated list of seasons to download.")
    parser.add_argument("--include-playoffs", action="store_true", help="Include playoff data.")
    parser.add_argument("--sleep", type=float, default=SLEEP, help="Base sleep between endpoint calls.")
    parser.add_argument("--max-retries", type=int, default=MAX_RETRIES, help="Maximum number of retries per call.")
    parser.add_argument("--per-mode", choices=["PerGame", "Totals", "Per36"], default=PER_MODE)
    parser.add_argument(
        "--measure-type",
        choices=["Base", "Advanced", "Four Factors", "Scoring", "Misc", "Usage"],
        default=MEASURE_TYPE,
    )
    return parser


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def run_task(script: str, argv: List[str]) -> tuple[bool, float]:
    start = time.perf_counter()
    try:
        subprocess.run(argv, check=True, cwd=repo_root())
        duration = time.perf_counter() - start
        LOGGER.info("✅ %s (%.2fs)", script, duration)
        return True, duration
    except subprocess.CalledProcessError as exc:
        duration = time.perf_counter() - start
        LOGGER.error("❌ %s failed after %.2fs", script, duration)
        LOGGER.error("Command: %s", " ".join(argv))
        LOGGER.error("Return code: %s", exc.returncode)
        return False, duration


def build_command(script: str, args: argparse.Namespace, extras: List[str]) -> List[str]:
    command = [
        sys.executable,
        str(repo_root() / "scripts" / "01_download_data" / script),
        "--seasons",
        args.seasons,
        "--sleep",
        str(args.sleep),
        "--max-retries",
        str(args.max_retries),
    ]
    if args.include_playoffs:
        command.append("--include-playoffs")
    command.extend(extras)
    return command


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    seasons = parse_seasons_arg(args.seasons)
    if not seasons:
        LOGGER.warning("No seasons provided; tasks will still run with the raw argument value.")

    summary = {"completed": 0, "failed": 0, "durations": []}

    for task in TASKS:
        if not task.get("enabled", False):
            LOGGER.info("Skipping disabled task: %s", task["name"])
            continue
        command = build_command(task["script"], args, task.get("extra", []))
        success, duration = run_task(task["script"], command)
        summary["durations"].append((task["name"], duration))
        if success:
            summary["completed"] += 1
        else:
            summary["failed"] += 1

    LOGGER.info("--- Task summary ---")
    for name, duration in summary["durations"]:
        LOGGER.info("%s: %.2fs", name, duration)
    LOGGER.info(
        "Completed: %s | Failed: %s | Tasks configured: %s",
        summary["completed"],
        summary["failed"],
        sum(1 for task in TASKS if task.get("enabled", False)),
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
