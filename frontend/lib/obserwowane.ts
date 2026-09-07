import { klientZapisu } from "./dane";

/**
 * Watchlisty — KILKA nazwanych list na konto, każda z własnymi spółkami
 * i notatkami.
 *
 * DLACZEGO NOWA TABELA, A NIE STARA `watchlist`. Streamlitowa watchlist ma
 * `ticker` jako klucz główny i ani jednej kolumny o użytkowniku — to jedna
 * lista na całą instalację. Od wprowadzenia kont jest to niespójne z resztą:
 * alarmy są per konto, watchlist byłaby wspólna dla wszystkich. SQLite nie
 * pozwala dopisać kolumny do klucza głównego bez przebudowy tabeli, a
 * przebudowa cudzej tabeli w locie przy bazie z prawdziwymi danymi to ostatnia
 * rzecz, jakiej chcemy. Idziemy jak przy alarmach: tabele zakłada FRONTEND,
 * bo to sprawa kont. Stara `watchlist` zostaje nietknięta i nadal obsługuje
 * Streamlita.
 *
 * PRZEJŚCIE Z JEDNEJ LISTY NA WIELE (2026-09-07) jest zrobione tak, żeby nie
 * dotknąć danych, które już są. `obserwowane` dostaje kolumnę `lista_id`
 * przez `ALTER TABLE` (SQLite to potrafi), a stary indeks jednoznaczności
 * (użytkownik, ticker) ustępuje nowemu (użytkownik, lista, ticker) — indeks
 * wolno podmienić, w odróżnieniu od klucza głównego. Wiersze sprzed zmiany
 * mają `lista_id = 0` i przy pierwszym wejściu trafiają do listy domyślnej.
 *
 * TA SAMA SPÓŁKA MOŻE BYĆ NA KILKU LISTACH i tak ma być — „Dywidendowe"
 * i „Kupione" to dwa różne powody obserwowania, każdy z własną notatką.
 */

export type Lista = {
  id: number;
  nazwa: string;
  utworzona: string;
  /** Ile spółek jest na tej liście. Liczone jednym zapytaniem dla wszystkich. */
  ile: number;
};

export type Obserwowana = {
  ticker: string;
  notatka: string;
  dodano: string;
};

/** Ile spółek może obserwować jedno konto ŁĄCZNIE, we wszystkich listach. */
export const LIMIT_OBSERWOWANYCH = 200;

/** Ile list może mieć jedno konto. */
export const LIMIT_LIST = 20;

/** Górna granica długości notatki — pole opisowe, nie magazyn na esej. */
export const MAKS_NOTATKA = 500;

/** Górna granica długości nazwy listy. */
export const MAKS_NAZWA = 60;

/** Nazwa listy zakładanej automatycznie, gdy konto nie ma jeszcze żadnej. */
export const LISTA_DOMYSLNA = "Obserwowane";

const SCHEMAT = [
  `CREATE TABLE IF NOT EXISTS listy (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     uzytkownik_id INTEGER NOT NULL,
     nazwa TEXT NOT NULL,
     utworzona TEXT NOT NULL
   )`,
  // Dwie listy o tej samej nazwie na jednym koncie nie mają sensu — a bez
  // indeksu dwa równoległe żądania przeszłyby przez sprawdzenie w kodzie.
  `CREATE UNIQUE INDEX IF NOT EXISTS idx_listy_nazwa
     ON listy(uzytkownik_id, nazwa)`,
  `CREATE TABLE IF NOT EXISTS obserwowane (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     uzytkownik_id INTEGER NOT NULL,
     ticker TEXT NOT NULL,
     notatka TEXT NOT NULL DEFAULT '',
     dodano TEXT NOT NULL
   )`,
];

let schematGotowy = false;

