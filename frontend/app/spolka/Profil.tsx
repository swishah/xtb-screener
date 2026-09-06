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
        Brak rekomendacji — sprawdzamy trzy źródła (Yahoo, stockanalysis.com
        i polskie domy maklerskie) i żadne nie pokrywa tej spółki. To normalne
        przy mniejszych spółkach i przy ETF-ach; nie mówi nic o jakości
        biznesu.
      </p>
    );
  }

  const potencjal =
    cel !== null && cena !== null && cena > 0
      ? ((cel - cena) / cena) * 100
      : null;

  // Skan zapisuje źródło jako "Yahoo", "stockanalysis" albo
  // "biznesradar (BM mBank, BOS DM)" — trzy różne metody liczenia.
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
        ) : zrodlo === "stockanalysis" ? (
          <>
            Źródło: <b>stockanalysis.com</b> — uśredniony konsensus analityków,
            ta sama metodologia co Yahoo, więc wartości są porównywalne.
            Używamy go tam, gdzie Yahoo nie ma danych — dotyczy to sporej
            części giełd europejskich. Konsensus bywa spóźniony i przesunięty
            w stronę rekomendacji „kupuj”.
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

/**
 * Krótkie pozycje. Sekcja istnieje TAKŻE wtedy, gdy danych nie ma — bo puste
 * miejsce znaczy tu dwie zupełnie różne rzeczy i użytkownik musi wiedzieć,
 * którą widzi:
 *
 *   „nikt nie gra na spadek tej spółki"  vs  „my tego rynku nie sprawdzamy"
 *
 * Pomylenie ich jest kosztowne: brak danych o shortach na spółce z GPW
 * wyglądałby na zielone światło, a znaczy tylko tyle, że nie zaczytujemy
 * rejestru KNF.
 */
function KrotkiePozycje({ spolka }: { spolka: Instrument }) {
  const ticker = String(spolka.Ticker ?? "");
  const sufiks = ticker.includes(".") ? ticker.split(".").pop() ?? "" : "";
  const zrodlo = String(spolka["Źródło shortów"] ?? "");
  const procent = liczba(spolka["Krótkie pozycje (%)"]);

  // Rynki, dla których mamy jakiekolwiek źródło. Reszta = nie sprawdzamy.
  const NADZOR: Record<string, string> = {
    L: "rejestr brytyjskiego nadzoru (FCA)",
    WA: "rejestr Komisji Nadzoru Finansowego",
    DE: "publikacje Bundesanzeigera",
    PA: "otwarte dane francuskiego nadzoru (AMF)",
    MC: "rejestr hiszpańskiego nadzoru (CNMV)",
    ST: "rejestr szwedzkiego nadzoru (Finansinspektionen)",
    OL: "rejestr norweskiego nadzoru (Finanstilsynet)",
    LS: "rejestr portugalskiego nadzoru (CMVM)",
  };
  const zrodloRynku = sufiks === "" ? "dane Yahoo dla USA" : NADZOR[sufiks];
  const sprawdzany = Boolean(zrodloRynku);

  if (procent === null) {
    return (
      <p className="pusto">
        {sprawdzany ? (
          <>
            Brak zgłoszonych pozycji krótkich. Przy tym instrumencie sprawdzamy{" "}
            {zrodloRynku}, więc pusto znaczy tu „nikt nie przekroczył progu
            jawności" — a nie „nie wiadomo".
          </>
        ) : (
          <>
            <b>Tego rynku nie sprawdzamy.</b> Krótkie pozycje w Europie
            publikują krajowe nadzory, każdy w innym formacie; na razie
            zaczytujemy rejestry brytyjski (FCA), polski (KNF), niemiecki
            (Bundesanzeiger), francuski (AMF), hiszpański (CNMV), szwedzki
            (Finansinspektionen), norweski (Finanstilsynet) i portugalski
            (CMVM), a dla USA dane z Yahoo. Puste miejsce NIE znaczy, że nikt nie gra na spadek tej
            spółki — znaczy, że nie mamy tu źródła.
          </>
        )}
      </p>
    );
  }

  // FCA i KNF podają procent wyemitowanego kapitału; Yahoo — wolnego obrotu.
  const REJESTRY: Record<string, string> = {
    FCA: "rejestr FCA",
    KNF: "rejestr KNF",
    Bundesanzeiger: "Bundesanzeiger",
    AMF: "rejestr AMF",
    CNMV: "rejestr CNMV",
    FI: "rejestr Finansinspektionen",
    SSR: "rejestr Finanstilsynet",
    CMVM: "rejestr CMVM",
  };
  const nazwaRejestru = Object.entries(REJESTRY).find(([k]) =>
    zrodlo.startsWith(k),
  )?.[1];
  const zRejestru = Boolean(nazwaRejestru);
  const dni = liczba(spolka["Short: dni do pokrycia"]);
  const ile = liczba(spolka["Short: liczba pozycji"]);
  const najwiekszy = String(spolka["Short: największy gracz"] ?? "");
  const data = String(spolka["Short z dnia"] ?? "");

  // Progi z praktyki rynkowej, nie z naszych pomiarów — stąd ostrożne słowa.
  const ocena =
    procent >= 10 ? "bardzo wysokie" : procent >= 5 ? "wysokie" : procent >= 2 ? "zauważalne" : "niskie";

  return (
    <div className="rek">
      <div className="rek-poz">
        <span className="rek-etykieta">Sprzedane na krótko</span>
        <strong>
          {procent.toLocaleString("pl-PL", { maximumFractionDigits: 2 })}%
        </strong>
        <span className="brak">{ocena}</span>
      </div>

      {dni !== null && (
        <div className="rek-poz">
          <span className="rek-etykieta">Dni do pokrycia</span>
          <strong>{dni.toLocaleString("pl-PL", { maximumFractionDigits: 1 })}</strong>
          <span className="brak">
            tyle dni typowego obrotu zajęłoby odkupienie tych akcji
          </span>
        </div>
      )}

      {ile !== null && (
        <div className="rek-poz">
          <span className="rek-etykieta">Zgłoszone pozycje</span>
          <strong>{ile}</strong>
          {najwiekszy && najwiekszy !== "BRAK" && (
            <span className="brak">największa: {najwiekszy}</span>
          )}
        </div>
      )}

      <p className="pusto" style={{ marginTop: 6 }}>
        {zRejestru ? (
          <>
            Źródło: <b>{nazwaRejestru}</b> — procent <b>wyemitowanego kapitału</b>,
            zsumowany z pojedynczych zgłoszeń funduszy powyżej progu jawności
            {data && data !== "BRAK" ? `, najnowsze z ${data}` : ""}. Pozycje
            poniżej progu nie są nigdzie zgłaszane, więc to wartość minimalna.
          </>
        ) : (
          <>
            Źródło: <b>Yahoo Finance</b> — procent <b>wolnego obrotu</b>, nie
            całego kapitału. To inna miara niż europejska: przy spółce z dużym
            pakietem kontrolnym obie potrafią się różnić kilkukrotnie
            {data && data !== "BRAK" ? `. Dane z ${data}` : ""}.
          </>
        )}{" "}
        Wysoki short bywa sygnałem problemów, ale bywa też paliwem do
        gwałtownego wzrostu, gdy pozycje trzeba odkupić. To opis liczby, nie
        rekomendacja.
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

      <section className="sekcja">
        <h3>Krótkie pozycje</h3>
        <KrotkiePozycje spolka={spolka} />
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
