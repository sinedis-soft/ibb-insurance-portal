"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Locale = "ru" | "ka";

type CurrentUser = {
  language: Locale;
};

const messages: Record<Locale, Record<string, string>> = {
  ru: {
    eyebrow: "IBB Insurance Portal",
    title: "Смена пароля",
    subtitle: "После смены пароля все активные сессии будут завершены. Войдите заново с новым паролем.",
    currentPassword: "Текущий пароль",
    newPassword: "Новый пароль",
    submit: "Сменить пароль",
    success: "Пароль изменен. Войдите заново.",
    login: "Перейти ко входу",
    loading: "Проверяем сессию",
    INVALID_CREDENTIALS: "Неверный текущий пароль.",
    PASSWORD_TOO_WEAK: "Пароль должен быть не короче 10 символов и содержать букву и цифру.",
    SESSION_EXPIRED: "Сессия истекла. Войдите заново.",
    UNAUTHORIZED: "Войдите в личный кабинет.",
    fallback: "Попробуйте еще раз.",
  },
  ka: {
    eyebrow: "IBB Insurance Portal",
    title: "პაროლის შეცვლა",
    subtitle: "პაროლის შეცვლის შემდეგ ყველა აქტიური სესია დასრულდება. შედით თავიდან ახალი პაროლით.",
    currentPassword: "მიმდინარე პაროლი",
    newPassword: "ახალი პაროლი",
    submit: "პაროლის შეცვლა",
    success: "პაროლი შეიცვალა. შედით თავიდან.",
    login: "შესვლაზე გადასვლა",
    loading: "სესიის შემოწმება",
    INVALID_CREDENTIALS: "მიმდინარე პაროლი არასწორია.",
    PASSWORD_TOO_WEAK: "პაროლი უნდა იყოს მინიმუმ 10 სიმბოლო და შეიცავდეს ასოსა და ციფრს.",
    SESSION_EXPIRED: "სესიის ვადა ამოიწურა. შედით თავიდან.",
    UNAUTHORIZED: "შედით პირად კაბინეტში.",
    fallback: "სცადეთ ხელახლა.",
  },
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

export default function ChangePasswordPage() {
  const [locale, setLocale] = useState<Locale>("ru");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [errorCode, setErrorCode] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const t = messages[locale];

  useEffect(() => {
    let isMounted = true;

    async function loadCurrentUser() {
      try {
        const currentUser = (await requestJson("/auth/me")) as CurrentUser;
        if (isMounted) {
          setLocale(currentUser.language === "ka" ? "ka" : "ru");
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
        <p className="eyebrow">{t.eyebrow}</p>
        <h1>{t.title}</h1>
        <p className="subtitle">{t.subtitle}</p>
        {isLoading ? <p className="stateText">{t.loading}</p> : null}
        {isDone ? (
          <div className="sessionBox">
            <p className="stateText success">{t.success}</p>
            <Link className="textLink" href="/">
              {t.login}
            </Link>
          </div>
        ) : null}
        {!isLoading && !isDone ? (
          <form className="loginForm" onSubmit={submit}>
            <label>
              <span>{t.currentPassword}</span>
              <input
                autoComplete="current-password"
                onChange={(event) => setCurrentPassword(event.target.value)}
                required
                type="password"
                value={currentPassword}
              />
            </label>
            <label>
              <span>{t.newPassword}</span>
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
                {t[errorCode] ?? t.fallback}
              </p>
            ) : null}
            <button className="primaryButton" disabled={isSubmitting} type="submit">
              {t.submit}
            </button>
            <Link className="textLink" href="/">
              {t.login}
            </Link>
          </form>
        ) : null}
      </section>
    </main>
  );
}
