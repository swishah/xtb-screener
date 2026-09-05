import Link from "next/link";
import { liczba, type Instrument } from "@/lib/filtry";

/**
 * Tabela instrumentów. Komponent serwerowy — nie ma tu stanu ani zdarzeń,
 * więc do przeglądarki nie leci ani bajt JavaScriptu na jej obsługę.
 *
 * Formatowanie liczb polskie (przecinek dziesiętny, spacja jako separator
 * tysięcy) i nierozdzielające spacje, żeby wartość nie łamała się w pół.
 */
function fmt(wartosc: unknown, cyfry = 2, sufiks = ""): React.ReactNode {
  const n = liczba(wartosc);
  if (n === null) return <span className="brak">BRAK</span>;
  const tekst = n.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  });
  return `${tekst}${sufiks}`;
}

export default function Tabela({
  wiersze,
  link,
  linkWykres,
  wybrany,
}: {
  wiersze: Instrument[];
  /**
   * Dokąd prowadzi kliknięcie w spółkę. Screener podaje adres otwierający
   * panel boczny obok listy, pulpit — pełną stronę profilu. Bez tej funkcji
   * tickery zostają zwykłym tekstem.
   */
  link?: (ticker: string) => string;
  /**
   * Adres otwierający wykres na pełnym ekranie. Osobno od "link", bo to dwie
   * różne intencje: profil obok listy i wykres na cały ekran.
   */
  linkWykres?: (ticker: string) => string;
  wybrany?: string;
}) {
  if (wiersze.length === 0) {
    return (
      <p style={{ padding: "16px", color: "var(--muted)" }}>
        Brak instrumentów spełniających kryteria.
      </p>
    );
  }

  return (
    <div className="scroll">
      <table>
        <thead>
          <tr>
            <th>Spółka</th>
            {linkWykres && <th className="kol-wykres">Wykres</th>}
            <th className="r">Cena</th>
            <th className="r">RSI</th>
            <th className="r">Od ATH</th>
            <th className="r">C/Z</th>
            <th className="r">Stopa dyw.</th>
            <th className="r">Score</th>
            <th className="r">Flagi</th>
          </tr>
        </thead>
        <tbody>
          {wiersze.map((w) => {
            const ticker = String(w.Ticker);
            const ath = liczba(w["pct_from_ath"]);
            const flagi = liczba(w["Liczba flag"]);
            const nazwa = String(w.Nazwa ?? "");
            return (
              <tr key={ticker} className={ticker === wybrany ? "wiersz-wybrany" : undefined}>
                <td className="t">
                  {link ? (
                    <Link href={link(ticker)} className="ticker-link">
                      {ticker}
                      <small>{nazwa}</small>
                    </Link>
                  ) : (
                    <>
                      {ticker}
                      <small>{nazwa}</small>
                    </>
                  )}
                </td>
                {linkWykres && (
                  <td className="kol-wykres">
                    <Link
                      href={linkWykres(ticker)}
                      className="btn-wykres"
                      aria-label={`Wykres ${ticker}`}
                      title="Pokaż wykres na pełnym ekranie"
                    >
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M3 3v18h18" />
                        <path d="M7 14l4-5 3 3 5-7" />
                      </svg>
                    </Link>
                  </td>
                )}
                <td className="r n cena">
                  {fmt(w.Cena)} <span className="brak">{String(w.Waluta ?? "")}</span>
                </td>
                <td className="r n rsi" data-l="RSI">
                  {fmt(w.RSI, 1)}
                </td>
                <td
                  className={`r n ath${ath !== null && ath < 0 ? " down" : ""}`}
                  data-l="od ATH"
                >
                  {fmt(ath, 1, "%")}
                </td>
                <td className="r n pe">{fmt(w["C/Z (P/E)"])}</td>
                <td className="r n dyw">{fmt(w["Stopa Dyw. (%)"], 2, "%")}</td>
                <td className="r n score" data-l="score">
                  {fmt(w["Buy Score"], 0)}
                </td>
                <td className="r flagi">
                  <span className={`pill${flagi === 0 ? " good" : ""}`}>
                    {flagi === null ? "?" : flagi}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
