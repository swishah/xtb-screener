import Link from "next/link";
import { Suspense } from "react";
import Pasek from "../Pasek";
import PanelSpolki from "../PanelSpolki";
import WykresPelny from "../spolka/WykresPelny";
import Suwaki from "./Suwaki";
import { migawkaBezpieczna } from "@/lib/dane";
import { newsySpolki } from "@/lib/newsy";
import { anomalieCZ } from "@/lib/sektor";
import { symbolTradingView } from "@/lib/tradingview";
import { liczba, zieloneFlagi } from "@/lib/filtry";

export const dynamic = "force-dynamic";

const LIMIT = 120;

function num(wejscie: string | undefined, domyslna: number): number {
  if (wejscie === undefined) return domyslna;
  const n = Number(wejscie);
  return Number.isFinite(n) ? n : domyslna;
}

export default async function TanieVsSektor({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };

  const minSpolek = num(jeden("minSpolek"), 5);
  const maksRoznica = num(jeden("maksRoznica"), -20);

  const { data, tryb, instrumenty, blad } = await migawkaBezpieczna();
  const wyniki = anomalieCZ(instrumenty, minSpolek, maksRoznica);
  const widoczne = wyniki.slice(0, LIMIT);

  const wybranyTicker = (jeden("wybrana") ?? "").toUpperCase();
  const wybrana = wybranyTicker
    ? instrumenty.find((i) => String(i.Ticker ?? "").toUpperCase() === wybranyTicker)
    : undefined;
  const newsy = wybrana
    ? await newsySpolki(String(wybrana.Ticker), String(wybrana.Nazwa ?? ""))
    : [];

  const wykresTicker = (jeden("wykres") ?? "").toUpperCase();
  const doWykresu = wykresTicker
    ? instrumenty.find((i) => String(i.Ticker ?? "").toUpperCase() === wykresTicker)
    : undefined;

  function adres(zmiany: Record<string, string | null>): string {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(q)) {
      const w = Array.isArray(v) ? v[0] : v;
      if (w) p.set(k, w);
    }
    for (const [k, v] of Object.entries(zmiany)) {
      if (v === null) p.delete(k);
      else p.set(k, v);
    }
    const s = p.toString();
    return s ? `/tanie?${s}` : "/tanie";
  }

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
        <h2 style={{ fontSize: "1.15rem" }}>Tanie vs sektor</h2>
        <em>migawka z {data}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Spółki, których C/Z jest wyraźnie niższe niż mediana ich WŁASNEGO sektora —
        czyli tanie na tle bezpośredniej konkurencji, nie całego rynku. Kolumna
        „mocne strony” ma pomóc odróżnić okazję od pułapki wartościowej: niskie
        C/Z bywa też skutkiem tego, że rynek słusznie wycenia problemy.
      </p>

      <Suspense fallback={<div className="filtry">Wczytuję ustawienia…</div>}>
        <Suwaki
          minSpolek={minSpolek}
          maksRoznica={maksRoznica}
          znalezionych={wyniki.length}
        />
      </Suspense>

      <div className={wybrana ? "uklad-z-panelem" : undefined}>
        <div className="card" style={{ marginTop: 12 }}>
          {widoczne.length === 0 ? (
            <p style={{ padding: 16, color: "var(--muted)" }}>
              Żadna spółka nie spełnia tych kryteriów. Poluzuj ustawienia powyżej —
              najczęściej pomaga zmniejszenie wymaganej różnicy od mediany.
            </p>
          ) : (
            <div className="scroll">
              <table className="tab-tanie">
                <thead>
                  <tr>
                    <th>Spółka</th>
                    <th className="kol-wykres">Wykres</th>
                    <th className="r">C/Z</th>
                    <th className="r">Mediana sektora</th>
                    <th className="r">Różnica</th>
                    <th>Sektor</th>
                    <th className="r">Flagi</th>
                    <th>Mocne strony</th>
                  </tr>
                </thead>
                <tbody>
                  {widoczne.map((w) => {
                    const t = String(w.spolka.Ticker);
                    const flagi = liczba(w.spolka["Liczba flag"]);
                    const mocne = zieloneFlagi(w.spolka);
                    return (
                      <tr key={t} className={t === wybranyTicker ? "wiersz-wybrany" : undefined}>
                        <td className="t">
                          <Link href={adres({ wybrana: t })} className="ticker-link">
                            {t}
                            <small>{String(w.spolka.Nazwa ?? "")}</small>
                          </Link>
                        </td>
                        <td className="kol-wykres">
                          <Link
                            href={adres({ wykres: t })}
                            className="btn-wykres"
                            aria-label={`Wykres ${t}`}
                            title="Pokaż wykres na pełnym ekranie"
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                              <path d="M3 3v18h18" />
                              <path d="M7 14l4-5 3 3 5-7" />
                            </svg>
                          </Link>
                        </td>
                        <td className="r n" data-l="C/Z">
                          {w.cz.toLocaleString("pl-PL", { maximumFractionDigits: 2 })}
                        </td>
                        <td className="r n brak" data-l="mediana">
                          {w.medianaSektora.toLocaleString("pl-PL", {
                            maximumFractionDigits: 2,
                          })}
                        </td>
                        <td className="r n down" data-l="różnica">
                          {w.roznicaProc.toLocaleString("pl-PL", {
                            maximumFractionDigits: 1,
                          })}
                          %
                        </td>
                        <td className="sektor-kom">
                          {String(w.spolka.Sektor ?? "")}
                          <small>{w.spolekWSektorze} spółek</small>
                        </td>
                        <td className="r">
                          <span className={`pill${flagi === 0 ? " good" : ""}`}>
                            {flagi === null ? "?" : flagi}
                          </span>
                        </td>
                        <td className="mocne-kom">
                          {mocne.length === 0 ? (
                            <span className="brak">brak</span>
                          ) : (
                            <span className="mocne-licznik" title={mocne.join(" · ")}>
                              {mocne.length} ·{" "}
                              <span className="brak">{mocne[0]}</span>
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {wybrana && (
          <PanelSpolki
            spolka={wybrana}
            wszystkie={instrumenty}
            newsy={newsy}
            adresZamkniecia={adres({ wybrana: null })}
          />
        )}
      </div>

      <footer>
        {wyniki.length > LIMIT && (
          <>
            Pokazane pierwsze {LIMIT} z {wyniki.length.toLocaleString("pl-PL")} —
            zaostrz kryteria, żeby zobaczyć resztę.{" "}
          </>
        )}
        Spółki na stracie (C/Z ujemne) są pomijane: przy ujemnym zysku wskaźnik
        przestaje cokolwiek mierzyć. Sektory poniżej progu liczebności też —
        mediana z kilku spółek to nie opis branży, tylko przypadek.
      </footer>

      {doWykresu && (
        <WykresPelny
          ticker={String(doWykresu.Ticker)}
          nazwa={String(doWykresu.Nazwa ?? "")}
          symbol={symbolTradingView(String(doWykresu.Ticker ?? ""))}
          adresZamkniecia={adres({ wykres: null })}
        />
      )}
    </main>
  );
}
