from contextlib import redirect_stdout, redirect_stderr
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from PIL import Image

from bot import database, emojis
from bot.emoji_sync import download_png, sync_emojis, write_emoji_map


class AppEmojis(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / emojis.EMOJI_MAP_FILE
        self.client = SimpleNamespace(application_id=123456789012345678,
            fetch_application_emojis=AsyncMock(return_value=[]),
            create_application_emoji=AsyncMock())

    async def test_restart_uses_new_ids_in_stats_and_falls_back_for_deleted_emoji(self):
        fire = discord.PartialEmoji(name="kirim_fire", id=234567890123456789)
        damage = discord.PartialEmoji(name="kirim_damage", id=234567890123456790)
        write_emoji_map(self.path, self.client.application_id, {
            emojis.FIRE.source_id: fire, emojis.DAMAGE.source_id: damage,
        })
        self.client.fetch_application_emojis.return_value = [fire]
        with patch.object(emojis, "_active_emojis", {}):
            count = await emojis.activate_emoji_map(self.client, self.path)
            self.assertEqual(count, 1)
            self.assertEqual(str(database.translate_school(2)), str(fire))
            self.assertEqual(database.translate_school(2).url, fire.url)
            stat = database._fnv_1a(b"CanonicalFireDamage")
            self.assertEqual(database.translate_stat(stat)[1], f" {fire}[Schaden]")
            self.assertEqual(str(database.translate_type_emoji("PowerPips_image")), "[Power-Pip]")

    async def test_map_is_scoped_to_the_discord_app(self):
        fire = discord.PartialEmoji(name="kirim_fire", id=234567890123456789)
        write_emoji_map(self.path, self.client.application_id + 1, {emojis.FIRE.source_id: fire})
        with patch.object(emojis, "_active_emojis", {}):
            self.assertEqual(await emojis.activate_emoji_map(self.client, self.path), 0)
            self.assertEqual(str(emojis.FIRE), "[Feuer]")
        self.client.fetch_application_emojis.assert_not_awaited()

    def test_negative_aura_fallback_does_not_insert_positive_aura(self):
        from bot.extensions.spells import Spells

        positive = discord.PartialEmoji(name="kirim_aura", id=234567890123456789)
        with patch.object(emojis, "_active_emojis", {emojis.AURA.source_id: positive}):
            rendered = Spells(None).replace_condition_with_emojis("Target Negative Aura")
        self.assertEqual(rendered, "Target [Aura (negativ)]")

    async def test_interrupted_upload_is_reused_on_retry(self):
        fire_id = emojis.FIRE.source_id
        damage_id = emojis.DAMAGE.source_id
        catalog = {fire_id: "kirim_fire", damage_id: "kirim_damage"}
        remote = []
        self.client.fetch_application_emojis.side_effect = lambda: list(remote)

        async def upload(name, image):
            emoji = discord.PartialEmoji(name=name, id=234567890123456789 + len(remote))
            remote.append(emoji)
            if name == "kirim_damage":
                raise TimeoutError("The response was lost after the upload")
            return emoji

        self.client.create_application_emoji.side_effect = upload
        with patch.dict(emojis.APP_EMOJI_NAMES, catalog, clear=True), \
             patch("bot.emoji_sync.download_png", return_value=b"png") as download, \
             redirect_stdout(StringIO()):
            with self.assertRaises(TimeoutError):
                await sync_emojis(self.client, None, self.path)
            self.assertEqual(set(emojis.read_emoji_map(self.path, self.client.application_id)), {fire_id})
            await sync_emojis(self.client, None, self.path)
            self.assertEqual(set(emojis.read_emoji_map(self.path, self.client.application_id)), {fire_id, damage_id})
        self.assertEqual(download.await_count, 2)
        self.assertEqual(self.client.create_application_emoji.await_count, 2)

    async def test_unavailable_source_does_not_block_other_symbols(self):
        fire_id = emojis.FIRE.source_id
        damage_id = emojis.DAMAGE.source_id
        catalog = {fire_id: "kirim_fire", damage_id: "kirim_damage"}
        damage = discord.PartialEmoji(name="kirim_damage", id=234567890123456790)
        self.client.create_application_emoji.return_value = damage
        with patch.dict(emojis.APP_EMOJI_NAMES, catalog, clear=True), \
             patch("bot.emoji_sync.download_png", side_effect=[OSError("Feuer fehlt"), b"png"]), \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            with self.assertRaisesRegex(RuntimeError, "Einige Symbole fehlen"):
                await sync_emojis(self.client, None, self.path)
            mapping = emojis.read_emoji_map(self.path, self.client.application_id)
            self.assertEqual(mapping, {damage_id: damage})

    async def test_download_converts_webp_to_transparent_128px_png(self):
        data = BytesIO()
        Image.new("RGBA", (16, 8), (250, 80, 5, 160)).save(data, format="WEBP", lossless=True)
        response = MagicMock(read=AsyncMock(return_value=data.getvalue()))
        session = MagicMock()
        session.get.return_value.__aenter__.return_value = response
        png = await download_png(session, emojis.FIRE.source_id)
        with Image.open(BytesIO(png)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (128, 128))
            self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertEqual(image.getpixel((64, 64))[3], 160)
