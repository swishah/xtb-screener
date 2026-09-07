import Link from "next/link";
import Pasek from "../Pasek";
import PanelSpolki from "../PanelSpolki";
import WykresPelny from "../spolka/WykresPelny";
import { migawkaBezpieczna } from "@/lib/dane";
import { liczba, type Instrument } from "@/lib/filtry";
import { newsySpolki } from "@/lib/newsy";
import { symbolTradingView } from "@/lib/tradingview";
import {
  dniDossier,
  dossierDnia,
  sladyKandydatow,
  tickeryZPlanem,
  type WpisDossier,
} from "@/lib/dossier";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

function lb(w: number | null | undefined, cyfry = 2): string {
  if (w === null || w === undefined || !Number.isFinite(w)) return "—";
  return w.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  });
}

function cyfryCeny(w: number | null): number {
  return w !== null && Math.abs(w) < 10 ? 3 : 2;
}

/**
 * Trzy interwały jednym rzutem oka.
 *
 * Strzałka zamiast słowa, bo w tabeli chodzi o ZGODNOŚĆ trzech interwałów,
 * a nie o każdy z osobna — trzy strzałki w górę widać natychmiast, trzech
 * słów „wzrostowy" trzeba się doczytać. Pełna nazwa siedzi w dymku.
 */
function Trendy({ d, w, m }: { d: string; w: string; m: string }) {
  const znak = (t: string) =>
    t === "wzrostowy" ? "↑" : t === "spadkowy" ? "↓" : t === "boczny" ? "→" : "·";
  const klasa = (t: string) =>
    t === "wzrostowy" ? "up" : t === "spadkowy" ? "down" : "brak";
  return (
    <span className="trendy" title={`1D ${d} / 1W ${w} / 1M ${m}`}>
      {([["1D", d], ["1W", w], ["1M", m]] as const).map(([e, t]) => (
        <span key={e} className={klasa(t)}>
          {znak(t)}
        </span>
      ))}
    </span>
  );
}

