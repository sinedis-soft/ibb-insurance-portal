"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import {
  type CompanyAccess,
  CompanyContextProvider,
  useCompanyContext,
} from "../lib/company-context";
import { Locale, DEFAULT_LOCALE, normalizeLocale, t } from "../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CurrentUser = {
  id: string;
  role: string;
  user_type: string;
  language: Locale;
  status: string;
};

async function requestJson<T = unknown>(path: string, options: RequestInit = {}) {
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
  return data as T;
}

function errorMessage(locale: Locale, code: string) {
  const message = t(locale, `errors.${code}`);
  return message === `errors.${code}` ? t(locale, "errors.fallback") : message;
}

function companyTitle(company: CompanyAccess) {
  return company.company_title || company.bitrix_company_id;
}

function CompanyContextPanel({ locale, user }: { locale: Locale; user: CurrentUser }) {
  const {
    availableCompanies,
    selectedCompany,
    selectedCompanyId,
    isLoadingCompanies,
    companyErrorCode,
    contextVersion,
    reloadCompanies,
    setSelectedCompanyId,
  } = useCompanyContext();
  const [scopedDataVersion, setScopedDataVersion] = useState(0);

  useEffect(() => {
    setScopedDataVersion(0);
    if (!selectedCompany) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      setScopedDataVersion(contextVersion);
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [contextVersion, selectedCompany]);

  if (user.user_type === "partner") {
    return (
      <section className="companyPanel">
        <p className="sectionLabel">{t(locale, "companies.partnerScopeTitle")}</p>
        <p className="stateText">{t(locale, "companies.partnerScopeDescription")}</p>
      </section>
    );
  }

  return (
    <section className="companyPanel" aria-busy={isLoadingCompanies}>
      <div className="sectionHeader">
        <div>
          <p className="sectionLabel">{t(locale, "companies.contextLabel")}</p>
          <h2>{t(locale, "companies.selectTitle")}</h2>
        </div>
        <button
          className="secondaryButton"
          disabled={isLoadingCompanies}
          onClick={() => void reloadCompanies()}
          type="button"
        >
          {t(locale, "companies.reload")}
        </button>
      </div>

      {isLoadingCompanies ? <p className="stateText">{t(locale, "companies.loading")}</p> : null}

      {!isLoadingCompanies && availableCompanies.length === 0 ? (
        <p className="stateText">{t(locale, "companies.empty")}</p>
      ) : null}

      {companyErrorCode ? (
        <p className="errorText" role="alert">
          {errorMessage(locale, companyErrorCode)}
        </p>
      ) : null}

      {availableCompanies.length > 0 ? (
        <div className="companyList">
          {availableCompanies.map((company) => {
            const isSelected = company.bitrix_company_id === selectedCompanyId;
            return (
              <button
                className={isSelected ? "companyOption selected" : "companyOption"}
                key={company.bitrix_company_id}
                onClick={() => setSelectedCompanyId(company.bitrix_company_id)}
                type="button"
              >
                <span className="companyName">{companyTitle(company)}</span>
                <span className="companyMeta">
                  {t(locale, `roles.${company.role_code}`)} · {t(locale, `accessStatuses.${company.access_status}`)}
                </span>
                {company.company_country_code ? (
                  <span className="companyCountry">{company.company_country_code}</span>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}

      {selectedCompany ? (
        <div className="selectedCompanyBox">
          <p className="sectionLabel">{t(locale, "companies.currentTitle")}</p>
          <dl>
            <div>
              <dt>{t(locale, "companies.company")}</dt>
              <dd>{companyTitle(selectedCompany)}</dd>
            </div>
            <div>
              <dt>{t(locale, "companies.role")}</dt>
              <dd>{t(locale, `roles.${selectedCompany.role_code}`)}</dd>
            </div>
            {selectedCompany.company_country_code ? (
              <div>
                <dt>{t(locale, "companies.country")}</dt>
                <dd>{selectedCompany.company_country_code}</dd>
              </div>
            ) : null}
          </dl>
          <div className="scopedData">
            <p>
              {scopedDataVersion === contextVersion
                ? t(locale, "companies.dataUpdated")
                : t(locale, "companies.dataRefreshing")}
            </p>
            <span>{t(locale, "companies.scopedDataHint")}</span>
          </div>
        </div>
      ) : null}
    </section>
  );
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
        const currentUser = await requestJson<CurrentUser>("/auth/me");
        if (isMounted) {
          setUser(currentUser);
          setLocale(normalizeLocale(currentUser.language));
          setErrorCode(null);
        }
      } catch {
        try {
          await requestJson("/auth/refresh", { method: "POST", body: "{}" });
          const currentUser = await requestJson<CurrentUser>("/auth/me");
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
      const data = await requestJson<{ user: CurrentUser }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
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
    <CompanyContextProvider
      isAuthenticated={Boolean(user)}
      isClientUser={user?.user_type === "client"}
      requestJson={requestJson}
    >
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
            <nav className="dashboardNav" aria-label={t(locale, "navigation.title")}>
              <Link className="dashboardNavItem" href="/applications">
                <span>{t(locale, "navigation.applications")}</span>
                <small>{t(locale, "navigation.applicationsHint")}</small>
              </Link>
              <Link className="dashboardNavItem" href="/applications/auto/new">
                <span>{t(locale, "navigation.newAutoApplication")}</span>
                <small>{t(locale, "navigation.newAutoApplicationHint")}</small>
              </Link>
              <Link className="dashboardNavItem" href="/applications/cargo/new">
                <span>{t(locale, "navigation.newCargoApplication")}</span>
                <small>{t(locale, "navigation.newCargoApplicationHint")}</small>
              </Link>
              <Link className="dashboardNavItem" href="/policies">
                <span>{t(locale, "navigation.policies")}</span>
                <small>{t(locale, "navigation.policiesHint")}</small>
              </Link>
              <Link className="dashboardNavItem" href="/change-password">
                <span>{t(locale, "navigation.settings")}</span>
                <small>{t(locale, "navigation.settingsHint")}</small>
              </Link>
            </nav>
            <CompanyContextPanel locale={locale} user={user} />
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
    </CompanyContextProvider>
  );
}
