import { klientZapisu } from "./dane";
import { xtbNaYahoo } from "./transakcje";

/**
 * Własne instrumenty — ręczne dopisywanie tickerów do uniwersum skanu.
 *
 * TA TABELA NALEŻY DO PYTHONA i to jest wyjątek wart odnotowania. Wszystkie
 * pozostałe tabele zakładane przez frontend (konta, sesje, alarmy, listy,
 * obserwowane) są sprawą samego frontendu. Tutaj jest odwrotnie: schemat
 * `wlasne_instrumenty` powstaje w `core/db.py`, a **czyta go codzienny skan**,
 * żeby dołożyć te tickery do uniwersum. Dlatego my tylko dopisujemy i kasujemy
 * wiersze — schematu nie tworzymy i nie zmieniamy.
 *
 * LISTA JEST WSPÓLNA DLA CAŁEJ INSTALACJI, nie per użytkownik — i tak ma być.
 * Skan jest jeden, więc „moje uniwersum" nie miałoby jak istnieć osobno dla
 * każdego konta. Watchlisty są per konto właśnie dlatego, że nie dotykają
 * skanu; tutaj jest odwrotnie.
 */

export type WlasnyInstrument = {
  ticker: string;
  nazwa: string;
  typ: string;
  dodano: string;
};

export const TYPY: Record<string, string> = {
  stock: "Akcja",
  etf: "ETF",
  index: "Indeks",
};

/** Zapora przed listą, która wydłużałaby skan w nieskończoność. */
export const LIMIT_WLASNYCH = 100;

export async function wlasneInstrumenty(): Promise<WlasnyInstrument[]> {
  try {
    const wynik = await klientZapisu().execute(
      `SELECT ticker, nazwa, typ, dodano FROM wlasne_instrumenty
       ORDER BY dodano DESC, ticker`,
    );
    return wynik.rows.map((w) => {
      const r = w as Record<string, unknown>;
      return {
        ticker: String(r.ticker),
        nazwa: String(r.nazwa ?? ""),
        typ: String(r.typ ?? "stock"),
        dodano: String(r.dodano ?? ""),
      };
    });
  } catch {
    // Tabeli nie ma dopiero co postawionej bazie — to nie błąd, tylko
    // informacja, że nikt jeszcze nic nie dopisał (schemat stworzy Python).
    return [];
  }
}

export type WynikDodania =
  | { ok: true }
  | { ok: false; powod: "duplikat" | "limit" | "blad" };

export async function dodajWlasny(
  ticker: string,
  nazwa: string,
  typ: string,
): Promise<WynikDodania> {
  const t = ticker.trim().toUpperCase();
  if (!t) return { ok: false, powod: "blad" };

  const istniejace = await wlasneInstrumenty();
  if (istniejace.length >= LIMIT_WLASNYCH) return { ok: false, powod: "limit" };
  if (istniejace.some((i) => i.ticker === t)) return { ok: false, powod: "duplikat" };

  try {
    await klientZapisu().execute({
      sql: `INSERT INTO wlasne_instrumenty (ticker, nazwa, typ, dodano)
            VALUES (?, ?, ?, ?)`,
      args: [
        t,
        nazwa.trim() || t,
        TYPY[typ] ? typ : "stock",
        new Date().toISOString().slice(0, 10),
      ],
    });
  } catch {
    return { ok: false, powod: "blad" };
  }
  return { ok: true };
}

export async function usunWlasny(ticker: string): Promise<void> {
  try {
    await klientZapisu().execute({
      sql: "DELETE FROM wlasne_instrumenty WHERE ticker = ?",
      args: [ticker.trim().toUpperCase()],
    });
  } catch {
    // Brak tabeli znaczy, że nie ma czego kasować.
  }
}

// ---------------------------------------------------------------------------
// Weryfikacja tickera w Yahoo
// ---------------------------------------------------------------------------

