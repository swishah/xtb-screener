import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "XTB Screener",
  description: "Screener akcji i ETF-ów pod instrumenty dostępne na XTB.",
};

/**
 * Skrypt ustawiający motyw MUSI wykonać się przed pierwszym malowaniem, inaczej
 * przy wybranym trybie ciemnym mignęłoby białe tło. Stąd wstrzyknięcie go
 * bezpośrednio w <head>, a nie zwykły komponent kliencki.
 *
 * Czytanie localStorage owinięte w try — w oknie prywatnym albo przy
 * zablokowanych danych witryny rzuca wyjątkiem, a to nie może wywalić strony.
 */
const skryptMotywu = `
try {
  var z = localStorage.getItem('motyw');
  if (z === 'dark' || z === 'light') {
    document.documentElement.setAttribute('data-theme', z);
  }
} catch (e) {}
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pl">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;800&family=IBM+Plex+Mono:wght@400;600&display=swap"
        />
        <script dangerouslySetInnerHTML={{ __html: skryptMotywu }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
