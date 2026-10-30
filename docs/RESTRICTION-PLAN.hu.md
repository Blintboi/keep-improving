# Többlépcsős korlátozások

A 2.35.0-ban beépített működés. A korábbi tervet ez a leírás váltja fel.

## Beállítás

Az Időkeretek oldalon nyiss meg egy keretet, majd a **Figyelmeztetések és korlátozások…** ablakot. Az egyéni lépések bekapcsolása lecseréli az adott keret régi figyelmeztetési és minimalizálási szabályát. Az ablak mentése után az időkeret módosításait is mentsd. A meglévő profiloknál ez nincs automatikusan bekapcsolva.

Legfeljebb húsz lépés állítható: hangos vagy felugró figyelmeztetés, minimalizálás, kitakarás és némítás, illetve bezárás. Figyelmeztetés lejárat előtt, lejáratkor és utána is lehet; korlátozás a lejáratkor vagy utána. A lejárat utáni késleltetés valós időben telik, háttérbe váltáskor is. Több figyelmeztetés egy üzenetbe kerül; korlátozásnál a bezárás, kitakarás, minimalizálás sorrend dönt.

Az egyszeri mentési idő 0–60 egész perc: a nulla kikapcsolja. Csak kitakaráskor kérhető. Több keret esetén mindegyiknek engednie kell, és a legrövidebb idő számít. A jog az érintett keret egészére, a közös napváltásig egyszer jár. Újraindítás, napváltási beállítás módosítása és játékazonosítók összevonása nem frissíti fel a már elhasznált lehetőséget. A keret növelése vagy a terv módosítása megszünteti az addigi hosszabbítást, de aznapra nem ad újat.

## Alkalmazások és játékok

A kitakarófelület átlátszatlan, az érintett ablak helyére kerül. Másik alkalmazásra váltva elrejtőzik; visszatéréskor újra megjelenik. Az **Másik alkalmazás használata** gomb minimalizálja a célablakot. A mentési idő gombja visszaadja az alkalmazást és a hangot, a számláló pedig jelzi a hátralévő időt. A határidő után bezárás következik.

Kizárólagos teljes képernyőn a célablak egyszeri minimalizálása után jelenik meg az interaktív felület. Ez különbözik a fókuszt nem kérő figyelmeztetéstől. A korlátozófelület nem RTSS-be rajzolt gombokat használ. Játékhoz a meglévő asztali/RTSS-számláló mutatja a mentési időt; más alkalmazáshoz külön, fókuszt nem kérő számláló tartozik.

A művelet teljes fájlútvonalhoz, PID-hez és folyamatindítási időhöz kötött. A bezárás előbb normál ablakbezárást kér, legfeljebb öt másodperc múlva az ugyanazon nyitott handle-lel azonosított folyamatot állítja le. Nem zár be teljes folyamatfát. A bezárási és hosszabbítási beállításhoz el kell fogadni a nem mentett munka elvesztését. Rendszerfolyamatok, saját folyamatok, parancsértelmezők, játékindítók és felismert védett játékok nem kaphatják ezeket a műveleteket. Korábbi megjelenítési hozzájárulás nem engedélyez erőltetett leállítást.

A hangkezelő külön rövid életű segédfolyamat, kizárólag Windows Core Audio interfészekkel. Csak az ellenőrzött folyamat saját, normál megosztott hangfolyamait némítja. Az eredetileg néma hangfolyamokhoz nem nyúl. Feloldáskor és a szülőfolyamat kapcsolatának megszűnésekor visszaállítja a saját némításait. Más folyamat által lejátszott, több folyamathoz tartozó vagy kizárólagos hangot nem garantáltan kezel. Nincs rendszerszintű némítás, folyamatfelfüggesztés, DLL-injektálás vagy input-hook. Sikertelen segédindítás után legfeljebb harminc másodpercenként próbálkozik újra.

## Weboldalak

A párosított Chromium-bővítmény a kijelölt domainek érintett lapjait helyi tiltóoldalra irányítja. Webhelyre a minimalizálás is tiltóoldalt jelent; a bezárási lépés csak az érintett lapot zárja be, nem az egész böngészőt. Háttérben lejátszó lap is átirányítható. Privát lapot nem módosít.

Az eredeti teljes URL kizárólag a böngésző átmeneti munkamenet-tárában van. A tiltóoldal címében véletlen token szerepel. A helyi asztali programhoz csak domain és token jut el, hitelesített helyi kéréssel. A mentési idő ugyanazt a lapot nyitja vissza, és csak ahhoz ad ideiglenes engedélyt. Lejáratkor ismét a tiltóoldal jön; külön bezárási lépés továbbra is bezárhatja a lapot. Más fókusztiltás vagy másik aktív keret nem kerülhető meg.

A bővítményt frissítés után újra kell tölteni az új navigációs engedéllyel. Kapcsolathibánál a korlátozások feloldódnak. A funkció nem kijátszhatatlan felügyeleti megoldás.

## Állapot és erőforrások

A tervek és az egyszeri jogosultságok helyiek, nem szinkronizálódnak. A `restriction_state` SQLite-tábla megőrzi az adott napra kiadott értesítéseket, lejáratot és hosszabbítást; a hosszabbítás tranzakciója újra ellenőrzi, hogy azt nem használták-e már el. A meglévő egy másodperces előtérmintavétel indítja a lépéseket. A bezárás háttérszálon vár, nem fagyasztja a felületet. Hangkezelő csak aktív némításkor fut, a böngésző pedig csak aktív tiltáskor ellenőriz sűrűbben.

## Ellenőrzés

A `test_restriction_steps.py` és `test_restriction_steps_ui.py` külön tesztprofilokon vizsgálja az ütemezést, egyszeriséget, átfedő kereteket, újraindítást, napváltást, szerkesztést és bezárásmegszakítást. A Node-tesztek a tényleges böngészőháttérkódot is futtatják Chrome API-próbákkal: visszatérés, laphoz kötött engedély, navigációs versenyhelyzet és későbbi lapbezárás.

A natív próba kizárólag a mellékelt, előzetesen Defenderrel ellenőrzött `FixtureRestriction.exe` tesztfolyamaton vizsgálja a némítást, visszaállítást, szülőkilépést és pontos célbezárást. A teszt nem bizonyít minden játékra, anti-cheat rendszerre és hangmeghajtóra általános kompatibilitást.
