# Kódos statisztikaszinkron

**Állapot:** éles Supabase-háttér a felhasználó meglévő **Game Monitor** projektjében,
ellenőrzött **Free** csomagban. Projektazonosító: `jtvdbqwmejrckjejjrdl`;
régió: `eu-west-1`; PostgreSQL 17. A kliens 2.7.0-tól használja a kódos felületet.
A végpont: `https://jtvdbqwmejrckjejjrdl.supabase.co/functions/v1/statistics-sync`.

**2.9.0: ellenőrzött, üzemeltető által engedélyezett csoportok.** A meglévő
kapcsolatok megmaradnak. Új kód nem hoz létre automatikusan csoportot vagy
szerveroldali tárhelyet. A szabad nyilvános regisztráció még zárva van;
a szükséges beléptetésről, fennmaradó kockázatokról és incidenskezelésről
a [biztonsági leírás](../SECURITY.md) rendelkezik. A Free csomag nem garantál
elérhetőséget támadó kérésáradat ellen.

A háttér egy Supabase adatbázis és egy Edge Function. Ezt a program
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
A napi keret és a kizárások továbbra is helyi beállítások.

## Újratelepítés vagy másik saját háttér

1. Supabase-fiók csatlakoztatása, majd külön projekt kiválasztása vagy létrehozása
   **Free** csomagban. Meglévő projekt sémáját előbb ellenőrizni kell.
2. A `supabase/migrations/` összes migrációjának alkalmazása fájlnévsorrendben.
   Minden táblán RLS aktív, közvetlen `anon` / `authenticated` hozzáférés nincs.
   A függvényt kizárólag a szerver oldali `service_role` hívhatja.
3. A `statistics-sync` Edge Function telepítése a mellékelt `index.ts` és
   `handler.mjs` fájllal, `verify_jwt=false` beállítással. A függvény saját
   csoportonkénti hitelesítést végez. A Supabase `service_role` kulcsot csak a
   szolgáltatás környezetéből olvassa; telepítőbe és GitHubra nem kerülhet.
4. Éles ellenőrzés: két külön adatprofil ugyanazzal a kóddal egyesít; eltérő
   kóddal nem kap adatot; a nyilvános adatbáziskulccsal nincs hozzáférés;
   hibás/túl nagy csomag és régi verzió nem ír felül jó adatot. Az ideiglenes
   próbaprofilok adatait a végén törölni kell, a tárhelyszámlálót igazítva.
5. Csak ezután változtatható meg a végleges HTTPS-végpont a Windows-kliensben. Új verzió,
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
| Tárolt base64-adat | 4 MiB/csoport, globálisan 200 MiB (nem a teljes adatbázisméret) |
| Percenkénti kérések | 4/gép, 40/csoport, 600/IP-lenyomat |
| Sikeres havi adatcserék | 60 000/csoport, globálisan 350 000 |
| Számolt havi válaszforgalom | 512 MiB/csoport, globálisan 4 GiB |
| Napi fel- és válaszforgalom | irányonként 64 MiB/csoport |
| Válasz | legfeljebb kb. 1 MiB titkosított pillanatkép, többlépéses felzárkózás |
| Edge kérés | 750 000 bájt, 5 másodperces beolvasás; legfeljebb 8 párhuzamos kérés/isolate |
| Inaktív szervermásolat | 90 nap után törlődik az óránkénti karbantartásban |

A hozzáférési kulcs és a nyers IP nem kerül az adatbázisba. Az IP az utolsó
proxycím szerverkulccsal képzett HMAC-lenyomata, kiegészítő védelem; nem
használható egyetlen megbízható felhasználói azonosítóként. A kvóta elérésekor
a helyi követés és a letöltött statisztika megmarad. A kliens legfeljebb egy
napos `Retry-After` értéket követ, hibánál növekvő, véletlen eltéréssel ritkított
újrapróbálkozást használ. Az üres szinkronszál várólistán alszik.

A saját kvóta nem a szolgáltató fogyasztásmérője: az elutasított kérés,
HTTP-fejléc, hálózati többlet és más Supabase-forgalom is terhelheti a keretet.
A Free csomag jelenleg 500 000 Edge-hívást, 5 GB egress-t és 500 MB
adatbázist tartalmaz; ez nem garantált felhasználószám. Példa: két mindig
futó gép ötpercenkénti üresjárati szinkronja 30 nap alatt kb. 17 280 kérés,
így a saját 350 000-es plafon kb. 20 ilyen felhasználót fed le, tartalék nélkül.
Folyamatos percenkénti aktív szinkronnál ugyanez 86 400 kérés/felhasználó,
ami már egy csoport havi kvótáját is eléri. Kezdj kevés meghívottal, és az
éles szolgáltatói mérések alapján méretezz; a tárhely önmagában félrevezető.

Új meghívott a saját gépén futtathatja a `group_fingerprint.py` segédet:
az rejtve kéri be a kódot, és csak a szerveroldali lenyomatot írja ki.
A lenyomat átadható az üzemeltetőnek, a kódot nem kell megosztani.
Ellenőrzött meghívás után kizárólag az üzemeltető illeszthet be ilyen sort:

```sql
insert into public.gametime_sync_groups(group_hash) values ('<64 hex karakter>');
```

Ez kézi meghívási folyamat, nem nyilvános önkiszolgáló regisztráció.
A lenyomat önmagában nem ad hozzáférést a titkosított adatokhoz.

## Helyi ellenőrzés

A jelenlegi éles projektben a kétprofilos HTTPS-próba, a közvetlen adatbázis-hozzáférés
elutasítása, a revíziós és kvótaszabályok ellenőrzése már sikeres. A próbaadatokat
eltávolítottuk. Az RLS-ellenőrzés tájékoztató „nincs klienspolicy” jelzése a
szándékosan lezárt táblákhoz tartozik; részletek a fő `TESTING.md` fájlban.

```powershell
.\.venv\Scripts\python.exe -m pip install -r sync_backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_statistics_cloud.py -v
node --test sync_backend/tests/handler.test.mjs
```

Ezek az ellenőrzések a titkosított HTTP-protokollt és a függvény határait
tesztelik. A valódi PostgreSQL-migrációt, RLS-jogosultságokat, Supabase-kapukat
és a szolgáltató elérhetőségét a csatlakoztatott projektben kell ellenőrizni.

A `tests/hardening.sql` tranzakciója valós PostgreSQL-en vizsgálja a
kvótákat, az izolációt, a revíziókat, a kapcsolót, a válaszlapozást és a
karbantartási számlálókat, majd mindent visszagörget. Meglévő próbajelölőkkel
ütközéskor megáll; éles felhasználó kódját nem használja.
