# Játékidőfigyelő — 2.5.0

Windows 11-en futó, sötét felületű Gaming Hub és játékidőfigyelő egy alkalmazásban. A játékgyűjteményből közvetlenül indíthatod a játékokat, követheted az idődet és megnézheted a napi statisztikákat. A repó és a kiadások egyelőre **privátak**. A másik gépen is hozzáférő GitHub-fiókkal jelentkezz be a letöltéshez.

A 2.0-s felület Qt-ra váltott: letisztult sötét oldalsáv, átrendeződő játékkártyák, kör alakú napi keretjelző és új statisztikaoldal került bele. A kártyák meglévő helyi Steam-borítóképeket, telepített játékképeket és játékikonokat használnak, képletöltés nélkül. A borítóképek teljes egészükben, az eredeti oldalarányukat megtartva férnek a képmezőbe; a szabad hely sötét marad. A közös kontrolleres-órás alkalmazásikon megmaradt. A kijelölt játék kezelését az alsó **…** menüben találod; a nyelvválasztó az oldalsáv alján van.

A rövidített felületen a mai és hátralévő idő, a játéknevek és a kezelőgombok maradnak előtérben. Az indítógomb a játék neve mellett jelenik meg. Nullás játékidő nem foglal helyet a kártyán; a forrásjelzés az azonos nevű játékokat különbözteti meg. A részletes súgó tooltipben érhető el, a további launcherútvonalakat a **Beállítások → Játékmappa → Haladó** részben találod.

## Telepítés

Töltsd le a Kiadások / Releases oldalról a `GameTimeMonitor-2.5.0-Setup.exe` fájlt, és indítsd el. A Python, a Qt/PySide6 és az SQLite benne van: semmit nem kell külön telepíteni. A program megnyílik, felismeri a játékokat, és a következő Windows-bejelentkezéskor a tálcán indul. A telepítő jelenleg nincs digitálisan aláírva.

A program helye: `%LOCALAPPDATA%\Programs\GameTimeMonitor`. Az előzmények és beállítások a Windows Dokumentumok mappájában, a `GameTimeMonitor\data` alatt maradnak. A frissítés mentést készít, és megtartja az eddigi keretet, kizárásokat, EXE-szabályokat, rejtett játékokat és Hub-mappát.

Az asztalon egy közös **Gaming Hub** parancsikon marad a megszokott kontrolleres-órás ikonnal. Ez a már futó figyelő játékgyűjteményét nyitja meg. A frissítés a régi, saját monitor- és Hub-parancsikont összevonja, és előtte menti őket.

## Játékok indítása

A **Játéktár** a kezdőlap: színes játékcsempék, helyi borítóképek és ikonok, gyorsindítás és rendezés a mai játékidő szerint. Keress játéknevet, vagy szűrj forrásra, válassz ki egy játékot, majd kattints a **Játék indítása** gombra. A kártyán dupla kattintás vagy Enter is indít. A Steam-, Epic-, Ubisoft- és Riot-játékot a megfelelő kliensen át, Minecraftot a launcherével vagy a meglévő hivatkozásával indítja; az eredeti parancsikon argumentumai megmaradnak. Egyértelmű, önálló EXE közvetlenül is indulhat.

Ha több EXE közül kell választani, az **EXE hozzárendelése** gombbal egyszer jelöld ki a játék tényleges futtatható fájlját. Ezt az indításhoz és a méréshez is megjegyzi. A **Hozzáadás** is elmenti a választást. Az indítás előkészítése közben folytatódik az időmérés; a launcher megnyitása önmagában nem fogyasztja a keretet. A mérésből kizárt játékot is indíthatod, az eltávolítottat nem.

Az elrejtés, eltávolítás és időmérési beállítás ugyanebben a gyűjteményben érhető el; a **Statisztikák** külön oldal az oldalsávban. A **Játékmappa megnyitása** a kiválasztott játék fájljaihoz vezet. Az asztali ikon és a tálcamenü Gaming Hub pontja mindig a beépített játéklistához tér vissza.

## Játékkliensek és helyi képek

Az oldalsáv **Játékkliensek** oldalán külön nyitható a telepített **Steam, Epic Games Launcher, Riot Client, Ubisoft Connect és Minecraft Launcher**. Mindegyik saját ikont és **Megnyitás** gombot kap. A keresés a helyi parancsikonokból és telepítési adatokból dolgozik; egy játék indítására szolgáló argumentumokat nem használ fel általános kliensnyitásra. Indítás előtt újra ellenőrzi a program helyét. Egyetlen klienst sem indít el magától. A **Frissítés** újrakeresi a klienseket; a látható oldal körülbelül percenként is frissül.

