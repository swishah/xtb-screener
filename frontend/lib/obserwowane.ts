import { klientZapisu } from "./dane";

/**
 * Watchlist — obserwowane spółki z notatkami, PER UŻYTKOWNIK.
 *
 * DLACZEGO NOWA TABELA, A NIE STARA `watchlist`. Streamlitowa watchlist ma
 * `ticker` jako klucz główny i ani jednej kolumny o użytkowniku — to jedna
 * lista na całą instalację. Od czasu wprowadzenia kont (2026-09-06) jest to
 * niespójne z resztą: alarmy są per konto, a watchlist byłaby wspólna dla
 * wszystkich. SQLite nie pozwala dopisać kolumny do klucza głównego bez
 * przebudowy tabeli, a przebudowa cudzej tabeli w locie to ostatnia rzecz,
 * jakiej chcemy przy bazie z prawdziwymi danymi.
 *
 * Dlatego idziemy dokładnie tak jak przy alarmach: tabelę zakłada FRONTEND,
 * bo to sprawa kont, a konta należą do frontendu. Stara `watchlist` zostaje
 * nietknięta — jest kopią zapasową i nadal obsługuje Streamlita.
 *
 * PRZENIESIENIE STAREJ LISTY JEST RĘCZNE I JAWNE. Nie zgadujemy, do kogo
 * należą wpisy sprzed kont: gdyby kont było kilka, każdy przydział byłby
 * strzałem. Zamiast tego strona pokazuje przycisk, gdy stara lista coś
 * zawiera — patrz `staraWatchlista()`. Kopiujemy, nie przenosimy, więc
 * pomyłka nic nie niszczy.
 */

export type Obserwowana = {
  ticker: string;
  notatka: string;
  dodano: string;
};

/** Ile spółek może obserwować jedno konto. */
export const LIMIT_OBSERWOWANYCH = 200;

/** Górna granica długości notatki — pole opisowe, nie magazyn na esej. */
export const MAKS_NOTATKA = 500;

const SCHEMAT = [
  `CREATE TABLE IF NOT EXISTS obserwowane (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     uzytkownik_id INTEGER NOT NULL,
     ticker TEXT NOT NULL,
     notatka TEXT NOT NULL DEFAULT '',
     dodano TEXT NOT NULL
   )`,
  // Jedna spółka raz na koncie. Pilnuje tego BAZA, a nie sprawdzenie w kodzie
  // — dwa równoległe żądania przeszłyby przez sprawdzenie i zrobiły duplikat.
  `CREATE UNIQUE INDEX IF NOT EXISTS idx_obserwowane_para
     ON obserwowane(uzytkownik_id, ticker)`,
];

let schematGotowy = false;

async function zapewnijSchemat(): Promise<void> {
  if (schematGotowy) return;
  const db = klientZapisu();
  for (const polecenie of SCHEMAT) await db.execute(polecenie);
  schematGotowy = true;
}

function naObserwowana(w: Record<string, unknown>): Obserwowana {
  return {
    ticker: String(w.ticker),
    notatka: String(w.notatka ?? ""),
    dodano: String(w.dodano),
  };
}

function terazISO(): string {
  return new Date().toISOString();
}

export async function obserwowaneUzytkownika(
  uzytkownikId: number,
): Promise<Obserwowana[]> {
  await zapewnijSchemat();
  const wynik = await klientZapisu().execute({
    sql: `SELECT ticker, notatka, dodano FROM obserwowane
          WHERE uzytkownik_id = ? ORDER BY dodano DESC`,
    args: [uzytkownikId],
  });
  return wynik.rows.map((w) => naObserwowana(w as Record<string, unknown>));
}

export async function czyObserwuje(
  uzytkownikId: number,
  ticker: string,
): Promise<boolean> {
  await zapewnijSchemat();
  const wynik = await klientZapisu().execute({
    sql: "SELECT 1 FROM obserwowane WHERE uzytkownik_id = ? AND ticker = ?",
    args: [uzytkownikId, ticker],
  });
  return wynik.rows.length > 0;
}

