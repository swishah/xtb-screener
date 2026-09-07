import Link from "next/link";
import Pasek from "../Pasek";
import Krzywa from "./Krzywa";
import { daty, migawkaBezpieczna, wszystkieMigawki } from "@/lib/dane";
import { backtestKolumny, podsumuj } from "@/lib/backtest";
import { STRATEGIE } from "@/lib/strategie";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

function lb(w: number | null, cyfry = 2, sufiks = ""): string {
  if (w === null) return "—";
  return `${w.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  })}${sufiks}`;
}

export default async function Backtest({
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

  const { data, tryb } = await migawkaBezpieczna();
  const dostepne = await daty().catch(() => [] as string[]);
  const migawek = dostepne.length;

  const topN = Math.max(1, Math.min(20, Number(jeden("topN") ?? 5) || 5));
  const trzymaj = Math.max(1, Math.min(20, Number(jeden("trzymaj") ?? 5) || 5));

  // Strategia z adresu; przy śmieciach bierzemy pierwszą z listy.
  const zadana = jeden("strategia") ?? "";
  const strategia =
    STRATEGIE.find((s) => s.klucz === zadana) ?? STRATEGIE[0];

  const licz = jeden("licz") === "1";
  let podsum = podsumuj([]);
  let dostepneKolumny: string[] = [];
  if (licz && migawek >= 2) {
    const wszystkie = await wszystkieMigawki();
    // Starsze migawki nie mają wszystkich kolumn wyniku — strategie dochodziły
    // z czasem. Sprawdzamy, czy wybrana w ogóle występuje, zamiast pokazywać
    // pusty wykres i kazać użytkownikowi zgadywać dlaczego.
    const pierwsza = [...wszystkie.values()].at(-1) ?? [];
    dostepneKolumny = STRATEGIE.filter((s) =>
      pierwsza.some((r) => r[s.kolumnaScore] !== undefined),
    ).map((s) => s.kolumnaScore);
    podsum = podsumuj(
      backtestKolumny(wszystkie, strategia.kolumnaScore, topN, trzymaj),
    );
  }

  const brakKolumny =
    licz && dostepneKolumny.length > 0 && !dostepneKolumny.includes(strategia.kolumnaScore);

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
    return s ? `/backtest?${s}` : "/backtest";
  }

  return (
    <main className="wrap wrap-szeroki">
      <Pasek dataMigawki={data} tryb={tryb} />

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Backtest strategii</h2>
        <em>{migawek} migawek w bazie</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Co by było, gdyby co skan kupić TOP N spółek wg wybranej strategii
        i sprzedać je po K kolejnych skanach. Liczone na <b>zapisanych
        migawkach</b>, nie na pełnej historii cen — bo tylko migawki mają
        realny, historyczny scoring fundamentalny z tamtego dnia. Im dłużej
        aplikacja zbiera skany, tym wiarygodniejszy wynik.
      </p>

      {migawek < 2 ? (
        <div className="card" style={{ marginTop: 12, padding: "16px 20px" }}>
          <p className="pusto">
            Masz {migawek} {migawek === 1 ? "migawkę" : "migawek"} w bazie.
            Potrzeba co najmniej kilku, żeby backtest miał sens — zbiorą się
            same wraz z kolejnymi skanami.
          </p>
        </div>
      ) : (
        <>
          <div className="filtry">
            <div className="podpanel-ustawienia" style={{ marginBottom: 10 }}>
              <span>Strategia:</span>
              {STRATEGIE.map((s) => (
                <Link
                  key={s.klucz}
                  href={adres({ strategia: s.klucz, licz: "1" })}
                  className={
                    s.klucz === strategia.klucz ? "pigulka aktywna" : "pigulka"
                  }
                >
                  {s.nazwa}
                </Link>
              ))}
            </div>
            <div className="podpanel-ustawienia">
              <span>TOP N:</span>
              {[3, 5, 10, 20].map((n) => (
                <Link
                  key={n}
                  href={adres({ topN: String(n), licz: "1" })}
                  className={n === topN ? "pigulka aktywna" : "pigulka"}
                >
                  {n}
                </Link>
              ))}
              <span style={{ marginLeft: 12 }}>Trzymaj przez:</span>
              {[1, 3, 5, 10].map((n) => (
                <Link
                  key={n}
                  href={adres({ trzymaj: String(n), licz: "1" })}
                  className={n === trzymaj ? "pigulka aktywna" : "pigulka"}
                >
                  {n}
                </Link>
              ))}
            </div>
          </div>

          {!licz ? (
            <div className="card" style={{ marginTop: 12, padding: "16px 20px" }}>
              <p className="pusto">
                Wybierz strategię albo kliknij poniżej — backtest liczy się na
                żądanie, bo wczytuje wszystkie migawki naraz.
              </p>
              <p style={{ marginTop: 10 }}>
                <Link className="link" href={adres({ licz: "1" })}>
                  Policz backtest →
                </Link>
              </p>
            </div>
          ) : brakKolumny ? (
            <div className="card" style={{ marginTop: 12, padding: "16px 20px" }}>
              <p className="komunikat-blad" style={{ margin: 0 }}>
                Strategia „{strategia.nazwa}” nie występuje w zapisanych
                migawkach — doszła do skanu później niż one. Wybierz inną albo
                poczekaj, aż uzbiera się historia z tą kolumną.
              </p>
            </div>
          ) : podsum.okna.length === 0 ? (
            <div className="card" style={{ marginTop: 12, padding: "16px 20px" }}>
              <p className="pusto">
                Za mało danych dla tej kombinacji: przy trzymaniu przez{" "}
                {trzymaj} skanów potrzeba co najmniej {trzymaj + 1} migawek,
                a jest {migawek}. Skróć okres trzymania.
              </p>
            </div>
          ) : (
            <>
              <div className="stats">
                <div>
                  <b
                    className={
                      podsum.sredniZwrot !== null && podsum.sredniZwrot < 0
                        ? "down"
                        : "up"
                    }
                  >
                    {podsum.sredniZwrot === null
                      ? "—"
                      : `${podsum.sredniZwrot > 0 ? "+" : ""}${lb(podsum.sredniZwrot)}%`}
                  </b>
                  <span>średni zwrot na okno</span>
                </div>
                <div>
                  <b>{lb(podsum.sredniWinRate, 1, "%")}</b>
                  <span>okien zakończonych zyskiem</span>
                </div>
                <div>
                  <b>{podsum.okna.length}</b>
                  <span>przetestowanych okien</span>
                </div>
                <div>
                  <b>
                    {lb(podsum.najlepsze, 1, "%")} / {lb(podsum.najgorsze, 1, "%")}
                  </b>
                  <span>najlepsze / najgorsze okno</span>
                </div>
              </div>

              <div className="card" style={{ marginTop: 12, padding: "14px 18px" }}>
                <h3 className="naglowek-sekcji">Skumulowany zwrot</h3>
                <p className="drobne" style={{ marginTop: 0 }}>
                  Krzywa zakłada <b>mechaniczne reinwestowanie</b> zwrotu
                  z każdego okna z rzędu. To uproszczenie, bo okna się
                  nakładają w czasie — traktuj jako orientacyjny obraz
                  kierunku, nie realną symulację portfela.
                </p>
                <Krzywa punkty={podsum.krzywa} />
              </div>

              <div className="card" style={{ marginTop: 12 }}>
                <div className="scroll">
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
                      {podsum.okna.map((o) => (
                        <tr key={`${o.wejscie}-${o.wyjscie}`}>
                          <td className="t">{o.wejscie}</td>
                          <td className="t">{o.wyjscie}</td>
                          <td className={o.sredniZwrot < 0 ? "r n down" : "r n up"}>
                            {o.sredniZwrot > 0 ? "+" : ""}
                            {lb(o.sredniZwrot)}%
                          </td>
                          <td className="r n">{lb(o.winRate, 1, "%")}</td>
                          <td className="r n">{o.spolek}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </>
      )}

      <footer>
        Okna są <b>nakładające się</b> — każdy skan to osobne wejście, więc
        sąsiednie okna opisują w dużej części ten sam ruch rynku i nie są
        niezależnymi próbami. Backtest nie uwzględnia prowizji, podatku ani
        dywidend, a historia liczy {migawek} migawek od sierpnia 2026, czyli
        jeden krótki wycinek rynku. To ocena doboru spółek, nie prognoza.
      </footer>
    </main>
  );
}
