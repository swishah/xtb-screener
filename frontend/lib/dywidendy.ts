import { liczba, porownajRemis, type Instrument } from "./filtry";

/**
 * Moduł Dywidendy — tanie spółki przed sezonem dywidendowym.
 *
 * ZERO IMPORTÓW Z NODE, tak samo jak `lib/filtry.ts` — to czysta logika.
 *
 * CO OZNACZA "STOPA DYW. (%)" I DLACZEGO TO WAŻNE. Do 2026-09-06 liczyliśmy
 * ją sami: suma wypłat z POPRZEDNIEGO ROKU KALENDARZOWEGO podzielona przez
 * dzisiejszą cenę. Miara okazała się zawodna w dwóch mierzalnych sytuacjach:
 *
 *  - wypłata JEDNORAZOWA wyglądała jak coroczna (TransDigm: 75 i 90 USD
 *    dywidendy specjalnej dawały u nas 7,74% "stopy", przy 0% u Yahoo),
 *  - OBNIŻKA dywidendy była niewidoczna nawet przez 20 miesięcy (Whirlpool:
 *    13,49% u nas kontra 7,01% naprawdę).
 *
 * Od tej daty `Stopa Dyw. (%)` pochodzi z pola `dividendYield` Yahoo, a nasze
 * wyliczenie zostaje osobno jako `Stopa dyw. z roku kal. (%)`. Kolumna
 * `Dywidenda nieregularna` mówi wprost, że Yahoo nie uznaje wypłaty za
 * powtarzalną.
 *
 * MIGAWKI SPRZED TEJ DATY NIE MAJĄ NOWYCH KOLUMN i to jest normalne — moduł
 * musi działać na jednych i drugich. `nowaMetodologia()` sprawdza, czy
 * migawka je niesie, a ekran mówi o tym wprost zamiast po cichu pokazywać
 * starą liczbę jako nową.
 */

export type FiltryDywidend = {
  minStopa: number;
  maksZmiana1Y: number;
  maksPayout: number;
  tylkoPrzedSezonem: boolean;
};

export const DYWIDENDY_DOMYSLNE: FiltryDywidend = {
  minStopa: 4,
  maksZmiana1Y: 15,
  maksPayout: 80,
  tylkoPrzedSezonem: false,
};

export const KOL_SCORE = "Score: Dywidenda-Okazja";

/** Czy migawka pochodzi ze skanu po naprawie liczenia stopy dywidendy. */
export function nowaMetodologia(instrumenty: Instrument[]): boolean {
  return instrumenty.some(
    (i) => i["Źródło stopy dyw."] !== undefined,
  );
}

/** Spółka wypłaciła coś jednorazowo — Yahoo nie uznaje tego za dywidendę. */
export function nieregularna(s: Instrument): boolean {
  return String(s["Dywidenda nieregularna"] ?? "") === "Tak";
}

/**
 * Czy spółka jest jeszcze PRZED tegoroczną wypłatą.
 *
 * Sedno strategii, ale ma wbudowaną sezonowość, o której trzeba wiedzieć:
 * im bliżej końca roku, tym mniej takich spółek, bo większość zdążyła już
 * zapłacić. Na migawce z 4 września 2026 było ich 20 na 1281. W styczniu
 * warunek spełnia niemal każdy płacący — i to nie znaczy, że nagle jest
 * 900 okazji.
 */
export function przedSezonem(s: Instrument): boolean {
  return (
    String(s["Dyw. w poprzednim roku"] ?? "") === "Tak" &&
    String(s["Dyw. w tym roku"] ?? "") === "Nie"
  );
}

export function filtrujDywidendy(
  instrumenty: Instrument[],
  f: FiltryDywidend,
): Instrument[] {
  const wynik = instrumenty.filter((s) => {
    if (String(s.Typ ?? "") !== "stock") return false;

    const stopa = liczba(s["Stopa Dyw. (%)"]);
    if (stopa === null || stopa < f.minStopa) return false;

    // Spółka z wypłatą jednorazową nie należy do tego modułu — nie ma tu
    // sezonu, na który dałoby się czekać. Odsiewamy ją, nawet gdyby ktoś
    // ustawił niski próg stopy.
    if (nieregularna(s)) return false;

    const zmiana = liczba(s["Zmiana ceny (1Y%)"]);
    if (zmiana !== null && zmiana > f.maksZmiana1Y) return false;

    // Brak payout ratio NIE dyskwalifikuje — Yahoo nie podaje go dla części
    // spółek, a odrzucanie ich znaczyłoby karanie za lukę u dostawcy.
    const payout = liczba(s["Payout ratio (%)"]);
    if (payout !== null && payout > f.maksPayout) return false;

    if (f.tylkoPrzedSezonem && !przedSezonem(s)) return false;
    return true;
  });

  // Ta sama reguła remisów co w rankingach strategii: wyniki są całkowite
  // i niskie, więc bez niej czołówka zmienia się między odświeżeniami.
  wynik.sort((a, b) => {
    const rb = liczba(b[KOL_SCORE]) ?? 0;
    const ra = liczba(a[KOL_SCORE]) ?? 0;
    if (rb !== ra) return rb - ra;
    return porownajRemis(a, b);
  });
  return wynik;
}
