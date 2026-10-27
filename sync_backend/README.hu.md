# Kódos statisztikaszinkron

[English deployment and operator guide](README.md)

**Állapot:** éles Supabase-háttér a felhasználó meglévő **Game Monitor** projektjében,
ellenőrzött **Free** csomagban. Projektazonosító: `jtvdbqwmejrckjejjrdl`;
régió: `eu-west-1`; PostgreSQL 17. A kliens 2.7.0-tól használja a kódos felületet.
A végpont: `https://jtvdbqwmejrckjejjrdl.supabase.co/functions/v1/statistics-sync`.

**2.12.0: eseményvezérelt szinkron, tartós gépenkénti és közös keretek.** A
szolgáltató, a helyi PKCE-visszatérés, a tokenfrissítés és a kijelentkezés éles
ellenőrzése sikeres. Az új regisztráció a kezdeti kereteken belül nyitva van.
Egy fiók egy aktuális kódot kezel; másik gép a meglévő kóddal csatlakozhat.
A korábbi kapcsolat és mindkét gép adatai megmaradtak. A Free csomag támadó
kérésáradat elleni elérhetőséget nem garantál; részletek a
[biztonsági leírásban](../SECURITY.md).

A `Before User Created` SQL Auth Hook a fiók tárolása előtt korlátozza a
szolgáltatót és a regisztrációkat: napi 25, összesen 500 lefoglalt
regisztrációs hely. A csoportkeret 100 aktív csoport, napi 25 új
tulajdonos; fiókonként havi 3 létrehozás/átvétel/kódcsere. A kódcsere nem
nullázza a fiók forgalmi keretét. Sikertelen regisztráció is foglalhat helyet;
ellenőrzés nélkül ne nullázd a számlálókat. A titkosított csoportadatok mellett
a Supabase Auth már fiókazonosítót, GitHub-profilt és ellenőrzött e-mailt is tárol.
Az adatkezelési tájékoztató a végpont `/about` útvonalán olvasható.

A háttér egy Supabase adatbázis, Auth és két Edge Function. Ezt a program
üzemeltetője egyszer állítja be. A játékosoknak nincs szükségük saját Supabase
fiókra, közös mappára vagy adminisztrátori API-kulcsra. Az első gép véletlen
128 bites kódot generál; ugyanennek a kódnak a megadása kapcsolja hozzá a
további gépeket. Rövid, tetszőleges PIN nem használható internetes hozzáférési
kulcsként. A kódot meg kell őrizni; elvesztett kódhoz nincs szerveroldali
helyreállítás, másnak átadva hozzáférést ad a csoporthoz.

A kliens külön kulcsot származtat a szerveres hozzáféréshez és az AES-256-GCM
titkosításhoz. A szerver a hozzáférési kulcs lenyomatával választja ki a
csoportot. A kód és a titkosítási kulcs nem kerül a szerverhez. A szerver
titkosított statisztikát és véletlen gépazonosítót tárol; a játéknevek, gépnevek
és időadatok a titkosított csomagban vannak. Minden kliens a saját összesített
napi adatait tölti fel, ezért a más gépről származó idő nem többszöröződik meg.
A felhasznált napi keret és a helyi előzmények gépenként külön maradnak. A
támogatott beállítások és játékonkénti kizárások a titkosított csomagban
szinkronizálódnak; a gépspecifikus mappák és a védett játékokra adott
hozzájárulások helyben maradnak.

## Újratelepítés vagy másik saját háttér

1. Supabase-fiók csatlakoztatása, majd külön projekt kiválasztása vagy létrehozása
   **Free** csomagban. Meglévő projekt sémáját előbb ellenőrizni kell.
2. A `supabase/migrations/` összes migrációjának alkalmazása fájlnévsorrendben.
   Minden táblán RLS aktív, közvetlen `anon` / `authenticated` hozzáférés nincs.
   A függvényt kizárólag a szerver oldali `service_role` hívhatja.
3. GitHub OAuth-alkalmazás létrehozása, visszatérési cím:
   `https://<projekt>.supabase.co/auth/v1/callback`. A klienskulcs kizárólag a
   Supabase GitHub-szolgáltató beállításába kerüljön. E-mail nélküli belépés,
   e-mail/jelszó és anonim belépés legyen kikapcsolva. A projekt URL-listáján
   kizárólag `http://127.0.0.1:*/gametime/callback/*` kell a natív kliensnek.
   A Before User Created Auth Hook Postgres-függvénye:
   `public.gametime_before_user_created`; a kapu a sikeres ellenőrzésig zárt.
