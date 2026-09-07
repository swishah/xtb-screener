import Link from "next/link";
import Pasek from "../Pasek";
import WyborSpolki from "./Wybor";
import { historiaSpolki, migawkaBezpieczna } from "@/lib/dane";
import { liczba, type Instrument } from "@/lib/filtry";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

/** Wskaźniki pokazywane w tabeli dnia — te, które faktycznie coś mówią. */
const WSKAZNIKI = [
  "Cena",
  "Buy Score",
  "RSI",
  "pct_from_ath",
  "C/Z (P/E)",
  "C/WK (P/B)",
  "ROE (%)",
  "Marża netto (%)",
  "Stopa Dyw. (%)",
  "Dług/Kapitał",
  "Liczba flag",
  "SMA50",
  "SMA200",
];

function lb(w: number | null, cyfry = 2): string {
  if (w === null) return "—";
  return w.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  });
}

/**
 * Dwie ścieżki na jednym wykresie: cena i Buy Score.
 *
 * Każda ma WŁASNĄ skalę — cena idzie w setkach, a score od zera do dziewięciu,
 * więc na wspólnej osi score byłby płaską kreską przy dole. Wykres pokazuje
 * KSZTAŁT obu przebiegów obok siebie, nie ich wartości bezwzględne; dokładne
 * liczby są w tabeli poniżej.
 */
function Wykres({
  punkty,
}: {
  punkty: { dzien: string; cena: number | null; score: number | null }[];
}) {
  const zCena = punkty.filter((p) => p.cena !== null);
  if (zCena.length < 2) {
    return (
      <p className="pusto">
        Za mało migawek, żeby narysować przebieg (potrzeba co najmniej dwóch
        z ceną).
      </p>
    );
  }

  const SZER = 720;
  const WYS = 200;
  const M = { gora: 12, dol: 26, lewo: 46, prawo: 12 };

  const sciezka = (
    pobierz: (p: (typeof punkty)[number]) => number | null,
  ): string => {
    const wart = punkty.map(pobierz);
    const znane = wart.filter((w): w is number => w !== null);
    if (znane.length < 2) return "";
    const min = Math.min(...znane);
    const maks = Math.max(...znane);
    const rozp = maks - min || 1;
    let d = "";
    let zaczete = false;
    wart.forEach((w, i) => {
      if (w === null) return;
      const x = M.lewo + (i / (punkty.length - 1)) * (SZER - M.lewo - M.prawo);
      const y = M.gora + (1 - (w - min) / rozp) * (WYS - M.gora - M.dol);
      d += `${zaczete ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)} `;
      zaczete = true;
    });
    return d.trim();
  };

  const ceny = punkty.map((p) => p.cena).filter((w): w is number => w !== null);
  const scory = punkty.map((p) => p.score).filter((w): w is number => w !== null);

  return (
    <div className="scroll">
      <svg viewBox={`0 0 ${SZER} ${WYS}`} className="krzywa" role="img"
           aria-label="Przebieg ceny i Buy Score na tle migawek">
        <path d={sciezka((p) => p.cena)} className="krzywa-linia" />
        <path d={sciezka((p) => p.score)} className="krzywa-linia druga" />
        <text x={4} y={16} className="krzywa-opis">
          cena {lb(Math.min(...ceny))}–{lb(Math.max(...ceny))}
        </text>
        {scory.length > 0 && (
          <text x={4} y={30} className="krzywa-opis druga">
            score {lb(Math.min(...scory), 0)}–{lb(Math.max(...scory), 0)}
          </text>
        )}
        <text x={M.lewo} y={WYS - 6} className="krzywa-opis">
          {punkty[0].dzien}
        </text>
        <text x={SZER - M.prawo} y={WYS - 6} textAnchor="end" className="krzywa-opis">
          {punkty[punkty.length - 1].dzien}
        </text>
      </svg>
    </div>
  );
}

