# Játékidőfigyelő — 2.2.0

Windows 11-en futó, sötét felületű Gaming Hub és játékidőfigyelő egy alkalmazásban. A játékgyűjteményből közvetlenül indíthatod a játékokat, követheted az idődet és megnézheted a napi statisztikákat. A repó és a kiadások egyelőre **privátak**. A másik gépen is hozzáférő GitHub-fiókkal jelentkezz be a letöltéshez.

A 2.0-s felület Qt-ra váltott: letisztult sötét oldalsáv, átrendeződő játékkártyák, kör alakú napi keretjelző és új statisztikaoldal került bele. A kártyák meglévő helyi Steam-borítóképeket és játékikonokat használnak, képletöltés nélkül. A borítóképek teljes egészükben, az eredeti oldalarányukat megtartva férnek a képmezőbe; a szabad hely sötét marad. A közös kontrolleres-órás alkalmazásikon megmaradt. A kijelölt játék kezelését az alsó **…** menüben találod; a nyelvválasztó az oldalsáv alján van.

## Telepítés

Töltsd le a Kiadások / Releases oldalról a `GameTimeMonitor-2.2.0-Setup.exe` fájlt, és indítsd el. A Python, a Qt/PySide6 és az SQLite benne van: semmit nem kell külön telepíteni. A program megnyílik, felismeri a játékokat, és a következő Windows-bejelentkezéskor a tálcán indul. A telepítő jelenleg nincs digitálisan aláírva.

A program helye: `%LOCALAPPDATA%\Programs\GameTimeMonitor`. Az előzmények és beállítások a Windows Dokumentumok mappájában, a `GameTimeMonitor\data` alatt maradnak. A frissítés mentést készít, és megtartja az eddigi keretet, kizárásokat, EXE-szabályokat, rejtett játékokat és Hub-mappát.

Az asztalon egy közös **Gaming Hub** parancsikon marad a megszokott kontrolleres-órás ikonnal. Ez a már futó figyelő játékgyűjteményét nyitja meg. A frissítés a régi, saját monitor- és Hub-parancsikont összevonja, és előtte menti őket.

## Játékok indítása

A **Játéktár** a kezdőlap: színes játékcsempék, helyi borítóképek és ikonok, gyorsindítás és rendezés a mai játékidő szerint. Keress játéknevet, vagy szűrj forrásra, válassz ki egy játékot, majd kattints a **Játék indítása** gombra. A kártyán dupla kattintás vagy Enter is indít. A Steam-, Epic-, Ubisoft- és Riot-játékot a megfelelő kliensen át, Minecraftot a launcherével vagy a meglévő hivatkozásával indítja; az eredeti parancsikon argumentumai megmaradnak. Egyértelmű, önálló EXE közvetlenül is indulhat.

Ha több EXE közül kell választani, az **EXE hozzárendelése** gombbal egyszer jelöld ki a játék tényleges futtatható fájlját. Ezt az indításhoz és a méréshez is megjegyzi. A **Játék hozzáadása** is elmenti a választást. Az indítás előkészítése közben folytatódik az időmérés; a launcher megnyitása önmagában nem fogyasztja a keretet. A mérésből kizárt játékot is indíthatod, az eltávolítottat nem.

Az elrejtés, eltávolítás és időmérési beállítás ugyanebben a gyűjteményben érhető el; a **Statisztikák** külön oldal az oldalsávban. A **Játékmappa megnyitása** a kiválasztott játék fájljaihoz vezet. Az asztali ikon és a tálcamenü Gaming Hub pontja mindig a beépített játéklistához tér vissza.

## Magyar vagy angol felület

Az oldalsáv alján lévő **Nyelv / Language** listában válassz **Magyar** vagy **English** nyelvet. A főfelület azonnal vált, és megjegyzi a választást. Az új párbeszédablakok, a tálcamenü és a játékidő-emlékeztetők is ezt a nyelvet használják. Egy új telepítés alapból angol.

## Napi játékidő

A **Gaming Hub** oldalon látszik a mai összes játékidő, a hátralévő keret és az aktív játék. Alapból napi 120 perc a keret, és 100 percnél jön az előzetes jelzés. A Beállításokban módosíthatod őket.

Csak az előtérben lévő, figyelt játék ideje számít. A böngésző, a játékkezelő kliens, a háttérben futó játék, az alvás és a zárolt munkamenet nem számít. Játékon belüli átvezetők közben is mér; a billentyűzet tétlensége önmagában nem szüneteltet. Éjfélkor új napi összesítés kezdődik.

