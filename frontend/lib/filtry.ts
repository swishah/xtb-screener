/**
 * Czysta logika: typy, filtrowanie, sortowanie, statystyki.
 *
 * DLACZEGO OSOBNY PLIK OD dane.ts: ten moduł importuje panel filtrów, który
 * działa w PRZEGLĄDARCE. Gdyby siedział razem z dostępem do bazy, webpack
 * próbowałby spakować do przeglądarki `node:path` i klienta SQLite — i słusznie
 * by odmówił ("UnhandledSchemeError"). Sprawdzanie typów tego nie łapie, bo
 * z punktu widzenia TypeScriptu wszystko się zgadza; wychodzi dopiero przy
 * budowaniu.
 *
 * Zasada: tutaj ZERO importów z Node. Wszystko, co dotyka bazy, zostaje
 * w lib/dane.ts.
 */

/** Instrument w postaci, w jakiej zapisuje go skan (klucze po polsku). */
export type Instrument = {
  Ticker: string;
  Nazwa: string;
  Typ: string;
  Sektor?: string;
  Rynek?: string;
  Waluta?: string;
  Cena?: number | string;
  RSI?: number | string;
  pct_from_ath?: number | string;
  "Buy Score"?: number | string;
  "C/Z (P/E)"?: number | string;
  "Stopa Dyw. (%)"?: number | string;
  "Liczba flag"?: number | string;
  [klucz: string]: unknown;
};

/** Liczba w postaci nadającej się do sortowania — "BRAK" i null dają null. */
export function liczba(wartosc: unknown): number | null {
  if (typeof wartosc === "number" && Number.isFinite(wartosc)) return wartosc;
  if (typeof wartosc === "string") {
    const n = Number(wartosc.replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export type Filtry = {
  typ: string;
  rynek: string;
  sektor: string;
  minScore: number;
  maxAth: number;
  maxFlag: number;
  szukaj: string;
  sortuj: string;
};

export const FILTRY_DOMYSLNE: Filtry = {
  typ: "stock",
  rynek: "",
  sektor: "",
  minScore: 0,
  maxAth: 0,
  maxFlag: 10,
  szukaj: "",
  sortuj: "Buy Score",
};

/** Kolumny, po których wolno sortować — etykieta widoczna w interfejsie. */
export const SORTOWANIA: { klucz: string; etykieta: string; rosnaco?: boolean }[] = [
  { klucz: "Buy Score", etykieta: "Buy Score (najwyższy)" },
  { klucz: "pct_from_ath", etykieta: "Spadek od ATH (największy)", rosnaco: true },
  { klucz: "RSI", etykieta: "RSI (najniższy)", rosnaco: true },
  { klucz: "Stopa Dyw. (%)", etykieta: "Stopa dywidendy (najwyższa)" },
  { klucz: "C/Z (P/E)", etykieta: "C/Z (najniższy)", rosnaco: true },
  { klucz: "Liczba flag", etykieta: "Liczba flag (najmniej)", rosnaco: true },
];

/** Unikalne wartości kolumny — do wypełnienia list wyboru. */
export function wartosci(instrumenty: Instrument[], kolumna: string): string[] {
  const zbior = new Set<string>();
  for (const i of instrumenty) {
    const v = i[kolumna];
    if (typeof v === "string" && v && v !== "BRAK") zbior.add(v);
  }
  return [...zbior].sort((a, b) => a.localeCompare(b, "pl"));
}

export function filtruj(instrumenty: Instrument[], f: Filtry): Instrument[] {
  const szukaj = f.szukaj.trim().toLowerCase();

  const wynik = instrumenty.filter((i) => {
    if (f.typ && i.Typ !== f.typ) return false;
    if (f.rynek && i.Rynek !== f.rynek) return false;
    if (f.sektor && i.Sektor !== f.sektor) return false;

    // Instrument bez policzonej wartości odpada dopiero wtedy, gdy filtr
    // faktycznie czegoś wymaga — inaczej samo otwarcie ekranu ucinałoby
    // spółki, dla których Yahoo nie podało kompletu danych.
    if (f.minScore > 0) {
      const s = liczba(i["Buy Score"]);
      if (s === null || s < f.minScore) return false;
    }
    if (f.maxAth < 0) {
      const a = liczba(i["pct_from_ath"]);
      if (a === null || a > f.maxAth) return false;
    }
    if (f.maxFlag < 10) {
      const fl = liczba(i["Liczba flag"]);
      if (fl === null || fl > f.maxFlag) return false;
    }
    if (szukaj) {
      const t = String(i.Ticker ?? "").toLowerCase();
      const n = String(i.Nazwa ?? "").toLowerCase();
      if (!t.includes(szukaj) && !n.includes(szukaj)) return false;
    }
    return true;
  });

  const spec = SORTOWANIA.find((s) => s.klucz === f.sortuj) ?? SORTOWANIA[0];
  return wynik.sort((a, b) => {
    const x = liczba(a[spec.klucz]);
    const y = liczba(b[spec.klucz]);
    // Brak wartości zawsze na koniec, niezależnie od kierunku sortowania —
    // "BRAK" nie może udawać najlepszego ani najgorszego wyniku.
    if (x === null && y === null) return 0;
    if (x === null) return 1;
    if (y === null) return -1;
    return spec.rosnaco ? x - y : y - x;
  });
}

export type Statystyki = {
  wszystkie: number;
  akcje: number;
  etfy: number;
  bezFlag: number;
  sredniScore: number | null;
};

export function statystyki(instrumenty: Instrument[]): Statystyki {
  const score = instrumenty
    .map((i) => liczba(i["Buy Score"]))
    .filter((n): n is number => n !== null);

  return {
    wszystkie: instrumenty.length,
    akcje: instrumenty.filter((i) => i.Typ === "stock").length,
    etfy: instrumenty.filter((i) => i.Typ === "etf").length,
    bezFlag: instrumenty.filter((i) => liczba(i["Liczba flag"]) === 0).length,
    sredniScore: score.length
      ? score.reduce((a, b) => a + b, 0) / score.length
      : null,
  };
}

/** TOP N wg Buy Score. Instrumenty bez wyniku wypadają, nie lądują na końcu. */
export function najlepsze(instrumenty: Instrument[], ile = 10): Instrument[] {
  return instrumenty
    .filter((i) => i.Typ === "stock" && liczba(i["Buy Score"]) !== null)
    .sort((a, b) => (liczba(b["Buy Score"]) ?? 0) - (liczba(a["Buy Score"]) ?? 0))
    .slice(0, ile);
}
