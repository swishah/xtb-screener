import { klientZapisu } from "./dane";

/**
 * Dossier kandydatów — odczyt jednego dnia i historia w czasie.
 *
 * HISTORIA JEST ZBIERANA OD POCZĄTKU, bez żadnej dodatkowej pracy: tabela
 * `dossier` ma klucz główny `(dzien, ticker)`, a `zapisz_dossier` w Pythonie
 * nic nie kasuje. Każdy poranny przebieg dokłada nowy dzień obok poprzednich.
 *
 * DWA SPOSOBY CZYTANIA I TO JEST CAŁA SZTUCZKA WYDAJNOŚCIOWA. Jeden wpis waży
 * ~16 kB, z czego **75% to świece** (60 dziennych, 52 tygodniowe, 60
 * miesięcznych) — potrzebne warstwie oceniającej, bezużyteczne na ekranie.
 * Dossier jednego dnia to 310 kB i można je wciągnąć w całości; historia
 * wszystkich dni po roku to 76 MB i wciągnąć się jej NIE DA. Dlatego przegląd
 * historyczny idzie przez `json_extract` i pobiera po kilkanaście bajtów
 * z wiersza, nigdy całego payloadu.
 *
 * Ta tabela należy do Pythona — frontend wyłącznie ją CZYTA.
 */

export type PoziomDossier = {
  id: string;
  wartosc: number;
  opis: string;
  rodzaj: string;
  dystansPct: number;
};

export type ZrodloDossier = { ranking: string; miejsce: number };

export type WpisDossier = {
  ticker: string;
  nazwa: string;
  rynek: string;
  sektor: string;
  waluta: string;
  wPodjednostkach: boolean;
  zrodla: ZrodloDossier[];
  liczbaZrodel: number;
  sredniMiejsce: number;
  kurs: number | null;
  atr: number | null;
  atrPct: number | null;
  trend1d: string;
  trend1w: string;
  trend1m: string;
  zakresMin: number | null;
  zakresMaks: number | null;
  pozycjaPct: number | null;
  wolumenKrotnosc: number | null;
  rozjazdPct: number | null;
  poziomy: PoziomDossier[];
  migawka: Record<string, unknown>;
};

/** Jedna spółka widziana przez wszystkie dni, w których była w dossier. */
export type SladKandydata = {
  ticker: string;
  nazwa: string;
  dni: number;
  pierwszyDzien: string;
  ostatniDzien: string;
  kursPierwszy: number | null;
  kursOstatni: number | null;
  /** Zmiana kursu od pierwszego pojawienia się w dossier, w procentach. */
  zmianaPct: number | null;
  maksZrodel: number;
  /** Ile razy ta spółka stała się planem. */
  planow: number;
};

/**
 * Zapora na wypadek, gdyby historia urosła bardziej, niż zakładam.
 * Przy 20 kandydatach dziennie to około pięciu lat.
 */
const MAKS_WIERSZY_HISTORII = 25000;

function lb(w: unknown): number | null {
  if (w === null || w === undefined) return null;
  const x = Number(w);
  return Number.isFinite(x) ? x : null;
}

function txt(w: unknown): string {
  return w === null || w === undefined ? "" : String(w);
}

