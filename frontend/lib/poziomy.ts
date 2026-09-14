/**
 * Poziomy techniczne liczone z surowego OHLC — LUSTRO `core/poziomy.py`.
 *
 * DLACZEGO ISTNIEJE DRUGA IMPLEMENTACJA TEGO SAMEGO. Pythonowa wersja liczy
 * poziomy podczas porannego dossier, na komputerze użytkownika albo w GitHub
 * Actions. Maszyna researchowa w Claude ma działać Z PRACY, dla DOWOLNEJ
 * spółki, o dowolnej porze — także takiej, której nie ma w dzisiejszym dossier
 * (dossier obejmuje ~20 kandydatów, uniwersum ma ~1300 instrumentów). Bez tej
 * kopii jedyny plan wejścia, jaki dałoby się ułożyć zdalnie, opierałby się na
 * poziomach zmyślonych przez model — czyli dokładnie na tym, czego bramka
 * w `core/bramka.py` zabrania.
 *
 * ZASADA LUSTRA: ten plik nie wymyśla własnych reguł. Każda stała, każdy próg
 * i każde zaokrąglenie pochodzi z `core/poziomy.py`. Zmiana po jednej stronie
 * wymaga zmiany po drugiej, a `scripts/porownaj_poziomy.py` sprawdza zgodność
 * na żywych danych.
 *
 * CENY ZOSTAJĄ W WALUCIE NOTOWANIA, bez przeliczania. Yahoo podaje Londyn
 * w PENSACH ("GBp"), tak samo jak migawka ze skanu, więc obie strony mówią
 * tym samym językiem. Przeliczenie tutaj rozjechałoby je i dałoby poziomy
 * 100x nie takie. Fakt notowania w subjednostkach wychodzi na wierzch jako
 * `waluta_w_podjednostkach` i ma tam zostać.
 */
import { notowania, skalaCeny } from "./transakcje";

/** Okno wykrywania ekstremów: punkt jest swingiem, gdy dominuje w tym promieniu. */
const OKNO_SWINGU = 5;
/** Ile ostatnich swingów każdego rodzaju zatrzymujemy. */
const ILE_SWINGOW = 4;
const SWIEC_1D = 60;
const SWIEC_1W = 52;
const SWIEC_1M = 60;

export type Swieca = {
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
};

export type Poziom = {
  id: string;
  wartosc: number;
  opis: string;
  rodzaj: "wsparcie" | "opór" | "średnia" | "luka";
  dystans_pct: number;
};

export type Luka = {
  data: string;
  od: number;
  do: number;
  kierunek: "w górę" | "w dół";
};

export type Poziomy = {
  kurs: number;
  atr: number | null;
  atr_pct: number | null;
  trend: { "1d": string; "1w": string; "1m": string };
  zakres_52t: {
    min: number | null;
    maks: number | null;
    pozycja_pct: number | null;
  };
  wolumen: { ostatni: number; srednia_20: number; krotnosc: number } | null;
  luki: Luka[];
  poziomy: Poziom[];
  swiece: { "1d": Swieca[]; "1w": Swieca[]; "1m": Swieca[] };
  sesji_w_historii: number;
};

/**
 * Zaokrąglenie zgodne z `round()` w Pythonie.
 *
 * NIE `Math.round(x * 100) / 100` — mnożenie wprowadza własny błąd
 * (0,595 x 100 daje 59,50000000000001), przez co ta sama liczba wychodzi
 * inaczej po obu stronach. Ta pułapka kosztowała już jeden rozjazd
 * statystyki planów (+0,60 R kontra +0,59 R).
 */
function zaokr(x: number, cyfry: number): number {
  return Number(x.toFixed(cyfry));
}

function skonczona(x: unknown): number | null {
  return typeof x === "number" && Number.isFinite(x) ? x : null;
}

// ---------------------------------------------------------------------------
// Przeliczanie interwałów
// ---------------------------------------------------------------------------

/** Niedziela kończąca tydzień danej daty — etykieta jak w `resample("W")`. */
function koniecTygodnia(dzien: string): string {
  const d = new Date(`${dzien}T00:00:00Z`);
  // getUTCDay(): 0 = niedziela. Do niedzieli zostaje (7 - dzień) % 7 dni.
  const doNiedzieli = (7 - d.getUTCDay()) % 7;
  d.setUTCDate(d.getUTCDate() + doNiedzieli);
  return d.toISOString().slice(0, 10);
}

