"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Wykres z TradingView.
 *
 * DLACZEGO NIE WŁASNY: rysowanie świec to najmniejszy problem — kłopotem są
 * DANE. Migawka trzyma stan z jednego dnia, nie historię notowań, więc własny
 * wykres wymagałby osobnego pobierania OHLC dla każdej spółki i utrzymywania
 * tego w czasie. Widget TradingView przynosi własne dane, obsługuje wszystkie
 * giełdy z naszego uniwersum i ma gotowe wskaźniki, o które prosiłeś.
 *
 * Wskaźniki włączone na starcie:
 *   - chmura Ichimoku,
 *   - średnia krocząca,
 *   - punkty zwrotne (klasyczne wsparcia i opory).
 *
 * Interwał przełącza się przez przemontowanie widgetu — TradingView nie
 * pozwala zmienić go po utworzeniu.
 */
const INTERWALY = [
  { klucz: "D", etykieta: "1D" },
  { klucz: "W", etykieta: "1W" },
  { klucz: "M", etykieta: "1M" },
];

export default function Wykres({
  symbol,
  pelnyEkran = false,
}: {
  symbol: string;
  /** Na pełnym ekranie ramka rośnie do wysokości okna. */
  pelnyEkran?: boolean;
}) {
  const kontener = useRef<HTMLDivElement>(null);
  const [interwal, setInterwal] = useState("D");

  useEffect(() => {
    const el = kontener.current;
    if (!el || !symbol) return;

    // Motyw czytamy w chwili montowania: widget nie umie go zmienić w locie,
    // a przemontowywanie przy każdym przełączeniu trybu byłoby nachalne.
    const ciemny =
      document.documentElement.getAttribute("data-theme") === "dark" ||
      (!document.documentElement.getAttribute("data-theme") &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);

    el.innerHTML = "";
    const skrypt = document.createElement("script");
    skrypt.src =
      "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    skrypt.async = true;
    skrypt.innerHTML = JSON.stringify({
      symbol,
      interval: interwal,
      timezone: "Europe/Warsaw",
      theme: ciemny ? "dark" : "light",
      style: "1",
      locale: "pl",
      allow_symbol_change: false,
      hide_side_toolbar: true,
      withdateranges: true,
      studies: [
        "IchimokuCloud@tv-basicstudies",
        "MASimple@tv-basicstudies",
        "PivotPointsStandard@tv-basicstudies",
      ],
      autosize: true,
    });
    el.appendChild(skrypt);

    return () => {
      el.innerHTML = "";
    };
  }, [symbol, interwal]);

  if (!symbol) {
    return (
      <div className="wykres-brak">
        Nie udało się ustalić symbolu giełdowego dla tego instrumentu, więc
        wykres nie zostanie wczytany.
      </div>
    );
  }

  return (
    <div className={pelnyEkran ? "wykres wykres-pelny" : "wykres"}>
      <div className="wykres-pasek">
        <span className="wykres-symbol">{symbol}</span>
        <div className="wykres-interwaly">
          {INTERWALY.map((i) => (
            <button
              key={i.klucz}
              onClick={() => setInterwal(i.klucz)}
              className={i.klucz === interwal ? "aktywny" : undefined}
              aria-pressed={i.klucz === interwal}
            >
              {i.etykieta}
            </button>
          ))}
        </div>
      </div>
      <div className="wykres-ramka" ref={kontener} />
      <p className="wykres-stopka">
        Wykres i dane notowań: TradingView. Widoczne: chmura Ichimoku, średnia
        krocząca i punkty zwrotne (wsparcia i opory).
      </p>
    </div>
  );
}
