/**
 * Kształt danych oddawanych przez PUBLICZNE trasy `/api/dane/*`.
 *
 * PO CO TO ISTNIEJE. Cała aplikacja siedzi za logowaniem, więc Claude
 * w przeglądarce w pracy nie ma jak dosięgnąć wyników skanu — a bez nich
 * research spółki sprowadza się do tego, co model znajdzie w sieci, czyli
 * do danych bez naszych scoringów, flag i historii. Te trasy są jedynym
 * wyjątkiem od reguły „wszystko za logowaniem" i wyjątek ma ściśle
 * wyznaczoną granicę.
 *
 * CO WOLNO ODDAĆ: wyłącznie dane RYNKOWE — kursy, wskaźniki, scoringi,
 * rankingi. Wszystkie są wyliczone z publicznych notowań; ujawnienie ich
 * nikogo nie naraża, a dają maszynie researchowej to, czego w sieci nie ma.
 *
 * CZEGO NIE WOLNO ODDAĆ NIGDY: kont, sesji, alarmów, watchlist, planów dnia
 * i analizy transakcji. To są dane o użytkowniku, nie o rynku — z nich składa
 * się obraz portfela. Ten moduł nie importuje `lib/konta`, `lib/alarmy`,
 * `lib/obserwowane`, `lib/plany` ani `lib/transakcje` i nie powinien zacząć.
 * Gdyby kiedyś miał, trasa przestaje być publiczna i potrzebuje tokenu.
 */
import { migawka, historiaSpolki, type Migawka } from "./dane";
import { liczba, porownajRemis, type Instrument } from "./filtry";
import { STRATEGIE } from "./strategie";
import { statystykiSektora, WSKAZNIKI_SEKTORA } from "./sektor";

/** Wersja kontraktu. Podbij, gdy zmieni się ZNACZENIE pola, nie gdy dojdzie nowe. */
export const WERSJA = 1;

/** Ile pozycji oddaje ranking. Dziesięć mieści się w rozmowie i wystarcza. */
export const ILE_W_RANKINGU = 10;

/**
 * Wskaźniki, których KIERUNEK ZMIANY niesie informację.
 *
 * Sam poziom RSI mówi mało; RSI 38 spadające z 62 przez dwa tygodnie to
 * zupełnie inna sytuacja niż RSI 38 odbijające od 22. Dlatego przy każdej
 * spółce oddajemy nie tylko dzisiejszą wartość, ale i stan sprzed tygodnia
 * i miesiąca.
 */
const WSKAZNIKI_KIERUNKU = [
  "Cena",
  "RSI",
  "Buy Score",
  "C/Z (P/E)",
  "pct_from_ath",
  "Stopa Dyw. (%)",
  "Cena docelowa (analitycy)",
  "Liczba flag",
] as const;

function zaokr(x: number, cyfry: number): number {
  return Number(x.toFixed(cyfry));
}

/** Ile dni ROBOCZYCH minęło od daty migawki. Weekend nie starzeje danych. */
export function wiekRoboczy(dataMigawki: string, dzisiaj = new Date()): number {
  const od = new Date(`${dataMigawki}T00:00:00Z`);
  if (Number.isNaN(od.getTime())) return -1;
  const do_ = new Date(
    Date.UTC(dzisiaj.getUTCFullYear(), dzisiaj.getUTCMonth(), dzisiaj.getUTCDate()),
  );
  let dni = 0;
  const kursor = new Date(od);
  while (kursor < do_) {
    kursor.setUTCDate(kursor.getUTCDate() + 1);
    const dzien = kursor.getUTCDay();
    if (dzien !== 0 && dzien !== 6) dni++;
  }
  return dni;
}

// ---------------------------------------------------------------------------
// Wyszukiwanie
// ---------------------------------------------------------------------------

export type Trafienie = {
  ticker: string;
  nazwa: string;
  rynek: string;
  typ: string;
  sektor: string;
};

function opis(i: Instrument): Trafienie {
  return {
    ticker: String(i.Ticker ?? ""),
    nazwa: String(i.Nazwa ?? ""),
    rynek: String(i.Rynek ?? ""),
    typ: String(i.Typ ?? ""),
    sektor: String(i.Sektor ?? ""),
  };
}

/**
 * Szukanie po tickerze i nazwie. Trafienie w ticker stoi wyżej niż w nazwie —
 * kto wpisuje „KO", szuka Coca-Coli, a nie każdej spółki z „ko" w nazwie.
 */
export function szukaj(
  instrumenty: Instrument[],
  zapytanie: string,
  limit = 25,
): Trafienie[] {
  const q = zapytanie.trim().toLowerCase();
  if (!q) return [];
  const dokladne: Instrument[] = [];
  const poTickerze: Instrument[] = [];
  const poNazwie: Instrument[] = [];
  for (const i of instrumenty) {
    const t = String(i.Ticker ?? "").toLowerCase();
    const n = String(i.Nazwa ?? "").toLowerCase();
    if (t === q) dokladne.push(i);
    else if (t.includes(q)) poTickerze.push(i);
    else if (n.includes(q)) poNazwie.push(i);
  }
  return [...dokladne, ...poTickerze, ...poNazwie].slice(0, limit).map(opis);
}

