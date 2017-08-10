"""This module contains classes which hold or map region and platform IDs."""
from discord import Colour
from .errors import InvalidRegion, InvalidPlatform

class Regions:
    """Region IDs and mappings."""
    AMERICA = 'ncsa'
    EUROPE = 'emea'
    ASIA = 'apac'

    @classmethod
    def get_name(cls, region_id: str):
        """Get a region's name by its ID."""
        region_names = {
            cls.ASIA: "Asia Pacific",
            cls.EUROPE:   "Europe",
            cls.AMERICA:   "North America"
        }
        return region_names.get(region_id)

    @classmethod
    def get_id(cls, region_name: str):
        """Get a region's ID by some name of the region."""
        region_mapping = {
            "na":        cls.AMERICA,
            "us":        cls.AMERICA,
            "america":   cls.AMERICA,
            cls.AMERICA: cls.AMERICA,
            "eu":        cls.EUROPE,
            "europe":    cls.EUROPE,
            cls.EUROPE:  cls.EUROPE,
            "asia":      cls.ASIA,
            "au":        cls.ASIA,
            "anz":       cls.ASIA,
            "oceania":   cls.ASIA,
            cls.ASIA:    cls.ASIA
        }
        try:
            region_id = region_mapping[region_name]
        except KeyError:
            region_id = None
            raise InvalidRegion()
        return region_id

class Ranks:
    """Rank IDs and mappings."""
    RANKS = (
        'Unranked',
        'Copper IV', 'Copper III', 'Copper II', 'Copper I',
        'Bronze IV', 'Bronze III', 'Bronze II', 'Bronze I',
        'Silver IV', 'Silver III', 'Silver II', 'Silver I',
        'Gold IV', 'Gold III', 'Gold II', 'Gold I',
        'Platinum III', 'Platinum II', 'Platinum I',
        'Diamond'
    )

    @classmethod
    def get_name(cls, rank_id: int):
        """Get a rank's name by its ID."""
        return cls.RANKS[rank_id]

    @classmethod
    def get_id(cls, rank_name: str):
        """Get a rank's ID by its name."""
        return cls.RANKS.index(rank_name)

    @classmethod
    def get_icon(cls, rank_id: int):
        """Get a rank's icon from its ID."""
        rank_icons = (
            "https://i.imgur.com/3m73Mdj.png",
            "https://i.imgur.com/ehILQ3i.jpg",
            "https://i.imgur.com/6CxJoMn.jpg",
            "https://i.imgur.com/eI11lah.jpg",
            "https://i.imgur.com/0J0jSWB.jpg",
            "https://i.imgur.com/42AC7RD.jpg",
            "https://i.imgur.com/QD5LYD7.jpg",
            "https://i.imgur.com/9AORiNm.jpg",
            "https://i.imgur.com/hmPhPBj.jpg",
            "https://i.imgur.com/D36ZfuR.jpg",
            "https://i.imgur.com/m8GToyF.jpg",
            "https://i.imgur.com/m8GToyF.jpg",
            "https://i.imgur.com/EswGcx1.jpg",
            "https://i.imgur.com/KmFpkNc.jpg",
            "https://i.imgur.com/6Qg6aaH.jpg",
            "https://i.imgur.com/B0s1o1h.jpg",
            "https://i.imgur.com/ELbGMc7.jpg",
            "https://i.imgur.com/ffDmiPk.jpg",
            "https://i.imgur.com/Sv3PQQE.jpg",
            "https://i.imgur.com/Uq3WhzZ.jpg",
            "https://i.imgur.com/xx03Pc5.jpg",
            "https://i.imgur.com/nODE0QI.jpg"
        )
        return rank_icons[rank_id]

