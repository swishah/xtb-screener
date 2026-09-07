/**
 * Krzywa skumulowanego zwrotu — inline SVG, bez biblioteki wykresów.
 *
 * Komponent SERWEROWY: to statyczny obrazek liczony z gotowych punktów, więc
 * do przeglądarki nie leci ani bajt JavaScriptu na jego obsługę. Ta sama
 * zasada co przy histogramie w Globalnym przeglądzie — kilkanaście punktów
 * nie jest warte kolejnej zależności do utrzymania przez lata.
 */
export default function Krzywa({
  punkty,
}: {
  punkty: { dzien: string; wartosc: number }[];
}) {
  if (punkty.length < 2) {
    return (
      <p className="pusto">
        Za mało okien, żeby narysować krzywą (potrzeba co najmniej dwóch).
      </p>
    );
  }

  const SZER = 720;
  const WYS = 190;
  const MARG = { gora: 12, dol: 26, lewo: 46, prawo: 12 };

  const wartosci = punkty.map((p) => p.wartosc);
  // Zero zawsze mieści się w skali — bez tego krzywa w całości pod kreską
  // wyglądałaby jak wzrost, bo oś zaczynałaby się od najgorszej wartości.
  const min = Math.min(0, ...wartosci);
  const maks = Math.max(0, ...wartosci);
  const rozpietosc = maks - min || 1;

  const x = (i: number) =>
    MARG.lewo +
    (i / (punkty.length - 1)) * (SZER - MARG.lewo - MARG.prawo);
  const y = (w: number) =>
    MARG.gora + (1 - (w - min) / rozpietosc) * (WYS - MARG.gora - MARG.dol);

  const sciezka = punkty
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.wartosc).toFixed(1)}`)
    .join(" ");
  const yZera = y(0);
  const ostatnia = punkty[punkty.length - 1].wartosc;

  return (
    <div className="scroll">
      <svg
        viewBox={`0 0 ${SZER} ${WYS}`}
        className="krzywa"
        role="img"
        aria-label={`Skumulowany zwrot: ${ostatnia.toFixed(1)}% po ${punkty.length} oknach`}
      >
        {/* Linia zera — punkt odniesienia „ani zysku, ani straty". */}
        <line
          x1={MARG.lewo}
          x2={SZER - MARG.prawo}
          y1={yZera}
          y2={yZera}
          className="krzywa-zero"
        />
        <text x={4} y={yZera + 4} className="krzywa-opis">
          0%
        </text>
        <text x={4} y={y(maks) + 4} className="krzywa-opis">
          {maks.toFixed(0)}%
        </text>
        <text x={4} y={y(min) + 4} className="krzywa-opis">
          {min.toFixed(0)}%
        </text>

        <path
          d={sciezka}
          className={ostatnia < 0 ? "krzywa-linia spadek" : "krzywa-linia"}
        />

        <text x={MARG.lewo} y={WYS - 6} className="krzywa-opis">
          {punkty[0].dzien}
        </text>
        <text
          x={SZER - MARG.prawo}
          y={WYS - 6}
          textAnchor="end"
          className="krzywa-opis"
        >
          {punkty[punkty.length - 1].dzien}
        </text>
      </svg>
    </div>
  );
}
