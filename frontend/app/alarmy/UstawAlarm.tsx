"use client";

import { useMemo, useRef, useState } from "react";
import { dodaj } from "./akcje";

/**
 * Ustawianie alarmu przez przeciągnięcie linii po wykresie.
 *
 * DLACZEGO WŁASNY WYKRES, A NIE TRADINGVIEW. Wykres TradingView jest osadzony
 * jako <iframe> z obcej domeny. Nie widzimy jego skali cenowej ani tego, czy
 * użytkownik przed chwilą nie przewinął kółkiem albo nie przełączył skali na
 * logarytmiczną — więc przeliczenie pozycji linii na cenę byłoby zgadywaniem.
 * Błąd objawiłby się alarmem na cenie, której nikt nie wskazał, i to jest
 * najgorszy możliwy rodzaj błędu w narzędziu do pieniędzy. Tutaj rysujemy
 * sami, więc przelicznik jest nasz i dokładny co do grosza.
 *
 * TRZY SPOSOBY USTAWIENIA TEJ SAMEJ WARTOŚCI, celowo:
 * 1. przeciągnięcie linii — szybkie i poglądowe,
 * 2. pole liczbowe — bo trafienie palcem w konkretną cenę na telefonie jest
 *    loterią, a to narzędzie ma działać na telefonie,
 * 3. strzałki na klawiaturze — dla dostępności i precyzji.
 *
 * Kierunek alarmu wynika z POŁOŻENIA linii względem kursu: wyżej znaczy
 * „powiadom, gdy wzrośnie", niżej — „gdy spadnie". Bez dodatkowego przełącznika,
 * bo gest już to powiedział.
 */

const SZER = 600;
const WYS = 200;
const MARGINES = 8;

type Punkt = { dzien: string; cena: number };

