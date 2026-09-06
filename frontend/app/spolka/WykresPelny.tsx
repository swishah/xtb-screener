import Link from "next/link";
import Wykres from "./Wykres";
import PrzyciskAlarmu from "../alarmy/PrzyciskAlarmu";

/**
 * Wykres na pełnym ekranie.
 *
 * Wcześniej siedział w panelu bocznym i był tam po prostu nieczytelny —
 * świece na 300 px wysokości przy trzech wskaźnikach na wierzchu nie dawały
 * się odczytać. Teraz zajmuje prawie cały ekran, a panel boczny został tym,
 * czym miał być: samymi danymi spółki.
 *
 * Otwarcie i zamknięcie to zwykłe odnośniki zmieniające adres (?wykres=TICKER),
 * nie stan komponentu. Dzięki temu działa przycisk „wstecz”, da się wysłać
 * komuś link prosto do wykresu, a odświeżenie strony niczego nie gubi.
 */
export default function WykresPelny({
  ticker,
  nazwa,
  symbol,
  adresZamkniecia,
  cena,
  waluta,
  powrot,
}: {
  ticker: string;
  nazwa: string;
  symbol: string;
  adresZamkniecia: string;
  /** Kurs z migawki — panel alarmu bez niego nie ma od czego zacząć. */
  cena?: number | null;
  waluta?: string;
  /** Adres, na który wracamy po ustawieniu alarmu (z wykresem nadal otwartym). */
  powrot?: string;
}) {
  return (
    <div className="naklada" role="dialog" aria-modal="true" aria-label={`Wykres ${ticker}`}>
      <div className="naklada-okno">
        <div className="naklada-pasek">
          <div>
            <strong>{ticker}</strong>
            <span className="brak"> · {nazwa}</span>
          </div>
          <div className="naklada-narzedzia">
            {/* Alarm stawia się TU, bez zamykania wykresu — patrzysz na
                notowanie i od razu wskazujesz próg. Bez ceny z migawki nie ma
                od czego zacząć, więc wtedy przycisku po prostu nie ma. */}
            {typeof cena === "number" && cena > 0 && (
              <PrzyciskAlarmu
                ticker={ticker}
                nazwa={nazwa}
                cena={cena}
                waluta={waluta ?? ""}
                powrot={powrot ?? adresZamkniecia}
              />
            )}
            <Link href={adresZamkniecia} className="naklada-zamknij" aria-label="Zamknij wykres">
              ✕
            </Link>
          </div>
        </div>
        <Wykres symbol={symbol} pelnyEkran />
      </div>
      {/* Kliknięcie w tło też zamyka — bez tego jedynym wyjściem byłby mały
          krzyżyk w rogu, co na telefonie jest niewygodne. */}
      <Link href={adresZamkniecia} className="naklada-tlo" aria-hidden="true" tabIndex={-1} />
    </div>
  );
}
