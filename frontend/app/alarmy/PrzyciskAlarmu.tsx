"use client";

import { useState } from "react";
import { dodaj } from "./akcje";

/**
 * Alarm cenowy dostępny WPROST przy wykresie TradingView.
 *
 * Wykresu nie da się dotknąć — siedzi w ramce z obcej domeny — ale panel obok
 * niego już tak. Dzięki temu nie trzeba zamykać wykresu, wracać na profil
 * i szukać sekcji alarmu: patrzysz na notowanie i od razu stawiasz próg.
 *
 * WERYFIKACJA INSTRUMENTU I WALUTY JEST TU CZĘŚCIĄ FUNKCJI, nie ozdobą.
 * Panel pokazuje ticker, nazwę, walutę notowania i bieżący kurs, bo alarm
 * ustawiony na spółce notowanej w innej walucie, niż się komuś wydaje, jest
 * gorszy niż brak alarmu. Najgroźniejszy przypadek to Londyn: Yahoo notuje
 * LSE w PENSACH (GBp), więc kurs „1563" to 15,63 funta. Ktoś, kto myśli
 * w funtach, ustawiłby próg 100× za nisko i alarm odpaliłby natychmiast.
 * Dlatego przy GBp panel mówi o tym wprost.
 *
 * KROKI SĄ DOPASOWANE DO CENY. Użytkownik prosił o „+/- 1 i 10", i tak jest
 * przy normalnych kursach — ale przy spółce po 2 EUR skok o 1 to 50% ceny,
 * więc krok schodzi do 0,10. Przyciski pokazują swoją realną wartość, żeby
 * nigdy nie było niespodzianki.
 */

/** Waluty notowane w setnych częściach jednostki — pułapka przy alarmach. */
const PODJEDNOSTKI: Record<string, string> = {
  GBp: "pensach (100 pensów = 1 funt)",
  GBX: "pensach (100 pensów = 1 funt)",
  ZAc: "centach randa",
  ILA: "agorach (100 agor = 1 szekel)",
};

function kroki(cena: number): [number, number] {
  if (cena >= 20) return [1, 10];
  if (cena >= 2) return [0.1, 1];
  return [0.01, 0.1];
}

export default function PrzyciskAlarmu({
  ticker,
  nazwa,
  cena,
  waluta,
  powrot,
}: {
  ticker: string;
  nazwa: string;
  cena: number;
  waluta: string;
  powrot: string;
}) {
  const [otwarty, setOtwarty] = useState(false);
  const [prog, setProg] = useState(() => Math.round(cena * 1.05 * 100) / 100);

  const [maly, duzy] = kroki(cena);
  const kierunek = prog >= cena ? "powyzej" : "ponizej";
  const roznica = cena > 0 ? ((prog - cena) / cena) * 100 : 0;
  const podjednostka = PODJEDNOSTKI[waluta];

  const formatuj = (w: number) =>
    w.toLocaleString("pl-PL", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  function przesun(o: number) {
    setProg((p) => Math.round(Math.max(0.01, p + o) * 100) / 100);
  }

  return (
    <div className="alarm-przy-wykresie">
      <button
        type="button"
        className={`btn-alarm${otwarty ? " aktywny" : ""}`}
        onClick={() => setOtwarty((w) => !w)}
        aria-expanded={otwarty}
      >
        Alarm cenowy
      </button>

      {otwarty && (
        <div className="alarm-panelik" role="dialog" aria-label="Ustaw alarm cenowy">
          {/* Weryfikacja instrumentu — na co dokładnie stawiamy alarm */}
          <div className="alarm-panelik-glowa">
            <strong>{ticker}</strong>
            <span className="brak">{nazwa}</span>
          </div>

          <div className="alarm-panelik-kurs">
            <span className="brak">kurs</span>
            <b className="n">{formatuj(cena)}</b>
            <span className="alarm-waluta">{waluta || "?"}</span>
          </div>

          {podjednostka && (
            <p className="alarm-ostrzezenie">
              Uwaga: ten instrument notowany jest w {podjednostka}. Podaj próg
              w tej samej jednostce, w jakiej widzisz kurs powyżej.
            </p>
          )}

          <div className="alarm-kroki">
            <button type="button" onClick={() => przesun(-duzy)}>
              −{duzy}
            </button>
            <button type="button" onClick={() => przesun(-maly)}>
              −{maly}
            </button>
            <input
              type="number"
              step={maly}
              min={0.01}
              value={prog}
              onChange={(e) => {
                const n = Number(e.target.value);
                if (Number.isFinite(n)) setProg(n);
              }}
              aria-label={`Cena alarmu w ${waluta || "walucie notowania"}`}
            />
            <button type="button" onClick={() => przesun(maly)}>
              +{maly}
            </button>
            <button type="button" onClick={() => przesun(duzy)}>
              +{duzy}
            </button>
          </div>

          <p className="alarm-panelik-podsumowanie">
            {kierunek === "powyzej" ? "Wzrost powyżej" : "Spadek poniżej"}{" "}
            <b>
              {formatuj(prog)} {waluta}
            </b>
            <span className="brak">
              {" "}
              ({roznica > 0 ? "+" : ""}
              {roznica.toLocaleString("pl-PL", { maximumFractionDigits: 1 })}%)
            </span>
          </p>

          <form action={dodaj}>
            <input type="hidden" name="ticker" value={ticker} />
            <input type="hidden" name="nazwa" value={nazwa} />
            <input type="hidden" name="waluta" value={waluta} />
            <input type="hidden" name="kierunek" value={kierunek} />
            <input type="hidden" name="cena" value={prog} />
            <input type="hidden" name="powrot" value={powrot} />
            <button type="submit" className="btn-alarm-zapisz">
              Ustaw alarm
            </button>
          </form>

          <p className="alarm-panelik-stopka">
            Sprawdza go codzienny skan (pon–pt, 22:30 UTC), po maksimum
            i minimum dnia. To nie jest alert w czasie rzeczywistym.
          </p>
        </div>
      )}
    </div>
  );
}
