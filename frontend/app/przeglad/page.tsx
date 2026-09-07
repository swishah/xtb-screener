import Link from "next/link";
import Pasek from "../Pasek";
import { daty, migawka, migawkaBezpieczna } from "@/lib/dane";
import type { Instrument } from "@/lib/filtry";
import {
  heatmapa,
  histogramRSI,
  najwiekszeRuchy,
  szerokoscRynku,
  wiarygodna,
  type WierszHeatmapy,
} from "@/lib/przeglad";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

function proc(w: number | null, cyfry = 0): string {
  if (w === null) return "brak danych";
  return `${w.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  })}%`;
}

function lb(w: number | null, cyfry = 1): string {
  if (w === null) return "—";
  return w.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  });
}

/**
 * Podkład komórki: im wyżej w skali, tym mocniejszy kolor.
 *
 * Podkłady robimy w `rgba`, nie w `hex` — ten sam kolor musi działać na
 * jasnym i ciemnym motywie, a półprzezroczysty dopasowuje się do tła sam.
 */
function tlo(wartosc: number | null, min: number, maks: number, dobre: "gora" | "dol") {
  if (wartosc === null || maks <= min) return undefined;
  const udzial = (wartosc - min) / (maks - min);
  const sila = (dobre === "gora" ? udzial : 1 - udzial) * 0.28;
  return { background: `rgba(20, 128, 74, ${sila.toFixed(3)})` };
}