/** Pasek pokazujący, gdzie w rocznym zakresie stoi kurs. */
function Pozycja({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="brak">—</span>;
  const x = Math.max(0, Math.min(100, pct));
  return (
    <span className="miernik" title={`${lb(pct, 0)}% zakresu 52 tygodni`}>
      <span className="miernik-tor">
        <span className="miernik-wypelnienie" style={{ width: `${x}%` }} />
      </span>
      <span className="miernik-liczba">{lb(pct, 0)}%</span>
    </span>
  );
}

export default async function Dossier({
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

  const { data, tryb, instrumenty } = await migawkaBezpieczna();
  const dni = await dniDossier();

  const zadany = jeden("dzien");
  const dzien = zadany && dni.includes(zadany) ? zadany : dni[0];

  const [wpisy, slady, zPlanem] = await Promise.all([
    dzien ? dossierDnia(dzien) : Promise.resolve([] as WpisDossier[]),
    sladyKandydatow(),
    dzien ? tickeryZPlanem(dzien) : Promise.resolve(new Set<string>()),
  ]);

  const rynek = new Map<string, Instrument>(
    instrumenty.map((i) => [String(i.Ticker ?? "").toUpperCase(), i]),
  );

  const wybranyTicker = (jeden("wybrana") ?? "").toUpperCase();
  const wybrana = wybranyTicker ? rynek.get(wybranyTicker) : undefined;
  const newsy = wybrana
    ? await newsySpolki(String(wybrana.Ticker), String(wybrana.Nazwa ?? ""))
    : [];

  const wykresTicker = (jeden("wykres") ?? "").toUpperCase();
  const doWykresu = wykresTicker ? rynek.get(wykresTicker) : undefined;

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
    return s ? `/dossier?${s}` : "/dossier";
  }

  const wracajace = slady.filter((s) => s.dni > 1);

  return (
    <main className="wrap wrap-szeroki">
      <Pasek dataMigawki={data} tryb={tryb} />

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Dossier kandydatów</h2>
        <em>{dzien ? dzien : "jeszcze puste"}</em>
        <Link className="link" href="/plan">
          Plan dnia →
        </Link>
      </div>

      <p className="opis-strategii">
        Materiał, z którego powstają plany: po pięć spółek z czoła każdego
        rankingu, zebrane o 6:00 i policzone z dziesięciu lat notowań. Spółka
        wskazana przez kilka rankingów naraz jest widoczna i od strony wyceny,
        i od strony techniki — dlatego liczba źródeł decyduje o kolejności.
        Większość kandydatów nie staje się planem i to jest normalne; tutaj
        widać, co było brane pod uwagę.
      </p>

      {dni.length > 1 && (
        <div className="wybor">
          {dni.slice(0, 20).map((d) => (
            <Link
              key={d}
              href={adres({ dzien: d })}
              className={d === dzien ? "wybor-poz aktywna" : "wybor-poz"}
            >
              {d}
            </Link>
          ))}
        </div>
      )}

      <div className={wybrana ? "uklad-z-panelem" : undefined}>
        <div>
          {dni.length === 0 ? (
            <div className="card" style={{ marginTop: 14, padding: "16px 18px" }}>
              <h3 className="naglowek-sekcji">Dossier jeszcze nie powstało</h3>
              <p className="pusto">
                Buduje się samo o 6:00 w dni robocze przez GitHub Actions. Da
                się je też wywołać ręcznie: Actions → „Dossier kandydatow" →
                Run workflow.
              </p>
            </div>
          ) : (
            <>
              <div className="cardhead" style={{ padding: "16px 0 4px" }}>
                <h2 style={{ fontSize: "1.05rem" }}>Kandydaci z {dzien}</h2>
                <em>
                  {wpisy.length}, z tego {zPlanem.size} z planem
                </em>
              </div>
              <div className="card" style={{ marginTop: 12 }}>
                <div className="scroll">
                  <table className="tab-dossier">
                    <thead>
                      <tr>
                        <th>Spółka</th>
                        <th className="kol-wykres">Wykres</th>
                        <th className="r">Źródeł</th>
                        <th>Rankingi</th>
                        <th className="r">Kurs</th>
                        <th className="r">ATR</th>
                        <th>Trendy</th>
                        <th className="r">W zakresie 52t</th>
                        <th className="r">Poziomów</th>
                        <th>Plan</th>
                      </tr>
                    </thead>
                    <tbody>
                      {wpisy.map((w) => {
                        const c = cyfryCeny(w.kurs);
                        const maPlan = zPlanem.has(w.ticker.toUpperCase());
                        return (
                          <tr
                            key={w.ticker}
                            className={
                              w.ticker.toUpperCase() === wybranyTicker
                                ? "wiersz-wybrany"
                                : undefined
                            }
                          >
                            <td className="t">
                              <Link
                                href={adres({ wybrana: w.ticker })}
                                className="ticker-link"
                              >
                                {w.ticker}
                                <small>{w.nazwa}</small>
                              </Link>
                            </td>
                            <td className="kol-wykres">
                              <Link
                                href={adres({ wykres: w.ticker })}
                                className="btn-wykres"
                              >
                                wykres
                              </Link>
                            </td>
                            <td className="r n" data-l="Źródeł">
                              <b>{w.liczbaZrodel}</b>
                            </td>
                            <td data-l="Rankingi" className="kol-rankingi">
                              {w.zrodla.map((z) => z.ranking).join(", ")}
                            </td>
                            <td className="r n" data-l="Kurs">
                              {lb(w.kurs, c)}{" "}
                              <span className="brak">{w.waluta}</span>
                            </td>
                            <td className="r n" data-l="ATR">
                              {lb(w.atrPct, 2)}%
                            </td>
                            <td data-l="Trendy">
                              <Trendy d={w.trend1d} w={w.trend1w} m={w.trend1m} />
                            </td>
                            <td className="r" data-l="W zakresie 52t">
                              <Pozycja pct={w.pozycjaPct} />
                            </td>
                            <td className="r n" data-l="Poziomów">
                              {w.poziomy.length}
                            </td>
                            <td data-l="Plan">
                              {maPlan ? (
                                <Link href="/plan" className="pill good">
                                  jest
                                </Link>
                              ) : (
                                <span className="brak">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
              <p className="drobne" style={{ padding: "8px 2px 0" }}>
                „Poziomów” to ile nazwanych poziomów policzono z notowań —
                swingi, średnie, ekstrema roku, brzegi luk. Plan może się oprzeć
                wyłącznie na nich. „W zakresie 52t” mówi, jak wysoko w rocznym
                przedziale stoi kurs: 0% to dołek roku, 100% to szczyt.
              </p>
            </>
          )}

          {dni.length > 0 && (
            <>
              <div className="cardhead" style={{ padding: "22px 0 4px" }}>
                <h2 style={{ fontSize: "1.05rem" }}>Kandydaci w czasie</h2>
                <em>
                  {dni.length} {dni.length === 1 ? "dzień" : "dni"} historii
                </em>
              </div>

              {dni.length === 1 ? (
                <div className="card" style={{ marginTop: 12, padding: "14px 18px" }}>
                  <p className="pusto">
                    Historia ma na razie jeden dzień, więc nie ma czego
                    porównywać. Każdy poranny przebieg dokłada kolejny — po
                    tygodniu zobaczysz tu, które spółki wracają, a które
                    mignęły raz. <b>Nic nie trzeba włączać</b>: dossier nie jest
                    nadpisywane, tylko dopisywane.
                  </p>
                </div>
              ) : (
                <>
                  <div className="card" style={{ marginTop: 12 }}>
                    <div className="scroll">
                      <table className="tab-dossier-historia">
                        <thead>
                          <tr>
                            <th>Spółka</th>
                            <th className="kol-wykres">Wykres</th>
                            <th className="r">Dni w dossier</th>
                            <th>Pierwszy raz</th>
                            <th>Ostatni raz</th>
                            <th className="r">Kurs wtedy</th>
                            <th className="r">Kurs ostatnio</th>
                            <th className="r">Zmiana</th>
                            <th className="r">Maks. źródeł</th>
                            <th className="r">Planów</th>
                          </tr>
                        </thead>
                        <tbody>
                          {slady.map((s) => {
                            const c = cyfryCeny(s.kursPierwszy);
                            return (
                              <tr
                                key={s.ticker}
                                className={
                                  s.ticker.toUpperCase() === wybranyTicker
                                    ? "wiersz-wybrany"
                                    : undefined
                                }
                              >
                                <td className="t">
                                  <Link
                                    href={adres({ wybrana: s.ticker })}
                                    className="ticker-link"
                                  >
                                    {s.ticker}
                                    <small>{s.nazwa}</small>
                                  </Link>
                                </td>
                                <td className="kol-wykres">
                                  <Link
                                    href={adres({ wykres: s.ticker })}
                                    className="btn-wykres"
                                  >
                                    wykres
                                  </Link>
                                </td>
                                <td className="r n" data-l="Dni">
                                  <b>{s.dni}</b>
                                </td>
                                <td data-l="Pierwszy raz">{s.pierwszyDzien}</td>
                                <td data-l="Ostatni raz">{s.ostatniDzien}</td>
                                <td className="r n" data-l="Kurs wtedy">
                                  {lb(s.kursPierwszy, c)}
                                </td>
                                <td className="r n" data-l="Kurs ostatnio">
                                  {lb(s.kursOstatni, c)}
                                </td>
                                <td
                                  className={
                                    s.zmianaPct !== null && s.zmianaPct < 0
                                      ? "r n down"
                                      : s.zmianaPct !== null && s.zmianaPct > 0
                                        ? "r n up"
                                        : "r n"
                                  }
                                  data-l="Zmiana"
                                >
                                  {s.zmianaPct === null
                                    ? "—"
                                    : `${s.zmianaPct > 0 ? "+" : ""}${lb(s.zmianaPct, 1)}%`}
                                </td>
                                <td className="r n" data-l="Maks. źródeł">
                                  {s.maksZrodel}
                                </td>
                                <td className="r n" data-l="Planów">
                                  {s.planow > 0 ? (
                                    <b>{s.planow}</b>
                                  ) : (
                                    <span className="brak">0</span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <p className="drobne" style={{ padding: "8px 2px 0" }}>
                    {wracajace.length > 0 ? (
                      <>
                        <b>{wracajace.length}</b> z {slady.length} spółek pojawiło
                        się w dossier więcej niż raz.{" "}
                      </>
                    ) : (
                      <>Żadna spółka nie powtórzyła się jeszcze między dniami. </>
                    )}
                    „Zmiana” to ruch kursu od pierwszego pojawienia się w dossier
                    do ostatniego — mierzy, co się działo, gdy spółka była
                    wskazywana, <b>niezależnie od tego, czy powstał z niej plan</b>.
                    To najbliższe sprawdzeniu, czy sam dobór kandydatów cokolwiek
                    znaczy. Uwaga: spółka, która była w dossier jeden dzień, ma
                    tu z definicji zmianę zerową — porównuj tylko te z kilkoma
                    dniami.
                  </p>
                </>
              )}
            </>
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
        Dossier zapisuje się do bazy raz dziennie i nie jest nadpisywane, więc
        historia narasta sama. Jeden wpis to około 16 kB, z czego trzy czwarte
        to świece 1D/1W/1M — potrzebne przy układaniu planu, nieużywane na tym
        ekranie. Dlatego tabela „Kandydaci w czasie” czyta z bazy wyłącznie
        pojedyncze pola, nigdy całych paczek.
      </footer>

      {doWykresu && (
        <WykresPelny
          ticker={String(doWykresu.Ticker)}
          nazwa={String(doWykresu.Nazwa ?? "")}
          symbol={symbolTradingView(String(doWykresu.Ticker ?? ""))}
          adresZamkniecia={adres({ wykres: null })}
          cena={liczba(doWykresu.Cena)}
          waluta={String(doWykresu.Waluta ?? "")}
          powrot={adres({})}
        />
      )}
    </main>
  );
}
