"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ForgotPasswordPage() {
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
        <p className="eyebrow">IBB Insurance Portal</p>
        <h1>Восстановление пароля</h1>
        <p className="subtitle">Если пользователь существует, мы отправим письмо со ссылкой для восстановления.</p>
        {isDone ? (
          <div className="sessionBox">
            <p className="stateText success">Проверьте почту, если аккаунт зарегистрирован в портале.</p>
            <Link className="textLink" href="/">
              Вернуться ко входу
            </Link>
          </div>
        ) : (
          <form className="loginForm" onSubmit={submit}>
            <label>
              <span>Email</span>
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
              Отправить ссылку
            </button>
            <Link className="textLink" href="/">
              Перейти ко входу
            </Link>
          </form>
        )}
      </section>
    </main>
  );
}