A jelzés emlékeztető: nem állítja le és nem zárja ki a játékot. Bekapcsolt felugró jelzésnél a megfelelő előtérben lévő játéknál előbb egy Esc-et próbál küldeni, majd előre hozza a figyelmeztetést. A korábbi Tk-felülettel a Minecraft Java teljes képernyős próbája sikeres volt; az új Qt-felülettel ezt még meg kell ismételni.

Az ablak bezárása és a **Tálcára** gomb mellett tovább fut a mérés. A tálcaikon bal kattintásra megnyitja az ablakot, jobb kattintásra menüt ad. A **Kilépés a figyelőből** állítja le a programot.

## Játék közbeni visszaszámláló

A **Beállítások → Játék közbeni visszaszámláló** részen kapcsolhatod be az áttetsző számlálót, majd mentsd a beállításokat. Új és korábbi telepítéseken alapból kikapcsolva marad. Csak az előtérben lévő, figyelt játék közben jelenik meg, és a közös napi keret hátralévő idejét mutatja. Másik alkalmazásra váltáskor vagy zároláskor eltűnik; a Hub tálcára tétele mellett tovább látható. Az egérkattintásokat átengedi, nem kér fókuszt és nem fogja el a billentyűket.

Bekapcsoláskor alapból a korai popup helyett pirosasra vált a beállított figyelmeztetési küszöbnél. A szokásos 100/120 perces keretnél ez 20 perc hátralévő időt jelent. Ehhez nem küld Esc-et és nem szól hang. A korai popup külön visszakapcsolható. A **Felugró figyelmeztetés a napi keret lejáratakor** ettől független kapcsoló, alapból bekapcsolva; a később indított, kereten túli játékmenetek jelzését is vezérli. Lejárat után a számláló nullán marad. A popup nem állítja le a játékot.

A helyét a Beállításokban a kicsinyített kijelzőn húzással vagy nyílbillentyűkkel módosíthatod. Választhatsz automatikus vagy konkrét kijelzőt; lecsatlakoztatott kijelzőnél az elsődlegeset használja. A háttér fedettsége 25–95% között állítható, a számjegyek jól olvashatók maradnak. Az **Előnézet 10 másodpercig** mentés nélkül megmutatja az új helyet, időmérés és előzménymódosítás nélkül. Végül nyomd meg a **Beállítások mentése** gombot.

Ez asztali Windows-overlay, nem épül bele a játékba. Exkluzív teljes képernyős, emelt jogosultságú vagy védett játék eltakarhatja. Keret nélküli ablakos módban megbízhatóbb; a Minecraftban is külön ellenőrizni kell. Nem váltja át magától a játék megjelenítési módját. Ha nem látszik a játékod felett, kapcsold vissza a korai popupot. Megjelenítési hiba esetén a program visszaáll a korai popupra, de az exkluzív fullscreen miatti takarást nem mindig lehet felismerni.

## Választható játékkorlát

A **Beállítások → Játék korlátozása** részen kapcsold be a **További figyelt játék megakadályozása a napi határ után** lehetőséget, add meg a napi összesített perceket, majd ments. Új és korábbi telepítésnél alapból kikapcsolva marad, a kezdeti határ **125 perc**. Ez külön állítható a 120 perces emlékeztető kerettől.

A határ elérésekor egy ellenőrzött Esc-et próbál küldeni a felismert, előtérben lévő játéknak, 200 ms múlva pedig ugyanazt az ablakot minimalizálja és megnyitja a Hubot. Ha visszatérsz a játékba, újra minimalizálja; a próbák között legalább két másodperc telik el. Az Esc-et folyamatonként/naponként egyszer próbálja a futó figyelőben, így nem kapcsolgatja folyton a játék menüjét. A Hubból sem indítható figyelt játék, a már előkészített indítást is újraellenőrzi. Külső launcheres indításnál az előtérbe kerülést követően lép közbe. Az összesített idő újraindítás után is megmarad, helyi éjfélkor új nap kezdődik. A rejtett játékokra is vonatkozik; a mérésből kizártakra nem.

A Hub piros sávja jelzi az aktív korlátot, a **Beállítások** bármikor elérhető: ott módosíthatod vagy kikapcsolhatod. Az esedékes popupok helyett ilyenkor ez a sáv jelenik meg. Ez önkéntes korlátozás: a figyelő bezárásával vagy a beállítás átírásával feloldható. Nem zárja be és nem függeszti fel a játék folyamatát, nem tiltja le a bevitelt és nem zárolja a Windowst. Minimalizáláskor különösen az online játék tovább futhat, ezért ments/lépj ki a meccsből időben. Ismeretlen vagy emelt jogosultságú/védett játéknál kézi lépésre lehet szükség. Másik alkalmazásra váltás, zárolás vagy késleltetés közbeni kikapcsolás esetén nem avatkozik közbe. Ha a minimalizálás nem sikerül, állapotüzenetet ad és csak figyelt játék előtérbe kerülésekor próbálkozik újra.

