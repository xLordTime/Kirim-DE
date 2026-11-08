"""Wizard101-Symbole und ihre Zuordnung zu Discord-App-Emojis."""
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path

import aiohttp
import discord
from loguru import logger


EMOJI_MAP_FILE = "emojis.json"
APP_EMOJI_NAMES: dict[int, str] = {}
_active_emojis: dict[int, discord.PartialEmoji] = {}


def source_url(source_id: int) -> str:
    return f"https://cdn.discordapp.com/emojis/{source_id}.webp?size=128"


@dataclass(frozen=True, slots=True)
class GameEmoji:
    source_id: int
    label: str

    def __str__(self) -> str:
        emoji = _active_emojis.get(self.source_id)
        return str(emoji) if emoji else f"[{self.label}]"

    @property
    def url(self) -> str:
        emoji = _active_emojis.get(self.source_id)
        # Discord kann das Originalbild in einem Embed auch als CDN-URL laden.
        return emoji.url if emoji else source_url(self.source_id)


def _register(name: str, source_id: int, label: str) -> GameEmoji:
    # Mehrere Spielsymbole mit derselben Quell-ID teilen sich einen Upload.
    APP_EMOJI_NAMES.setdefault(source_id, f"kirim_{name}")
    return GameEmoji(source_id, label)


def read_emoji_map(path: Path, application_id: int | None) -> dict[int, discord.PartialEmoji]:
    if application_id is None:
        return {}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        logger.warning("Emoji-Zuordnung konnte nicht gelesen werden: {}", error)
        return {}

    if not isinstance(state, dict) or not isinstance(state.get("emojis"), dict):
        logger.warning("Ungültiges Format für die Emoji-Zuordnung in {}", path)
        return {}
    if state.get("application_id") != str(application_id):
        logger.warning("Die Emoji-Zuordnung in {} gehört zu einer anderen Discord-App.", path)
        return {}

    entries = {}
    for source_id in APP_EMOJI_NAMES:
        value = state["emojis"].get(str(source_id))
        if isinstance(value, str):
            emoji = discord.PartialEmoji.from_str(value)
            if emoji.id is not None:
                entries[source_id] = emoji
    return entries


async def activate_emoji_map(client: discord.Client, path: Path) -> int:
    global _active_emojis
    saved = read_emoji_map(path, client.application_id)
    if saved:
        try:
            async with asyncio.timeout(5):
                current = await client.fetch_application_emojis()
        except (discord.DiscordException, aiohttp.ClientError, OSError, TimeoutError):
            logger.warning("App-Emojis konnten nicht abgeglichen werden. Gespeicherte IDs werden verwendet.")
        else:
            by_id = {emoji.id: emoji for emoji in current}
            saved = {
                source_id: discord.PartialEmoji.from_str(str(by_id[emoji.id]))
                for source_id, emoji in saved.items()
                if emoji.id in by_id
            }
    _active_emojis = saved
    return len(saved)


UNIVERSAL = _register("universal", 1111511060839669820, "Alle Schulen")
FIRE = _register("fire", 1111509221054361700, "Feuer")
ICE = _register("ice", 1111509224506265761, "Eis")
STORM = _register("storm", 1111509228541190214, "Sturm")
DEATH = _register("death", 1111509223591915560, "Tod")
LIFE = _register("life", 1111509357679628298, "Leben")
MYTH = _register("myth", 1111509222480416849, "Mythos")
BALANCE = _register("balance", 1111509219968045166, "Balance")
SUN = _register("sun", 1111509218898481184, "Sonne")
STAR = _register("star", 1111509217921220629, "Stern")
MOON = _register("moon", 1111509325744189553, "Mond")
GARDENING = _register("gardening", 1110954212566761604, "Gartenarbeit")
SHADOW = _register("shadow", 1111509216432242748, "Schatten")
FISHING = _register("fishing", 1110954210557694154, "Angeln")
CANTRIPS = _register("cantrips", 1099490127983673434, "Zaubertricks")
CASTLEMAGIC = _register("castlemagic", 1110953210694353028, "Schlossmagie")
WHIRLYBURLY = _register("whirlyburly", 1099498462711648416, "WhirlyBurly")
WEAVING_CASTER = _register("weaving_caster", 1435134801270280192, "Webschule des Zaubernden")
WEAVING_TARGET = _register("weaving_target", 1435136856885825606, "Webschule des Ziels")

