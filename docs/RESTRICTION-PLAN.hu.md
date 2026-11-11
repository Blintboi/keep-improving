# Többlépcsős korlátozások

A jelenlegi működés leírása.

Az időkeretek félbehagyott módosításai helyi piszkozatként automatikusan megmaradnak, visszalépés és újraindítás után is. A **Módosítások mentése** érvényesíti őket; a **Piszkozat elvetése** külön, megerősíthető művelet. Az általános beállításokra ez nem vonatkozik.

Minden keret egy beállításcsomagot és a saját érvényes napjait tartalmazza. Eltérő hétvégi értékekhez külön időkeret hozható létre, géphasználati időszakból is lehet több. A korábbi, naponként eltérő beállítások külön keretként jelennek meg a szerkesztőben; a mentésig a korábban mentett szabályok érvényesek. Közös tevékenységekre, átfedő időszakokra vonatkozó kereteknél figyelmeztetés jelenik meg; a mentést ez nem tiltja, és minden érintett korlátozás számít.

A keret neve alatt minden kiválasztott tag látható, szükség esetén több sorban. A korlátozási művelet alkalmazás- és weboldalrésze közvetlenül mutatja a beállításokat. Korábban kifejezetten kikapcsolt típus továbbra sem kapcsolódik be automatikusan.

## Beállítás

Az Időkeretek oldalon nyiss meg egy keretet, majd a **Figyelmeztetések és korlátozások** részen a **Művelet hozzáadása** gombbal adj hozzá lépést, és válaszd ki a típusát. A kockák automatikusan időrendbe kerülnek; az azonos időpontú lépések egyszerre lépnek életbe. Az új lépések mellett a meglévő figyelmeztetési és minimalizálási szabályok is érvényben maradnak, amíg el nem távolítod őket. A korábbi verzióban mentett egyéni tervek megtartják eredeti működésüket. A géphasználati időszak külön keretben állítható.

Legfeljebb húsz lépés állítható: hangos vagy felugró figyelmeztetés, korlátozás és ismétlődő szünet. Alkalmazásoknál egyféle új korlátozás választható, a korábban mentett különféle lépések működése változatlan marad. Az új lépések a megadott percnyi tényleges használat után indulnak, akár a napi keret lejárta előtt is. A korábbi, lejárathoz viszonyított lépések időzítése megmarad; azokat a lépésen külön lehet használati időre váltani.

A **Szünet** lépésnél a használati időt, a korlátozás módját és a szünet hosszát választod ki. A **Kitakarás és némítás / weboldal átirányítása** a keret alkalmazásait és játékait kitakarja és némítja, az érintett weboldalakat pedig a megadott http vagy https címre irányítja át; üres címnél a böngésző új lapja jelenik meg. A szünet lejártakor a kitakarás és a szünet miatti némítás megszűnik, az eredeti weboldal ismét megnyitható, ha más korlátozás nem aktív. Az átirányítás nem írja felül a céloldalra vonatkozó másik korlátozást. A szünet valós időben telik; a végén újabb ugyanennyi használat után indul a következő, amíg van idő a napi keretben. A keret lejáratakor vagy utána már nem indul új szünet. Újraindítás és napváltás nem szakítja meg. A bezárást választó szünetnél az alkalmazásokhoz és játékokhoz egyszeri mentési idő is beállítható. A többi szünetmód önmagában nem ad mentési időt; egyidejű korlátozás esetén viszont a korlátozás mentési ideje kérhető.

Az egyszeri mentési idő a korlátozásnál, a korábbi bezárási lépésnél és a bezárást választó szünetnél is megadható. A mentési idő 0–60 egész perc: a nulla kikapcsolja. Vegyes keret műveleteinél a két típus külön értéket is kaphat; a kérés továbbra is keretenként egyszer használható fel a következő megújulásig. A kért mentési idő végén az alkalmazás akkor is bezárul, ha közben a szünet lejárt; utána újra elindítható, ha más korlátozás nincs. Több érintett korlátozás esetén mindegyiknek engednie kell, és a legrövidebb idő számít. Ha szünet is aktív, a korlátozás az erősebb: a szünet tovább telik, de nem akadályozza a mentési időt. A jog keretenként, a saját napváltásig egyszer jár. A folyamat azonosítójához kötött, már kért mentési idő a megújuláson is átnyúlhat; a lejárat utáni bezárás a megkezdett mentésre vonatkozik.

A műveletkártyák csak a keret kiválasztott tagjaihoz tartozó típusokat mutatják. Vegyes keretnél az **Alkalmazások és játékok** és a **Weboldalak** külön rész: saját hangos/felugró figyelmeztetés, szünetmód és szünethossz, valamint korlátozás és mentési idő adható meg. A használati küszöb közös. Figyelmeztetésnél és szünetnél egy típus jelölését kikapcsolva az adott művelet arra a típusra nem vonatkozik. A weboldalaknál takarófelület, átirányítás vagy lapbezárás választható; alkalmazásoknál az új korlátozás továbbra is bezárás. A meg nem változtatott régi beállítások eredeti viselkedése megmarad.

