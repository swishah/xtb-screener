"use client";

import { useState } from "react";

/**
 * Pasek górny: nazwa, data migawki, przełącznik motywu i pytajnik.
 *
 * Komponent kliencki, bo obsługuje kliknięcia. Wszystko poniżej (dane, tabele)
 * zostaje po stronie serwera — do przeglądarki nie leci ani jeden wiersz
 * z bazy więcej, niż widać na ekranie.
 */
export default function Pasek({
  dataMigawki,
  tryb,
}: {
  dataMigawki: string;
  tryb: "zdalny" | "lokalny";
}) {
  const [pomoc, setPomoc] = useState(false);

  function przelaczMotyw() {
    const root = document.documentElement;
    const systemCiemny = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const teraz = root.getAttribute("data-theme") ?? (systemCiemny ? "dark" : "light");
    const nowy = teraz === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", nowy);
    try {
      localStorage.setItem("motyw", nowy);
    } catch {
      /* okno prywatne — trudno, motyw po prostu się nie zapamięta */
    }
  }

  return (
    <>
      <div className="bar">
        <h1 className="brand">XTB Screener</h1>
        <span className="stamp">{dataMigawki}</span>
        <div className="tools">
          <button
            className="icobtn"
            onClick={przelaczMotyw}
            aria-label="Przełącz tryb jasny i ciemny"
            title="Tryb jasny / ciemny"
          >
            <svg className="ico-moon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
            </svg>
            <svg className="ico-sun" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
            </svg>
          </button>
          <button
            className="icobtn"
            onClick={() => setPomoc((p) => !p)}
            aria-expanded={pomoc}
            title="Skąd te dane?"
          >
            ?
          </button>
        </div>
      </div>

      {pomoc && (
        <div className="panel">
          <p style={{ margin: "0 0 8px" }}>
            <b>Dane:</b> Yahoo Finance, pobierane raz dziennie po zamknięciu rynków
            amerykańskich.
          </p>
          <p style={{ margin: "0 0 8px" }}>
            <b>Uniwersum:</b> składy głównych indeksów plus popularne ETF-y UCITS.
            Przed transakcją sprawdź dostępność instrumentu w platformie XTB.
          </p>
          <p style={{ margin: 0 }}>
            <b>Buy Score:</b> suma dziewięciu sygnałów technicznych i
            fundamentalnych — im wyżej, tym więcej z nich zagrało naraz.{" "}
            <b>Czerwone flagi</b> to ostrzeżenia o kondycji spółki; zero flag nie
            znaczy „dobra inwestycja", tylko „nie znaleziono ostrzeżeń".
          </p>
        </div>
      )}

      {tryb === "lokalny" && (
        <div className="alert">
          <b>Tryb zapasowy — lokalna kopia bazy.</b> Dane nie są odświeżane, bo
          brakuje zmiennych <code>TURSO_DATABASE_URL</code> i{" "}
          <code>TURSO_AUTH_TOKEN</code>. Normalne przy pracy na własnym
          komputerze; na produkcji oznacza błąd konfiguracji.
        </div>
      )}
    </>
  );
}
