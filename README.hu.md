# Játékidőfigyelő — 2.26.2

**[Letöltés Windows x64-re — 2.26.2](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 ellenőrzőösszeg](downloads/GameTimeMonitor-Setup.exe.sha256) · [English](README.md)

Windows 11-es Gaming Hub, amely méri az előtérben töltött játékidőt, mutatja a megmaradt napi keretet, és emlékeztet a befejezésre. Heti időrendet, lefekvési emlékeztetőt, testreszabható számlálót és a saját számítógépek közötti választható, titkosított statisztikaszinkront kínál.

Ingyenes, nyílt forráskódú személyes projekt. A mérés és a helyi funkciók internet és fiók nélkül működnek. **Az automatikus verzióellenőrzés alapból bekapcsolt, de kikapcsolható; a felhőszinkron alapból kikapcsolt.**

## Mit tud a program?

- **Játékkönyvtár:** telepített játékok felismerése és indítása, keresés, szűrés, kártyák elrejtése, EXE-hozzárendelés és játékok kizárása. A borítók helyi fájlokból és gyorsítótárakból származnak.
- **Időmérés:** a követett játékok egy közös helyi napi keretet használnak. A háttérben futó játék, böngésző, indítókliens, alvó vagy zárolt gép nem fogyasztja. A menü és a szünet is beleszámíthat, ha a játék marad az előtérben.
- **Heti időrend:** hét napgombbal egyetlen napra vagy tetszőleges napcsoportra állítható keret, figyelmeztetés, korlátozás és lefekvés.
- **Visszaszámláló:** asztali vagy választható RTSS-megjelenítés, pontos elhelyezés, kijelző, fedettség, méret, normál/figyelmeztető szín és játékonkénti eltérések.
- **Emlékeztetők:** szerkeszthető alapüzenetek, időhelyettesítők, választható hangok, saját WAV vagy némítás, mentés előtti próbával.
- **Statisztikák:** színkódolt napi oszlopok játékok vagy gépek szerint, jelmagyarázat, részletek rámutatásra/kattintásra, időszakok és összesítések. Az összekapcsolt gépek átnevezhetők.
- **Magyar és angol felület:** a nyelvváltás a szövegeket frissíti, a betöltött képek, kijelölések és nem mentett beállítások megtartásával.

**A 2.26.2-ben:** javult a számláló átadása gyors Alt–Tab, játékok közötti váltás és az előnézet ki-be kapcsolása közben. A régi RTSS-válasz nem állíthat vissza korábbi állapotot; az állapotellenőrzés nem törölgeti a változatlan szöveget. Az átmeneti felderítési/figyelési hibák csendben, naplózva újrapróbálkoznak; tartós hibánál közérthető jelzés jelenik meg.

![Játékkönyvtár és napi időkeret](docs/images/library-en.png)
*Az angol felület szemléltetése. A képek korábbi elrendezést és példaelőzményeket is mutathatnak; a játékborítók jogai az eredeti tulajdonosoké.*

## Követelmények és támogatott források

A támogatott rendszer **Windows 11 x64**. A telepítő tartalmazza a Pythont, a Qt/PySide6 6.12.0-t és a szükséges futtatókönyvtárakat; a szokásos telepítéshez és használathoz nem kell rendszergazdai jogosultság. macOS-re, Linuxra és Windows ARM64-re nincs támogatott kiadás.

| Forrás | Felismerés és indítás |
| --- | --- |
| Steam | Helyi telepítési bejegyzések, több játékkönyvtárral is. |
| Epic Games Launcher | Telepített játékok helyi jegyzékei. |
| Ubisoft Connect | Telepített játékok és indítás a kiadó kliensével. |
| Riot Client | Telepített játékok és klienses indítás; a Riot Client és Vanguard ideje nem játékidő. |
| EA app / Origin | Helyi telepítési bejegyzések; kiadói indítóhivatkozás vagy hozzárendelt játék-EXE. |
| Battle.net | Telepítési bejegyzések és helyi Agent-jegyzék; felismert termékek indítóhivatkozásai. |
| GOG Galaxy / offline GOG | Bejegyzett játékok, Galaxy-indítás és helyi elsődleges indítási feladatok Galaxy nélkül. |
| Xbox / Microsoft Store | Telepített GDK-/Xbox Live-játékcsomagok; Windows-alkalmazásazonosítóval történő indítás. |
| Rockstar Games Launcher | Telepítési bejegyzések és indítás a kiadó kliensével. |
| Amazon Games | Helyi telepítési adatbázis és kiadói indítóhivatkozások. |
| Minecraft: Java Edition | Hivatalos Java-adatkönyvtár és a hozzá tartozó külön futtatókörnyezet. |
| Önálló és egyéb játékok | A beállított Games mappa és kézi EXE-hozzárendelések. |