export default async function Historia({
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

  const { instrumenty, data, tryb } = await migawkaBezpieczna();
  const zadany = (jeden("spolka") ?? "").toUpperCase();
  const spolka: Instrument | undefined =
    instrumenty.find((i) => String(i.Ticker ?? "").toUpperCase() === zadany) ??
    instrumenty[0];

  const ticker = String(spolka?.Ticker ?? "");
  const historia = ticker ? await historiaSpolki(ticker) : [];

  const punkty = historia.map((h) => ({
    dzien: h.dzien,
    cena: liczba(h.wiersz.Cena),
    score: liczba(h.wiersz["Buy Score"]),
  }));

  // Wybrany dzień; domyślnie najnowszy.
  const zadanyDzien = jeden("dzien") ?? "";
  const wybrany =
    historia.find((h) => h.dzien === zadanyDzien) ?? historia[historia.length - 1];

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
    return s ? `/historia?${s}` : "/historia";
  }

  return (
    <main className="wrap wrap-szeroki">
      <Pasek dataMigawki={data} tryb={tryb} />

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Backtest spółki</h2>
        <em>jak wyglądała w zapisanych migawkach</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Jak konkretna spółka wyglądała w kolejnych skanach — nie tylko cena, ale
        <b> komplet wskaźników z tamtego dnia</b>. To dane zapisane wtedy,
        a nie przeliczone dziś wstecz, więc widać dokładnie to, co pokazywała
        aplikacja w danym momencie.
      </p>

      <WyborSpolki spolki={instrumenty} wybrana={ticker} />

      {historia.length === 0 ? (
        <div className="card" style={{ marginTop: 12, padding: "16px 20px" }}>
          <p className="pusto">
            Brak zapisanych migawek dla {ticker || "tej spółki"}. Instrumenty
            dopisane ręcznie pojawiają się dopiero po pierwszym skanie.
          </p>
        </div>
      ) : (
        <>
          <div className="card" style={{ marginTop: 12, padding: "14px 18px" }}>
            <h3 className="naglowek-sekcji">
              {ticker} — {String(spolka?.Nazwa ?? "")}
            </h3>
            <p className="drobne" style={{ marginTop: 0 }}>
              {historia.length} migawek od {historia[0].dzien} do{" "}
              {historia[historia.length - 1].dzien}. Cena i Buy Score mają
              WŁASNE skale — wykres pokazuje kształt obu przebiegów obok siebie,
              nie ich wartości bezwzględne.
            </p>
            <Wykres punkty={punkty} />
          </div>

          <div className="cardhead" style={{ padding: "18px 0 4px" }}>
            <h2 style={{ fontSize: "1.05rem" }}>Stan w wybranym dniu</h2>
            <em>{wybrany?.dzien}</em>
          </div>

          <div className="filtry">
            <div className="podpanel-ustawienia">
              <span>Dzień migawki:</span>
              {historia.map((h) => (
                <Link
                  key={h.dzien}
                  href={adres({ dzien: h.dzien })}
                  className={
                    h.dzien === wybrany?.dzien ? "pigulka aktywna" : "pigulka"
                  }
                >
                  {h.dzien.slice(5)}
                </Link>
              ))}
            </div>
          </div>

          {wybrany && (
            <div className="card" style={{ marginTop: 12 }}>
              <div className="scroll">
                <table className="tab-historia">
                  <thead>
                    <tr>
                      <th>Wskaźnik</th>
                      <th className="r">{wybrany.dzien}</th>
                      <th className="r">dziś ({data})</th>
                      <th className="r">zmiana</th>
                    </tr>
                  </thead>
                  <tbody>
                    {WSKAZNIKI.filter((k) => wybrany.wiersz[k] !== undefined).map(
                      (k) => {
                        const wtedy = liczba(wybrany.wiersz[k]);
                        const teraz = liczba(spolka?.[k]);
                        const zmiana =
                          wtedy !== null && teraz !== null && wtedy !== 0
                            ? ((teraz - wtedy) / Math.abs(wtedy)) * 100
                            : null;
                        return (
                          <tr key={k}>
                            <td className="t">{k}</td>
                            <td className="r n">{lb(wtedy)}</td>
                            <td className="r n">{lb(teraz)}</td>
                            <td
                              className={
                                zmiana === null
                                  ? "r n"
                                  : zmiana < 0
                                    ? "r n down"
                                    : "r n up"
                              }
                            >
                              {zmiana === null
                                ? "—"
                                : `${zmiana > 0 ? "+" : ""}${zmiana.toFixed(1)}%`}
                            </td>
                          </tr>
                        );
                      },
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      <footer>
        Historia sięga tak daleko, jak sięgają zapisane migawki — pierwsza
        pochodzi z sierpnia 2026, więc to obraz ostatnich tygodni, nie lat.
        Kolumna „zmiana” porównuje wybrany dzień z najnowszą migawką; przy
        wskaźnikach, które w danym dniu były puste, zostaje kreska.
      </footer>
    </main>
  );
}
