import Link from "next/link";
import Pasek from "../Pasek";
import { anuluj } from "./akcje";
import { migawkaBezpieczna } from "@/lib/dane";
import {
  ETYKIETY_STANU,
  OPISY_STANU,
  dniPlanow,
  planyDnia,
  planyOtwarte,
  planyZamkniete,
  podsumowanie,
  polozenie,
  type Plan,
} from "@/lib/plany";
import { wymagajZalogowania } from "@/lib/sesja";

export const dynamic = "force-dynamic";

const KOMUNIKATY: Record<string, string> = {
  anulowany: "Plan anulowany. Nie wchodzi do statystyki skuteczności.",
  nieotwarty:
    "Ten plan jest już rozliczony — anulowanie go nic by nie zmieniło, a wynik z przeszłości ma zostać nietknięty.",
  blad: "Nie udało się anulować planu.",
};

function lb(w: number | null | undefined, cyfry = 2): string {
  if (w === null || w === undefined || !Number.isFinite(w)) return "—";
  return w.toLocaleString("pl-PL", {
    minimumFractionDigits: cyfry,
    maximumFractionDigits: cyfry,
  });
}

/** Cena bywa notowana w setnych częściach jednostki — wtedy dwie cyfry to za mało. */
function cyfryCeny(wartosc: number): number {
  return Math.abs(wartosc) < 10 ? 3 : 2;
}

function Pewnosc({ ile }: { ile: number | null }) {
  if (ile === null) return null;
  return (
    <span className="pewnosc" title={`Pewność ${ile} z 5`}>
      {"●".repeat(ile)}
      <span className="pewnosc-puste">{"●".repeat(Math.max(0, 5 - ile))}</span>
    </span>
  );
}

