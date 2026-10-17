# Játékidőfigyelő – Windows 11

Sötét témájú, offline játékidőfigyelő személyes használatra, Steam-, Epic-,
Ubisoft Connect- és Riot-támogatással. A napi közös keret
alapból **120 perc**, előzetes figyelmeztetés **100 percnél**. Csak az előtérben
lévő telepített játék ideje számít. A program figyelmeztet, és nem állít le játékot.

Ez a meglévő Python/Tkinter alapú projekt önálló játékfigyelő modulja.
A lefekvési emlékeztetővel együtt használható: külön fájlokat, adatbázist és
automatikus indítási bejegyzést használ. Lefekvési értesítést és ahhoz tartozó
ütemezett feladatot nem hoz létre, a meglévő emlékeztetőt nem módosítja.

## Telepítés és indítás

1. A teljes csomagot bontsd ki egy mappába.
2. Kattints duplán a **Telepites.cmd** fájlra, normál felhasználóként.
3. Add meg a saját Games mappádat. Enterrel a `C:\Games` marad.
4. A telepítő ellenőrzi a Python 3.9+ és a beépített Tkinter/SQLite meglétét,
   elvégzi a kezdeti játékfelismerést, beállítja a bejelentkezés utáni indulást,
   és megnyitja a kezelőfelületet.
5. A **Popup próba** gombbal ellenőrizd az értesítést és a hangot.

