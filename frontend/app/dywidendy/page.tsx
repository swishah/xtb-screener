import Link from "next/link";
import { Suspense } from "react";
import Pasek from "../Pasek";
import PanelSpolki from "../PanelSpolki";
import WykresPelny from "../spolka/WykresPelny";
import Suwaki from "./Suwaki";
import { migawkaBezpieczna } from "@/lib/dane";
import { newsySpolki } from "@/lib/newsy";
import { symbolTradingView } from "@/lib/tradingview";
import { liczba } from "@/lib/filtry";
import {
  DYWIDENDY_DOMYSLNE,
  KOL_SCORE,
  filtrujDywidendy,
  nowaMetodologia,
  przedSezonem,
  type FiltryDywidend,
} from "@/lib/dywidendy";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

const LIMIT = 120;

/**
 * Liczba z adresu URL; przy śmieciach wraca wartość domyślna.
 *
 * Pusty parametr (`?maksZmiana1Y=`) MUSI być traktowany jak jego brak.
 * `Number("")` daje w JavaScripcie 0, a nie NaN, więc pierwsza wersja
 * przepuszczała pustkę jako twarde zero — zmierzone: `?maksZmiana1Y=`
 * dawało 35 wyników zamiast 51 z wartości domyślnej. Formularze i ręcznie
 * czyszczone adresy produkują takie parametry same z siebie.
 */
function num(wejscie: string | undefined, domyslna: number): number {
  if (wejscie === undefined || wejscie.trim() === "") return domyslna;
  const n = Number(wejscie);
  return Number.isFinite(n) ? n : domyslna;
}

function fmt(w: unknown, cyfry = 2, sufiks = ""): React.ReactNode {
  const n = liczba(w);
  if (n === null) return <span className="brak">BRAK</span>;
  return `${n.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  })}${sufiks}`;
}

