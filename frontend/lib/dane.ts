/**
 * JEDYNY moduł w całym frontendzie, który dotyka bazy.
 *
 * To nie jest porządkowa fanaberia, tylko decyzja pod przenośność (faza 05
 * planu — przeniesienie na serwer NAS). Gdy kiedyś zamienimy Turso na lokalny
 * plik SQLite obok kontenera, zmiana ogranicza się do tego pliku — ekrany nic
 * o źródle danych nie wiedzą.
 *
 * Dwa tryby, wybierane tak samo jak w core/db.py po stronie Pythona:
 *   - ZDALNY  — gdy jest TURSO_DATABASE_URL (produkcja),
 *   - LOKALNY — plik SQLite (praca na własnym komputerze).
 *
 * Klient @libsql/client obsługuje oba przez ten sam interfejs: adres zaczyna
 * się od "libsql://" albo od "file:". Dzięki temu ścieżka kodu jest jedna.
 *
 * UWAGA: tego modułu NIE WOLNO importować z komponentu klienckiego — ciągnie
 * `node:path` i klienta bazy, których webpack nie spakuje do przeglądarki.
 * Czysta logika (typy, filtrowanie, statystyki) siedzi w lib/filtry.ts
 * właśnie po to, żeby przeglądarka miała skąd ją brać.
 */
import { createClient, type Client } from "@libsql/client";
import path from "node:path";
import type { Instrument } from "./filtry";

export type TrybBazy = "zdalny" | "lokalny";

export type Migawka = {
  data: string;
  tryb: TrybBazy;
  instrumenty: Instrument[];
};

export function tryb(): TrybBazy {
  return process.env.TURSO_DATABASE_URL ? "zdalny" : "lokalny";
}

let klientCache: Client | null = null;

function klient(): Client {
  if (klientCache) return klientCache;

  const url = process.env.TURSO_DATABASE_URL;
  if (url) {
    klientCache = createClient({
      url,
      authToken: process.env.TURSO_AUTH_TOKEN,
    });
  } else {
    // UWAGA: ścieżki NIE wolno liczyć wyłącznie względem katalogu roboczego.
    // Serwer w trybie standalone (ten sam, który pójdzie do Dockera) startuje
    // z .next/standalone, przez co domyślna ścieżka wskazywała
    // frontend/.next/data/history.db i połączenie się nie otwierało. Lokalnie
    // błąd nie występował — wyszedł dopiero przy uruchomieniu paczki
    // produkcyjnej.
    //
    // Stąd jawna zmienna środowiskowa; wartość domyślna służy tylko wygodzie
    // przy `npm run dev`.
    const plik =
      process.env.SCIEZKA_BAZY ??
      path.resolve(process.cwd(), "..", "data", "history.db");
    klientCache = createClient({ url: `file:${plik}` });
  }
  return klientCache;
}

/**
 * Gołe NaN / Infinity w pozycji WARTOŚCI — czyli po dwukropku, przecinku albo
 * otwarciu tablicy. Lookbehind i lookahead pilnują, żeby nie ruszyć tekstu
 * wewnątrz cudzysłowów: spółka o nazwie zawierającej "NaN" ma zostać nietknięta.
 */
const NIEPOPRAWNE_LITERALY = /(?<=[:[,]\s*)(-?Infinity|NaN)(?=\s*[,\]}])/g;

/**
 * Payloady zapisane przed 2026-09-04 zawierają gołe NaN, bo tak działa domyślnie
 * json.dumps w Pythonie. To nie jest poprawny JSON i JSON.parse je odrzuca.
 * Zapis został naprawiony (core/db.py), ale 21 istniejących migawek zostaje
 * takich, jakie są — nie da się przeskanować przeszłości. Stąd druga próba
 * z podmianą literałów na null.
 *
 * Najpierw parsowanie zwykłe: dla nowych, poprawnych danych to jedna szybka
 * ścieżka bez żadnej obróbki tekstu.
 */
function parsujPayload(tekst: string): Instrument | null {
  try {
    return JSON.parse(tekst) as Instrument;
  } catch {
    try {
      return JSON.parse(tekst.replace(NIEPOPRAWNE_LITERALY, "null")) as Instrument;
    } catch {
      return null;
    }
  }
}

/**
 * Bufor w pamięci procesu.
 *
 * Migawka to około 1350 wierszy po ~1,4 kB, czyli blisko 2 MB do wczytania
 * i sparsowania. Lokalnie niezauważalne, ale na hostingu bezstanowym każde
 * wejście na stronę płaciłoby ten koszt od nowa.
 *
 * Dane zmieniają się RAZ NA DOBĘ, po nocnym skanie — kwadrans nieświeżości
 * jest bez znaczenia, a różnica w szybkości ogromna (zmierzone: 366 ms → 83 ms).
 *
 * Celowo zwykła zmienna, a nie mechanizm buforowania Next.js: ma działać tak
 * samo w kontenerze na NAS-ie, gdzie tamtego nie będzie.
 */
const BUFOR_MS = 15 * 60 * 1000;
let bufor: { klucz: string; czas: number; dane: Migawka } | null = null;

/** Daty wszystkich migawek, od najnowszej. */
export async function daty(): Promise<string[]> {
  const wynik = await klient().execute(
    "SELECT DISTINCT scan_date FROM snapshots ORDER BY scan_date DESC",
  );
  return wynik.rows.map((r) => String(r.scan_date));
}

/**
 * Migawka z podanego dnia; bez argumentu — najnowsza.
 *
 * Uszkodzony wiersz pomijamy zamiast wywalać całą stronę — jeden zepsuty
 * rekord nie może kosztować dostępu do 1300 pozostałych.
 */
export async function migawka(dzien?: string): Promise<Migawka> {
  const klucz = dzien ?? "najnowsza";
  if (bufor && bufor.klucz === klucz && Date.now() - bufor.czas < BUFOR_MS) {
    return bufor.dane;
  }

  const dostepne = await daty();
  const wybrana = dzien ?? dostepne[0];
  if (!wybrana) {
    return { data: "brak", tryb: tryb(), instrumenty: [] };
  }

  const wynik = await klient().execute({
    sql: "SELECT payload FROM snapshots WHERE scan_date = ?",
    args: [wybrana],
  });

  const instrumenty: Instrument[] = [];
  for (const wiersz of wynik.rows) {
    const rekord = parsujPayload(String(wiersz.payload));
    if (rekord) instrumenty.push(rekord);
  }

  const dane: Migawka = { data: wybrana, tryb: tryb(), instrumenty };
  bufor = { klucz, czas: Date.now(), dane };
  return dane;
}

/**
 * Migawka, która NIE rzuca wyjątkiem.
 *
 * Wyjątek w komponencie serwerowym kończy się stroną błędu Next.js zamiast
 * naszej — sprawdzone. A nawet gdyby zadziałała, zabranie użytkownikowi całej
 * strony dlatego, że baza chwilowo nie odpowiada, jest przesadą: kafelki
 * nawigacji i tak da się pokazać.
 *
 * Zamiast tego zwracamy pusty zestaw plus opis problemu, a ekrany decydują,
 * co z tym zrobić.
 */
export async function migawkaBezpieczna(
  dzien?: string,
): Promise<Migawka & { blad: string | null }> {
  try {
    const m = await migawka(dzien);
    return { ...m, blad: null };
  } catch (e) {
    return {
      data: "brak",
      tryb: tryb(),
      instrumenty: [],
      blad: e instanceof Error ? e.message : String(e),
    };
  }
}
