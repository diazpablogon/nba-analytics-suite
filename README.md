# BasketballAnalysis

Proyecto de análisis y predicción NBA que organiza todo el ciclo de vida de datos, características y modelos para generar métricas accionables sobre equipos y jugadores.

## 🔄 Flujo de datos
1. `data/01_raw` ➝ descarga de fuentes originales.
2. `data/02_cleaned` ➝ limpieza de tipos, nulos y formatos.
3. `data/03_merged` ➝ unión de tablas homogéneas.
4. `data/04_features` ➝ ingeniería de características temáticas.
5. `data/05_datasets` ➝ conjuntos finales de entrenamiento/validación/test.
6. `data/06_models` ➝ artefactos serializados y métricas.
7. `data/07_predictions` ➝ inferencias listas para consumo.

## 📂 Resumen de carpetas
| Ruta | Emoji | Descripción | Contenido clave |
| --- | --- | --- | --- |
| `data/01_raw` | 📂 | Datos originales descargados sin modificar. | Archivos fuente y bitácoras de ingesta.
| `data/02_cleaned` | 📂 | Datasets tras limpieza y tipado consistente. | Tablas normalizadas listas para merge.
| `data/03_merged` | 📂 | Integración de fuentes (equipos, jugadores, calendario). | Tablas maestras por temporada/partido.
| `data/04_features` | 📂 | Características derivadas por tema (baseline, venue, elo, lineup, etc.). | Tablas con variables listas para dataset final.
| `data/05_datasets` | 📂 | Conjuntos listos para modelado. | Splits train/valid/test y metadata asociada.
| `data/06_models` | 📂 | Artefactos producidos tras entrenamiento. | Pesos, métricas, reportes.
| `data/07_predictions` | 📂 | Resultados de inferencia. | Predicciones finales y reportes de entrega.
| `scripts/01_download_data` | ⚙️ | Automatiza la descarga de fuentes NBA. | Orquestadores y utilidades de descarga.
| `scripts/02_clean_stage` | ⚙️ | Limpieza de tipos y valores faltantes. | `clean_types_nulls.py`.
| `scripts/03_merge_data` | ⚙️ | Cruce y consolidación de fuentes. | `merge_sources.py`.
| `scripts/04_build_features` | ⚙️ | Generación de distintos sets de features. | `build_baseline.py`, `build_venue.py`, `build_enhanced.py`, `build_elo.py`, `build_lineup.py`.
| `scripts/05_make_datasets` | ⚙️ | Construcción de datasets finales. | `make_datasets.py`.
| `scripts/06_utils` | ⚙️ | Utilidades de control de calidad. | `check_leakage.py`, `summarize_tables.py`.
| `models/01_team_wl` | 📈 | Modelos de clasificación victoria/derrota. | Scripts `01_train.py`, `02_evaluate.py`, `03_infer.py`, `config.yaml`, `artifacts/`, `notes.md`.
| `models/02_team_pts` | 📈 | Modelos de puntos anotados por equipo. | Scripts `01_train.py`, `02_evaluate.py`, `03_infer.py`, `artifacts/`.
| `models/03_team_diff` | 📈 | Modelos de diferencial de puntuación. | Scripts `01_train.py`, `02_evaluate.py`, `03_infer.py`, `artifacts/`.
| `models/04_player_stats` | 📈 | Proyecciones de estadísticas individuales. | Scripts `01_train.py`, `02_evaluate.py`, `03_infer.py`, `config.yaml`, `artifacts/`, `notes.md`.

## ⚙️ Orden de ejecución de scripts
1. `python scripts/01_download_data/01a_downloader_total.py`
2. `python scripts/02_clean_stage/clean_types_nulls.py`
3. `python scripts/03_merge_data/merge_sources.py`
4. `python scripts/04_build_features/build_baseline.py`
5. (Opcionales según necesidad) `build_venue.py`, `build_enhanced.py`, `build_elo.py`, `build_lineup.py`
6. `python scripts/05_make_datasets/make_datasets.py`
7. Ejecutar los scripts de `models/*` según el objetivo (ver abajo).

## 01 – Descarga de datos (scripts/01_download_data/)
La carpeta `scripts/01_download_data/` centraliza los procesos para descargar datos crudos desde la NBA, incorporando utilidades compartidas, orquestación y scripts especializados por endpoint.

