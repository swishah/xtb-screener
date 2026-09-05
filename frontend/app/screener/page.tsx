import Link from "next/link";
import { Suspense } from "react";
import Pasek from "../Pasek";
import Tabela from "../Tabela";
import PanelFiltrow from "./Filtry";
import PanelSpolki from "../PanelSpolki";
import WykresPelny from "../spolka/WykresPelny";
import { migawkaBezpieczna } from "@/lib/dane";
import { newsySpolki } from "@/lib/newsy";
import { symbolTradingView } from "@/lib/tradingview";
import { FILTRY_DOMYSLNE, filtruj, wartosci, type Filtry } from "@/lib/filtry";

export const dynamic = "force-dynamic";

const LIMIT = 200;

/** Liczba z adresu URL; przy śmieciach wraca wartość domyślna. */
function num(wejscie: string | undefined, domyslna: number): number {
  if (wejscie === undefined) return domyslna;
  const n = Number(wejscie);
  return Number.isFinite(n) ? n : domyslna;
}

export default async function Screener({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };

  const filtry: Filtry = {
    typ: jeden("typ") ?? FILTRY_DOMYSLNE.typ,
    rynek: jeden("rynek") ?? "",
    sektor: jeden("sektor") ?? "",
    minScore: num(jeden("minScore"), 0),
    maxAth: num(jeden("maxAth"), 0),
    maxFlag: num(jeden("maxFlag"), 10),
    szukaj: jeden("szukaj") ?? "",
    sortuj: jeden("sortuj") ?? FILTRY_DOMYSLNE.sortuj,
  };

  const { data, tryb, instrumenty, blad } = await migawkaBezpieczna();

  // Listy wyboru budujemy z instrumentów danego TYPU, ale bez pozostałych
  // filtrów — inaczej wybranie sektora wycinałoby z listy rynki i nie dałoby
  // się już wrócić.
  const wTypie = filtry.typ ? instrumenty.filter((i) => i.Typ === filtry.typ) : instrumenty;

  const dopasowane = filtruj(instrumenty, filtry);
  const widoczne = dopasowane.slice(0, LIMIT);

  // --- panel boczny -------------------------------------------------------
  const wybranyTicker = (jeden("wybrana") ?? "").toUpperCase();
  const wybrana = wybranyTicker
    ? instrumenty.find((i) => String(i.Ticker ?? "").toUpperCase() === wybranyTicker)
    : undefined;
  const newsy = wybrana
    ? await newsySpolki(String(wybrana.Ticker), String(wybrana.Nazwa ?? ""))
    : [];

  /**
   * Adres zachowujący wszystkie filtry i zmieniający tylko jeden parametr.
   * Dzięki temu otwarcie wykresu nie gubi wybranej spółki, a zamknięcie
   * panelu nie gubi wykresu.
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
    return s ? `/screener?${s}` : "/screener";
  }

  const wykresTicker = (jeden("wykres") ?? "").toUpperCase();
  const doWykresu = wykresTicker
    ? instrumenty.find((i) => String(i.Ticker ?? "").toUpperCase() === wykresTicker)
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
        <h2 style={{ fontSize: "1.15rem" }}>Screener</h2>
        <em>migawka z {data}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <Suspense fallback={<div className="filtry">Wczytuję filtry…</div>}>
        <PanelFiltrow
          wartosci={filtry}
          rynki={wartosci(wTypie, "Rynek")}
          sektory={wartosci(wTypie, "Sektor")}
          liczbaWynikow={dopasowane.length}
          liczbaWszystkich={wTypie.length}
        />
      </Suspense>

      <div className={wybrana ? "uklad-z-panelem" : undefined}>
        <div className="card" style={{ marginTop: 12 }}>
          <Tabela
            wiersze={widoczne}
            link={(t) => adres({ wybrana: t })}
            linkWykres={(t) => adres({ wykres: t })}
            wybrany={wybranyTicker}
          />
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
        {dopasowane.length > LIMIT ? (
          <>
            Pokazane pierwsze {LIMIT} z {dopasowane.length.toLocaleString("pl-PL")}{" "}
            dopasowań — zawęź filtry, żeby zobaczyć resztę.
          </>
        ) : (
          <>Wszystkie dopasowania mieszczą się na liście.</>
        )}{" "}
        Kliknij spółkę, żeby zobaczyć wykres i pełne dane obok listy. Wskaźniki
        liczone podczas codziennego skanu; „BRAK” znaczy, że Yahoo nie podało
        danej wartości.
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
