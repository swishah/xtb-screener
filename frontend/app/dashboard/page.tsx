import Link from "next/link";
import Pasek from "../Pasek";
import { daty, migawka, migawkaBezpieczna } from "@/lib/dane";
import { liczba, type Instrument } from "@/lib/filtry";
import {
  heatmapa,
  histogramRSI,
  najwiekszeRuchy,
  szerokoscRynku,
  tylkoSpolki,
  wiarygodna,
} from "@/lib/przeglad";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

const KAFELKOW = 6;

function lb(w: number | null, cyfry = 1, sufiks = ""): string {
  if (w === null) return "—";
  return `${w.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  })}${sufiks}`;
}

/** Pasek postępu 0–100%. Bez JS: szerokość liczona po stronie serwera. */
function Pasekek({ pct, etykieta }: { pct: number | null; etykieta: string }) {
  return (
    <div className="pasek-wiersz">
      <span className="pasek-etykieta">{etykieta}</span>
      <div className="pasek-tlo">
        <div
          className="pasek-wypelnienie"
          style={{ width: `${Math.max(0, Math.min(100, pct ?? 0))}%` }}
        />
      </div>
      <span className="pasek-wartosc n">{pct === null ? "—" : `${Math.round(pct)}%`}</span>
    </div>
  );
}