## Alkalmazások és játékok

Minden keret új műveletválasztójában egyetlen **Korlátozás** szerepel. Alkalmazásnál **0** perc mentési idő esetén azonnal a bezárás indul; pozitív értéknél a mentési idő kérhető. Az egyszer már felhasznált mentési idő után az újra megnyitott alkalmazás is bezárul. Weboldalnál a korlátozás a takarófelületet jeleníti meg. A korábban mentett lépések automatikusan nem válnak erősebb, bezárást végző műveletté.

A kitakarófelület átlátszatlan, az érintett ablak helyére kerül. Másik alkalmazásra váltva elrejtőzik; visszatéréskor újra megjelenik. Az **Másik alkalmazás használata** gomb minimalizálja a célablakot. A mentési idő gombja visszaadja az alkalmazást és a hangot, a számláló pedig jelzi a hátralévő időt. A határidő után bezárás következik.

Kizárólagos teljes képernyőn a célablak egyszeri minimalizálása után jelenik meg az interaktív felület. Ez különbözik a fókuszt nem kérő figyelmeztetéstől. A korlátozófelület nem RTSS-be rajzolt gombokat használ. Játékhoz a meglévő asztali/RTSS-számláló mutatja a mentési időt; más alkalmazáshoz külön, fókuszt nem kérő számláló tartozik.

A művelet teljes fájlútvonalhoz, PID-hez és folyamatindítási időhöz kötött. A bezárás előbb normál ablakbezárást kér, legfeljebb öt másodperc múlva az ugyanazon nyitott handle-lel azonosított folyamatot állítja le. Nem zár be teljes folyamatfát. A bezárási és hosszabbítási beállításhoz el kell fogadni a nem mentett munka elvesztését. Rendszerfolyamatok, saját folyamatok, parancsértelmezők, játékindítók és felismert védett játékok nem kaphatják ezeket a műveleteket. Korábbi megjelenítési hozzájárulás nem engedélyez erőltetett leállítást.

A hangkezelő külön rövid életű segédfolyamat, kizárólag Windows Core Audio interfészekkel. Csak az ellenőrzött folyamat saját, normál megosztott hangfolyamait némítja. Az eredetileg néma hangfolyamokhoz nem nyúl. Feloldáskor és a szülőfolyamat kapcsolatának megszűnésekor visszaállítja a saját némításait. Más folyamat által lejátszott, több folyamathoz tartozó vagy kizárólagos hangot nem garantáltan kezel. Nincs rendszerszintű némítás, folyamatfelfüggesztés, DLL-injektálás vagy input-hook. Sikertelen segédindítás után legfeljebb harminc másodpercenként próbálkozik újra.

## Weboldalak

A párosított Chromium-bővítmény a kijelölt domainek érintett lapjait helyi tiltóoldalra irányítja. Webhelyre a minimalizálás is tiltóoldalt jelent; a bezárási lépés csak az érintett lapot zárja be, nem az egész böngészőt. Háttérben lejátszó lap is átirányítható. Privát lapot nem módosít.

Az eredeti teljes URL kizárólag a böngésző átmeneti munkamenet-tárában van. A tiltóoldal címében véletlen token szerepel. A helyi asztali programhoz csak domain és token jut el, hitelesített helyi kéréssel. A mentési idő ugyanazt a lapot nyitja vissza, és csak ahhoz ad ideiglenes engedélyt. Lejáratkor ismét a tiltóoldal jön; külön bezárási lépés továbbra is bezárhatja a lapot. Más fókusztiltás vagy másik aktív keret nem kerülhető meg.

A régi, memóriában maradt bővítmény a helyi tiltóprotokollon keresztül is megkapja az aktív tiltást. A tiltóoldal és a csatlakoztatási oldal ellenőrzi a helyben telepített bővítményverziót, és eltéréskor egyszer újratölti a bővítményt; a párosítás megmarad. Kapcsolathibánál a korlátozások feloldódnak. A funkció nem kijátszhatatatlan felügyeleti megoldás.

## Napi időablak és érvényes napok

Minden keretnél külön kijelölhető, mely hétköznapokon érvényes. A kijelölt nap a keret saját napi megújulásakor kezdődik; például a hétfői 06:00-s nap kedden 06:00-ig tart. A ki nem jelölt napokon a keret nem figyelmeztet és nem korlátoz. A használati előzmények rögzítése folytatódik.

