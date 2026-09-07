"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { MAKS_WAGA, SKLADNIKI, type Wagi } from "@/lib/wlasny";

/**
 * Suwaki wag — wszystkie w adresie URL, tak jak filtry Screenera.
 *
 * Dzięki temu ULUBIONĄ FORMUŁĘ DA SIĘ ZAPISAĆ W ZAKŁADCE i wrócić do niej za
 * miesiąc albo wysłać komuś linkiem. To jedyny sensowny sposób „zapisania"
 * własnego scoringu bez dokładania kolejnej tabeli w bazie.
 */
export default function PanelWag({
  wagi,
  suma,
}: {
  wagi: Wagi;
  suma: number;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [oczekuje, startTransition] = useTransition();

  function ustaw(kolumna: string, wartosc: string) {
    const nowe = new URLSearchParams(params.toString());
    nowe.set(`w_${kolumna}`, wartosc);
    startTransition(() => {
      router.replace(`/scoring?${nowe.toString()}`, { scroll: false });
    });
  }

  return (
    <div className="filtry">
      <div className="wagi-siatka">
        {SKLADNIKI.map((s) => {
          const w = wagi[s.kolumna] ?? 0;
          return (
            <label key={s.kolumna} className={w === 0 ? "waga wylaczona" : "waga"}>
              <span className="waga-etykieta">
                {s.etykieta}
                <b>{w === 0 ? "pomijam" : `×${w}`}</b>
              </span>
              <input
                type="range"
                min={0}
                max={MAKS_WAGA}
                step={1}
                value={w}
                onChange={(e) => ustaw(s.kolumna, e.target.value)}
                aria-label={s.etykieta}
              />
            </label>
          );
        })}
      </div>

      <div className="filtry-stopka">
        <span className={oczekuje ? "liczy" : undefined}>
          {oczekuje
            ? "Liczę…"
            : suma === 0
              ? "Ustaw przynajmniej jedną wagę większą od zera"
              : `Suma wag: ${suma} — wynik to średnia ważona pozycji percentylowych`}
        </span>
      </div>
    </div>
  );
}