function Heatmapa({
  wiersze,
  tytul,
  opis,
}: {
  wiersze: WierszHeatmapy[];
  tytul: string;
  opis: string;
}) {
  if (wiersze.length === 0) {
    return (
      <div className="card" style={{ marginTop: 12, padding: "14px 18px" }}>
        <h3 className="naglowek-sekcji">{tytul}</h3>
        <p className="pusto">Brak danych do pokazania w tej migawce.</p>
      </div>
    );
  }

  const score = wiersze.map((w) => w.sredniScore).filter((w): w is number => w !== null);
  const ath = wiersze.map((w) => w.sredniOdATH).filter((w): w is number => w !== null);
  const minS = Math.min(...score);
  const maksS = Math.max(...score);
  const minA = Math.min(...ath);
  const maksA = Math.max(...ath);

  return (
    <div className="card" style={{ marginTop: 12, padding: "14px 18px 6px" }}>
      <h3 className="naglowek-sekcji">{tytul}</h3>
      <p className="drobne" style={{ marginTop: 0 }}>
        {opis}
      </p>
      <div className="scroll">
        <table className="tab-heatmapa">
          <thead>
            <tr>
              <th>Grupa</th>
              <th className="r">Śr. Buy Score</th>
              <th className="r">Śr. od ATH</th>
              <th className="r">Spółek</th>
            </tr>
          </thead>
          <tbody>
            {wiersze.map((w) => (
              <tr key={w.grupa}>
                <td className="t">{w.grupa}</td>
                <td className="r n" style={tlo(w.sredniScore, minS, maksS, "gora")}>
                  {lb(w.sredniScore)}
                </td>
                <td className="r n" style={tlo(w.sredniOdATH, minA, maksA, "gora")}>
                  {w.sredniOdATH === null ? "—" : `${lb(w.sredniOdATH)}%`}
                </td>
                <td className="r n">{w.ile}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default async function Przeglad() {
  await wymagajZalogowania();

  const { instrumenty, data, tryb, blad } = await migawkaBezpieczna();
  const szer = szerokoscRynku(instrumenty);
  const rynki = heatmapa(instrumenty, "Rynek");
  const sektory = heatmapa(instrumenty, "Sektor");
  const hist = histogramRSI(instrumenty);
  const najwyzszySlupek = Math.max(1, ...hist.map((s) => s.ile));

  // Poprzednia migawka tylko po to, żeby policzyć ruchy dzień do dnia.
  // Gdy jest jedna, sekcja mówi wprost, czego brakuje.
  const dostepne = await daty().catch(() => [] as string[]);
  let poprzednia: Instrument[] = [];
  let dataPoprzedniej = "";
  if (dostepne.length >= 2) {
    try {
      const m = await migawka(dostepne[1]);
      poprzednia = m.instrumenty;
      dataPoprzedniej = m.data;
    } catch {
      poprzednia = [];
    }
  }
  const ruchy = najwiekszeRuchy(instrumenty, poprzednia);

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
        <h2 style={{ fontSize: "1.15rem" }}>Globalny przegląd</h2>
        <em>migawka z {data}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Kondycja całego rynku, niezależnie od strategii. Wysoki odsetek spółek
        nad średnią 200-sesyjną to szeroka hossa — ciągnie wiele spółek naraz.
        Niski odsetek przy rosnących indeksach znaczy, że wzrost napędza
        garstka największych spółek, a reszta rynku stoi albo spada.
      </p>

      <div className="stats">
        {(
          [
            [szer.nadSMA200, "spółek > SMA200", true],
            [szer.nadSMA50, "spółek > SMA50", true],
            [szer.sredniRSI, "średnie RSI", false],
            [szer.buyScore5, "z Buy Score ≥ 5", true],
          ] as const
        ).map(([m, etykieta, procentowa]) => {
          const ok = wiarygodna(m, szer.spolek);
          return (
            <div key={etykieta}>
              <b className={ok ? undefined : "brak"}>
                {ok
                  ? procentowa
                    ? proc(m.wartosc)
                    : lb(m.wartosc)
                  : "brak danych"}
              </b>
              <span>{etykieta}</span>
              {!ok && (
                <em className="podstawa">
                  {m.podstawa} z {szer.spolek} spółek
                </em>
              )}
            </div>
          );
        })}
      </div>
      <p className="drobne">
        Liczone na {szer.spolek.toLocaleString("pl-PL")} spółkach — bez ETF-ów,
        bo koszyk powtarzałby to samo drugi raz, tyle że z wagą indeksu.
        Średnie RSI powyżej 50 to generalnie trend wzrostowy, poniżej —
        spadkowy.
      </p>
      {(!wiarygodna(szer.nadSMA200, szer.spolek) ||
        !wiarygodna(szer.nadSMA50, szer.spolek)) && (
        <p className="komunikat-blad">
          <b>Ta migawka nie ma średnich kroczących dla większości spółek</b>
          {" ("}
          {szer.nadSMA200.podstawa} z {szer.spolek} ma SMA200
          {"). "}
          Odsetek policzony z takiej resztki wyglądałby jak obraz całego rynku,
          a byłby obrazem kilku spółek — dlatego pokazujemy „brak danych”
          zamiast liczby. Pozostałe sekcje (RSI, heatmapy, ruchy) liczą się
          normalnie.
        </p>
      )}

      <div className="dwie-kolumny">
        <Heatmapa
          wiersze={rynki}
          tytul="Heatmapa rynków"
          opis="Który kraj ma teraz najwyższy średni Buy Score i największy spadek od szczytu — szybki obraz, który rynek jest przeceniony, a który drogi."
        />
        <Heatmapa
          wiersze={sektory}
          tytul="Heatmapa sektorów"
          opis="To samo w podziale na sektor gospodarki zamiast kraju notowania. Grupy poniżej trzech spółek są pominięte — średnia z dwóch nie mówi nic o sektorze."
        />
      </div>

      <div className="card" style={{ marginTop: 12, padding: "14px 18px" }}>
        <h3 className="naglowek-sekcji">Rozkład RSI</h3>
        <p className="drobne" style={{ marginTop: 0 }}>
          Dużo spółek po lewej (RSI poniżej 30) = rynek generalnie wyprzedany,
          dużo po prawej (powyżej 70) = wykupiony.
        </p>
        <div className="histogram" role="img" aria-label="Histogram RSI całego rynku">
          {hist.map((s) => (
            <div key={s.od} className="hist-slupek">
              <span className="hist-liczba">{s.ile || ""}</span>
              <div
                className={s.od < 30 ? "hist-pasek wyprzedane" : s.od >= 70 ? "hist-pasek wykupione" : "hist-pasek"}
                style={{ height: `${(s.ile / najwyzszySlupek) * 100}%` }}
              />
              <span className="hist-etykieta">{s.od}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.05rem" }}>Największe ruchy</h2>
        <em>
          {dataPoprzedniej
            ? `${dataPoprzedniej} → ${data}`
            : "potrzebna druga migawka"}
        </em>
      </div>

      {ruchy.wzrosty.length === 0 ? (
        <div className="card" style={{ marginTop: 12, padding: "14px 18px" }}>
          <p className="pusto">
            Ruchy pojawią się, gdy w bazie będą dwie migawki do porównania.
          </p>
        </div>
      ) : (
        <>
          <div className="dwie-kolumny">
            {(
              [
                ["Największe wzrosty", ruchy.wzrosty],
                ["Największe spadki", ruchy.spadki],
              ] as const
            ).map(([tytul, lista]) => (
              <div
                key={tytul}
                className="card"
                style={{ marginTop: 12, padding: "14px 18px 6px" }}
              >
                <h3 className="naglowek-sekcji">{tytul}</h3>
                <div className="scroll">
                  <table className="tab-ruchy">
                    <thead>
                      <tr>
                        <th>Spółka</th>
                        <th>Rynek</th>
                        <th className="r">Cena</th>
                        <th className="r">Zmiana</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lista.map((r) => (
                        <tr key={r.ticker}>
                          <td className="t">
                            <Link
                              className="ticker-link"
                              href={`/spolka/${encodeURIComponent(r.ticker)}`}
                            >
                              {r.ticker}
                              <small>{r.nazwa}</small>
                            </Link>
                          </td>
                          <td className="drobna-kom">{r.rynek}</td>
                          <td className="r n">{lb(r.cena, 2)}</td>
                          <td className={r.zmiana < 0 ? "r n down" : "r n up"}>
                            {r.zmiana > 0 ? "+" : ""}
                            {lb(r.zmiana, 2)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
          <p className="drobne">
            Skan chodzi od poniedziałku do piątku, więc „ruch” to zmiana między
            dwoma ostatnimi skanami — po weekendzie albo święcie obejmuje więcej
            niż jedną sesję. Stąd obie daty podane wyżej wprost.
          </p>
        </>
      )}

      <footer>
        Wszystkie liczby pochodzą z migawki {data} i zmieniają się po każdym
        skanie. Szerokość rynku i heatmapy liczone są wyłącznie na spółkach;
        największe ruchy obejmują też ETF-y, bo tam pytanie brzmi „co się
        ruszyło”, a nie „jak stoi rynek”.
      </footer>
    </main>
  );
}
