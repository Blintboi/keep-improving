# Játékidőfigyelő — 2.12.0

**[Letöltés Windows x64-re — 2.12.0](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 ellenőrzőösszeg](downloads/GameTimeMonitor-Setup.exe.sha256) · [English](README.md)

Windows 11-es Gaming Hub, amely méri az előtérben töltött játékidőt, mutatja a napi keretet, és emlékeztet a befejezésre. Beállítható lefekvési emlékeztetőt is tartalmaz.

Elsősorban a saját mindennapi használatomra készítettem, és megosztom azokkal, akiknek szintén hasznos lehet. A helyi funkciók internet és fiók nélkül működnek. A saját számítógépeid statisztikáinak összekapcsolása választható.

![Játéktár és napi játékidőkeret](docs/images/library-en.png)
*Angol felület valódi játékokkal és helyi játékborítókkal. A játékidők bemutatóadatok; a játékok képei a megfelelő jogtulajdonosokhoz tartoznak.*

## Funkciók

- **Előtérben töltött játékidő mérése.** Csak a figyelt, aktív játék idejét számolja. A böngészők, játékkliensek, háttérben futó játékok, az alvás és a zárolt munkamenet nem fogyasztják a napi keretet.
- **Napi keret és emlékeztetők.** A figyelt játékok közös helyi keretet használnak. Külön állítható a korai figyelmeztetés és a lejárat; az új nap helyi éjfélkor kezdődik.
- **Gaming Hub.** Telepített játékok keresése és indítása, szűrés, kártyák elrejtése, EXE-hozzárendelés és játékonkénti kizárás a mérésből. A képeket és ikonokat helyi fájlokból használja.
- **Játék közbeni visszaszámláló.** Választható átlátszó számláló, beállítható kijelzővel, pozícióval és fedettséggel. Asztali megjelenítővel és külön telepített RTSS-sel is működik.
- **Játékkorlát.** Külön napi küszöbhöz kapcsolható minimalizálás, amely minden játékba visszatéréskor tíz másodpercet hagy mentésre és kilépésre.
- **Lefekvési emlékeztető.** Külön figyelmeztetési, lefekvési és reggeli feloldási idő. Lefekvéstől opcionálisan tíz másodpercenként minimalizálja az aktív ablakot, böngészőnél és más alkalmazásnál is, Esc küldése nélkül.
- **Statisztikák és gépek összekapcsolása.** Napi diagramok, időszakos és játékonkénti összesítések, választható titkosított szinkronizálással és gépenkénti szűréssel.
- **Magyar és angol felület.** A nyelv az oldalsávban váltható.

## Támogatott platformok és játékok

| Platform vagy forrás | Támogatás |
| --- | --- |
| Windows 11 x64 | Támogatott asztali rendszer; a szokásos telepítéshez és használathoz nem kell rendszergazdai jogosultság. |
| Steam | Automatikus felismerés a helyi telepítési adatokból, több játékkönyvtárral is. |
| Epic Games Launcher | Telepített játékok automatikus felismerése a helyi jegyzékekből. |
| Ubisoft Connect | Telepített játékok felismerése és kliensen keresztüli indítása. |
| Riot Client | Telepített játékok felismerése és indítása; a Riot Client és a Vanguard ideje nem számít játékidőnek. |
| Minecraft: Java Edition | Felismerés a hivatalos Java-adatkönyvtárból és a hozzá tartozó külön futtatókörnyezet azonosítása. |
| Önálló és egyéb játékok | Felismerés a beállított játékmappában, illetve kézi EXE-hozzárendelés. |
| RTSS 7.3.7+ | Választható játékon belüli számláló; az [RTSS külön tölthető le](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/). |

macOS-re, Linuxra és Windows ARM64-re nincs támogatott kiadás. Minecraft Bedrockhoz és Xbox/Microsoft Store-játékokhoz nincs külön automatikus felismerés. A kézi méréshez hozzáférhető játék-EXE szükséges. Emelt jogosultságú, védett vagy csalásvédelemmel ellátott játékok korlátozhatják az előtér felismerését, a számlálót vagy a minimalizálást; a kompatibilitás játékonként eltérhet.

## Telepítés és frissítés

1. Töltsd le a **GameTimeMonitor-Setup.exe** fájlt a lap tetején található linkről.
2. Indítsd el a telepítőt. A Python, a Qt és a szükséges futtatókönyvtárak benne vannak.
3. Nyisd meg a **Gaming Hubot** az asztali vagy a tálcaikonról. A következő Windows-bejelentkezéseknél a tálcán indul.

A frissítés megőrzi az előzményeket, beállításokat, rejtett játékokat és kizárásokat, és előtte profilmentést készít. A telepítő jelenleg **nincs digitálisan aláírva**, ezért a Windows kiadói vagy megbízhatósági figyelmeztetést mutathat.

A főablak **X** gombja a tálcára rejti a programot; a mérés és az emlékeztetők tovább működnek. A leállításhoz válaszd a tálcamenü **Kilépés a figyelőből** pontját.

## Időkeretek beállítása

