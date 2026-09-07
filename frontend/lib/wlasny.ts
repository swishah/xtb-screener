import { backtestOgolny, type OknoBacktestu } from "./backtest";
import { liczba, type Instrument } from "./filtry";

/**
 * Własny scoring — ranking na bazie WŁASNYCH wag zamiast sztywnych strategii.
 *
 * ZERO IMPORTÓW Z NODE, tak samo jak `lib/filtry.ts` — czysta logika.
 *
 * WYNIK TO POZYCJA PERCENTYLOWA, NIE SUROWA WARTOŚĆ. Gdyby wagi mnożyły
 * surowe liczby, jedna kolumna zjadłaby resztę: kapitalizacja idzie
 * w miliardach, a stopa dywidendy w jednostkach procentu. Percentyl (0–1)
 * sprowadza każdą kolumnę do tej samej skali, więc suwak „2" naprawdę znaczy
 * „dwa razy ważniejsze", niezależnie od jednostek.
 *
 * BRAK DANYCH DOSTAJE 0,5, a nie zero. Spółka bez podanego ROE nie jest
 * „najgorsza w stawce" — po prostu nie wiadomo. Zero spychałoby ją na dno
 * rankingu za brak danych u dostawcy, co jest karą za cudzy błąd.
 */

export type Kierunek = "wyzej" | "nizej";

export type Skladnik = {
  etykieta: string;
  kolumna: string;
  kierunek: Kierunek;
  domyslna: number;
};

/** Lustro `CUSTOM_COMPONENTS` z `ui/custom.py` — kolejność i wagi te same. */
export const SKLADNIKI: Skladnik[] = [
  { etykieta: "Spadek od ATH (duży = lepiej)", kolumna: "pct_from_ath", kierunek: "nizej", domyslna: 2 },
  { etykieta: "ROE", kolumna: "ROE (%)", kierunek: "wyzej", domyslna: 1 },
  { etykieta: "Marża operacyjna", kolumna: "Marża Operac. (%)", kierunek: "wyzej", domyslna: 1 },
  { etykieta: "Marża netto", kolumna: "Marża netto (%)", kierunek: "wyzej", domyslna: 1 },
  { etykieta: "Wzrost przychodów", kolumna: "Wzrost przychodów (%)", kierunek: "wyzej", domyslna: 1 },
  { etykieta: "Wzrost EPS", kolumna: "Wzrost EPS (%)", kierunek: "wyzej", domyslna: 1 },
  { etykieta: "Dług/Kapitał (niższy = lepiej)", kolumna: "Dług/Kapitał", kierunek: "nizej", domyslna: 1 },
  { etykieta: "C/Z (niższe = taniej)", kolumna: "C/Z (P/E)", kierunek: "nizej", domyslna: 1 },
  { etykieta: "Stopa dywidendy", kolumna: "Stopa Dyw. (%)", kierunek: "wyzej", domyslna: 1 },
  { etykieta: "RSI (niższe = wyprzedanie)", kolumna: "RSI", kierunek: "nizej", domyslna: 1 },
  { etykieta: "Wolumen rosnący", kolumna: "volume_ratio", kierunek: "wyzej", domyslna: 0 },
  { etykieta: "Payout ratio (niższy = bezpieczniej)", kolumna: "Payout ratio (%)", kierunek: "nizej", domyslna: 0 },
  { etykieta: "Zmiana ceny 1R (niższa = jeszcze niezauważona)", kolumna: "Zmiana ceny (1Y%)", kierunek: "nizej", domyslna: 0 },
];

export const MAKS_WAGA = 5;

export type Wagi = Record<string, number>;

export function wagiDomyslne(): Wagi {
  const w: Wagi = {};
  for (const s of SKLADNIKI) w[s.kolumna] = s.domyslna;
  return w;
}

/**
 * Pozycja percentylowa każdej wartości w kolumnie, 0–1.
 *
 * Odpowiednik `Series.rank(pct=True)` z pandas, razem z jego obsługą remisów:
 * wartości równe dostają ŚREDNIĄ z pozycji, które zajmują. Bez tego dziesięć
 * spółek z identycznym RSI dostałoby dziesięć różnych wyników zależnie od
 * kolejności w tabeli — czyli ranking zależałby od przypadku.
 */
export function percentyle(
  wartosci: (number | null)[],
  kierunek: Kierunek,
): (number | null)[] {
  const znane: { i: number; w: number }[] = [];
  wartosci.forEach((w, i) => {
    if (w !== null) znane.push({ i, w });
  });
  if (znane.length === 0) return wartosci.map(() => null);

  znane.sort((a, b) => (kierunek === "wyzej" ? a.w - b.w : b.w - a.w));

  const wynik: (number | null)[] = wartosci.map(() => null);
  let i = 0;
  while (i < znane.length) {
    let j = i;
    while (j + 1 < znane.length && znane[j + 1].w === znane[i].w) j += 1;
    // Średnia ranga (1-based) dla całej grupy remisujących.
    const srednia = (i + 1 + (j + 1)) / 2;
    for (let k = i; k <= j; k++) wynik[znane[k].i] = srednia / znane.length;
    i = j + 1;
  }
  return wynik;
}

/** Wynik 0–100 dla każdej spółki. `null`, gdy wszystkie wagi są zerowe. */
export function policzWyniki(
  spolki: Instrument[],
  wagi: Wagi,
): (number | null)[] | null {
  const suma = SKLADNIKI.reduce((s, k) => s + (wagi[k.kolumna] ?? 0), 0);
  if (suma <= 0) return null;

  const punkty = spolki.map(() => 0);
  for (const s of SKLADNIKI) {
    const w = wagi[s.kolumna] ?? 0;
    if (w === 0) continue;
    const kolumna = spolki.map((r) => liczba(r[s.kolumna]));
    const p = percentyle(kolumna, s.kierunek);
    p.forEach((v, i) => {
      punkty[i] += w * (v ?? 0.5);
    });
  }
  return punkty.map((p) => Math.round((p / suma) * 1000) / 10);
}

// ---------------------------------------------------------------------------
// Backtest własnych wag
// ---------------------------------------------------------------------------

/**
 * Backtest tej konkretnej kombinacji wag.
 *
 * Korzysta ze WSPÓLNEJ implementacji z `lib/backtest.ts`, tej samej co
 * Backtest strategii — inaczej dwa ekrany liczyłyby „to samo" dwoma kodami,
 * które z czasem by się rozjechały. Różnica jest jedna: tutaj wynik trzeba
 * policzyć osobno dla KAŻDEJ migawki, bo percentyl zależy od całej stawki
 * z tamtego dnia, a nie od gotowej kolumny.
 */
export function backtest(
  wgDaty: Map<string, Instrument[]>,
  wagi: Wagi,
  topN: number,
  trzymaj: number,
): OknoBacktestu[] {
  return backtestOgolny(
    wgDaty,
    (spolki) => policzWyniki(spolki, wagi),
    topN,
    trzymaj,
  );
}
