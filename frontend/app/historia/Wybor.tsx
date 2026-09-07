"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import type { Instrument } from "@/lib/filtry";

/** Wybór spółki; stan siedzi w adresie, więc widok da się wysłać linkiem. */
export default function WyborSpolki({
  spolki,
  wybrana,
}: {
  spolki: Instrument[];
  wybrana: string;
}) {
  const router = useRouter();
  const [oczekuje, startTransition] = useTransition();

  const posortowane = [...spolki].sort((a, b) =>
    String(a.Ticker).localeCompare(String(b.Ticker), "pl"),
  );

  return (
    <div className="filtry">
      <div className="filtry-siatka">
        <label style={{ flex: "1 1 420px" }}>
          <span>Spółka lub ETF</span>
          <select
            value={wybrana}
            onChange={(e) =>
              startTransition(() => {
                // Zmiana spółki kasuje wybrany dzień — migawki innej spółki
                // mogą mieć inne daty, a stary parametr wskazywałby w próżnię.
                router.replace(
                  `/historia?spolka=${encodeURIComponent(e.target.value)}`,
                  { scroll: false },
                );
              })
            }
          >
            {posortowane.map((s) => (
              <option key={String(s.Ticker)} value={String(s.Ticker)}>
                {String(s.Ticker)} — {String(s.Nazwa ?? "")}
              </option>
            ))}
          </select>
        </label>
      </div>
      {oczekuje && (
        <div className="filtry-stopka">
          <span className="liczy">Wczytuję…</span>
        </div>
      )}
    </div>
  );
}
