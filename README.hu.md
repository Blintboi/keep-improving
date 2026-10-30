# Keep Improving — 2.35.0

**[Letöltés Windows x64-re — 2.35.0](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 ellenőrzőösszeg](downloads/GameTimeMonitor-Setup.exe.sha256) · [English](README.md)

A Keep Improving megmutatja, mire megy el a gép előtt töltött időd, és segít saját kereteket beállítani. Játékokat, alkalmazásokat és weboldalakat mér, egyéni vagy közös időkereteket, emlékeztetőket és fókuszidőzítőt kínál. Ingyenes, nyílt forráskódú, magyar és angol felülettel.

![Tevékenységek a 2.35.0-s verzióban](docs/images/library-en.png)
*A jelenlegi felület a fejlesztő valódi játéktárával. A játékok képei a tulajdonosaikhoz tartoznak.*

## Első lépések

1. **Windows 11 x64** rendszeren futtasd a fenti telepítőt. Normál telepítéshez nem kell Python vagy rendszergazdai jogosultság.
2. Nyisd meg a **Keep Improving** alkalmazást. A nyelvet az oldalsáv alján választhatod ki.
3. Nézd át a játékokat és tevékenységeket. A hiányzó játékot a futtatható fájljával adhatod hozzá.
4. Az **Időkeretek → Új hozzáadása** alatt válassz játékot, alkalmazást, weboldalt vagy közös keretet használó csoportot. Új profilnál nincs kötelező alapkeret.
5. A weboldalak méréséhez és tiltásához [csatlakoztasd a böngészőbővítményt](#böngészőbővítmény).

Minden oldalnak saját beállításgombja van. A **nap kezdete** univerzális: a statisztika és a napi keretek együtt váltanak napot, alapból éjfélkor. Ha 01:00-t állítasz be, az előtte végzett tevékenység még az előző naphoz tartozik. A korábbi napi összesítések pontos időbélyegek hiányában nem oszthatók újra visszamenőleg.

A főablak bezárása után a program a tálcán fut tovább; teljes leállításhoz válaszd a kilépést a tálcaikon menüjében. A frissítés megőrzi a profilodat. A program a Windowszal együtt indul.

A telepítő jelenleg **nincs digitálisan aláírva**. Az aláírás későbbre maradt; nincs aktív SignPath-tanúsítvány. Részletek a [Windows-bizalmi útmutatóban](docs/WINDOWS-TRUST.hu.md). Jelzett fájl telepítéséhez ne kapcsold ki a vírusvédelmet.

## Időkeretek: te döntöd el, mi történjen

Nyiss meg egy keretet, majd a **Figyelmeztetések és korlátozások…** gombot. Kapcsold be az egyéni lépéseket, add meg a műveleteket, végül mentsd az időkeret módosításait is.

| Művelet | Alkalmazás és játék | Weboldal |
| --- | --- | --- |
| Figyelmeztetés | Hang, felugró értesítés vagy mindkettő | Hang, felugró értesítés vagy mindkettő |
| Minimalizálás | Az érintett ablak minimalizálása | Tiltóoldal megjelenítése |
| Kitakarás és némítás / weboldal tiltása | Átlátszatlan korlátozási felület, a célalkalmazás némításával | Átirányítás a helyi tiltóoldalra |
| Alkalmazás / böngészőlap bezárása | Bezárási kérés, majd legfeljebb öt másodperc után kényszerített leállítás | Csak az érintett lapok bezárása |

A figyelmeztetés a keret lejárta előtt, akkor vagy utána is jöhet. Korlátozás a lejáratkor vagy utána indulhat. Több lépést kombinálhatsz: például két perccel előtte figyelmeztetés, lejáratkor kitakarás, öt perccel később bezárás. A figyelmeztetés önmagában nem tilt semmit. Egyidejű korlátozásnál a bezárás, majd a kitakarás, végül a minimalizálás az erősebb.

Az **egyszeri mentési idő** kikapcsolható, vagy **1–60 percre** állítható. A kitakarófelületen keretenként és naponta egyszer kérheted. Ekkor az alkalmazás és a hangja visszatér, a számláló mutatja a hátralévő időt, utána az alkalmazás bezárul. Weboldalnál csak az eredeti lap kap hosszabbítást, majd visszatér a tiltás. Több érintett keretnek is engednie kell ezt; a legrövidebb hosszabbítás érvényes. A program újraindítása nem ad újabb lehetőséget.

A bezárás miatt elveszhet a nem mentett munka, ezért a bezárás és a mentési idő engedélyezéséhez jelölőnégyzet tartozik. Rendszerfolyamatokra, játékindítókra és felismert védett játékokra az új kitakarás és bezárás nem alkalmazható. Kizárólagos teljes képernyőn az interaktív felülethez egyszeri minimalizálás lehet szükséges. A némítás az ellenőrzött folyamat normál Windows-hangfolyamaira vonatkozik, nem a rendszer vagy más folyamatok hangjára. [Részletes működés](docs/RESTRICTION-PLAN.hu.md).

A meglévő keretek működése megmarad, amíg be nem kapcsolod az egyéni lépéseket. A játékkeretek, heti beosztás és lefekvési korlát továbbra is használható. A program személyes időkezelő, nem kijátszhatatlan szülői felügyelet.

![A közös játékkeret jelenlegi szerkesztője](docs/images/bedtime-en.png)

## Értesítések és számlálók

Az **Értesítések** oldalon együtt látod a beépített emlékeztetőket és a saját üzeneteidet. Egyéni címet, szöveget, ikont, időpontot és napokat adhatsz meg. Az asztali értesítések bezárhatók és mozgathatók. A normál emlékeztető és számláló nem veszi el a billentyűzet fókuszát a játéktól.

A számláló megjelenése és helye célonként állítható. Támogatott teljes képernyős játékokhoz a külön telepíthető **RTSS 7.3.7 vagy újabb** használható; ahol lehet, asztali megjelenítés működik. A kompatibilitás a játéktól és a megjelenítési módtól is függ. Védett játékokhoz külön, kifejezett hozzájárulási beállítások tartoznak: [anti-cheat útmutató](docs/ANTICHEAT.hu.md).

## Mi számít bele az időbe?

Csak az előtérben lévő tevékenységet méri. Az olvasás, játékmenü és szünet is számít, akkor is, ha nem mozgatod az egeret. A háttérben hagyott alkalmazás, zárolás és alvás nem számít; a játékindító nem játékidő. A Windows Intéző és rendszerhéj képernyői inaktívnak számítanak, a korábbi alkalmazásstatisztikákból is eltűnnek.

A párosított bővítmény felismeri a nyilvános webhelyek domainjét és a Brave új lapját. A felismert Brave-kezdőlap inaktív. Más, azonosítatlan böngészőidő megmarad: a régi összesített adatokból nem választható külön biztosan a kezdőlap és az olyan oldal, amelynek domainje nem jutott el a programhoz. A weboldalidő a böngészőidő része, nem számítódik hozzá még egyszer.

Privát lapok domainjét, oldalcímeket és oldaltartalmat nem rögzít. Az alkalmazások és webhelyek mérése kikapcsolható. Egy alkalmazás kizárása elrejti a korábbi adatait és leállítja az új mérést; a játékok mérése és kizárása ettől külön működik.

## Böngészőbővítmény

Brave, Chrome és Edge esetén:

1. Fusson a program; nyisd meg a **Fókuszmód → Böngésző csatlakoztatása** ablakot.
2. A böngészőben nyisd meg a `brave://extensions`, `chrome://extensions` vagy `edge://extensions` oldalt, és kapcsold be a **Fejlesztői módot**.
3. A **Kicsomagolt bővítmény betöltése** gombbal válaszd ki a program által mutatott `browser_extension` mappát.
4. A bővítmény beállításaiban illeszd be az alkalmazásból kimásolt párosítási kódot, válaszd ki a böngészőt, és csatlakozz.
5. Ismételd meg minden használt böngészőben és profilban. A párosítási kód maradjon titkos.

Régebbi verzió frissítése után **töltsd újra a bővítményt**, hogy az új tiltóoldal és navigációs jogosultság is működjön. A kapcsolat helyi. A visszatéréshez szükséges eredeti URL átmenetileg a böngésző munkamenetében marad; nem kerül az asztali programhoz vagy a statisztikai szolgáltatáshoz. A bővítmény kikapcsolása leállítja a webmérést és webtiltást. Kapcsolathibánál a böngészős korlátozás megszűnik.

## Fókusz és statisztikák

A **Fókuszmód** állítható munka- és szünetidőt kínál. Munka alatt a kiválasztott webhelyeket tiltja, az előtérbe kerülő kijelölt alkalmazásokat minimalizálja. Szüneteltetés, leállítás és pihenő feloldja ezt. Az egyszeri mentési idő nem ír felül külön aktív fókusztiltást.

A **Statisztikák** napok és gépek szerint mutatja a játék-, alkalmazás- és webhelyidőt, a böngészés kétszeres számolása nélkül. Opcionálisan összekapcsolhatod saját gépeid előzményeit és támogatott beállításait. Az első gépen a gépek és szinkronizálás ablakában GitHub-belépéssel hozhatsz létre kapcsolatot, a többi gépen annak kódját használhatod. A kód hozzáférést ad a közös adatokhoz, ezért tartsd titokban.

Az adatok feltöltés előtt a gépen titkosítódnak. A keretek fogyasztása helyi; az új korlátozási lépések és mentési hosszabbítások is helyben maradnak. A szinkronizálási kérések között legalább tíz perc telik el; a korlát UTC-naponként 20, havonta 600 sikeres kérés. Helyben internet nélkül is mér.

![Ténylegesen mért játékstatisztikák](docs/images/statistics-en.png)
*Valós, helyben mért játékelőzmények, engedéllyel közzétéve; 2026-10-30-i felvétel. Az időadatok nem generáltak.*

![A jelenlegi fókuszidőzítő](docs/images/focus-en.png)

## Adatok és segítség

A profil a `Documents\GameTimeMonitor\data` mappában van. Biztonsági másoláshoz lépj ki a programból, és másold a teljes mappát. Az eltávolítás megőrzi. A helyi előzmények nincsenek titkosítva. Nincs reklám vagy általános analitikai követés: [adatvédelem](PRIVACY.md), [biztonság](SECURITY.md).

A frissítésellenőrzés legfeljebb naponta egyszer kapcsolódik a GitHubhoz, és kikapcsolható. A frissítés böngészővel töltődik le; te döntöd el, mikor telepíted. Az elsődleges letöltés a README tetején található.

Hibát a [GitHub Issues](https://github.com/Blintboi/keep-improving/issues) oldalon jelezhetsz, kapcsolati kód, token és profiladatbázis nélkül. További információ: [MIT-licenc](LICENSE), [külső összetevők](THIRD-PARTY-NOTICES.md), [fejlesztés](docs/DEVELOPMENT.md), [felépítés](ARCHITECTURE.md), [tesztelés](TESTING.md).