export default async function Dashboard() {
  await wymagajZalogowania();

  const { instrumenty, data, tryb, blad } = await migawkaBezpieczna();
  const spolki = tylkoSpolki(instrumenty);
  const szer = szerokoscRynku(instrumenty);
  const rynki = heatmapa(instrumenty, "Rynek");
  const hist = histogramRSI(instrumenty);
  const najwyzszy = Math.max(1, ...hist.map((s) => s.ile));

  const dostepne = await daty().catch(() => [] as string[]);
  let poprzednie: Instrument[] = [];
  if (dostepne.length >= 2) {
    try {
      poprzednie = (await migawka(dostepne[1])).instrumenty;
    } catch {
      poprzednie = [];
    }
  }
  const ruchy = najwiekszeRuchy(instrumenty, poprzednie, KAFELKOW);

  const topKupno = [...spolki]
    .filter((s) => liczba(s["Buy Score"]) !== null)
    .sort((a, b) => (liczba(b["Buy Score"]) ?? 0) - (liczba(a["Buy Score"]) ?? 0))
    .slice(0, KAFELKOW);

  const najwiecejFlag = [...spolki]
    .filter((s) => (liczba(s["Liczba flag"]) ?? 0) > 0)
    .sort((a, b) => (liczba(b["Liczba flag"]) ?? 0) - (liczba(a["Liczba flag"]) ?? 0))
    .slice(0, KAFELKOW);

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
        <h2 style={{ fontSize: "1.15rem" }}>Dashboard</h2>
        <em>migawka z {data}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Jeden ekran z tym, co dzieje się na rynku dziś: szerokość, ruchy,
        najwyżej oceniane spółki i te z największą liczbą ostrzeżeń. Wszystko
        z najnowszej migawki — po szczegóły i heatmapy sektorów zajrzyj do{" "}
        <Link className="link" href="/przeglad">
          Globalnego przeglądu
        </Link>
        .
      </p>

      <div className="kafelki-dashboard">
        <section className="card kafel">
          <h3 className="naglowek-sekcji">Szerokość rynku</h3>
          {wiarygodna(szer.nadSMA200, szer.spolek) ? (
            <>
              <Pasekek pct={szer.nadSMA200.wartosc} etykieta="nad SMA200" />
              <Pasekek pct={szer.nadSMA50.wartosc} etykieta="nad SMA50" />
            </>
          ) : (
            <p className="drobne" style={{ marginTop: 0 }}>
              Ta migawka nie ma średnich kroczących dla większości spółek
              ({szer.nadSMA200.podstawa} z {szer.spolek}), więc odsetek
              „nad średnią” byłby obrazem kilku spółek, nie rynku.
            </p>
          )}
          <Pasekek pct={szer.buyScore5.wartosc} etykieta="Buy Score ≥ 5" />
          <p className="drobne">
            Średnie RSI całego rynku:{" "}
            <b>{lb(szer.sredniRSI.wartosc)}</b> — powyżej 50 to generalnie trend
            wzrostowy.
          </p>
        </section>

        <section className="card kafel">
          <h3 className="naglowek-sekcji">Rozkład RSI</h3>
          <div className="histogram maly" role="img" aria-label="Histogram RSI">
            {hist.map((s) => (
              <div key={s.od} className="hist-slupek">
                <div
                  className={
                    s.od < 30
                      ? "hist-pasek wyprzedane"
                      : s.od >= 70
                        ? "hist-pasek wykupione"
                        : "hist-pasek"
                  }
                  style={{ height: `${(s.ile / najwyzszy) * 100}%` }}
                />
                <span className="hist-etykieta">{s.od}</span>
              </div>
            ))}
          </div>
          <p className="drobne">
            Zielone słupki po lewej = spółki wyprzedane (RSI &lt; 30), czerwone
            po prawej = wykupione.
          </p>
        </section>

        <section className="card kafel">
          <h3 className="naglowek-sekcji">Rynki wg średniego Buy Score</h3>
          {rynki.slice(0, KAFELKOW).map((r) => (
            <Pasekek
              key={r.grupa}
              // Buy Score ma skalę 0–9, więc na pasek 0–100% przeliczamy go
              // wprost, zamiast normalizować do najlepszego rynku — inaczej
              // lider zawsze miałby pełny pasek, nawet przy słabym wyniku.
              pct={r.sredniScore === null ? null : (r.sredniScore / 9) * 100}
              etykieta={`${r.grupa} (${lb(r.sredniScore)})`}
            />
          ))}
        </section>

        <section className="card kafel">
          <h3 className="naglowek-sekcji">Najwyższy Buy Score</h3>
          <ul className="lista-kafel">
            {topKupno.map((s) => (
              <li key={String(s.Ticker)}>
                <Link
                  className="ticker-link"
                  href={`/spolka/${encodeURIComponent(String(s.Ticker))}`}
                >
                  {String(s.Ticker)}
                  <small>{String(s.Nazwa ?? "")}</small>
                </Link>
                <b className="n">{lb(liczba(s["Buy Score"]), 0)}</b>
              </li>
            ))}
          </ul>
        </section>

        <section className="card kafel">
          <h3 className="naglowek-sekcji">Najwięcej czerwonych flag</h3>
          {najwiecejFlag.length === 0 ? (
            <p className="pusto">Żadna spółka nie ma ostrzeżeń w tej migawce.</p>
          ) : (
            <ul className="lista-kafel">
              {najwiecejFlag.map((s) => (
                <li key={String(s.Ticker)}>
                  <Link
                    className="ticker-link"
                    href={`/spolka/${encodeURIComponent(String(s.Ticker))}`}
                  >
                    {String(s.Ticker)}
                    <small>{String(s.Nazwa ?? "")}</small>
                  </Link>
                  <b className="n down">{lb(liczba(s["Liczba flag"]), 0)}</b>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card kafel">
          <h3 className="naglowek-sekcji">Największe ruchy</h3>
          {ruchy.wzrosty.length === 0 ? (
            <p className="pusto">
              Ruchy pojawią się, gdy w bazie będą dwie migawki do porównania.
            </p>
          ) : (
            <ul className="lista-kafel">
              {[...ruchy.wzrosty.slice(0, 3), ...ruchy.spadki.slice(0, 3)].map((r) => (
                <li key={r.ticker}>
                  <Link
                    className="ticker-link"
                    href={`/spolka/${encodeURIComponent(r.ticker)}`}
                  >
                    {r.ticker}
                    <small>{r.nazwa}</small>
                  </Link>
                  <b className={r.zmiana < 0 ? "n down" : "n up"}>
                    {r.zmiana > 0 ? "+" : ""}
                    {lb(r.zmiana, 2, "%")}
                  </b>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <footer>
        Wszystkie liczby pochodzą z migawki {data} i zmieniają się po każdym
        skanie. <b>Nie ma tu wskaźnika nastrojów ani VIX-a</b> — w Streamlicie
        liczą się na żywo z sieci, a ten ekran ma się otwierać natychmiast
        i wyłącznie z danych, które już mamy. Szerokość rynku i heatmapa liczone
        są bez ETF-ów; ruchy obejmują wszystko.
      </footer>
    </main>
  );
}
