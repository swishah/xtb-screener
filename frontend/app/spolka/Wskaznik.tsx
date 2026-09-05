"use client";

import { useState } from "react";
import type { Ocena } from "@/lib/wskazniki";

/**
 * Jeden wskaźnik: nazwa, wartość, krótka ocena i pytajnik z wyjaśnieniem.
 *
 * Układ wynika wprost z wymagania: najpierw KRÓTKA OCENA jednym słowem
 * („dobrze”, „przeciętnie”, „słabo”), a dopiero za nią pytajnik z pełnym
 * wyjaśnieniem i porównaniem do mediany branży. Dzięki temu da się przelecieć
 * wzrokiem całą listę i zatrzymać tylko tam, gdzie coś zwraca uwagę.
 *
 * Komponent kliencki wyłącznie z powodu rozwijania wyjaśnienia — cała reszta
 * profilu renderuje się na serwerze.
 */
export default function Wskaznik({
  etykieta,
  wartosc,
  ocena,
  opis,
  porownanie,
}: {
  etykieta: string;
  wartosc: string;
  ocena: Ocena;
  opis: string;
  porownanie: string | null;
}) {
  const [otwarte, setOtwarte] = useState(false);
  const brak = wartosc === "BRAK";

  return (
    <div className={`wsk${otwarte ? " wsk-otwarty" : ""}`}>
      <div className="wsk-glowna">
        <span className="wsk-etykieta">{etykieta}</span>
        <span className={`wsk-wartosc${brak ? " brak" : ""}`}>{wartosc}</span>
        {ocena && <span className={`wsk-ocena ocena-${ocena.replace("ę", "e")}`}>{ocena}</span>}
        <button
          className="wsk-pytajnik"
          onClick={() => setOtwarte((o) => !o)}
          aria-expanded={otwarte}
          aria-label={`Wyjaśnij: ${etykieta}`}
          title="Co to znaczy?"
        >
          ?
        </button>
      </div>
      {otwarte && (
        <div className="wsk-opis">
          <p>{opis}</p>
          {porownanie && <p className="wsk-porownanie">{porownanie}</p>}
        </div>
      )}
    </div>
  );
}
