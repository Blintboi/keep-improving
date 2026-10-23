# Windows-megbízhatóság és kódaláírás

Áttekintés: 2026-10-23. A jelenlegi telepítő és fő program Authenticode-aláírása
hiányzik. A fájlok helyi `Get-AuthenticodeSignature` ellenőrzése `NotSigned`
eredményt adott. A Windows-verzióadatok és az ikon azonosítják az alkalmazást,
de nem tanúsítják a kiadót. A SHA-256 az egyezést ellenőrzi egy megbízhatóan
megszerzett referenciaértékhez; önmagában nem jelent Windows-jóváhagyást.

## Mitől függ, hogy futtatható-e?

- **SmartScreen:** a fájl és a kiadó ismertségét is figyeli. Egy új vagy ritkán
  letöltött, szabályosan aláírt verzió is kaphat figyelmeztetést. Az EV-tanúsítvány
  sem biztosít automatikus, azonnali mentességet. Következetes, hiteles kiadói
  aláírás segítheti a hírnév felépülését; az aláíratlan verziók önállóan építik
  a fájlhoz tartozó ismertséget. [Microsoft: SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).
- **Smart App Control:** az ismeretlen, aláíratlan kódot is blokkolhatja.
  A Microsoft útmutatója szerint a teljes futási láncot vizsgálni kell:
  a telepítőt, programokat, DLL-eket, segédprogramokat, telepítési/eltávolítási
  szkripteket és ideiglenes összetevőket is. A hiteles aláírást elismert
  tanúsítványszolgáltatótól kell megszerezni. [Microsoft: overview](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview),
  [aláírás](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control),
  [a teljes alkalmazáskód aláírása](https://learn.microsoft.com/en-us/windows/security/book/application-security-application-and-driver-control).
- **Defender-vírusriasztás:** egy konkrét téves kártevő/PUA-besorolás külön
  felülvizsgálatra küldhető a Microsoftnak. Ez a megállapított észlelésről szól;
  nem jelent általános, minden későbbi verzióra érvényes engedélyt.
  [Microsoft fejlesztői mintabeküldés](https://www.microsoft.com/en-us/wdsi/filesubmission),
  [beküldési útmutató](https://learn.microsoft.com/en-us/defender-xdr/submission-guide).

## Megvalósítható kiadói lépések

1. Hiteles aláírási szolgáltatás/tanúsítvány megszerzése. Nyílt forrású projekthez
   a [SignPath Foundation](https://signpath.org/) ingyenes lehetőséget kínál,
   [feltételekkel és külön jóváhagyással](https://signpath.org/terms.html).
   Ez egy lehetséges út; a projekt felvételéről a szolgáltató dönt. Alapítványi
   tanúsítvány esetén a kiadó az alapítvány lesz.
2. A teljes csomag aláírása a megfelelő sorrendben, időbélyeggel, majd a végleges
   telepítő ellenőrzése. Aláírás után kell újraszámolni a telepítő SHA-256-át,
   méretét és a frissítési verziólistát. A privát kulcs nem kerülhet a kliensbe
   vagy a nyilvános tárolóba.
3. Tiszta, ideiglenes tesztkörnyezetben ellenőrizni a teljes telepítést és
   eltávolítást, valamint az összes segédprogramot. A felhasználó működő gépén
   nem kapcsolunk át védelmi házirendet a teszt kedvéért.
4. Konkrét téves észlelésnél a pontos érintett fájlt és észlelési nevet kell
   felülvizsgálatra beadni. Fájlbeküldés és a szolgáltatói jelentkezés külön
   felhasználói intézkedés/jóváhagyás után történhet.

A Microsoft Artifact Signing szolgáltatása további lehetőség: a jelenlegi
feltételek szerint EU-s szervezetek számára elérhető, magánszemély fejlesztők
nyilvánosan megbízható aláírásánál az USA/Kanada régiókorlát érvényes. Magyar
magánszemélynél ezért ezt külön jogosultsági ellenőrzés nélkül nem feltételezzük.
[Microsoft feltételek](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart).

A program és a telepítő nem ad saját magának Defender-kivételt, nem telepít
önaláírt gyökértanúsítványt, és nem kapcsolja ki a SmartScreent vagy a Smart App
Controlt. Nem adható garancia arra, hogy minden gép és vállalati házirend
engedélyezi a futást. A Microsoft Store terjesztése további út lehet, de külön
csomagolást, jogosultságot és ellenőrzést igényel; a projekt elsődleges
terjesztési útja továbbra is a README közvetlen GitHub-letöltése.