export type WynikDodania =
  | { ok: true }
  | { ok: false; powod: "limit" | "duplikat" | "brakTickera" };

export async function dodajObserwowana(
  uzytkownikId: number,
  ticker: string,
  notatka = "",
): Promise<WynikDodania> {
  const t = ticker.trim().toUpperCase();
  if (!t) return { ok: false, powod: "brakTickera" };

  await zapewnijSchemat();
  const db = klientZapisu();

  const ile = await db.execute({
    sql: "SELECT COUNT(*) AS n FROM obserwowane WHERE uzytkownik_id = ?",
    args: [uzytkownikId],
  });
  if (Number((ile.rows[0] as unknown as { n: number }).n) >= LIMIT_OBSERWOWANYCH) {
    return { ok: false, powod: "limit" };
  }

  try {
    await db.execute({
      sql: `INSERT INTO obserwowane (uzytkownik_id, ticker, notatka, dodano)
            VALUES (?, ?, ?, ?)`,
      args: [uzytkownikId, t, notatka.slice(0, MAKS_NOTATKA), terazISO()],
    });
  } catch {
    // Jedyny powód, dla którego wstawienie może się tu wywrócić, to złamanie
    // indeksu jednoznaczności — czyli spółka już jest na liście.
    return { ok: false, powod: "duplikat" };
  }
  return { ok: true };
}

/**
 * Kasuje wpis. Warunek na `uzytkownik_id` jest w SAMYM SQL-u i to nie jest
 * ozdoba: bez niego podanie cudzego tickera kasowałoby cudzy wpis.
 */
export async function usunObserwowana(
  uzytkownikId: number,
  ticker: string,
): Promise<void> {
  await zapewnijSchemat();
  await klientZapisu().execute({
    sql: "DELETE FROM obserwowane WHERE uzytkownik_id = ? AND ticker = ?",
    args: [uzytkownikId, ticker.trim().toUpperCase()],
  });
}

export async function zapiszNotatke(
  uzytkownikId: number,
  ticker: string,
  notatka: string,
): Promise<void> {
  await zapewnijSchemat();
  await klientZapisu().execute({
    sql: `UPDATE obserwowane SET notatka = ?
          WHERE uzytkownik_id = ? AND ticker = ?`,
    args: [
      notatka.slice(0, MAKS_NOTATKA),
      uzytkownikId,
      ticker.trim().toUpperCase(),
    ],
  });
}

/**
 * Zawartość STAREJ, wspólnej watchlisty ze Streamlita.
 *
 * Tabela należy do Pythona (`core/db.py`) i my jej wyłącznie CZYTAMY. Gdy
 * jej nie ma — a nie ma jej w świeżej bazie — zapytanie rzuca wyjątkiem;
 * to nie jest błąd, tylko informacja, że nie ma czego przenosić.
 */
export async function staraWatchlista(): Promise<Obserwowana[]> {
  try {
    const wynik = await klientZapisu().execute(
      "SELECT ticker, note, added_date FROM watchlist ORDER BY added_date DESC",
    );
    return wynik.rows.map((w) => {
      const r = w as Record<string, unknown>;
      return {
        ticker: String(r.ticker),
        notatka: String(r.note ?? ""),
        dodano: String(r.added_date ?? ""),
      };
    });
  } catch {
    return [];
  }
}

/**
 * Kopiuje starą wspólną watchlistę na konto. Zwraca liczbę dopisanych spółek.
 *
 * KOPIUJE, NIE PRZENOSI — stara tabela zostaje nietknięta, więc powtórzenie
 * niczego nie psuje, a Streamlit dalej widzi swoje. Wpisy, które już są na
 * koncie, pomijamy: notatki zrobione w nowej wersji mają pierwszeństwo przed
 * tym, co przyszło ze starej.
 */
export async function przeniesStaraWatchliste(
  uzytkownikId: number,
): Promise<number> {
  const stare = await staraWatchlista();
  let dopisane = 0;
  for (const w of stare) {
    const wynik = await dodajObserwowana(uzytkownikId, w.ticker, w.notatka);
    if (wynik.ok) dopisane += 1;
  }
  return dopisane;
}
