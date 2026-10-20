# Kódos statisztikaszinkron

**Állapot:** éles Supabase-háttér a felhasználó meglévő **Game Monitor** projektjében,
ellenőrzött **Free** csomagban. Projektazonosító: `jtvdbqwmejrckjejjrdl`;
régió: `eu-west-1`; PostgreSQL 17. A kliens 2.7.0-tól használja a kódos felületet.
A végpont: `https://jtvdbqwmejrckjejjrdl.supabase.co/functions/v1/statistics-sync`.

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
2. A `supabase/migrations/20261020174132_statistics_sync.sql` migráció alkalmazása.
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

A saját további korlátok: legfeljebb 20 gép/kód, 512 KiB tömörített és
titkosított csomag/gép, összesen 200 MiB tárolt base64-adat és 10 000 gép;
percenként 120 kérés/csoport és 600 kérés/IP-lenyomat. A hozzáférési kulcs és
a nyers IP nem kerül az adatbázisba. A titkosított adatok tárhelyszámlálója
tranzakciós; a kvóta elérésekor a helyi követés és a korábban letöltött
statisztika megmarad. A kvóták nem akadályozzák meg a szolgáltatói ingyenes
függvényhívási/adatforgalmi keret kimerülését: az éles használatot figyelni
kell, az adatvesztés nélküli automatikus újrapróbálás a kliens feladata.

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
