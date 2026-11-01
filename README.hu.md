# Keep Improving — 2.39.21

**[Letöltés Windows x64-re — 2.39.21](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 ellenőrzőösszeg](downloads/GameTimeMonitor-Setup.exe.sha256) · [English](README.md)

Lásd, mire megy el a gép előtt töltött időd, szabj határt a használatnak, és iktass be szüneteket. A Keep Improving játékokat, alkalmazásokat és weboldalakat mér, egyéni vagy közös időkeretekkel, emlékeztetőkkel és fókuszidőzítővel. Ingyenes, nyílt forráskódú, magyar és angol felülettel.

![Tevékenységek: játékok, alkalmazások és weboldalak a Keep Improving 2.39.21-ben](docs/images/library-hu.png)
*Minden képernyőkép a 2.39.21-es verzióból, külön bemutatóprofillal készült. Az időadatok és keretek szemléltető példák. A játékok képei a tulajdonosaikhoz tartoznak.*

## Első lépések

1. **Windows 11 x64** rendszeren futtasd a fenti telepítőt. Normál telepítéshez nem kell Python vagy rendszergazdai jogosultság.
2. A **Tevékenységek** oldalon nézd át a játékokat, alkalmazásokat és weboldalakat. A hiányzó játékot a futtatható fájljával adhatod hozzá. Nyelvet az oldalsáv alján választhatsz.
3. Az **Időkeretek → Új hozzáadása** alatt válaszd ki, mire vonatkozzon a keret. Játékok, alkalmazások és weboldalak közös csoportba is kerülhetnek.
4. Add meg az érvényes napokat, a megújulási időt és a napi keretet, majd a kívánt műveleteket. Új profilnál nincs kötelező alapkeret.
5. Weboldalak méréséhez és korlátozásához [csatlakoztasd a böngészőbővítményt](#böngészőbővítmény).

Az ablak bezárása után a program a tálcán fut tovább. Teljes leállításhoz válaszd a kilépést a tálcaikon menüjében. A program a Windowszal együtt indul, a frissítés pedig megőrzi a profilodat.

A telepítő jelenleg **nincs digitálisan aláírva**. Részletek a [Windows-bizalmi útmutatóban](docs/WINDOWS-TRUST.hu.md); jelzett fájl telepítéséhez ne kapcsold ki a vírusvédelmet.

## Állítsd össze a saját időkereteidet

Minden keretnek saját **napválasztója**, **napi megújulási időpontja** és opcionális **perces kerete** van. Eltérő hétvégi beállításhoz hozz létre másik keretet a megfelelő napokkal. A szerkesztő jelzi az átfedéseket; minden érvényes korlátozás számít.

A művelet történhet **megadott percnyi használat után** vagy **napi óraidőpontban**. Például 06:00-s megújulással és 22:00-s korlátozással ebben az időablakban engedheted a használatot. A perces keret kikapcsolható, ha az időablak önmagában elég. A bekapcsolt **0 perces keret azonnal tilt**, külön korlátozó művelet nélkül.

![Időkeret-szerkesztő napválasztóval, megújulási idővel és megőrzött piszkozattal](docs/images/budget-editor-hu.png)

A félbehagyott módosítások helyi **piszkozatként megmaradnak**, elnavigálás és újraindítás után is. A **Módosítások mentése** érvényesíti, a **Piszkozat elvetése** megerősítés után törli őket. Az általános beállításokra ez nem vonatkozik. Egy keret törlése és mentése nem törli a mért előzményeket.

A **Művelet hozzáadása** gombbal válaszd ki, mi történjen. Vegyes keretnél egy műveleten belül külön állíthatod be az alkalmazások/játékok és a weboldalak működését. Csak a keretben szereplő típusok beállításai jelennek meg.

| Művelet | Alkalmazás és játék | Weboldal |
| --- | --- | --- |
| Figyelmeztetés | Hang, felugró értesítés vagy mindkettő | Hang, felugró értesítés vagy mindkettő |
| Szünet | Minimalizálás, kitakarás és némítás vagy bezárás a szünet idejére | Takarófelület, átirányítás vagy a lap bezárása |
| Korlátozás | Azonnali bezárás vagy egyszer kérhető mentési idő, utána automatikus bezárás | Takarófelület, átirányítás vagy a lap bezárása |

A használathoz kötött **szünet ismétlődik** újabb ugyanennyi használat után, amíg van idő a keretben. Valós időben telik, akkor is, ha közben mást használsz. A már futó szünet újraindítás és napi megújulás után is megmarad. Weboldal átirányításához megadhatsz HTTP- vagy HTTPS-címet; üresen hagyva új lap nyílik. A szünet után az eredeti oldal ismét megnyitható, ha más aktív korlát nem tiltja.

Alkalmazásbezárásnál az **egyszeri mentési idő 0–60 perc** lehet. A 0 azonnali bezárást jelent. Egyébként kérheted a megadott időt, vagy rögtön bezárhatod az alkalmazást; mentés közben újra használható, az idő lejártakor pedig automatikusan bezárul. Weboldalnál a hosszabbítás az eredeti lapra vonatkozik. Újraindítással nem kérhető újra. Több korlátozásnak is engednie kell a mentési időt, és a legrövidebb érvényesül. Egyidejű korlátozás és szünet esetén a korlátozás az erősebb; a szünet is engedi a jóváhagyott mentési időt.

Bezáráskor elveszhet a nem mentett munka, ezért ehhez külön tudomásulvétel tartozik a szerkesztőben. A rendszerfolyamatok, játékindítók és felismert védett játékok kivételeket képeznek; a teljes képernyős működés és némítás az alkalmazástól is függ. A régebben mentett műveletek viselkedése átállításig megmarad. [Részletes működés](docs/RESTRICTION-PLAN.hu.md). A program személyes időkezelő, nem kijátszhatatlan szülői felügyelet.

<details>
<summary>Példák: külön keretek, vegyes szünet és mentési idő</summary>

![Külön hétköznapi, hétvégi, nulla perces és géphasználati keretek](docs/images/budgets-hu.png)
*Egy helyen az egyéni és közös keretek, külön hétvégi beállítással is.*

![Ismétlődő szünet: a játék kitakarása és némítása, a weboldalak átirányítása új lapra](docs/images/break-hu.png)
*30 perc használat után: a játék kitakarása és némítása, a weboldalak átirányítása, öt perc szünet.*

![Korlátozás három perc alkalmazásmentési idővel és azonnali weboldaltiltással](docs/images/restriction-hu.png)
*60 perc után: az alkalmazásban egyszer három perc kérhető a mentéshez; a weboldalak rögtön tiltva lesznek.*

</details>

Külön **géphasználati időszakokat** is hozzáadhatsz. Válaszd ki a napokat, a kezdő és záró időt, majd adj hozzá figyelmeztetést vagy ablakminimalizálást. Például egy 22:00–06:00 közötti korlátozó időszak 21:55-kor emlékeztethet, éjszaka pedig minimalizálhatja az aktív ablakot. Több, eltérő nevű és napokon érvényes időszak is lehet.

<details>
<summary>Példa géphasználati időszakra</summary>

![Géphasználati időszak napválasztóval, külön figyelmeztetéssel és korlátozással](docs/images/computer-period-hu.png)

</details>

## Számlálók és értesítések

A számláló **a következő eseményig hátralévő időt** mutatja nagyban, alatta a teljes napi keret maradékát. Egy órás keretnél, 30 percenkénti szünettel először a szünetig számol vissza. A futó szünet a tálcaikon fölött és a keretnévvel felsorolt időzítők menüjében is követhető, új lapra átirányítás után is.

A **Számláló beállításai…** alatt megadható a láthatóság, hely, méret és szín. A csoport alapbeállítása mellett minden tag külön beállítható. Játékokhoz a külön telepített **RTSS 7.3.7 vagy újabb** is használható, ahol támogatott. Az **Értesítések** oldalon kikapcsolható a **Részletes RTSS-számláló**: ekkor játék közben csak a következő eseményig tartó idő látszik. Az asztali és tálcás részletek megmaradnak. [Anti-cheat és kompatibilitási útmutató](docs/ANTICHEAT.hu.md).

Az **Értesítések** oldalon saját szövegű, ikonú, időpontú és napokon ismétlődő üzeneteket is létrehozhatsz. A korlátozás **nem kapcsol be automatikus lejárati figyelmeztetést**: ehhez adj hozzá külön **Figyelmeztetés** műveletet. A mentési idő kérésére szolgáló ablak a beállítása szerint jelenik meg.

## Áttekintés: mire ment el az idő?

Szűrj tevékenységtípusra, időszakra és gépre, válassz napot a részletekhez, keress a listában, vagy vond össze az azonos nevű tételeket. Az **Áttekintés megjegyzi a választásaidat** ezen a gépen, a szűrőket és az összevonás jelölőnégyzetét is. A relatív időszakok mindig az aktuális naphoz igazodnak.

![Áttekintés napi időadatokkal, szűrőkkel és az azonos nevűek összevonásával](docs/images/statistics-hu.png)
*Szemléltető hétnapos előzmény a bemutatóprofilból.*

Csak az előtérben lévő tevékenységet méri. Az olvasás és a játékmenü bevitel nélkül is számít; a háttérben hagyott alkalmazás, zárolás és alvás nem. A Windows Intéző és rendszerhéj inaktív. A weboldalidő a böngészőidő része, így egyszer számít bele. A bővítmény a Brave felismert új lapját inaktívnak tekinti; más, azonosítatlan böngészőidő megmaradhat az összesítésben.

Privát lapok domainjét, oldalcímeket és oldaltartalmat nem rögzít. Az alkalmazások és webhelyek mérése kikapcsolható. Egy alkalmazás kizárása elrejti a korábbi adatait és leállítja az új mérést; a játékok kizárása ettől külön működik. A **nap kezdete** a statisztika napváltását és a keretek alapértelmezett megújulását adja meg, amit keretenként felülírhatsz. Módosításkor a már felhasznált idő megmarad; a régi napi összesítések pontos időbélyegek nélkül nem oszthatók újra visszamenőleg.

## Böngészőbővítmény

Brave, Chrome és Edge esetén:

1. Fusson a program; nyisd meg a **Tevékenységek → Weboldalak → Böngésző csatlakoztatása** ablakot.
2. Nyisd meg a `brave://extensions`, `chrome://extensions` vagy `edge://extensions` oldalt, és kapcsold be a **Fejlesztői módot**.
3. A **Kicsomagolt bővítmény betöltése** gombbal válaszd ki a program által mutatott `browser_extension` mappát.
4. A bővítmény beállításaiba illeszd be az alkalmazás párosítási kódját, válaszd ki a böngészőt, és csatlakozz.
5. Ismételd meg minden használt böngészőben és profilban. A párosítási kód maradjon titkos.

Frissítés után **töltsd újra a bővítményt**, hogy az új működés és jogosultságok is életbe lépjenek. A kapcsolat helyi. A tiltóoldalról visszatéréshez szükséges eredeti URL átmenetileg a böngésző munkamenetében marad, nem kerül az asztali statisztikába. A bővítmény kikapcsolása leállítja a webmérést és webtiltást; kapcsolathibánál a böngészős korlátozás megszűnik.

## Fókusz és összekapcsolt gépek

A **Fókusz mód** állítható munkaidőt, rövid és hosszú szüneteket kínál. Munka közben tiltja a kiválasztott webhelyeket, és minimalizálja az előtérbe kerülő kijelölt alkalmazásokat. Szüneteltetés, leállítás és pihenő feloldja ezeket a fókuszkorlátozásokat. Egy időkeret mentési ideje nem ír felül külön aktív fókusztiltást.

<details>
<summary>Fókuszidőzítő és weboldallista</summary>

![Fókuszidőzítő beállítható weboldal-tiltólistával](docs/images/focus-hu.png)
*Példalista a böngésző csatlakoztatása előtt; a weboldaltiltáshoz csatlakoztatni kell a bővítményt.*

</details>

Saját gépeidet az **Áttekintés → Gépek és szinkron** alatt kapcsolhatod össze. Az első gépen lépj be GitHubbal, a többin használd az ott kapott kapcsolati kódot. A kód hozzáférést ad a közös adatokhoz, ezért tartsd titokban. Az előzmények és támogatott beállítások feltöltés előtt a gépen titkosítódnak.

A közös játékkeret és a játékonkénti keretek a szinkronizált játékidőt is számolják; az egységes elszámoláshoz frissíts minden kapcsolt gépet. A többi tevékenység kerete, a korlátozási lépések és mentési hosszabbítások helyiek maradnak. A kérések között legalább tíz perc telik el; a korlát UTC-naponként 20, havonta 600 sikeres kérés. A távoli előzmény késhet vagy internet nélkül hiányozhat; a helyi mérés internet nélkül is folytatódik.

## Adatok, frissítés és segítség

A profil a `Documents\GameTimeMonitor\data` mappában van. Biztonsági másolathoz lépj ki a programból, és másold a teljes mappát. Az eltávolítás megőrzi. A helyi előzmények nincsenek titkosítva. Nincs reklám vagy általános analitikai követés: [adatvédelem](PRIVACY.md), [biztonság](SECURITY.md).

A frissítésellenőrzés legfeljebb naponta egyszer kapcsolódik a GitHubhoz, és kikapcsolható. Te döntöd el, mikor töltesz le és telepítesz. Az elsődleges letöltés a README tetején található közvetlen telepítőlink.

Hibát a [GitHub Issues](https://github.com/Blintboi/keep-improving/issues) oldalon jelezhetsz, kódok, tokenek és profiladatbázis nélkül. További információ: [MIT-licenc](LICENSE), [külső összetevők](THIRD-PARTY-NOTICES.md), [fejlesztés](docs/DEVELOPMENT.md), [felépítés](ARCHITECTURE.md), [tesztelés](TESTING.md).
