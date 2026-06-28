"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function FirstLoginForm() {
  const token = useSearchParams().get("token") ?? "";
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
        <span>Новый пароль</span>
        <input
          autoComplete="new-password"
          minLength={10}
          onChange={(event) => setPassword(event.target.value)}
          required
          type="password"
          value={password}
        />
      </label>
      {status === "success" ? (
        <p className="stateText success">Пароль установлен. Теперь войдите обычным способом.</p>
      ) : null}
      {status === "error" ? (
        <p className="errorText" role="alert">
          {errorCode}
        </p>
      ) : null}
      <button className="primaryButton" disabled={isSubmitting || !token} type="submit">
        Установить пароль
      </button>
      <Link className="textLink" href="/">
        Перейти ко входу
      </Link>
    </form>
  );
}

export default function FirstLoginPage() {
  return (
    <main className="shell">
      <section className="authPanel">
        <p className="eyebrow">IBB Insurance Portal</p>
        <h1>Первый вход</h1>
        <p className="subtitle">Задайте пароль для доступа к порталу.</p>
        <Suspense fallback={<p className="stateText">Загрузка ссылки</p>}>
          <FirstLoginForm />
        </Suspense>
      </section>
    </main>
  );
}