HEART = _register("heart", 1099490441268834365, "Heilung")
HEALTH = _register("health", 1099490340685226166, "Lebenspunkte")
MANA = _register("mana", 1099494269959557240, "Mana")
ENERGY = _register("energy", 1099494247381598279, "Energie")
DAMAGE = _register("damage", 1099490157587075075, "Schaden")
FLAT_DAMAGE = _register("flat_damage", 1099504205175206009, "Fester Schaden")
RESIST = _register("resist", 1099490284083101706, "Resistenz")
FLAT_RESIST = _register("flat_resist", 1099504248179404911, "Feste Resistenz")
ACCURACY = _register("accuracy", 1099490418661531678, "Genauigkeit")
CRIT = _register("crit", 1099490127983673434, "Kritisch")
BLOCK = _register("block", 1099490076670570526, "Block")
PIERCE = _register("pierce", 1099490253686980622, "Durchdringung")
INCOMING = _register("incoming", 1099494559907581982, "Erhalten")
OUTGOING = _register("outgoing", 1099490223680913591, "Ausgehend")
STUN_BLOCK = _register("stun_block", 1099499321528942622, "Betäubungsschutz")
PIP_CONVERSION = _register("pip_conversion", 1099498554277507073, "Pip-Umwandlung")
ARCHMASTERY = _register("archmastery", 1099498588008095845, "Erzmeisterschaft")
SPEED = _register("speed", 1099499155640029284, "Tempo")

HEALTH_WISP = _register("health_wisp", 1057796529286549524, "Lebensgeist")
MANA_WISP = _register("mana_wisp", 1057796530855227503, "Manageist")
FISHING_LUCK = _register("fishing_luck", 1099505488086962197, "Angelglück")

PIP = _register("pip", 1099498720686526596, "Pip")
POWER_PIP = _register("power_pip", 1099490366832525422, "Power-Pip")
SHADOW_PIP = _register("shadow_pip", 1099490394884014090, "Schatten-Pip")
SHADOW_PIP_STAT = _register("shadow_pip_stat", 1111511532472385599, "Schatten-Pip")

HAT = _register("hat", 1056720350890696794, "Hut")
ROBE = _register("robe", 1056724593244635156, "Robe")
BOOTS = _register("boots", 1056720259240972308, "Stiefel")
WAND = _register("wand", 1056726250829389844, "Zauberstab")
ATHAME = _register("athame", 1056720255315099649, "Athame")
AMULET = _register("amulet", 1056720253213749259, "Amulett")
RING = _register("ring", 1056722653311938580, "Ring")
DECK = _register("deck", 1056720307433521172, "Deck")
MOUNT = _register("mount", 1056721062102048878, "Reittier")
JEWEL = _register("jewel", 1058115414888026254, "Juwel")

SOCKET_LOCKED = _register("socket_locked", 1099498847882981386, "Gesperrt")
SOCKET_TEAR = _register("socket_tear", 1099505202173837372, "Tränensockel")
SOCKET_CIRCLE = _register("socket_circle", 1099498888047644703, "Kreissockel")
SOCKET_SQUARE = _register("socket_square", 1099505313616502856, "Quadratsockel")
SOCKET_TRIANGLE = _register("socket_triangle", 1099505231055818823, "Dreieckssockel")
SOCKET_STAR = _register("socket_star", 1435739641402753106, "Sternsockel")

