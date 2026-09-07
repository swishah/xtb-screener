"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import type { Instrument } from "@/lib/filtry";

/**
 * Wybór spółki do porównania.
 *
 * Zwykłe `select` z pełną listą, a nie pole z podpowiedziami jak w Watchliście:
 * tam wpisuje się ticker, który się zna, a tutaj przegląda się i porównuje,
 * więc widok całej listy z nazwami jest tym, czego się szuka. Wybór ląduje
 * w adresie strony, więc porównanie da się wysłać linkiem.
 */
export default function Wybor({
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
          <span>Spółka do porównania</span>
          <select
            value={wybrana}
            onChange={(e) =>
              startTransition(() => {
                router.replace(
                  `/sektor?spolka=${encodeURIComponent(e.target.value)}`,
                  { scroll: false },
                );
              })
            }
          >
            {posortowane.map((s) => (
              <option key={String(s.Ticker)} value={String(s.Ticker)}>
                {String(s.Ticker)} — {String(s.Nazwa ?? "")} ({String(s.Sektor ?? "")})
              </option>
            ))}
          </select>
        </label>
      </div>
      {oczekuje && (
        <div className="filtry-stopka">
          <span className="liczy">Liczę…</span>
        </div>
      )}
    </div>
  );
}
