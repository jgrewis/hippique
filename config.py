"""Central configuration: paths, data sources and collection settings."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("HIPPIQUE_DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "turf.db"
MODEL_PATH = DATA_DIR / "model.json"
BACKTEST_PATH = DATA_DIR / "backtest.json"
OUTPUT_DIR = Path(os.environ.get("HIPPIQUE_OUTPUT_DIR", ROOT / "output"))
SCHEMA_PATH = ROOT / "db" / "schema.sql"

# Two independent hosts serving the same PMU JSON API, tried in this order.
PMU_HOSTS = (
    "https://offline.turfinfo.api.pmu.fr/rest/client/7",
    "https://online.turfinfo.api.pmu.fr/rest/client/61",
)
# Fallback HTML source (results only).
TURFFR_RESULTS_INDEX = "https://www.turf-fr.com/arrivees-rapports-pmu"

USER_AGENT = "Mozilla/5.0 (compatible; hippique-perso/1.0; usage personnel)"
REQUEST_DELAY_S = float(os.environ.get("PMU_DELAY", "1.0"))
REQUEST_TIMEOUT_S = 20
MAX_RETRIES = 3

# Only French meetings are collected.
COUNTRIES = {"FRA"}

TIMEZONE = "Europe/Paris"
SITE_TITLE = "Hippique"
# Absolute base path of the published site (GitHub project pages: "/<repo>/").
# Only the 404 page needs it: every other link is relative.
SITE_BASE_PATH = os.environ.get("SITE_BASE_PATH", "/").rstrip("/") + "/"