A művelet **Mikor történjen?** mezőjében az összegyűlt használat helyett **Megadott napi időpontban** is választható. Korlátozásnál a keret a megújulástól a megadott óráig használható, utána a következő megújulásig korlátozott. A megújulásnál korábbi záróóra a következő naptári napra esik. Azonos kezdő- és záróóra azonnali korlátozást jelent.

A **Napi keret (perc)** kikapcsolható: ilyenkor csak a beállított műveletek érvényesek, nincs elfogyó perces keret. Bekapcsolva a 0 perc továbbra is külön művelet nélküli tiltás. A napi időpontra állított figyelmeztetés naponta egyszer jelez; az ilyen szünet a megadott időponttól számított szünethosszig tart. A használathoz kötött szünet továbbra is ismétlődik.

## Számláló és tálca

A számláló a következő beállított eseményig hátralévő időt mutatja nagyban, alatta kisebb betűvel a napi keretből megmaradó időt. Például az órás keretben félóránként előírt szünet előtt **Szünetig 00:30:00**, alatta **Napi keretből: 01:00:00** jelenik meg. A szünet után a következő korlátozásig számol. Egyidejű eseményeknél a korlátozás elsőbbséget élvez; a kért mentési idő a saját visszaszámlálását kapja. Kikapcsolt perces keretnél nincs kitalált napi összeg.

Szünet alatt a lebegő számláló elrejtőzik. A tálcaikonon az aktuális tevékenység legközelebbi eseménye, a napi hátralévő idő és a legközelebb lejáró szünet látszik. Ha nincs aktuális keret, a futó szünet kerül előre. Így egy új lapra átirányítás után is követhető a szünet. A jobb gombos menü a futó időzítőket keretnévvel sorolja fel; a sorra kattintva az adott keret nyílik meg.

A korlátozás nem ad hozzá automatikus figyelmeztetést. Az egyéni keret elfogyása önmagában nem nyit értesítést, és műveletlistás játékkeretnél sem fut le mellé a régi lejárati vagy újraindítási értesítés. A külön beállított figyelmeztetés és a mentési idő kérésére szolgáló korlátozófelület továbbra is működik.

## Állapot és erőforrások

A **Beállítások → Emlékeztetők** alatt a **Részletes RTSS-számláló** kikapcsolható. Ekkor az RTSS-számlálón csak a következő eseményig hátralévő idő látszik; az esemény neve és a kisebb napi keret sor elmarad. Az asztali számláló és a tálca továbbra is részletes marad. A választás újraindítás után is megmarad.

A tervek és az egyszeri jogosultságok helyiek, nem szinkronizálódnak. A `restriction_state` SQLite-tábla megőrzi az adott napra kiadott értesítéseket, lejáratot és hosszabbítást; a hosszabbítás tranzakciója újra ellenőrzi, hogy azt nem használták-e már el. A meglévő egy másodperces előtérmintavétel indítja a lépéseket. A bezárás háttérszálon vár, nem fagyasztja a felületet. Hangkezelő csak aktív némításkor fut, a böngésző pedig csak aktív tiltáskor ellenőriz sűrűbben.

## Ellenőrzés

A 0 perces weboldalkeret tiltását az eredeti böngészőprotokollban is elküldjük. Így a korábban betöltött, az új műveletlistát még nem ismerő bővítmény is letiltja a már megnyitott oldalt. Ehhez nem kell műveletet hozzáadni vagy a bővítményt újratölteni. A kikapcsolt fókuszlistákat ez nem aktiválja.

A 0 perces napi keret külön művelet nélkül tiltja a hozzáférést: az alkalmazásokat és játékokat kitakarja és némítja, a weboldalakon takarófelületet jelenít meg. Nem indít automatikus bezárást, szünetet vagy mentési ráhagyást. Egy korábban kért ráhagyást a nullára állítás megszüntet. A tiltás megmarad újraindítás és napi megújulás után is, amíg az adott napra 0 perc jut; pozitív keretre váltás vagy kikapcsolás feloldja ezt a tiltást. Az eredeti műveletek megmaradnak, pozitív keretnél ismét a beállításuk szerint működnek.

A `test_restriction_steps.py` és `test_restriction_steps_ui.py` külön tesztprofilokon vizsgálja az ütemezést, egyszeriséget, átfedő kereteket, újraindítást, napváltást, szerkesztést és bezárásmegszakítást. A Node-tesztek a tényleges böngészőháttérkódot is futtatják Chrome API-próbákkal: visszatérés, laphoz kötött engedély, navigációs versenyhelyzet és későbbi lapbezárás.

A natív próba kizárólag a mellékelt, előzetesen Defenderrel ellenőrzött `FixtureRestriction.exe` tesztfolyamaton vizsgálja a némítást, visszaállítást, szülőkilépést és pontos célbezárást. A teszt nem bizonyít minden játékra, anti-cheat rendszerre és hangmeghajtóra általános kompatibilitást.
