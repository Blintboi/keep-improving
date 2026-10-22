"""Shared client identities; discovery never installs or downloads a client."""

CLIENTS = {
    'steam': ('Steam', {'steam.exe'}),
    'epic': ('Epic Games Launcher', {'epicgameslauncher.exe'}),
    'riot': ('Riot Client', {'riotclientservices.exe'}),
    'ubisoft': ('Ubisoft Connect', {'ubisoftconnect.exe', 'upc.exe'}),
    'minecraft': ('Minecraft Launcher', {'minecraftlauncher.exe'}),
    'ea': ('EA app', {'eadesktop.exe', 'ealauncher.exe', 'origin.exe'}),
    'battlenet': ('Battle.net', {'battle.net.exe', 'battle.net launcher.exe'}),
    'gog': ('GOG Galaxy', {'galaxyclient.exe'}),
    'rockstar': ('Rockstar Games Launcher', {'launcher.exe'}),
    'amazon': ('Amazon Games', {'amazon games.exe'}),
    'xbox': ('Xbox', {'xboxpcapp.exe', 'xboxapp.exe'}),
}

CLIENT_PATHS = (
    'Epic Games/Launcher/Portal/Binaries/Win64/EpicGamesLauncher.exe',
    'Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe',
    'Ubisoft/Ubisoft Game Launcher/UbisoftConnect.exe',
    'Minecraft Launcher/MinecraftLauncher.exe',
    'Electronic Arts/EA Desktop/EA Desktop/EADesktop.exe',
    'Electronic Arts/EA Desktop/EA Desktop/EALauncher.exe',
    'Origin/Origin.exe', 'Battle.net/Battle.net.exe',
    'GOG Galaxy/GalaxyClient.exe', 'Rockstar Games/Launcher/Launcher.exe',
    'Amazon Games/App/Amazon Games.exe',
)

PLATFORM_SOURCES = ('EA', 'Battle.net', 'GOG', 'Xbox', 'Rockstar', 'Amazon')
SOURCE_CLIENT = dict(zip(PLATFORM_SOURCES, ('ea', 'battlenet', 'gog', 'xbox', 'rockstar', 'amazon')))


def client_id(path):
    import ntpath
    name = ntpath.basename(str(path)).lower()
    for key, (_, names) in CLIENTS.items():
        if name in names:
            # Launcher.exe is also used by unrelated games and applications.
            if key == 'rockstar':
                from pathlib import Path
                usual = (ntpath.basename(ntpath.dirname(str(path))).lower() == 'launcher'
                         and 'rockstar games' in str(path).lower().replace('/', '\\').split('\\'))
                if not usual and not (Path(path).parent / 'RockstarService.exe').is_file():
                    continue
            return key
    return None


# Always reject these before exact EXE assignments, including publisher helpers.
CLIENT_PROCESSES = {name for _, names in CLIENTS.values() for name in names if name != 'launcher.exe'} | {
    'eabackgroundservice.exe', 'eacefsubprocess.exe', 'eacrashreporter.exe',
    'originwebhelperservice.exe', 'originclientservice.exe', 'originthinsetupinternal.exe',
    'galaxyclient helper.exe', 'galaxycommunication.exe', 'galaxyclientservice.exe',
    'galaxyclient helper (renderer).exe', 'gog galaxy notifications renderer.exe',
    'battle.net helper.exe', 'blizzarderror.exe', 'rockstarservice.exe', 'socialclubhelper.exe',
    'launcherpatcher.exe', 'amazon games ui.exe', 'amazon games services.exe',
    'gamingservices.exe', 'gamingservicesnet.exe', 'gamingapp.exe', 'gamebar.exe', 'gamebarftserver.exe',
}