export type Sprawdzenie =
  | {
      ok: true;
      ticker: string;
      nazwa: string;
      cena: number;
      waluta: string;
      typ: string;
      gielda: string;
      poprawionyZ?: string;
    }
  | { ok: false; powod: string };

const CHART = "https://query1.finance.yahoo.com/v8/finance/chart/";

async function sprobuj(symbol: string): Promise<Sprawdzenie | null> {
  try {
    const odp = await fetch(`${CHART}${encodeURIComponent(symbol)}?range=1mo&interval=1d`, {
      headers: { "User-Agent": "xtb-screener/1.0" },
      signal: AbortSignal.timeout(15000),
      cache: "no-store",
    });
    if (!odp.ok) return null;
    const dane = await odp.json();
    const w = dane?.chart?.result?.[0];
    const meta = w?.meta;
    if (!meta) return null;

    // Ostatni wiersz bywa pusty (sesja w toku, dzień bez obrotu), więc bierzemy
    // ostatnie ZAMKNIĘCIE Z WARTOŚCIĄ. Bez tego użytkownik widziałby cenę
    // „nan" przy poprawnym instrumencie i słusznie uznał, że coś jest nie tak.
    const zamkniecia: unknown[] = w?.indicators?.quote?.[0]?.close ?? [];
    const ostatnia = [...zamkniecia]
      .reverse()
      .find((c) => typeof c === "number") as number | undefined;
    const cena = ostatnia ?? (typeof meta.regularMarketPrice === "number"
      ? meta.regularMarketPrice
      : undefined);
    if (cena === undefined) return null;

    const rodzaj = String(meta.instrumentType ?? "").toUpperCase();
    const typ =
      rodzaj === "ETF" || rodzaj === "MUTUALFUND"
        ? "etf"
        : rodzaj === "INDEX"
          ? "index"
          : "stock";

    return {
      ok: true,
      ticker: String(meta.symbol ?? symbol).toUpperCase(),
      nazwa: String(meta.longName ?? meta.shortName ?? symbol),
      cena: Math.round(cena * 100) / 100,
      waluta: String(meta.currency ?? ""),
      typ,
      gielda: String(meta.fullExchangeName ?? meta.exchangeName ?? ""),
    };
  } catch {
    return null;
  }
}

/**
 * Sprawdza, czy Yahoo zna instrument, ZANIM trafi on na listę do skanowania.
 *
 * Bez tego kroku literówka albo ticker w formacie XTB (`ALE.PL` zamiast
 * `ALE.WA`) wchodziłby na listę i cicho wypadał przy każdym nocnym skanie —
 * użytkownik widziałby instrument na liście, ale nigdy w tabelach.
 *
 * Sprawdzamy HISTORIĘ NOTOWAŃ, nie samą nazwę: dla nieistniejących symboli
 * Yahoo potrafi oddać metadane bez ani jednej ceny.
 */
export async function sprawdzInstrument(ticker: string): Promise<Sprawdzenie> {
  const surowy = String(ticker ?? "").trim().toUpperCase();
  if (!surowy) return { ok: false, powod: "Nie podano tickera." };

  const proba = await sprobuj(surowy);
  if (proba) return proba;

  // Druga próba po przetłumaczeniu z formatu XTB — użytkownik ma tickery
  // z platformy pod ręką i naturalnie wkleja właśnie je.
  const przetlumaczony = xtbNaYahoo(surowy);
  if (przetlumaczony !== surowy) {
    const druga = await sprobuj(przetlumaczony);
    if (druga && druga.ok) return { ...druga, poprawionyZ: surowy };
  }

  return {
    ok: false,
    powod:
      `Yahoo Finance nie zwraca notowań dla „${surowy}”. Sprawdź pisownię ` +
      `i sufiks giełdy — polskie spółki mają .WA (np. ALE.WA), niemieckie .DE, ` +
      `amerykańskie żadnego.`,
  };
}
