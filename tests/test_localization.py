import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiosqlite
import discord
from discord import app_commands

from bot.__main__ import make_bot
from bot.command_locale import GermanTranslator
from bot.localization import language_hash, parse_lang, install_locale, load_entries


class LanguageFiles(unittest.TestCase):
    def test_utf16_comments_and_empty_values(self):
        data = "1:Spells\r\n00000001\r\nKommentar\r\nTestname DE\r\n00000002\r\n\r\n\r\n"
        self.assertEqual(parse_lang(data.encode("utf-16")), {"Spells_00000001": "Testname DE"})

    def test_rejects_truncated_record(self):
        with self.assertRaises(ValueError):
            parse_lang(b"1:Spells\nkey\ncomment")

    def test_compiler_preserves_parameter_templates(self):
        from tools.compile_locale import compile_pair
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            en, de, out = root / "en.lang", root / "de.lang", root / "result.json"
            en.write_bytes("1:Spell\r\nexample\r\n\r\nDamage $eA$\r\n".encode("utf-16"))
            de.write_bytes("1:Spell\r\nexample\r\n\r\nSchaden $eA$\r\n".encode("utf-16"))
            self.assertEqual(compile_pair(en, de, out), 1)
            self.assertEqual(json.loads(out.read_text())["entries"]["Spell_example"], ["Damage $eA$", "Schaden $eA$"])



class RuntimeLocale(unittest.IsolatedAsyncioTestCase):
    async def test_version_guard_and_unambiguous_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            custom = Path(directory)
            records = {
                "Test_correct": ["English A", "Deutsch A"],
                "Test_changed": ["Old B", "Deutsch B"],
                "Test_ambiguous1": ["Same C", "Deutsch C1"],
                "Test_ambiguous2": ["Same C", "Deutsch C2"],
            }
            (custom / "test.json").write_text(json.dumps({"entries": records}))
            async with aiosqlite.connect(":memory:") as db:
                await db.execute("CREATE TABLE locale_en (id INTEGER PRIMARY KEY, data TEXT)")
                await db.executemany("INSERT INTO locale_en VALUES (?, ?)", [
                    (language_hash("Test_correct"), "English A"),
                    (language_hash("Test_changed"), "Completely different"),
                    (123, "English A"), (124, "Same C"), (125, "Deutsch A")])
                await install_locale(db, custom)
                async with db.execute("SELECT id, data FROM locale_en") as cursor:
                    localized = dict(await cursor.fetchall())
                self.assertEqual(localized[language_hash("Test_correct")], "Deutsch A")
                self.assertEqual(localized[language_hash("Test_changed")], "Completely different")
                self.assertEqual(localized[123], "Deutsch A")
                self.assertEqual(localized[124], "Same C")
                async with db.execute("SELECT data FROM main.locale_en WHERE id=123") as cursor:
                    self.assertEqual((await cursor.fetchone())[0], "English A")

    async def test_german_choice_labels_keep_original_values(self):
        result = await GermanTranslator().translate(app_commands.locale_str("Fire"), discord.Locale.german, None)
        self.assertEqual(result, "Feuer")
        self.assertIsNone(await GermanTranslator().translate(app_commands.locale_str("Fire"), discord.Locale.american_english, None))

    async def test_bot_supports_already_german_database_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            source = data / "items.db"
            custom = data / "locales"
            custom.mkdir()
            (custom / "example.json").write_text(json.dumps({"entries": {"Spells_00000000": ["Testname EN", "Testname DE"]}}))
            with sqlite3.connect(source) as db:
                db.execute("CREATE TABLE locale_en (id INTEGER PRIMARY KEY, data TEXT)")
                db.execute("INSERT INTO locale_en VALUES (?, ?)", (language_hash("Spells_00000000"), "Testname DE"))
                for table in ("items", "spells", "mobs", "pets", "fish"):
                    db.execute(f"CREATE TABLE {table} (id INTEGER, name INTEGER, real_name BLOB)")
                    db.execute(f"INSERT INTO {table} VALUES (1, ?, ?)", (language_hash("Spells_00000000"), b"StormBeetle"))
                for table in ("effects", "spell_effects", "statcaps"):
                    db.execute(f"CREATE TABLE {table} (id INTEGER)")
                db.execute("CREATE TABLE deck (id INTEGER PRIMARY KEY, name TEXT, spell TEXT, count INTEGER)")
                db.execute("INSERT INTO deck VALUES (1, 'Mob', 'StormBeetle', 2)")
            original_hash = hashlib.sha256(source.read_bytes()).digest()
            config = {"items": source, "decks": data / "missing.db", "data": data, "locale": "de"}
            async with make_bot(config) as bot:
                await bot.prepare_data()
                self.assertEqual(bot.resolve_search("spell", "TESTNAME EN"), "Testname DE")
                self.assertEqual(bot.resolve_search("spell", "TESTNAME DE"), "Testname DE")
                self.assertEqual(bot.matching_names("spell", "testname en"), ["Testname DE"])
                async with bot.deck_db.execute("SELECT count FROM deck") as cursor:
                    self.assertEqual((await cursor.fetchone())[0], 2)
                await bot.load_extensions_from_dir()
                self.assertEqual({command.name for command in bot.tree.get_commands()},
                    {"schaden", "fisch", "hilfe", "status", "gegner", "begleiter", "zauber", "grenzwerte", "gegenstand"})
                await bot.tree.set_translator(GermanTranslator())
                for command in bot.tree.get_commands():
                    payload = await command.get_translated_payload(bot.tree, bot.tree.translator)
                    self.assertTrue(payload["name"])
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original_hash)

    async def test_missing_source_does_not_create_empty_db(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            config = {"items": data / "missing.db", "decks": data / "decks.db", "data": data, "locale": "de"}
            async with make_bot(config) as bot:
                with self.assertRaisesRegex(RuntimeError, "Spieldatenbank fehlt"):
                    await bot.prepare_data()
            self.assertFalse(config["items"].exists())

    async def test_empty_search_and_invalid_statcap_are_user_messages(self):
        from bot.extensions.spells import Spells
        from bot.extensions.statcaps import StatCaps
        fake_bot = SimpleNamespace(resolve_search=lambda _, text: text, spell_list=[])
        interaction = SimpleNamespace(response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()), user=SimpleNamespace(name="Tester"),
            channel=SimpleNamespace(name="Test"), guild=SimpleNamespace(name="Test"))
        cog = Spells(fake_bot)
        cog.fetch_spells_with_filter = AsyncMock(return_value=[])
        await cog.find.callback(cog, interaction, "nicht vorhanden")
        self.assertIn("Keine Treffer", interaction.followup.send.call_args.args[0])
        caps = StatCaps(fake_bot)
        caps.fetch_stat_cap = AsyncMock(return_value=[])
        await caps.find.callback(caps, interaction, 190, "Fire")
        self.assertIn("keine Werte", interaction.followup.send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
