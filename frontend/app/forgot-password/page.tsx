"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { DEFAULT_LOCALE, t } from "../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ForgotPasswordPage() {
  const locale = DEFAULT_LOCALE;
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDone, setIsDone] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    await fetch(`${apiBaseUrl}/auth/password-reset/request`, {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email }),
    }).catch(() => undefined);
    setIsSubmitting(false);
    setIsDone(true);
  }

  return (
    <main className="shell">
      <section className="authPanel">
        <p className="eyebrow">{t(locale, "app.brand")}</p>
        <h1>{t(locale, "forgotPassword.title")}</h1>
        <p className="subtitle">{t(locale, "forgotPassword.subtitle")}</p>
        {isDone ? (
          <div className="sessionBox">
            <p className="stateText success">{t(locale, "forgotPassword.success")}</p>
            <Link className="textLink" href="/">
              {t(locale, "app.backToLogin")}
            </Link>
          </div>
        ) : (
          <form className="loginForm" onSubmit={submit}>
            <label>
              <span>{t(locale, "app.email")}</span>
              <input
                autoComplete="email"
                inputMode="email"
                onChange={(event) => setEmail(event.target.value)}
                required
                type="email"
                value={email}
              />
            </label>
            <button className="primaryButton" disabled={isSubmitting} type="submit">
              {t(locale, "forgotPassword.submit")}
            </button>
            <Link className="textLink" href="/">
              {t(locale, "app.goToLogin")}
            </Link>
          </form>
        )}
      </section>
    </main>
  );
}
