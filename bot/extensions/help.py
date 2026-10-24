import discord
from discord import app_commands
from discord.ext import commands

from .. import TheBot

HELP_DESCRIPTION = """
**/zauber suchen · /zauber liste** – Zauber, Beschreibungen und Effekte.
**/gegenstand suchen · /gegenstand liste** – Ausrüstung und Werte.
**/gegner suchen · /gegner liste · /gegner deck** – Gegnerwerte und Karten.
**/gegner schaden** – Schaden gegen einen bestimmten Gegner berechnen.
**/begleiter suchen · /begleiter liste** – Begleiter, Talente und Karten.
**/fisch suchen · /fisch liste** – Fischwerte und Größen.
**/grenzwerte suchen** – Werteobergrenzen nach Schule und Stufe.
**/schaden** – Allgemeinen Schaden berechnen.
**/status** – Version, Datenstand und Übersetzungsabdeckung.

Deutsche und englische Namen werden unterstützt. Bei der Liste zeigt ein
Sternchen alle Einträge mit den gewählten Filtern. Fehlt ein deutscher Originaltext,
erscheint der englische Text. Objektnamen und IDs bleiben für die technische Suche erhalten.
"""


class Help(commands.Cog):
    def __init__(self, bot: TheBot):
        self.bot = bot

    @app_commands.command(name="hilfe", description="Zeigt alle Befehle von Kirim-DE")
    async def find(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=discord.Embed(
            title="Kirim-DE · Befehlsübersicht", color=discord.Color.dark_blue(),
            description=HELP_DESCRIPTION))

    @app_commands.command(name="status", description="Zeigt Version, Datenstand und Übersetzungsabdeckung")
    async def status(self, interaction: discord.Interaction):
        from pathlib import Path
        version = (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
        stats = self.bot.locale_stats
        embed = discord.Embed(title=f"Kirim-DE {version}", color=discord.Color.dark_blue())
        for entity, label in (("spell", "Zauber"), ("item", "Gegenstände"), ("mob", "Gegner"), ("pet", "Begleiter"), ("fish", "Fische")):
            embed.add_field(name=label, value=str(len(getattr(self.bot, f"{entity}_list"))))
        embed.add_field(name="Zuordnungen des Sprachpakets", value=f"{stats.get('translated', 0)} / {stats.get('total', 0)}")
        embed.set_footer(text="Namen aus der importierten Spieldatenbank; fehlende deutsche Texte mit englischem Fallback.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: TheBot):
    await bot.add_cog(Help(bot))