class Platforms:
    """Platform IDs and mappings."""
    UPLAY = 'uplay'
    XBOX = 'xb1'
    PLAYSTATION = 'psn'

    @classmethod
    def get_name(cls, platform_id: str):
        """Get a platform's name by its ID."""
        platform_names = {
            cls.XBOX:        'Xbox One',
            cls.PLAYSTATION: 'PS4',
            cls.UPLAY:       'Uplay'
        }
        return platform_names.get(platform_id)

    @classmethod
    def get_id(cls, platform_name: str):
        """Get a platform's ID by some name of the platform."""
        platform_mapping = {
            "xb1":          cls.XBOX,
            "xone":         cls.XBOX,
            "xbone":        cls.XBOX,
            "xbox":         cls.XBOX,
            "xboxone":      cls.XBOX,
            "ps":           cls.PLAYSTATION,
            "ps4":          cls.PLAYSTATION,
            "playstation":  cls.PLAYSTATION,
            "uplay":        cls.UPLAY,
            "pc":           cls.UPLAY
        }
        try:
            platform_id = platform_mapping[platform_name.lower()]
        except KeyError:
            platform_id = None
            raise InvalidPlatform()
        return platform_id

    @classmethod
    def get_username(cls, platform_id: str):
        """Get a platform's username by its ID."""
        platform_usernames = {
            cls.XBOX: "Xbox Gamertag",
            cls.PLAYSTATION: "PSN ID",
            cls.UPLAY: "Uplay Nickname"
        }
        return platform_usernames.get(platform_id)

    @classmethod
    def get_colour(cls, platform_id: str):
        """Get a platform's colour by its ID."""
        platform_colours = {
            cls.XBOX:         Colour.green(),
            cls.PLAYSTATION:  Colour.magenta(),
            cls.UPLAY:        Colour.blue()
        }
        return platform_colours.get(platform_id)

