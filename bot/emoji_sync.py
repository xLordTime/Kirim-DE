"""Einmaliger Import der Wizard101-Symbole in die eigene Discord-App."""
import asyncio
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

import aiohttp
import discord
from PIL import Image, ImageOps

from .config import load_config
from .emojis import APP_EMOJI_NAMES, EMOJI_MAP_FILE, read_emoji_map, source_url


async def download_png(session: aiohttp.ClientSession, source_id: int) -> bytes:
    for attempt in range(3):
        try:
            async with session.get(source_url(source_id)) as response:
                response.raise_for_status()
                source = await response.read()
            break
        except (aiohttp.ClientError, TimeoutError) as error:
            permanent = isinstance(error, aiohttp.ClientResponseError) and error.status < 500 and error.status != 429
            if permanent or attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)

    # discord.py akzeptiert PNG. Die Konvertierung erhält die Transparenz der WebP-Quelle.
    with Image.open(BytesIO(source)) as image:
        icon = ImageOps.pad(image.convert("RGBA"), (128, 128), method=Image.Resampling.LANCZOS)
        output = BytesIO()
        icon.save(output, format="PNG")
        return output.getvalue()


def write_emoji_map(path: Path, application_id: int, emojis: dict[int, discord.Emoji]) -> None:
    state = {
        "application_id": str(application_id),
        "emojis": {str(source_id): str(emoji) for source_id, emoji in emojis.items()},
    }
    file = NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".emojis-", delete=False)
    temporary = Path(file.name)
    try:
        with file:
            json.dump(state, file, indent=2)
            file.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


async def sync_emojis(client: discord.Client, session: aiohttp.ClientSession, path: Path) -> None:
    application_id = client.application_id
    if application_id is None:
        raise RuntimeError("Die Discord-App-ID konnte nicht ermittelt werden.")

    saved = read_emoji_map(path, application_id)
    existing = await client.fetch_application_emojis()
    by_id = {emoji.id: emoji for emoji in existing}
    by_name = {emoji.name: emoji for emoji in existing}
    mapping = {}
    for source_id, name in APP_EMOJI_NAMES.items():
        previous = saved.get(source_id)
        emoji = by_id.get(previous.id) if previous else None
        if emoji is None:
            emoji = by_name.get(name)
        if emoji is not None:
            mapping[source_id] = emoji

    reused = len(mapping)
    total = len(APP_EMOJI_NAMES)
    print(f"App-Emojis: {reused}/{total} vorhanden. Importiere fehlende Symbole …", flush=True)
    try:
        for source_id, name in APP_EMOJI_NAMES.items():
            if source_id in mapping:
                continue
            try:
                png = await download_png(session, source_id)
            except (aiohttp.ClientError, OSError, TimeoutError) as error:
                print(f"{name} konnte nicht geladen werden: {error}", file=sys.stderr, flush=True)
                continue
            try:
                mapping[source_id] = await client.create_application_emoji(name=name, image=png)
            except discord.DiscordException as error:
                raise RuntimeError(f"Discord-Upload für {name} fehlgeschlagen: {error}") from error
    finally:
        write_emoji_map(path, application_id, mapping)

    print(f"App-Emojis: {len(mapping)}/{total} bereit, davon {len(mapping) - reused} neu. Zuordnung: {path}", flush=True)
    if len(mapping) < total:
        raise RuntimeError("Einige Symbole fehlen. Mit python3 server.py emojis sync den Import fortsetzen.")


async def run_sync(token: str, path: Path) -> None:
    async with discord.Client(intents=discord.Intents.none()) as client:
        # Nur die HTTP-API anmelden. Der laufende Bot nutzt seine Gateway-Verbindung weiter.
        await client.login(token)
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            await sync_emojis(client, session, path)


def main() -> None:
    config = load_config()
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise SystemExit("Kirim-DE: Bitte DISCORD_TOKEN in .env eintragen.")
    try:
        asyncio.run(run_sync(token, config["data"] / EMOJI_MAP_FILE))
    except discord.LoginFailure:
        raise SystemExit("Kirim-DE: Discord hat DISCORD_TOKEN abgelehnt.") from None
    except (discord.DiscordException, aiohttp.ClientError, OSError, RuntimeError) as error:
        raise SystemExit(f"Kirim-DE: Emoji-Abgleich fehlgeschlagen. {error}") from None


if __name__ == "__main__":
    main()
