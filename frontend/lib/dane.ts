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
 *   - LOKALNY — plik ../data/history.db (praca na własnym komputerze).
 *
 * Klient @libsql/client obsługuje oba przez ten sam interfejs: adres zaczyna
 * się od "libsql://" albo od "file:". Dzięki temu ścieżka kodu jest jedna.
 */
import { createClient, type Client } from "@libsql/client";
import path from "node:path";

export type TrybBazy = "zdalny" | "lokalny";

/** Instrument w postaci, w jakiej zapisuje go skan (klucze po polsku). */
export type Instrument = {
  Ticker: string;
  Nazwa: string;
  Typ: string;
  Sektor?: string;
  Rynek?: string;
  Waluta?: string;
  Cena?: number | string;
  RSI?: number | string;
  pct_from_ath?: number | string;
  "Buy Score"?: number | string;
  "C/Z (P/E)"?: number | string;
  "Stopa Dyw. (%)"?: number | string;
  "Liczba flag"?: number | string;
  [klucz: string]: unknown;
};

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
    // process.cwd() wskazuje katalog frontend/, baza leży piętro wyżej.
    const plik = path.resolve(process.cwd(), "..", "data", "history.db");
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
 * Payload jest tekstem JSON. Uszkodzony wiersz pomijamy zamiast wywalać całą
 * stronę — jeden zepsuty rekord nie może kosztować dostępu do 1300 pozostałych.
 */
export async function migawka(dzien?: string): Promise<Migawka> {
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
  return { data: wybrana, tryb: tryb(), instrumenty };
}

/** Liczba w postaci nadającej się do sortowania — "BRAK" i null dają null. */
export function liczba(wartosc: unknown): number | null {
  if (typeof wartosc === "number" && Number.isFinite(wartosc)) return wartosc;
  if (typeof wartosc === "string") {
    const n = Number(wartosc.replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export type Statystyki = {
  wszystkie: number;
  akcje: number;
  etfy: number;
  bezFlag: number;
  sredniScore: number | null;
};

export function statystyki(instrumenty: Instrument[]): Statystyki {
  const score = instrumenty
    .map((i) => liczba(i["Buy Score"]))
    .filter((n): n is number => n !== null);

  return {
    wszystkie: instrumenty.length,
    akcje: instrumenty.filter((i) => i.Typ === "stock").length,
    etfy: instrumenty.filter((i) => i.Typ === "etf").length,
    bezFlag: instrumenty.filter((i) => liczba(i["Liczba flag"]) === 0).length,
    sredniScore: score.length
      ? score.reduce((a, b) => a + b, 0) / score.length
      : null,
  };
}

/** TOP N wg Buy Score. Instrumenty bez wyniku wypadają, nie lądują na końcu. */
export function najlepsze(instrumenty: Instrument[], ile = 10): Instrument[] {
  return instrumenty
    .filter((i) => i.Typ === "stock" && liczba(i["Buy Score"]) !== null)
    .sort((a, b) => (liczba(b["Buy Score"]) ?? 0) - (liczba(a["Buy Score"]) ?? 0))
    .slice(0, ile);
}
