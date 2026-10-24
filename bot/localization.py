"""Offizielle .lang-Schlüssel mit versionsgeprüftem englischem Fallback."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def language_hash(key: str) -> int:
    value = 0xCBF29CE484222325
    for byte in key.encode("utf-8"):
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value >> 1


def parse_lang(data: bytes) -> dict[str, str]:
    text = data.decode("utf-16") if data.startswith((b"\xff\xfe", b"\xfe\xff")) else data.decode("utf-8-sig")
    lines = text.splitlines()
    if not lines or ":" not in lines[0]:
        raise ValueError("Ungültige .lang-Kopfzeile")
    namespace = lines[0].split(":", 1)[1].strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", namespace):
        raise ValueError("Ungültiger .lang-Namensraum")
    lines = lines[1:]
    # Ein abschließender Zeilenumbruch gehört nicht zum letzten Datensatz.
    if len(lines) % 3:
        raise ValueError("Unvollständiger .lang-Datensatz")
    result = {}
    for offset in range(0, len(lines), 3):
        key, _comment, value = lines[offset:offset + 3]
        if key and value:
            result[f"{namespace}_{key}"] = value
    return result


def load_entries(custom_dir: Path | None = None) -> dict:
    entries = {}
    for directory in (ROOT / "locales" / "de", custom_dir):
        if directory and directory.is_dir():
            for path in sorted(directory.glob("*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                for key, pair in payload.get("entries", {}).items():
                    if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(s, str) for s in pair):
                        raise ValueError(f"Ungültiger Spracheintrag in {path.name}")
                    entries[key] = pair
    return entries


async def install_locale(db, custom_dir: Path | None = None) -> dict[str, int]:
    """Nur die RAM-Kopie ändern; die Quelldatenbank bleibt unverändert."""
    async with db.execute("SELECT id, data FROM main.locale_en") as cursor:
        original = dict(await cursor.fetchall())
    entries = load_entries(custom_dir)
    candidates = {}
    for english, german in entries.values():
        candidates.setdefault(english, set()).add(german)
        candidates.setdefault(german, set()).add(german)
    by_text = {en: next(iter(de)) for en, de in candidates.items() if len(de) == 1}
    translations = {key: by_text[text] for key, text in original.items() if text in by_text}
    matched_by_key = 0
    for key, (english, german) in entries.items():
        hashed = language_hash(key)
        # Numerische IDs können sich zwischen Spielständen verschieben.
        if original.get(hashed) in {english, german}:
            translations[hashed] = german
            matched_by_key += 1
    await db.execute("CREATE TEMP TABLE kirim_locale_de (id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
    await db.executemany("INSERT INTO kirim_locale_de VALUES (?, ?)", translations.items())
    await db.execute("""
        CREATE TEMP VIEW locale_en AS
        SELECT source.id, COALESCE(de.data, source.data) AS data
        FROM main.locale_en AS source
        LEFT JOIN kirim_locale_de AS de ON de.id = source.id
    """)
    return {"entries": len(entries), "translated": len(translations), "matched_by_key": matched_by_key, "total": len(original)}


def normalize_name(value: str) -> str:
    return value.casefold().strip()
