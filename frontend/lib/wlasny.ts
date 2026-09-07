import { liczba, porownajRemis, type Instrument } from "./filtry";

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

export type OknoBacktestu = {
  wejscie: string;
  wyjscie: string;
  sredniZwrot: number;
  winRate: number;
  spolek: number;
};

/**
 * Backtest na zapisanych migawkach: dla każdego dnia skanu bierze TOP N spółek
 * wg wyniku, sprawdza ich cenę `trzymaj` migawek później i liczy średni zwrot
 * oraz odsetek zyskownych pozycji.
 *
 * Lustro `backtest_strategy()` z `core/scanner.py` — ta sama pętla i te same
 * definicje, żeby liczby po obu stronach dawały się porównać.
 *
 * CZEGO TO NIE MIERZY: kosztów transakcyjnych, dywidend i poślizgu. To ocena
 * samego doboru spółek, nie symulacja rachunku maklerskiego.
 */
export function backtest(
  wgDaty: Map<string, Instrument[]>,
  wagi: Wagi,
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

    const punkty = policzWyniki(wejsciowe, wagi);
    if (!punkty) return [];

    const uszeregowane = wejsciowe
      .map((r, idx) => ({ r, p: punkty[idx] ?? 0 }))
      // Ta sama reguła remisów co w rankingu na ekranie — inaczej backtest
      // testowałby inny zestaw spółek niż ten, który użytkownik widzi.
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