4. A `statistics-sync` Edge Function telepítése a mellékelt `index.ts` és
   `handler.mjs` fájllal, `verify_jwt=false` beállítással. A függvény saját
   csoportonkénti hitelesítést végez. A Supabase `service_role` kulcsot csak a
   szolgáltatás környezetéből olvassa; telepítőbe és GitHubra nem kerülhet.
5. A `statistics-account` Edge Function telepítése a saját két forrásfájljával,
   `verify_jwt=true` értékkel. A nyilvános publishable projektkulcs a kliens Auth
   hívásaihoz használható; nem ad adatbázis- vagy adminisztrátori hozzáférést.
6. Éles ellenőrzés: két külön adatprofil ugyanazzal a kóddal egyesít; eltérő
   kóddal nem kap adatot; a nyilvános adatbáziskulccsal nincs hozzáférés;
   hibás/túl nagy csomag és régi verzió nem ír felül jó adatot. Az ideiglenes
   próbaprofilok adatait a végén törölni kell, a tárhelyszámlálót igazítva.
7. Csak ezután változtatható meg a végleges HTTPS-végpont a Windows-kliensben. Új verzió,
   tesztelt telepítő és README-frissítés együtt kerüljön GitHubra.

A `gametime/statistics_cloud.py` a kliens átviteli és titkosítási modulja.
A függőségeket a `requirements-runtime.txt` rögzíti; a Windows-telepítő ezeket
és a hozzájuk tartozó licencszövegeket is tartalmazza. A szolgáltatói adminisztrátori
kulcsot a kliens nem használja és nem tartalmazza.

## Kapacitás és költség

A szolgáltatás Free csomagot használ. A szolgáltató ingyenes csomagja korlátozott,
nem jelent korlátlan vagy garantáltan folyamatos szolgáltatást. Nem kell
fizetős csomagra váltani a megvalósítás miatt; csomagváltást ez a kód nem végez.
Az aktuális feltételek: https://supabase.com/pricing

A saját korlátok az éles adatbázisban tranzakciósan érvényesülnek:

| Korlát | Érték |
| --- | --- |
| Gépek | 20/csoport, globálisan 10 000 |
| Titkosított csomag | legfeljebb 512 KiB/gép, a base64 boríték legfeljebb 699 052 bájt |
| Tárolt base64-adat | 2 MiB/csoport, globálisan 200 MiB (nem a teljes adatbázisméret) |
| Percenkénti kérések | 4/gép, 40/csoport, 600/IP-lenyomat |
| Sikeres adatcserék | UTC-naponként 20, havonta min(600, 350 000 / max(25, aktív csoportok)) csoportonként ÉS tulajdonosonként; globálisan havi 350 000 |
| Gépenkénti várakozás | Legalább 10 perc két befejezett adatcsere között, szerveroldalon is |
| Számolt havi válaszforgalom | min(128 MiB, 3 GiB / max(25, aktív csoportok)), globálisan 4 GiB |
| Napi fel- és válaszforgalom | irányonként 8 MiB/csoport és tulajdonos |
| Összes feltöltés | globálisan 64 MiB/UTC-nap és 1 GiB/UTC-hónap; teljes felülírásokat is számol |
| Havi feltöltés csoportonként és tulajdonosonként | min(64 MiB, 1 GiB / max(25, aktív csoportok)) |
| Válasz | legfeljebb kb. 1 MiB titkosított pillanatkép, többlépéses felzárkózás |
| Edge kérés | 750 000 bájt, 5 másodperces beolvasás; legfeljebb 8 párhuzamos kérés/isolate |
| Inaktív szervermásolat | 90 nap után törlődik az óránkénti karbantartásban |

A hozzáférési kulcs és a nyers IP nem kerül az adatbázisba. Az IP az utolsó
proxycím szerverkulccsal képzett HMAC-lenyomata, kiegészítő védelem; nem
használható egyetlen megbízható felhasználói azonosítóként. A kvóta elérésekor
a helyi követés és a letöltött statisztika megmarad. A kliens legfeljebb egy
napos `Retry-After` értéket követ; hiba önmagában nem indít automatikus újrapróbálkozást. Az üres szinkronszál várólistán alszik.

A saját kvóta nem a szolgáltató fogyasztásmérője: az elutasított kérés,
HTTP-fejléc, hálózati többlet és más Supabase-forgalom is terhelheti a keretet.
A Free csomag jelenleg 500 000 Edge-hívást, 5 GB egress-t és 500 MB
adatbázist tartalmaz; ez nem garantált felhasználószám. A 2.12 induláskor egyszer,
játékkezdéskor és játék után, valamint kézzel frissít. A közeli váltásokat egy
nyugodt perc után összevonja. Nincs rendszeres hálózati lekérdezés. Az egyszeri
eseményidőzítő kivárja a 10 perces gépenkénti korlátot és a szerver késleltetését.
Az újraindítás és a kódcsere nem nullázza a helyi várakozást. A szerver a gép
várakozásán túl csoportonként és tulajdonosonként is napi 20/havi 600 sikeres
kérést enged; a tulajdonosi keret kódcsere után megmarad.