PIN_POWER = _register("pin_power", 1099490465117642823, "Kraft-Pin")
PIN_SHIELD = _register("pin_shield", 1099504900452405268, "Schild-Pin")
PIN_SWORD = _register("pin_sword", 1099490500651794442, "Schwert-Pin")

NO_AUCTION = _register("no_auction", 1103072061997469806, "Keine Auktion")
CROWNS_ONLY = _register("crowns_only", 1103073196795772988, "Nur Kronen")
NO_COMBAT = _register("no_combat", 1103072126115782656, "Kein Kampf")
NO_DROPS = _register("no_drops", 1103077911067643974, "Kein Beutefund")
NO_DYE = _register("no_dye", 1103072157904424971, "Nicht färbbar")
NO_HATCHMAKING = _register("no_hatchmaking", 1103072185611984896, "Keine Zuchtbörse")
NO_PVP = _register("no_pvp", 1103072213525082243, "Kein PvP")
NO_SELL = _register("no_sell", 1103073274474287174, "Nicht verkäuflich")
NO_SHATTER = _register("no_shatter", 1103073305843478599, "Nicht zerstörbar")
NO_TRADE = _register("no_trade", 1103074240741244928, "Nicht handelbar")
PVP_ONLY = _register("pvp_only", 1103076334130958406, "Nur PvP")
ARENA_POINTS_ONLY = _register("arena_points_only", 1103076387478306826, "Nur Arenapunkte")
BLUE_ARENA_POINTS_ONLY = _register("blue_arena_points_only", 1103076471750279229, "Nur blaue Arenapunkte")
LEVEL_RESTRICTION = _register("level_restriction", 1250964062758764614, "Mindeststufe")

NONE = _register("none", 1107114212142100480, "Kein Effekt")
CHARM = _register("charm", 1107749929880911953, "Zauberzeichen")
WARD = _register("ward", 1107116033279524946, "Schutzzeichen")
AURA = _register("aura", 1107114218714583050, "Aura")
GLOBAL = _register("global", 1099498462711648416, "Global")
AOE = _register("aoe", 1107752173271531601, "Flächeneffekt")
STEAL = _register("steal", 1107116039034122281, "Diebstahl")
MANIPULATION = _register("manipulation", 1107113759757049956, "Manipulation")
ENCHANTMENT = _register("enchantment", 1107114210862829578, "Verzauberung")
AURA_NEGATIVE = _register("aura_negative", 1107114217632440491, "Aura (negativ)")
BLADE = _register("blade", 1107114216420294696, "Klinge")
CURSE = _register("curse", 1107114214738382848, "Fluch")
DOT = _register("dot", 1107113767868842094, "Schaden pro Runde")
BOMB = _register("bomb", 1107113765511626863, "Verzögerter Schaden")
HOT = _register("hot", 1107113760927252501, "Heilung pro Runde")
JINX = _register("jinx", 1107114209390637126, "Verhexung")
MUTATE = _register("mutate", 1107113757693448202, "Mutation")
PABSORB = _register("pabsorb", 1107113758289047615, "Geschützte Absorption")
PBLADE = _register("pblade", 1107113756397420556, "Geschützte Klinge")
PCHARM = _register("pcharm", 1107113755428524064, "Geschütztes Zauberzeichen")
PCURSE = _register("pcurse", 1107113754883280956, "Geschützter Fluch")
PDOT = _register("pdot", 1107113753541099561, "Geschützter Rundenschaden")
PBOMB = _register("pbomb", 1107116043316506644, "Geschützter verzögerter Schaden")
PHOT = _register("phot", 1107116041928200294, "Geschützte Rundenheilung")
PJINX = _register("pjinx", 1107116040606982279, "Geschützte Verhexung")
POLYMORPH = _register("polymorph", 1107118045744332812, "Verwandlung")
PTRAP = _register("ptrap", 1107116039994617887, "Geschützte Falle")
PWARD = _register("pward", 1107133878575059044, "Geschütztes Schutzzeichen")
RANDOM = _register("random", 1107133876603715644, "Zufällig")
TRAP = _register("trap", 1107116031417266187, "Falle")
THREAT = _register("threat", 1107113771173949460, "Bedrohung")
STUN = _register("stun", 1107114221021450250, "Betäubung")
DISPEL = _register("dispel", 1107114277665525852, "Zaubersperre")
MINION = _register("minion", 1107114223496081518, "Handlanger")
ROUNDS = _register("rounds", 1107133797109075988, "Runden")
SPIRIT = _register("spirit", 1107113774378405901, "Geist")
ELEMENTAL = _register("elemental", 1107111620800426024, "Elementar")
ALL_ENEMIES = _register("all_enemies", 1107111669961855018, "Alle Gegner")
ALL_FRIENDS = _register("all_friends", 1107111568463908905, "Alle Verbündeten")
ALL_ENEMIES_SQUARE = _register("all_enemies_square", 1107749884880228472, "Gegnergruppe")
ALL_FRIENDS_SQUARE = _register("all_friends_square", 1107749883101839390, "Verbündetengruppe")
ALL_ENEMIES_SELECT = _register("all_enemies_select", 1222021754986430504, "Gegnerauswahl")
ALL_FRIENDS_SELECT = _register("all_friends_select", 1222021790184898621, "Verbündetenauswahl")
AFTERLIFE = _register("afterlife", 1107111534506823840, "Nachwirkung")
ABSORB = _register("absorb", 1107111476730286141, "Absorption")
DAMAGE_OR_DRAIN = _register("damage_or_drain", 1107111451342147645, "Schaden oder Entzug")
SELF = _register("self", 1107111430278357093, "Selbst")
CLOAK = _register("cloak", 1107111407138394113, "Tarnung")
CHROMATIC_CASTER = _register("chromatic_caster", 1222566258705432596, "Schule des Zaubernden")
CHROMATIC_TARGET = _register("chromatic_target", 1222566223431077968, "Schule des Ziels")
SHIELD = _register("shield", 1222565837978730538, "Schild")
WEAKNESS = _register("weakness", 1222565866806186038, "Schwäche")

