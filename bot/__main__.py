import argparse
import asyncio
import os
import sys

import discord
from discord.ext import commands
from loguru import logger

from .bot import TheBot
from .config import load_config


def make_bot(config):
    intents = discord.Intents.none()
    intents.guilds = True
    intents.emojis = True
    return TheBot(config["items"], config["decks"], locale=config["locale"], data_dir=config["data"],
        command_prefix=commands.when_mentioned, intents=intents,
        allowed_mentions=discord.AllowedMentions.none())


async def check(config, code_only=False):
    async with make_bot(config) as bot:
        if not code_only:
            await bot.prepare_data()
        count = await bot.load_extensions_from_dir()
        if not code_only:
            for table, builder in (("items", "build_item_embed"), ("spells", "build_spell_embed"),
                ("mobs", "build_mob_embed"), ("pets", "build_pet_embed"), ("fish", "build_fish_embed")):
                cog = next(cog for cog in bot.cogs.values() if hasattr(cog, builder))
                async with bot.db.execute(
                    f"SELECT * FROM {table} JOIN locale_en ON locale_en.id={table}.name LIMIT 3"
                ) as cursor:
                    rows = await cursor.fetchall()
                for row in rows:
                    result = await getattr(cog, builder)(row)
                    if isinstance(result, tuple) and result[1] is not None:
                        result[1].close()
        for command in bot.tree.get_commands():
            command.to_dict(bot.tree)
        print(f"OK: {count} Module, {len(bot.tree.get_commands())} Befehlsgruppen.")
        if bot.locale_stats:
            print(f"Deutsche Texte: {bot.locale_stats['translated']} von {bot.locale_stats['total']}.")


def main():
    parser = argparse.ArgumentParser(description="Kirim-DE – deutscher Wizard101-Bot")
    parser.add_argument("--check", action="store_true", help="Offline-Prüfung einschließlich Spieldatenbank")
    parser.add_argument("--code-only", action="store_true", help="Offline-Prüfung ohne Spieldatenbank")
    args = parser.parse_args()
    config = load_config()
    logger.remove()
    logger.add(sys.stderr, level=os.getenv("KIRIM_LOG_LEVEL", "INFO"))
    if args.check or args.code_only:
        asyncio.run(check(config, args.code_only))
        return
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise SystemExit("Bitte DISCORD_TOKEN in der automatisch erstellten .env eintragen.")
    make_bot(config).run(token, log_handler=None)


if __name__ == "__main__":
    main()
