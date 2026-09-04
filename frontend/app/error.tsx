"use client";

/**
 * Obsługa awarii dla całej aplikacji.
 *
 * Bez tego pliku Next.js pokazuje surowy komunikat błędu — na produkcji
 * bezużyteczny dla czytającego i nieprzyjemny. Najbardziej prawdopodobna
 * przyczyna to niedostępna baza albo brakujące zmienne środowiskowe, więc
 * właśnie od tego zaczynamy podpowiedź.
 *
 * Treść wyjątku pokazujemy drobnym drukiem: przy diagnozowaniu ratuje życie,
 * a nie zawiera niczego wrażliwego — token nigdy nie trafia do komunikatu.
 */
export default function Blad({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="wrap">
      <div className="bar">
        <h1 className="brand">XTB Screener</h1>
      </div>

      <div className="alert" style={{ marginTop: 22 }}>
        <p style={{ margin: "0 0 10px" }}>
          <b>Nie udało się wczytać danych.</b>
        </p>
        <p style={{ margin: "0 0 10px" }}>
          Najczęstsza przyczyna to chwilowo niedostępna baza albo brakujące
          zmienne <code>TURSO_DATABASE_URL</code> i <code>TURSO_AUTH_TOKEN</code>{" "}
          w konfiguracji hostingu.
        </p>
        <p style={{ margin: "0 0 14px", fontSize: "0.8rem", opacity: 0.75 }}>
          {error.message}
          {error.digest ? ` (${error.digest})` : ""}
        </p>
        <button className="icobtn" style={{ width: "auto", padding: "0 14px" }} onClick={reset}>
          Spróbuj ponownie
        </button>
      </div>
    </main>
  );
}
