"use client";

import { FormEvent, useEffect, useState } from "react";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Locale = "ru" | "ka";

type CurrentUser = {
  id: string;
  role: string;
  language: Locale;
  status: string;
};

type AuthErrorCode =
  | "INVALID_CREDENTIALS"
  | "TOO_MANY_LOGIN_ATTEMPTS"
  | "SESSION_EXPIRED"
  | "UNAUTHORIZED"
  | "FORBIDDEN"
  | "USER_BLOCKED";

const messages: Record<Locale, Record<string, string>> = {
  ru: {
    title: "IBB Insurance Portal",
    subtitle: "Безопасный вход в личный кабинет клиента и партнёра.",
    email: "Email",
    password: "Пароль",
    login: "Войти",
    logout: "Выйти",
    checking: "Проверяем сессию",
    signedIn: "Сессия активна",
    role: "Роль",
    language: "Язык",
    status: "Статус",
    retry: "Попробуйте ещё раз.",
    INVALID_CREDENTIALS: "Неверный email или пароль.",
    TOO_MANY_LOGIN_ATTEMPTS: "Слишком много попыток входа. Попробуйте позже.",
    SESSION_EXPIRED: "Сессия истекла. Войдите снова.",
    UNAUTHORIZED: "Войдите в личный кабинет.",
    FORBIDDEN: "Доступ запрещён.",
    USER_BLOCKED: "Пользователь заблокирован.",
  },
  ka: {
    title: "IBB Insurance Portal",
    subtitle: "უსაფრთხო შესვლა კლიენტისა და პარტნიორის კაბინეტში.",
    email: "Email",
    password: "პაროლი",
    login: "შესვლა",
    logout: "გასვლა",
    checking: "სესიის შემოწმება",
    signedIn: "სესია აქტიურია",
    role: "როლი",
    language: "ენა",
    status: "სტატუსი",
    retry: "სცადეთ ხელახლა.",
    INVALID_CREDENTIALS: "Email ან პაროლი არასწორია.",
    TOO_MANY_LOGIN_ATTEMPTS: "შესვლის მცდელობა ძალიან ბევრია. სცადეთ მოგვიანებით.",
    SESSION_EXPIRED: "სესიის ვადა ამოიწურა. შედით თავიდან.",
    UNAUTHORIZED: "შედით პირად კაბინეტში.",
    FORBIDDEN: "წვდომა აკრძალულია.",
    USER_BLOCKED: "მომხმარებელი დაბლოკილია.",
  },
};

function getMessage(locale: Locale, code: AuthErrorCode | string) {
  return messages[locale][code] ?? messages[locale].retry;
}

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

export default function Home() {
  const [locale, setLocale] = useState<Locale>("ru");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [errorCode, setErrorCode] = useState<AuthErrorCode | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const t = messages[locale];

  useEffect(() => {
    let isMounted = true;

    async function loadCurrentUser() {
      try {
        const currentUser = (await requestJson("/auth/me")) as CurrentUser;
        if (isMounted) {
          setUser(currentUser);
          setLocale(currentUser.language);
          setErrorCode(null);
        }
      } catch {
        try {
          await requestJson("/auth/refresh", { method: "POST", body: "{}" });
          const currentUser = (await requestJson("/auth/me")) as CurrentUser;
          if (isMounted) {
            setUser(currentUser);
            setLocale(currentUser.language);
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
      setLocale(data.user.language);
      setPassword("");
    } catch (error) {
      setErrorCode(error instanceof Error ? (error.message as AuthErrorCode) : "UNAUTHORIZED");
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
      setErrorCode(error instanceof Error ? (error.message as AuthErrorCode) : "UNAUTHORIZED");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="shell">
      <section className="authPanel" aria-busy={isLoading}>
        <div className="topBar">
          <p className="eyebrow">IBB Insurance Portal</p>
          <div className="localeSwitch" aria-label="Language">
            <button className={locale === "ru" ? "active" : ""} onClick={() => setLocale("ru")} type="button">
              RU
            </button>
            <button className={locale === "ka" ? "active" : ""} onClick={() => setLocale("ka")} type="button">
              KA
            </button>
          </div>
        </div>
        <h1>{t.title}</h1>
        <p className="subtitle">{t.subtitle}</p>

        {isLoading ? <p className="stateText">{t.checking}</p> : null}

        {!isLoading && user ? (
          <div className="sessionBox">
            <p className="stateText success">{t.signedIn}</p>
            <dl>
              <div>
                <dt>ID</dt>
                <dd>{user.id}</dd>
              </div>
              <div>
                <dt>{t.role}</dt>
                <dd>{user.role}</dd>
              </div>
              <div>
                <dt>{t.language}</dt>
                <dd>{user.language}</dd>
              </div>
              <div>
                <dt>{t.status}</dt>
                <dd>{user.status}</dd>
              </div>
            </dl>
            <button className="primaryButton" disabled={isSubmitting} onClick={handleLogout} type="button">
              {t.logout}
            </button>
          </div>
        ) : null}

        {!isLoading && !user ? (
          <form className="loginForm" onSubmit={handleLogin}>
            <label>
              <span>{t.email}</span>
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
              <span>{t.password}</span>
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
                {getMessage(locale, errorCode)}
              </p>
            ) : null}
            <button className="primaryButton" disabled={isSubmitting} type="submit">
              {t.login}
            </button>
          </form>
        ) : null}
      </section>
    </main>
  );
}
