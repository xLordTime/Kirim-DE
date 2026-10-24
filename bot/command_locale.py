"""Deutsche Anzeigenamen; interne Filterwerte bleiben unverändert."""
import discord
from discord import app_commands

LABELS = {
    "name": "name", "school": "schule", "kind": "art", "level": "stufe",
    "rank": "rang", "search_by": "suche_nach", "show_spell_effects": "effekte_anzeigen",
    "num_targets": "ziele", "is_sentinel": "waechter", "use_object_name": "objektname",
    "wow": "wow_faktor", "exclusive": "exklusiv", "base": "grundschaden",
    "damage": "schaden", "pierce": "durchdringung", "critical": "kritisch",
    "resist": "resistenz", "block": "block", "buffs": "verstaerkungen",
    "pvp": "pvp", "Any": "Alle", "Fire": "Feuer", "Ice": "Eis",
    "Storm": "Sturm", "Myth": "Mythos", "Life": "Leben", "Death": "Tod",
    "Balance": "Balance", "Star": "Stern", "Sun": "Sonne", "Moon": "Mond",
    "Gardening": "Gärtnern", "Shadow": "Schatten", "Fishing": "Angeln",
    "Cantrips": "Zaubertricks", "Castlemagic": "Hausmagie", "WhirlyBurly": "Whirlyburly",
    "Hat": "Hut", "Robe": "Robe", "Shoes": "Schuhe", "Weapon": "Zauberstab",
    "Athame": "Athame", "Amulet": "Amulett", "Ring": "Ring", "Deck": "Deck",
    "Jewel": "Juwel", "Mount": "Reittier", "Healing": "Heilung", "Damage": "Schaden",
    "Charm": "Talisman", "Ward": "Schutz", "Aura": "Aura", "Global": "Global",
    "AOE": "Flächeneffekt", "Steal": "Entzug", "Manipulation": "Manipulation",
    "Enchantment": "Verzauberung", "Polymorph": "Verwandlung", "Curse": "Fluch",
    "Jinx": "Verwünschung", "Mutate": "Mutation", "Cloak": "Verschleierung",
    "Easy": "Leicht", "Normal": "Normal", "Elite": "Elite", "Boss": "Boss",
    "Name": "Name", "Object": "Objektname", "ID": "ID",
}


class GermanTranslator(app_commands.Translator):
    async def translate(self, string, locale, context):
        if locale == discord.Locale.german:
            return LABELS.get(string.message)
        return None
