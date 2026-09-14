/**
 * Spis treści publicznego API — punkt, od którego zaczyna maszyna researchowa.
 *
 * Trasa jest SAMOOPISUJĄCA się celowo: model, który dostanie ten JSON, ma
 * z niego wiedzieć, czego może zażądać dalej i jak stare są dane, bez
 * sięgania po żadną dokumentację. Instrukcja Projektu w Claude może się
 * rozjechać z kodem, ten spis nie może — jest generowany z tego samego
 * miejsca, które obsługuje zapytania.
 */
import { migawka } from "@/lib/dane";
import { odpowiedz, blad } from "@/lib/api";
import { WERSJA, wiekRoboczy, ILE_W_RANKINGU } from "@/lib/publiczne";
import { STRATEGIE } from "@/lib/strategie";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(): Promise<Response> {
  let m;
  try {
    m = await migawka();
  } catch (e) {
    return blad(
      503,
      `Baza nie odpowiada: ${e instanceof Error ? e.message : String(e)}`,
      "Spróbuj ponownie za chwilę. Jeśli to się powtarza, dane w raporcie " +
        "trzeba zebrać wyłącznie z sieci i wyraźnie to zaznaczyć.",
    );
  }

  const wiek = wiekRoboczy(m.data);
  return odpowiedz({
    nazwa: "XTB Screener — publiczne dane rynkowe",
    wersja: WERSJA,
    jezyk: "pl",
    migawka: {
      data: m.data,
      instrumentow: m.instrumenty.length,
      wiek_dni_roboczych: wiek,
      aktualna: wiek <= 3,
    },
    czym_to_jest:
      "Wyniki codziennego skanu ~1300 akcji i ETF-ów dostępnych na XTB: kursy, " +
      "wskaźniki techniczne i fundamentalne, autorskie scoringi, czerwone flagi. " +
      "Dane liczone raz na dobę po zamknięciu sesji, źródłem notowań jest Yahoo " +
      "Finance.",
    punkty: [
      {
        adres: "/api/dane/szukaj?q=<fraza>",
        po_co: "Zamiana nazwy na ticker. Szukaj tak, zanim zgadniesz ticker.",
        przyklad: "/api/dane/szukaj?q=ferro",
      },
      {
        adres: "/api/dane/spolka/<TICKER>",
        po_co:
          "Wszystko, co skan wie o jednej spółce: pełny wiersz migawki, kierunek " +
          "zmiany wskaźników 7d i 30d, mediany jej sektora, obecność w rankingach " +
          "i nasza historia ceny.",
        przyklad: "/api/dane/spolka/FRO.WA",
      },
      {
        adres: "/api/dane/notowania/<TICKER>",
        po_co:
          "Poziomy techniczne liczone NA ŻYWO z surowego OHLC: ATR, swingi, " +
          "średnie, zakres 52 tygodni, niedomknięte luki, świece 1D/1W/1M. " +
          "Te liczby są jedynymi, z których wolno budować plan wejścia.",
        parametry: "?swiece=nie — sama tabela poziomów, bez świec (mniejsza paczka)",
        przyklad: "/api/dane/notowania/FRO.WA",
      },
      {
        adres: "/api/dane/finanse/<TICKER>",
        po_co:
          "Sprawozdania finansowe: cztery lata i pięć kwartałów — przychody, " +
          "koszty, marże, przepływy operacyjne, nakłady, dług netto, liczba akcji, " +
          "plus policzone marże i relacja przepływów do zysku. Weź to STĄD zamiast " +
          "szukać sprawozdań w sieci.",
        przyklad: "/api/dane/finanse/ALE.WA",
      },
      {
        adres: "/api/dane/kurs",
        po_co:
          "Kursy walut z NBP (tabela A) do przeliczenia pozycji na złote. Bez " +
          "parametru USD, EUR, GBP i CHF naraz.",
        parametry: "?waluta=SEK — dowolna inna waluta",
        przyklad: "/api/dane/kurs",
      },
      {
        adres: "/api/dane/rankingi",
        po_co: `Czołowe ${ILE_W_RANKINGU} spółek w każdym z ${STRATEGIE.length + 1} rankingów.`,
        parametry: "?ile=<1-30>, ?klucz=<klucz rankingu>",
        przyklad: "/api/dane/rankingi?klucz=wartosc-zlozona&ile=5",
      },
    ],
    czego_tu_nie_ma: [
      "Raportów bieżących, transkrypcji konferencji, transakcji insiderów " +
        "i powodów spadków — tego szukaj w sieci, najlepiej WYSZUKIWARKĄ, " +
        "a pobieraj konkretny adres dopiero wtedy, gdy wynik wyszukiwania " +
        "nie wystarcza.",
      "Krótkich pozycji i rekomendacji analityków dla części rynków — w migawce " +
        "są tylko tam, gdzie skan zdołał je pobrać; pole 'BRAK' znaczy brak danych, " +
        "nie zero.",
      "Czegokolwiek o użytkowniku: kont, watchlist, alarmów, planów, transakcji. " +
        "Te dane zostają za logowaniem i nie ma do nich trasy.",
    ],
    jak_czytac: [
      "'BRAK' w polu liczbowym znaczy: dostawca nie podał wartości. Nigdy nie " +
        "traktuj tego jako zera i nie uzupełniaj z pamięci — sprawdź w sieci albo " +
        "napisz w raporcie, że danych nie ma.",
      "Ceny są w walucie notowania. Londyn Yahoo podaje w PENSACH ('GBp'), więc " +
        "kurs 122,30 znaczy 1,22 funta — pole 'waluta_w_podjednostkach' mówi o tym " +
        "wprost.",
      "Scoringi ('Score: ...', 'Buy Score') to autorskie rankingi wewnątrz tego " +
        "uniwersum, nie standard rynkowy. Nie cytuj ich bez wyjaśnienia, czym są.",
    ],
  });
}