function KartaPlanu({
  plan,
  cena,
  nazwa,
  waluta,
}: {
  plan: Plan;
  cena: number | null;
  nazwa: string;
  waluta: string;
}) {
  const c = cyfryCeny(plan.wejscieDo);
  const gdzie = polozenie(plan, cena);
  const otwarty = plan.stan === "czeka" || plan.stan === "aktywny";
  const uwagi = plan.uwagi
    .split(";")
    .map((u) => u.trim())
    .filter(Boolean);

  return (
    <div className="card plan">
      <div className="plan-glowa">
        <div>
          <Link className="plan-ticker" href={`/spolka/${encodeURIComponent(plan.ticker)}`}>
            {plan.ticker}
          </Link>
          <span className="plan-nazwa">{nazwa}</span>
        </div>
        <span className={`stan-pill stan-${plan.stan}`} title={OPISY_STANU[plan.stan]}>
          {ETYKIETY_STANU[plan.stan]}
        </span>
      </div>

      <p className="plan-teza">{plan.teza}</p>

      <div className="plan-poziomy">
        <div className="plan-poz">
          <span>Wejście</span>
          <strong>
            {lb(plan.wejscieOd, c)} – {lb(plan.wejscieDo, c)}
          </strong>
        </div>
        <div className="plan-poz">
          <span>Stop</span>
          <strong className="down">{lb(plan.sl, c)}</strong>
          {plan.slPoziom && <em>{plan.slPoziom}</em>}
        </div>
        <div className="plan-poz">
          <span>Cel</span>
          <strong className="up">
            {lb(plan.tp1, c)}
            {plan.tp2 !== null ? ` → ${lb(plan.tp2, c)}` : ""}
          </strong>
        </div>
        <div className="plan-poz">
          <span>Zysk do ryzyka</span>
          <strong>{plan.rr !== null ? `${lb(plan.rr, 2)} : 1` : "—"}</strong>
        </div>
        <div className="plan-poz">
          <span>Pewność</span>
          <Pewnosc ile={plan.pewnosc} />
        </div>
      </div>

      <div className="plan-stopka">
        {cena !== null && (
          <span>
            Kurs <b>{lb(cena, c)}</b> {waluta} — {gdzie ?? "brak odniesienia"}
          </span>
        )}
        {otwarty ? (
          <span>
            {plan.sesjiMinelo} z {plan.horyzontSesji} sesji
            {plan.dataWejscia ? ` · wejście ${plan.dataWejscia}` : ""}
          </span>
        ) : (
          <span>
            {plan.dataZamkniecia ? `zamknięty ${plan.dataZamkniecia}` : "zamknięty"}
            {plan.cenaZamkniecia !== null ? ` po ${lb(plan.cenaZamkniecia, c)}` : ""}
            {plan.wynikR !== null && (
              <b className={plan.wynikR > 0 ? "up" : plan.wynikR < 0 ? "down" : undefined}>
                {" "}
                {plan.wynikR > 0 ? "+" : ""}
                {lb(plan.wynikR, 2)} R
              </b>
            )}
          </span>
        )}
        {plan.zrodla && <span className="plan-zrodla">Wskazana przez: {plan.zrodla}</span>}
        {otwarty && (
          <form action={anuluj} className="plan-anuluj">
            <input type="hidden" name="id" value={plan.id} />
            <input type="hidden" name="dzien" value={plan.dzien} />
            <button type="submit" title="Plan nie wchodzi wtedy do statystyki">
              Anuluj
            </button>
          </form>
        )}
      </div>

      {uwagi.length > 0 && (
        <ul className="plan-uwagi">
          {uwagi.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default async function PlanDnia({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  await wymagajZalogowania();

  const q = await searchParams;
  const jeden = (k: string) => {
    const v = q[k];
    return Array.isArray(v) ? v[0] : v;
  };

  const { data, tryb, instrumenty } = await migawkaBezpieczna();
  const dni = await dniPlanow();

  // Śmieci w adresie nie mogą wywalać strony — nieznany dzień traktujemy tak
  // jak jego brak, czyli pokazujemy najnowszy.
  const zadany = jeden("dzien");
  const dzien = zadany && dni.includes(zadany) ? zadany : dni[0];

  const [dnia, otwarte, zamkniete] = await Promise.all([
    dzien ? planyDnia(dzien) : Promise.resolve([]),
    planyOtwarte(),
    planyZamkniete(),
  ]);

  const stat = podsumowanie(zamkniete);

  const rynek = new Map(
    instrumenty.map((i) => [
      String(i.Ticker ?? ""),
      {
        cena: typeof i.Cena === "number" ? i.Cena : null,
        nazwa: String(i.Nazwa ?? ""),
        waluta: String(i.Waluta ?? ""),
      },
    ]),
  );
  const opis = (t: string) =>
    rynek.get(t) ?? { cena: null, nazwa: "", waluta: "" };

  // Plany z wcześniejszych dni, które wciąż żyją — inaczej znikałyby z oczu
  // dokładnie wtedy, gdy są najciekawsze.
  const zPoprzednichDni = otwarte.filter((p) => p.dzien !== dzien);

  const wynik = jeden("wynik");
  const komunikat = wynik ? KOMUNIKATY[wynik] : null;

  return (
    <main className="wrap">
      <Pasek dataMigawki={data} tryb={tryb} />

      <div className="cardhead" style={{ padding: "18px 0 4px" }}>
        <h2 style={{ fontSize: "1.15rem" }}>Plan dnia</h2>
        <em>{dzien ? dzien : "brak planów"}</em>
        <Link className="link" href="/">
          ← Wróć na pulpit
        </Link>
      </div>

      <p className="opis-strategii">
        Konkretne poziomy wejścia, stop-lossa i celów dla spółek wskazanych
        przez rankingi. Każdy plan przeszedł mechaniczną kontrolę: stop i cel
        muszą odpowiadać poziomom policzonym z notowań, zysk do ryzyka co
        najmniej 1,5, a stop leżeć między 0,5 a 3 ATR od wejścia. Rozliczane
        są same, przy codziennym skanie.
      </p>

      {komunikat && (
        <p className={wynik === "anulowany" ? "panel" : "komunikat-blad"}>{komunikat}</p>
      )}

      {stat.liczba > 0 && (
        <>
          <div className="stats">
            <div>
              <b>{stat.liczba}</b>
              <span>rozliczonych planów</span>
            </div>
            <div>
              <b>{lb(stat.skutecznosc, 1)}%</b>
              <span>na plusie ({stat.trafione})</span>
            </div>
            <div>
              <b className={stat.sumaR > 0 ? "up" : stat.sumaR < 0 ? "down" : undefined}>
                {stat.sumaR > 0 ? "+" : ""}
                {lb(stat.sumaR, 2)} R
              </b>
              <span>suma wyników</span>
            </div>
            <div>
              <b>
                {stat.sredniaR !== null && stat.sredniaR > 0 ? "+" : ""}
                {lb(stat.sredniaR, 2)} R
              </b>
              <span>średnio na plan</span>
            </div>
          </div>
          <p className="drobne">
            R to jednostka ryzyka: różnica między zakładanym wejściem
            a stop-lossem. +2 R znaczy „zarobione dwa razy tyle, ile było na
            stole". Rozliczenie zakłada wejście po najgorszej cenie w strefie,
            a przy świecy, która dotknęła i stopa, i celu — przyjmuje stop.
          </p>
        </>
      )}

      {dni.length > 1 && (
        <div className="wybor">
          {dni.slice(0, 14).map((d) => (
            <Link
              key={d}
              href={`/plan?dzien=${d}`}
              className={d === dzien ? "wybor-poz aktywna" : "wybor-poz"}
            >
              {d}
            </Link>
          ))}
        </div>
      )}

      {dni.length === 0 ? (
        <div className="card" style={{ marginTop: 14, padding: "16px 18px" }}>
          <h3 className="naglowek-sekcji">Nie ma jeszcze żadnych planów</h3>
          <p className="pusto">
            Dossier kandydatów przygotowuje się samo o 6:00 w dni robocze, ale
            plany powstają dopiero wtedy, gdy je zamówisz — poleceniem{" "}
            <code>/plan-dnia</code> w Claude Code. Analiza wykresów nie chodzi
            automatycznie i to jest świadome: wybór poziomów kosztuje, a Ty i
            tak decydujesz, w które dni chcesz go mieć.
          </p>
        </div>
      ) : dnia.length === 0 ? (
        <div className="card" style={{ marginTop: 14, padding: "16px 18px" }}>
          <p className="pusto">Na {dzien} nie zapisano żadnego planu.</p>
        </div>
      ) : (
        <div className="plany">
          {dnia.map((p) => {
            const o = opis(p.ticker);
            return (
              <KartaPlanu
                key={p.id}
                plan={p}
                cena={o.cena}
                nazwa={o.nazwa}
                waluta={o.waluta}
              />
            );
          })}
        </div>
      )}

      {zPoprzednichDni.length > 0 && (
        <>
          <div className="cardhead" style={{ padding: "20px 0 4px" }}>
            <h2 style={{ fontSize: "1.05rem" }}>Wciąż otwarte z wcześniejszych dni</h2>
            <em>{zPoprzednichDni.length}</em>
          </div>
          <div className="plany">
            {zPoprzednichDni.map((p) => {
              const o = opis(p.ticker);
              return (
                <KartaPlanu
                  key={p.id}
                  plan={p}
                  cena={o.cena}
                  nazwa={o.nazwa}
                  waluta={o.waluta}
                />
              );
            })}
          </div>
        </>
      )}

      {zamkniete.length > 0 && (
        <>
          <div className="cardhead" style={{ padding: "20px 0 4px" }}>
            <h2 style={{ fontSize: "1.05rem" }}>Rozliczone</h2>
            <em>ostatnie {zamkniete.length}</em>
          </div>
          <div className="card" style={{ marginTop: 12 }}>
            <div className="scroll">
              <table className="tab-plany">
                <thead>
                  <tr>
                    <th>Spółka</th>
                    <th>Plan z dnia</th>
                    <th>Jak się skończył</th>
                    <th>Zamknięty</th>
                    <th className="r">Wynik</th>
                    <th className="r">Sesji</th>
                  </tr>
                </thead>
                <tbody>
                  {zamkniete.map((p) => (
                    <tr key={p.id}>
                      <td className="t">
                        <Link href={`/spolka/${encodeURIComponent(p.ticker)}`}>
                          {p.ticker}
                        </Link>
                      </td>
                      <td data-l="Plan z dnia">{p.dzien}</td>
                      <td data-l="Koniec">
                        <span className={`stan-pill stan-${p.stan}`}>
                          {ETYKIETY_STANU[p.stan]}
                        </span>
                      </td>
                      <td data-l="Zamknięty">{p.dataZamkniecia ?? "—"}</td>
                      <td className="r n" data-l="Wynik">
                        {p.wynikR === null ? (
                          <span className="brak">—</span>
                        ) : (
                          <b
                            className={
                              p.wynikR > 0 ? "up" : p.wynikR < 0 ? "down" : undefined
                            }
                          >
                            {p.wynikR > 0 ? "+" : ""}
                            {lb(p.wynikR, 2)} R
                          </b>
                        )}
                      </td>
                      <td className="r n" data-l="Sesji">
                        {p.sesjiMinelo}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <p className="drobne" style={{ marginTop: 18 }}>
        Skąd się to bierze: o 6:00 GitHub Actions zbiera po pięć spółek z czoła
        każdego rankingu, liczy dla nich poziomy techniczne z dziesięciu lat
        notowań i zapisuje dossier. Plany powstają dopiero na Twoje żądanie
        (<code>/plan-dnia</code>) i przechodzą przez bramkę, która odrzuca
        wszystko, czego nie da się oprzeć na policzonym poziomie. Zapisanego
        planu nie można już zmienić — inaczej statystyka skuteczności nie
        znaczyłaby nic.
      </p>
    </main>
  );
}