export default async function Dywidendy({
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

  const filtry: FiltryDywidend = {
    minStopa: num(jeden("minStopa"), DYWIDENDY_DOMYSLNE.minStopa),
    maksZmiana1Y: num(jeden("maksZmiana1Y"), DYWIDENDY_DOMYSLNE.maksZmiana1Y),
    maksPayout: num(jeden("maksPayout"), DYWIDENDY_DOMYSLNE.maksPayout),
    tylkoPrzedSezonem: jeden("przedSezonem") === "1",
  };

  const { data, tryb, instrumenty, blad } = await migawkaBezpieczna();
  const wyniki = filtrujDywidendy(instrumenty, filtry);
  const widoczne = wyniki.slice(0, LIMIT);
  const swieze = nowaMetodologia(instrumenty);

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
    return s ? `/dywidendy?${s}` : "/dywidendy";
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
        <h2 style={{ fontSize: "1.15rem" }}>Dywidendy</h2>
        <em>migawka z {data}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Spółki z wysoką stopą dywidendy, których cena jeszcze się nie ruszyła —
        plus wskaźniki bezpieczeństwa wypłaty (payout ratio, wzrost przychodów,
        marża), żeby odróżnić okazję od pułapki dywidendowej, czyli wysokiej
        stopy wynikającej z tego, że kurs spadł z powodu kłopotów firmy.
        Kolumny „Zeszły rok” i „Ten rok” mówią, czy tegoroczna wypłata jest
        jeszcze przed spółką.
      </p>

      {!swieze && (
        <p className="komunikat-blad">
          Ta migawka pochodzi sprzed poprawki liczenia stopy dywidendy
          (2026-09-06). Stopa jest w niej liczona z sumy wypłat za poprzedni
          rok kalendarzowy, więc <b>wypłaty jednorazowe wyglądają jak coroczne,
          a obniżki nie są jeszcze widoczne</b>. Po najbliższym skanie liczby
          się poprawią same.
        </p>
      )}

      <Suspense fallback={<div className="filtry">Wczytuję ustawienia…</div>}>
        <Suwaki filtry={filtry} znalezionych={wyniki.length} />
      </Suspense>

      <div className={wybrana ? "uklad-z-panelem" : undefined}>
        <div className="card" style={{ marginTop: 12 }}>
          {widoczne.length === 0 ? (
            <p style={{ padding: 16, color: "var(--muted)" }}>
              Żadna spółka nie spełnia tych kryteriów. Najczęściej pomaga
              obniżenie minimalnej stopy dywidendy albo podniesienie limitu
              zmiany ceny.
              {filtry.tylkoPrzedSezonem && (
                <>
                  {" "}
                  Masz też włączone „tylko przed tegoroczną wypłatą” — im bliżej
                  końca roku, tym mniej takich spółek, bo większość zdążyła już
                  zapłacić.
                </>
              )}
            </p>
          ) : (
            <div className="scroll">
              <table className="tab-dywidendy">
                <thead>
                  <tr>
                    <th>Spółka</th>
                    <th className="kol-wykres">Wykres</th>
                    <th className="r">Cena</th>
                    <th className="r">Stopa dyw.</th>
                    <th className="r">Payout</th>
                    <th className="r">Zmiana 1R</th>
                    <th className="r">Lat z dyw.</th>
                    <th className="r">Zeszły rok</th>
                    <th className="r">Ten rok</th>
                    <th>Najbliższa wypłata</th>
                    <th className="r">Wynik</th>
                  </tr>
                </thead>
                <tbody>
                  {widoczne.map((s) => {
                    const t = String(s.Ticker);
                    const zmiana = liczba(s["Zmiana ceny (1Y%)"]);
                    const przyszla = String(s["Przyszła dywidenda"] ?? "BRAK");
                    return (
                      <tr
                        key={t}
                        className={t === wybranyTicker ? "wiersz-wybrany" : undefined}
                      >
                        <td className="t">
                          <Link href={adres({ wybrana: t })} className="ticker-link">
                            {t}
                            <small>{String(s.Nazwa ?? "")}</small>
                          </Link>
                        </td>
                        <td className="kol-wykres">
                          <Link href={adres({ wykres: t })} className="btn-wykres">
                            wykres
                          </Link>
                        </td>
                        <td className="r n">{fmt(s.Cena)}</td>
                        <td className="r n">{fmt(s["Stopa Dyw. (%)"], 2, "%")}</td>
                        <td className="r n">{fmt(s["Payout ratio (%)"], 0, "%")}</td>
                        <td className={zmiana !== null && zmiana < 0 ? "r n down" : "r n"}>
                          {fmt(s["Zmiana ceny (1Y%)"], 1, "%")}
                        </td>
                        <td className="r n">{fmt(s["Lata z dywidendą (3Y)"], 0)}</td>
                        <td className="r">
                          {String(s["Dyw. w poprzednim roku"] ?? "—")}
                        </td>
                        <td className="r">
                          {przedSezonem(s) ? (
                            <b className="przed-sezonem">Nie</b>
                          ) : (
                            String(s["Dyw. w tym roku"] ?? "—")
                          )}
                        </td>
                        <td>
                          {przyszla === "BRAK" ? (
                            <span className="brak">BRAK</span>
                          ) : (
                            przyszla
                          )}
                        </td>
                        <td className="r n">{fmt(s[KOL_SCORE], 0)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {wyniki.length > LIMIT && (
            <p className="drobne" style={{ padding: "0 16px 12px" }}>
              Pokazujemy {LIMIT} najlepszych z {wyniki.length}. Zawęź kryteria,
              żeby zobaczyć inne.
            </p>
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

      {doWykresu && (
        <WykresPelny
          symbol={symbolTradingView(String(doWykresu.Ticker))}
          ticker={String(doWykresu.Ticker)}
          nazwa={String(doWykresu.Nazwa ?? "")}
          adresZamkniecia={adres({ wykres: null })}
        />
      )}

      <footer>
        Stopa dywidendy pochodzi z Yahoo (pole <code>dividendYield</code>), więc
        uwzględnia obniżki i pomija wypłaty jednorazowe — spółki z dywidendą
        specjalną są z tego modułu wykluczone, bo nie tworzą sezonu, na który
        dałoby się czekać. „Najbliższa wypłata” bywa pusta poza USA: Yahoo
        podaje tę datę dla około 58% płacących spółek amerykańskich i 11%
        pozostałych. Puste pole znaczy „nie wiadomo kiedy”, a nie „nie zapłaci”.
      </footer>
    </main>
  );
}