GROWING = _register("growing", 1110956271928086709, "Wachstum")
PEST = _register("pest", 1110956273014427778, "Schädlinge")
SOIL = _register("soil", 1110956263740821614, "Erde")
G_UTILITY = _register("g_utility", 1110956270804021358, "Gartenhilfe")
PROTECTION = _register("protection", 1110958909918806076, "Schutz")

CATCHING = _register("catching", 1110956269851922572, "Fang")
FS_UTILITY = _register("fs_utility", 1110956265951199293, "Angelhilfe")

INCANTATION = _register("incantation", 1110957277042725047, "Beschwörung")
BENEFICIAL = _register("beneficial", 1110956268434247780, "Unterstützung")
SIGIL = _register("sigil", 1110957279940984872, "Siegel")
TELEPORTATION = _register("teleportation", 1110957278540070983, "Teleportation")
RITUAL = _register("ritual", 1110956267134013543, "Ritual")

SHADOW_SELF = _register("shadow_self", 1429994134713925672, "Schattenform")
SHADOW_CREATURE = _register("shadow_creature", 1429994132117393591, "Schattenwesen")
SHADOW_MINION = _register("shadow_minion", 1429994133358907513, "Schattenhandlanger")

FIRE_PIP = _register("fire_pip", 1434355875132211210, "Feuer-Pip")
ICE_PIP = _register("ice_pip", 1434355880723222569, "Eis-Pip")
STORM_PIP = _register("storm_pip", 1434355876491300964, "Sturm-Pip")
DEATH_PIP = _register("death_pip", 1434355881641771149, "Todes-Pip")
LIFE_PIP = _register("life_pip", 1434355879825637456, "Lebens-Pip")
MYTH_PIP = _register("myth_pip", 1434355878642847774, "Mythos-Pip")
BALANCE_PIP = _register("balance_pip", 1434355882409459712, "Balance-Pip")
