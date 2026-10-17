# Tesztelés

A tesztek ideiglenes mappákban és külön adatbázisban futnak. Nem módosítanak valódi
játékfájlokat vagy a lefekvési emlékeztetőt. A Steam/Epic telepítési jegyzékek
**szimulált tesztadatok**; nem állítjuk, hogy valódi Steam-/Epic-telepítést vagy
valódi kontrollerhardvert teszteltünk.

A Ubisoft-tesztek elkülönített registryadatokat és ideiglenes könyvtárakat
használnak; valódi Ubisoft-játékot sem telepítenek vagy indítanak.
A Riot-tesztek is szintetikus telepítési adatokat használnak; Riot-játékot
nem telepítenek és nem indítanak.

## Automatizált tesztek

A `test_notifications.py` a valódi küszöbkezelésből indít értesítést minimalizált
és tálcára rejtett főablaknál, valamint szintetikus, keret nélküli, teljes képernyős
topmost tesztablak fölött. Ellenőrzi az elutasított fókuszkérést, a sikertelen
megjelenítés újrapróbálását és az Esc utáni 200 ms sorrendet. A SendInput hívás
ezekben helyettesített: nincs billentyűküldés a felhasználó játékába a tesztekből.
A `test_minecraft.py` ellenőrzi az új runtime-útvonalakat, az általános Java és
a launcher kizárását, az adatmegőrző átvezetést és az előtér/háttér elszámolást.
A hubtesztek két külön adatbázis ugyanarra a Games mappára irányított szinkronját
is ellenőrzik: a második tulajdonos visszautasítást kap, másolatok létrehozása nélkül.

A csomag gyökérmappájában:

```powershell
py -3 -B -m unittest discover -s tests -v
```

A kritikus logika rendszerfüggetlen; a `test_windows.py` natív tesztjei Windows alatt
futnak. Fő területek: modern és régebbi VDF, több könyvtár/meghajtó, Epic `.item`
és launcherindex, áthelyezés/eltávolítás, induláskor egyeztetés, Games almappák,
segédprogramok, első indítás és telepítési versenyhelyzet, késői besorolás és
visszamenőleges elszámolás, Alt+Tab, háttér, két játék közös kerete, beviteltől
független mérés, alvás/óraugrás, zárolás, mentés/újraindítás, éjfél, 100/120 perces
küszöb, új folyamatra ismételt értesítés, sakk, kivételek és beállítások.

A natív tesztek valódi `ReadDirectoryChangesW` értesítéseket és futó háttérfigyelőt
használnak új Games-, Steam- és Epic-tesztadatok hozzáadásakor. Ellenőrzik a
folyamat teljes útvonalának és létrehozási idejének kiolvasását és az egypéldányos futást.

A `test_ubisoft.py` külön ellenőrzi a helyi indexből történő felismerést,
az egyéni telepítési helyeket, az első indítás tartalék felismerését, az
áthelyezést/eltávolítást, a kliens kizárását és a kézi rekord adatvesztés
nélküli átvezetését Ubisoft-azonosítóra. Egy natív teszt egyedi HKCU-tesztkulcsban
valódi `RegNotifyChangeKeyValue` értesítésekkel ellenőrzi a futás közbeni
telepítést, áthelyezést és törlést; a tesztkulcsot utána eltávolítja.

A `test_riot.py` 18 tesztje a YAML/JSON/registry forrásokat, az egyéni helyeket,
a később telepített új termékazonosítókat, a preview-jegyzék kihagyását, a
félkész index megőrzését, a Riot/League kliens és Vanguard kizárását, az első
indításkor mért idő összevonását és a kézi rekord adatmegőrző átvezetését ellenőrzi.
Két natív teszt valódi fájlrendszer- és registryértesítésekkel követi a telepítési
adatok változásait, újraindítás nélkül, ideiglenes mappákban és saját HKCU-kulcsban.

A `test_hub.py` külön ellenőrzi a termékazonosítós Steam/Epic/Ubisoft/Riot-indítókat,
az eredeti indítási paraméterek megőrzését, az egyéb és a sakkjátékokat, a
névütközést, az idegen és kézzel átírt fájlok megtartását, a saját ikonok mentését,
a gyökérváltást, a félreérthető EXE-k mappahivatkozását és a könyvtárkapcsolatok
elutasítását. A két natív próba valódi Windows-parancsikont olvas vissza, illetve
futó Tk-alkalmazással követi egy új szimulált Steam-telepítés és egy kézi játék
hubba kerülését, újraindítás nélkül. Az asztali fájlokat ezek a próbák nem törlik.
Ugyanez a natív próba a Steam-jegyzék törlését, egy kézi EXE eltávolítását
megmaradó mentésmappa mellett, az EXE visszatelepítését, valamint egy Epic-mappa
közvetlen törlését és újralétrehozását is ellenőrzi. A hubikonok kövessék a változást,
a korábbi játékidő maradjon meg.

