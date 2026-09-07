import Link from "next/link";
import Pasek from "../Pasek";
import Wybor from "./Wybor";
import { migawkaBezpieczna } from "@/lib/dane";
import { liczba, type Instrument } from "@/lib/filtry";
import {
  MIN_SPOLEK_W_SEKTORZE,
  porownajZSektorem,
  type Ocena,
} from "@/lib/sektor";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

const OCENY: Record<Ocena, { tekst: string; klasa: string }> = {
  lepiej: { tekst: "lepiej niż mediana", klasa: "ocena lepiej" },
  gorzej: { tekst: "gorzej niż mediana", klasa: "ocena gorzej" },
  podobnie: { tekst: "podobnie do sektora", klasa: "ocena podobnie" },
  brak: { tekst: "brak danych", klasa: "ocena brak-oceny" },
};

function fmt(w: number | null, cyfry = 2): React.ReactNode {
  if (w === null) return <span className="brak">—</span>;
  return w.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  });
}

export default async function VsSektor({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  await wymagajZalogowania();

  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };

  const { instrumenty, data, tryb, blad } = await migawkaBezpieczna();
  const zSektorem = instrumenty.filter((i) => {
    if (String(i.Typ ?? "") !== "stock") return false;
    const s = String(i.Sektor ?? "").trim();
    return s !== "" && s !== "Nieznany" && s !== "BRAK";
  });

  const zadany = (jeden("spolka") ?? "").toUpperCase();
  const spolka: Instrument | undefined =
    zSektorem.find((i) => String(i.Ticker ?? "").toUpperCase() === zadany) ??
    zSektorem[0];

  const sektor = spolka ? String(spolka.Sektor ?? "") : "";
  const rowiesnicy = zSektorem.filter((i) => String(i.Sektor ?? "") === sektor);
  const porownanie = spolka ? porownajZSektorem(spolka, rowiesnicy) : [];

  const posortowani = [...rowiesnicy].sort(
    (a, b) => (liczba(b["Buy Score"]) ?? 0) - (liczba(a["Buy Score"]) ?? 0),
  );

  return (
    <main className="wrap wrap-szeroki">
      <Pasek dataMigawki={data} tryb={tryb} />

      {blad && (
        <div className="alert">
          <b>Nie udało się wczytać danych.</b>
          <div style={{ marginTop: 8, fontSize: "0.78rem", opacity: 0.75 }}>{blad}</div>
        </div>
      )}

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>vs Sektor</h2>
        <em>migawka z {data}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Jak konkretna spółka wypada na tle <b>mediany swojego sektora</b> w tej
        migawce. To porównanie liczone na żywo na aktualnych danych — inaczej
        niż stałe progi w dymkach Screenera, które są te same dla całego rynku.
        Marża 8% jest słaba w oprogramowaniu i bardzo dobra w handlu detalicznym,
        więc bez odniesienia do branży ocena „dobrze / słabo” wprowadza w błąd.
      </p>

      {zSektorem.length === 0 ? (
        <div className="card" style={{ marginTop: 12, padding: "16px 20px" }}>
          <p className="pusto">
            Ta migawka nie ma rozpoznanych sektorów — uruchom skan ponownie.
          </p>
        </div>
      ) : (
        <>
          <Wybor spolki={zSektorem} wybrana={String(spolka?.Ticker ?? "")} />

          {spolka && (
            <>
              <p className="drobne">
                Sektor: <b>{sektor}</b> — {rowiesnicy.length}{" "}
                {rowiesnicy.length === 1 ? "spółka" : "spółek"} w tej migawce,
                razem z {String(spolka.Ticker)}.
              </p>

              {rowiesnicy.length < MIN_SPOLEK_W_SEKTORZE && (
                <p className="komunikat-blad">
                  W tym sektorze są tylko {rowiesnicy.length}{" "}
                  {rowiesnicy.length === 1 ? "spółka" : "spółki"} w tej migawce.
                  Mediana z tylu pozycji to praktycznie jedna z nich, a wygląda
                  jak charakterystyka całej branży — traktuj poniższe oceny
                  z rezerwą.
                </p>
              )}

              <div className="card" style={{ marginTop: 12 }}>
                <div className="scroll">
                  <table className="tab-vs-sektor">
                    <thead>
                      <tr>
                        <th>Wskaźnik</th>
                        <th className="r">{String(spolka.Ticker)}</th>
                        <th className="r">Mediana sektora</th>
                        <th className="r">Różnica</th>
                        <th>Ocena</th>
                      </tr>
                    </thead>
                    <tbody>
                      {porownanie.map((p) => (
                        <tr key={p.kolumna}>
                          <td className="t">
                            {p.kolumna}
                            <small>
                              {p.kierunek === "wyzej"
                                ? "wyżej = lepiej"
                                : "niżej = lepiej"}
                            </small>
                          </td>
                          <td className="r n">{fmt(p.wartosc)}</td>
                          <td className="r n">{fmt(p.mediana)}</td>
                          <td className="r n">
                            {p.roznica === null ? (
                              <span className="brak">—</span>
                            ) : (
                              `${p.roznica > 0 ? "+" : ""}${p.roznica.toFixed(1)}%`
                            )}
                          </td>
                          <td>
                            <span className={OCENY[p.ocena].klasa}>
                              {OCENY[p.ocena].tekst}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <p className="drobne">
                „Podobnie do sektora” znaczy różnicę mniejszą niż 5%. Bez tego
                progu spółka odstająca o pół procenta dostawałaby ocenę lepiej
                albo gorzej, sugerując różnicę tam, gdzie przy medianie z
                kilkunastu spółek jest już tylko szum.
              </p>

              <div className="cardhead" style={{ padding: "18px 0 4px" }}>
                <h2 style={{ fontSize: "1.05rem" }}>
                  Wszystkie spółki w sektorze „{sektor}”
                </h2>
                <em>posortowane wg Buy Score</em>
              </div>

              <div className="card" style={{ marginTop: 12 }}>
                <div className="scroll">
                  <table className="tab-sektor-lista">
                    <thead>
                      <tr>
                        <th>Spółka</th>
                        <th>Rynek</th>
                        <th className="r">Cena</th>
                        <th className="r">C/Z</th>
                        <th className="r">ROE</th>
                        <th className="r">Marża netto</th>
                        <th className="r">Stopa dyw.</th>
                        <th className="r">Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {posortowani.map((r) => {
                        const t = String(r.Ticker);
                        return (
                          <tr
                            key={t}
                            className={
                              t === String(spolka.Ticker) ? "wiersz-wybrany" : undefined
                            }
                          >
                            <td className="t">
                              <Link
                                className="ticker-link"
                                href={`/sektor?spolka=${encodeURIComponent(t)}`}
                              >
                                {t}
                                <small>{String(r.Nazwa ?? "")}</small>
                              </Link>
                            </td>
                            <td className="drobna-kom">{String(r.Rynek ?? "")}</td>
                            <td className="r n">{fmt(liczba(r.Cena))}</td>
                            <td className="r n">{fmt(liczba(r["C/Z (P/E)"]), 1)}</td>
                            <td className="r n">{fmt(liczba(r["ROE (%)"]), 1)}</td>
                            <td className="r n">{fmt(liczba(r["Marża netto (%)"]), 1)}</td>
                            <td className="r n">{fmt(liczba(r["Stopa Dyw. (%)"]), 2)}</td>
                            <td className="r n">{fmt(liczba(r["Buy Score"]), 0)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </>
      )}

      <footer>
        Mediany liczone są z TEJ migawki, więc zmieniają się po każdym skanie —
        spółka może „poprawić się względem sektora”, nie zmieniając się ani
        trochę, jeśli pogorszy się reszta branży. Sektor pochodzi z danych Yahoo
        i bywa zgrubny: spółki z pogranicza branż trafiają czasem nie tam, gdzie
        by się ich szukało.
      </footer>
    </main>
  );
}
