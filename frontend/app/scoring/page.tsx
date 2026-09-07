import Link from "next/link";
import { Suspense } from "react";
import Pasek from "../Pasek";
import PanelWag from "./Wagi";
import { migawkaBezpieczna, wszystkieMigawki } from "@/lib/dane";
import { liczba, porownajRemis, type Instrument } from "@/lib/filtry";
import {
  MAKS_WAGA,
  SKLADNIKI,
  backtest,
  policzWyniki,
  wagiDomyslne,
  type Wagi,
} from "@/lib/wlasny";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

const LIMIT = 30;

function fmt(w: unknown, cyfry = 2, sufiks = ""): React.ReactNode {
  const n = liczba(w);
  if (n === null) return <span className="brak">BRAK</span>;
  return `${n.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  })}${sufiks}`;
}

export default async function Scoring({
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

  // Wagi z adresu; brak parametru = wartość domyślna składnika. Wartości spoza
  // zakresu przycinamy, żeby ręcznie podrasowany adres nie robił dziwnych rzeczy.
  const domyslne = wagiDomyslne();
  const wagi: Wagi = {};
  for (const s of SKLADNIKI) {
    const surowa = jeden(`w_${s.kolumna}`);
    const n = surowa === undefined || surowa.trim() === "" ? s.domyslna : Number(surowa);
    wagi[s.kolumna] = Number.isFinite(n)
      ? Math.max(0, Math.min(MAKS_WAGA, Math.round(n)))
      : s.domyslna;
  }
  const suma = SKLADNIKI.reduce((s, k) => s + wagi[k.kolumna], 0);
  const domyslny = SKLADNIKI.every((s) => wagi[s.kolumna] === domyslne[s.kolumna]);

  const { instrumenty, data, tryb, blad } = await migawkaBezpieczna();
  const spolki = instrumenty.filter((i) => String(i.Typ ?? "") === "stock");
  const punkty = policzWyniki(spolki, wagi);

  const ranking: { s: Instrument; p: number }[] = punkty
    ? spolki
        .map((s, i) => ({ s, p: punkty[i] ?? 0 }))
        // Remisy rozstrzygamy wspólną regułą projektu (mniej flag → wyższy
        // Buy Score → ticker alfabetycznie). Bez niej dwie spółki z tym samym
        // wynikiem zamieniałyby się miejscami między odświeżeniami.
        .sort((a, b) => (b.p !== a.p ? b.p - a.p : porownajRemis(a.s, b.s)))
        .slice(0, LIMIT)
    : [];

  const aktywne = SKLADNIKI.filter((s) => wagi[s.kolumna] > 0);

  // Backtest liczy się WYŁĄCZNIE na żądanie — czyta całą tabelę migawek.
  const chceBacktest = jeden("backtest") === "1";
  const topN = Math.max(1, Math.min(20, Number(jeden("topN") ?? 5) || 5));
  const trzymaj = Math.max(1, Math.min(20, Number(jeden("trzymaj") ?? 5) || 5));
  let okna: ReturnType<typeof backtest> = [];
  let migawek = 0;
  if (chceBacktest && punkty) {
    const wszystkie = await wszystkieMigawki();
    migawek = wszystkie.size;
    okna = backtest(wszystkie, wagi, topN, trzymaj);
  }
  const sredniZwrot = okna.length
    ? okna.reduce((s, o) => s + o.sredniZwrot, 0) / okna.length
    : null;
  const sredniWin = okna.length
    ? okna.reduce((s, o) => s + o.winRate, 0) / okna.length
    : null;

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
    return s ? `/scoring?${s}` : "/scoring";
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
        <h2 style={{ fontSize: "1.15rem" }}>Własny scoring</h2>
        <em>migawka z {data}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Zamiast gotowych strategii — ustaw własne wagi wskaźników, które są dla
        Ciebie ważne. Zero znaczy „pomiń całkowicie”. Wynik to średnia ważona
        pozycji percentylowych na tle reszty rynku (0–100), więc suwaki działają
        niezależnie od jednostek: stopa dywidendy w procentach i C/Z w krotnościach
        ważą tyle samo przy tej samej wadze. Ustawienia siedzą w adresie strony,
        więc ulubioną formułę zapiszesz zwykłą zakładką przeglądarki.
      </p>

      <Suspense fallback={<div className="filtry">Wczytuję wagi…</div>}>
        <PanelWag wagi={wagi} suma={suma} />
      </Suspense>

      {!domyslny && (
        <p className="drobne">
          <Link className="link" href="/scoring">
            ← Wróć do wag domyślnych
          </Link>
        </p>
      )}

      <div className="card" style={{ marginTop: 12 }}>
        {!punkty ? (
          <p style={{ padding: 16, color: "var(--muted)" }}>
            Wszystkie wagi są zerowe, więc nie ma z czego liczyć wyniku. Podnieś
            przynajmniej jeden suwak.
          </p>
        ) : (
          <div className="scroll">
            <table className="tab-scoring">
              <thead>
                <tr>
                  <th>Spółka</th>
                  <th className="r">Wynik</th>
                  <th className="r">Cena</th>
                  {aktywne.map((s) => (
                    <th key={s.kolumna} className="r" title={s.etykieta}>
                      {s.kolumna}
                    </th>
                  ))}
                  <th className="r">Flagi</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map(({ s, p }) => (
                  <tr key={String(s.Ticker)}>
                    <td className="t">
                      <Link
                        className="ticker-link"
                        href={`/spolka/${encodeURIComponent(String(s.Ticker))}`}
                      >
                        {String(s.Ticker)}
                        <small>{String(s.Nazwa ?? "")}</small>
                      </Link>
                    </td>
                    <td className="r n">
                      <b>{p.toLocaleString("pl-PL", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</b>
                    </td>
                    <td className="r n">{fmt(s.Cena)}</td>
                    {aktywne.map((k) => (
                      <td key={k.kolumna} className="r n">
                        {fmt(s[k.kolumna], 1)}
                      </td>
                    ))}
                    <td className="r n">{fmt(s["Liczba flag"], 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="drobne">
        Widzisz {ranking.length} najlepszych spółek z{" "}
        {spolki.length.toLocaleString("pl-PL")} (bez ETF-ów). W tabeli pokazujemy
        tylko te wskaźniki, którym nadałeś wagę większą od zera. Spółka bez danej
        wartości dostaje w tym miejscu środek stawki, a nie zero — brak danych
        u dostawcy nie jest winą spółki.
      </p>

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.05rem" }}>Backtest tych wag</h2>
        <em>jak ta formuła spisywałaby się na zapisanych migawkach</em>
        {punkty && !chceBacktest && (
          <Link className="link" href={adres({ backtest: "1" })}>
            Policz →
          </Link>
        )}
        {chceBacktest && (
          <Link className="link" href={adres({ backtest: null })}>
            Ukryj
          </Link>
        )}
      </div>

      <div className="card" style={{ marginTop: 12, padding: "12px 20px" }}>
        {!chceBacktest ? (
          <p className="pusto">
            Kliknij „Policz”, żeby sprawdzić, jak ta kombinacja wag wypadłaby
            wstecz. Liczone na żądanie, bo wymaga wczytania wszystkich migawek
            naraz — to jedyne miejsce w aplikacji, które czyta całą historię.
          </p>
        ) : okna.length === 0 ? (
          <p className="pusto">
            Za mało migawek na taki backtest ({migawek} w bazie, a przy trzymaniu
            przez {trzymaj} skanów potrzeba co najmniej {trzymaj + 1}). Skróć
            okres trzymania albo poczekaj na kolejne skany.
          </p>
        ) : (
          <>
            <div className="podpanel-ustawienia">
              <span>TOP N spółek:</span>
              {[3, 5, 10, 20].map((n) => (
                <Link
                  key={n}
                  href={adres({ topN: String(n) })}
                  className={n === topN ? "pigulka aktywna" : "pigulka"}
                >
                  {n}
                </Link>
              ))}
              <span style={{ marginLeft: 12 }}>Trzymaj przez:</span>
              {[1, 3, 5, 10].map((n) => (
                <Link
                  key={n}
                  href={adres({ trzymaj: String(n) })}
                  className={n === trzymaj ? "pigulka aktywna" : "pigulka"}
                >
                  {n}
                </Link>
              ))}
            </div>

            <div className="stats" style={{ marginTop: 12 }}>
              <div>
                <b className={sredniZwrot !== null && sredniZwrot < 0 ? "down" : "up"}>
                  {sredniZwrot === null
                    ? "—"
                    : `${sredniZwrot > 0 ? "+" : ""}${sredniZwrot.toFixed(2)}%`}
                </b>
                <span>średni zwrot na okno</span>
              </div>
              <div>
                <b>{sredniWin === null ? "—" : `${sredniWin.toFixed(1)}%`}</b>
                <span>okien zakończonych zyskiem</span>
              </div>
              <div>
                <b>{okna.length}</b>
                <span>przetestowanych okien</span>
              </div>
            </div>

            <div className="scroll" style={{ marginTop: 10 }}>
              <table className="tab-backtest">
                <thead>
                  <tr>
                    <th>Wejście</th>
                    <th>Wyjście</th>
                    <th className="r">Śr. zwrot</th>
                    <th className="r">Zyskownych</th>
                    <th className="r">Spółek</th>
                  </tr>
                </thead>
                <tbody>
                  {okna.map((o) => (
                    <tr key={`${o.wejscie}-${o.wyjscie}`}>
                      <td className="t">{o.wejscie}</td>
                      <td className="t">{o.wyjscie}</td>
                      <td className={o.sredniZwrot < 0 ? "r n down" : "r n up"}>
                        {o.sredniZwrot > 0 ? "+" : ""}
                        {o.sredniZwrot.toFixed(2)}%
                      </td>
                      <td className="r n">{o.winRate.toFixed(1)}%</td>
                      <td className="r n">{o.spolek}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="drobne">
              Okna są <b>nakładające się</b> (każdy skan to osobne wejście), więc
              nie traktuj ich jak niezależnych prób — sąsiednie okna opisują w dużej
              części ten sam ruch rynku. Backtest nie uwzględnia prowizji, podatku
              ani dywidend, a historia liczy {migawek} migawek od sierpnia 2026,
              czyli obejmuje jeden krótki wycinek rynku. To wskazówka o doborze
              spółek, nie prognoza.
            </p>
          </>
        )}
      </div>

      <footer>
        Wynik jest pozycją percentylową w TEJ migawce, więc zmienia się po każdym
        skanie — spółka może dostać wyższy wynik, nie zmieniając się ani trochę,
        jeśli reszta rynku się pogorszy. Kolumny bez danych liczą się jako środek
        stawki.
      </footer>
    </main>
  );
}
