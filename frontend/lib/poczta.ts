import nodemailer from "nodemailer";

/**
 * Wysyłka poczty — na razie służy wyłącznie do resetu hasła.
 *
 * DLACZEGO JEDNA NOWA ZALEŻNOŚĆ. Projekt świadomie unika bibliotek, ale Node
 * nie ma wbudowanego klienta SMTP, a napisanie własnego (TLS, AUTH, kodowanie
 * nagłówków) to sto kilkadziesiąt linii protokołu, w którym łatwo o błąd
 * i bardzo trudno o test. To dokładnie ten przypadek "realnej potrzeby",
 * który przewiduje zasada minimalizmu w CLAUDE.md. `nodemailer` jest czysto
 * javascriptowy, bez kompilacji natywnej, i utrzymywany od ponad dekady.
 *
 * TE SAME ZMIENNE CO W PYTHONIE. `core/alerts.py` używa już EMAIL_SMTP_HOST,
 * EMAIL_SMTP_PORT, EMAIL_FROM i EMAIL_PASSWORD — używamy dokładnie tych
 * samych nazw, żeby w całym projekcie były JEDNE dane dostępowe do poczty,
 * a nie dwa komplety, które się rozjadą.
 *
 * GDY POCZTA NIE JEST SKONFIGUROWANA, mówimy o tym wprost zamiast udawać
 * wysyłkę. Formularz "zapomniałem hasła", który zawsze odpowiada "wysłano",
 * a nigdy nic nie wysyła, jest gorszy od komunikatu o błędzie: użytkownik
 * czeka na maila, którego nie ma.
 */

export function pocztaSkonfigurowana(): boolean {
  return Boolean(
    process.env.EMAIL_SMTP_HOST &&
      process.env.EMAIL_FROM &&
      process.env.EMAIL_PASSWORD,
  );
}

export async function wyslijMail(
  do_: string,
  temat: string,
  tresc: string,
): Promise<{ ok: boolean; powod?: string }> {
  if (!pocztaSkonfigurowana()) {
    return {
      ok: false,
      powod:
        "Wysyłka poczty nie jest skonfigurowana (brak EMAIL_SMTP_HOST, " +
        "EMAIL_FROM lub EMAIL_PASSWORD w ustawieniach wdrożenia).",
    };
  }

  const port = Number(process.env.EMAIL_SMTP_PORT ?? "587");
  try {
    const transport = nodemailer.createTransport({
      host: process.env.EMAIL_SMTP_HOST,
      port,
      // 465 to SMTP owinięty w TLS od pierwszego bajtu; 587 zaczyna jawnie
      // i podnosi szyfrowanie przez STARTTLS. Pomylenie tych dwóch to
      // najczęstsza przyczyna "połączenie wisi i nic się nie dzieje".
      secure: port === 465,
      auth: {
        user: process.env.EMAIL_FROM,
        pass: process.env.EMAIL_PASSWORD,
      },
    });

    await transport.sendMail({
      from: process.env.EMAIL_FROM,
      to: do_,
      subject: temat,
      text: tresc,
    });
    return { ok: true };
  } catch (e) {
    // Treści błędu NIE pokazujemy użytkownikowi: potrafi zawierać adres
    // serwera i nazwę konta pocztowego.
    console.error("Wysyłka maila nie powiodła się:", e);
    return {
      ok: false,
      powod: "Nie udało się wysłać wiadomości. Spróbuj ponownie za chwilę.",
    };
  }
}

/**
 * Adres aplikacji do linków w mailach. Vercel podaje go sam w VERCEL_URL,
 * ale bez schematu — stąd doklejanie https. ADRES_APLIKACJI ma pierwszeństwo,
 * bo VERCEL_URL wskazuje konkretne wdrożenie, a nie stały adres.
 */
export function adresAplikacji(): string {
  const jawny = process.env.ADRES_APLIKACJI;
  if (jawny) return jawny.replace(/\/+$/, "");
  const vercel = process.env.VERCEL_URL;
  if (vercel) return `https://${vercel}`;
  return "http://localhost:3000";
}