/** Dni, na które istnieje dossier — od najnowszego. */
export async function dniDossier(): Promise<string[]> {
  try {
    const w = await klientZapisu().execute(
      "SELECT DISTINCT dzien FROM dossier ORDER BY dzien DESC",
    );
    return w.rows.map((r) => String(r.dzien));
  } catch (e) {
    console.error("Nie udało się odczytać dni dossier:", e);
    return [];
  }
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function zPayloadu(p: any): WpisDossier {
  const zakres = p?.zakres_52t ?? {};
  const trend = p?.trend ?? {};
  return {
    ticker: txt(p?.ticker),
    nazwa: txt(p?.nazwa),
    rynek: txt(p?.rynek),
    sektor: txt(p?.sektor),
    waluta: txt(p?.waluta),
    wPodjednostkach: Boolean(p?.waluta_w_podjednostkach),
    zrodla: Array.isArray(p?.zrodla)
      ? p.zrodla.map((z: any) => ({
          ranking: txt(z?.ranking),
          miejsce: lb(z?.miejsce) ?? 0,
        }))
      : [],
    liczbaZrodel: lb(p?.liczba_zrodel) ?? 0,
    sredniMiejsce: lb(p?.srednie_miejsce) ?? 0,
    kurs: lb(p?.kurs),
    atr: lb(p?.atr),
    atrPct: lb(p?.atr_pct),
    trend1d: txt(trend?.["1d"]),
    trend1w: txt(trend?.["1w"]),
    trend1m: txt(trend?.["1m"]),
    zakresMin: lb(zakres?.min),
    zakresMaks: lb(zakres?.maks),
    pozycjaPct: lb(zakres?.pozycja_pct),
    wolumenKrotnosc: lb(p?.wolumen?.krotnosc),
    rozjazdPct: lb(p?.rozjazd_wobec_migawki_pct),
    poziomy: Array.isArray(p?.poziomy)
      ? p.poziomy.map((x: any) => ({
          id: txt(x?.id),
          wartosc: lb(x?.wartosc) ?? 0,
          opis: txt(x?.opis),
          rodzaj: txt(x?.rodzaj),
          dystansPct: lb(x?.dystans_pct) ?? 0,
        }))
      : [],
    migawka: (p?.migawka ?? {}) as Record<string, unknown>,
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/**
 * Dossier z jednego dnia, w całości (bez świec — te zostają w bazie).
 *
 * Kolejność jak przy zbiórce: najpierw wskazane przez najwięcej rankingów.
 */
export async function dossierDnia(dzien?: string): Promise<WpisDossier[]> {
  let wybrany = dzien;
  if (!wybrany) {
    const dni = await dniDossier();
    if (dni.length === 0) return [];
    wybrany = dni[0];
  }
  try {
    const w = await klientZapisu().execute({
      sql: "SELECT payload FROM dossier WHERE dzien = ?",
      args: [wybrany],
    });
    const wpisy: WpisDossier[] = [];
    for (const r of w.rows) {
      try {
        wpisy.push(zPayloadu(JSON.parse(String(r.payload))));
      } catch {
        // Pojedynczy uszkodzony payload nie może wywalić całego ekranu.
      }
    }
    wpisy.sort(
      (a, b) =>
        b.liczbaZrodel - a.liczbaZrodel ||
        a.sredniMiejsce - b.sredniMiejsce ||
        a.ticker.localeCompare(b.ticker),
    );
    return wpisy;
  } catch (e) {
    console.error("Nie udało się odczytać dossier:", e);
    return [];
  }
}

/**
 * Ślad każdej spółki przez wszystkie dni dossier.
 *
 * Odpowiada na pytanie, którego pojedynczy dzień nie odpowie: czy spółka
 * wraca. Wskazanie przez rankingi ósmy dzień z rzędu to inny sygnał niż
 * jednodniowe mignięcie — a bez historii nie da się tego odróżnić.
 *
 * `zmianaPct` liczymy od kursu z PIERWSZEGO pojawienia się do OSTATNIEGO,
 * więc mierzy, co się działo, gdy spółka siedziała w dossier. To jest
 * najbliższe sprawdzeniu, czy sam dobór kandydatów cokolwiek znaczy —
 * niezależnie od tego, czy powstał z niego plan.
 */
export async function sladyKandydatow(): Promise<SladKandydata[]> {
  let wiersze: { ticker: string; dzien: string; nazwa: string; kurs: number | null; zrodel: number }[];
  try {
    const w = await klientZapisu().execute({
      sql: `SELECT ticker, dzien,
                   json_extract(payload, '$.nazwa')         AS nazwa,
                   json_extract(payload, '$.kurs')          AS kurs,
                   json_extract(payload, '$.liczba_zrodel') AS zrodel
            FROM dossier
            ORDER BY ticker, dzien
            LIMIT ?`,
      args: [MAKS_WIERSZY_HISTORII],
    });
    wiersze = w.rows.map((r) => ({
      ticker: String(r.ticker),
      dzien: String(r.dzien),
      nazwa: txt(r.nazwa),
      kurs: lb(r.kurs),
      zrodel: lb(r.zrodel) ?? 0,
    }));
  } catch (e) {
    console.error("Nie udało się odczytać historii dossier:", e);
    return [];
  }

  // Ile razy każda spółka stała się planem. Brak tabeli `plany` nie może
  // wywrócić widoku dossier — to dwie osobne rzeczy.
  const planow = new Map<string, number>();
  try {
    const w = await klientZapisu().execute(
      "SELECT ticker, count(*) AS ile FROM plany GROUP BY ticker",
    );
    for (const r of w.rows) {
      planow.set(String(r.ticker).toUpperCase(), lb(r.ile) ?? 0);
    }
  } catch {
    /* brak planów to nie błąd */
  }

  const wg = new Map<string, typeof wiersze>();
  for (const r of wiersze) {
    const lista = wg.get(r.ticker);
    if (lista) lista.push(r);
    else wg.set(r.ticker, [r]);
  }

  const slady: SladKandydata[] = [];
  for (const [ticker, lista] of wg) {
    const pierwszy = lista[0];
    const ostatni = lista[lista.length - 1];
    const zmiana =
      pierwszy.kurs && ostatni.kurs && pierwszy.kurs > 0
        ? Number((((ostatni.kurs - pierwszy.kurs) / pierwszy.kurs) * 100).toFixed(2))
        : null;
    slady.push({
      ticker,
      nazwa: lista.find((r) => r.nazwa)?.nazwa ?? "",
      dni: lista.length,
      pierwszyDzien: pierwszy.dzien,
      ostatniDzien: ostatni.dzien,
      kursPierwszy: pierwszy.kurs,
      kursOstatni: ostatni.kurs,
      zmianaPct: zmiana,
      maksZrodel: Math.max(...lista.map((r) => r.zrodel)),
      planow: planow.get(ticker.toUpperCase()) ?? 0,
    });
  }

  // Najpierw te, które wracają najczęściej; przy remisie ostatnio widziane.
  slady.sort(
    (a, b) =>
      b.dni - a.dni ||
      b.maksZrodel - a.maksZrodel ||
      b.ostatniDzien.localeCompare(a.ostatniDzien) ||
      a.ticker.localeCompare(b.ticker),
  );
  return slady;
}

/** Tickery, które danego dnia stały się planem — do oznaczenia na liście. */
export async function tickeryZPlanem(dzien: string): Promise<Set<string>> {
  try {
    const w = await klientZapisu().execute({
      sql: "SELECT DISTINCT ticker FROM plany WHERE dzien = ?",
      args: [dzien],
    });
    return new Set(w.rows.map((r) => String(r.ticker).toUpperCase()));
  } catch {
    return new Set();
  }
}
