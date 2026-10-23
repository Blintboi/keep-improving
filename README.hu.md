# Játékidőfigyelő — 2.26.2

**[Letöltés Windows x64-re — 2.26.2](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 ellenőrzőösszeg](downloads/GameTimeMonitor-Setup.exe.sha256) · [English](README.md)

A Játékidőfigyelő egy helyen kezeli a telepített játékaidat, a napi játékidőt és a személyes emlékeztetőket. Tervezd meg a játékra szánt időt, kövesd a megmaradt keretedet, és tekintsd át a játékszokásaidat a saját számítógépeiden.

Ingyenes, nyílt forráskódú Windows-alkalmazás, magyar és angol felülettel. A helyi időmérés internet és fiók nélkül is működik; a gépek összekapcsolása választható.

## Főbb funkciók

- **Játékkönyvtár:** telepített játékok felismerése és indítása, keresés a gyűjteményben, az időmérésbe bevont játékok kiválasztása.
- **Napi keret és heti időrend:** időkeretek, figyelmeztetések és lefekvési emlékeztetők külön napokra vagy napcsoportokra.
- **Testreszabható számláló:** hátralévő játékidő megjelenítése állítható helyzettel, mérettel, fedettséggel és színekkel, akár játékonként eltérően.
- **Személyes emlékeztetők:** saját üzenetek a hátralévő idő adataival, választható hangjelzéssel vagy saját WAV-fájllal.
- **Játékidő-statisztikák:** színkódolt diagramok játékok vagy gépek szerint, napi részletek és a kiválasztott időszak összesítése.
- **Gépek összekapcsolása:** a saját számítógépek statisztikáinak összesítése titkosított szinkronnal és átnevezhető gépekkel.

![Játékkönyvtár és napi időkeret](docs/images/library-en.png)
*Az angol felület szemléltetése. A képek korábbi elrendezést és példaelőzményeket is mutathatnak. A játékborítók jogai az eredeti tulajdonosoké.*

## Követelmények és támogatott játékforrások

**Windows 11 x64.** A telepítő tartalmazza a szükséges futtatókörnyezetet; Pythont nem kell külön telepíteni. A szokásos telepítéshez és használathoz nem szükséges rendszergazdai jogosultság.

Támogatott források: **Steam, Epic Games Launcher, Ubisoft Connect, Riot Client, EA app / Origin, Battle.net, GOG Galaxy és offline GOG-játékok, Xbox / Microsoft Store, Rockstar Games Launcher, Amazon Games és Minecraft: Java Edition**.

Az önálló vagy fel nem ismert játékokhoz használható a beállított **Games mappa**, illetve kézzel is hozzárendelhető a játék indítófájlja. A meglévő klienskönyvtárakat nem kell áthelyezni. A felismerés és az indítás a telepítéstől is függ; egyes védett vagy Store-csomagoknál korlátozott lehet.

## Első lépések

1. Töltsd le és indítsd el a **GameTimeMonitor-Setup.exe** fájlt a fenti hivatkozásról.
2. Nyisd meg a **Gaming Hubot** az asztali parancsikonról vagy a tálcáról, és tekintsd át a játékkönyvtáradat.
3. Add meg az időrendet és az emlékeztetőket a **Beállításokban**, majd válaszd a **Mentés** gombot.

A figyelő a Windows-bejelentkezéskor a tálcán indul. A Hub **X** gombja után a mérés és az emlékeztetők tovább működnek; a programot a tálcamenü **Kilépés a figyelőből** pontja állítja le.

A frissítés megőrzi az előzményeket, a beállításokat és az időmérési kizárásokat. Az automatikus frissítési értesítés alapból bekapcsolt, a Beállításokban kikapcsolható. A **Frissítés letöltése** a böngészőben nyitja meg a telepítőt; a letöltés és a telepítés időpontját te választod meg.

A program jelenleg **nincs digitálisan aláírva**, ezért a Windows ismeretlen kiadóra figyelmeztethet vagy korlátozhatja a futását. Részletek: [Windows-megbízhatóság és aláírás](docs/WINDOWS-TRUST.hu.md).

## Tervezd meg a játékidőt

A követett játékok közös napi keretet használnak. Az idő akkor számít, amikor a felismert játék van az előtérben, beleértve annak menüjét vagy szünetét is. A háttérben futó játék, az indítókliens és a zárolt gép nem fogyasztja a keretet. A napi keret helyi idő szerint éjfélkor újul meg.

A **Beállítások → Heti időrend** hét napgombjával minden nap külön állítható, vagy egyszerre több napra is alkalmazható ugyanaz a terv. Megadható napi keret, korai figyelmeztetés és lefekvés, valamint választható automatikus minimalizálás a korlát elérésekor.

Az **A hátralévő játékidő igazodjon a lefekvéshez** beállítással a számláló a napi keretből és a lefekvésig hátralévő időből a rövidebbet mutatja. Ha 23:00-kor még két órád lenne, de éjfélkor lefekszel, egy órát jelez.