A `test_tray.py` saját Windows-ablakokkal és valódi tálcaikonnal ellenőrzi a
modern és tartalék kattintási eseményeket, a saját ikon betöltését, a natív menü
elvetését, az X gomb utáni újbóli megnyitást és a külön kilépési parancsot.
Nem küld általános billentyű- vagy egéreseményeket más alkalmazásoknak.
Egy külön alfolyamatos regressziós próba a Windows `PostMessageW` hívásával
küldi a saját rejtett ablaknak az eseményeket, miközben a valódi Tk `mainloop`
fut. Ellenőrzi a látható, rejtett és minimalizált ablak megnyitását, a gyorsan
ismételt és billentyűzetes aktiválást, a hover eseményeket, a natív menü
elvetését és a külön kilépési parancsot. Az 1.3.1 korábbi tesztjei közvetlenül
hívták a Python-kezelőt, ezért a natív eseményhurokból eredő összeomlást nem
fedték fel. A regressziós próba nem fizikai egérkattintás a Windows tálcáján.

Telepítési integrációs próba (külön ideiglenes telepítés és egyedi Run-érték):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\install_smoke.ps1 -ReportPath .\test-reports\install.json
```

Telepítés, ismételt telepítés, adatok/kivételek megőrzése, háttérindítás,
futás közbeni ellenőrzés és eltávolítás. A saját ideiglenes automatikusindítás-
bejegyzését a teszt eltávolítja. Az adatmegőrzés ellenőrzéséhez az ideiglenes
adatmappát meghagyja; helye a JSON-jelentésben található. A kezdeti felismerés
a gép meglévő launcherjegyzékeit olvashatja, de játékot nem telepít és nem módosít.

Vizuális próba külön tesztadatokkal:

```powershell
py -3 -B tests\gui_smoke.py --ui-only --report .\test-reports\gui.json
```

Ez tényleges sötét Tk-ablakokat, beállításokat, figyelmeztetéseket és tálcaikont
hoz létre, ellenőrzi a topmost tulajdonságot, a háttérbe rejtett főablak melletti
popupot és a nyugtázó gombot. A saját tesztablakairól PNG-ket ment. A próbaablakok
automatikusan bezárulnak. A szintetikus tesztprogram fordításához a Windows .NET
Framework C# fordítója szükséges; a játékfigyelő működéséhez nem kell fordító.

Valódi előtéri folyamatot mérő, önmagát bezáró szintetikus játékablakokkal futó próba:

```powershell
py -3 -B tests\gui_smoke.py --report .\test-reports\foreground.json
```

Ennél ne válts más alkalmazásra a körülbelül 15 másodperces próba alatt.
A Windows fókuszátadási korlátozásai miatt automatizálási környezetből
az aktiválás visszautasítható; ilyenkor a teszt sikertelenséget jelent, nem
minősíti sikeresnek az előtéri mérés próbáját. Ez a próba is szintetikus alkalmazást
használ, nem tényleges játékot.

## Kézi ellenőrzési lista

| Eset | Lépés és elvárt eredmény |
| --- | --- |
| Steam / több könyvtár | Telepíts egy játékot a normál és egy másik meghajtón lévő könyvtárba. Rövid időn belül jelenjenek meg a listában, a Steam kezelőfelülete ne fogyasszon időt. |
| Epic / több meghajtó | Telepíts játékot egy másik meghajtóra. A listában az `.item` szerinti hely és név jelenjen meg. A Launcher kezelőfelülete ne számítson. |
| Ubisoft Connect | Telepíts egy játékot Connectből, akár egyéni meghajtóra. Újraindítás nélkül jelenjen meg Ubisoft forrással, és az első előtéri indítástól mérjen. A Connect és a UplayWebCore ne fogyasszon időt. Áthelyezés/eltávolítás után frissüljön a lista. |
| Riot | Telepíts egy Riot-játékot egyéni meghajtóra. Újraindítás nélkül Riot forrással jelenjen meg. A VALORANT vagy a League tényleges játékfolyamata mérjen, a Riot Client, LeagueClient és Vanguard ne. Áthelyezés/eltávolítás után frissüljön a lista. |
| Gaming Hub | Kapcsold be a beállításokban, majd telepíts új játékot vagy vegyél fel egy kézi játékot. A Games főmappájában jelenjen meg az indító. Az eredeti kliensen keresztül indítson, az EXE munkamappája/paraméterei maradjanak meg. A sakk külön almappába kerüljön. |
| Hub eltávolítás | Távolíts el egy launcherjátékot, majd külön egy kézi játék EXE-jét, a mentésmappát meghagyva. A saját hubikon tűnjön el mentéssel; a korábbi időadat maradjon meg. Ugyanoda újratelepítve kerüljön vissza. |
| Tálcavezérlés | A kék játékvezérlő–óra ikon bal kattintásra nyisson. Jobb kattintás menüt adjon. A menü elvetése ne zárja be az alkalmazást. Az X csak rejtse a főablakot; a külön Kilépés állítsa le a figyelőt. |
| Hub fájlvédelem | Egy külön tesztmappában hozz létre azonos nevű saját fájlt, majd szerkessz át egy generált ikont. A hub mindkettőt őrizze meg; saját indítója külön nevet kapjon. Eltávolított játék esetén csak a saját változatlan ikonja vonuljon vissza, mentéssel. |
| Games új játék | Indítsd el a figyelőt, majd telepíts/másolj saját játékot a beállított Games mappa új almappájába, akár `bin` alá. Felismerés újraindítás nélkül. |
| Első indítás / egyidejű telepítés | Telepítés után azonnal indítsd az új játékot, és maradj benne 30 másodpercig. Körülbelül 30 másodperc gyűljön, külön ellenőrzés nélkül. |
| Alt+Tab / háttér | Mérj 30 másodpercet a játékban, majd válts más alkalmazásra 30 másodpercre. A háttéridő ne adódjon hozzá; a váltás körül kb. 1 másodperc eltérés elfogadható. |
| Két játék | Futtass két játékot, de mindig csak az egyiket használd. Az összidő a tényleges eltelt idő legyen, ne annak kétszerese. |
| Menü / kontroller | Tölts 30 másodpercet a játék menüjében, majd játssz kizárólag kontrollerrel. Mindkettő számítson, billentyű/egér nélkül is. |
| Alvás / hibernálás | Játék előtérben, majd alvás/hibernálás legalább két percre. A visszatérés után a kiesett idő ne jelenjen meg. |
| Zárolás | Zárold a gépet játék közben. A zárolt idő ne számítson. |
| Újraindítás | Tálcamenüből lépj ki, majd indítsd újra. A mai idő maradjon meg. Windows újraindítása után automatikusan induljon a háttérfigyelő. |
| Váratlan leállás | Külön tesztpéldányt állíts le váratlanul. A korábbi mentés és kivételek maradjanak meg; általában legfeljebb tíz másodperc hiányozhat. |
| Éjfél | Játssz helyi éjfél körül; a főablak az új napra váltson. A korábbi nap ideje az adatbázisban maradjon meg. Éles gépen ne állítsd el emiatt a rendszerórát; az automatikus teszt ezt szimulálja. |
| 100/120 perces küszöb | Próbához állíts 1/2 perces küszöböt. Mindkét sötét popup és hang jelenjen meg egyszer, a gombok működjenek. Utána állítsd vissza 100/120 percre. |
| Lejárt keret új játék | Nyugtázás után Alt+Tab ugyanarra a futó játékra ne ismételjen. A játék újraindítása vagy új játék indítása adjon új figyelmeztetést, egyszer. |
| Teljes képernyő | Próbáld a két popupot keret nélküli és kizárólagos teljes képernyős módban. Ha a popup nem kerül fölé, a hang legyen hallható. |
| Sakk és böngésző | Chess.com, valamint egy kizárt telepített sakkprogram ne növelje a keretet. Szokatlan nevű sakkprogramot kézzel zárj ki; újraindítás után is maradjon kizárva. |
| Kézi javítás | Rendelj egy EXE-t egy kiválasztott játékhoz, majd vond vissza a Kivételek ablakban. Az új minták kövessék a változást. |
| Áthelyezés / eltávolítás | Steam/Epic saját felületén mozgasd vagy távolítsd el a játékot. A lista frissüljön; az addigi mai idő maradjon meg. |
| Telepítés leállított figyelő mellett | Lépj ki a figyelőből, telepíts játékot, majd indítsd újra a figyelőt. Az induláskori egyeztetés találja meg. |
| Bejelentkezés / eltávolítás | Telepítés után ellenőrizd az automatikus indulást. Eltávolítás után a saját Run-bejegyzés tűnjön el; a lefekvési emlékeztető változatlanul maradjon. |

Az aktuális végrehajtott tesztek eredményeit az átadott TESZTEREDMENYEK.txt foglalja össze.
