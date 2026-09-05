import Wskaznik from "./Wskaznik";
import { liczba, zieloneFlagi, type Instrument } from "@/lib/filtry";
import { statystykiSektora } from "@/lib/sektor";
import type { News } from "@/lib/newsy";
import {
  GRUPY,
  WSZYSTKIE_WSKAZNIKI,
  formatuj,
  ocen,
  wartoscWskaznika,
  zdanieOSektorze,
} from "@/lib/wskazniki";

/**
 * Profil spółki — komponent SERWEROWY, używany w dwóch miejscach: na własnej
 * stronie /spolka/[ticker] oraz w panelu bocznym Screenera. Dzięki temu obie
 * ścieżki pokazują dokładnie to samo i nie rozjadą się przy kolejnych zmianach.
 */

function Rekomendacja({ spolka }: { spolka: Instrument }) {
  const rek = String(spolka["Rekomendacja analityków"] ?? "BRAK");
  const ilu = liczba(spolka["Liczba analityków"]);
  const cel = liczba(spolka["Cena docelowa (analitycy)"]);
  const cena = liczba(spolka["Cena"]);
  const brakDanych = rek === "BRAK" || rek === "Brak" || !ilu;

  if (brakDanych) {
    return (
      <p className="pusto">
        Brak rekomendacji — ani w konsensusie Yahoo, ani wśród polskich domów
        maklerskich. To normalne przy mniejszych spółkach spoza USA i nie mówi
        nic o jakości biznesu.
      </p>
    );
  }

  const potencjal =
    cel !== null && cena !== null && cena > 0
      ? ((cel - cena) / cena) * 100
      : null;

  // Skan zapisuje źródło w postaci "biznesradar (BM mBank, BOS DM)".
  const zrodlo = String(spolka["Źródło rekomendacji"] ?? "");
  const zBiznesradar = zrodlo.startsWith("biznesradar");
  const domy = zBiznesradar ? (zrodlo.match(/\(([^)]+)\)/)?.[1] ?? "") : "";
  const suroweData = String(spolka["Rekomendacja z dnia"] ?? "");
  const dataRek = suroweData && suroweData !== "BRAK" ? suroweData : "";

  return (
    <div className="rek">
      <div className="rek-poz">
        <span className="rek-etykieta">Konsensus</span>
        <strong>{rek}</strong>
        <span className="brak">
          {ilu} {zBiznesradar ? "rekomendacji" : "analityków"}
        </span>
      </div>
      {cel !== null && (
        <div className="rek-poz">
          <span className="rek-etykieta">Cena docelowa</span>
          <strong>
            {cel.toLocaleString("pl-PL", { maximumFractionDigits: 2 })}{" "}
            {String(spolka.Waluta ?? "")}
          </strong>
          {potencjal !== null && (
            <span className={potencjal < 0 ? "down" : "up"}>
              {potencjal > 0 ? "+" : ""}
              {potencjal.toLocaleString("pl-PL", { maximumFractionDigits: 1 })}% do
              kursu
            </span>
          )}
        </div>
      )}
      <p className="pusto" style={{ marginTop: 6 }}>
        {zBiznesradar ? (
          <>
            Źródło: <b>biznesradar.pl</b> — pojedyncze rekomendacje domów
            maklerskich{domy ? ` (${domy})` : ""}
            {dataRek ? `, najnowsza z ${dataRek}` : ""}. To INNA metodologia niż
            konsensus Yahoo: kilka polskich rekomendacji zamiast dziesiątek
            analityków. Uzupełniamy nią spółki, których Yahoo nie pokrywa —
            dotyczy to większości polskiej giełdy.
          </>
        ) : (
          <>
            Źródło: <b>Yahoo Finance</b> — uśredniony konsensus analityków.
            Bywa spóźniony i przesunięty w stronę rekomendacji „kupuj”, więc
            traktuj jako jedną z przesłanek, nie rozstrzygnięcie.
          </>
        )}
      </p>
    </div>
  );
}

export default function Profil({
  spolka,
  wszystkie,
  newsy,
  kompaktowy = false,
}: {
  spolka: Instrument;
  wszystkie: Instrument[];
  newsy: News[];
  /** Wersja do panelu bocznego: węższa siatka, bez powtarzania nagłówka. */
  kompaktowy?: boolean;
}) {
  const sektor = typeof spolka.Sektor === "string" ? spolka.Sektor : undefined;
  const stat = statystykiSektora(
    wszystkie,
    sektor,
    WSZYSTKIE_WSKAZNIKI.map((w) => w.klucz),
  );

  // Skan wpisuje tu "Brak" albo "BRAK", gdy nic nie znalazł — bez tego
  // sprawdzenia sekcja pokazywała pozycję listy o treści „Brak”, co wygląda
  // jak flaga, a znaczy jej brak.
  const suroweFlagi = String(spolka["Czerwone flagi"] ?? "").trim();
  const flagi = suroweFlagi.toLowerCase() === "brak" ? "" : suroweFlagi;
  const mocneStrony = zieloneFlagi(spolka);

  return (
    <div className={kompaktowy ? "profil profil-kompakt" : "profil"}>
      {flagi && (
        <section className="sekcja">
          <h3>Czerwone flagi</h3>
          <ul className="flagi-lista">
            {flagi
              .split(/[;|]\s*/)
              .filter(Boolean)
              .map((f, i) => (
                <li key={i}>{f}</li>
              ))}
          </ul>
        </section>
      )}

      {mocneStrony.length > 0 && (
        <section className="sekcja">
          <h3>Mocne strony</h3>
          <ul className="flagi-lista flagi-zielone">
            {mocneStrony.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="sekcja">
        <h3>Analitycy</h3>
        <Rekomendacja spolka={spolka} />
      </section>

      {GRUPY.map((grupa) => (
        <section key={grupa.nazwa} className="sekcja">
          <h3>{grupa.nazwa}</h3>
          <div className="wsk-siatka">
            {grupa.wskazniki.map((def) => {
              const wartosc = wartoscWskaznika(spolka, def.klucz);
              const mediana = stat?.mediany[def.klucz] ?? null;
              return (
                <Wskaznik
                  key={def.klucz}
                  etykieta={def.etykieta}
                  wartosc={formatuj(def, spolka[def.klucz])}
                  ocena={ocen(def, wartosc, mediana)}
                  opis={def.opis}
                  porownanie={zdanieOSektorze(
                    def,
                    wartosc,
                    mediana,
                    stat?.sektor,
                    stat?.liczbaSpolek ?? 0,
                  )}
                />
              );
            })}
          </div>
        </section>
      ))}

      <section className="sekcja">
        <h3>Newsy z ostatniego miesiąca</h3>
        {newsy.length > 0 ? (
          <ul className="newsy">
            {newsy.map((n) => (
              <li key={n.link}>
                <a href={n.link} target="_blank" rel="noopener noreferrer">
                  {n.tytul}
                </a>
                <span className="brak">
                  {n.wydawca} ·{" "}
                  {new Date(n.czas * 1000).toLocaleDateString("pl-PL")}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="pusto">
            Brak artykułów z ostatniego miesiąca, w których tytule pada nazwa
            tej spółki. Wymóg nazwy w tytule jest celowy — bez niego przy
            wieloznacznych nazwach trafiały tu teksty o zupełnie innych firmach.
          </p>
        )}
      </section>
    </div>
  );
}
