"use server";

import { wczytajPlik } from "@/lib/import_transakcji";
import {
  analizujTransakcje,
  notowania,
  STAN_POCZATKOWY,
  type Notowania,
  type StanAnalizy,
  type WynikTransakcji,
} from "@/lib/transakcje";
import { wymagajZalogowania } from "@/lib/sesja";

/**
 * Analiza wgranego pliku z transakcjami.
 *
 * Akcja zaczyna się od `wymagajZalogowania()` — akcja serwerowa jest zwykłym
 * punktem wejścia po sieci, więc sprawdzenie sesji na stronie nie wystarcza.
 *
 * PLIKU NIGDZIE NIE ZAPISUJEMY. Przechodzi przez pamięć procesu na czas tego
 * jednego żądania; do bazy ani na dysk nie trafia nic. Do sieci wychodzą
 * WYŁĄCZNIE zapytania o historię cen podanych tickerów.
 */

/** Zapory: plik od użytkownika nie może zająć serwera na kwadrans. */
const MAKS_BAJTOW = 8 * 1024 * 1024;
const MAKS_TRANSAKCJI = 500;
const MAKS_TICKEROW = 80;
/** Ile zapytań do Yahoo naraz. Więcej = szybciej, ale łatwiej o odcięcie. */
const ROWNOLEGLE = 4;

function blad(tresc: string): StanAnalizy {
  return { ...STAN_POCZATKOWY, etap: "blad", komunikat: tresc };
}

export async function analizuj(
  _poprzedni: StanAnalizy,
  dane: FormData,
): Promise<StanAnalizy> {
  await wymagajZalogowania();

  const plik = dane.get("plik");
  if (!(plik instanceof File) || plik.size === 0) {
    return blad("Nie wybrano pliku.");
  }
  if (plik.size > MAKS_BAJTOW) {
    return blad(
      `Plik ma ${(plik.size / 1024 / 1024).toFixed(1)} MB, a limit to ${
        MAKS_BAJTOW / 1024 / 1024
      } MB.`,
    );
  }

  const okno = Number(dane.get("okno"));
  const oknoDni = Number.isFinite(okno) ? Math.max(7, Math.min(365, okno)) : 90;
  const tlumaczXtb = dane.get("tlumacz") === "1";

  const bufor = Buffer.from(await plik.arrayBuffer());
  const wczytane = await wczytajPlik(plik.name, bufor, tlumaczXtb);
  if (wczytane.blad) return blad(wczytane.blad);
  if (wczytane.transakcje.length === 0) {
    return blad("W pliku nie znalazłem żadnej transakcji kupna.");
  }

  const transakcje = wczytane.transakcje.slice(0, MAKS_TRANSAKCJI);
  const tickery = [...new Set(transakcje.map((t) => t.ticker))].slice(
    0,
    MAKS_TICKEROW,
  );

  // Historię pobieramy RAZ NA TICKER, nie raz na transakcję — przy dziesięciu
  // zakupach tej samej spółki to dziesięciokrotnie mniej zapytań.
  const historie = new Map<string, Notowania | null>();
  for (let i = 0; i < tickery.length; i += ROWNOLEGLE) {
    const paczka = tickery.slice(i, i + ROWNOLEGLE);
    const pobrane = await Promise.all(paczka.map((t) => notowania(t)));
    paczka.forEach((t, j) => historie.set(t, pobrane[j]));
  }

  const wyniki: WynikTransakcji[] = [];
  const nieudane: string[] = [];
  const przeskalowane = new Set<string>();

  for (const t of transakcje) {
    const n = historie.get(t.ticker);
    if (n === undefined) {
      nieudane.push(`${t.ticker} — pominięty, przekroczony limit ${MAKS_TICKEROW} instrumentów`);
      continue;
    }
    if (n === null) {
      nieudane.push(`${t.ticker} — brak danych cenowych, sprawdź format tickera`);
      continue;
    }
    const wynik = analizujTransakcje(t, n, oknoDni, wczytane.zrodloXtb);
    if (!wynik) {
      nieudane.push(`${t.ticker} — brak notowań z okolic ${t.dataZakupu}`);
      continue;
    }
    if (wynik.przeskalowana) przeskalowane.add(t.ticker);
    wyniki.push(wynik);
  }

  if (wyniki.length === 0) {
    return {
      ...blad(
        "Nie udało się przeanalizować żadnej transakcji. Najczęstsza przyczyna: " +
          "tickery nie są w formacie Yahoo Finance.",
      ),
      nieudane,
      mapa: wczytane.mapa,
    };
  }

  return {
    etap: "gotowe",
    komunikat: null,
    wyniki,
    nieudane,
    mapa: wczytane.mapa,
    zrodloXtb: wczytane.zrodloXtb,
    przeskalowane: [...przeskalowane].sort(),
    wczytanych: wczytane.transakcje.length,
    oknoDni,
  };
}
