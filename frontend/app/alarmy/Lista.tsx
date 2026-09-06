import Link from "next/link";
import { usun, wznow } from "./akcje";
import type { Alarm } from "@/lib/alarmy";

/**
 * Lista alarmów. Komponent serwerowy — kasowanie i wznawianie to zwykłe
 * formularze z akcją serwerową, więc działa bez JavaScriptu.
 *
 * Alarm wyzwolony NIE ZNIKA sam. Zostaje na liście z datą i ceną, przy której
 * zadziałał, dopóki go nie skasujesz albo nie wznowisz. Gdyby znikał, jedyną
 * informacją o zadziałaniu byłoby powiadomienie — a to zakłada, że kanał
 * powiadomień jest skonfigurowany i że wiadomość dotarła.
 */
export default function ListaAlarmow({
  alarmy,
  powrot,
  pokazTicker = true,
}: {
  alarmy: Alarm[];
  powrot: string;
  pokazTicker?: boolean;
}) {
  if (alarmy.length === 0) {
    return (
      <p className="pusto">
        Nie masz jeszcze żadnych alarmów. Wejdź na profil spółki i przeciągnij
        linię na wybraną cenę.
      </p>
    );
  }

  const formatuj = (w: number) =>
    w.toLocaleString("pl-PL", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  return (
    <ul className="lista-alarmow">
      {alarmy.map((a) => (
        <li key={a.id} className={a.wyzwolony ? "alarm-wyzwolony" : undefined}>
          <div className="alarm-opis">
            {pokazTicker && (
              <Link
                className="alarm-ticker"
                href={`/spolka/${encodeURIComponent(a.ticker)}`}
              >
                {a.ticker}
                <small>{a.nazwa}</small>
              </Link>
            )}
            <span className="alarm-warunek">
              {a.kierunek === "powyzej" ? "wzrost powyżej" : "spadek poniżej"}{" "}
              <b className="n">
                {formatuj(a.cena)} {a.waluta}
              </b>
            </span>
            {a.wyzwolony ? (
              <span className="alarm-znacznik">
                zadziałał {a.wyzwolony}
                {a.cenaWyzwolenia !== null
                  ? ` przy ${formatuj(a.cenaWyzwolenia)} ${a.waluta}`
                  : ""}
              </span>
            ) : (
              <span className="brak alarm-znacznik">czeka</span>
            )}
          </div>

          <div className="alarm-przyciski">
            {a.wyzwolony && (
              <form action={wznow}>
                <input type="hidden" name="id" value={a.id} />
                <input type="hidden" name="powrot" value={powrot} />
                <button type="submit" className="btn-drobny">
                  Wznów
                </button>
              </form>
            )}
            <form action={usun}>
              <input type="hidden" name="id" value={a.id} />
              <input type="hidden" name="powrot" value={powrot} />
              <button type="submit" className="btn-drobny btn-usun">
                Usuń
              </button>
            </form>
          </div>
        </li>
      ))}
    </ul>
  );
}