Nincs pip-függőség, letöltés vagy rendszergazdai lépés. Ha nincs megfelelő Python,
a telepítő ezt jelzi; telepítsd a [Python hivatalos Windows-kiadását](https://www.python.org/downloads/windows/)
Tkinterrel, és indítsd újra a telepítést. Ezen a gépen Python 3.12.10-zel teszteltük.

A telepítés helye a Windows Dokumentumok mappáján belül `GameTimeMonitor`.
A forráscsomagot ezután áthelyezheted; a telepített Pythont tartsd meg.
A Games mappát az automatikus Gaming Hub bekapcsolásakor létrehozza, ha szükséges.
A játékok fájljait nem módosítja.

Másik Python vagy telepítési hely megadása PowerShellből:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -PythonPath "C:\Python312\python.exe" -GamesRoot "D:\Games" `
  -InstallDir "$env:USERPROFILE\Documents\GameTimeMonitor"
```

Indítás telepítés után: **Inditas.cmd**, illetve a tálcaikon. Az X gomb a tálcára
teszi a programot; tényleges kilépés a tálca jobb gombos menüjében érhető el.
Ha az ikon a Windows rejtett ikonjai között van, a tálca felfelé mutató nyilánál keresd.
Második indítás a már futó példány ablakát nyitja meg.
Telepítés után a kibontott csomag `Inditas.cmd` fájlja is a telepített példányt
nyitja meg, ugyanazzal az adatbázissal. Külön fejlesztői próbaadatokhoz
explicit `--data-dir` szükséges. Két háttérindításból egy figyelő marad futva.

A játékfigyelő saját kék játékvezérlő–óra ikont használ. **Bal kattintás**
megnyitja az ablakot akkor is, ha korábban az X gombbal elrejtetted.
Ha az ablak már nyitva van, előtérbe hozza; újabb kattintás nem rejti el.
**Jobb kattintás** natív Windows-menüt nyit: Játékidőfigyelő, Gaming Hub,
Beállítások, Játéklista és hub frissítése, illetve külön Kilépés.
A menü elvetése és az ikon fölé vitt egér nem állítja le a figyelőt.

Telepítés nélküli kipróbálás: `py -3 -B main.py`. Telepített példány hiányában
a forrás melletti `data` mappát használja; automatikus indulást a telepítő állít be.
Meglévő telepítésnél a normál indítás annak közös adatbázisát használja.

## Játékfelismerés

- **Steam:** rendszerleíró adatbázisból felismert Steam-telepítés,
  `steamapps/libraryfolders.vdf` és `config/libraryfolders.vdf`, majd a könyvtárankénti
  `appmanifest_*.acf` fájlok. A több meghajtón lévő könyvtárak is működnek.
  A Steam játékainak teljes fájlfáját nem járja be.
- **Epic:** a ProgramData alatti Epic-jegyzékmappa `.item` fájljai és a
  `LauncherInstalled.dat` tartalék telepítési index. A jegyzékekben szereplő
  tetszőleges meghajtón lévő telepítési helyek támogatottak.
- **Ubisoft Connect:** a helyi `Software\Ubisoft\Launcher\Installs` bejegyzések
  `InstallDir` értékei, valamint a `Uplay Install <azonosító>` eltávolítási
  bejegyzések neve és telepítési helye. Kezeli a felhasználói és a gépszintű,
  32/64 bites adatokat, valamint az egyéni meghajtókat. A Ubisoft Connect,
  `upc.exe` és `UplayWebCore.exe` nem számít játéknak.
- **Riot:** a ProgramData `Riot Games/Metadata` könyvtárának
  `*.product_settings.yaml` telepítési adatai és a `Riot Game <termék>.<kiadás>`
  eltávolítási registrybejegyzések. A `RiotClientInstalls.json` társított
  telepítési útvonalai tartalék felismerést adnak. A VALORANT, a League of Legends
  és később telepített, más termékazonosítójú Riot-játékok is támogatottak;
  az egyéni meghajtók és telepítési helyek automatikusan követhetők.
  A Riot Client, a League kliensfelülete és a Vanguard nem fogyaszt játékidőt.
  A pusztán letöltést előnéző `preview.manifest` nem jelent telepített játékot.
- **Games:** a beállított gyökér minden közvetlen almappája egy játékcsoport;
  az alatta lévő `bin`, `engine` és más alkönyvtárak EXE-fájljai ugyanahhoz a
  játékhoz tartoznak. A gyökérben közvetlenül lévő EXE-k egy közös csoportot alkotnak.
- **Minecraft Java:** a helyi `.minecraft/versions` telepítés és a hivatalos
  launcher saját `runtime` könyvtárai alapján felismeri a játék Java-folyamatát,
  új runtime-verziónál is. A launcher és a más programokhoz tartozó általános
  Java nem számít. Egyéni, külső Java-runtime kézzel rendelhető hozzá.

Induláskor összeveti a jegyzékeket a korábbi nyilvántartással. Működés közben
natív `ReadDirectoryChangesW` fájleseményeket és a Ubisofthoz/Riothoz
`RegNotifyChangeKeyValue` registryértesítéseket használ; nincs rendszeres teljes gép-
vagy teljes játékkönyvtár-ellenőrzés. Steam/Epic-esemény után a kis méretű
telepítési jegyzékeket és a Ubisoft/Riot telepítési indexeit olvassa újra.
A Riotnál a YAML/JSON telepítési adatok változását figyeli; a nagy játékadatokat,
adatbázisokat és javítócsomagokat nem olvassa be a felismeréshez.
A registryfigyelés a kulcsok létrehozását, módosítását és törlését is követi.
Games-eseménynél csak az érintett játékcsoportot
ellenőrzi. Teljes Games-bejárás induláskor, Games-gyökér váltásakor és elveszett
fájlrendszeresemények helyreállításakor szükséges. A mentési fájlok és textúrák
szokásos változásai nem indítanak játékkeresést.

Az eseményeket 1,2 másodperces nyugalmi idővel vonja össze; folyamatos telepítésnél
legfeljebb 5 másodpercig vár egy ellenőrzéssel. Félkész jegyzék esetén megtartja
a korábban olvasott adatot, és ritkuló ütemben újrapróbálja az olvasást.
Új fájlesemény később is kivált új ellenőrzést.

**Az első indítás is számít:** az előtérben futó EXE teljes útvonalát közvetlenül
ellenőrzi az ismert Steam-könyvtárak `steamapps/common` alkönyvtáraiban és a Games
gyökérben. Epicnél az `.item` és a launcher közös indexe adja a telepítési helyet.
Ubisoftnál a telepítési index mellett az ismert launcher `games` mappája is
tartalék felismerési gyökér, már az első indításkor.
Riotnál a kliens társított telepítési indexében szereplő pontos játékmappa
ad tartalék felismerést, amíg a termék saját telepítési adata megérkezik.
Ha a jegyzék késik, legfeljebb az utolsó 120 másodperc valóban megfigyelt előtéri
intervallumát tudja utólag besorolni. Nem talál ki játékidőt a folyamat puszta
futása alapján. A Steam ideiglenes útvonal alapú rekordja a végleges AppID-hez
olvad össze, az addig mért idő megőrzésével.
A Ubisoft és Riot ideiglenes rekordja ugyanígy a végleges játékazonosítóhoz kerül.
Ha egy korábban kézzel felvett telepítés később automatikusan felismerhetővé
válik ugyanazon a helyen, a játékideje, kizárása és EXE-szabályai összeolvadnak.

## Automatikus Gaming Hub

A **Beállítások → Gaming Hub** kapcsolóval a konfigurált Games mappa központi
indítómappává válik. Telepítéskor PowerShellből az `-EnableHub` kapcsoló is
bekapcsolja. A **Games mappa** gomb megnyitja a hubot. A Windowsban ehhez a
mappához készített asztali parancsikon közvetlenül is használható.

- A főmappában a felismert videojátékok indítói jelennek meg. A Steam/Epic/Ubisoft/Riot
  mellett a Games mappában felismert és a kézzel felvett egyéb játékok is bekerülnek.
- A `Mappak` almappa az eredeti telepítési helyekre mutat. A `Launcherek` mappában
  a megtalált Steam-, Epic-, Ubisoft- és Riot-kliensindítók vannak.
- A sakkprogramok a `Sakk` almappába kerülnek, továbbra is a játékidőkereten kívül.

A meglévő eredeti Windows-indítókat lehetőleg változatlanul másolja: az indítási
paraméterek, munkamappa és ikon megmaradnak. Steamnél és Ubisoftnál termékazonosítós
URI-t is tud készíteni, Epicnél a helyi jegyzék adja az indítási azonosítókat,
Riotnál a termék és a kiadás paramétereit használja. Egyéb játékhoz az ismert,
hozzárendelt EXE-t vagy az egyértelmű Games-EXE-t használja. Bizonytalan több-EXE-s
telepítéshez mappahivatkozást készít, amely később pontos EXE-hozzárendeléssel javítható.

A frissítés külön háttérszálon, játéklista- és parancsikonváltozásra fut. Az
asztal és a Start menü indítóinak változásait Windows-fájleseményekkel követi.
A játékidő másodpercenkénti változása nem indít parancsikongenerálást. Nincs
periodikus teljes gépkeresés, és a hub nem indít el játékot.

A hub kizárólag a saját `data/hub-state.json` nyilvántartásában szereplő,
változatlan `.lnk`/`.url` fájlokat cseréli vagy távolítja el; előbb másolatot
ment a `data/backups/hub-links-*` mappába. Egy névütközés vagy kézzel átírt
parancsikon megmarad, a saját új indító egyedi nevet kap. Könyvtárkapcsolatra
nem ír. A hub kikapcsolása vagy a figyelő eltávolítása megtartja a Games mappát.
Games-gyökér váltásakor a korábbi mappában lévő fájlokat megtartja.

**Játék eltávolításakor** az automatikusan kezelt indító és mappahivatkozás
is visszavonódik, a korábbi játékidő megmarad. A launcherindexek mellett az ismert
telepítési mappák közvetlen szülőjének létrehozás/törlés eseményeit is követi.
A kézi játékoknál a hozzárendelt EXE-k mappáit célzottan figyeli: ha minden
hozzárendelt EXE eltűnik, a játék kikerül a hubból akkor is, ha a mappája vagy
mentései megmaradtak. Ugyanoda visszatelepítve újra bekerül, a régi idővel és
szabályokkal. A felhasználó által átírt parancsikonokat továbbra is megőrzi.

Más helyre telepített, egyik ismert forrásban sem szereplő játékhoz továbbra is
az **Új kézi játék** gomb használható; ezután a hub is automatikusan átveszi.
A hub a már felismert játékokból dolgozik, az EXE-k általános játékként besorolására
nem használ önálló, teljes lemezt átvizsgáló keresőt. Az asztali egyedi ikonokat
a program folyamatos működés közben nem törli; az első géprendezés külön,
mentéssel és a hubban lévő megfelelő ellenőrzésével történt.

## Mérés és értesítések

Az előtéri ablak folyamatát másodpercenként kérdezi le, olvasási jogosultsággal.
Az EXE teljes útvonala alapján mér; a játékmappán belüli gyermekfolyamatok is
felismerhetők. Alt+Tab után a háttérben maradó játék ideje nem gyűlik tovább.
Egyszerre mindig egy előtéri folyamat időszaka számít, ezért két futó játék nem
fogyaszt kétszeres időt. Menüben, kontrollerrel és billentyűzet-/egéraktivitás
nélkül is mér. Böngészős játékokat és a Steam/Epic/Ubisoft/Riot kezelőfelületét kizárja.

Alváshoz és hibernáláshoz a Windows ébren töltött idejét mérő
`QueryUnbiasedInterruptTime` számlálót használja. Hosszú mintavételi szünetet,
óraugrást és zárolt/biztonságos asztalt nem számol el. A mintavétel miatt az
alkalmazásváltások határán körülbelül egy másodperc eltérés lehetséges.
Három másodpercnél hosszabb mintavételi szünetet biztonságból kihagy.

A nap a Windows helyi ideje szerint éjfélkor vált. Az éjfélen átnyúló rövid
intervallumot megosztja a két nap között. Az időadatok és kivételek SQLite-ban
maradnak meg. Az időadatokat 10 másodpercenként és szabályos kilépéskor menti;
váratlan leálláskor általában legfeljebb 10 másodperc még nem mentett idő veszhet el.
Nem számol időt arra az időszakra, amikor a figyelő nem futott.

100 percnél: „Már csak 20 perc játékidőd maradt mára.”

120 percnél: „Lejárt a mai 2 órás játékidőd. Ideje befejezni a játékot.”

A sötét popup a normál ablakok fölé kerül, és értesítési hang is megszólal.
Az értesítő a főablaktól független, ezért kicsinyített és tálcára rejtett
főablak mellett is megjelenik. Figyelt játék előterében előbb egyszer Esc-et
küld, majd 200 ms múlva megjelenik. A folyamat azonosságát és az előteret
közvetlenül a billentyűküldés előtt ellenőrzi; lenyomott módosítóbillentyű
mellett kihagyja az Esc-et. Egy értesítés újrapróbálása nem küld újabb Esc-et.
A küszöb napi értesítését tartósan jelöli. Lejárt keret után egy másik játékfolyamat
első előtérbe kerülése újra figyelmeztet; ugyanarra a folyamatra az Alt+Tab
nem generál állandó figyelmeztetést. A PID mellett a folyamat létrehozási idejét
is figyeli, így az újraindított játék új menetnek számít.

## Beállítások, sakk és javítások

A főablak mutatja a napi összidőt, a hátralévő időt, az aktív játékot, valamint
a játékok nevét, forrását és mai idejét. A beállításokban módosítható a napi keret,
az előzetes figyelmeztetés ideje és a Games mappa. A figyelmeztetési küszöbnek
kisebbnek kell lennie a napi keretnél. A meglévő mai időadatok beállításváltáskor
is megmaradnak.

Nem alapértelmezett Steam-, Epic- és Ubisoft Connect-helyek a beállításokban
szintén hozzáadhatók. A korábbi beállítások a frissítéskor megmaradnak.
A Riot egyéni játékhelyeit a helyi telepítési adatokból veszi át, külön beállítás nélkül.

- **Kizárás / engedélyezés:** a kiválasztott teljes játékot kapcsolja át.
- **Új kézi játék:** kiválasztasz egy EXE-t, és nevet adsz neki.
- **EXE hozzárendelése:** egy kiválasztott játékhoz rendel másik EXE-t, például
  a játékmappán kívül telepített gyermekfolyamatot vagy egy tévesen kihagyott launchert.
- **Kivételek:** pontos EXE-útvonal alapján kizárás, illetve korábbi szabály törlése.

Az ismert sakknevek (`chess`, `sakk`, `stockfish`, `lc0`, `fritz` stb.) alapból
kizártak. A megnevezés alapú felismerés nem teljes sakkkatalógus: egy más néven
telepített sakkprogramot egyszer ki kell zárni. A Chess.com böngészőben eleve
nem számít. A kizárások és hozzárendelések újraindítás után is megmaradnak.
A javítások a következő mintáktól hatnak; korábbi időt nem törölnek.

## Korlátok

- A helyi launcherjegyzékek nem hivatalos, verziózott API-k; szokatlan vagy új
  formátumhoz később módosítás kellhet. Nem alapértelmezett jegyzékhely a beállításokban
  hozzáadható. Új meghajtó csatlakoztatásakor újra ellenőrzi a launcherforrásokat.
- Steam nem játék jellegű alkalmazásai offline, pusztán a telepítési jegyzékből
  nem mindig különíthetők el. Ezeket kézzel ki lehet zárni.
- Az EXE-nevek alapján kiszűrt konfigurálók, launcherek és segédprogramok között
  lehet valódi játék is. A pontos EXE-hozzárendelés felülírja ezt a heurisztikát.
  Ismeretlen segédprogramot egyszer kézzel ki kell zárni. Böngészők és a Steam/Epic/Ubisoft/Riot
  általános kezelőfelülete kézi hozzárendeléssel sem válik játékká.
- Egy Games almappa egy játékcsoport. Több, egymásba ágyazott játékot külön
  főmappákba érdemes telepíteni, vagy pontos EXE-hozzárendeléssel elkülöníteni.
  Könyvtárkapcsolatok/junctionök bejárását kerüli.
- A Games mappába tett `.lnk` parancsikonok az eredeti telepítési helyre mutatnak.
  Önmagukban nem regisztrálnak új játékot. Külső, launcher által nem ismert
  játékhoz az eredeti EXE-t kell kézzel hozzáadni a figyelőben.
- Epic tetszőleges új telepítési helye csak valamely helyi telepítési indexből
  ismerhető meg. Ha egyik index sem írja le időben, az ismeretlen helyen futó
  játék azonosítása késhet; 120 másodpercnél régebbi ismeretlen időszakot nem pótol.
- Ubisoftnál a szabványos launcher- és telepítési registrybejegyzéseket kezeli.
  Ha ezek hiányoznak, az ismert `games` mappák és az utolsó 120 másodperc
  megfigyelt előtéri időszaka ad tartalék felismerést. Szokatlan, index nélküli
  telepítéshez kézi EXE-hozzárendelés szükséges lehet.
- Riotnál a szabványos helyi telepítési indexekből és a legfelső szintű YAML
  telepítési mezőkből dolgozik, fiókadatokat nem olvas. Ha egyik indexben sem
  szerepel időben a telepítési hely, a besorolás késhet; az utolsó 120 másodperc
  valóban megfigyelt ideje utólag elszámolható. Új indexformátumhoz frissítés kellhet.
- Más helyre telepített gyermekfolyamat vagy nem olvasható, védett folyamat kézi
  hozzárendelést igényelhet. Ha a Windows nem engedi lekérdezni az EXE útvonalát,
  a program nem próbál jogosultságot emelni vagy anti-cheat védelmet megkerülni.
- Kizárólagos teljes képernyő, UAC vagy más biztonságos asztal fölötti popup
  nem garantálható. A hang tartalék jelzés; némított hangrendszeren nem hallható.
- A figyelő figyelmeztető eszköz; kézi kilépéssel vagy az automatikus indulás
  kikapcsolásával szüneteltethető. Nem szülői zárolás és nem megkerülésbiztos.

## Eltávolítás, ellenőrzés és adatok

**Eltavolitas.cmd:** szabályosan leállítja a saját figyelőt, eltávolítja a saját
automatikus indítási bejegyzését és az ismert programfájljait. A játékokat és
a `data` mappában tárolt időadatokat/kivételeket megtartja. A Pythont és a
lefekvési emlékeztetőt nem módosítja. Újratelepítéskor az adatok újra használhatók.

Automatikus indítás: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`,
értéknév: `GameTimeMonitor`. Nincs szolgáltatás vagy új ütemezett feladat.
Az Indítópultban saját `GameTimeMonitor.lnk` tartalék indító is van, ugyanarra
a háttérparancsra. A két bejelentkezési út ugyanazt az egypéldányos figyelőt
használja; eltávolításkor mindkét saját indítási bejegyzés megszűnik.
A `.cmd` indítók csak a saját PowerShell-folyamatuk végrehajtási házirendjét
állítják `Bypass` módba; a gép tartós beállításait nem változtatják meg.

**Ellenorzes.cmd:** telepített fájlok, Python, SQLite és automatikus indulás ellenőrzése.
Napló: `data/monitor.log`, méretkorláttal. Adatbázis: `data/usage.sqlite3`.
Mentéshez állítsd le a figyelőt és másold a teljes `data` mappát. Nincs telemetria,
hálózati kérés vagy internetigény. A Git-repóba nem kerül adatbázis, napló vagy
személyes játéklista. Részletes tesztelés: [TESZTELES.md](TESZTELES.md).

Műszaki alapok: [előtéri ablak](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow),
[teljes folyamatútvonal](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew),
[fájlrendszeresemények](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-readdirectorychangesw),
[registryértesítések](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regnotifychangekeyvalue),
[alvást kihagyó időmérés](https://learn.microsoft.com/en-us/windows/win32/sysinfo/interrupt-time),
[tálcaikon](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shell_notifyiconw),
[natív tálcamenü](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-trackpopupmenuex).
