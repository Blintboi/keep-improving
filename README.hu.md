# Játékidőfigyelő — 1.6.0

Windows 11-en futó, sötét felületű Gaming Hub és játékidőfigyelő egy alkalmazásban. A játékgyűjteményből közvetlenül indíthatod a játékokat, követheted az idődet és megnézheted a napi statisztikákat. A repó és a kiadások egyelőre **privátak**. A másik gépen is hozzáférő GitHub-fiókkal jelentkezz be a letöltéshez.

## Telepítés

Töltsd le a Kiadások / Releases oldalról a `GameTimeMonitor-1.6.0-Setup.exe` fájlt, és indítsd el. A Python, a Tk és az SQLite benne van: semmit nem kell külön telepíteni. A program megnyílik, felismeri a játékokat, és a következő Windows-bejelentkezéskor a tálcán indul. A telepítő jelenleg nincs digitálisan aláírva.

A program helye: `%LOCALAPPDATA%\Programs\GameTimeMonitor`. Az előzmények és beállítások a Windows Dokumentumok mappájában, a `GameTimeMonitor\data` alatt maradnak. A frissítés mentést készít, és megtartja az eddigi keretet, kizárásokat, EXE-szabályokat, rejtett játékokat és Hub-mappát.

Az asztalon egy közös **Gaming Hub** parancsikon marad a megszokott kontrolleres-órás ikonnal. Ez a már futó figyelő játékgyűjteményét nyitja meg. A frissítés a régi, saját monitor- és Hub-parancsikont összevonja, és előtte menti őket.

## Játékok indítása

A **Gaming Hub** az alkalmazás kezdőlapja. Keress játéknevet, vagy szűrj forrásra, válassz ki egy játékot, majd kattints a **Játék indítása** gombra. A soron dupla kattintás vagy Enter is indít. A Steam-, Epic-, Ubisoft- és Riot-játékot a megfelelő kliensen át, Minecraftot a launcherével vagy a meglévő hivatkozásával indítja; az eredeti parancsikon argumentumai megmaradnak. Egyértelmű, önálló EXE közvetlenül is indulhat.

Ha több EXE közül kell választani, az **EXE hozzárendelése** gombbal egyszer jelöld ki a játék tényleges futtatható fájlját. Ezt az indításhoz és a méréshez is megjegyzi. A **Játék hozzáadása** is elmenti a választást. Az indítás előkészítése közben folytatódik az időmérés; a launcher megnyitása önmagában nem fogyasztja a keretet. A mérésből kizárt játékot is indíthatod, az eltávolítottat nem.

Az elrejtés, eltávolítás és időmérési beállítás ugyanebben a gyűjteményben érhető el; a **Statisztikák** a másik fül. A **Játékmappa megnyitása** a kiválasztott játék fájljaihoz vezet. Az asztali ikon és a tálcamenü Gaming Hub pontja mindig a beépített játéklistához tér vissza.

## Magyar vagy angol felület

A felső **Nyelv / Language** listában válassz **Magyar** vagy **English** nyelvet. A főfelület azonnal vált, és megjegyzi a választást. Az új párbeszédablakok, a tálcamenü és a játékidő-emlékeztetők is ezt a nyelvet használják. Egy új telepítés alapból angol.

## Napi játékidő

A **Gaming Hub** oldalon látszik a mai összes játékidő, a hátralévő keret és az aktív játék. Alapból napi 120 perc a keret, és 100 percnél jön az előzetes jelzés. A Beállításokban módosíthatod őket.

Csak az előtérben lévő, figyelt játék ideje számít. A böngésző, a játékkezelő kliens, a háttérben futó játék, az alvás és a zárolt munkamenet nem számít. Játékon belüli átvezetők közben is mér; a billentyűzet tétlensége önmagában nem szüneteltet. Éjfélkor új napi összesítés kezdődik.

A jelzés emlékeztető: nem állítja le és nem zárja ki a játékot. A megfelelő előtérben lévő játéknál előbb egy Esc-et próbál küldeni, majd előre hozza a figyelmeztetést. Minecraft Java teljes képernyőn már sikeresen teszteltük; más játékok kizárólagos fullscreen módja még igényelhet próbát.

Az ablak bezárása és a **Tálcára** gomb mellett tovább fut a mérés. A tálcaikon bal kattintásra megnyitja az ablakot, jobb kattintásra menüt ad. A **Kilépés a figyelőből** állítja le a programot.

## Statisztikák

A **Statisztikák** fülön napi diagram, napi lista és játékonkénti időbontás látható.

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
