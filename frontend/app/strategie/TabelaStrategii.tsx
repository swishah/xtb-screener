import Link from "next/link";
import { liczba, type Instrument } from "@/lib/filtry";
import { czyProcent, etykieta, type Strategia } from "@/lib/strategie";

/**
 * Tabela rankingu strategii. W odróżnieniu od tabeli Screenera ma ZMIENNY
 * zestaw kolumn — każda strategia pokazuje wskaźniki, na których się opiera,
 * bo inaczej nie widać, dlaczego spółka dostała taki wynik.
 *
 * Komponent serwerowy: zero stanu, zero zdarzeń, zero JavaScriptu w przeglądarce.
 * Sortowanie też — nagłówki są zwykłymi odnośnikami, a stan siedzi w adresie
 * URL. Dzięki temu posortowany widok da się zapisać w zakładkach i wysłać,
 * a strona nie potrzebuje ani bajta JavaScriptu po stronie przeglądarki.
 */

function formatuj(wartosc: unknown, kolumna: string): React.ReactNode {
  if (wartosc === null || wartosc === undefined || wartosc === "BRAK") {
    return <span className="brak">BRAK</span>;
  }
  // Kolumny "Tak"/"Nie" i daty zostawiamy tekstem — liczbowe formatowanie
  // zrobiłoby z nich NaN.
  if (typeof wartosc === "string" && liczba(wartosc) === null) {
    return wartosc;
  }
  const n = liczba(wartosc);
  if (n === null) return <span className="brak">BRAK</span>;

  const calkowita = Number.isInteger(n);
  const tekst = n.toLocaleString("pl-PL", {
    minimumFractionDigits: calkowita ? 0 : 2,
    maximumFractionDigits: calkowita ? 0 : 2,
  });
  return czyProcent(kolumna) ? `${tekst}%` : tekst;
}

export default function TabelaStrategii({
  wiersze,
  strategia,
  sortKolumna = null,
  sortRosnaco = false,
  link,
  linkWykres,
  wybrany,
}: {
  wiersze: Instrument[];
  strategia: Strategia;
  /** Kolumna, po której sortujemy; null = kolejność wg wyniku strategii. */
  sortKolumna?: string | null;
  sortRosnaco?: boolean;
  /** Kliknięcie w nazwę spółki — otwiera profil w panelu obok listy. */
  link?: (ticker: string) => string;
  /** Osobna kolumna z ikoną — otwiera wykres na prawie całym ekranie. */
  linkWykres?: (ticker: string) => string;
  wybrany?: string;
}) {
  if (wiersze.length === 0) {
    return (
      <p style={{ padding: 16, color: "var(--muted)" }}>
        Żadna spółka nie spełnia kryteriów tej strategii w tej migawce.
      </p>
    );
  }

  const bazowy = `/strategie?s=${strategia.klucz}`;

  // Pierwsze kliknięcie sortuje malejąco (najwyższe wartości na górze — tego
  // ludzie oczekują po kliknięciu w liczbową kolumnę), kolejne odwraca.
  function adresSortowania(kolumna: string): string {
    const odwroc = kolumna === sortKolumna && !sortRosnaco;
    const kier = odwroc ? "&kier=asc" : "";
    return `${bazowy}&sort=${encodeURIComponent(kolumna)}${kier}`;
  }

  function strzalka(kolumna: string): string {
    if (kolumna !== sortKolumna) return "";
    return sortRosnaco ? " ↑" : " ↓";
  }

  return (
    <div className="scroll">
      <table className="tab-strategia">
        <thead>
          <tr>
            <th>Spółka</th>
            {linkWykres && <th className="kol-wykres">Wykres</th>}
            <th
              className="r"
              aria-sort={sortKolumna === null ? "descending" : "none"}
            >
              {sortKolumna === null ? (
                <>Wynik ↓</>
              ) : (
                <Link className="naglowek-sort" href={bazowy}>
                  Wynik
                </Link>
              )}
            </th>
            {strategia.kolumny.map((k) => (
              <th
                key={k}
                className="r"
                aria-sort={
                  k === sortKolumna
                    ? sortRosnaco
                      ? "ascending"
                      : "descending"
                    : "none"
                }
              >
                <Link className="naglowek-sort" href={adresSortowania(k)}>
                  {etykieta(k)}
                  {strzalka(k)}
                </Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {wiersze.map((w) => {
            const score = liczba(w[strategia.kolumnaScore]) ?? 0;
            const udzial = Math.max(0, Math.min(1, score / strategia.maks));
            return (
              <tr
                key={String(w.Ticker)}
                className={
                  String(w.Ticker) === wybrany ? "wiersz-wybrany" : undefined
                }
              >
                <td className="t">
                  {link ? (
                    <Link href={link(String(w.Ticker))} className="ticker-link">
                      {String(w.Ticker)}
                      <small>{String(w.Nazwa ?? "")}</small>
                    </Link>
                  ) : (
                    <>
                      {String(w.Ticker)}
                      <small>{String(w.Nazwa ?? "")}</small>
                    </>
                  )}
                </td>
                {linkWykres && (
                  <td className="kol-wykres">
                    <Link
                      href={linkWykres(String(w.Ticker))}
                      className="btn-wykres"
                      aria-label={`Wykres ${String(w.Ticker)}`}
                      title="Pokaż wykres na pełnym ekranie"
                    >
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M3 3v18h18" />
                        <path d="M7 14l4-5 3 3 5-7" />
                      </svg>
                    </Link>
                  </td>
                )}
                <td className="r wynik" data-l="wynik">
                  <span className="miernik">
                    <span className="miernik-tor">
                      <span className="miernik-wypelnienie" style={{ width: `${udzial * 100}%` }} />
                    </span>
                    <span className="miernik-liczba">
                      {score}
                      <span className="brak"> / {strategia.maks}</span>
                    </span>
                  </span>
                </td>
                {strategia.kolumny.map((k) => (
                  <td key={k} className="r n" data-l={etykieta(k)}>
                    {formatuj(w[k], k)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