A kliensek az aktív játékkorlát mellett is megnyithatók, így a könyvtár, telepítés és frissítés elérhető. A kliensben töltött idő nem fogyasztja a játékkeretet. A belőle indított tényleges, figyelt játékra továbbra is érvényes az időmérés és a beállított korlátozás.

Minden játékkártyához háttérben keres helyi képet: az adott játék Steam-gyorsítótárában, a telepítési mappában és annak kép-, splash-, resource- és content-mappáiban. Az önálló játék `steam_appid.txt` fájlját is használhatja a megfelelő helyi Steam-kép azonosítására. Borítót, fejlécet, bannert, splash képet, címlogót vagy ikont keres. Minecraftnál a telepített verzió JAR-jából is beolvashatja az ismert címlogót, kicsomagolás és programfuttatás nélkül.

A keresés korlátozott mélységű és idejű, nem járja be az egész meghajtót, nem követ mappahivatkozásokat, nem olvas launcherfiókokat, és kihagyja a mentéseket, képernyőképeket, modokat és naplókat. A sérült vagy túl nagy képeket átugorja. A saját/titkosított játékcsomagokat nem bontja ki. Ha nincs megfelelő helyi borító, játékikont vagy a tényleges EXE ikonját használja; végső esetben marad a monogram. Nem tölt le és nem talál ki borítókat. Az oldalarány megmarad, a szabad hely sötét marad.

A tálcamenü **Játékok és Hub frissítése** pontja a képkeresést is újraindítja. A játékfájlokat és előzményeket nem módosítja, a képeket nem tölti fel.

## Magyar vagy angol felület

Az oldalsáv alján lévő **Nyelv / Language** listában válassz **Magyar** vagy **English** nyelvet. A főfelület azonnal vált, és megjegyzi a választást. Az új párbeszédablakok, a tálcamenü és a játékidő-emlékeztetők is ezt a nyelvet használják. Egy új telepítés alapból angol.

## Napi játékidő

A **Gaming Hub** oldalon látszik a mai összes játékidő, a hátralévő keret és az aktív játék. Alapból napi 120 perc a keret, és 100 percnél jön az előzetes jelzés. A Beállításokban módosíthatod őket.

Csak az előtérben lévő, figyelt játék ideje számít. A böngésző, a játékkezelő kliens, a háttérben futó játék, az alvás és a zárolt munkamenet nem számít. Játékon belüli átvezetők közben is mér; a billentyűzet tétlensége önmagában nem szüneteltet. Éjfélkor új napi összesítés kezdődik.

A jelzés emlékeztető: nem állítja le és nem zárja ki a játékot. Bekapcsolt felugró jelzésnél a megfelelő előtérben lévő játéknál előbb egy Esc-et próbál küldeni, majd előre hozza a figyelmeztetést. A korábbi Tk-felülettel a Minecraft Java teljes képernyős próbája sikeres volt; az új Qt-felülettel ezt még meg kell ismételni.

Az ablak bezárása és a **Tálcára** gomb mellett tovább fut a mérés. A tálcaikon bal kattintásra megnyitja az ablakot, jobb kattintásra menüt ad. A **Kilépés a figyelőből** állítja le a programot.

## Játék közbeni visszaszámláló

A **Beállítások → Visszaszámláló** részen kapcsolhatod be a **Megjelenítés játék közben** lehetőséget, majd mentsd a beállításokat. Új és korábbi telepítéseken alapból kikapcsolva marad. Csak a hátralévő idő fehér számjegyei látszanak, teljesen átlátszó háttéren, keret, felirat és folyamatjelző nélkül. Az előtérben lévő, figyelt játék közben jelenik meg, és a közös napi keret hátralévő idejét mutatja. Másik alkalmazásra váltáskor vagy zároláskor eltűnik; a Hub tálcára tétele mellett tovább látható. Az egérkattintásokat átengedi, nem kér fókuszt és nem fogja el a billentyűket.

Bekapcsoláskor alapból a korai popup helyett pirosra vált a beállított figyelmeztetési küszöbnél. A szokásos 100/120 perces keretnél ez 20 perc hátralévő időt jelent. Ehhez nem küld Esc-et és nem szól hang. A korai popup külön visszakapcsolható. A **Felugró jelzés lejáratkor** ettől független kapcsoló, alapból bekapcsolva; a később indított, kereten túli játékmenetek jelzését is vezérli. Lejárat után a számláló nullán marad. A popup nem állítja le a játékot.