**A Games mappa megmarad.** Kiegészítő felismerési hely az önálló játékokhoz; a Steam vagy más felismert kliens könyvtárait nem kell ide áthelyezni. A kézi EXE-hozzárendelés segíthet a fel nem ismert játékoknál, de nem tesz hozzáférhetővé védett EXE-t vagy ellenőrizhetetlen telepítést. A megfelelő játékadatok nélküli Store-csomagoknál, emelt jogosultságú és védett játékoknál lehetnek korlátok. A kliensfelismerés nem telepít indítóprogramot vagy játékot.

A **Játékkliensek** oldala megjegyzi a felismert klienseket újraindítások között. Kliens telepítése, áthelyezése vagy törlése után használd a **Frissítés** gombot. A játékkártya elrejtése és a játék időmérésből való kizárása külön művelet.

## Telepítés, frissítés és bezárás

1. Töltsd le a **GameTimeMonitor-Setup.exe** fájlt a lap tetejéről, majd indítsd el.
2. Nyisd meg a **Gaming Hubot** az asztali parancsikonról vagy a tálcáról. A következő Windows-bejelentkezéseknél a figyelő a tálcán indul.
3. A **Beállításokban** módosítsd az értékeket, majd válaszd a **Mentés** gombot. Az alapértelmezett programmappa `%LOCALAPPDATA%\Programs\GameTimeMonitor`; a külön tárolt profil a Windows Dokumentumok mappáján belüli `GameTimeMonitor\data`.

A frissítés előbb profilmentést készít, és megőrzi az előzményeket, beállításokat, szinkronizálási hitelesítő adatokat, elrejtett játékokat és mérési kizárásokat. Az ablak **X** gombja a Hubot a tálcára rejti; a mérés és az emlékeztetők tovább működnek. A leállításhoz válaszd a tálcamenü **Kilépés a figyelőből** pontját.

### Frissítési értesítések

A **Beállítások → Programfrissítések** alatt látható a telepített verzió, kikapcsolható az automatikus keresés, és kézzel is indítható frissítéskeresés. Automatikusan legfeljebb naponta egyszer kér le egy kis nyilvános GitHub-verziófájlt. Új verziónál a Hubban és a tálcán jelez, játékot megszakító felugró ablak nélkül.

A **Frissítés letöltése** a hivatalos telepítő címét nyitja meg a böngészőben. A letöltést és a telepítést te indítod; a program nem tölt le és nem telepít végrehajtható fájlt a háttérben. Az átmeneti automatikus ellenőrzési hibák csak naplózódnak. A 2.26.0-nál régebbi kiadásról kézi letöltéssel lehet erre a funkcióra frissíteni.

### Windows-megbízhatóság

A telepítő és a fő program jelenleg **nincs digitálisan aláírva**. A Windows ismeretlen kiadóra figyelmeztethet, helyi biztonsági házirend pedig blokkolhatja a futást. Az ikon, a verzióadat és az egyező SHA-256 nem Microsoft-jóváhagyás vagy kiadói aláírás. A program nem ad magának vírusirtó-kivételt, és nem kapcsolja ki a Windows védelmét. Részletek: [Windows-megbízhatóság és aláírás](docs/WINDOWS-TRUST.hu.md).

## Napi keret, heti időrend és lefekvés

A **Beállítások → Heti időrend** hét napgombja és a **Minden nap / Hétköznapok / Hétvége** gyorskijelölés egy napot vagy tetszőleges napcsoportot választ ki. Az eltérő értékeket külön jelzi; csoportos szerkesztéskor csak az átírt mezők változnak. Egy nap teljes időrendje külön paranccsal másolható. A korábbi hétvégi beállítások megmaradnak.

