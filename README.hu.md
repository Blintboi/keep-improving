# Játékidőfigyelő — 2.11.0

**[Legfrissebb telepítő letöltése — 2.11.0 · Windows x64](https://github.com/Blintboi/windows-game-time-monitor/raw/refs/heads/main/downloads/GameTimeMonitor-Setup.exe)** · [SHA-256 ellenőrzőösszeg](downloads/GameTimeMonitor-Setup.exe.sha256)

A letöltött telepítőt indítsd el a telepítéshez vagy frissítéshez. A korábbi előzmények, beállítások és kizárások megmaradnak, és frissítés előtt biztonsági mentés készül.

A **2.11.0-ban a lefekvési emlékeztető is a Játékfigyelő része**. A **Beállítások → Lefekvési emlékeztető** alatt külön állítható a figyelmeztetés (alapból **23:55**), a lefekvés (**00:00**) és a reggeli feloldás (**06:00**). Opcionálisan a lefekvéstől a feloldásig **10 másodpercenként minimalizálja az előtérben lévő ablakot**, böngészőnél és más alkalmazásoknál is, Esc küldése nélkül. A Hub és a beállítások elérhetők maradnak. A próbagomb csak a figyelmeztetést mutatja meg. Mindez helyi idő szerint, a tálcán is működik, amíg a Játékfigyelő fut; nem ébreszti a gépet és nem pótolja az elmulasztott figyelmeztetést. Az első minimalizálás előtt 10 másodpercet hagy, feloldáskor automatikusan leáll.

A meglévő külön `BedtimeReminder` saját, 23:55-ös ütemezett feladatát az új program a szokásos profil első indításakor automatikusan átveszi: bekapcsolja az emlékeztetőt, menti a régi feladat XML-jét az adatmappa `backups` könyvtárába, és letiltja azt. A korábbi fájlokat megtartja. Új telepítésen az esti funkció kikapcsolva indul, a minimalizálást mindig külön kell bekapcsolni. Az esti időpontok és a napi játékkeret egymástól függetlenek.

A 2.10.0 GitHub-belépést ad az összekapcsolási kód létrehozásához, cseréjéhez és visszavonásához. További gép továbbra is ugyanazzal a kóddal csatlakozik. A tokeneket és a függő kódcserét Windows-fiókhoz kötött védelem tárolja; a meglévő kapcsolatok és előzmények megmaradnak. A 2.11.0 legfeljebb **100 aktív csoportot** fogad, arányosan megosztott kérés- és forgalmi kerettel, a bejelentkezési adatok és a spam korlátozásával. Ez belépési plafon, nem 100 folyamatosan aktív felhasználó garanciája. A közös ingyenes keret kíméléséhez mindkét gépet frissítsd. Részletek a [biztonsági leírásban](SECURITY.md).

A 2.7.4 kevesebb felesleges háttérmunkát végez: a rejtett vagy minimalizált ablak a játéktárat és a statisztikanézetet visszanyitáskor frissíti, az üres feldolgozási várólistákat ritkábban ellenőrzi, az overlay gyors időzítője pedig csak játék vagy előnézet közben fut. A tálcán tovább működik az időmérés, a figyelmeztetés és a szinkronizálás.

Windows 11-en futó, sötét felületű Gaming Hub és játékidőfigyelő egy alkalmazásban. A játékgyűjteményből közvetlenül indíthatod a játékokat, követheted az idődet és megnézheted a napi statisztikákat. A repó és a telepítő egyelőre **privát**. A másik gépen is hozzáférő GitHub-fiókkal jelentkezz be a letöltéshez.

A 2.0-s felület Qt-ra váltott: letisztult sötét oldalsáv, átrendeződő játékkártyák, kör alakú napi keretjelző és új statisztikaoldal került bele. A kártyák meglévő helyi Steam-borítóképeket, telepített játékképeket és játékikonokat használnak, képletöltés nélkül. A 2.7.3-tól minden játék azonos, nagy, lekerekített négyzetes képkeretet kap a színes háttér előtt. Az ikonok teljes alakja megmarad; a borítókból torzítás nélkül, középre igazított négyzetes kivágás készül. A kis pixelikonok betöltése nem nagyítja és homályosítja előre a forrást. A közös kontrolleres-órás alkalmazásikon megmaradt. A játék kezelését a saját kártyájának alsó részén, a neve mellett lévő **…** menüben találod; a nyelvválasztó az oldalsáv alján van.

A rövidített felületen a mai és hátralévő idő, a játéknevek és a kezelőgombok maradnak előtérben. A játék nagy képére kattintva indíthatsz; a **…** menü a neve mellett van. Nullás játékidő nem foglal helyet a kártyán; a forrásjelzés az azonos nevű játékokat különbözteti meg. A részletes súgó tooltipben érhető el, a további launcherútvonalakat a **Beállítások → Játékmappa → Haladó** részben találod.

## Telepítés

Kattints a README legelején található **Legfrissebb telepítő letöltése** linkre, majd indítsd el a `GameTimeMonitor-Setup.exe` fájlt. A Python, a Qt/PySide6 és az SQLite benne van: semmit nem kell külön telepíteni. A program megnyílik, felismeri a játékokat, és a következő Windows-bejelentkezéskor a tálcán indul. A telepítő jelenleg nincs digitálisan aláírva.

A program helye: `%LOCALAPPDATA%\Programs\GameTimeMonitor`. Az előzmények és beállítások a Windows Dokumentumok mappájában, a `GameTimeMonitor\data` alatt maradnak. A frissítés mentést készít, és megtartja az eddigi keretet, kizárásokat, EXE-szabályokat, rejtett játékokat és Hub-mappát.

Az asztalon egy közös **Gaming Hub** parancsikon marad a megszokott kontrolleres-órás ikonnal. Ez a már futó figyelő játékgyűjteményét nyitja meg. A frissítés a régi, saját monitor- és Hub-parancsikont összevonja, és előtte menti őket.

## Játékok indítása

A 2.7.2-től a háttérben futó játékkeresés megtartja a meglévő kártyákat és képeket, így nem építi újra villogva a teljes rácsot. Változatlan találatoknál megmarad a kijelölés, a billentyűzetfókusz és a görgetési hely. Az új kép csak akkor váltja le a régit, ha már elkészült.

A **Játéktár** a kezdőlap: színes játékcsempék, helyi borítóképek és ikonok, gyorsindítás és rendezés a mai játékidő szerint. Keress játéknevet, vagy szűrj forrásra, majd kattints közvetlenül a játék nagy képére. Egy kattintással indul, előzetes kijelölés és külön alsó kezelősáv nélkül. A névre kattintás kijelöl; a kijelölt játék Enterrel is indítható. A Steam-, Epic-, Ubisoft- és Riot-játékot a megfelelő kliensen át, Minecraftot a launcherével vagy a meglévő hivatkozásával indítja; az eredeti parancsikon argumentumai megmaradnak. Egyértelmű, önálló EXE közvetlenül is indulhat.

Ha több EXE közül kell választani, az **EXE hozzárendelése** gombbal egyszer jelöld ki a játék tényleges futtatható fájlját. Ezt az indításhoz és a méréshez is megjegyzi. A **Hozzáadás** is elmenti a választást. Az indítás előkészítése közben folytatódik az időmérés; a launcher megnyitása önmagában nem fogyasztja a keretet. A mérésből kizárt játékot is indíthatod, az eltávolítottat nem.

Az elrejtés, eltávolítás és időmérési beállítás ugyanebben a gyűjteményben érhető el; a **Statisztikák** külön oldal az oldalsávban. A **Játékmappa megnyitása** a kiválasztott játék fájljaihoz vezet. Az asztali ikon és a tálcamenü Gaming Hub pontja mindig a beépített játéklistához tér vissza.

## Játékkliensek és helyi képek

Az oldalsáv **Játékkliensek** oldalán külön nyitható a telepített **Steam, Epic Games Launcher, Riot Client, Ubisoft Connect és Minecraft Launcher**. Mindegyik saját ikont és **Megnyitás** gombot kap. A keresés a helyi parancsikonokból és telepítési adatokból dolgozik; egy játék indítására szolgáló argumentumokat nem használ fel általános kliensnyitásra. Indítás előtt újra ellenőrzi a program helyét. Egyetlen klienst sem indít el magától. A **Frissítés** újrakeresi a klienseket; a látható oldal körülbelül percenként is frissül.

A kliensek az aktív játékkorlát mellett is megnyithatók, így a könyvtár, telepítés és frissítés elérhető. A kliensben töltött idő nem fogyasztja a játékkeretet. A belőle indított tényleges, figyelt játékra továbbra is érvényes az időmérés és a beállított korlátozás.

Minden játékkártyához háttérben keres helyi képet: az adott játék Steam-gyorsítótárában, a telepítési mappában és annak kép-, splash-, resource- és content-mappáiban. Az önálló játék `steam_appid.txt` fájlját is használhatja a megfelelő helyi Steam-kép azonosítására. Borítót, fejlécet, bannert, splash képet, címlogót vagy ikont keres. Minecraftnál a telepített verzió JAR-jából is beolvashatja az ismert címlogót, kicsomagolás és programfuttatás nélkül.

A keresés korlátozott mélységű és idejű, nem járja be az egész meghajtót, nem követ mappahivatkozásokat, nem olvas launcherfiókokat, és kihagyja a mentéseket, képernyőképeket, modokat és naplókat. A sérült vagy túl nagy képeket átugorja. A saját/titkosított játékcsomagokat nem bontja ki. Ha nincs megfelelő helyi borító, játékikont vagy a tényleges EXE ikonját használja; végső esetben marad a monogram. Nem tölt le és nem talál ki borítókat. A megjelenítés torzítás nélkül, a közös négyzetes képkeretben történik.

A tálcamenü **Játékok és Hub frissítése** pontja a képkeresést is újraindítja. A játékfájlokat és előzményeket nem módosítja, a képeket nem tölti fel.

## Magyar vagy angol felület

Az oldalsáv alján lévő **Nyelv / Language** listában válassz **Magyar** vagy **English** nyelvet. A főfelület azonnal vált, és megjegyzi a választást. Az új párbeszédablakok, a tálcamenü és a játékidő-emlékeztetők is ezt a nyelvet használják. Egy új telepítés alapból angol.

## Napi játékidő

A **Gaming Hub** oldalon látszik a mai összes játékidő, a hátralévő keret és az aktív játék. Alapból napi 120 perc a keret, és 100 percnél jön az előzetes jelzés. A Beállításokban módosíthatod őket.

Csak az előtérben lévő, figyelt játék ideje számít. A böngésző, a játékkezelő kliens, a háttérben futó játék, az alvás és a zárolt munkamenet nem számít. Játékon belüli átvezetők közben is mér; a billentyűzet tétlensége önmagában nem szüneteltet. Éjfélkor új napi összesítés kezdődik.

A jelzés emlékeztető: nem állítja le és nem zárja ki a játékot. Bekapcsolt felugró jelzésnél a megfelelő előtérben lévő játéknál előbb egy Esc-et próbál küldeni, majd előre hozza a figyelmeztetést. A korábbi Tk-felülettel a Minecraft Java teljes képernyős próbája sikeres volt; az új Qt-felülettel ezt még meg kell ismételni.

A jobb felső **X** a tálcára rejti az ablakot, és tovább fut a mérés. A tálcaikon bal kattintásra megnyitja az ablakot, jobb kattintásra menüt ad. A **Kilépés a figyelőből** állítja le a programot.

## Játék közbeni visszaszámláló

A **Beállítások → Visszaszámláló** részen kapcsolhatod be a **Megjelenítés játék közben** lehetőséget, majd mentsd a beállításokat. Új és korábbi telepítéseken alapból kikapcsolva marad. Csak a hátralévő idő fehér számjegyei látszanak, teljesen átlátszó háttéren, keret, felirat és folyamatjelző nélkül. Az előtérben lévő, figyelt játék közben jelenik meg, és a közös napi keret hátralévő idejét mutatja. Másik alkalmazásra váltáskor vagy zároláskor eltűnik; a Hub tálcára tétele mellett tovább látható. Az egérkattintásokat átengedi, nem kér fókuszt és nem fogja el a billentyűket.

Bekapcsoláskor alapból a korai popup helyett pirosra vált a beállított figyelmeztetési küszöbnél. A szokásos 100/120 perces keretnél ez 20 perc hátralévő időt jelent. Ehhez nem küld Esc-et és nem szól hang. A korai popup külön visszakapcsolható. A **Felugró jelzés lejáratkor** ettől független kapcsoló, alapból bekapcsolva; a később indított, kereten túli játékmenetek jelzését is vezérli. Lejárat után a számláló nullán marad. A popup nem állítja le a játékot.

A helyét a Beállításokban a kicsinyített kijelzőn húzással vagy nyílbillentyűkkel módosíthatod. A teljes kijelző területén elhelyezhető, kis szélmargóval; az alsó pozíciót nem korlátozza a Windows tálcája. Választhatsz automatikus vagy konkrét kijelzőt; lecsatlakoztatott kijelzőnél az elsődlegeset használja. Az **Előnézet (10 mp)** mentés nélkül megmutatja az új helyet, időmérés és előzménymódosítás nélkül. Végül nyomd meg a **Mentés** gombot. A **Szöveg fedettsége** csúszka 25–100% között csak a számjegyek áttetszőségét állítja; a környezetük teljesen átlátszó marad. A korábban mentett százalék frissítéskor megmarad, és a szövegre érvényes. Az **Értesítés próbája** gomb itt teszteli a felugró figyelmeztetést.

Az alapértelmezett megjelenítő asztali Windows-overlay; az exkluzív teljes képernyős, emelt jogosultságú vagy védett játék eltakarhatja. A program nem változtatja meg a játék megjelenítési módját. Megjelenítési hibánál, elavult RTSS-visszajelzésnél vagy működő RTSS-kapcsolat nélküli fullscreen/foglalt Windows-állapotnál megtartja a korai popupot. Önmagában a látható, legfelül lévő asztali ablak nem bizonyítja, hogy a játék felett is látszik a számláló.

Exkluzív fullscreenhez külön telepíthető az **RTSS 7.3.7 vagy újabb** a [hivatalos Guru3D-oldalról](https://www.guru3d.com/download/rtss-rivatuner-statistics-server-download/). A 2.8.0-tól a bekapcsolt visszaszámláló automatikusan használja az RTSS-t minden figyelt játéknál, ha telepítve van. Nem kell külön exe-listát megadnod. A Hub a meglévő exe-hozzárendelésekből és képfelderítésből készíti elő a játékprofilokat, szükség esetén elindítja az RTSS-t, majd követi az előtérben lévő játékot. Az újonnan észlelt játék-exe-ket használatkor is előkészíti. A kizárt játékokat, klienseket és más nem figyelt programokat kihagyja. Az RTSS általános felismerési és teljesítménybeállításait megőrzi; a Global felismerés maradhat None értéken. Ha egy játék már futott a profil előkészítése előtt, ments, és egyszer indítsd újra. A **Beállítások → Visszaszámláló → Játékon belüli számláló (RTSS)…** ablakban az automatikus RTSS kikapcsolható az asztali megjelenítő javára.

Az RTSS-számláló ugyanazt a napi keretet, fehér/piros számjegyeket, fedettséget és pozíciót használja, háttér és gombok nélkül. Az RTSS saját pozícióvezérlését és a teljes képkockát használja, így a játék belső HUD-területe nem tolja el. Az ugyanabban a játékban használt más RTSS-kliensek kijelzése is együtt mozoghat vele. A játék aktív kijelzőjén jelenik meg; a kijelzőválasztó és a tíz másodperces asztali előnézet az asztali megjelenítőre vonatkozik. Az **RTSS csatlakoztatva** állapot a játék OSD-frissítési visszajelzését jelenti; a tényleges láthatóságot játék közben kell ellenőrizni. Ha az RTSS nem elérhető vagy nem ad működő visszajelzést, az asztali számláló jelenik meg, és a fullscreenhez tartozó figyelmeztetési védelem megmarad. Egyes védett vagy nem kompatibilis játékok megtagadhatják a játékon belüli overlayt. Az RTSS kikapcsolása leállítja a Hub szövegét, az előkészített profilok az RTSS-ben maradnak szerkeszthetők. Az RTSS fájlnév alapján választ profilt, a Hub csak a figyelt, előtérben lévő játék pontos útvonalánál küld szöveget. Az RTSS külön program; a Hub telepítője nem tartalmazza, az eltávolítója nem törli.

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

A már meglévő előzményeket használja, az elrejtett, kizárt és eltávolított játékok korábban rögzített idejével együtt. Rögzített idő nélküli napok nullával jelennek meg. **A napi átlagot legkorábban a telepítés napjától számítja**, a kijelölt időszak máig eltelt napjaiból. A telepítés utáni játékmentes napok számítanak, a telepítés előtti és a jövőbeli napok nem. Alul látszik a kezdőnap és az átlag alapjául szolgáló napok száma. A telepítés dátuma frissítéskor megmarad; régi profilnál az adatbázis létrehozási idejéből és a legelső rögzített játékidőből elérhető korábbi napot használja. A figyelő telepítése előtti vagy korábban fel nem ismert játékidőt nem lehet utólag visszaállítani.

## Statisztikák összekapcsolása több gépen

A 2.7.2-től a statisztikatáblázat **Gép** oszlopa megmutatja az adatot küldő számítógép nevét. Ugyanaz a játék gépenként külön sorban, külön idővel jelenik meg a teljes időszakban és a napi bontásban is. Az összesítés és a diagram továbbra is a kiválasztott gépek közös idejét mutatja. A **Gépek** listával egyetlen gépre is szűrhetsz; a helyi gépet az „ez a gép” jelzés azonosítja.

A 2.7.1-től az összekapcsolási kód minden ablaknyitáskor rejtett. A **Kód mutatása / Kód elrejtése** gombbal kapcsolhatod a láthatóságát; másik ablakra váltáskor vagy az ablak elrejtésekor automatikusan visszarejti. A **Másolás** gomb rejtett kódnál is működik, és az újonnan generált kód is rejtve marad. A frissítés megtartja a korábbi kódot és az összekapcsolt gépeket.

A **Statisztikák → Gépek összekapcsolása** vagy a Beállítások azonos nevű gombjával kapcsolhatod össze a saját gépeidet. Az első gépen 2.10.0 vagy újabb verzióval hozz létre kódot; meglévő kódhoz a 2.7.0-s vagy újabb kliens is csatlakozhat. Közös mappa nem szükséges.

1. Az első gépen kattints a **Bejelentkezés GitHubbal** gombra, majd térj vissza az alkalmazásba és adj nevet a gépnek.
2. Hagyd bekapcsolva az automatikus szinkronizálást, majd kattints a **Mentés** gombra.
3. Másold ki a kódot, a másik gépen ugyanebbe az ablakba illeszd be, és mentsd el. Meglévő kódhoz nem szükséges újabb bejelentkezés.
4. A **Szinkronizálás** gombbal azonnali frissítést kérhetsz, percenként legfeljebb egyszer, a szerver korlátain belül. Visszaszámlálás védi az ismételt kattintástól. Automatikusan a megnyitott Statisztikák mellett 5 percenként, háttérben 15 percenként frissít; a rejtett ablak nem építi újra emiatt a statisztikákat.

Minden felhasználó saját, véletlenszerű kódot használ. A kód hozzáférést ad a csoporthoz és a titkosítási kulcshoz, ezért tartsd titokban: aki ismeri, olvashatja és meghamisíthatja a csoport statisztikáit. Egy ellenőrzött GitHub-fiók egy aktuális kódot kezel. Az **Új kód** mentése megerősítést kér a korábbi kezelt kód lecseréléséhez: annak szerveroldali másolatai törlődnek, gépei leválnak, a helyi előzmények megmaradnak. A többi gépen is add meg az új kódot. A **Felhős kapcsolat visszavonása** megerősítés után törli a kezelt szervercsoportot. A **Kijelentkezés** a fiókkezelést zárja le ezen a gépen; a kódos szinkronizálás tovább működik.

A **Gépek** listában az összesített előzmény, az aktuális gép vagy egy másik gép külön is megtekinthető. Az átlag a kiválasztott gépek közül a legkorábbi követéskezdethez igazodik. Az ismételt frissítés nem adja hozzá újra ugyanazt az időt. A launcherazonosítók alapján ugyanaz a játék közös sorba kerül; a kézzel felvett és önálló játékok azonos forrás és normalizált név alapján kapcsolódnak össze.

Csak a gép neve, a játéknevek/források és a játékonkénti napi mért idő kerül át, a gépen titkosítva a Supabase-szerverre való feltöltés előtt. A kód és a titkosítási kulcs nem kerül a szerverhez. A napi keret, a korlátozás, a kizárások, a parancsikonok és az EXE-útvonalak gépenként maradnak. Minden gép saját SQLite-adatbázist használ. A szinkronizálás alapból kikapcsolt. Internetkimaradásnál a mérés folytatódik, az utolsó átvett adatok megmaradnak, és a program később újrapróbálja. Kikapcsoláskor a már átvett előzmények helyben továbbra is elérhetők.

A 2.9.0-tól a mentett kódot a Windows DPAPI az aktuális Windows-fiókhoz köti. Másik fiókba átmásolt adatbázisnál ugyanazt a kódot újra meg kell adni. A régi biztonsági mentések még tartalmazhatják a korábban nyíltan tárolt kódot; tartsd őket bizalmasan. A 90 napja nem használt szervermásolatok lejárnak, a helyi előzmények és a korábban átvett statisztikák megmaradnak. Visszacsatlakozáskor a gép újratöltheti saját előzményeit. Kvótatúllépés csak a felhőszinkront késlelteti; az ingyenes háttér nem garantál folyamatos elérhetőséget támadó kérésáradat esetén.

A háttér a Supabase **Free**, ingyenes csomagját használja, annak kapacitási és inaktivitási korlátaival. A program nem vált fizetős csomagra. [A szolgáltató aktuális keretei](https://supabase.com/pricing). Egy kóddal legfeljebb 20 gép kapcsolható össze. A 2.6-os változat frissítése megőrzi az előzményeket, de kikapcsolja a régi mappás szinkront; az internetes összekapcsoláshoz új kódot kell létrehozni.

## Gaming Hub és játékkezelés

Steam, Epic, Ubisoft Connect, Riot, Minecraft Java és a beállított játékmappában lévő önálló játékok támogatottak. A játékfájlok és mentések nem költöznek. Az új és eltávolított játékok követése automatikus; más, ismeretlen helyen lévő játékot a **Hozzáadás** gombbal vehetsz fel. A régi parancsikonmappa megmarad választható kiegészítőként; a Beállításokban a **Parancsikonok frissítése** jelöléssel vezérelhető. A beépített játéklista és indítás ettől függetlenül működik.

Az **Elrejtés / visszaállítás** csak a főlistát módosítja: a mérés, az előzmény és a Hub-parancsikon megmarad. A **Rejtett játékok mutatása** jelöléssel visszahozhatod a sort. A **Kizárás / mérés** külön szabályozza, számítson-e a játék jövőbeli ideje.

A **Játék eltávolítása…** előbb útmutatót mutat, és csak a Tovább után indítja a megfelelő saját eltávolítót, launchert vagy a Windows Telepített alkalmazások oldalát. Hordozható játéknál szükség esetén megnyitja a mappát a kézi lépésekhez. Nem töröl találomra játékfájlokat, és nem ad csendes törlési kapcsolókat. A kiadó megerősítését ellenőrizd, a helyi mentésekről előtte készíts másolatot.

Minden játék azonos szabályok szerint számít. Amit nem szeretnél mérni, a játék kártyájának **… → Kizárás / mérés** menüpontjával vagy egy konkrét EXE kizárásával állíthatod be.

## Adatok és eltávolítás

Nincs általános telemetria. A program helyi telepítési jegyzékeket, folyamatútvonalakat és parancsikonokat olvas. A bekapcsolt statisztikaszinkron titkosított csomagokat továbbít a Supabase-háttérhez. A GitHub-belépés a profilodat és az ellenőrzött e-mail-címedet a Supabase Auth számára is átadja; a szolgáltató hozzáférési és biztonsági naplókat kezelhet. A Supabase-tokeneket a Windows DPAPI védi; a GitHub szolgáltatói tokenjeit a kliens nem őrzi meg. [Adatkezelési tájékoztató](https://jtvdbqwmejrckjejjrdl.supabase.co/functions/v1/statistics-sync/about). A helyi mérés fiók nélkül is működik. Előzménymentés előtt lépj ki a tálcamenüből, majd másold ki az adatkönyvtárat.

A figyelőt a Windows **Gépház → Alkalmazások → Telepített alkalmazások → Game Time Monitor → Eltávolítás** útvonalon távolíthatod el. Az alkalmazás saját asztali ikonja eltűnik, a játékok, a kiegészítő mappa parancsikonjai és az előzmények megmaradnak. A részletes fejlesztői, hibakeresési és tesztleírás az [angol dokumentációban](README.md) található.

A Qt-változat önálló figyelmeztetése rejtett és minimalizált főablakkal is tesztelt. Az Esc és az előtérbe hozás megmaradt, de a Minecraft teljes képernyős próbáját az új felülettel még érdemes megismételni; a korábbi sikeres próba a Tk-változattal történt.