async function zapewnijSchemat(): Promise<void> {
  if (schematGotowy) return;
  const db = klientZapisu();
  for (const polecenie of SCHEMAT) await db.execute(polecenie);

  // Kolumna `lista_id` dochodzi osobno, bo `CREATE TABLE IF NOT EXISTS` nie
  // rusza tabeli, która już istnieje. `ALTER TABLE` wywala się, gdy kolumna
  // jest — więc najpierw pytamy schemat, zamiast łykać wyjątek w ciemno.
  const kolumny = await db.execute("PRAGMA table_info(obserwowane)");
  const maListe = kolumny.rows.some(
    (w) => String((w as Record<string, unknown>).name) === "lista_id",
  );
  if (!maListe) {
    await db.execute(
      "ALTER TABLE obserwowane ADD COLUMN lista_id INTEGER NOT NULL DEFAULT 0",
    );
  }

  // Stary indeks pilnował jednej spółki na KONTO. Teraz pilnujemy jednej
  // spółki na LISTĘ — ta sama spółka na dwóch listach jest w porządku.
  await db.execute("DROP INDEX IF EXISTS idx_obserwowane_para");
  await db.execute(
    `CREATE UNIQUE INDEX IF NOT EXISTS idx_obserwowane_lista
       ON obserwowane(uzytkownik_id, lista_id, ticker)`,
  );
  schematGotowy = true;
}

function terazISO(): string {
  return new Date().toISOString();
}

/**
 * Listy użytkownika. Zakłada domyślną, gdy konto nie ma żadnej, i przypisuje
 * do niej wiersze sprzed wprowadzenia list (`lista_id = 0`).
 *
 * To jedyne miejsce, które tworzy listy „samo z siebie" — dzięki temu każda
 * pozostała funkcja może założyć, że lista istnieje.
 */
export async function listyUzytkownika(uzytkownikId: number): Promise<Lista[]> {
  await zapewnijSchemat();
  const db = klientZapisu();

  let wynik = await db.execute({
    sql: "SELECT id, nazwa, utworzona FROM listy WHERE uzytkownik_id = ? ORDER BY id",
    args: [uzytkownikId],
  });

  if (wynik.rows.length === 0) {
    await db.execute({
      sql: "INSERT INTO listy (uzytkownik_id, nazwa, utworzona) VALUES (?, ?, ?)",
      args: [uzytkownikId, LISTA_DOMYSLNA, terazISO()],
    });
    wynik = await db.execute({
      sql: "SELECT id, nazwa, utworzona FROM listy WHERE uzytkownik_id = ? ORDER BY id",
      args: [uzytkownikId],
    });
  }

  const listy = wynik.rows.map((w) => {
    const r = w as Record<string, unknown>;
    return {
      id: Number(r.id),
      nazwa: String(r.nazwa),
      utworzona: String(r.utworzona),
      ile: 0,
    };
  });

  // Wiersze sprzed wprowadzenia list trafiają do pierwszej listy konta.
  // Idempotentne: po pierwszym przebiegu nie ma już czego przenosić.
  await db.execute({
    sql: "UPDATE obserwowane SET lista_id = ? WHERE uzytkownik_id = ? AND lista_id = 0",
    args: [listy[0].id, uzytkownikId],
  });

  const liczby = await db.execute({
    sql: `SELECT lista_id, COUNT(*) AS ile FROM obserwowane
          WHERE uzytkownik_id = ? GROUP BY lista_id`,
    args: [uzytkownikId],
  });
  const wgListy = new Map<number, number>();
  for (const w of liczby.rows) {
    const r = w as Record<string, unknown>;
    wgListy.set(Number(r.lista_id), Number(r.ile));
  }
  for (const l of listy) l.ile = wgListy.get(l.id) ?? 0;
  return listy;
}

export type WynikListy =
  | { ok: true; id: number }
  | { ok: false; powod: "limit" | "duplikat" | "pustaNazwa" };

