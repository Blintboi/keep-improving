# Anticheat-kompatibilitási áttekintés — 2.24.0

Ellenőrzés dátuma: 2026. október 23.

## Kompetitív játékok és stabilitás a 2.24.0-ban

| Művelet | Nem védett/casual játék | Védett vagy ellenőrizhetetlen játék |
| --- | --- | --- |
| Játékidőmérés | Változatlan | Változatlan, korlátozott folyamatlekérdezés |
| Emlékeztető | Korábbi normál megjelenítés | Fókuszt nem kérő ablak; problémás teljes képernyős értesítési állapotban csak hang |
| Automatikus Escape | Korábbi, előtérhez kötött működés | Mindig tiltott; beleegyezés sem oldja fel |
| Overlay és játékkép | Korábbi beállítások szerint | Külön overlayengedély szükséges, ellenőrizhetetlen helyen nem oldható fel |
| Kényszerített minimalizálás | Korábbi játékkorlátozási/lefekvési szabályok | Alapból tiltott; külön minimalizálási engedély kell, ellenőrizhetetlen helyen nem oldható fel |
| Anticheat-segédfolyamat | Nem játék | Soha nem engedélyezhető |

A passzív értesítés már létrehozáskor nem kér fókuszt. A natív útvonalon
`WS_EX_NOACTIVATE` és `SWP_NOACTIVATE` szerepel; nincs Escape, aktiválás,
minimalizálás, játékablak- vagy grafikusmód-váltás. Ha a Windows értesítési
állapota nem alkalmas vizuális értesítésre, nem hozunk létre ablakot, csak a
beállított aszinkron hangot kérjük. Néma alkalmazásbeállítás vagy lejátszási hiba
esetén az értesítés várakozik a vizuális lehetőségre; hibás hangot legfeljebb
30 másodpercenként próbál újra. A rendszer/hangszóró tényleges hallhatóságát
nem tudjuk garantálni. Zárolt vagy le nem kérdezhető asztalnál várakozik.