// ---------------------------------------------------------------------------
// Rankingi
// ---------------------------------------------------------------------------

export type PozycjaRankingu = {
  miejsce: number;
  ticker: string;
  nazwa: string;
  rynek: string;
  wynik: number;
  maks: number;
  cena: number | null;
  waluta: string;
  spadek_od_ath_pct: number | null;
  flag: number | null;
};

/**
 * Czołówka jednego rankingu.
 *
 * Remisy rozstrzyga `porownajRemis()` — ta sama reguła co w Screenerze,
 * Strategiach i backteście. Bez niej o czołówce decydowałaby kolejność
 * wierszy z bazy, bo wyniki strategii są całkowite i niskie, więc remisuje
 * po kilkanaście spółek naraz.
 */
export function ranking(
  instrumenty: Instrument[],
  kolumnaScore: string,
  maks: number,
  ile = ILE_W_RANKINGU,
): PozycjaRankingu[] {
  return instrumenty
    .filter((i) => i.Typ === "stock" && liczba(i[kolumnaScore]) !== null)
    .sort((a, b) => {
      const wa = liczba(a[kolumnaScore]) ?? -1;
      const wb = liczba(b[kolumnaScore]) ?? -1;
      if (wa !== wb) return wb - wa;
      return porownajRemis(a, b);
    })
    .slice(0, ile)
    .map((i, nr) => ({
      miejsce: nr + 1,
      ticker: String(i.Ticker ?? ""),
      nazwa: String(i.Nazwa ?? ""),
      rynek: String(i.Rynek ?? ""),
      wynik: liczba(i[kolumnaScore]) ?? 0,
      maks,
      cena: liczba(i.Cena),
      waluta: String(i.Waluta ?? ""),
      spadek_od_ath_pct: liczba(i.pct_from_ath),
      flag: liczba(i["Liczba flag"]),
    }));
}

export type Rankingi = {
  data_migawki: string;
  rankingi: {
    klucz: string;
    nazwa: string;
    kolumna: string;
    maks: number;
    opis: string;
    czolowka: PozycjaRankingu[];
  }[];
};

/**
 * Wszystkie rankingi naraz: dziewięć strategii plus bazowy Buy Score.
 *
 * Buy Score jest tu celowo, mimo że nie jest strategią — to najszersze
 * sito techniczne i punkt wyjścia, gdy żadna strategia nie podpowiada nic
 * ciekawego.
 */
export function wszystkieRankingi(m: Migawka, ile = ILE_W_RANKINGU): Rankingi {
  const lista = STRATEGIE.map((s) => ({
    klucz: s.klucz,
    nazwa: s.nazwa,
    kolumna: s.kolumnaScore,
    maks: s.maks,
    opis: s.opis,
    czolowka: ranking(m.instrumenty, s.kolumnaScore, s.maks, ile),
  }));
  lista.push({
    klucz: "buy-score",
    nazwa: "Buy Score (bazowy scoring techniczny)",
    kolumna: "Buy Score",
    maks: 9,
    opis:
      "Nie jest strategią, tylko wspólnym scoringiem technicznym liczonym " +
      "dla każdego instrumentu: położenie wobec średnich, RSI, MACD, wolumen, " +
      "dystans od ATH. Punkt wyjścia, gdy żadna strategia nie podpowiada nic " +
      "ciekawego.",
    czolowka: ranking(m.instrumenty, "Buy Score", 9, ile),
  });
  return { data_migawki: m.data, rankingi: lista };
}

// ---------------------------------------------------------------------------
// Pojedyncza spółka
// ---------------------------------------------------------------------------

export type Kierunek = {
  wskaznik: string;
  teraz: number | null;
  tydzien_temu: number | null;
  miesiac_temu: number | null;
  zmiana_7d: number | null;
  zmiana_30d: number | null;
};

/** Wiersz historii najbliższy podanej liczbie dni wstecz, ale NIE nowszy. */
function wierszSprzed(
  historia: { dzien: string; wiersz: Instrument }[],
  dni: number,
): Instrument | null {
  if (historia.length === 0) return null;
  const ostatni = new Date(`${historia[historia.length - 1].dzien}T00:00:00Z`);
  const cel = new Date(ostatni);
  cel.setUTCDate(cel.getUTCDate() - dni);
  let wybrany: Instrument | null = null;
  for (const h of historia) {
    if (new Date(`${h.dzien}T00:00:00Z`) <= cel) wybrany = h.wiersz;
  }
  return wybrany;
}