| Beállítás | Új profil kezdőértéke |
| --- | --- |
| A követett játékok közös napi kerete | 120 perc |
| Korai figyelmeztetés | 100 perc után |
| Választható játékkorlát küszöbe | 125 perc; a korlátozás kikapcsolt |
| Lefekvési figyelmeztetés / lefekvés / reggeli feloldás | 23:55 / 00:00 / 06:00; a lefekvési funkció kikapcsolt |
| A hátralévő játékidő igazodjon a lefekvéshez | Kikapcsolt |
| Visszaszámláló / RTSS / felhőszinkron | Kikapcsolt |
| Automatikus verzióellenőrzés | Bekapcsolt |

A napi keret **helyi idő szerinti éjfélkor** újul meg. A választható **A hátralévő játékidő igazodjon a lefekvéshez** beállítás a megmaradt napi keret és a lefekvésig hátralévő idő közül a rövidebbet mutatja. Ha 23:00-kor még két teljes óra felhasználatlan kereted van, de éjfélkor lefekszel, egy órát jelez. A Hub, a tálca és az asztali/RTSS-számláló egységesen számol. Az alvási időszakban a reggeli feloldásig nulla marad. Ez a mutatott szabad időt igazítja; a megadott napi keretet és a naptári előzményeket nem írja át.

A napi játékkorlát és a lefekvési minimalizálás külön bekapcsolható funkció. A napi korlátozás a küszöb után ismételten minimalizálhatja az engedett követett játékot; visszatéréskor tíz másodpercet hagy mentésre/kilépésre. A lefekvési minimalizálás reggelig tíz másodpercenként érintheti az engedett előtérben lévő alkalmazásokat, köztük a böngészőt is. **A program nem kapcsolja le a számítógépet.** A minimalizált játék tovább futhat; online játékban inaktivitási vagy meccselhagyási büntetés is előfordulhat. A védett játékok további korlátait lentebb ismertetjük.

A lefekvési funkció a helyi órát követi, amíg a figyelő fut; nem ébreszti a gépet, és nem pótolja az elmulasztott jelzést. A Hub elérhető marad a beállítások módosításához. Ez személyes emlékeztető, nem megkerülhetetlen szülői felügyelet.

![Lefekvési beállítások](docs/images/bedtime-en.png)

## Visszaszámláló, előnézet és egyéni üzenetek

A számlálót a **Beállításokban** kapcsolhatod be. Választható kijelző, fedettség, valamint külön normál és figyelmeztető szín. A méret **8–72 pt** között állítható; az elhelyezéshez pontos vízszintes/függőleges pixelmező vagy húzható kisméretű ábra használható. A nyílbillentyű egy, a Shift + nyíl tíz pixelt mozgat. Az útmutató az ábra alatt marad, nem takarja el húzás közben.

A **Játékonkénti számlálók** a játék menüjéből is elérhetők, és telepített játékokat sorolnak fel. Játékonként örökölhetők a közös értékek, használható saját kijelző/elhelyezés/méret/szín, vagy elrejthető a számláló. A fedettség és az automatikus RTSS-mód közös beállítás. Az elrejtés nem állítja le az időmérést; a felugró emlékeztető tartalék útvonala megmarad. Az eltávolított játék kikerül a telepített játékok választójából, de az előzménye és mentett beállítása megmarad.

Az elhelyező ábrán az engedett futó játékablak halvány **állóképe** is megjelenhet. A szerkesztő megnyitása vagy a **Játékkép frissítése** új képet kér; ez nem folyamatos videókép. Egyes megjelenítők nem adnak képet. A kép csak memóriában marad, nem mentődik és nem szinkronizálódik.

Az **Előnézet (10 mp)** előtérbe hozza az engedett felismert játékot, szükség esetén visszaállítja a tálcáról, és az asztali/RTSS-megjelenítést használja. Az Alt–Tab megszakítja ezt az előnézetet. A nem mentett módosítások ugyanazt a számlálót frissítik; az előnézeti számok minták, miközben a tényleges előtérben töltött idő mérése tovább fut. Az előnézeti állapot a gomb mellett választható, a módosítások menthetők vagy elvethetők.

Kompatibilis teljes képernyős játékhoz külön telepíthető az [RTSS 7.3.7+](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/), és bekapcsolható a számláló beállításaiban. A program a felismert, engedett játékokra automatikusan alkalmazza; nem kell kézi EXE-lista. Ha a játék már futott, az RTSS engedélyezése után egyszer mentésre és játék-újraindításra lehet szükség. Az asztali tartalék megjelenítés és az emlékeztetők lehetősége a játéktól és a Windows értesítési állapotától is függ.

