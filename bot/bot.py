import os
import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
import discord
from discord.ext import commands
from loguru import logger

from .emojis import APP_EMOJI_NAMES, EMOJI_MAP_FILE, activate_emoji_map
from .localization import install_locale, normalize_name, load_entries
from .command_locale import GermanTranslator

EXTENSIONS = Path(__file__).parent / "extensions"
ENTITY_TABLES = {"item": "items", "spell": "spells", "mob": "mobs", "pet": "pets", "fish": "fish"}
REQUIRED_TABLES = {"locale_en", "items", "spells", "mobs", "pets", "fish", "effects", "spell_effects", "statcaps"}


class TheBot(commands.Bot):
    def __init__(self, db_path: Path, deck_db_path: Path, *, locale="de", data_dir=None, **kwargs):
        super().__init__(**kwargs)
        self.db_path = db_path
        self.deck_db_path = deck_db_path
        self.data_dir = data_dir or db_path.parent
        self.locale = locale
        self.db = None
        self.deck_db = None
        self.search_aliases = {}
        self.locale_stats = {}
        self._owns_ready_marker = False
        self.tree.error(self.on_app_command_error)
        self.uptime = datetime.now()
        for entity in ENTITY_TABLES:
            setattr(self, f"{entity}_list", [])
            setattr(self, f"{entity}_object_list", [])

    async def prepare_data(self):
        if self.db is not None:
            return
        if not self.db_path.is_file():
            raise RuntimeError(f"Spieldatenbank fehlt: {self.db_path}. Mit python3 server.py import-db PFAD importieren.")
        source = await aiosqlite.connect(self.db_path.resolve().as_uri() + "?mode=ro", uri=True)
        self.db = await aiosqlite.connect(":memory:")
        try:
            await source.backup(self.db)
        finally:
            await source.close()
        async with self.db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = {row[0] for row in await cursor.fetchall()}
        missing = REQUIRED_TABLES - tables
        if missing:
            raise RuntimeError("Die wizdb-Datenbank passt nicht. Fehlende Tabellen: " + ", ".join(sorted(missing)))
        if self.locale == "de":
            self.locale_stats = await install_locale(self.db, self.data_dir / "locales")
            logger.info("Deutsche Texte: {translated}/{total}", **self.locale_stats)
        locale_entries = load_entries(self.data_dir / "locales") if self.locale == "de" else {}
        for entity, table in ENTITY_TABLES.items():
            query = f"""SELECT localized.data, original.data, {table}.real_name
                FROM {table} JOIN locale_en AS localized ON localized.id = {table}.name
                JOIN main.locale_en AS original ON original.id = {table}.name"""
            async with self.db.execute(query) as cursor:
                rows = await cursor.fetchall()
            setattr(self, f"{entity}_list", sorted({row[0] for row in rows}))
            setattr(self, f"{entity}_object_list", [row[2].decode("utf-8") if isinstance(row[2], bytes) else row[2] for row in rows])
            self.search_aliases[entity] = {normalize_name(name): localized for localized, english, _ in rows for name in (english, localized)}
            for english, german in locale_entries.values():
                localized = self.search_aliases[entity].get(normalize_name(german))
                if localized:
                    self.search_aliases[entity].setdefault(normalize_name(english), localized)
        self.deck_db = await aiosqlite.connect(":memory:")
        if self.deck_db_path.is_file():
            source = await aiosqlite.connect(self.deck_db_path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                await source.backup(self.deck_db)
            finally:
                await source.close()
        else:
            await self.deck_db.execute("CREATE TABLE deck (id INTEGER PRIMARY KEY, name TEXT, spell TEXT, count INTEGER)")
            if "deck" in tables:
                async with self.db.execute("SELECT id, name, spell, count FROM deck") as cursor:
                    await self.deck_db.executemany("INSERT INTO deck VALUES (?, ?, ?, ?)", await cursor.fetchall())
            else:
                logger.warning("Keine Gegnerdecks vorhanden; /gegner deck liefert keine Treffer.")

    def resolve_search(self, entity, name):
        return self.search_aliases.get(entity, {}).get(normalize_name(name), name)

    def matching_names(self, entity, name):
        needle = normalize_name(name)
        if needle == "*":
            return getattr(self, f"{entity}_list")
        return sorted({localized for alias, localized in self.search_aliases.get(entity, {}).items() if needle in alias})

    async def load_extensions_from_dir(self, path=EXTENSIONS):
        for subpath in sorted(path.glob("[!_]*.py")):
            module = f"bot.extensions.{subpath.stem}"
            if module not in self.extensions:
                await self.load_extension(module)
        return len(self.extensions)

    async def setup_hook(self):
        await self.prepare_data()
        emoji_count = await activate_emoji_map(self, self.data_dir / EMOJI_MAP_FILE)
        logger.info("Kirim-DE App-Emojis: {}/{}. Fehlende Symbole erscheinen als Text.",
            emoji_count, len(APP_EMOJI_NAMES))
        await self.load_extensions_from_dir()
        await self.tree.set_translator(GermanTranslator())
        if os.getenv("KIRIM_SYNC_COMMANDS", "true").lower() in {"true", "1", "yes"}:
            guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
            else:
                synced = await self.tree.sync()
            logger.info("{} Befehle synchronisiert", len(synced))

    async def on_ready(self):
        logger.info("Kirim-DE angemeldet als {} mit {} Modulen", self.user, len(self.extensions))
        (self.data_dir / "ready.json").write_text(json.dumps({
            "pid": os.getpid(), "ready_utc": datetime.now(timezone.utc).isoformat()
        }))
        self._owns_ready_marker = True

    async def on_app_command_error(self, interaction, error):
        original = getattr(error, "original", error)
        logger.error("Befehlsfehler: {!r}", original)
        message = "Bei der Abfrage ist ein Fehler aufgetreten. Details stehen im Serverprotokoll."
        if isinstance(original, (ValueError, TypeError)):
            message = "Ungültige Eingabe. Bei der Suche nach ID bitte eine Zahl eingeben."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def close(self):
        try:
            await super().close()
        finally:
            if self._owns_ready_marker:
                (self.data_dir / "ready.json").unlink(missing_ok=True)
            for attr in ("db", "deck_db"):
                connection = getattr(self, attr)
                if connection is not None:
                    await connection.close()
                    setattr(self, attr, None)
