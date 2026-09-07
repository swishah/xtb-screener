import { liczba, porownajRemis, type Instrument } from "./filtry";

/**
 * Backtest na zapisanych migawkach — wspólny dla strategii i własnych wag.
 *
 * ZERO IMPORTÓW Z NODE. Lustro `backtest_strategy()` z `core/scanner.py`:
 * dla każdego dnia skanu bierze TOP N spółek wg wskazanego wyniku, sprawdza
 * ich cenę `trzymaj` migawek później i liczy średni zwrot oraz odsetek
 * pozycji zyskownych.
 *
 * CZEGO TO NIE MIERZY: prowizji, podatku, dywidend i poślizgu. To ocena
 * samego DOBORU SPÓŁEK, nie symulacja rachunku maklerskiego.
 *
 * OKNA SIĘ NAKŁADAJĄ — każdy skan jest osobnym wejściem, więc sąsiednie okna
 * opisują w dużej części ten sam ruch rynku. Nie są niezależnymi próbami
 * i średnia z nich nie ma błędu standardowego, który dałoby się tak czytać.
 * Ekrany mówią to wprost i **nie usuwaj tego zastrzeżenia**.
 */

export type OknoBacktestu = {
  wejscie: string;
  wyjscie: string;
  sredniZwrot: number;
  winRate: number;
  spolek: number;
};

export type Podsumowanie = {
  okna: OknoBacktestu[];
  sredniZwrot: number | null;
  sredniWinRate: number | null;
  najlepsze: number | null;
  najgorsze: number | null;
  /** Skumulowany zwrot po kolejnych oknach, w procentach. */
  krzywa: { dzien: string; wartosc: number }[];
};

/**
 * Backtest po gotowej kolumnie wyniku (strategie) albo po wynikach policzonych
 * na żywo dla każdej migawki (własne wagi) — o tym decyduje `wynikDla`.
 */
export function backtestOgolny(
  wgDaty: Map<string, Instrument[]>,
  wynikDla: (spolki: Instrument[]) => (number | null)[] | null,
  topN: number,
  trzymaj: number,
): OknoBacktestu[] {
  const daty = [...wgDaty.keys()].sort();
  if (daty.length <= trzymaj) return [];

  const wyniki: OknoBacktestu[] = [];
  for (let i = 0; i + trzymaj < daty.length; i++) {
    const wejscie = daty[i];
    const wyjscie = daty[i + trzymaj];
    const wejsciowe = (wgDaty.get(wejscie) ?? []).filter(
      (r) => String(r.Typ ?? "") === "stock",
    );
    if (wejsciowe.length === 0) continue;

    const punkty = wynikDla(wejsciowe);
    if (!punkty) return [];

    const uszeregowane = wejsciowe
      .map((r, idx) => ({ r, p: punkty[idx] }))
      // Spółki bez wyniku odpadają, zamiast lądować na dole z zerem —
      // brak danych to nie to samo co najgorszy możliwy wynik.
      .filter((x): x is { r: Instrument; p: number } => x.p !== null)
      // Ta sama reguła remisów co w rankingach na ekranie.
      .sort((a, b) => (b.p !== a.p ? b.p - a.p : porownajRemis(a.r, b.r)))
      .slice(0, topN);

    const ceny = new Map<string, number>();
    for (const r of wgDaty.get(wyjscie) ?? []) {
      const c = liczba(r.Cena);
      if (c !== null && c > 0) ceny.set(String(r.Ticker), c);
    }

    const zwroty: number[] = [];
    for (const { r } of uszeregowane) {
      const start = liczba(r.Cena);
      const koniec = ceny.get(String(r.Ticker));
      if (start === null || start <= 0 || koniec === undefined) continue;
      zwroty.push((koniec / start - 1) * 100);
    }
    if (zwroty.length === 0) continue;

    wyniki.push({
      wejscie,
      wyjscie,
      sredniZwrot:
        Math.round((zwroty.reduce((a, b) => a + b, 0) / zwroty.length) * 100) / 100,
      winRate:
        Math.round((zwroty.filter((z) => z > 0).length / zwroty.length) * 1000) / 10,
      spolek: zwroty.length,
    });
  }
  return wyniki;
}

/** Backtest po istniejącej kolumnie wyniku — używany przez strategie. */
export function backtestKolumny(
  wgDaty: Map<string, Instrument[]>,
  kolumna: string,
  topN: number,
  trzymaj: number,
): OknoBacktestu[] {
  return backtestOgolny(
    wgDaty,
    (spolki) => spolki.map((r) => liczba(r[kolumna])),
    topN,
    trzymaj,
  );
}

export function podsumuj(okna: OknoBacktestu[]): Podsumowanie {
  if (okna.length === 0) {
    return {
      okna,
      sredniZwrot: null,
      sredniWinRate: null,
      najlepsze: null,
      najgorsze: null,
      krzywa: [],
    };
  }
  const zwroty = okna.map((o) => o.sredniZwrot);

  // Krzywa kapitału zakłada MECHANICZNE reinwestowanie zwrotu z każdego okna
  // z rzędu. To uproszczenie, bo okna się nakładają — traktuj jako orientacyjny
  // obraz kierunku, nie jako realną symulację portfela.
  let mnoznik = 1;
  const krzywa = okna.map((o) => {
    mnoznik *= 1 + o.sredniZwrot / 100;
    return {
      dzien: o.wyjscie,
      wartosc: Math.round((mnoznik - 1) * 10000) / 100,
    };
  });

  return {
    okna,
    sredniZwrot:
      Math.round((zwroty.reduce((a, b) => a + b, 0) / zwroty.length) * 100) / 100,
    sredniWinRate:
      Math.round(
        (okna.reduce((s, o) => s + o.winRate, 0) / okna.length) * 10,
      ) / 10,
    najlepsze: Math.max(...zwroty),
    najgorsze: Math.min(...zwroty),
    krzywa,
  };
}