A **Beállítások → Egyéni üzenetek** alatt szerkeszthető a figyelmeztetés, a napi keret lejártának, a későbbi játékmenetnek és a lefekvésnek a szövege. A mezők szerkeszthető alapüzenettel indulnak. Használható időhelyettesítők: `{remaining}`, `{minutes}`, `{time}`, `{bedtime}`; a többi szöveg szó szerint jelenik meg. Az alapértékek visszaállíthatók. Windows-hang, saját WAV vagy némítás választható. Az üzenetek, hangok, játékonkénti stílusok és kockázati engedélyek helyben maradnak.

## Védett játékok és az anticheat korlátai

Az automatikus besorolás játékazonosítókat, EXE-neveket és ismert telepítési jelzőfájlokat használ. Játékonként működik; a rangsorolt és offline módot nem próbálja játékadatok olvasásával megkülönböztetni. A felismerés nem kiadói jóváhagyás, és nem garantál minden játékverziónál tiltás- vagy összeomlásmentességet.

| Művelet | Felismert védett játék esetén |
| --- | --- |
| Előtérben töltött idő mérése | Folytatódik, amennyire a Windows engedi a folyamat azonosítását. |
| Overlay, játékkép és élő előnézet | Külön játékonkénti overlayengedélyig kikapcsolt; a vezérlők engedély nélkül rejtve maradnak. |
| Automatikus minimalizálás | Külön játékonkénti minimalizálási engedély kell; az overlay elfogadása nem jogosítja fel. |
| Automatikus Escape | Beleegyezéssel is mindig tiltott. |
| Emlékeztető | Fókuszt nem kérő ablak; nem megfelelő teljes képernyős helyzetben a választott hang. Néma vagy hibás hangnál a kézbesítés várakozik. |
| Ellenőrizhetetlen telepítés / anticheat-segédfolyamat | A tiltást beleegyezés sem írja felül. |

Az engedély a **Játékonkénti számlálók → Overlaykockázatok áttekintése** alatt megtekinthető vagy visszavonható. Helyben, a játékhoz és telepítési helyéhez kötve mentődik; változáskor új elfogadás kellhet. A nem védett/casual játékok beállított funkciói megmaradnak. Az RTSS külső grafikus hookot használhat; az engedély visszavonása nem tölti ki a más program által már betöltött modult. Részletek és hivatalos források: [anticheat-kompatibilitási áttekintés](docs/ANTICHEAT.hu.md).

## Statisztikák és a gépek összekapcsolása

A statisztika színkódolt, egymásra épülő napi oszlopokat ad **játék/gép** váltóval, egyező jelmagyarázattal és táblázatjelölőkkel, idő- és arányösszesítéssel, időszakokkal és napi részletekkel rámutatásra/kattintásra. A **Gép átnevezése** minden összekapcsolt gépre működik: a saját név a következő szinkronnal átkerül, a többi gép beceneve helyi, az aktuális kapcsolathoz tartozik, és offline is használható.

![Napi statisztikák](docs/images/statistics-en.png)

A saját gépeid összekapcsolása:

1. Az első gépen nyisd meg a **Statisztikák → Gépek összekapcsolása** ablakot, jelentkezz be GitHubbal, kapcsold be a szinkront, majd ments.
2. A kapcsolati kódot másold be a másik gépen ugyanebbe az ablakba, és ments. Meglévő kódhoz csatlakozáshoz nem kell újabb GitHub-belépés.

A szinkron eseményekre indul: egyszer induláskor, követett játék kezdésekor és utána, a közeli változásokat egy nyugodt perc után összevonva. Nincs időszakos háttérszinkron. Kézzel is frissíthetsz. Gépenként legalább tíz perc telik el két kérés között, újraindítás után is. A közös szolgáltatás UTC-naponként 20, havonta 600 sikeres kérést enged az összekapcsolt gépeknek, tulajdonosonkénti korláttal is. A függő feltöltés kivárja a korlátot; a gépnek bekapcsolva és online kell maradnia, hogy a legutóbbi ideje átérjen. Minden összekapcsolt géphez legalább 2.12.0 szükséges; az aktuális javításokhoz a legfrissebb verzió ajánlott.

A diagram gépeket is összesíthet, de **a napi keret, a beállítások és a játékkizárások helyben maradnak**. A közös szolgáltatás regisztrációs/erőforrás-korlátokkal, garantált rendelkezésre állás nélkül működik. Kimaradáskor a helyi mérés folytatódik.

