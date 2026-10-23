# Titkos adatok nyilvános kitettségének ellenőrzése — 2026-10-23

Az ellenőrzött forrásban, Git-előzményekben, telepítőkben és éles API-felületeken
nem találtam valódi, nem nyilvános használatra szánt szolgáltatói kulcsot vagy
nyilvánosan letölthető felhasználói profilt. Ez a konkrét ellenőrzések eredménye;
nem teljes körű behatolási teszt vagy minden jövőbeli hibát kizáró garancia.

## Vizsgált felületek és eredmények

| Felület | Ellenőrzés | Eredmény |
| --- | --- | --- |
| Nyilvános Git-forrás | A `main` fej `3a54e59`, 42 commit, teljes elérhető előzmény; Gitleaks 8.30.1, dekódolás, meglévő kivételek felülvizsgálata | Valódi titok nem került elő |
| Helyi aktuális forrás | Követett és nem ignorált új fájlok, köztük a még nem publikált változtatások | Valódi titok nem került elő |
| Korábbi letöltések | Mind a 18, Gitből elérhető különböző telepítő és 11 Release összesen 33 melléklete | Profil, adatbázis, környezeti titok vagy valódi privát kulcs nem került elő |
| Telepítők belseje | CAB, beágyazott ZIP-ek, natív karakterláncok, PyInstaller PYZ modulok, fordított konstansok | A Gitből kimaradó, buildkor beépített értékek is vizsgálva |
| GitHub további felületei | Egy Actions-futás naplója, mellékletek, issue-k és pull requestek | Ismert titokmintát nem találtam; nincs Actions-melléklet, issue vagy PR |
| Éles Supabase | Mind a hat alkalmazástábla, tíz függvény, Auth-táblák, Storage és Realtime jogosultságai | Az `anon` és `authenticated` szerepkörnek nincs közvetlen alkalmazásadat- vagy függvényhozzáférése; nincs nyilvános Storage-tartalom vagy alkalmazástábla-publikáció |
| Külső HTTP-próbák | 17 kis kérés, kizárólag publikus kulccsal és mesterséges, ismeretlen kapcsolati azonosítóval | Az adat-, felhasználólista- és fiókkezelési próbák elutasítva; ismeretlen csoporthoz nincs hozzáférés |
| Kliens és szerver határa | A két telepített Edge Function forrásának összevetése a helyi forrással; kliens HTTP-, titkosítási és hitelesítési útvonalak | A források egyeznek; adminisztrációs kulcs kizárólag szerveroldali környezeti változóból származik |

A 2026-10-21-én már kibontott régi mellékleteknél a jelenlegi GitHub-metaadatok
mind a 33 SHA-256 értékének egyezését ellenőriztem, majd újra átvizsgáltam a
helyben tárolt, dekódolt tartalmat. Ezeket az azonos bájtokat nem töltöttem le
ismét. Az azóta hozzáadott hat történeti telepítőt külön kibontottam.
A két történeti vizsgálat összesen 5 400 beágyazott Python-modulpéldányt érintett;
ez tartalmaz ismétlődő függőségeket is. A helyi 2.21.2 telepítőt külön ellenőriztem.

## Miért látszik mégis kulcs a kliensben?

