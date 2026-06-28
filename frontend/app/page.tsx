"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { Locale, DEFAULT_LOCALE, normalizeLocale, t } from "../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CurrentUser = {
  id: string;
  role: string;
  language: Locale;
  status: string;
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

export default function Home() {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadCurrentUser() {
      try {
        const currentUser = (await requestJson("/auth/me")) as CurrentUser;
        if (isMounted) {
          setUser(currentUser);
          setLocale(normalizeLocale(currentUser.language));
          setErrorCode(null);
        }
      } catch {
        try {
          await requestJson("/auth/refresh", { method: "POST", body: "{}" });
          const currentUser = (await requestJson("/auth/me")) as CurrentUser;
          if (isMounted) {
            setUser(currentUser);
            setLocale(normalizeLocale(currentUser.language));
            setErrorCode(null);
          }
        } catch {
          if (isMounted) {
            setUser(null);
          }
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

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorCode(null);
    try {
      const data = (await requestJson("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      })) as { user: CurrentUser };
      setUser(data.user);
      setLocale(normalizeLocale(data.user.language));
      setPassword("");
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "UNAUTHORIZED");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogout() {
    setIsSubmitting(true);
    setErrorCode(null);
    try {
      await requestJson("/auth/logout", { method: "POST", body: "{}" });
      setUser(null);
      setPassword("");
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "UNAUTHORIZED");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="shell">
      <section className="authPanel" aria-busy={isLoading}>
        <div className="topBar">
          <p className="eyebrow">{t(locale, "app.brand")}</p>
          <div className="localeSwitch" aria-label="Language">
            <button className={locale === "ru" ? "active" : ""} onClick={() => setLocale("ru")} type="button">
              RU
            </button>
            <button className={locale === "ka" ? "active" : ""} onClick={() => setLocale("ka")} type="button">
              KA
            </button>
          </div>
        </div>
        <h1>{t(locale, "auth.title")}</h1>
        <p className="subtitle">{t(locale, "auth.subtitle")}</p>

        {isLoading ? <p className="stateText">{t(locale, "auth.checking")}</p> : null}

        {!isLoading && user ? (
          <div className="sessionBox">
            <p className="stateText success">{t(locale, "auth.signedIn")}</p>
            <dl>
              <div>
                <dt>ID</dt>
                <dd>{user.id}</dd>
              </div>
              <div>
                <dt>{t(locale, "auth.role")}</dt>
                <dd>{user.role}</dd>
              </div>
              <div>
                <dt>{t(locale, "auth.language")}</dt>
                <dd>{user.language}</dd>
              </div>
              <div>
                <dt>{t(locale, "auth.status")}</dt>
                <dd>{user.status}</dd>
              </div>
            </dl>
            <button className="primaryButton" disabled={isSubmitting} onClick={handleLogout} type="button">
              {t(locale, "auth.logout")}
            </button>
            <Link className="textLink" href="/change-password">
              {t(locale, "auth.changePassword")}
            </Link>
          </div>
        ) : null}

        {!isLoading && !user ? (
          <form className="loginForm" onSubmit={handleLogin}>
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
            <label>
              <span>{t(locale, "auth.password")}</span>
              <input
                autoComplete="current-password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </label>
            {errorCode ? (
              <p className="errorText" role="alert">
                {errorMessage(locale, errorCode)}
              </p>
            ) : null}
            <button className="primaryButton" disabled={isSubmitting} type="submit">
              {t(locale, "auth.login")}
            </button>
          </form>
        ) : null}
      </section>
    </main>
  );
}
