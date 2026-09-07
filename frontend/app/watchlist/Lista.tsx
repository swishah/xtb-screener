import Link from "next/link";
import { notatka as zapiszNotatke, przeniesSpolke, usun } from "./akcje";
import { liczba, type Instrument } from "@/lib/filtry";
import { MAKS_NOTATKA, type Lista, type Obserwowana } from "@/lib/obserwowane";

/**
 * Tabela obserwowanych spółek jednej listy. Komponent SERWEROWY — edycja
 * notatki, przeniesienie i usunięcie to zwykłe formularze z akcją serwerową,
 * więc całość działa bez jednego bajtu JavaScriptu.
 *
 * Notatkę zapisuje się per wiersz, a nie zbiorczym przyciskiem jak
 * w Streamlicie. Zbiorczy zapis wymaga stanu całej tabeli, a przy
 * formularzach bez JS oznaczałby wysyłanie wszystkich notatek przy zmianie
 * jednej — i cichy nadpis, gdyby ktoś edytował z drugiego urządzenia.
 */

function fmt(wartosc: unknown, cyfry = 2, sufiks = ""): React.ReactNode {
  const n = liczba(wartosc);
  if (n === null) return <span className="brak">BRAK</span>;
  return `${n.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  })}${sufiks}`;
}

export default function ListaObserwowanych({
  pozycje,
  dane,
  powrot,
  listaId,
  listy,
}: {
  pozycje: Obserwowana[];
  /** Wiersz z najnowszej migawki, po tickerze. Brak = spółka bez danych. */
  dane: Map<string, Instrument>;
  powrot: string;
  listaId: number;
  listy: Lista[];
}) {
  if (pozycje.length === 0) {
    return (
      <p className="pusto">
        Ta lista jest pusta. Dodaj spółkę powyżej albo wejdź na profil spółki
        i kliknij „Obserwuj”.
      </p>
    );
  }

  const inne = listy.filter((l) => l.id !== listaId);

  return (
    <div className="scroll">
      <table className="tab-watchlist">
        <thead>
          <tr>
            <th>Spółka</th>
            <th className="r">Cena</th>
            <th className="r">Od ATH</th>
            <th className="r">C/Z</th>
            <th className="r">Score</th>
            <th className="r">Flagi</th>
            <th>Notatka</th>
            {inne.length > 0 && <th>Przenieś</th>}
            <th />
          </tr>
        </thead>
        <tbody>
          {pozycje.map((p) => {
            const w = dane.get(p.ticker);
            return (
              <tr key={p.ticker}>
                <td className="t">
                  <Link
                    className="ticker-link"
                    href={`/spolka/${encodeURIComponent(p.ticker)}`}
                  >
                    {p.ticker}
                    <small>{String(w?.Nazwa ?? "—")}</small>
                  </Link>
                </td>
                <td className="r n">{fmt(w?.["Cena"])}</td>
                <td className="r n">{fmt(w?.["pct_from_ath"], 1, "%")}</td>
                <td className="r n">{fmt(w?.["C/Z (P/E)"], 1)}</td>
                <td className="r n">{fmt(w?.["Buy Score"], 0)}</td>
                <td className="r n">{fmt(w?.["Liczba flag"], 0)}</td>

                <td className="kol-notatka">
                  <form action={zapiszNotatke} className="form-notatka">
                    <input type="hidden" name="ticker" value={p.ticker} />
                    <input type="hidden" name="lista" value={listaId} />
                    <input type="hidden" name="powrot" value={powrot} />
                    <input
                      type="text"
                      name="notatka"
                      defaultValue={p.notatka}
                      maxLength={MAKS_NOTATKA}
                      placeholder="np. czekam na wyniki Q3"
                      aria-label={`Notatka do ${p.ticker}`}
                    />
                    <button type="submit" title="Zapisz notatkę">
                      Zapisz
                    </button>
                  </form>
                </td>

                {inne.length > 0 && (
                  <td>
                    <form action={przeniesSpolke} className="form-przenies">
                      <input type="hidden" name="ticker" value={p.ticker} />
                      <input type="hidden" name="lista" value={listaId} />
                      <input type="hidden" name="powrot" value={powrot} />
                      <select
                        name="naListe"
                        aria-label={`Przenieś ${p.ticker} na inną listę`}
                        defaultValue={inne[0].id}
                      >
                        {inne.map((l) => (
                          <option key={l.id} value={l.id}>
                            {l.nazwa}
                          </option>
                        ))}
                      </select>
                      <button type="submit" title="Przenieś na wybraną listę">
                        →
                      </button>
                    </form>
                  </td>
                )}

                <td className="r">
                  <form action={usun}>
                    <input type="hidden" name="ticker" value={p.ticker} />
                    <input type="hidden" name="lista" value={listaId} />
                    <input type="hidden" name="powrot" value={powrot} />
                    <button
                      type="submit"
                      className="btn-usun"
                      title={`Usuń ${p.ticker} z tej listy`}
                    >
                      Usuń
                    </button>
                  </form>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
