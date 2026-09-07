import Link from "next/link";
import Pasek from "../Pasek";
import Formularz from "./Formularz";
import { migawkaBezpieczna } from "@/lib/dane";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

export default async function Transakcje() {
  await wymagajZalogowania();
  const { data, tryb } = await migawkaBezpieczna();

  return (
    <main className="wrap wrap-szeroki">
      <Pasek dataMigawki={data} tryb={tryb} />

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Analiza transakcji</h2>
        <em>import z XTB</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Wgraj historię swoich transakcji, a aplikacja sprawdzi dla każdego
        zakupu: <b>ile taniej dało się kupić</b>, gdybyś poczekał, oraz jakie
        wskaźniki panowały w dniu zakupu. Jeśli w pliku są też sprzedaże —
        sprawdzi, czy nie sprzedałeś zbyt wcześnie.
      </p>

      <Formularz />

      <details className="listy-ustawienia" style={{ marginTop: 16 }}>
        <summary>Jak przygotować plik?</summary>
        <div className="drobne" style={{ maxWidth: "80ch" }}>
          <p>
            <b>Eksport z XTB działa od ręki — nic nie trzeba poprawiać.</b>{" "}
            W xStation 5 wejdź w zakładkę <i>Historia</i> (dolny panel), ustaw
            zakres dat, kliknij prawym przyciskiem na dowolną transakcję
            i wybierz <i>Eksportuj do Excel (XLSX)</i>. Aplikacja sama rozpozna
            format, pominie wiersze metadanych, weźmie pozycje zamknięte
            i wciąż otwarte oraz przetłumaczy tickery z oznaczeń XTB
            (<code>ALE.PL</code>) na format Yahoo Finance (<code>ALE.WA</code>).
          </p>
          <p>
            <b>Inny broker albo własny plik?</b> Zapisz go jako CSV z nagłówkami
            w pierwszym wierszu. Rozpoznajemy kolumny po nazwie — wystarczy
            jedna z: <code>ticker</code> / <code>symbol</code>,{" "}
            <code>data zakupu</code> / <code>buy date</code> /{" "}
            <code>open price</code>… Sprzedaż jest opcjonalna
            (<code>data sprzedaży</code>, <code>cena sprzedaży</code>). Jeśli
            tickery używają oznaczeń XTB, zaznacz pole przy formularzu.
          </p>
          <p>
            <b>Czym różni się od wersji w Streamlicie:</b> tam po wgraniu
            dowolnego pliku wskazywało się ręcznie, która kolumna jest która.
            Tutaj kolumny rozpoznajemy po nazwach, a przy nieudanym
            rozpoznaniu wypisujemy nagłówki, które znaleźliśmy — bez
            dwuetapowego kreatora.
          </p>
        </div>
      </details>

      <footer>
        <b>Twój plik nie jest nigdzie zapisywany.</b> Przechodzi przez pamięć
        serwera na czas jednej analizy — nie trafia ani do bazy, ani na dysk.
        Do sieci wychodzą wyłącznie zapytania do Yahoo Finance o historię cen
        podanych tickerów. Krótkie pozycje (SELL) są pomijane: pytanie „ile
        taniej dało się kupić” nie ma dla nich sensu.
      </footer>
    </main>
  );
}