/** Ostatni dzień miesiąca danej daty — etykieta jak w `resample("ME")`. */
function koniecMiesiaca(dzien: string): string {
  const d = new Date(`${dzien}T00:00:00Z`);
  // Dzień 0 następnego miesiąca to ostatni dzień bieżącego.
  const ostatni = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0));
  return ostatni.toISOString().slice(0, 10);
}

/**
 * Świece dzienne na tygodniowe albo miesięczne: otwarcie pierwsze, maksimum
 * najwyższe, minimum najniższe, zamknięcie ostatnie, wolumen zsumowany.
 */
export function przelicz(swiece: Swieca[], interwal: "W" | "M"): Swieca[] {
  const etykieta = interwal === "W" ? koniecTygodnia : koniecMiesiaca;
  const grupy = new Map<string, Swieca>();
  for (const s of swiece) {
    const klucz = etykieta(s.d);
    const biezaca = grupy.get(klucz);
    if (!biezaca) {
      grupy.set(klucz, { d: klucz, o: s.o, h: s.h, l: s.l, c: s.c, v: s.v });
      continue;
    }
    biezaca.h = Math.max(biezaca.h, s.h);
    biezaca.l = Math.min(biezaca.l, s.l);
    biezaca.c = s.c;
    biezaca.v += s.v;
  }
  return [...grupy.values()].sort((a, b) => a.d.localeCompare(b.d));
}

// ---------------------------------------------------------------------------
// Wskaźniki
// ---------------------------------------------------------------------------

/**
 * Średni rzeczywisty zakres — zmienność w jednostkach ceny.
 *
 * Stop-loss ma sens wyłącznie wobec zmienności papieru: trzy złote to przepaść
 * przy spółce ruszającej się o 50 groszy dziennie i szum przy takiej, która
 * rusza się o pięć.
 */
export function atr(swiece: Swieca[], okres = 14): number | null {
  if (swiece.length < okres + 1) return null;
  const zakresy: number[] = [];
  for (let i = 1; i < swiece.length; i++) {
    const poprzednie = swiece[i - 1].c;
    zakresy.push(
      Math.max(
        swiece[i].h - swiece[i].l,
        Math.abs(swiece[i].h - poprzednie),
        Math.abs(swiece[i].l - poprzednie),
      ),
    );
  }
  const okno = zakresy.slice(-okres);
  if (okno.length < okres) return null;
  const wynik = okno.reduce((a, b) => a + b, 0) / okres;
  return wynik ? zaokr(wynik, 4) : null;
}

/**
 * Lokalne szczyty i dołki, od najnowszych.
 *
 * Ostatnie `okno` sesji jest z definicji niepełne — nie wiadomo jeszcze, czy
 * nie padnie tam wyższy szczyt — więc ich nie zgłaszamy. Poziom, który może
 * się jeszcze zmienić, nie nadaje się na stop-loss.
 */
export function swingi(
  swiece: Swieca[],
  okno = OKNO_SWINGU,
): { gory: [string, number][]; doly: [string, number][] } {
  if (swiece.length < okno * 2 + 1) return { gory: [], doly: [] };
  const gory: [string, number][] = [];
  const doly: [string, number][] = [];
  for (let i = okno; i < swiece.length - okno; i++) {
    const okolica = swiece.slice(i - okno, i + okno + 1);
    const maks = Math.max(...okolica.map((s) => s.h));
    const min = Math.min(...okolica.map((s) => s.l));
    if (swiece[i].h === maks) gory.push([swiece[i].d, zaokr(swiece[i].h, 4)]);
    if (swiece[i].l === min) doly.push([swiece[i].d, zaokr(swiece[i].l, 4)]);
  }
  return { gory: gory.reverse(), doly: doly.reverse() };
}

function srednia(swiece: Swieca[], okres: number): number | null {
  if (swiece.length < okres) return null;
  const zamkniecia = swiece.map((s) => s.c).filter((c) => Number.isFinite(c));
  if (zamkniecia.length < okres) return null;
  const okno = zamkniecia.slice(-okres);
  return zaokr(okno.reduce((a, b) => a + b, 0) / okres, 4);
}

/**
 * Kierunek trendu: cena wobec średniej PLUS nachylenie samej średniej.
 *
 * Sama relacja ceny do średniej nie wystarcza — cena bywa nad opadającą
 * średnią w trakcie odbicia w trendzie spadkowym.
 */