A Supabase `sb_publishable_…` projektkulcsa szándékosan publikus azonosító.
Nem adminisztrációs hitelesítő adat, és nem jogosít más felhasználó adatainak
lekérésére. A tényleges tiltásokat az éles adatbázis jogosultságain és külső
HTTP-kérésekkel is ellenőriztem. A szolgáltatói adminisztrációs kulcs, GitHub OAuth
titok, kapcsolati kód és titkosítási kulcs nem része a kiosztott közös klienskódnak.
Lásd a [Supabase hivatalos kulcsdokumentációját](https://supabase.com/docs/guides/getting-started/api-keys).

A Qt könyvtáraiban talált `BEGIN … PRIVATE KEY` / `END … PRIVATE KEY` jelölők
kulcsformátum-feldolgozó szövegek, kulcsanyag nélkül. A `PKCS8_PRIVATEKEY` egy
Windows CNG formátumazonosító. Ezekre csak pontos teljes tartalmi hashhez kötött
kivételek kerültek az ellenőrzőbe. A Qt 6.12 két további bináris találattípusát
is a hivatalos wheel RECORD hashével és a konkrét bájtokkal ellenőriztem:
lefordított időzónanevek `…sk-tyd…` jellegű részletei, valamint három PNG-ikon
PLTE színpalettájának véletlen számsorozatai. Ezek sem szolgáltatói kulcsok;
kivételük a teljes, változatlan DLL SHA-256 értékéhez kötött.
A helyi Auth-teszt egyik szándékosan érvénytelen
tokenmintáját ugyancsak teljes fájlhash és konkrét találati hely azonosítja.
Általános könyvtár-, teszt- vagy kulcstípus-kizárás nincs.

## Megelőző változtatások

- A csomagolás átvizsgálja az aktuális forrást és a végleges telepítőt, a
  `FreezeOnly` mód pedig a fagyasztott könyvtárat. A scanner vagy a kibontás
  hibája sikertelen buildet eredményez.
- A Gitleaks verziója rögzített; a letöltött ZIP SHA-256 értékét futtatás előtt
  ellenőrzi a build. Az EXE-t minden alkalommal az ellenőrzött ZIP-ből bontja ki.
- Külön felismerés védi a bináris és UTF-16 formában beépített szolgáltatói
  kulcsokat és a `service_role` JWT-ket. A jelentések helyet és szabályazonosítót
  tartalmaznak, titkos értéket nem.
- Az új regressziós teszt valódi tömörített PYZ-archívumban vizsgál egy fordításkor
  beépített tesztkulcsot. További esetek ellenőrzik a beágyazott profilfájlokat,
  `.env` fájlokat, SQLite-adatokat, rossz archívumokat és a jelentések kitakarását.
- Az új GitHub-workflow push és PR esetén ellenőrzi az előzményt és a forrást.
  Ez csak a workflow későbbi, külön engedélyezett publikálása után fut GitHubon.
- A helyi `.env` fájlok és privát aláírókulcs-tárolók Git-ignorálást kaptak.
  Az ignorálás önmagában nem töröl régi commitot és nem hozzáférésvédelem.

## Bizonyítékok és korlátok

A részletes, csak helyben tárolt gépi jelentések a
`test-reports/secrets-audit-20261023/` ignorált könyvtárban vannak. A kapcsolódó
ellenőrzések: 44 statisztikai klienspróba, 24 Edge Function-próba, hat Windows
hitelesítőadat-próba, öt csomagbiztonsági regressziós teszt és 17 éles HTTP-próba.
Az audit nem olvasott ki valós felhasználói felhőadatot vagy szolgáltatói
adminisztrációs kulcsot, és nem módosította az éles sémát vagy jogosultságokat.

A Supabase advisor jelszószivárgás-védelmi figyelmeztetése továbbra is megjelenik.
A valódi publikus Auth-beállítások szerint az email/jelszó és anonim belépés
ki van kapcsolva, a GitHub-belépés engedélyezett. A Free csomag és a meglévő
projekt megmaradt. A szándékosan policy nélküli, RLS-sel lezárt szervertáblák
információs jelzése nem engedélyezi az adatok elérését.

Mások által korábban letöltött fájlokat, felhasználói megosztásokat, szolgáltatói
adminisztrátorok fiókvédelmét vagy ugyanazzal a Windows-felhasználóval futó kártevőt
ez az audit nem tudja kizárni. A helyi profil, naplók és korábbi mentések továbbra
is magánadatok; ezeket ne csatold nyilvános hibajegyhez. A kapcsolati kódot is
jelszóként kell kezelni. A DPAPI védi a helyben mentett hitelesítő adatokat,
a teljes játékidő-adatbázis azonban nincs titkosítva.

GitHubra ebben a munkamenetben nem történt publikálás.
