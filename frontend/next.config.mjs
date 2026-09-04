/** @type {import('next').NextConfig} */
const nextConfig = {
  // DECYZJA POD PRZENOŚNOŚĆ (faza 05 planu — serwer NAS).
  //
  // Tryb "standalone" pakuje aplikację razem z minimalnym zestawem zależności,
  // dzięki czemu obraz Dockera powstaje z gotowego projektu, bez przepisywania
  // czegokolwiek. Podjęte teraz kosztuje jedną linijkę; podjęte później
  // oznaczałoby przebudowę.
  output: "standalone",

  // Klient bazy zostaje po stronie serwera i nie jest pakowany do bundla
  // wysyłanego do przeglądarki. W starszych wersjach Next.js ta opcja
  // nazywała się experimental.serverComponentsExternalPackages.
  serverExternalPackages: ["@libsql/client"],
};

export default nextConfig;