function trend(swiece: Swieca[], okres: number, wstecz: number): string {
  const zamkniecia = swiece.map((s) => s.c).filter((c) => Number.isFinite(c));
  if (zamkniecia.length < okres + wstecz) return "nieokreślony";
  const sredniaDo = (koniec: number): number | null => {
    const okno = zamkniecia.slice(koniec - okres, koniec);
    if (okno.length < okres) return null;
    return okno.reduce((a, b) => a + b, 0) / okres;
  };
  const teraz = sredniaDo(zamkniecia.length);
  const kiedys = sredniaDo(zamkniecia.length - wstecz);
  const cena = zamkniecia[zamkniecia.length - 1];
  if (teraz === null || kiedys === null || !Number.isFinite(cena)) {
    return "nieokreślony";
  }
  const rosnie = teraz > kiedys;
  const nad = cena > teraz;
  if (nad && rosnie) return "wzrostowy";
  if (!nad && !rosnie) return "spadkowy";
  return "boczny";
}

/**
 * Niedomknięte luki cenowe. Za domkniętą uznajemy taką, przez którą cena już
 * przeszła — te pomijamy, bo nie są już żadnym poziomem.
 */
export function luki(swiece: Swieca[], ile = 3): Luka[] {
  if (swiece.length < 2) return [];
  const wynik: Luka[] = [];
  const zamkniecia = swiece.map((s) => s.c).filter((c) => Number.isFinite(c));
  const ostatnia = zamkniecia[zamkniecia.length - 1];
  const granica = Math.max(0, swiece.length - 120);
  for (let i = swiece.length - 1; i > granica; i--) {
    const wGore = swiece[i].l > swiece[i - 1].h;
    const wDol = swiece[i].h < swiece[i - 1].l;
    if (!wGore && !wDol) continue;
    const od = wGore ? swiece[i - 1].h : swiece[i].h;
    const doKad = wGore ? swiece[i].l : swiece[i - 1].l;
    if (Math.min(od, doKad) <= ostatnia && ostatnia <= Math.max(od, doKad)) {
      continue;
    }
    wynik.push({
      data: swiece[i].d,
      od: zaokr(Math.min(od, doKad), 4),
      do: zaokr(Math.max(od, doKad), 4),
      kierunek: wGore ? "w górę" : "w dół",
    });
    if (wynik.length >= ile) break;
  }
  return wynik;
}

function ogon(swiece: Swieca[], ile: number): Swieca[] {
  return swiece.slice(-ile).map((s) => ({
    d: s.d,
    o: zaokr(s.o, 4),
    h: zaokr(s.h, 4),
    l: zaokr(s.l, 4),
    c: zaokr(s.c, 4),
    v: Math.round(s.v),
  }));
}

// ---------------------------------------------------------------------------
// Komplet
// ---------------------------------------------------------------------------

/**
 * Komplet poziomów i kontekstu dla jednej spółki.
 *
 * `swiece` to dzienne OHLC rosnąco. Tygodniowe i miesięczne przeliczamy sami,
 * zamiast pobierać osobno — mniej zapytań i pewność, że wszystkie trzy
 * interwały opisują dokładnie ten sam zakres dat.
 */
