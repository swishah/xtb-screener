import Link from "next/link";
import Pasek from "../Pasek";
import ListaAlarmow from "./Lista";
import { alarmyUzytkownika, LIMIT_ALARMOW } from "@/lib/alarmy";
import { migawkaBezpieczna } from "@/lib/dane";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

export default async function Alarmy() {
  const uzytkownik = await wymagajZalogowania();
  const { data, tryb } = await migawkaBezpieczna();
  const alarmy = await alarmyUzytkownika(uzytkownik.id);
  const wyzwolone = alarmy.filter((a) => a.wyzwolony).length;
  const czekajace = alarmy.length - wyzwolone;

  return (
    <main className="wrap">
      <Pasek dataMigawki={data} tryb={tryb} />

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Alarmy cenowe</h2>
        <em>
          {czekajace} {czekajace === 1 ? "czeka" : "czeka"}
          {wyzwolone > 0 ? ` · ${wyzwolone} zadziałało` : ""}
        </em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <div className="card" style={{ marginTop: 12, padding: "4px 20px 12px" }}>
        <ListaAlarmow alarmy={alarmy} powrot="/alarmy" />
      </div>

      <footer>
        Alarmy sprawdza codzienny skan (poniedziałek–piątek, 22:30 UTC), więc to
        NIE jest alert w czasie rzeczywistym. Skan porównuje jednak maksimum
        i minimum dnia, a nie cenę zamknięcia — przebicie progu w ciągu dnia,
        które do wieczora się cofnęło, też zostanie złapane. Alarm, który
        zadziałał, zostaje na liście z datą i ceną; możesz go wznowić albo
        usunąć. Limit na konto: {LIMIT_ALARMOW}.
      </footer>
    </main>
  );
}
