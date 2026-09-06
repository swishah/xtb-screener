import { klientZapisu } from "./dane";

/**
 * Alarmy cenowe — progi zapisane per użytkownik, sprawdzane przez codzienny skan.
 *
 * CZEGO TU NIE MA I DLACZEGO: alarmu nie da się postawić na wykresie
 * TradingView. Wykres jest osadzony jako <iframe> z obcej domeny, więc nie
 * widzimy jego skali cenowej ani tego, czy użytkownik przed chwilą nie
 * przewinął albo nie przełączył skali na logarytmiczną. Przeliczenie pozycji
 * na cenę byłoby zgadywaniem, a błąd objawiłby się alarmem na cenie, której
 * nikt nie wskazał. Dlatego linię przeciąga się po NASZYM wykresie, gdzie
 * przelicznik jest nasz i dokładny.
 *
 * GRANULACJA JEST DOBOWA. Sprawdza je skan (pon-pt, 22:30 UTC), więc to nie
 * jest alert w czasie rzeczywistym i nie zastąpi alarmu na tradingview.com.
 * Skan porównuje jednak MAKSIMUM I MINIMUM DNIA, a nie zamknięcie — dzięki
 * temu przebicie w ciągu dnia, które do wieczora się cofnęło, też zostanie
 * złapane.
 */

export type Kierunek = "powyzej" | "ponizej";

export type Alarm = {
  id: number;
  ticker: string;
  nazwa: string;
  kierunek: Kierunek;
  cena: number;
  waluta: string;
  utworzony: string;
  wyzwolony: string | null;
  cenaWyzwolenia: number | null;
};

/** Ile alarmów może mieć jedno konto. Zapora przed zapchaniem skanu. */
export const LIMIT_ALARMOW = 200;

const SCHEMAT = [
  `CREATE TABLE IF NOT EXISTS alarmy (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     uzytkownik_id INTEGER NOT NULL,
     ticker TEXT NOT NULL,
     nazwa TEXT NOT NULL DEFAULT '',
     kierunek TEXT NOT NULL,
     cena REAL NOT NULL,
     waluta TEXT NOT NULL DEFAULT '',
     utworzony TEXT NOT NULL,
     wyzwolony TEXT,
     cena_wyzwolenia REAL
   )`,
  "CREATE INDEX IF NOT EXISTS idx_alarmy_uzytkownik ON alarmy(uzytkownik_id)",
  // Skan przechodzi po alarmach czekających — indeks po tickerze oszczędza mu
  // przemiatania całej tabeli dla każdego instrumentu.
  "CREATE INDEX IF NOT EXISTS idx_alarmy_ticker ON alarmy(ticker)",
];

let schematGotowy = false;

async function zapewnijSchemat(): Promise<void> {
  if (schematGotowy) return;
  const db = klientZapisu();
  for (const polecenie of SCHEMAT) await db.execute(polecenie);
  schematGotowy = true;
}

function naAlarm(w: Record<string, unknown>): Alarm {
  return {
    id: Number(w.id),
    ticker: String(w.ticker),
    nazwa: String(w.nazwa ?? ""),
    kierunek: w.kierunek === "ponizej" ? "ponizej" : "powyzej",
    cena: Number(w.cena),
    waluta: String(w.waluta ?? ""),
    utworzony: String(w.utworzony),
    wyzwolony: w.wyzwolony ? String(w.wyzwolony) : null,
    cenaWyzwolenia:
      w.cena_wyzwolenia === null || w.cena_wyzwolenia === undefined
        ? null
        : Number(w.cena_wyzwolenia),
  };
}

export async function alarmyUzytkownika(uzytkownikId: number): Promise<Alarm[]> {
  await zapewnijSchemat();
  const wynik = await klientZapisu().execute({
    // Wyzwolone na górze — to one wymagają uwagi. Dalej najnowsze.
    sql: `SELECT * FROM alarmy WHERE uzytkownik_id = ?
          ORDER BY (wyzwolony IS NOT NULL) DESC, id DESC`,
    args: [uzytkownikId],
  });
  return wynik.rows.map((r) => naAlarm(r as unknown as Record<string, unknown>));
}

export async function alarmySpolki(
  uzytkownikId: number,
  ticker: string,
): Promise<Alarm[]> {
  await zapewnijSchemat();
  const wynik = await klientZapisu().execute({
    sql: "SELECT * FROM alarmy WHERE uzytkownik_id = ? AND ticker = ? ORDER BY cena DESC",
    args: [uzytkownikId, ticker],
  });
  return wynik.rows.map((r) => naAlarm(r as unknown as Record<string, unknown>));
}

export async function dodajAlarm(
  uzytkownikId: number,
  dane: {
    ticker: string;
    nazwa: string;
    kierunek: Kierunek;
    cena: number;
    waluta: string;
  },
): Promise<{ ok: true } | { ok: false; powod: string }> {
  if (!dane.ticker) return { ok: false, powod: "brak-tickera" };
  if (!Number.isFinite(dane.cena) || dane.cena <= 0) {
    return { ok: false, powod: "cena" };
  }

  await zapewnijSchemat();
  const db = klientZapisu();

  const ile = await db.execute({
    sql: "SELECT COUNT(*) AS n FROM alarmy WHERE uzytkownik_id = ?",
    args: [uzytkownikId],
  });
  if (Number((ile.rows[0] as unknown as { n: number }).n) >= LIMIT_ALARMOW) {
    return { ok: false, powod: "limit" };
  }

  // Ten sam próg w tę samą stronę nie ma po co istnieć dwa razy — przy
  // przeciąganiu linii łatwo o przypadkowe podwojenie.
  const duplikat = await db.execute({
    sql: `SELECT id FROM alarmy WHERE uzytkownik_id = ? AND ticker = ?
          AND kierunek = ? AND ABS(cena - ?) < 0.005 AND wyzwolony IS NULL`,
    args: [uzytkownikId, dane.ticker, dane.kierunek, dane.cena],
  });
  if (duplikat.rows.length > 0) return { ok: false, powod: "duplikat" };

  await db.execute({
    sql: `INSERT INTO alarmy
          (uzytkownik_id, ticker, nazwa, kierunek, cena, waluta, utworzony)
          VALUES (?, ?, ?, ?, ?, ?, ?)`,
    args: [
      uzytkownikId,
      dane.ticker,
      dane.nazwa,
      dane.kierunek,
      Math.round(dane.cena * 10000) / 10000,
      dane.waluta,
      new Date().toISOString(),
    ],
  });
  return { ok: true };
}

/**
 * Kasuje alarm. Warunek na uzytkownik_id jest tu KLUCZOWY, nie ozdobny:
 * bez niego wystarczyłoby zgadnąć cudze id, żeby skasować cudzy alarm.
 */
export async function usunAlarm(
  uzytkownikId: number,
  id: number,
): Promise<void> {
  await zapewnijSchemat();
  await klientZapisu().execute({
    sql: "DELETE FROM alarmy WHERE id = ? AND uzytkownik_id = ?",
    args: [id, uzytkownikId],
  });
}

/** Ustawia wyzwolony alarm z powrotem na czekający — po zmianie zdania. */
export async function wznowAlarm(
  uzytkownikId: number,
  id: number,
): Promise<void> {
  await zapewnijSchemat();
  await klientZapisu().execute({
    sql: `UPDATE alarmy SET wyzwolony = NULL, cena_wyzwolenia = NULL
          WHERE id = ? AND uzytkownik_id = ?`,
    args: [id, uzytkownikId],
  });
}