export async function dodajListe(
  uzytkownikId: number,
  nazwa: string,
): Promise<WynikListy> {
  const n = nazwa.trim().slice(0, MAKS_NAZWA);
  if (!n) return { ok: false, powod: "pustaNazwa" };

  const istniejace = await listyUzytkownika(uzytkownikId);
  if (istniejace.length >= LIMIT_LIST) return { ok: false, powod: "limit" };

  const db = klientZapisu();
  try {
    await db.execute({
      sql: "INSERT INTO listy (uzytkownik_id, nazwa, utworzona) VALUES (?, ?, ?)",
      args: [uzytkownikId, n, terazISO()],
    });
  } catch {
    return { ok: false, powod: "duplikat" };
  }
  const wynik = await db.execute({
    sql: "SELECT id FROM listy WHERE uzytkownik_id = ? AND nazwa = ?",
    args: [uzytkownikId, n],
  });
  return { ok: true, id: Number((wynik.rows[0] as Record<string, unknown>).id) };
}

export async function zmienNazweListy(
  uzytkownikId: number,
  listaId: number,
  nazwa: string,
): Promise<boolean> {
  const n = nazwa.trim().slice(0, MAKS_NAZWA);
  if (!n) return false;
  await zapewnijSchemat();
  try {
    await klientZapisu().execute({
      sql: "UPDATE listy SET nazwa = ? WHERE id = ? AND uzytkownik_id = ?",
      args: [n, listaId, uzytkownikId],
    });
  } catch {
    return false; // nazwa zajęta
  }
  return true;
}

export type WynikUsunieciaListy =
  | { ok: true }
  | { ok: false; powod: "ostatnia" | "niepusta"; ile?: number };

/**
 * Kasuje listę. NIE kasuje list niepustych ani ostatniej.
 *
 * Bez JavaScriptu nie ma okna „na pewno?", więc jedno kliknięcie kasowałoby
 * od razu — a razem z listą przepadłyby wszystkie notatki, które ktoś pisał
 * miesiącami. Dlatego wymagamy, żeby lista była pusta: przeniesienie spółek
 * gdzie indziej albo ich skasowanie to świadome kroki, a nie skutek uboczny.
 */
export async function usunListe(
  uzytkownikId: number,
  listaId: number,
): Promise<WynikUsunieciaListy> {
  const listy = await listyUzytkownika(uzytkownikId);
  if (listy.length <= 1) return { ok: false, powod: "ostatnia" };

  const lista = listy.find((l) => l.id === listaId);
  if (lista && lista.ile > 0) {
    return { ok: false, powod: "niepusta", ile: lista.ile };
  }

  await klientZapisu().execute({
    sql: "DELETE FROM listy WHERE id = ? AND uzytkownik_id = ?",
    args: [listaId, uzytkownikId],
  });
  return { ok: true };
}

export async function obserwowaneZListy(
  uzytkownikId: number,
  listaId: number,
): Promise<Obserwowana[]> {
  await zapewnijSchemat();
  const wynik = await klientZapisu().execute({
    sql: `SELECT ticker, notatka, dodano FROM obserwowane
          WHERE uzytkownik_id = ? AND lista_id = ? ORDER BY dodano DESC`,
    args: [uzytkownikId, listaId],
  });
  return wynik.rows.map((w) => {
    const r = w as Record<string, unknown>;
    return {
      ticker: String(r.ticker),
      notatka: String(r.notatka ?? ""),
      dodano: String(r.dodano),
    };
  });
}

/** Czy spółka jest na KTÓREJKOLWIEK liście konta — do gwiazdki na profilu. */
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
  listaId: number,
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
      sql: `INSERT INTO obserwowane (uzytkownik_id, lista_id, ticker, notatka, dodano)
            VALUES (?, ?, ?, ?, ?)`,
      args: [uzytkownikId, listaId, t, notatka.slice(0, MAKS_NOTATKA), terazISO()],
    });
  } catch {
    // Jedyny powód, dla którego wstawienie może się tu wywrócić, to złamanie
    // indeksu jednoznaczności — czyli spółka już jest NA TEJ liście.
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
  listaId: number,
  ticker: string,
): Promise<void> {
  await zapewnijSchemat();
  await klientZapisu().execute({
    sql: `DELETE FROM obserwowane
          WHERE uzytkownik_id = ? AND lista_id = ? AND ticker = ?`,
    args: [uzytkownikId, listaId, ticker.trim().toUpperCase()],
  });
}