export function zbuduj(swiece: Swieca[], kurs?: number | null): Poziomy | null {
  if (!swiece || swiece.length < 60) return null;
  const zamkniecia = swiece.map((s) => s.c).filter((c) => Number.isFinite(c));
  if (zamkniecia.length === 0) return null;
  const cena = skonczona(kurs) ?? zamkniecia[zamkniecia.length - 1];
  if (cena <= 0) return null;

  const tyg = przelicz(swiece, "W");
  const mies = przelicz(swiece, "M");
  const { gory, doly } = swingi(swiece);
  const a = atr(swiece);

  const rok = swiece.slice(-252);
  const szczyt52 = rok.length ? Math.max(...rok.map((s) => s.h)) : null;
  const dolek52 = rok.length ? Math.min(...rok.map((s) => s.l)) : null;

  const poziomy: Poziom[] = [];
  const dodaj = (
    id: string,
    wartosc: number | null,
    opis: string,
    rodzaj: Poziom["rodzaj"],
  ): void => {
    const w = skonczona(wartosc);
    if (w === null || w <= 0) return;
    poziomy.push({
      id,
      wartosc: zaokr(w, 4),
      opis,
      rodzaj,
      dystans_pct: zaokr(((w - cena) / cena) * 100, 2),
    });
  };

  doly.slice(0, ILE_SWINGOW).forEach(([dzien, w], nr) => {
    dodaj(`swing_low_${nr + 1}`, w, `dołek swingu 1D z ${dzien}`, "wsparcie");
  });
  gory.slice(0, ILE_SWINGOW).forEach(([dzien, w], nr) => {
    dodaj(`swing_high_${nr + 1}`, w, `szczyt swingu 1D z ${dzien}`, "opór");
  });

  for (const okres of [20, 50, 200]) {
    dodaj(
      `sma${okres}`,
      srednia(swiece, okres),
      `średnia ${okres}-sesyjna`,
      "średnia",
    );
  }
  dodaj("sma_tyg_10", srednia(tyg, 10), "średnia 10-tygodniowa", "średnia");

  dodaj("szczyt_52t", szczyt52, "szczyt 52 tygodni", "opór");
  dodaj("dolek_52t", dolek52, "dołek 52 tygodni", "wsparcie");

  const listaLuk = luki(swiece);
  listaLuk.forEach((l, nr) => {
    dodaj(`luka_${nr + 1}_od`, l.od, `luka ${l.kierunek} z ${l.data} (brzeg)`, "luka");
    dodaj(`luka_${nr + 1}_do`, l.do, `luka ${l.kierunek} z ${l.data} (brzeg)`, "luka");
  });

  let wolumen: Poziomy["wolumen"] = null;
  if (swiece.length >= 20) {
    const ostatni = swiece[swiece.length - 1].v;
    const ostatnie20 = swiece.slice(-20).map((s) => s.v);
    const srednia20 =
      ostatnie20.reduce((x, y) => x + y, 0) / ostatnie20.length;
    if (Number.isFinite(ostatni) && srednia20) {
      wolumen = {
        ostatni: Math.trunc(ostatni),
        srednia_20: Math.trunc(srednia20),
        krotnosc: zaokr(ostatni / srednia20, 2),
      };
    }
  }

  const pozycja =
    szczyt52 !== null && dolek52 !== null && szczyt52 > dolek52
      ? zaokr(((cena - dolek52) / (szczyt52 - dolek52)) * 100, 1)
      : null;

  return {
    kurs: zaokr(cena, 4),
    atr: a,
    atr_pct: a ? zaokr((a / cena) * 100, 2) : null,
    trend: {
      "1d": trend(swiece, 20, 10),
      "1w": trend(tyg, 10, 4),
      "1m": trend(mies, 12, 3),
    },
    zakres_52t: {
      min: dolek52 !== null ? zaokr(dolek52, 4) : null,
      maks: szczyt52 !== null ? zaokr(szczyt52, 4) : null,
      pozycja_pct: pozycja,
    },
    wolumen,
    luki: listaLuk,
    poziomy: poziomy.sort((x, y) => x.wartosc - y.wartosc),
    swiece: {
      "1d": ogon(swiece, SWIEC_1D),
      "1w": ogon(tyg, SWIEC_1W),
      "1m": ogon(mies, SWIEC_1M),
    },
    sesji_w_historii: swiece.length,
  };
}

/**
 * Poziomy dla tickera prosto z Yahoo. `null`, gdy notowań nie ma albo jest
 * ich za mało (mniej niż 60 sesji — świeże IPO, wycofany instrument).
 */
export async function dlaTickera(
  ticker: string,
): Promise<(Poziomy & { waluta: string; waluta_w_podjednostkach: boolean }) | null> {
  // 10 lat i ceny skorygowane — DOKŁADNIE to, co pobiera
  // `scripts/przygotuj_dossier.py` (`period="10y"`, `auto_adjust=True`).
  // Krótszy okres dałby inne świece miesięczne i inny trend 1M, a ceny
  // nieskorygowane — inne swingi i inny zakres 52 tygodni na spółkach
  // dywidendowych. Lustro musi brać te same dane, nie podobne.
  const n = await notowania(ticker, "10y", true);
  if (!n) return null;
  const swiece: Swieca[] = n.dni.map((d, i) => ({
    d,
    o: n.otwarcie[i],
    h: n.najwyzsze[i],
    l: n.najnizsze[i],
    c: n.zamkniecie[i],
    v: n.wolumen[i],
  }));
  const p = zbuduj(swiece);
  if (!p) return null;
  return {
    ...p,
    waluta: n.waluta,
    waluta_w_podjednostkach: skalaCeny(n.waluta) !== 1,
  };
}