Két naponta egyszer induló gép 30 nap alatt kb. 60 induláskori kérést jelent,
a játékesemények, kézi frissítés és hiányzó szervermásolat javítása ezen felül jön.
Ez kérésbecslés, nem mért kapacitás vagy támadásvédelmi garancia.
Mindegyik gépet legalább 2.12.0-ra kell frissíteni. A régi protokoll 426 választ
kap az adatbázis és a törzs beolvasása előtt, egynapos várakozási javaslattal.
Az új nyilvános protokollfejléc nem hitelesítés; utánzásakor is érvényesek az
adatbázis korlátai. A kód, titkosított másolatok és helyi előzmények megmaradnak.
A friss játékidő átviteléhez a forrásgép a függő feltöltés végéig maradjon online.

A Custom Access Token Hook felhasználónként legfeljebb 10 munkamenetet,
percenként 12 és UTC-naponként 120 tokenkiadást, globálisan napi 1000-et enged.
A bejelentkezési állapotok két Auth-táblájában összesen legfeljebb 1000 sor,
soronként 16 KiB, a fiókmetaadatban 32 KiB tárolható. Ötpercenként takarítja
az egy óránál régebbi belépési állapotokat, az aktív munkameneteket megtartva.
A provider Auth-tábláihoz csatolt invoker triggerek frissítés után újraellenőrzendők.
Az üzemeltetői hozzáférés nem kerül a klienshez. A visszavont kódokat is számoló
nyilvántartás 10 000 sorra korlátozott. A telített percenkénti számlálók nem
íródnak újra minden elutasított kérésnél. Ez tárolási védelem; az elutasított
kérések továbbra is fogyaszthatnak szolgáltatói híváskeretet.

Új felhasználó a kliens GitHub-belépésével hozhat létre kódot a megadott
kereten belül. A `registration_enabled=false` csak az új regisztrációt és
csoportlétrehozást állítja le; az `enabled=false` a normál adatcserét is.
A fiókhoz kötött havi/napos keret kódcsere után is megmarad. A régi kód
visszavont jelölése és a kvótanapló szándékosan megmarad; ne töröld őket
ellenőrizetlenül. A `group_fingerprint.py` régi üzemeltetői helyreállításhoz
használható, a normál felhasználónak nincs rá szüksége.

## Helyi ellenőrzés

A jelenlegi éles projektben a kétprofilos HTTPS-próba, a közvetlen adatbázis-hozzáférés
elutasítása, a revíziós és kvótaszabályok ellenőrzése már sikeres. A próbaadatokat
eltávolítottuk. Az RLS-ellenőrzés tájékoztató „nincs klienspolicy” jelzése a
szándékosan lezárt táblákhoz tartozik; részletek a fő `TESTING.md` fájlban.

```powershell
.\.venv\Scripts\python.exe -m pip install -r sync_backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_statistics_cloud.py -v
node --test sync_backend/tests/*.test.mjs
```

Ezek az ellenőrzések a titkosított HTTP-protokollt és a függvény határait
tesztelik. A valódi PostgreSQL-migrációt, RLS-jogosultságokat, Supabase-kapukat
és a szolgáltató elérhetőségét a csatlakoztatott projektben kell ellenőrizni.

A `tests/hardening.sql` tranzakciója valós PostgreSQL-en vizsgálja a
kvótákat, az izolációt, a revíziókat, a kapcsolót, a válaszlapozást és a
karbantartási számlálókat, majd mindent visszagörget. Meglévő próbajelölőkkel
ütközéskor megáll; éles felhasználó kódját nem használja.

A `tests/account.sql` a valós `service_role` jogosultságokkal ellenőrzi az
ellenőrzött identitást, a munkamenetet, tulajdonjogot, kvótákat, izolációt és
visszavonást, majd visszagörget. A `tests/signup.sql` a regisztrációs Hookot
vizsgálja. A Supabase menedzselt postgres nem válthat auth-admin szerepre;
az Authon keresztüli éles, elutasított regisztráció külön igazolja a Hook útját.
A valódi GitHub-belépés, tokenfrissítés és külön tesztmunkamenet kijelentkezése
is ellenőrizve lett; a fő munkamenet és a meglévő kód megmaradt.
