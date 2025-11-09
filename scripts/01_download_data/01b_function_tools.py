"""Utility functions for NBA data downloads."""
from __future__ import annotations

import importlib
import pkgutil
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, List

import pandas as pd

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
LOGGER = logging.getLogger(__name__)

DEFAULT_SLEEP: float = 0.8
NBA_API_IMPORT_ERROR = (
    "The 'nba_api' package is required to run the download scripts. "
    "Install it with 'pip install nba_api'."
)
EXPECTED_META_COLUMNS = [
    "season",
    "season_type",
    "endpoint",
    "dataset",
    "game_id",
    "team_id",
    "player_id",
]


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def parse_seasons_arg(csv_str: str | None) -> List[str]:
    """Parse a comma-separated string of seasons into a list.

    Parameters
    ----------
    csv_str: str | None
        The CLI argument value. Values can be separated by commas. Empty values
        produce an empty list.

    Returns
    -------
    list[str]
        Normalised list of trimmed season strings.
    """

    if not csv_str:
        return []
    seasons = [season.strip() for season in csv_str.split(",")]
    return [season for season in seasons if season]


def ensure_dir(path: Path) -> None:
    """Ensure the directory for ``path`` exists."""

    directory = path if path.is_dir() else path.parent
    directory.mkdir(parents=True, exist_ok=True)


def repo_root() -> Path:
    """Locate the repository root by looking for a README.md file upwards."""

    current = Path(__file__).resolve().parent
    for ancestor in [current, *current.parents]:
        candidate = ancestor / "README.md"
        if candidate.exists():
            return ancestor
    return Path(__file__).resolve().parents[2]


def output_root() -> Path:
    """Return the root directory for raw outputs."""

    return repo_root() / "data" / "01_raw"


