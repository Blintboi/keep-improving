# Keep Improving Android – 0.1.0 előzetes

**[Android telepítő letöltése — 0.1.0 előzetes (.apk)](https://github.com/Blintboi/keep-improving/raw/refs/heads/main/downloads/KeepImproving-Android.apk)** · [SHA-256 ellenőrzőösszeg](../downloads/KeepImproving-Android.apk.sha256) · [English](README.md)

A telefon önálló eszköz: saját használatot mér, és ugyanahhoz a titkosított
statisztikai csoporthoz csatlakozik, mint a számítógépek. Android 8.0 vagy újabb
rendszerre készül. A Windows-verzió számozásától független.

## Kipróbálás

1. A telefonodon koppints a fenti **Android telepítő letöltése** hivatkozásra,
   majd nyisd meg a letöltött APK-t. Az Android szükség esetén engedélyt kér a fájlt
   megnyitó alkalmazásból történő telepítéshez.
2. Az alkalmazásban engedélyezd a használati hozzáférést. A mérés ettől kezdődik;
   üzeneteket, begépelt szöveget és képernyőtartalmat nem olvas.
3. A **Statisztikák → Eszközök és szinkron** részen add meg a PC-n már használt
   összekapcsolási kódot. Ez nem a böngészőkiterjesztés párosítási kódja.
4. A PC-n is indíts szinkronizálást, amikor a telefon feltöltése befejeződött.
   A telefon külön eszközként jelenik meg. A szolgáltatás tízperces korlátja és
   a csoport közös szinkronizálási kerete továbbra is érvényes.

Az előzetes közvetlen APK-letöltéssel telepíthető, nem alkalmazásboltból.

## Az első előzetes tartalma

- Alkalmazások és Android által játékként jelölt programok használati ideje,
  napi bontásban, helyi SQLite-előzményekkel és telefonos alkalmazásikonokkal.
- Összesített és eszközönkénti statisztikák; napos, heti és havi nézet,
  alkalmazás-, játék- és weboldalszűrő. Weboldaladatot a PC-ktől tud átvenni;
  a telefon böngészőjét alkalmazásként méri.
- Csatlakozás a meglévő kóddal; kézi és megnyitáskori szinkron, offline cache.
- Magyar és angol felület. A mérés, az eszköznév és a nyelv a Beállításokban van.

Telefonos időkeretek, értesítések, fókusztiltás, webhelyenkénti telefonos mérés,
PC-beállítások távoli szerkesztése és új összekapcsolási kód létrehozása még nincs
ebben az előzetesben. A meglévő PC-beállításokat nem módosítja.

Az Android rögzíti a használati eseményeket. Az alkalmazás megnyitáskor és az
Android által ütemezett, legalább 15 perces helyi háttérfeladatban menti őket.
Nincs folyamatos figyelőszolgáltatás vagy háttérbeli hálózati lekérdezés. Az Android
késleltetheti a feladatot; ha több nap eseménye már nem kérhető le, a hiányzó időt
nem találjuk ki. Megosztott képernyőn a legutóbb előtérbe került alkalmazást méri.
Ez alkalmazásban töltött idő, nem a lezárt képernyő vagy a háttérben szóló zene ideje.

## Adatok és frissítés

A szinkron a meglévő Free csomagos Game Monitor szolgáltatást használja.
A kódból külön HMAC-SHA256 hitelesítési és AES-256-GCM titkosítási kulcs származik;
a formátum a PC-vel azonos. A szerver nem kapja meg a kódot vagy a titkosítási
kulcsot. A telefon kódját az Android Keystore védi. Nincsenek szolgáltatói
adminisztrátori kulcsok az APK-ban. Más eszközről letöltött idő nem kerül a telefon
saját feltöltésébe. A leválasztás megtartja a helyi telefonos előzményeket.

A frissítés ugyanazzal a csomagnévvel és aláírókulccsal, eltávolítás nélkül
telepítendő. A helyi építés tartós saját kulcsot tárol a
`%LOCALAPPDATA%/KeepImprovingAndroidSigning` mappában, a jelszót Windows DPAPI-val
védve. Ezt meg kell őrizni a későbbi frissítésekhez; nem kerül a forráskódba vagy
az APK mellé. A telefonos felhőmentés és automatikus eszközmásolás ki van kapcsolva,
mert a Keystore-kulcs és az eszközazonosság nem másolható biztonságosan így.

## Fejlesztés és ellenőrzés

JDK 21, Android SDK 36 / Build Tools 36.0.0 és a projekt Python-környezete kell.
A Gradle 8.14 wrapper SHA-256-tal ellenőrzött, a függőségek verziója rögzített.
Nincsenek külső futásidejű Android-függőségek.

```powershell
.\android\build.ps1
```

A script külön, ASCII elérési utas építési környezetet használ; nem javítja vagy
törli más projektek Gradle-cache-ét. Lefuttatja a Java/Robolectric teszteket,
az Android lintet, a Python–Java titkosítási és valódi SQLite-importpróbát,
majd ellenőrzi az APK aláírását és kiírja a helyi APK-t a SHA-256 fájllal.
A tesztek szintetikus adatokat használnak, nem a felhasználó profilját vagy
éles szinkronkódját. Natív renderelésű HU/EN képek a helyi építés után:
`%LOCALAPPDATA%/KeepImprovingDev/android-build/app/ui/`.

A fizikai telefonos telepítést és a gyártó energiatakarékossági viselkedését külön
ki kell próbálni. A helyi gép Android-emulátorához nincs hardveres gyorsítás;
a szoftveres emulátor nem indult el, ezért ez a build Robolectric-eszköztesztekkel
és natív grafikus rendereléssel ellenőrzött, nem fizikai telefonon.

Alapul szolgáló dokumentáció: [UsageStatsManager](https://developer.android.com/reference/android/app/usage/UsageStatsManager),
[használati események](https://developer.android.com/reference/android/app/usage/UsageEvents.Event),
[Android build kompatibilitás](https://developer.android.com/build/releases/agp-8-11-0-release-notes),
[Robolectric kompatibilitás](https://robolectric.org/compatibility_table/).
