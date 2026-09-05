import { liczba, type Instrument } from "@/lib/filtry";
import { czyProcent, etykieta, type Strategia } from "@/lib/strategie";

/**
 * Tabela rankingu strategii. W odróżnieniu od tabeli Screenera ma ZMIENNY
 * zestaw kolumn — każda strategia pokazuje wskaźniki, na których się opiera,
 * bo inaczej nie widać, dlaczego spółka dostała taki wynik.
 *
 * Komponent serwerowy: zero stanu, zero zdarzeń, zero JavaScriptu w przeglądarce.
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
}: {
  wiersze: Instrument[];
  strategia: Strategia;
}) {
  if (wiersze.length === 0) {
    return (
      <p style={{ padding: 16, color: "var(--muted)" }}>
        Żadna spółka nie spełnia kryteriów tej strategii w tej migawce.
      </p>
    );
  }

  return (
    <div className="scroll">
      <table className="tab-strategia">
        <thead>
          <tr>
            <th>Spółka</th>
            <th className="r">Wynik</th>
            {strategia.kolumny.map((k) => (
              <th key={k} className="r">
                {etykieta(k)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {wiersze.map((w) => {
            const score = liczba(w[strategia.kolumnaScore]) ?? 0;
            const udzial = Math.max(0, Math.min(1, score / strategia.maks));
            return (
              <tr key={String(w.Ticker)}>
                <td className="t">
                  {String(w.Ticker)}
                  <small>{String(w.Nazwa ?? "")}</small>
                </td>
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
