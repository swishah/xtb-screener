import { liczba, type Instrument } from "./filtry";

/**
 * Globalny przegląd — kondycja całego rynku, niezależnie od strategii.
 *
 * ZERO IMPORTÓW Z NODE, tak samo jak `lib/filtry.ts` — to czysta logika.
 *
 * WSZYSTKO LICZYMY NA SPÓŁKACH, BEZ ETF-ów. ETF to koszyk, więc jego cena
 * względem SMA200 mówi o rynku drugi raz to samo, tyle że z wagą indeksu —
 * a średnia „ile spółek jest nad swoją średnią" ma sens tylko wtedy, gdy
 * każda pozycja jest jedną spółką. Streamlitowa wersja robi dokładnie to
 * samo (`df[df["Typ"] == "stock"]`).
 */

/** Miara wraz z informacją, na ilu spółkach ją policzono. */
export type Miara = {
  wartosc: number | null;
  /** Ile spółek miało komplet danych do tej miary. */
  podstawa: number;
};

export type Szerokosc = {
  nadSMA200: Miara;
  nadSMA50: Miara;
  sredniRSI: Miara;
  buyScore5: Miara;
  /** Ile spółek w ogóle wzięliśmy pod uwagę. */
  spolek: number;
};

/**
 * Poniżej tego pokrycia NIE pokazujemy procentu, tylko mówimy, że danych brak.
 *
 * Powód jest zmierzony, nie teoretyczny: w migawkach z sierpnia i września
 * 2026 kolumny `SMA200` i `SMA50` są puste dla 27–99% spółek, zależnie od
 * dnia skanu (2026-09-04: 1274 z 1281). Wyliczony z takiej resztki „odsetek
 * spółek nad średnią" wygląda jak pomiar całego rynku, a jest pomiarem
 * siedmiu spółek — i akurat ta liczba trafia potem do wniosku „hossa czy
 * bessa". Lepiej powiedzieć „nie wiadomo".
 */
export const MIN_POKRYCIE = 0.5;

export function tylkoSpolki(instrumenty: Instrument[]): Instrument[] {
  return instrumenty.filter((i) => String(i.Typ ?? "") === "stock");
}

function udzialPowyzej(spolki: Instrument[], kolumna: string): Miara {
  const pary = spolki
    .map((s) => [liczba(s.Cena), liczba(s[kolumna])] as const)
    .filter((p): p is [number, number] => p[0] !== null && p[1] !== null);
  if (pary.length === 0) return { wartosc: null, podstawa: 0 };
  return {
    wartosc: (pary.filter(([c, sma]) => c > sma).length / pary.length) * 100,
    podstawa: pary.length,
  };
}

export function szerokoscRynku(instrumenty: Instrument[]): Szerokosc {
  const spolki = tylkoSpolki(instrumenty);

  const rsi = spolki.map((s) => liczba(s.RSI)).filter((w): w is number => w !== null);
  const score = spolki
    .map((s) => liczba(s["Buy Score"]))
    .filter((w): w is number => w !== null);

  return {
    nadSMA200: udzialPowyzej(spolki, "SMA200"),
    nadSMA50: udzialPowyzej(spolki, "SMA50"),
    sredniRSI: {
      wartosc: rsi.length ? rsi.reduce((a, b) => a + b, 0) / rsi.length : null,
      podstawa: rsi.length,
    },
    buyScore5: {
      wartosc: score.length
        ? (score.filter((w) => w >= 5).length / score.length) * 100
        : null,
      podstawa: score.length,
    },
    spolek: spolki.length,
  };
}

/** Czy miarę wolno pokazać jako liczbę, czy trzeba przyznać się do braku danych. */
export function wiarygodna(m: Miara, spolek: number): boolean {
  return m.wartosc !== null && spolek > 0 && m.podstawa / spolek >= MIN_POKRYCIE;
}

export type WierszHeatmapy = {
  grupa: string;
  sredniScore: number | null;
  sredniOdATH: number | null;
  ile: number;
};