class Operators:
    """Operator IDs and mappings."""
    DOC = "DEFAULT"
    HIBANA = "HIBANA"
    SMOKE = "SMOKE"
    KAPKAN = "KAPKAN"
    TACHANKA = "TACHANKA"
    THERMITE = "THERMITE"
    THATCHER = "THATCHER"
    GLAZ = "GLAZ"
    BANDIT = "BANDIT"
    ROOK = "ROOK"
    I_Q = "IQ"
    PULSE = "PULSE"
    MUTE = "MUTE"
    VALKYRIE = "VALKYRIE"
    FROST = "FROST"
    DOC = "DOC"
    SLEDGE = "SLEDGE"
    JAGER = "JAGER"
    BLACKBEARD = "BLACKBEARD"
    FUZE = "FUZE"
    ECHO = "ECHO"
    CAVEIRA = "CAVEIRA"
    BLITZ = "BLITZ"
    MONTAGNE = "MONTAGNE"
    ASH = "ASH"
    TWITCH = "TWITCH"
    CASTLE = "CASTLE"
    BUCK = "BUCK"
    CAPITAO = "CAPITAO"
    JACKAL = "JACKAL"
    MIRA = "MIRA"

    @classmethod
    def get_profile(cls, operator: str):
        """Get an operator's profile picture."""
        operator_profiles = {
            cls.DOC: ("https://ubistatic-a.akamaihd.net"
                      "/0058/prod/assets/images/large-doc.0b0321eb.png"),
            cls.TWITCH: ("https://ubistatic-a.akamaihd.net"
                         "/0058/prod/assets/images/large-twitch.70219f02.png"),
            cls.ASH: ("https://ubistatic-a.akamaihd.net"
                      "/0058/prod/assets/images/large-ash.9d28aebe.png"),
            cls.THERMITE: ("https://ubistatic-a.akamaihd.net"
                           "/0058/prod/assets/images/large-thermite.e973bb04.png"),
            cls.BLITZ: ("https://ubistatic-a.akamaihd.net"
                        "/0058/prod/assets/images/large-blitz.734e347c.png"),
            cls.BUCK: ("https://ubistatic-a.akamaihd.net"
                       "/0058/prod/assets/images/large-buck.78712d24.png"),
            cls.HIBANA: ("https://ubistatic-a.akamaihd.net"
                         "/0058/prod/assets/images/large-hibana.2010ec35.png"),
            cls.KAPKAN: ("https://ubistatic-a.akamaihd.net"
                         "/0058/prod/assets/images/large-kapkan.db3ab661.png"),
            cls.PULSE: ("https://ubistatic-a.akamaihd.net"
                        "/0058/prod/assets/images/large-pulse.30ab3682.png"),
            cls.CASTLE: ("https://ubistatic-a.akamaihd.net"
                         "/0058/prod/assets/images/large-castle.b95704d7.png"),
            cls.ROOK: ("https://ubistatic-a.akamaihd.net"
                       "/0058/prod/assets/images/large-rook.b3d0bfa3.png"),
            cls.BANDIT: ("https://ubistatic-a.akamaihd.net"
                         "/0058/prod/assets/images/large-bandit.6d7d15bc.png"),
            cls.SMOKE: ("https://ubistatic-a.akamaihd.net"
                        "/0058/prod/assets/images/large-smoke.1bf90066.png"),
            cls.FROST: ("https://ubistatic-a.akamaihd.net"
                        "/0058/prod/assets/images/large-frost.f4325d10.png"),
            cls.VALKYRIE: ("https://ubistatic-a.akamaihd.net"
                           "/0058/prod/assets/images/large-valkyrie.c1f143fb.png"),
            cls.TACHANKA: ("https://ubistatic-a.akamaihd.net"
                           "/0058/prod/assets/images/large-tachanka.41caebce.png"),
            cls.GLAZ: ("https://ubistatic-a.akamaihd.net"
                       "/0058/prod/assets/images/large-glaz.8cd96a16.png"),
            cls.FUZE: ("https://ubistatic-a.akamaihd.net"
                       "/0058/prod/assets/images/large-fuze.dc9f2a14.png"),
            cls.SLEDGE: ("https://ubistatic-a.akamaihd.net"
                         "/0058/prod/assets/images/large-sledge.832f6c6b.png"),
            cls.MONTAGNE: ("https://ubistatic-a.akamaihd.net"
                           "/0058/prod/assets/images/large-montagne.1d04d00a.png"),
            cls.MUTE: ("https://ubistatic-a.akamaihd.net"
                       "/0058/prod/assets/images/large-mute.ae51429f.png"),
            cls.ECHO: ("https://ubistatic-a.akamaihd.net"
                       "/0058/prod/assets/images/large-echo.662156dc.png"),
            cls.THATCHER: ("https://ubistatic-a.akamaihd.net"
                           "/0058/prod/assets/images/large-thatcher.73132fcd.png"),
            cls.CAPITAO: ("https://ubistatic-a.akamaihd.net"
                          "/0058/prod/assets/images/large-capitao.1d0ea713.png"),
            cls.I_Q: ("https://ubistatic-a.akamaihd.net"
                      "/0058/prod/assets/images/large-iq.d97d8ee2.png"),
            cls.BLACKBEARD: ("https://ubistatic-a.akamaihd.net"
                             "/0058/prod/assets/images/large-blackbeard.2292a791.png"),
            cls.JAGER: ("https://ubistatic-a.akamaihd.net"
                        "/0058/prod/assets/images/large-jaeger.d8a6c470.png"),
            cls.CAVEIRA: ("https://ubistatic-a.akamaihd.net"
                          "/0058/prod/assets/images/large-caveira.e4d82365.png"),
            'DEFAULT': ("https://ubistatic-a.akamaihd.net"
                        "/0058/prod/assets/styles/images/mask-large-bandit.fc038cf1.png")
        }
        return operator_profiles.get(operator, operator_profiles['DEFAULT'])

    @classmethod
    def get_icon(cls, operator: str):
        """Get an operator's icon."""
        operator_icons = {
            cls.HIBANA: ("https://ubistatic19-a.akamaihd.net/resource"
                         "/en-GB/game/rainbow6/siege/R6-operators-badge-hibana_275569.png"),
            cls.SMOKE: ("https://ubistatic19-a.akamaihd.net/resource"
                        "/en-GB/game/rainbow6/siege/Smoke_Badge_196198.png"),
            cls.KAPKAN: ("https://ubistatic19-a.akamaihd.net/resource"
                         "/en-GB/game/rainbow6/siege/Kapkan_Badge_229123.png"),
            cls.TACHANKA: ("https://ubistatic19-a.akamaihd.net/resource"
                           "/en-GB/game/rainbow6/siege/Tachanka_Badge_229124.png"),
            cls.THERMITE: ("https://ubistatic19-a.akamaihd.net/resource"
                           "/en-GB/game/rainbow6/siege/Thermite_Badge_196408.png"),
            cls.THATCHER: ("https://ubistatic19-a.akamaihd.net/resource"
                           "/en-GB/game/rainbow6/siege/Thatcher_Badge_196196.png"),
            cls.GLAZ: ("https://ubistatic19-a.akamaihd.net/resource"
                       "/en-GB/game/rainbow6/siege/Glaz_Badge_229122.png"),
            cls.BANDIT: ("https://ubistatic19-a.akamaihd.net/resource"
                         "/en-GB/game/rainbow6/siege/Bandit_Badge_222163.png"),
            cls.ROOK: ("https://ubistatic19-a.akamaihd.net/resource"
                       "/en-GB/game/rainbow6/siege/Rook_Badge_211296.png"),
            cls.I_Q: ("https://ubistatic19-a.akamaihd.net/resource"
                      "/en-GB/game/rainbow6/siege/IQ_Badge_222165.png"),
            cls.PULSE: ("https://ubistatic19-a.akamaihd.net/resource"
                        "/en-GB/game/rainbow6/siege/Pulse_Badge_202497.png"),
            cls.MUTE: ("https://ubistatic19-a.akamaihd.net/resource"
                       "/en-GB/game/rainbow6/siege/Mute_Badge_196195.png"),
            cls.VALKYRIE: ("https://ubistatic19-a.akamaihd.net/resource"
                           "/en-GB/game/rainbow6/siege/R6-operators-badge-valkyrie_250313.png"),
            cls.FROST: ("https://ubistatic19-a.akamaihd.net/resource"
                        "/en-GB/game/rainbow6/siege/R6-operators-badge-frost_237595.png"),
            cls.DOC: ("https://ubistatic19-a.akamaihd.net/resource"
                      "/en-GB/game/rainbow6/siege/Doc_Badge_211294.png"),
            cls.SLEDGE: ("https://ubistatic19-a.akamaihd.net/resource"
                         "/en-GB/game/rainbow6/siege/Sledge_Badge_196197.png"),
            cls.JAGER: ("https://ubistatic19-a.akamaihd.net/resource"
                        "/en-GB/game/rainbow6/siege/Jager_Badge_222166.png"),
            cls.BLACKBEARD: ("https://ubistatic19-a.akamaihd.net/resource"
                             "/en-GB/game/rainbow6/siege/R6-operators-badge-blackbeard_250312.png"),
            cls.FUZE: ("https://ubistatic19-a.akamaihd.net/resource"
                       "/en-GB/game/rainbow6/siege/Fuze_Badge_229121.png"),
            cls.ECHO: ("https://ubistatic19-a.akamaihd.net/resource"
                       "/en-GB/game/rainbow6/siege/R6-operators-badge-echo_275572.png"),
            cls.CAVEIRA: ("https://ubistatic19-a.akamaihd.net/resource"
                          "/en-GB/game/rainbow6/siege/R6-operators-badge-caveira_263102.png"),
            cls.BLITZ: ("https://ubistatic19-a.akamaihd.net/resource"
                        "/en-GB/game/rainbow6/siege/Blitz_Badge_222164.png"),
            cls.MONTAGNE: ("https://ubistatic19-a.akamaihd.net/resource"
                           "/en-GB/game/rainbow6/siege/Montagne_Badge_211295.png"),
            cls.ASH: ("https://ubistatic19-a.akamaihd.net/resource"
                      "/en-GB/game/rainbow6/siege/Ash_Badge_196406.png"),
            cls.TWITCH: ("https://ubistatic19-a.akamaihd.net/resource"
                         "/en-GB/game/rainbow6/siege/Twitch_Badge_211297.png"),
            cls.CASTLE: ("https://ubistatic19-a.akamaihd.net/resource"
                         "/en-GB/game/rainbow6/siege/Castle_Badge_196407.png"),
            cls.BUCK: ("https://ubistatic19-a.akamaihd.net/resource"
                       "/en-GB/game/rainbow6/siege/R6-operators-badge-buck_237592.png"),
            cls.CAPITAO: ("https://ubistatic19-a.akamaihd.net/resource"
                          "/en-GB/game/rainbow6/siege/R6-operators-badge-capitao_263100.png"),
            cls.JACKAL: ("https://ubistatic19-a.akamaihd.net/resource"
                         "/en-GB/game/rainbow6/siege/R6-velvet-shell-badge-jackal_282825.png"),
            cls.MIRA: ("https://ubistatic19-a.akamaihd.net/resource"
                       "/en-GB/game/rainbow6/siege/R6-velvet-shell-badge-mira_282826.png")
        }
        return operator_icons.get(operator)

    @classmethod
    def get_statistic_id(cls, operator: str):
        """Get an operator's statistic ID."""
        operator_statistic_ids = {
            cls.DOC: "teammaterevive",
            cls.TWITCH: "gadgetdestroybyshockdrone",
            cls.ASH: "bonfirewallbreached",
            cls.THERMITE: "reinforcementbreached",
            cls.BLITZ: "flashedenemy",
            cls.BUCK: "kill",
            cls.HIBANA: "detonate_projectile",
            cls.KAPKAN: "boobytrapkill",
            cls.PULSE: "heartbeatspot",
            cls.CASTLE: "kevlarbarricadedeployed",
            cls.ROOK: "armortakenteammate",
            cls.BANDIT: "batterykill",
            cls.SMOKE: "poisongaskill",
            cls.FROST: "dbno",
            cls.VALKYRIE: "camdeployed",
            cls.TACHANKA: "turretkill",
            cls.GLAZ: "sniperkill",
            cls.FUZE: "clusterchargekill",
            cls.SLEDGE: "hammerhole",
            cls.MONTAGNE: "shieldblockdamage",
            cls.MUTE: "gadgetjammed",
            cls.ECHO: "enemy_sonicburst_affected",
            cls.THATCHER: "gadgetdestroywithemp",
            cls.CAPITAO: "lethaldartkills",
            cls.I_Q: "gadgetspotbyef",
            cls.BLACKBEARD: "gunshieldblockdamage",
            cls.JAGER: "gadgetdestroybycatcher",
            cls.CAVEIRA: "interrogations",
            cls.JACKAL: "cazador_assist_kill",
            cls.MIRA: "black_mirror_gadget_deployed"
        }
        return operator_statistic_ids.get(operator)

    @classmethod
    def get_statistic_name(cls, operator: str):
        """Get an operator's statistic name."""
        operator_statistic_names = {
            cls.DOC: "Teammates Revived",
            cls.TWITCH: "Gadgets Destroyed With Shock Drone",
            cls.ASH: "Walls Breached",
            cls.THERMITE: "Reinforcements Breached",
            cls.BLITZ: "Enemies Flahsed",
            cls.BUCK: "Shotgun Kills",
            cls.HIBANA: "Projectiles Detonated",
            cls.KAPKAN: "Boobytrap Kills",
            cls.PULSE: "Heartbeat Spots",
            cls.CASTLE: "Barricades Deployed",
            cls.ROOK: "Armor Taken",
            cls.BANDIT: "Battery Kills",
            cls.SMOKE: "Poison Gas Kills",
            cls.FROST: "DBNOs From Traps",
            cls.VALKYRIE: "Cameras Deployed",
            cls.TACHANKA: "Turret Kills",
            cls.GLAZ: "Sniper Kills",
            cls.FUZE: "Cluster Charge Kills",
            cls.SLEDGE: "Hammer Holes",
            cls.MONTAGNE: "Damage Blocked",
            cls.MUTE: "Gadgets Jammed",
            cls.ECHO: "Enemies Sonic Bursted",
            cls.THATCHER: "Gadgets Destroyed",
            cls.CAPITAO: "Lethal Dart Kills",
            cls.I_Q: "Gadgets Spotted",
            cls.BLACKBEARD: "Damage Blocked",
            cls.JAGER: "Projectiles Destroyed",
            cls.CAVEIRA: "Interrogations",
            cls.JACKAL: "Footprint Scan Assists",
            cls.MIRA: "Black Mirrors Deployed"
        }
        return operator_statistic_names.get(operator)