### Scripts disponibles
| Script | Descripción | Salida principal | Estado |
| --- | --- | --- | --- |
| `01a_downloader_total.py` | Orquestador que ejecuta el resto de scripts en serie con parámetros homogéneos. | Varias rutas bajo `data/01_raw/` según cada tarea. | Activo (habilita tareas vía `enabled`). |
| `01b_function_tools.py` | Utilidades comunes: paths, reintentos, guardado parquet y funciones auxiliares de nba_api. | N/A | Compartido. |
| `01c_get_league_team_stats.py` | Descarga agregados de equipos vía `LeagueDashTeamStats`. | `data/01_raw/league_dash_team_stats/<season>/<season_type>/` | Activo. |
| `01d_get_player_gamelogs.py` | Recolecta `PlayerGameLogs` por temporada y tipo de temporada. | `data/01_raw/player_gamelogs/<season>/<season_type>/` | Activo. |
| `01e_get_player_dashboard_splits.py` | Obtiene splits de jugadores (`PlayerDashboardByGameSplits`) por dataset. | `data/01_raw/player_dashboard_by_game_splits/<season>/<season_type>/<dataset>/` | Activo. |
| `01f_get_teamgamelogs_by_game.py` | Estructura para generar un parquet por juego desde `TeamGameLogs`. | `data/01_raw/teamgamelogs_by_game/<season>/` | Placeholder (TODO). |
| `01g_get_team_dashboards.py` | Plantilla para dashboards de equipo (ej. `TeamDashboardByGeneralSplits`). | `data/01_raw/team_dashboard/<slug>/` | Placeholder (TODO). |
| `01h_get_boxscores.py` | Bosquejo para descargar endpoints de boxscore por juego. | `data/01_raw/boxscore/<slug>/` | Placeholder (TODO). |

### Ejemplos de uso
```bash
python scripts/01_download_data/01a_downloader_total.py
python scripts/01_download_data/01c_get_league_team_stats.py --seasons "2024-25" --measure-type Advanced --per-mode PerGame
python scripts/01_download_data/01d_get_player_gamelogs.py --seasons "2024-25"
python scripts/01_download_data/01e_get_player_dashboard_splits.py --seasons "2024-25" --include-playoffs
```

### Mapa de salidas en `data/01_raw/`
- `league_dash_team_stats/<season>/<season_type>/league_dash_team_stats__<measure>__<per_mode>.parquet`
- `player_gamelogs/<season>/<season_type>/player_gamelogs__<season_type>.parquet`
- `player_dashboard_by_game_splits/<season>/<season_type>/<dataset>/player_dash_splits__<player_id>__<dataset>.parquet`
- `teamgamelogs_by_game/<season>/teamgamelogs_by_game__<GAME_ID>.parquet` *(planificado)*
- `team_dashboard/<slug>/<season>/<season_type>/<slug>__<TEAM_ID>__<dataset>.parquet` *(planificado)*
- `boxscore/<slug>/<season>/<slug>__<GAME_ID>.parquet` *(planificado)*

### Notas operativas
- Todos los scripts comparten la misma CLI base: `--seasons`, `--include-playoffs`, `--sleep`, `--max-retries` (más parámetros específicos según corresponda). Los reintentos implementan backoff exponencial y cada llamada respeta una espera mínima (`DEFAULT_SLEEP`).
- Ajusta las tareas activas del orquestador editando la lista `TASKS` en `01a_downloader_total.py` (campo `"enabled"`).
- Para evitar descargas repetidas, cada script omite archivos ya existentes en `data/01_raw/` y guarda metadatos junto a cada parquet.

## 🗂️ Resultados y almacenamiento
- 📂 `data/06_models`: guarda artefactos intermedios generados durante el entrenamiento (modelos serializados, métricas crudas).
- 📂 `data/07_predictions`: almacena predicciones finales listas para dashboards o APIs.
- 📈 `models/*/artifacts`: repositorio específico de cada modelo con pesos, curvas de aprendizaje y evaluaciones finales.

## 🧪 Ejecución de modelos
Para cada modelo sigue el patrón:
1. `python models/<modelo>/01_train.py`
2. `python models/<modelo>/02_evaluate.py`
3. `python models/<modelo>/03_infer.py`

Ejemplos:
- `models/01_team_wl`: predicción de victorias/derrotas.
- `models/02_team_pts`: proyección de puntos.
- `models/03_team_diff`: diferencial de marcador.
- `models/04_player_stats`: estadísticas individuales (usa `config.yaml` y `notes.md`).

## 🧭 Ejemplo de flujo completo
`01_download_data` ➝ `02_clean_stage` ➝ `03_merge_data` ➝ `04_build_features` ➝ `05_make_datasets` ➝ `models/01_team_wl/01_train.py` ➝ `models/01_team_wl/02_evaluate.py` ➝ `models/01_team_wl/03_infer.py`

Este flujo produce artefactos en `data/06_models` y predicciones en `data/07_predictions`, mientras que los detalles del modelo se documentan en `models/01_team_wl/`.
