import Link from "next/link";
import Wykres from "./Wykres";

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
}: {
  ticker: string;
  nazwa: string;
  symbol: string;
  adresZamkniecia: string;
}) {
  return (
    <div className="naklada" role="dialog" aria-modal="true" aria-label={`Wykres ${ticker}`}>
      <div className="naklada-okno">
        <div className="naklada-pasek">
          <div>
            <strong>{ticker}</strong>
            <span className="brak"> · {nazwa}</span>
          </div>
          <Link href={adresZamkniecia} className="naklada-zamknij" aria-label="Zamknij wykres">
            ✕
          </Link>
        </div>
        <Wykres symbol={symbol} pelnyEkran />
      </div>
      {/* Kliknięcie w tło też zamyka — bez tego jedynym wyjściem byłby mały
          krzyżyk w rogu, co na telefonie jest niewygodne. */}
      <Link href={adresZamkniecia} className="naklada-tlo" aria-hidden="true" tabIndex={-1} />
    </div>
  );
}