class Maps:
    """R6 Map IDs and mappings (hehehe)"""
    BARTLETT = 'bartlettuniversity'
    BANK = 'bank'
    BORDER = 'border'
    CHALET = 'chalet'
    CLUB_HOUSE = 'clubhouse'
    COASTLINE = 'coastline'
    CONSULATE = 'consulate'
    FAVELAS = 'favelas'
    HEREFORD = 'herefordbase'
    HOUSE = 'house'
    KAFE = 'kafedostoyevsky'
    KANAL = 'kanal'
    OREGON = 'oregon'
    PLANE = 'plane'
    SKYSCRAPER = 'skyscraper'
    YACHT = 'yacht'
    ESL = [
        BANK, BORDER, CHALET, CLUB_HOUSE, COASTLINE,
        CONSULATE, KAFE, OREGON, SKYSCRAPER
    ]
    ALL = [
        BARTLETT, BANK, BORDER, CHALET, CLUB_HOUSE, COASTLINE,
        CONSULATE, FAVELAS, HEREFORD, HOUSE, KAFE, KANAL, OREGON,
        PLANE, SKYSCRAPER, YACHT
    ]

    @classmethod
    def get_name(cls, map_id: str):
        """Get a map's name from its ID."""
        map_names = {
            cls.BARTLETT:   'Bartlett University',
            cls.BANK:       'Bank',
            cls.BORDER:     'Border',
            cls.CHALET:     'Chalet',
            cls.CLUB_HOUSE: 'Club House',
            cls.COASTLINE:  'Coastline',
            cls.CONSULATE:  'Consulate',
            cls.FAVELAS:    'Favelas',
            cls.HEREFORD:   'Hereford Base',
            cls.HOUSE:      'House',
            cls.KAFE:       'Kafe Dostoyevsky',
            cls.KANAL:      'Kanal',
            cls.OREGON:     'Oregon',
            cls.PLANE:      'Plane',
            cls.SKYSCRAPER: 'Skyscraper',
            cls.YACHT:      'Yacht'
        }
        return map_names.get(map_id)

def get_uplay_avatar(ubi_id: str):
    """Get a player's Uplay Avatar from their ubisoft ID."""
    return ("http://uplay-avatars.s3.amazonaws.com/"
            "{ubi_id}/default_146_146.png".format(ubi_id=ubi_id))