/**
 * Średni Buy Score i średni spadek od szczytu w podziale na rynek albo sektor.
 *
 * Grupy poniżej `minSpolek` pomijamy: średnia z dwóch spółek nie mówi nic
 * o rynku, a w tabeli wygląda tak samo poważnie jak średnia z pięciuset.
 */
export function heatmapa(
  instrumenty: Instrument[],
  kolumna: string,
  minSpolek = 3,
): WierszHeatmapy[] {
  const grupy = new Map<string, Instrument[]>();
  for (const s of tylkoSpolki(instrumenty)) {
    const g = String(s[kolumna] ?? "").trim();
    if (!g || g === "Nieznany" || g === "BRAK") continue;
    const lista = grupy.get(g);
    if (lista) lista.push(s);
    else grupy.set(g, [s]);
  }

  const srednia = (lista: Instrument[], kol: string): number | null => {
    const w = lista
      .map((s) => liczba(s[kol]))
      .filter((x): x is number => x !== null);
    return w.length ? w.reduce((a, b) => a + b, 0) / w.length : null;
  };

  return [...grupy.entries()]
    .filter(([, lista]) => lista.length >= minSpolek)
    .map(([grupa, lista]) => ({
      grupa,
      sredniScore: srednia(lista, "Buy Score"),
      sredniOdATH: srednia(lista, "pct_from_ath"),
      ile: lista.length,
    }))
    .sort((a, b) => (b.sredniScore ?? -1) - (a.sredniScore ?? -1));
}

export type SlupekRSI = { od: number; do: number; ile: number };

/** Histogram RSI w dziesięciu przedziałach po 10 punktów, jak w Streamlicie. */
export function histogramRSI(instrumenty: Instrument[]): SlupekRSI[] {
  const slupki: SlupekRSI[] = Array.from({ length: 10 }, (_, i) => ({
    od: i * 10,
    do: (i + 1) * 10,
    ile: 0,
  }));
  for (const s of tylkoSpolki(instrumenty)) {
    const r = liczba(s.RSI);
    if (r === null || r < 0 || r > 100) continue;
    // RSI = 100 wpada do ostatniego przedziału, a nie poza tablicę.
    slupki[Math.min(9, Math.floor(r / 10))].ile += 1;
  }
  return slupki;
}

export type Ruch = {
  ticker: string;
  nazwa: string;
  rynek: string;
  cena: number;
  zmiana: number;
};

/**
 * Największe ruchy dzień do dnia — porównanie dwóch kolejnych migawek.
 *
 * SKAN CHODZI PON-PT, więc „dzień do dnia" znaczy tu „między dwoma ostatnimi
 * skanami", a po weekendzie i święcie ta przerwa jest dłuższa niż doba.
 * Ekran podaje obie daty wprost, żeby nikt nie brał ruchu z trzech dni za
 * ruch jednosesyjny.
 *
 * Liczymy na WSZYSTKICH instrumentach, także ETF-ach: tutaj interesuje nas,
 * co się ruszyło, a nie kondycja rynku jako całości.
 */
export function najwiekszeRuchy(
  dzis: Instrument[],
  poprzednie: Instrument[],
  ile = 10,
): { wzrosty: Ruch[]; spadki: Ruch[] } {
  const wczoraj = new Map<string, number>();
  for (const s of poprzednie) {
    const c = liczba(s.Cena);
    if (c !== null && c > 0) wczoraj.set(String(s.Ticker), c);
  }

  const ruchy: Ruch[] = [];
  for (const s of dzis) {
    const teraz = liczba(s.Cena);
    const przed = wczoraj.get(String(s.Ticker));
    if (teraz === null || przed === undefined || przed <= 0) continue;
    ruchy.push({
      ticker: String(s.Ticker),
      nazwa: String(s.Nazwa ?? ""),
      rynek: String(s.Rynek ?? ""),
      cena: teraz,
      zmiana: (teraz / przed - 1) * 100,
    });
  }

  const rosnaco = [...ruchy].sort((a, b) => a.zmiana - b.zmiana);
  return {
    wzrosty: [...rosnaco].reverse().slice(0, ile),
    spadki: rosnaco.slice(0, ile),
  };
}
