import { klientZapisu } from "./dane";

/**
 * Plany wejścia — odczyt i jedna jedyna zmiana, jaką frontend może zrobić.
 *
 * TA TABELA NALEŻY DO PYTHONA, tak samo jak `wlasne_instrumenty`. Schemat
 * powstaje w `core/db.py`, plany zapisuje `scripts/zapisz_plany.py` po
 * przejściu przez bramkę, a rozlicza je codzienny skan (`core/plany.py`).
 * Frontend tylko POKAZUJE — i pozwala anulować plan, którego użytkownik
 * postanowił nie brać.
 *
 * DLACZEGO PLANY NIE SĄ PER KONTO. Bo skan jest jeden i dossier jest jedno.
 * „Mój plan dnia" nie miałby jak istnieć osobno dla każdego konta — tak samo
 * jak własne instrumenty. Watchlisty i alarmy są per konto dokładnie dlatego,
 * że nie dotykają skanu.
 *
 * CZEGO TU NIE MA I NIE BĘDZIE: edycji poziomów. Baza na to nie pozwala
 * (`aktualizuj_plan` w core/db.py rzuca wyjątkiem na pola inne niż
 * rozliczeniowe), a powód jest ten sam co po stronie Pythona: plan jest
 * świadectwem tego, co się myślało tamtego dnia. Gdyby dało się go poprawiać,
 * statystyka skuteczności przestałaby cokolwiek znaczyć.
 */

export type StanPlanu =
  | "czeka"
  | "aktywny"
  | "sl"
  | "tp1"
  | "tp2"
  | "wygasl"
  | "anulowany";

export type Plan = {
  id: number;
  dzien: string;
  ticker: string;
  kierunek: string;
  teza: string;
  wejscieOd: number;
  wejscieDo: number;
  sl: number;
  slPoziom: string;
  tp1: number;
  tp2: number | null;
  rr: number | null;
  pewnosc: number | null;
  horyzontSesji: number;
  zrodla: string;
  uwagi: string;
  stan: StanPlanu;
  dataWejscia: string | null;
  dataZamkniecia: string | null;
  cenaZamkniecia: number | null;
  wynikR: number | null;
  sesjiMinelo: number;
};

export const STANY_OTWARTE: StanPlanu[] = ["czeka", "aktywny"];

export const ETYKIETY_STANU: Record<StanPlanu, string> = {
  czeka: "Czeka na wejście",
  aktywny: "Pozycja otwarta",
  sl: "Stop",
  tp1: "Pierwszy cel",
  tp2: "Drugi cel",
  wygasl: "Wygasł",
  anulowany: "Anulowany",
};

export const OPISY_STANU: Record<StanPlanu, string> = {
  czeka: "Kurs nie wszedł jeszcze w strefę wejścia.",
  aktywny: "Kurs dotknął strefy — plan liczy się jak otwarta pozycja.",
  sl: "Kurs zszedł do stop-lossa.",
  tp1: "Kurs sięgnął pierwszego celu.",
  tp2: "Kurs sięgnął drugiego celu.",
  wygasl: "Minął horyzont planu — rozliczony po cenie z rynku.",
  anulowany: "Odrzucony ręcznie, nie wchodzi do statystyki.",
};

/**
 * Zaokrąglenie liczone na WARTOŚCI liczby, a nie po przemnożeniu jej przez 100.
 *
 * Popularny idiom `Math.round(x * 100) / 100` wygląda niewinnie, ale samo
 * mnożenie wprowadza własny błąd: 0,595 razy 100 daje w JavaScripcie
 * 59,50000000000001, więc wynik skacze do 0,60 — podczas gdy Python czyta tę
 * samą liczbę jako 0,59 i tyle właśnie zwraca `round()`. Zmierzone na żywym
 * ekranie: ta sama średnia wychodziła +0,60 R tutaj i +0,59 R po stronie
 * Pythona. `toFixed` zaokrągla poprawnie, na tej samej wartości co Python,
 * więc obie strony dają jedną liczbę.
 */
function zaokr(x: number, cyfry: number): number {
  return Number(x.toFixed(cyfry));
}

export type Podsumowanie = {
  liczba: number;
  trafione: number;
  skutecznosc: number | null;
  sumaR: number;
  sredniaR: number | null;
};

const KOLUMNY = `id, dzien, ticker, kierunek, teza, wejscie_od, wejscie_do, sl,
  sl_poziom, tp1, tp2, rr, pewnosc, horyzont_sesji, zrodla, uwagi, stan,
  data_wejscia, data_zamkniecia, cena_zamkniecia, wynik_r, sesji_minelo`;

function lb(w: unknown): number {
  return typeof w === "number" ? w : Number(w ?? 0);
}

function lbOpc(w: unknown): number | null {
  if (w === null || w === undefined) return null;
  const x = Number(w);
  return Number.isFinite(x) ? x : null;
}

