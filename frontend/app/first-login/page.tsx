"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { DEFAULT_LOCALE, Locale, t } from "../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function errorMessage(locale: Locale, code: string) {
  const message = t(locale, `errors.${code}`);
  return message === `errors.${code}` ? t(locale, "errors.fallback") : message;
}

function FirstLoginForm() {
  const token = useSearchParams().get("token") ?? "";
  const [locale] = useState<Locale>(DEFAULT_LOCALE);
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorCode, setErrorCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setStatus("idle");
    setErrorCode("");
    const response = await fetch(`${apiBaseUrl}/auth/first-login`, {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token, password }),
    });
    const data = await response.json().catch(() => ({}));
    setIsSubmitting(false);
    if (response.ok) {
      setPassword("");
      setStatus("success");
      return;
    }
    setErrorCode(typeof data.error_code === "string" ? data.error_code : "TOKEN_INVALID");
    setStatus("error");
  }

  return (
    <form className="loginForm" onSubmit={submit}>
      <label>
        <span>{t(locale, "firstLogin.newPassword")}</span>
        <input
          autoComplete="new-password"
          minLength={10}
          onChange={(event) => setPassword(event.target.value)}
          required
          type="password"
          value={password}
        />
      </label>
      {status === "success" ? <p className="stateText success">{t(locale, "firstLogin.success")}</p> : null}
      {status === "error" ? (
        <p className="errorText" role="alert">
          {errorMessage(locale, errorCode)}
        </p>
      ) : null}
      <button className="primaryButton" disabled={isSubmitting || !token} type="submit">
        {t(locale, "firstLogin.submit")}
      </button>
      <Link className="textLink" href="/">
        {t(locale, "app.goToLogin")}
      </Link>
    </form>
  );
}

export default function FirstLoginPage() {
  const locale = DEFAULT_LOCALE;

  return (
    <main className="shell">
      <section className="authPanel">
        <p className="eyebrow">{t(locale, "app.brand")}</p>
        <h1>{t(locale, "firstLogin.title")}</h1>
        <p className="subtitle">{t(locale, "firstLogin.subtitle")}</p>
        <Suspense fallback={<p className="stateText">{t(locale, "app.loadingLink")}</p>}>
          <FirstLoginForm />
        </Suspense>
      </section>
    </main>
  );
}
