"""Application configuration."""

from pathlib import Path
import os

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
DATA_DIR = PROJECT_ROOT / "data"
CLEANED_DATA_DIR = DATA_DIR / "cleaned"


def active_data_dir() -> Path:
    """Prefer validated, cleaned data when it has been generated."""
    return CLEANED_DATA_DIR if (CLEANED_DATA_DIR / "transactions.csv").is_file() else DATA_DIR


NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "money")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres@127.0.0.1:5432/postgres",
)