Nyisd meg a **Beállításokat**, módosítsd az értékeket, majd válaszd a **Mentés** gombot.

| Beállítás | Kezdőérték |
| --- | --- |
| Napi játékidőkeret | 120 perc |
| Korai figyelmeztetés | 100 perc után |
| Választható játékkorlát küszöbe | 125 perc |
| Lefekvési figyelmeztetés / lefekvés / reggeli feloldás | 23:55 / 00:00 / 06:00 |

Új profilon a visszaszámláló, a játékkorlát, a lefekvési emlékeztető és a felhőszinkron külön bekapcsolásig inaktív. A napi játékkeret és a lefekvési ütemezés egymástól független. Az esti funkció a helyi órát használja, amíg a figyelő fut; nem ébreszti a gépet, és nem pótolja az elmulasztott figyelmeztetést.

![A lefekvési emlékeztető beállításai](docs/images/bedtime-en.png)

A minimalizált játék tovább futhat, különösen online játék esetén. A Hub elérhető marad, így a korlátozás módosítható vagy kikapcsolható. Ez személyes emlékeztető eszköz, nem megkerülhetetlen szülői felügyelet.

## Statisztikák és választható szinkronizálás

A **Statisztikák** oldalon napi játékidő, időszakos összesítés, valamint játékonkénti és gépenkénti bontás látható.

![Napi statisztikák és játékidő-előzmények](docs/images/statistics-en.png)

A saját gépeid összekapcsolása:

1. Az első gépen nyisd meg a **Statisztikák → Gépek összekapcsolása** ablakot, jelentkezz be GitHubbal, kapcsold be a szinkronizálást, és ments.
2. Másold ki a létrehozott kapcsolati kódot. A másik gépen illeszd be ugyanebbe az ablakba, és ments. Meglévő kódhoz csatlakozáshoz nem kell újabb GitHub-belépés.

Induláskor egyszer, követett játék kezdésekor és játék után automatikusan frissít; a közeli váltásokat egy nyugodt perc után összevonja. Nincs időszakos háttérszinkron. A **Szinkronizálás** gombbal kézzel is frissíthetsz. Gépenként legalább tíz perc telik el két kérés között; a függőben lévő játékesemény kivárja ezt. Az összekapcsolt gépek közös szerverkerete UTC-naponként 20, havonta 600 sikeres kérés; a tulajdonos kerete kódcsere után is megmarad. Az újraindítás nem nullázza a várakozást. A felhőszinkronhoz mindegyik gépen legalább 2.12.0 szükséges; a meglévő kód és titkosított előzmények továbbra is használhatók. A napi keretek és kizárások helyben maradnak. A legutóbbi játékidő átviteléhez a gépnek a függő feltöltés befejezéséig bekapcsolva és online kell maradnia.

**A kapcsolati kódot tartsd titokban:** hozzáférést ad az összekapcsolt csoport titkosított előzményeihez. A közös háttérszolgáltatás regisztrációs és használati korlátokkal működik, folyamatos elérhetőségre vállalás nélkül. Szinkronkimaradáskor a helyi mérés tovább működik.

## Saját adatok

Az előzmények és beállítások a Windows Dokumentumok mappájában, a `GameTimeMonitor\data` alatt maradnak. A fiók nélküli helyi méréshez nem tartozik analitika vagy általános telemetria. A választható szinkronizálás a gépen titkosítja a játékidőadatokat és gépneveket a feltöltés előtt; a GitHub-belépés a felhős kapcsolat kezelésére szolgál.

Mentéshez lépj ki a tálcamenüből, majd másold ki az adatmappát. Az eltávolítás megőrzi az előzményeket. Az online funkciók adatairól és törlési lehetőségeiről az [adatkezelési leírás](PRIVACY.md) tájékoztat.

## Projekt és támogatás

Személyes projekt, amelyet a szabadidőmhöz igazodva tartok karban. Mások is szabadon használhatják, jelezhetnek reprodukálható hibákat és javasolhatnak fejlesztéseket a [GitHub Issues](https://github.com/Blintboi/windows-game-time-monitor/issues) felületén. Hibajelzéshez add meg az alkalmazás és a Windows verzióját, a játék forrását és a reprodukálás lépéseit. Kapcsolati kódot, tokent vagy személyes adatbázist ne tölts fel nyilvánosan.

Ha hasznosnak találod a Game Time Monitort, [GitHub Sponsorson keresztül támogathatod a fejlesztését](https://github.com/sponsors/Blintboi). A támogatás teljesen önkéntes; az alkalmazás továbbra is ingyenes és nyílt forráskódú.

A projekt saját forráskódja és dokumentációja [MIT licencű](LICENSE). A képeken látható játékborítók és a csomagolt függőségek jogai, illetve licencei megmaradnak; részletek a [külső összetevők leírásában](THIRD-PARTY-NOTICES.md).

A forrásból történő futtatáshoz és csomagoláshoz lásd a [fejlesztői útmutatót](docs/DEVELOPMENT.md). További műszaki leírás: [felépítés](ARCHITECTURE.md), [tesztelés](TESTING.md), [biztonság](SECURITY.md).