## Adatvédelem, mentés és eltávolítás

- A helyi napi előzmények/beállítások a Windows tényleges Dokumentumok helyén, a `GameTimeMonitor\data` mappában vannak. Nincs reklám- vagy általános analitikai telemetria; a helyi előzmény-adatbázis nem titkosított.
- A napi verziólekérésnél a GitHub normál kapcsolati adatokat, köztük IP-címet kap. Játékidőt, játéknevet/útvonalat, gépnevet, hitelesítő adatot, eszközazonosítót és telepített verziót nem küld a program. Az automatikus kérés kikapcsolható.
- A választható szinkron a játékidőket, játékneveket/forrásokat és gépneveket a gépen titkosítja. A szolgáltatás titkosított pillanatképet és kérési metaadatokat kap. **A kapcsolati kód birtokosa hozzáférhet és módosíthatja a csoport közös előzményeit: tartsd titokban.**
- A mentett kapcsolati kódok és fiókmunkamenetek a Windows-felhasználóhoz kötött védelemmel tárolódnak. A mentések magánjellegűek; másik Windows-fiókra/gépre költözéskor új belépésre vagy a kapcsolati kód újbóli megadására lehet szükség.

Mentéshez **lépj ki a figyelőből a tálcamenün át**, majd másold ki a teljes adatmappát. A frissítések profilmentést készítenek. Az eltávolítás megőrzi a profilt; a helyi adatok törléséhez külön kell eltávolítani az adatmappát és a már nem szükséges mentéseket. A szinkron kikapcsolása és a kijelentkezés nem vonja vissza a kódot, és nem törli a többi gép másolatait. A tulajdonosi visszavonás/kódcsere és szerveroldali megőrzés részletei az [adatkezelési](PRIVACY.md) és [biztonsági](SECURITY.md) leírásban találhatók.

## Gyakori kérdések

| Helyzet | Mit érdemes megnézni? |
| --- | --- |
| Hiányzik egy telepített játék | Frissítsd a felismerést, ellenőrizd a kliens bejegyzéseit, vagy rendelj hozzá hozzáférhető játék-EXE-t. Önálló játékokhoz megmarad a Games mappa. |
| Egy törölt játék látszik az előzményekben | Az előzményt megőrzi a program; a számláló választója csak telepített játékokat mutat. |
| Nincs számláló/játékkép | Nézd meg a közös/játékonkénti beállítást, kijelzőt, kockázati engedélyt és az RTSS-t. A képrögzítés a játék megjelenítőjétől függ. |
| A számláló kevesebbet mutat a napi keretnél | Ellenőrizd a lefekvéshez igazítást és az adott nap időrendjét. |
| Bezárás után is mér | Az X a tálcára rejt. A Kilépés a figyelőből állítja le. |
| Késik a másik gép játékideje | Ellenőrizd a szinkront, internetet, tízperces várakozást és közös szerverkeretet. |
| Átmeneti felderítési gond van | Az automatikus újrapróbálkozás naplózódik; tartós hibánál érthető jelzés jelenik meg. |

## Projekt, segítség és fejlesztés

Reprodukálható hibát a [GitHub Issues](https://github.com/Blintboi/windows-game-time-monitor/issues) felületén jelezhetsz az alkalmazás/Windows verziójával, a játék forrásával és a lépésekkel. Kapcsolati kódot, tokent vagy saját profiladatbázist ne csatolj nyilvánosan. Biztonsági hibához a [biztonsági leírás](SECURITY.md) szerinti privát útvonalat használd.

A fejlesztés [GitHub Sponsorson támogatható](https://github.com/sponsors/Blintboi). Ez önkéntes; a program ingyenes és nyílt forráskódú marad. A saját kód és dokumentáció [MIT licencű](LICENSE); a borítók és csomagolt összetevők saját jogai és [licencei](THIRD-PARTY-NOTICES.md) megmaradnak.

Forrásból futtatás, csomagolás és fejlesztői tesztelés: [fejlesztői útmutató](docs/DEVELOPMENT.md), [felépítés](ARCHITECTURE.md), [tesztelés](TESTING.md). A kiadás forrás- és telepítő-titokellenőrzést kap; az ellenőrzések csökkentik a kockázatot, nem ígérnek minden környezetre kompatibilitást.