def with_retries(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_sleep: float = DEFAULT_SLEEP,
    logger: logging.Logger | None = None,
    **kwargs: Any,
) -> Any:
    """Execute ``func`` with retries and exponential backoff."""

    attempts = max(1, max_retries)
    log = logger or LOGGER
    for attempt in range(1, attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - best-effort logging
            if attempt == attempts:
                log.error("Function %s failed after %s attempts", func.__name__, attempt)
                raise
            sleep_for = base_sleep * (2 ** (attempt - 1))
            log.warning(
                "Attempt %s/%s for %s failed: %s. Sleeping %.2fs",
                attempt,
                attempts,
                func.__name__,
                exc,
                sleep_for,
            )
            time.sleep(sleep_for)
    raise RuntimeError("with_retries exhausted without returning")


def _import_module(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:  # pragma: no cover - guidance for missing deps
        raise ModuleNotFoundError(f"{NBA_API_IMPORT_ERROR} (missing module '{module_name}')") from exc


def ensure_nba_api() -> None:
    """Ensure ``nba_api`` and its stats endpoints are importable."""

    _import_module("nba_api.stats.endpoints")


def _enrich_with_meta(df: pd.DataFrame, meta: dict[str, Any]) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    enriched = df.copy()
    for column in EXPECTED_META_COLUMNS:
        if column in meta and column not in enriched.columns:
            enriched[column] = meta[column]
    return enriched


def _serialise_meta(meta: dict[str, Any]) -> dict[str, Any]:
    serialisable: dict[str, Any] = {}
    for key, value in meta.items():
        if isinstance(value, (str, int, float, bool, type(None))):
            serialisable[key] = value
        else:
            try:
                serialisable[key] = json.loads(json.dumps(value))
            except Exception:  # pragma: no cover - fall back to repr
                serialisable[key] = repr(value)
    return serialisable


def save_parquet(df: pd.DataFrame, path: Path, **meta: Any) -> dict[str, Any]:
    """Persist a dataframe to parquet with basic metadata handling."""

    existed = path.exists()
    if existed:
        LOGGER.info("Skip save (exists): %s", path)
        return {"path": str(path), "rows": int(df.shape[0]), "existed": True, "empty": df.empty}

    ensure_dir(path)
    enriched = _enrich_with_meta(df, meta)
    rows = int(enriched.shape[0])
    empty = enriched.empty
    enriched.to_parquet(path, index=False)

    meta_path = path.with_suffix(path.suffix + ".meta.json")
    try:
        meta_payload = _serialise_meta({"rows": rows, "empty": empty, **meta})
        meta_path.write_text(json.dumps(meta_payload, indent=2, ensure_ascii=False))
    except Exception as exc:  # pragma: no cover - metadata persistence best effort
        LOGGER.warning("Unable to write metadata for %s: %s", path, exc)

    LOGGER.info("Saved %s rows to %s", rows, path)
    return {"path": str(path), "rows": rows, "existed": False, "empty": empty}


# ---------------------------------------------------------------------------
# NBA specific helpers
# ---------------------------------------------------------------------------
def list_team_ids() -> List[int]:
    """Return active team IDs from the static endpoint."""

    teams_module = _import_module("nba_api.stats.static.teams")
    team_info = teams_module.get_teams()
    team_ids = sorted({team["id"] for team in team_info if "id" in team})
    return team_ids


def list_player_ids(active_only: bool = True) -> List[int]:
    """Return player IDs from the static endpoint."""

    players_module = _import_module("nba_api.stats.static.players")
    player_info = players_module.get_players(active_only=active_only)
    player_ids = sorted({player["id"] for player in player_info if "id" in player})
    return player_ids


def season_types(include_playoffs: bool) -> List[str]:
    """Return the season types to iterate for a given flag."""

    base = ["Regular Season"]
    return base + (["Playoffs"] if include_playoffs else [])


_ENDPOINT_CLASS_CACHE: dict[str, type] = {}


def _resolve_endpoint_class(class_name: str) -> type:
    if class_name in _ENDPOINT_CLASS_CACHE:
        return _ENDPOINT_CLASS_CACHE[class_name]

    endpoints_pkg = _import_module("nba_api.stats.endpoints")
    if hasattr(endpoints_pkg, class_name):
        endpoint_cls = getattr(endpoints_pkg, class_name)
        _ENDPOINT_CLASS_CACHE[class_name] = endpoint_cls
        return endpoint_cls

    for module_info in pkgutil.iter_modules(endpoints_pkg.__path__):  # type: ignore[arg-type]
        module = importlib.import_module(f"{endpoints_pkg.__name__}.{module_info.name}")
        if hasattr(module, class_name):
            endpoint_cls = getattr(module, class_name)
            _ENDPOINT_CLASS_CACHE[class_name] = endpoint_cls
            return endpoint_cls

    raise ImportError(f"Endpoint class {class_name} not found in nba_api.stats.endpoints")


def _call_endpoint(class_name: str, **params: Any):
    endpoint_cls = _resolve_endpoint_class(class_name)
    return endpoint_cls(**params)


def fetch_endpoint_to_df(class_name: str, **params: Any) -> pd.DataFrame:
    """Fetch data from an ``nba_api`` endpoint and return a dataframe."""

    endpoint = _call_endpoint(class_name, **params)
    frames = endpoint.get_data_frames() or []
    datasets = getattr(endpoint, "data_sets", [])

    labelled_frames: list[pd.DataFrame] = []
    if frames and datasets:
        for frame, dataset in zip(frames, datasets):
            df = frame.copy()
            name = getattr(dataset, "data_set", getattr(dataset, "name", "")) or dataset.__class__.__name__
            df["dataset"] = df.get("dataset", name)
            labelled_frames.append(df)
    else:
        labelled_frames = [frame.copy() for frame in frames]

    if not labelled_frames:
        return pd.DataFrame()

    combined = pd.concat(labelled_frames, ignore_index=True)
    return combined


def list_game_ids(season: str, include_playoffs: bool = False) -> List[str]:
    """Return unique GAME_ID values for the requested season."""

    game_ids: list[str] = []
    for season_type in season_types(include_playoffs):
        params = {"Season": season, "SeasonType": season_type}
        df = fetch_endpoint_to_df("LeagueGameLog", **params)
        if "GAME_ID" in df.columns:
            game_ids.extend(df["GAME_ID"].astype(str).tolist())
        time.sleep(DEFAULT_SLEEP)
    return sorted({gid for gid in game_ids if gid})


__all__ = [
    "DEFAULT_SLEEP",
    "ensure_nba_api",
    "parse_seasons_arg",
    "ensure_dir",
    "repo_root",
    "output_root",
    "with_retries",
    "save_parquet",
    "list_team_ids",
    "list_player_ids",
    "list_game_ids",
    "season_types",
    "fetch_endpoint_to_df",
]