export default function UstawAlarm({
  ticker,
  nazwa,
  cena,
  min52,
  max52,
  waluta,
  punkty,
  progiIstniejace,
  powrot,
}: {
  ticker: string;
  nazwa: string;
  cena: number;
  min52: number | null;
  max52: number | null;
  waluta: string;
  punkty: Punkt[];
  /** Ceny alarmów już ustawionych — rysujemy je, żeby nie dublować. */
  progiIstniejace: number[];
  /** Dokąd wrócić po zapisaniu; podaje strona, bo komponent nie zna adresu. */
  powrot: string;
}) {
  // Oś obejmuje zakres 52-tygodniowy, bieżący kurs i całą ścieżkę, plus
  // margines — inaczej linii nie dałoby się postawić tam, gdzie widać wykres.
  const { dol, gora } = useMemo(() => {
    const wartosci = [cena, ...punkty.map((p) => p.cena), ...progiIstniejace];
    if (min52 && min52 > 0) wartosci.push(min52);
    if (max52 && max52 > 0) wartosci.push(max52);
    const min = Math.min(...wartosci);
    const max = Math.max(...wartosci);
    const zapas = Math.max((max - min) * 0.08, max * 0.02);
    return { dol: Math.max(0, min - zapas), gora: max + zapas };
  }, [cena, punkty, min52, max52, progiIstniejace]);

  const [prog, setProg] = useState<number>(() =>
    // Domyślnie 5% powyżej kursu: alarm najczęściej stawia się „w górę",
    // a linia leżąca dokładnie na kursie wyglądałaby na zepsutą.
    Math.round(cena * 1.05 * 100) / 100,
  );
  const [tekst, setTekst] = useState<string>(
    String(Math.round(cena * 1.05 * 100) / 100),
  );
  const [ciagnie, setCiagnie] = useState(false);
  const ramka = useRef<SVGSVGElement | null>(null);

  const kierunek = prog >= cena ? "powyzej" : "ponizej";

  function naY(wartosc: number): number {
    const udzial = (gora - wartosc) / (gora - dol || 1);
    return MARGINES + udzial * (WYS - 2 * MARGINES);
  }

  /** Piksel ekranu -> cena. Liczone z prostokąta elementu, więc skalowanie
      SVG przez CSS niczego nie psuje. */
  function zZdarzenia(klientY: number): number {
    const el = ramka.current;
    if (!el) return prog;
    const r = el.getBoundingClientRect();
    const udzial = Math.min(1, Math.max(0, (klientY - r.top) / r.height));
    const wartosc = gora - udzial * (gora - dol);
    return Math.round(wartosc * 100) / 100;
  }

  function ustaw(wartosc: number) {
    const zaokraglona = Math.round(Math.max(0.01, wartosc) * 100) / 100;
    setProg(zaokraglona);
    setTekst(String(zaokraglona));
  }

  const krok = Math.max(0.01, Math.round(((gora - dol) / 100) * 100) / 100);

  const sciezka = useMemo(() => {
    if (punkty.length < 2) return "";
    const krokX = (SZER - 2 * MARGINES) / (punkty.length - 1);
    return punkty
      .map(
        (p, i) =>
          `${i === 0 ? "M" : "L"}${(MARGINES + i * krokX).toFixed(1)},${naY(p.cena).toFixed(1)}`,
      )
      .join(" ");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [punkty, dol, gora]);

  const formatuj = (w: number) =>
    w.toLocaleString("pl-PL", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  const roznica = cena > 0 ? ((prog - cena) / cena) * 100 : 0;

  return (
    <div className="alarm-ustawianie">
      <svg
        ref={ramka}
        className={`alarm-wykres${ciagnie ? " ciagnie" : ""}`}
        viewBox={`0 0 ${SZER} ${WYS}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Wykres ceny ${ticker} z linią alarmu`}
        onPointerDown={(e) => {
          (e.target as Element).setPointerCapture?.(e.pointerId);
          setCiagnie(true);
          ustaw(zZdarzenia(e.clientY));
        }}
        onPointerMove={(e) => {
          if (ciagnie) ustaw(zZdarzenia(e.clientY));
        }}
        onPointerUp={() => setCiagnie(false)}
        onPointerCancel={() => setCiagnie(false)}
      >
        {/* Ścieżka ceny z naszych migawek */}
        {sciezka && <path className="alarm-sciezka" d={sciezka} />}

        {/* Bieżący kurs */}
        <line
          className="alarm-kurs"
          x1={0}
          x2={SZER}
          y1={naY(cena)}
          y2={naY(cena)}
        />
        <text className="alarm-etykieta-kurs" x={6} y={naY(cena) - 6}>
          kurs {formatuj(cena)}
        </text>

        {/* Alarmy już ustawione — żeby nie stawiać drugiego w tym samym miejscu */}
        {progiIstniejace.map((p) => (
          <line
            key={p}
            className="alarm-istniejacy"
            x1={0}
            x2={SZER}
            y1={naY(p)}
            y2={naY(p)}
          />
        ))}

        {/* Linia alarmu — ta, którą się przeciąga */}
        <line
          className="alarm-linia"
          x1={0}
          x2={SZER}
          y1={naY(prog)}
          y2={naY(prog)}
        />
        <rect
          className="alarm-uchwyt"
          x={SZER - 74}
          y={naY(prog) - 11}
          width={68}
          height={22}
          rx={5}
          tabIndex={0}
          role="slider"
          aria-label="Cena alarmu"
          aria-valuenow={prog}
          aria-valuemin={Math.round(dol * 100) / 100}
          aria-valuemax={Math.round(gora * 100) / 100}
          aria-valuetext={`${formatuj(prog)} ${waluta}`}
          onKeyDown={(e) => {
            const duzy = e.key === "PageUp" || e.key === "PageDown";
            const wGore = e.key === "ArrowUp" || e.key === "PageUp";
            const wDol = e.key === "ArrowDown" || e.key === "PageDown";
            if (!wGore && !wDol) return;
            e.preventDefault();
            const zmiana = (duzy ? krok * 10 : krok) * (wGore ? 1 : -1);
            ustaw(prog + zmiana);
          }}
        />
        <text
          className="alarm-etykieta-prog"
          x={SZER - 40}
          y={naY(prog) + 4}
          textAnchor="middle"
        >
          {formatuj(prog)}
        </text>
      </svg>

      <form action={dodaj} className="alarm-formularz">
        <input type="hidden" name="ticker" value={ticker} />
        <input type="hidden" name="nazwa" value={nazwa} />
        <input type="hidden" name="waluta" value={waluta} />
        <input type="hidden" name="kierunek" value={kierunek} />
        <input type="hidden" name="powrot" value={powrot} />

        <label>
          <span>Cena alarmu ({waluta || "waluta notowania"})</span>
          <input
            type="number"
            name="cena"
            step="0.01"
            min="0.01"
            value={tekst}
            onChange={(e) => {
              setTekst(e.target.value);
              const n = Number(e.target.value);
              if (Number.isFinite(n) && n > 0) setProg(n);
            }}
            required
          />
        </label>

        <p className="alarm-podsumowanie">
          Powiadom, gdy kurs{" "}
          <b>{kierunek === "powyzej" ? "wzrośnie powyżej" : "spadnie poniżej"}</b>{" "}
          <b>
            {formatuj(prog)} {waluta}
          </b>{" "}
          <span className="brak">
            ({roznica > 0 ? "+" : ""}
            {roznica.toLocaleString("pl-PL", { maximumFractionDigits: 1 })}% od
            dzisiejszego kursu)
          </span>
        </p>

        <button type="submit">Ustaw alarm</button>
      </form>
    </div>
  );
}
