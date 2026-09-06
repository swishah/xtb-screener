import Link from "next/link";
import { Suspense } from "react";
import Pasek from "../Pasek";
import PanelFiltrow from "../Filtry";
import PanelSpolki from "../PanelSpolki";
import TabelaStrategii from "./TabelaStrategii";
import WykresPelny from "../spolka/WykresPelny";
import { migawkaBezpieczna } from "@/lib/dane";
import { newsySpolki } from "@/lib/newsy";
import { symbolTradingView } from "@/lib/tradingview";
import {
  FILTRY_DOMYSLNE,
  filtruj,
  liczba,
  porownajRemis,
  wartosci,
  type Filtry,
} from "@/lib/filtry";
import { STRATEGIE, znajdzStrategie } from "@/lib/strategie";

export const dynamic = "force-dynamic";

const ILE = 30;

/** Liczba z adresu URL; przy śmieciach wraca wartość domyślna. */
function num(wejscie: string | undefined, domyslna: number): number {
  if (wejscie === undefined) return domyslna;
  const n = Number(wejscie);
  return Number.isFinite(n) ? n : domyslna;
}

export default async function Strategie({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };

  const strategia = znajdzStrategie(jeden("s"));

  // Te same filtry co w Screenerze, ten sam komponent, te same nazwy
  // parametrów. Pole „sortuj" jest tu nieużywane — kolejność wyznacza wynik
  // strategii, a przestawia się ją kliknięciem w nagłówek kolumny.
  const filtry: Filtry = {
    typ: jeden("typ") ?? FILTRY_DOMYSLNE.typ,
    rynek: jeden("rynek") ?? "",
    sektor: jeden("sektor") ?? "",
    minScore: num(jeden("minScore"), 0),
    maxAth: num(jeden("maxAth"), 0),
    maxFlag: num(jeden("maxFlag"), 10),
    szukaj: jeden("szukaj") ?? "",
    sortuj: FILTRY_DOMYSLNE.sortuj,
  };

  // Sortowanie po kolumnie trzymamy w adresie URL, tak samo jak wybór
  // strategii. Kolumna spoza tej strategii jest ignorowana, żeby ręcznie
  // podrasowany adres nie wywalał strony.
  const zadanaKolumna = jeden("sort");
  const sortKolumna =
    zadanaKolumna && strategia.kolumny.includes(zadanaKolumna)
      ? zadanaKolumna
      : null;
  const sortRosnaco = jeden("kier") === "asc";

  const { data, tryb, instrumenty, blad } = await migawkaBezpieczna();

  // Listy wyboru budujemy z instrumentów danego TYPU, ale bez pozostałych
  // filtrów — inaczej wybranie sektora wycinałoby z listy rynki i nie dałoby
  // się już wrócić.
  const wTypie = filtry.typ
    ? instrumenty.filter((i) => i.Typ === filtry.typ)
    : instrumenty;

  // NAJPIERW filtrujemy, POTEM szeregujemy. Odwrotna kolejność dawałaby
  // „trzydzieści najlepszych spółek świata, z których akurat dwie są polskie";
  // tak dostajemy trzydzieści najlepszych spośród tych, które wybrałeś.
  const dopasowane = filtruj(instrumenty, filtry);

  // Spółka bez policzonego wyniku nie ma czego szukać w rankingu — inaczej
  // wypełniałaby koniec listy zerami i sugerowała, że została oceniona.
  const ranking = dopasowane
    .filter((i) => liczba(i[strategia.kolumnaScore]) !== null)
    .sort((a, b) => {
      const roznica =
        (liczba(b[strategia.kolumnaScore]) ?? 0) -
        (liczba(a[strategia.kolumnaScore]) ?? 0);
      // Wyniki strategii są całkowite i niskie, więc na szczycie remisuje
      // kilkanaście spółek naraz. Bez jawnej reguły czołówka byłaby losowa
      // i zmieniałaby się między odświeżeniami — patrz porownajRemis().
      return roznica !== 0 ? roznica : porownajRemis(a, b);
    });

  // Sortowanie po kolumnie działa NA CZOŁÓWCE, nie na całym uniwersum:
  // strategia wybiera zestaw spółek, a kolumna zmienia tylko kolejność
  // wyświetlania. Inaczej sortowanie po ROE pokazywałoby spółki z wysokim ROE
  // i wynikiem 1/8, co nie miałoby nic wspólnego ze strategią.
  const czolo = ranking.slice(0, ILE);
  if (sortKolumna) {
    czolo.sort((a, b) => {
      const x = liczba(a[sortKolumna]);
      const y = liczba(b[sortKolumna]);
      // Brak wartości zawsze na koniec, niezależnie od kierunku — "BRAK" nie
      // może udawać ani najlepszego, ani najgorszego wyniku.
      if (x === null && y === null) return porownajRemis(a, b);
      if (x === null) return 1;
      if (y === null) return -1;
      if (x === y) return porownajRemis(a, b);
      return sortRosnaco ? x - y : y - x;
    });
  }
  const najlepszyWynik = liczba(czolo[0]?.[strategia.kolumnaScore]) ?? 0;

  /**
   * Adres zachowujący wszystko, co już jest w URL, i zmieniający tylko to,
   * co trzeba. Dzięki temu otwarcie wykresu nie gubi filtrów ani wybranej
   * strategii, a zamknięcie panelu nie gubi sortowania.
   */
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
    return s ? `/strategie?${s}` : "/strategie";
  }

  // --- panel boczny i wykres ----------------------------------------------
  const wybranyTicker = (jeden("wybrana") ?? "").toUpperCase();
  const wybrana = wybranyTicker
    ? instrumenty.find(
        (i) => String(i.Ticker ?? "").toUpperCase() === wybranyTicker,
      )
    : undefined;
  const newsy = wybrana
    ? await newsySpolki(String(wybrana.Ticker), String(wybrana.Nazwa ?? ""))
    : [];

  const wykresTicker = (jeden("wykres") ?? "").toUpperCase();
  const doWykresu = wykresTicker
    ? instrumenty.find(
        (i) => String(i.Ticker ?? "").toUpperCase() === wykresTicker,
      )
    : undefined;

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
        <h2 style={{ fontSize: "1.15rem" }}>Strategie</h2>
        <em>migawka z {data}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      {/* Wybór strategii zwykłymi odnośnikami, nie przyciskami: adres URL
          jednoznacznie opisuje widok, więc da się go zapisać i wysłać.
          Zmiana strategii zachowuje filtry — porównywanie tych samych spółek
          w różnych strategiach to główny sposób korzystania z tego modułu. */}
      <nav className="wybor">
        {STRATEGIE.map((s) => (
          <Link
            key={s.klucz}
            href={adres({ s: s.klucz, sort: null, kier: null })}
            className={`wybor-poz${s.klucz === strategia.klucz ? " aktywna" : ""}`}
            aria-current={s.klucz === strategia.klucz ? "page" : undefined}
          >
            {s.nazwa}
          </Link>
        ))}
      </nav>

      <p className="opis-strategii">{strategia.opis}</p>

      <Suspense fallback={<div className="filtry">Wczytuję filtry…</div>}>
        <PanelFiltrow
          wartosci={filtry}
          rynki={wartosci(wTypie, "Rynek")}
          sektory={wartosci(wTypie, "Sektor")}
          liczbaWynikow={ranking.length}
          liczbaWszystkich={wTypie.length}
          sciezka="/strategie"
          adresCzysty={`/strategie?s=${strategia.klucz}`}
          pokazSortowanie={false}
        />
      </Suspense>

      <div className={wybrana ? "uklad-z-panelem" : undefined}>
        <div className="card" style={{ marginTop: 12 }}>
          <div className="cardhead">
            <h2>Ranking</h2>
            <em>
              {ranking.length.toLocaleString("pl-PL")} ocenionych spółek · najwyższy
              wynik {najlepszyWynik} / {strategia.maks}
              {sortKolumna ? " · posortowano po kolumnie" : ""}
            </em>
          </div>
          {ranking.length > 0 ? (
            <TabelaStrategii
              wiersze={czolo}
              strategia={strategia}
              sortKolumna={sortKolumna}
              sortRosnaco={sortRosnaco}
              link={(t) => adres({ wybrana: t })}
              linkWykres={(t) => adres({ wykres: t })}
              wybrany={wybranyTicker}
            />
          ) : (
            <p className="pusto" style={{ padding: "18px 0" }}>
              Żadna spółka nie ma tu policzonego wyniku. Albo filtry są zbyt
              wąskie, albo ta migawka powstała przed dodaniem tej strategii —
              w tym drugim przypadku wyniki pojawią się po najbliższym
              codziennym skanie i nic nie trzeba robić.
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

      <footer>
        Pokazane pierwsze {ILE} pozycji rankingu. Filtry zawężają zestaw, ZANIM
        powstanie ranking — dostajesz {ILE} najlepszych spośród wybranych spółek,
        a nie najlepszych na świecie z przypadkowym trafieniem w Twój filtr.
        Kliknięcie w nazwę spółki otwiera profil obok listy, ikona obok — wykres
        na prawie całym ekranie. Kliknięcie w nagłówek kolumny sortuje te {ILE}{" "}
        spółek; ponowne odwraca kierunek. Wyniki liczone podczas codziennego
        skanu, maksimum wyznaczone empirycznie.
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