/**
 * Kasuje spółkę ze WSZYSTKICH list konta.
 *
 * Tego używa gwiazdka na profilu spółki: pokazuje ona „obserwujesz", gdy
 * spółka jest na którejkolwiek liście, więc jedno kliknięcie musi znaczyć
 * „przestaję obserwować", a nie „usuń z jednej z list i zostaw resztę".
 */
export async function usunZeWszystkichList(
  uzytkownikId: number,
  ticker: string,
): Promise<void> {
  await zapewnijSchemat();
  await klientZapisu().execute({
    sql: "DELETE FROM obserwowane WHERE uzytkownik_id = ? AND ticker = ?",
    args: [uzytkownikId, ticker.trim().toUpperCase()],
  });
}

/** Id pierwszej listy konta; zakłada domyślną, gdy nie ma żadnej. */
export async function pierwszaLista(uzytkownikId: number): Promise<number> {
  const listy = await listyUzytkownika(uzytkownikId);
  return listy[0].id;
}

/** Przenosi spółkę na inną listę. Notatka idzie razem z nią. */
export async function przeniesDoListy(
  uzytkownikId: number,
  zListy: number,
  naListe: number,
  ticker: string,
): Promise<boolean> {
  if (zListy === naListe) return true;
  await zapewnijSchemat();
  try {
    await klientZapisu().execute({
      sql: `UPDATE obserwowane SET lista_id = ?
            WHERE uzytkownik_id = ? AND lista_id = ? AND ticker = ?`,
      args: [naListe, uzytkownikId, zListy, ticker.trim().toUpperCase()],
    });
  } catch {
    return false; // spółka jest już na liście docelowej
  }
  return true;
}

export async function zapiszNotatke(
  uzytkownikId: number,
  listaId: number,
  ticker: string,
  notatka: string,
): Promise<void> {
  await zapewnijSchemat();
  await klientZapisu().execute({
    sql: `UPDATE obserwowane SET notatka = ?
          WHERE uzytkownik_id = ? AND lista_id = ? AND ticker = ?`,
    args: [
      notatka.slice(0, MAKS_NOTATKA),
      uzytkownikId,
      listaId,
      ticker.trim().toUpperCase(),
    ],
  });
}

/**
 * Zawartość STAREJ, wspólnej watchlisty ze Streamlita.
 *
 * Tabela należy do Pythona (`core/db.py`) i my ją wyłącznie CZYTAMY. Gdy jej
 * nie ma — a nie ma jej w świeżej bazie — zapytanie rzuca wyjątkiem; to nie
 * jest błąd, tylko informacja, że nie ma czego przenosić.
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
 * Kopiuje starą wspólną watchlistę na WSKAZANĄ listę. Zwraca liczbę dopisanych.
 *
 * KOPIUJE, NIE PRZENOSI — stara tabela zostaje nietknięta, więc powtórzenie
 * niczego nie psuje, a Streamlit dalej widzi swoje. Wpisy, które już są na tej
 * liście, pomijamy: notatki zrobione tutaj mają pierwszeństwo.
 */
export async function przeniesStaraWatchliste(
  uzytkownikId: number,
  listaId: number,
): Promise<number> {
  const stare = await staraWatchlista();
  let dopisane = 0;
  for (const w of stare) {
    const wynik = await dodajObserwowana(
      uzytkownikId,
      listaId,
      w.ticker,
      w.notatka,
    );
    if (wynik.ok) dopisane += 1;
  }
  return dopisane;
}
