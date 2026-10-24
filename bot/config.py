"""Konfiguration ohne Geheimnisse im Repository."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def ensure_env(root: Path = ROOT) -> Path:
    target = root / ".env"
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return target
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write((root / ".env.example").read_text(encoding="utf-8"))
    return target


def root_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_config() -> dict:
    load_dotenv(ensure_env(), override=False)
    data_dir = root_path(os.getenv("KIRIM_DATA_DIR") or "data")
    data_dir.mkdir(parents=True, exist_ok=True)
    items = os.getenv("KIRIM_ITEMS_DB")
    decks = os.getenv("KIRIM_DECKS_DB")
    return {
        "items": root_path(items) if items else (
            ROOT / "items.db" if (ROOT / "items.db").is_file() else data_dir / "items.db"
        ),
        "decks": root_path(decks) if decks else (
            ROOT / "decks.db" if (ROOT / "decks.db").is_file() else data_dir / "decks.db"
        ),
        "data": data_dir,
        "locale": os.getenv("KIRIM_LOCALE", "de"),
    }
