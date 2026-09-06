/**
 * Korelacje między obserwowanymi spółkami.
 *
 * ZERO IMPORTÓW Z NODE — tak samo jak `lib/filtry.ts`. To czysta matematyka,
 * więc wolno jej trafić i do komponentu serwerowego, i do klienckiego.
 *
 * SKĄD BIERZEMY CENY I CZYM SIĘ TO RÓŻNI OD STREAMLITA. Wersja streamlitowa
 * woła `compute_correlation_matrix()`, które ściąga historię wprost z Yahoo —
 * czyli lata notowań. Tutaj liczymy z NASZYCH migawek, tak samo jak wykres
 * przy alarmach. Powód jest architektoniczny: `lib/dane.ts` sięga do bazy
 * i tylko do bazy, a dokładanie ruchu sieciowego do aplikacji webowej jest
 * decyzją innego kalibru niż przeniesienie modułu.
 *
 * SKUTEK JEST REALNY I NIE UDAJEMY, ŻE GO NIE MA: skan chodzi raz na dobę od
 * sierpnia 2026, więc szereg jest krótki. Przy 20 obserwacjach błąd
 * standardowy współczynnika to około 0,22 — prawdziwe 0,5 potrafi wyjść
 * między 0,3 a 0,7. Dlatego pokazujemy liczbę sesji przy każdej macierzy,
 * a pary krótsze niż `MIN_SESJI` zostawiamy puste zamiast wpisywać liczbę,
 * która wygląda na pomiar. Z każdym kolejnym skanem robi się to dokładniejsze
 * samo z siebie.
 */

export type Szereg = {
  ticker: string;
  punkty: { dzien: string; cena: number }[];
};

export type Macierz = {
  tickery: string[];
  /** wartosci[i][j] — null, gdy para ma za mało wspólnych sesji. */
  wartosci: (number | null)[][];
  /** Najmniejsza i największa liczba zwrotów użyta w którejkolwiek parze. */
  minSesji: number;
  maksSesji: number;
};

/**
 * Poniżej tylu wspólnych zwrotów nie pokazujemy współczynnika.
 *
 * Próg jest arbitralny, ale nie przypadkowy: przy 15 obserwacjach błąd
 * standardowy to już około 0,26, czyli granica sensu. Niżej liczba mówiłaby
 * więcej o szumie niż o spółkach.
 */
export const MIN_SESJI = 15;

/** Ile spółek naraz. Macierz rośnie kwadratowo, a i tak nikt nie czyta 50×50. */
export const MAKS_SPOLEK = 25;

function zwrotyNaWspolnychDniach(
  a: Map<string, number>,
  b: Map<string, number>,
): [number[], number[]] {
  // Wspólne dni, po kolei. Zwroty liczymy WYŁĄCZNIE między sąsiadującymi
  // wspólnymi dniami — inaczej luka w jednej serii udawałaby jeden duży ruch.
  const dni = [...a.keys()].filter((d) => b.has(d)).sort();
  const zA: number[] = [];
  const zB: number[] = [];
  for (let i = 1; i < dni.length; i++) {
    const a0 = a.get(dni[i - 1])!;
    const a1 = a.get(dni[i])!;
    const b0 = b.get(dni[i - 1])!;
    const b1 = b.get(dni[i])!;
    if (a0 > 0 && b0 > 0) {
      zA.push(a1 / a0 - 1);
      zB.push(b1 / b0 - 1);
    }
  }
  return [zA, zB];
}

function pearson(x: number[], y: number[]): number | null {
  const n = x.length;
  if (n < MIN_SESJI) return null;
  const sx = x.reduce((s, w) => s + w, 0) / n;
  const sy = y.reduce((s, w) => s + w, 0) / n;
  let gora = 0;
  let dolX = 0;
  let dolY = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - sx;
    const dy = y[i] - sy;
    gora += dx * dy;
    dolX += dx * dx;
    dolY += dy * dy;
  }
  // Instrument bez ani jednego ruchu (np. zawieszony) ma zerową wariancję —
  // korelacja jest wtedy nieokreślona, a nie równa zeru.
  if (dolX <= 0 || dolY <= 0) return null;
  const r = gora / Math.sqrt(dolX * dolY);
  return Number.isFinite(r) ? Math.max(-1, Math.min(1, r)) : null;
}

export function macierzKorelacji(szeregi: Szereg[]): Macierz {
  const uzyte = szeregi.slice(0, MAKS_SPOLEK);
  const tickery = uzyte.map((s) => s.ticker);
  const mapy = uzyte.map(
    (s) => new Map(s.punkty.map((p) => [p.dzien, p.cena] as const)),
  );

  const wartosci: (number | null)[][] = tickery.map(() =>
    tickery.map(() => null),
  );
  let minSesji = Number.POSITIVE_INFINITY;
  let maksSesji = 0;

  for (let i = 0; i < tickery.length; i++) {
    wartosci[i][i] = 1;
    for (let j = i + 1; j < tickery.length; j++) {
      const [x, y] = zwrotyNaWspolnychDniach(mapy[i], mapy[j]);
      minSesji = Math.min(minSesji, x.length);
      maksSesji = Math.max(maksSesji, x.length);
      const r = pearson(x, y);
      wartosci[i][j] = r;
      wartosci[j][i] = r;
    }
  }

  return {
    tickery,
    wartosci,
    minSesji: Number.isFinite(minSesji) ? minSesji : 0,
    maksSesji,
  };
}
