import Link from "next/link";
import { MIN_SESJI, MAKS_SPOLEK, type Macierz } from "@/lib/korelacje";

/**
 * Macierz korelacji obserwowanych spółek.
 *
 * ZA PRZYCISKIEM, NIE AUTOMATYCZNIE — liczy się z historii cen, czyli
 * z jednego zapytania do bazy na spółkę. Ta sama zasada, co przy danych
 * „na żądanie” w Streamlicie: nie płacimy za coś, czego nikt nie otworzył.
 */

/** Kolor tła komórki. Mocna korelacja = ryzyko koncentracji, więc cieplej. */
function tlo(r: number): string {
  if (r >= 0.7) return "rgba(220, 80, 60, 0.22)";
  if (r >= 0.4) return "rgba(220, 150, 60, 0.18)";
  if (r <= -0.3) return "rgba(70, 130, 200, 0.18)";
  return "transparent";
}

export default function Korelacje({
  macierz,
  pominieto,
}: {
  macierz: Macierz | null;
  /** Ile spółek nie zmieściło się w limicie. */
  pominieto: number;
}) {
  if (!macierz) {
    return (
      <p className="pusto">
        Potrzeba co najmniej dwóch obserwowanych spółek, żeby policzyć
        korelację.
      </p>
    );
  }

  const { tickery, wartosci, minSesji, maksSesji } = macierz;
  const zaKrotko = maksSesji < MIN_SESJI;

  return (
    <>
      <p className="drobne">
        Liczone z <b>{minSesji === maksSesji ? maksSesji : `${minSesji}–${maksSesji}`}</b>{" "}
        dziennych zwrotów z naszych własnych skanów — nie z pełnej historii
        giełdowej. Skan chodzi raz na dobę od sierpnia 2026, więc szereg jest
        krótki: przy dwudziestu obserwacjach prawdziwe 0,5 potrafi wyjść między
        0,3 a 0,7. <b>Traktuj to jako wskazówkę, nie pomiar</b> — z każdym
        kolejnym skanem robi się dokładniejsze samo.
        {pominieto > 0 && (
          <>
            {" "}
            Pokazujemy pierwszych {MAKS_SPOLEK} spółek; {pominieto}{" "}
            {pominieto === 1 ? "pominięto" : "pominięto"}.
          </>
        )}
      </p>

      {zaKrotko ? (
        <p className="pusto">
          Za mało wspólnych sesji, żeby cokolwiek policzyć (potrzeba{" "}
          {MIN_SESJI}, jest {maksSesji}). Wróć tu po kilku kolejnych skanach.
        </p>
      ) : (
        <div className="scroll">
          <table className="tab-korelacje">
            <thead>
              <tr>
                <th />
                {tickery.map((t) => (
                  <th key={t} className="r">
                    {t}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tickery.map((t, i) => (
                <tr key={t}>
                  <td className="t">
                    <Link
                      className="ticker-link"
                      href={`/spolka/${encodeURIComponent(t)}`}
                    >
                      {t}
                    </Link>
                  </td>
                  {tickery.map((u, j) => {
                    const r = wartosci[i][j];
                    return (
                      <td
                        key={u}
                        className="r n"
                        style={r === null ? undefined : { background: tlo(r) }}
                      >
                        {r === null ? (
                          <span className="brak">—</span>
                        ) : (
                          r.toLocaleString("pl-PL", {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="drobne">
        Blisko <b>1,0</b> — spółki poruszają się razem, czyli obserwujesz w
        praktyce jeden zakład. Blisko <b>0</b> — niezależne. <b>Ujemne</b> —
        poruszają się przeciwnie. Kreska znaczy, że para ma mniej niż{" "}
        {MIN_SESJI} wspólnych sesji.
      </p>
    </>
  );
}