A program személyes időbeosztást segít, nem megkerülhetetlen szülői felügyelet. Az automatikus minimalizálás nem zárja be a játékot és nem kapcsolja le a gépet; online játékban inaktivitási vagy meccselhagyási következményekkel járhat.

![Lefekvési beállítások](docs/images/bedtime-en.png)

## Számláló és emlékeztetők a saját igényeidhez

Válassz kijelzőt, pontos elhelyezést, betűméretet, fedettséget, valamint külön normál és figyelmeztető színt. Az elhelyezés húzással vagy pixelkoordinátákkal adható meg. A **Játékonkénti számlálók** között minden játékhoz külön helyzet és megjelenés állítható, illetve elrejthető a számláló.

A tíz másodperces előnézettel egy kompatibilis, futó játék fölött is kipróbálható a megjelenés. Az elhelyezést halvány játékkép segítheti, amely csak a memóriában marad. Kompatibilis teljes képernyős játékokhoz külön telepíthető az [RTSS 7.3.7 vagy újabb verziója](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/).

A **Beállítások → Egyéni üzenetek** alatt személyre szabható a figyelmeztetések, a napi keret és a lefekvési emlékeztetők szövege, időadatok helyettesítőivel és választható hangjelzéssel. Az alapüzenetek bármikor visszaállíthatók.

### Védett játékok

A felismert védett játékoknál az overlay és a játékképes előnézet külön, játékonkénti kockázati beleegyezéshez kötött. Az automatikus minimalizálás önálló engedélyt igényel, bizonyos műveletek pedig nem engedélyezhetők. Az emlékeztető fókuszt nem kérő ablakkal vagy indokolt esetben hanggal jelez. Ezek az óvintézkedések nem garantálják a kompatibilitást vagy a kitiltás elkerülését. A funkciók engedélyezése előtt tekintsd át az [anticheat-kompatibilitási útmutatót](docs/ANTICHEAT.hu.md).

## Statisztikák több számítógépen

A **Statisztikák** oldalon összehasonlítható a játékidő játékok vagy gépek szerint, kiválasztható az időszak, és megtekinthetők az egyes napok részletei. A gépek neve szerkeszthető, hogy a diagramok könnyen áttekinthetők legyenek.

Az összekapcsoláshoz az első gépen nyisd meg a **Statisztikák → Gépek összekapcsolása** ablakot, jelentkezz be GitHubbal, és engedélyezd a szinkront. A kapott kapcsolati kódot add meg a többi gépen; meglévő kódhoz csatlakozáshoz nem kell újabb GitHub-belépés.

A szinkron választható, az adatokat a program a gépeden titkosítja. **A kapcsolati kódot tartsd titokban: a birtokosa hozzáférhet a csoport közös előzményeihez, és módosíthatja azokat.** A napi keretek, a beállítások és a játékkizárások helyben maradnak.

A gépek közötti frissítés nem azonnali: két kérés között legalább tíz perc telik el, a közös szolgáltatási keret UTC-naponként 20, havonta 600 sikeres kérés. A helyi időmérés internet nélkül és szolgáltatáskieséskor is működik.

![Napi statisztikák](docs/images/statistics-en.png)

## Saját adatok kezelése

A profil a Windows Dokumentumok mappáján belüli `GameTimeMonitor\data` könyvtárban található. Nincs reklám vagy általános analitikai adatgyűjtés. A helyi előzmény-adatbázis nem titkosított; a választható felhőszinkron statisztikái feltöltés előtt titkosítást kapnak.

Az automatikus verzióellenőrzés legfeljebb naponta egyszer kapcsolódik a GitHubhoz. A GitHub normál kapcsolati adatokat, köztük IP-címet kap; az ellenőrzés nem küld játékidőt, játékadatot vagy gépnevet. Az automatikus ellenőrzés kikapcsolható.

Biztonsági mentéshez lépj ki a figyelőből, majd másold ki a teljes adatmappát. Az eltávolítás megőrzi ezt a mappát. A tárolt adatokról, felhőbeli megőrzésről és törlésről az [adatkezelési leírásban](PRIVACY.md), a fiók és a kapcsolati kód védelméről a [biztonsági leírásban](SECURITY.md) olvashatsz.

## Segítség és fejlesztés

Hibajelzést és funkciójavaslatot a [GitHub Issues](https://github.com/Blintboi/windows-game-time-monitor/issues) oldalon várunk. Kapcsolati kódot, tokent és saját profiladatbázist ne csatolj nyilvánosan; biztonsági problémát a [biztonsági leírás](SECURITY.md) szerinti privát útvonalon jelezz.

A projekt [MIT licencű](LICENSE), az összetevőkre külön [harmadik féltől származó licencek](THIRD-PARTY-NOTICES.md) vonatkoznak. A fejlesztés [GitHub Sponsorson támogatható](https://github.com/sponsors/Blintboi).

Fejlesztőknek: [fejlesztői útmutató](docs/DEVELOPMENT.md), [felépítés](ARCHITECTURE.md), [tesztelés](TESTING.md).