function txt(w: unknown): string {
  return w === null || w === undefined ? "" : String(w);
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function zWiersza(w: any): Plan {
  return {
    id: lb(w.id),
    dzien: txt(w.dzien),
    ticker: txt(w.ticker),
    kierunek: txt(w.kierunek) || "long",
    teza: txt(w.teza),
    wejscieOd: lb(w.wejscie_od),
    wejscieDo: lb(w.wejscie_do),
    sl: lb(w.sl),
    slPoziom: txt(w.sl_poziom),
    tp1: lb(w.tp1),
    tp2: lbOpc(w.tp2),
    rr: lbOpc(w.rr),
    pewnosc: lbOpc(w.pewnosc),
    horyzontSesji: lb(w.horyzont_sesji) || 10,
    zrodla: txt(w.zrodla),
    uwagi: txt(w.uwagi),
    stan: (txt(w.stan) || "czeka") as StanPlanu,
    dataWejscia: w.data_wejscia ? txt(w.data_wejscia) : null,
    dataZamkniecia: w.data_zamkniecia ? txt(w.data_zamkniecia) : null,
    cenaZamkniecia: lbOpc(w.cena_zamkniecia),
    wynikR: lbOpc(w.wynik_r),
    sesjiMinelo: lb(w.sesji_minelo),
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/**
 * Brak tabeli NIE jest błędem — znaczy tyle, że Python nie zapisał jeszcze
 * ani jednego planu. Ekran ma wtedy pokazać pustkę z wyjaśnieniem, a nie
 * stronę błędu.
 */
async function pytanie(sql: string, args: unknown[] = []): Promise<Plan[]> {
  try {
    const wynik = await klientZapisu().execute({
      sql,
      args: args as never[],
    });
    return wynik.rows.map(zWiersza);
  } catch (e) {
    console.error("Nie udało się odczytać planów:", e);
    return [];
  }
}

/** Dni, na które istnieją plany — od najnowszego. */
export async function dniPlanow(): Promise<string[]> {
  try {
    const wynik = await klientZapisu().execute(
      "SELECT DISTINCT dzien FROM plany ORDER BY dzien DESC",
    );
    return wynik.rows.map((w) => String(w.dzien));
  } catch {
    return [];
  }
}

/** Plany z danego dnia; bez argumentu — z najnowszego, który je ma. */
export async function planyDnia(dzien?: string): Promise<Plan[]> {
  let wybrany = dzien;
  if (!wybrany) {
    const dni = await dniPlanow();
    if (dni.length === 0) return [];
    wybrany = dni[0];
  }
  // Ta sama kolejność co w core/db.py: pewność, potem R:R, na końcu id.
  return pytanie(
    `SELECT ${KOLUMNY} FROM plany WHERE dzien = ?
     ORDER BY pewnosc DESC, rr DESC, id`,
    [wybrany],
  );
}

/** Wszystkie plany, które skan jeszcze rozlicza — także z dawniejszych dni. */
export async function planyOtwarte(): Promise<Plan[]> {
  return pytanie(
    `SELECT ${KOLUMNY} FROM plany WHERE stan IN ('czeka', 'aktywny')
     ORDER BY dzien DESC, pewnosc DESC, id`,
  );
}

/** Zamknięte plany, od najświeższego. */
export async function planyZamkniete(limit = 60): Promise<Plan[]> {
  return pytanie(
    `SELECT ${KOLUMNY} FROM plany WHERE stan NOT IN ('czeka', 'aktywny')
     ORDER BY data_zamkniecia DESC, id DESC LIMIT ?`,
    [limit],
  );
}

/**
 * Statystyka zamkniętych planów — lustro `podsumowanie()` z core/plany.py.
 *
 * Plany nierozliczone są POMIJANE, a nie liczone jako zero: świeżo wystawiony
 * plan psułby statystykę do czasu zamknięcia. Anulowane wypadają same, bo nie
 * mają wyniku.
 *
 * ŚREDNIĄ LICZYMY Z ZAOKRĄGLONEJ SUMY, nie z surowej — dokładnie tak samo jak
 * `podsumowanie()` w core/plany.py. Sumowanie liczb zmiennoprzecinkowych
 * zależy od KOLEJNOŚCI składników, a Python czyta plany posortowane inaczej
 * niż my; bez tego kroku ta sama suma potrafi wyjść jako 2,3800000000000003
 * po jednej stronie.
 */
export function podsumowanie(plany: Plan[]): Podsumowanie {
  const zamkniete = plany.filter(
    (p) => !STANY_OTWARTE.includes(p.stan) && p.wynikR !== null,
  );
  if (zamkniete.length === 0) {
    return { liczba: 0, trafione: 0, skutecznosc: null, sumaR: 0, sredniaR: null };
  }
  const wyniki = zamkniete.map((p) => p.wynikR as number);
  const trafione = wyniki.filter((w) => w > 0).length;
  const sumaR = zaokr(wyniki.reduce((a, b) => a + b, 0), 2);
  return {
    liczba: zamkniete.length,
    trafione,
    skutecznosc: zaokr((trafione / zamkniete.length) * 100, 1),
    sumaR,
    sredniaR: zaokr(sumaR / zamkniete.length, 2),
  };
}

export type Polozenie = "w strefie" | "powyżej strefy" | "poniżej strefy";

/**
 * Gdzie stoi kurs względem strefy wejścia. Czysta funkcja — bez tego widok
 * mówi „czeka na wejście" i nie mówi, czy czeka na centymetr, czy na przepaść.
 */
export function polozenie(plan: Plan, cena: number | null): Polozenie | null {
  if (cena === null || !Number.isFinite(cena)) return null;
  if (cena < plan.wejscieOd) return "poniżej strefy";
  if (cena > plan.wejscieDo) return "powyżej strefy";
  return "w strefie";
}

/**
 * Anulowanie planu.
 *
 * Jedyna zmiana, jaką frontend robi w tej tabeli. Filtr po `stan` w samym SQL-u
 * znaczy, że anulowanie planu już rozliczonego nie zmienia niczego — wynik
 * z przeszłości ma zostać nietknięty.
 */
export async function anulujPlan(id: number): Promise<boolean> {
  try {
    const wynik = await klientZapisu().execute({
      sql: `UPDATE plany SET stan = 'anulowany', data_zamkniecia = ?
            WHERE id = ? AND stan IN ('czeka', 'aktywny')`,
      args: [new Date().toISOString().slice(0, 10), id],
    });
    return (wynik.rowsAffected ?? 0) > 0;
  } catch (e) {
    console.error("Nie udało się anulować planu:", e);
    return false;
  }
}