A minimalizálás saját, alapból üres helyi engedélyt kap; az overlay korábbi
elfogadása nem jogosítja fel. Visszavonását a már sorban álló korlátozási
művelet és a lefekvési minimalizálás is újraellenőrzi. Enélkül a napi
korlátozás emlékeztetőit sem nyeljük el. Ez az AFK/meccselhagyási kockázatot
kezeli: a [CS2 hivatalos leírása](https://help.steampowered.com/en/faqs/view/7580-7BDB-1C9A-AC67)
szerint az inaktivitás vagy a kapcsolat/meccs elhagyása is korlátozáshoz
vezethet. Ez külön kérdés az anticheat csalás miatti tiltásától.

Az ellenőrzés a Python vezérlőt, Qt/Tk értesítéseket, natív folyamat-/ablak-API-kat,
képrögzítést, indítási útvonalakat és a C# RTSS-hidat érintette. A híd az RTSS
saját megosztott SDK-területét használja; nem játékfolyamat-memóriát olvas.
Nincs memóriaírás, távoli szál indítása, kényszerített játékfelfüggesztés,
anticheat-szolgáltatás/driver átállítása, Trusted Mode-ot gyengítő indítási
kapcsoló vagy az anticheat védelmének megkerülése. Nem kínálunk ilyen
funkciót beleegyezéssel sem. Egyetlen általános API-ról sem állítjuk, hogy
minden játékverzióval bizonyíthatóan bann- vagy crashmentes.

Az opcionális RTSS továbbra is külső grafikus hookot alkalmazhat, ezért
kockázatos játékoknál csak kifejezett engedéllyel használható. Egy másik program
által korábban betöltött RTSS-modult a Game Time Monitor nem tölti ki a
játékból, és a külön telepített RTSS globális beállításait nem írja át. A már
betöltött külső hook kockázatát egy engedély visszavonása nem tudja visszamenőleg
eltüntetni. Kiadói jóváhagyást vagy abszolút stabilitást nem ígérünk.

Az automatikus besorolás játékonkénti: ugyanazon EXE rangsorolt és offline
módját nem próbálja játékadatok olvasásával megkülönböztetni. Az ismert védett
játékoknál emiatt óvatos, a nem védett casual játékoknál megmarad a működés.

A 2.34.1-től az **Értesítések → Megjelenítés anticheates játékokban is**
kapcsoló szabályozza a védett játékok számlálóját és értesítéseit. Alapból
kikapcsolt. Bekapcsoláskor rövid tájékoztató, egy üres elfogadó négyzet és külön
engedélyező gomb jelenik meg. Az X, a Mégse és az Enter önmagában nem fogadja el.

A kapcsoló minden védett játékra vonatkozik, a helyi játék-kizárásokat megtartva.
A beleegyezés verziója és UTC-időpontja csak ezen a gépen mentődik, nem
szinkronizálódik. Kikapcsoláskor a megjelenítés és az RTSS-előkészítés leáll,
a korábbi megjelenési beállítások és játékonkénti engedélyrekordok megmaradnak.
A játékkép-előnézet továbbra is külön, játékonkénti engedélyt igényel.

Az ismeretlen telepítések, az anticheat-segédfolyamatok és az automatikus Escape
beleegyezés után is tiltottak. A tájékoztató technikai kockázatelfogadás,
önmagában nem jelent kiadói jóváhagyást vagy jogi garanciát.

A kiadók eltérően kezelik az overlayeket. Nem áll rendelkezésre a Game Time
Monitorra vonatkozó kiadói jóváhagyás vagy minden játékra érvényes garancia.
Az alábbi védelem csökkenti az ütközések esélyét; nem bizonyítja, hogy egy
ismeretlen vagy később módosított anticheat minden körülmények között elfogadja
a programot. Valódi anticheates online játékba a tesztelés során nem történt
overlay-bekapcsolás vagy billentyűküldés.

## Mit találtam a programban?

- A játékidőmérés az előtérben lévő ablakhoz tartozó folyamat elérési útját és
  létrehozási azonosítóját kérdezi le, `QUERY_LIMITED_INFORMATION` joggal.
  Nem olvas vagy ír játékmemóriát, és nem keres rejtett játékadatokat.
- Az asztali számláló külön, átkattintható Windows-ablak. Nem illeszt kódot a
  játékba. A külön telepített RTSS viszont a saját grafikus hookjait használja;
  ez a lényeges kompatibilitási kockázat.
- A korábbi automatikus RTSS-előkészítés anticheates játékhoz és egyes
  segédprogramokhoz is létrehozhatott `EnableHooking=1` profilt. Az új verzió
  az RTSS-integráció indításakor az ismert védett futtatható fájlok profiljaiban
  letiltja a hookingot és az OSD-t.
- A figyelmeztetés előtti automatikus Escape `SendInput` művelet volt. A védett
  játékoknál ez is kimarad. Az időmérés és a külön figyelmeztető ablak megmarad.
- A külön bekapcsolható játékkorlátozás/lefekvési szabály továbbra is normál
  Windows-ablakminimalizálást kérhet. Nem állít le vagy függeszt fel játékot,
  nem módosít anticheat-szolgáltatást vagy drivert.
  Ez a `ShowWindowAsync(hwnd, SW_MINIMIZE)` ablakkezelő hívás, billentyűküldés
  nélkül; a pontos előtérbeli folyamat azonosságát előtte újraellenőrzi.
  A [Microsoft dokumentációja](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindowasync)
  szerint a művelet ablakállapot-váltási eseményt küld. A kód áttekintése alapján
  nincs indok az overlayhez hasonló anticheat-tiltásra; ez technikai következtetés,
  nem minden kiadóra érvényes jóváhagyás. A minimalizálás nem szünetelteti a
  játékot, így az online inaktivitási szabályok továbbra is érvényesülhetnek.

## Automatikus védelem

A központi szabályzat ismert játékazonosítókat, játék-/EXE-neveket és helyi
anticheat-fájlok/mappák jelenlétét használja. Példák: CS2, VALORANT, League of
Legends, Destiny 2, Rainbow Six, Fortnite, PUBG, Rust, Apex; Easy Anti-Cheat,
BattlEye, EA anticheat/Javelin és további helyi jelölők. A Riot-forrású játékok
óvatosságból tiltást kapnak. A lista nem kiadói kompatibilitási tanúsítvány.

Beleegyezés nélkül az érintett játékoknál sem az asztali, sem az RTSS-overlay, sem a játékablak
képének lekérése, sem az előnézet miatti aktiválás/automatikus Escape nem fut.
A globális és a játékonkénti bekapcsolás önmagában nem írja felül ezt. A felület megmutatja
a tiltás okát, és a korai figyelmeztetés újra felugró ablakként működik.

Új profilnál az RTSS alapból ki van kapcsolva; a már elmentett választást az
adatmegőrzés miatt megtartja a frissítés, de az automatikus védelem arra is
érvényes. Az anticheat-segédfolyamatok kézi EXE-hozzárendeléssel sem lesznek
játékok. Beleegyezés nélkül a tiltott RTSS-profilt korábbi sikeres konfigurálás után sem engedi
visszakapcsolni a backend. Sikertelen profiltiltáskor további RTSS-aktiválás nem
történik. A globális RTSS-beállítások és az FPS-korlátok megmaradnak.

A mappaellenőrzés néhány rögzített helyre és könyvtárbejegyzés-számra korlátozott,
eredménye legfeljebb 60 másodpercig gyorsítótárazott. Nem járja be a teljes
játékkönyvtárat minden képkockánál. Olvashatatlan, túl nagy vagy hálózati hely
esetén az overlay tiltást kap. Egyéni anticheat, eltérő telepítési szerkezet vagy
ismeretlen új játék felismerése nem garantált.

A védelem nem távolít el már betöltött külső DLL-t, és nem zár be önállóan
elindított más overlayprogramot. Nem kérjük és nem állítjuk át a játékot kevésbé
védett módba, nem kapcsoljuk ki az anticheatet, és nem használunk megkerülést.

## Hivatalos források

- [Valve: CS2 Trusted Mode](https://help.steampowered.com/en/faqs/view/09A0-4879-4353-EF95):
  a védett mód blokkolja a külső injektálást; a célzott folyamatmanipulációra
  külön szankciók vonatkoznak. A program nem módosítja az indítási opciókat.
- [Bungie: Destiny 2 és külső alkalmazások](https://help.bungie.net/hc/en-us/articles/360049199891-Destiny-2-PC-and-Third-Party-Application-Feature-Compatibility):
  a kliensbe kódot illesztő overlayfunkciók nem kompatibilisek. A Bungie a szokásos
  alkalmazások, például RTSS puszta használatát nem tekinti önmagában tiltási oknak.
- [BattlEye támogatás](https://www.battleye.com/support/): a nem csaló overlayek
  puszta használata nem globális tiltási ok. Ez nem jelent minden játékra és
  minden külső programra szóló jóváhagyást.
- [Riot: külső alkalmazások](https://support.riotgames.com/en-us/riot/events/third-party-applications):
  a tisztességtelen előny és az automatizált játékbeli műveletek kifogásolhatók;
  nincs teljes lista az összes biztonságos alkalmazásról.
- [Riot Vanguard és League/TFT](https://support.riotgames.com/en-us/league-of-legends/performance/riot-vanguard-faq-league-of-legends):
  a Vanguard a League klienshez és a PC-s TFT-hez is szükséges.
- [EA Javelin telepítés és felismerés](https://help.ea.com/en//articles/platforms/pc-ea-anticheat/):
  a védett játék telepítési mappájában anticheat-fájlok találhatók.

A következtetés saját óvatos fejlesztői szabályzat: a szolgáltatók nem követelik
egységesen minden overlay letiltását, de a program az érintett játékoknál ezt
választja automatikus alapvédelemként.
