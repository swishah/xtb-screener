import Link from "next/link";
import Pasek from "./Pasek";
import Tabela from "./Tabela";
import { KATEGORIE } from "./moduly";
import { migawkaBezpieczna } from "@/lib/dane";
import { najlepsze, statystyki } from "@/lib/filtry";

// Renderowanie na żądanie: strona ma pokazywać stan bazy, a nie zamrożoną
// wersję z chwili budowania. Powtarzalny koszt odczytu zdejmuje bufor
// w lib/dane.ts (kwadrans), więc "na żądanie" nie znaczy "za każdym razem
// od zera".
export const dynamic = "force-dynamic";

export default async function Pulpit() {
  const { data, tryb, instrumenty, blad } = await migawkaBezpieczna();
  const s = statystyki(instrumenty);
  const top = najlepsze(instrumenty, 8);

  return (
    <main className="wrap">
      <Pasek dataMigawki={data} tryb={tryb} />

      {blad && (
        <div className="alert">
          <b>Nie udało się wczytać danych.</b> Nawigacja poniżej działa, ale
          liczby i tabela pozostają puste. Najczęstsza przyczyna to niedostępna
          baza albo brak zmiennych konfiguracyjnych.
          <div style={{ marginTop: 8, fontSize: "0.78rem", opacity: 0.75 }}>
            {blad}
          </div>
        </div>
      )}

      <div className="stats">
        <div>
          <b>{s.wszystkie.toLocaleString("pl-PL")}</b>
          <span>instrumentów</span>
        </div>
        <div>
          <b>{s.akcje.toLocaleString("pl-PL")}</b>
          <span>akcji</span>
        </div>
        <div>
          <b>{s.etfy.toLocaleString("pl-PL")}</b>
          <span>ETF-ów</span>
        </div>
        <div>
          <b>{s.bezFlag.toLocaleString("pl-PL")}</b>
          <span>bez flag</span>
        </div>
        <div>
          <b>
            {s.sredniScore === null
              ? "—"
              : s.sredniScore.toLocaleString("pl-PL", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
          </b>
          <span>śr. buy score</span>
        </div>
      </div>

      {KATEGORIE.map((kat) => (
        <section key={kat.etykieta}>
          <div className="grouphead">
            <span className="dot" style={{ background: `var(--${kat.klasa}-fg)` }} />
            {kat.etykieta}
          </div>
          <div className="modules">
            {kat.moduly.map((m) =>
              m.sciezka ? (
                <Link key={m.nazwa} href={m.sciezka} className={`mod ${kat.klasa}`}>
                  <b>{m.nazwa}</b>
                  <span>{m.opis}</span>
                </Link>
              ) : (
                <div key={m.nazwa} className={`mod ${kat.klasa} wkrotce`}>
                  <b>{m.nazwa}</b>
                  <span>{m.opis}</span>
                  <span className="znacznik">wkrótce</span>
                </div>
              ),
            )}
          </div>
        </section>
      ))}

      <div className="card">
        <div className="cardhead">
          <h2>Najwyższy Buy Score</h2>
          <em>migawka z {data}</em>
          <Link className="link" href="/screener">
            Otwórz screener →
          </Link>
        </div>
        <Tabela wiersze={top} />
      </div>

      <footer>
        Narzędzie do przeglądu i rankingu, nie porada inwestycyjna — decyzje i ich
        skutki są po Twojej stronie. Wskaźniki liczone podczas codziennego skanu.
        Metodologia pod pytajnikiem u góry.
      </footer>
    </main>
  );
}
