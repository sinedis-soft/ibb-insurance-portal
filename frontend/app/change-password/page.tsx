"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { Locale, DEFAULT_LOCALE, normalizeLocale, t } from "../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CurrentUser = {
  language: Locale;
};

async function requestJson(path: string, options: RequestInit = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "content-type": "application/json",
      ...options.headers,
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data.error_code === "string" ? data.error_code : "UNAUTHORIZED");
  }
  return data;
}

function errorMessage(locale: Locale, code: string) {
  const message = t(locale, `errors.${code}`);
  return message === `errors.${code}` ? t(locale, "errors.fallback") : message;
}

export default function ChangePasswordPage() {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [errorCode, setErrorCode] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDone, setIsDone] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadCurrentUser() {
      try {
        const currentUser = (await requestJson("/auth/me")) as CurrentUser;
        if (isMounted) {
          setLocale(normalizeLocale(currentUser.language));
        }
      } catch (error) {
        if (isMounted) {
          setErrorCode(error instanceof Error ? error.message : "UNAUTHORIZED");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadCurrentUser();
    return () => {
      isMounted = false;
    };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorCode("");
    try {
      await requestJson("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setIsDone(true);
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "UNAUTHORIZED");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="shell">
      <section className="authPanel" aria-busy={isLoading}>
        <p className="eyebrow">{t(locale, "app.brand")}</p>
        <h1>{t(locale, "changePassword.title")}</h1>
        <p className="subtitle">{t(locale, "changePassword.subtitle")}</p>
        {isLoading ? <p className="stateText">{t(locale, "changePassword.loading")}</p> : null}
        {isDone ? (
          <div className="sessionBox">
            <p className="stateText success">{t(locale, "changePassword.success")}</p>
            <Link className="textLink" href="/">
              {t(locale, "app.goToLogin")}
            </Link>
          </div>
        ) : null}
        {!isLoading && !isDone ? (
          <form className="loginForm" onSubmit={submit}>
            <label>
              <span>{t(locale, "changePassword.currentPassword")}</span>
              <input
                autoComplete="current-password"
                onChange={(event) => setCurrentPassword(event.target.value)}
                required
                type="password"
                value={currentPassword}
              />
            </label>
            <label>
              <span>{t(locale, "changePassword.newPassword")}</span>
              <input
                autoComplete="new-password"
                minLength={10}
                onChange={(event) => setNewPassword(event.target.value)}
                required
                type="password"
                value={newPassword}
              />
            </label>
            {errorCode ? (
              <p className="errorText" role="alert">
                {errorMessage(locale, errorCode)}
              </p>
            ) : null}
            <button className="primaryButton" disabled={isSubmitting} type="submit">
              {t(locale, "changePassword.submit")}
            </button>
            <Link className="textLink" href="/">
              {t(locale, "app.goToLogin")}
            </Link>
          </form>
        ) : null}
      </section>
    </main>
  );
}