A helyét a Beállításokban a kicsinyített kijelzőn húzással vagy nyílbillentyűkkel módosíthatod. Választhatsz automatikus vagy konkrét kijelzőt; lecsatlakoztatott kijelzőnél az elsődlegeset használja. Az **Előnézet (10 mp)** mentés nélkül megmutatja az új helyet, időmérés és előzménymódosítás nélkül. Végül nyomd meg a **Mentés** gombot. A **Szöveg fedettsége** csúszka 25–100% között csak a számjegyek áttetszőségét állítja; a környezetük teljesen átlátszó marad. A korábban mentett százalék frissítéskor megmarad, és a szövegre érvényes. Az **Értesítés próbája** gomb itt teszteli a felugró figyelmeztetést.

Az alapértelmezett megjelenítő asztali Windows-overlay; az exkluzív teljes képernyős, emelt jogosultságú vagy védett játék eltakarhatja. A program nem változtatja meg a játék megjelenítési módját. Megjelenítési hibánál, elavult RTSS-visszajelzésnél vagy működő RTSS-kapcsolat nélküli fullscreen/foglalt Windows-állapotnál megtartja a korai popupot. Önmagában a látható, legfelül lévő asztali ablak nem bizonyítja, hogy a játék felett is látszik a számláló.

Exkluzív fullscreenhez külön telepíthető az **RTSS 7.3.7 vagy újabb** a [hivatalos Guru3D-oldalról](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/). Az RTSS-ben először állítsd a **Global profil felismerését None-ra**. A Hub **Beállítások → Visszaszámláló → Játékon belüli számláló (RTSS)…** gombjánál add hozzá a figyelt játék pontos `.exe`-fájlját, és mentsd. Ha már futott a játék, mentés után indítsd újra. A Hub csak a kiválasztott exe-k profilját készíti elő, és szükség esetén elindítja az RTSS-t. A sima időmérés és az asztali számláló RTSS nélkül is működik. Ez az integráció Riot-játékhoz nem kapcsolható be, és új játékokat nem vesz fel automatikusan.

Az RTSS-számláló ugyanazt a napi keretet, fehér/piros számjegyeket, fedettséget és pozíciót használja, háttér és gombok nélkül. Az RTSS saját pozícióvezérlését és a teljes képkockát használja, így a játék belső HUD-területe nem tolja el. Az ugyanabban a játékban használt más RTSS-kliensek kijelzése is együtt mozoghat vele. A játék aktív kijelzőjén jelenik meg; a kijelzőválasztó és a tíz másodperces asztali előnézet az asztali megjelenítőre vonatkozik. Az **RTSS csatlakoztatva** állapot a játék OSD-frissítési visszajelzését jelenti; a tényleges láthatóságot játék közben kell ellenőrizni. Az exe eltávolítása leállítja a Hub szövegét, az RTSS-profilja az RTSS-ben marad szerkeszthető. Az RTSS fájlnév alapján választ profilt, a Hub csak a kiválasztott pontos útvonalnál küld szöveget. A meglévő általános felismerési és teljesítménybeállításokat nem írja át. Az RTSS külön program; a Hub telepítője nem tartalmazza, az eltávolítója nem törli.

## Választható játékkorlát

A **Beállítások → Játék korlátozása** részen kapcsold be a **Korlátozás bekapcsolása** lehetőséget, add meg a napi összesített perceket, majd ments. Új és korábbi telepítésnél alapból kikapcsolva marad, a kezdeti határ **125 perc**. Ez külön állítható a 120 perces emlékeztető kerettől.

A határ elérésekor előbb **10 másodpercet hagy mentésre és szabályos kilépésre**. Ez az első beavatkozásra és a játékba való minden visszatérésre is érvényes; az idő akkor indul, amikor a figyelő a játékot előtérben észleli. Csak utána próbál egy ellenőrzött Esc-et küldeni, majd 200 ms múlva ugyanazt az ablakot minimalizálja és megnyitja a Hubot. Sikertelen minimalizálás után is új, teljes türelmi idő jár. Másik alkalmazásra váltás, zárolás, alvás, óraugrás vagy a figyelő elakadása után újrakezdődik a várakozás. Az előtérben töltött játékidőt eközben is méri. Az Esc-et folyamatonként/naponként egyszer próbálja a futó figyelőben, így nem kapcsolgatja folyton a játék menüjét. A Hubból sem indítható figyelt játék, a már előkészített indítást is újraellenőrzi. Külső launcheres indításnál az előtérbe kerülést követően lép közbe. Az összesített idő újraindítás után is megmarad, helyi éjfélkor új nap kezdődik. A rejtett játékokra is vonatkozik; a mérésből kizártakra nem.