function kierunki(
  teraz: Instrument,
  historia: { dzien: string; wiersz: Instrument }[],
): Kierunek[] {
  const tydzien = wierszSprzed(historia, 7);
  const miesiac = wierszSprzed(historia, 30);
  return WSKAZNIKI_KIERUNKU.map((w) => {
    const t = liczba(teraz[w]);
    const t7 = tydzien ? liczba(tydzien[w]) : null;
    const t30 = miesiac ? liczba(miesiac[w]) : null;
    return {
      wskaznik: w,
      teraz: t,
      tydzien_temu: t7,
      miesiac_temu: t30,
      zmiana_7d: t !== null && t7 !== null ? zaokr(t - t7, 4) : null,
      zmiana_30d: t !== null && t30 !== null ? zaokr(t - t30, 4) : null,
    };
  });
}

export type NaTleSektora = {
  sektor: string;
  spolek_w_probie: number;
  wskazniki: {
    kolumna: string;
    spolka: number | null;
    mediana_sektora: number;
    lepiej_znaczy: "wyzej" | "nizej";
  }[];
} | null;

function naTleSektora(m: Migawka, s: Instrument): NaTleSektora {
  const klucze = WSKAZNIKI_SEKTORA.map((w) => w.kolumna);
  const stat = statystykiSektora(m.instrumenty, String(s.Sektor ?? ""), klucze);
  if (!stat) return null;
  return {
    sektor: stat.sektor,
    spolek_w_probie: stat.liczbaSpolek,
    wskazniki: WSKAZNIKI_SEKTORA.filter(
      (w) => stat.mediany[w.kolumna] !== undefined,
    ).map((w) => ({
      kolumna: w.kolumna,
      spolka: liczba(s[w.kolumna]),
      mediana_sektora: zaokr(stat.mediany[w.kolumna], 4),
      lepiej_znaczy: w.kierunek,
    })),
  };
}

/** W których dzisiejszych czołówkach stoi ta spółka. */
function wRankingach(
  m: Migawka,
  ticker: string,
): { ranking: string; miejsce: number; wynik: number; maks: number }[] {
  const wynik: { ranking: string; miejsce: number; wynik: number; maks: number }[] = [];
  for (const r of wszystkieRankingi(m).rankingi) {
    const poz = r.czolowka.find((p) => p.ticker === ticker);
    if (poz) {
      wynik.push({
        ranking: r.nazwa,
        miejsce: poz.miejsce,
        wynik: poz.wynik,
        maks: poz.maks,
      });
    }
  }
  return wynik;
}

export type Spolka = {
  ticker: string;
  nazwa: string;
  rynek: string;
  sektor: string;
  branza: string;
  typ: string;
  waluta: string;
  waluta_w_podjednostkach: boolean;
  migawka: { data: string; wiek_dni_roboczych: number; dane: Instrument };
  kierunek_wskaznikow: Kierunek[];
  na_tle_sektora: NaTleSektora;
  w_rankingach: { ranking: string; miejsce: number; wynik: number; maks: number }[];
  historia_ceny: { d: string; c: number }[];
};

/**
 * Wszystko, co skan wie o jednej spółce.
 *
 * `waluta_w_podjednostkach` to nie ozdoba: Yahoo notuje Londyn w PENSACH,
 * więc kurs „122,30" znaczy 1,22 funta. Plan wejścia ułożony „w funtach" dla
 * ceny podanej w pensach byłby 100x nie taki.
 */
export async function spolka(ticker: string): Promise<Spolka | null> {
  const m = await migawka();
  const wiersz = m.instrumenty.find(
    (i) => String(i.Ticker ?? "").toUpperCase() === ticker.toUpperCase(),
  );
  if (!wiersz) return null;

  const historia = await historiaSpolki(String(wiersz.Ticker));
  const waluta = String(wiersz.Waluta ?? "");

  return {
    ticker: String(wiersz.Ticker),
    nazwa: String(wiersz.Nazwa ?? ""),
    rynek: String(wiersz.Rynek ?? ""),
    sektor: String(wiersz.Sektor ?? ""),
    branza: String(wiersz["Branża"] ?? ""),
    typ: String(wiersz.Typ ?? ""),
    waluta,
    waluta_w_podjednostkach: Boolean(waluta) && waluta !== waluta.toUpperCase(),
    migawka: {
      data: m.data,
      wiek_dni_roboczych: wiekRoboczy(m.data),
      dane: wiersz,
    },
    kierunek_wskaznikow: kierunki(wiersz, historia),
    na_tle_sektora: naTleSektora(m, wiersz),
    w_rankingach: wRankingach(m, String(wiersz.Ticker)),
    historia_ceny: historia
      .map((h) => ({ d: h.dzien, c: liczba(h.wiersz.Cena) }))
      .filter((p): p is { d: string; c: number } => p.c !== null),
  };
}