## Statisztikák

A **Statisztikák** oldalon napi diagram, napi lista és játékonkénti időbontás látható.

- Választhatsz 7 napot, 30 napot, az aktuális hónapot vagy saját kezdő- és zárónapot. A dátum formátuma `ÉÉÉÉ-HH-NN`, egy nézet legfeljebb 366 napot mutat.
- Kattints egy oszlopra vagy dátumsorra az adott nap játékaihoz. A **Teljes időszak** visszaállítja az egész kiválasztott időszak bontását.
- Az összes játékidő, a napi átlag és a legtöbbet játszott játék mellett az egyes játékok százalékos aránya is látszik.
- Az oldal megnyitva körülbelül 10 másodpercenként frissül. A **Frissítés** az addig mért időt is elmenti és beleszámítja.

A már meglévő előzményeket használja, az elrejtett, kizárt és eltávolított játékok korábban rögzített idejével együtt. Rögzített idő nélküli napok nullával jelennek meg. **A napi átlagot legkorábban a telepítés napjától számítja**, a kijelölt időszak máig eltelt napjaiból. A telepítés utáni játékmentes napok számítanak, a telepítés előtti és a jövőbeli napok nem. Alul látszik a kezdőnap és az átlag alapjául szolgáló napok száma. A telepítés dátuma frissítéskor megmarad; régi profilnál az adatbázis létrehozási idejéből és a legelső rögzített játékidőből elérhető korábbi napot használja. A figyelő telepítése előtti vagy korábban fel nem ismert játékidőt nem lehet utólag visszaállítani. A két gép előzményei külön maradnak, nincs felhőszinkron.

## Gaming Hub és játékkezelés

Steam, Epic, Ubisoft Connect, Riot, Minecraft Java és a beállított játékmappában lévő önálló játékok támogatottak. A játékfájlok és mentések nem költöznek. Az új és eltávolított játékok követése automatikus; más, ismeretlen helyen lévő játékot a **Játék hozzáadása** gombbal vehetsz fel. A régi parancsikonmappa megmarad választható kiegészítőként; a Beállításokban a **Parancsikonmappa karbantartása is** jelöléssel vezérelhető. A beépített játéklista és indítás ettől függetlenül működik.

Az **Elrejtés / visszaállítás** csak a főlistát módosítja: a mérés, az előzmény és a Hub-parancsikon megmarad. A **Rejtett játékok mutatása** jelöléssel visszahozhatod a sort. A **Kizárás / mérés** külön szabályozza, számítson-e a játék jövőbeli ideje.

A **Játék eltávolítása…** előbb útmutatót mutat, és csak a Tovább után indítja a megfelelő saját eltávolítót, launchert vagy a Windows Telepített alkalmazások oldalát. Hordozható játéknál szükség esetén megnyitja a mappát a kézi lépésekhez. Nem töröl találomra játékfájlokat, és nem ad csendes törlési kapcsolókat. A kiadó megerősítését ellenőrizd, a helyi mentésekről előtte készíts másolatot.

A sakk új telepítésben rendesen számít; az alapértelmezett kizárása választható személyes beállítás. A korábbi személyes sakkos kivétel frissítéskor megmarad.

## Adatok és eltávolítás

Nincs telemetria vagy automatikus feltöltés. A program helyi telepítési jegyzékeket, folyamatútvonalakat és parancsikonokat olvas. Előzménymentés előtt lépj ki a tálcamenüből, majd másold ki az adatkönyvtárat.

A figyelőt a Windows **Gépház → Alkalmazások → Telepített alkalmazások → Game Time Monitor → Eltávolítás** útvonalon távolíthatod el. Az alkalmazás saját asztali ikonja eltűnik, a játékok, a kiegészítő mappa parancsikonjai és az előzmények megmaradnak. A részletes fejlesztői, hibakeresési és tesztleírás az [angol dokumentációban](README.md) található.

A Qt-változat önálló figyelmeztetése rejtett és minimalizált főablakkal is tesztelt. Az Esc és az előtérbe hozás megmaradt, de a Minecraft teljes képernyős próbáját az új felülettel még érdemes megismételni; a korábbi sikeres próba a Tk-változattal történt.