A Hub piros sávja jelzi az aktív korlátot, a **Beállítások** bármikor elérhető: ott módosíthatod vagy kikapcsolhatod. Az esedékes popupok helyett ilyenkor ez a sáv jelenik meg. Ez önkéntes korlátozás: a figyelő bezárásával vagy a beállítás átírásával feloldható. Nem zárja be és nem függeszti fel a játék folyamatát, nem tiltja le a bevitelt és nem zárolja a Windowst. Minimalizáláskor különösen az online játék tovább futhat, ezért ments/lépj ki a meccsből időben. Ismeretlen vagy emelt jogosultságú/védett játéknál kézi lépésre lehet szükség. Másik alkalmazásra váltás, zárolás vagy késleltetés közbeni kikapcsolás esetén nem avatkozik közbe. Ha a minimalizálás nem sikerül, állapotüzenetet ad és csak figyelt játék előtérbe kerülésekor próbálkozik újra.

## Statisztikák

A **Statisztikák** oldalon napi diagram, napi lista és játékonkénti időbontás látható.

- Választhatsz 7 napot, 30 napot, az aktuális hónapot vagy saját kezdő- és zárónapot. A dátum formátuma `ÉÉÉÉ-HH-NN`, egy nézet legfeljebb 366 napot mutat.
- Kattints egy oszlopra vagy dátumsorra az adott nap játékaihoz. A **Teljes időszak** visszaállítja az egész kiválasztott időszak bontását.
- Az összes játékidő, a napi átlag és a legtöbbet játszott játék mellett az egyes játékok százalékos aránya is látszik.
- Az oldal megnyitva körülbelül 10 másodpercenként frissül. A **Frissítés** az addig mért időt is elmenti és beleszámítja.

A már meglévő előzményeket használja, az elrejtett, kizárt és eltávolított játékok korábban rögzített idejével együtt. Rögzített idő nélküli napok nullával jelennek meg. **A napi átlagot legkorábban a telepítés napjától számítja**, a kijelölt időszak máig eltelt napjaiból. A telepítés utáni játékmentes napok számítanak, a telepítés előtti és a jövőbeli napok nem. Alul látszik a kezdőnap és az átlag alapjául szolgáló napok száma. A telepítés dátuma frissítéskor megmarad; régi profilnál az adatbázis létrehozási idejéből és a legelső rögzített játékidőből elérhető korábbi napot használja. A figyelő telepítése előtti vagy korábban fel nem ismert játékidőt nem lehet utólag visszaállítani. A két gép előzményei külön maradnak, nincs felhőszinkron.

## Gaming Hub és játékkezelés

Steam, Epic, Ubisoft Connect, Riot, Minecraft Java és a beállított játékmappában lévő önálló játékok támogatottak. A játékfájlok és mentések nem költöznek. Az új és eltávolított játékok követése automatikus; más, ismeretlen helyen lévő játékot a **Hozzáadás** gombbal vehetsz fel. A régi parancsikonmappa megmarad választható kiegészítőként; a Beállításokban a **Parancsikonok frissítése** jelöléssel vezérelhető. A beépített játéklista és indítás ettől függetlenül működik.

Az **Elrejtés / visszaállítás** csak a főlistát módosítja: a mérés, az előzmény és a Hub-parancsikon megmarad. A **Rejtett játékok mutatása** jelöléssel visszahozhatod a sort. A **Kizárás / mérés** külön szabályozza, számítson-e a játék jövőbeli ideje.

A **Játék eltávolítása…** előbb útmutatót mutat, és csak a Tovább után indítja a megfelelő saját eltávolítót, launchert vagy a Windows Telepített alkalmazások oldalát. Hordozható játéknál szükség esetén megnyitja a mappát a kézi lépésekhez. Nem töröl találomra játékfájlokat, és nem ad csendes törlési kapcsolókat. A kiadó megerősítését ellenőrizd, a helyi mentésekről előtte készíts másolatot.

A sakk új telepítésben rendesen számít; az alapértelmezett kizárása választható személyes beállítás. A korábbi személyes sakkos kivétel frissítéskor megmarad.

## Adatok és eltávolítás

Nincs telemetria vagy automatikus feltöltés. A program helyi telepítési jegyzékeket, folyamatútvonalakat és parancsikonokat olvas. Előzménymentés előtt lépj ki a tálcamenüből, majd másold ki az adatkönyvtárat.

A figyelőt a Windows **Gépház → Alkalmazások → Telepített alkalmazások → Game Time Monitor → Eltávolítás** útvonalon távolíthatod el. Az alkalmazás saját asztali ikonja eltűnik, a játékok, a kiegészítő mappa parancsikonjai és az előzmények megmaradnak. A részletes fejlesztői, hibakeresési és tesztleírás az [angol dokumentációban](README.md) található.

A Qt-változat önálló figyelmeztetése rejtett és minimalizált főablakkal is tesztelt. Az Esc és az előtérbe hozás megmaradt, de a Minecraft teljes képernyős próbáját az új felülettel még érdemes megismételni; a korábbi sikeres próba a Tk-változattal történt.
