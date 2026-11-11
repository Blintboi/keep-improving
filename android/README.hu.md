# Keep Improving Androidra — 0.6.0

**[Letöltés Android 8.0 vagy újabb rendszerre (.apk)](https://github.com/Blintboi/keep-improving/raw/refs/heads/main/downloads/KeepImproving-Android.apk)** · [SHA-256](../downloads/KeepImproving-Android.apk.sha256) · [English](README.md) · [Windows-alkalmazás](../README.hu.md)

Mérd a telefonhasználatodat, nézd meg az időt és a munkameneteket, és állíts napi kereteket. A telefon önállóan működik, de titkosított statisztikákat és támogatott szabályokat is megoszthat a számítógépeiddel. Verziószámozása a Windowstól független.

## Telepítés és összekapcsolás

1. Töltsd le az APK-t a telefonon, és nyisd meg. Szükség esetén engedélyezd a csomag telepítését a letöltéshez használt alkalmazásnak. A meglévő appra telepíts, hogy megmaradjanak az adatok; előtte ne távolítsd el.
2. Nyisd meg a Keep Improvingot, és engedélyezd a **használati hozzáférést** a méréshez.
3. Gyors korlátozáshoz kapcsold be a **Beállítások → Alkalmazások eltakarása** lehetőséget. Az opcionális kisegítő szolgáltatás az alkalmazás és ablak azonosságát használja, nem olvas képernyőszöveget, bevitelt vagy gesztusokat. Az Android-beállítások megnyitása előtt elmagyarázza az engedélyt.
4. Add meg az értesítési engedélyt, amikor kéri. Android 12-től az **Ébresztések és emlékeztetők** engedélye is kellhet a pontos háttéridőzítéshez; nélküle az időzítés közelítő.
5. A **Beállítások → Eszközök és szinkron** alatt add meg a Windows-programban használt kapcsolati kódot. Ez nem a böngészőbővítmény párosítási kódja. Tartsd titokban.

Az alkalmazás közvetlen APK-letöltéssel érhető el, nem alkalmazásboltból. A frissítések ugyanazt az aláírókulcsot használják. A telefon energiatakarékossága késleltetheti a gyűjtést és az emlékeztetőket; kényszerített leállítás után újra meg kell nyitni az appot a háttérműködéshez.

## Mire használhatod?

- **Áttekintés:** idő vagy munkamenetszám választható, dátumra, eszközre és tevékenységtípusra szűrhetsz, kereshetsz, rendezhetsz és CSV-t exportálhatsz az Android fájlválasztójával. A mért számok legalábbjel nélkül jelennek meg; frissítéskor megmarad a görgetés helye.
- **Alkalmazások:** kijelölheted a telepített appokat, játékot jelölhetsz és kizárhatsz tevékenységeket a mérésből. A saját felület és a rendszerképernyők nem számítanak a használati összegbe.
- **Keretek:** alkalmazások vagy kategóriák, érvényes napok, megújulási idő és opcionális perckeret választható. Figyelmeztetés, korlátozás vagy szünet használati idő, időpont vagy napi munkamenetszám alapján is indulhat. Öt engedélyezett munkamenetnél a hatodik váltja ki a műveletet. Az átfedő kijelölések egyszer számolják az alkalmazást.
- **Fókusz:** Pomodoro, szüneteltetés és folytatás, rövid és hosszú szünetek, valamint kijelölt alkalmazások kitakarása. Az időzítő és a befejezett körök újraindítás után is megmaradnak.
- **Értesítések:** időponthoz, alkalmazásmegnyitáshoz és napi fókuszcélhoz kapcsolódó emlékeztetők hanggal, bezárási idővel, fókuszt vagy alkalmazást indító művelettel.
- **Eszközök:** a telefonos és PC-s keretek, emlékeztetők közös listában látszanak, eszközjelöléssel és szűréssel. Egy szabály egy eszközre, elnevezett csoportra vagy minden kapcsolt eszközre vonatkozhat. Az egyes platformok alkalmazásait külön kell kijelölni.

A számláló csendes, folyamatos értesítés. Bekapcsolt védelemnél követi az előtérbeli appváltást; rábökve megnyílnak a Keretek. A Beállításokban kikapcsolható. A kezdőlap, beállítások, engedélykérő és tárcsázó képernyők nem takarhatók ki. A védelem önkéntes, nem megkerülhetetlen.

A telefon a saját böngészőjét alkalmazásként méri. Weboldal-előzmények a kapcsolt PC-kről érkezhetnek; a telefon böngészőlapjait nem méri és tiltja külön. A Windows megnyitási célválasztója, válaszonkénti kerete és **Szünet most** művelete Androidon még nem érhető el.

## Munkamenetek és szinkron

Egy munkamenet folyamatos, mért előtérbeli használat, a kezdőnapjára számítva. Egy app belső képernyői közötti váltás nem hoz létre új munkamenetet. A régebbi előzmények csak a ténylegesen mérhető adatot tartalmazzák.

Csak a telefon saját használata töltődik fel; az átvett gépadat nem kerül fel még egyszer. A pillanatképek a készüléken, a meglévő kapcsolati kóddal titkosítódnak. A kapcsolódási titkokat az Android Keystore védi. A helyi előzmény az app saját adatbázisában marad; önmagában nincs titkosítva.

A megnyitott eszközök időszakosan keresnek változásokat; szerkesztéskor korábbi szinkronkérés indul. Az Android a háttérmunkát kötegelheti, a szolgáltatás kvótái és újrapróbálási ideje elsőbbséget élveznek. Kapcsolat nélkül a helyi mérés és időzítés folytatódik. A közös keret az utolsó átvett összesítéssel számol, ezért az offline eszközök átmenetileg túlléphetik az együttes határt. A szinkron állapota látható az alkalmazásban.

Engedélyezett USB-hibakeresési kapcsolatnál fejlesztőként a `build/venv-security/Scripts/python.exe android/usb_sync.py` paranccsal is szinkronizálhatsz a projektmappából. Mindkét eszközön ugyanaz a kapcsolati kód és futó Windows-app kell. A korlátozott méretű, titkosított átvitel törli az ideiglenes fájljait; a felhős kvótákat nem nullázza.

## Fejlesztés és adatvédelem

Az `android/build.ps1` teszteket, lintet, APK-építést, Android/Windows titkosítási együttműködési és aláírás-ellenőrzést futtat. JDK 21-et és Android SDK 36-ot használ. Az aláírókulcs és jelszava a repón kívül marad; frissítéshez őrizd meg az eredeti kulcsot.

[Adatvédelem](../PRIVACY.md), [biztonság](../SECURITY.md), [teszteredmények](../TESTING.md), [GitHub Issues](https://github.com/Blintboi/keep-improving/issues). Hibajelentésbe ne tegyél kapcsolati kódot, tokent vagy személyes használati adatbázist.
