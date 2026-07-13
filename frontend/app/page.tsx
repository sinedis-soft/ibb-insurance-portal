"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  type CompanyAccess,
  CompanyContextProvider,
  useCompanyContext,
} from "../lib/company-context";
import { Locale, DEFAULT_LOCALE, normalizeLocale, t } from "../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CurrentUser = {
  id: string;
  display_name?: string | null;
  role: string;
  user_type: string;
  language: string | null;
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

function companyTitle(locale: Locale, company: CompanyAccess) {
  return company.company_title?.trim() || t(locale, "companies.unknownTitle");
}

function userDisplayName(locale: Locale, user: CurrentUser) {
  return user.display_name?.trim() || t(locale, "auth.userFallback");
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
                <span className="companyName">{companyTitle(locale, company)}</span>
                <span className="companyMeta">
                  {t(locale, `roles.${company.role_code}`)} / {t(locale, `accessStatuses.${company.access_status}`)}
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
              <dd>{companyTitle(locale, selectedCompany)}</dd>
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
type DashboardApplication = {
  id: string;
  application_number?: string | null;
  title?: string | null;
  application_type?: string | null;
  product_type?: string | null;
  portal_status?: string | null;
  status?: string | null;
  created_at?: string | null;
  submitted_at?: string | null;
};

type DashboardPolicy = {
  id: string;
  policy_number?: string | null;
  product_type?: string | null;
  insured_object?: string | null;
  status?: string | null;
  valid_to?: string | null;
  expires_at?: string | null;
};

type DashboardDocument = {
  id: string;
  filename?: string | null;
  document_type?: string | null;
  created_at?: string | null;
  uploaded_at?: string | null;
  related_number?: string | null;
};

type DashboardData = {
  applications: DashboardApplication[];
  policies: DashboardPolicy[];
  documents: DashboardDocument[];
};

function normalizeList<T>(data: unknown, keys: string[]): T[] {
  if (Array.isArray(data)) {
    return data as T[];
  }

  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    for (const key of keys) {
      const value = record[key];
      if (Array.isArray(value)) {
        return value as T[];
      }
    }
  }

  return [];
}

function formatDashboardDate(value?: string | null) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function daysUntil(value?: string | null) {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  date.setHours(0, 0, 0, 0);

  return Math.ceil((date.getTime() - today.getTime()) / 86_400_000);
}

function applicationStatus(application: DashboardApplication) {
  return application.portal_status || application.status || "unknown";
}

function applicationDate(application: DashboardApplication) {
  return application.submitted_at || application.created_at || null;
}

function policyExpiryDate(policy: DashboardPolicy) {
  return policy.valid_to || policy.expires_at || null;
}

function isActivePolicy(policy: DashboardPolicy) {
  const status = policy.status?.toLowerCase();
  if (status && ["active", "issued", "policy_issued"].includes(status)) {
    return true;
  }

  const expiryDays = daysUntil(policyExpiryDate(policy));
  return expiryDays !== null && expiryDays >= 0;
}

function isApplicationInProgress(application: DashboardApplication) {
  const status = applicationStatus(application);
  return !["draft", "policy_issued", "issued", "rejected", "cancelled", "canceled"].includes(status);
}

function isAwaitingApproval(application: DashboardApplication) {
  const status = applicationStatus(application);
  return ["awaiting_approval", "pending_approval", "client_approval_required"].includes(status);
}


function StatCard({
  value,
  label,
  hint,
  href,
}: {
  value: number;
  label: string;
  hint: string;
  href: string;
}) {
  return (
    <article className="portalStatCard">
      <div className="portalStatIcon" aria-hidden="true" />
      <strong>{value}</strong>
      <span>{label}</span>
      <Link href={href} className="portalStatLink">
        {hint} →
      </Link>
    </article>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`statusBadge status-${status}`}>{status}</span>;
}

function ClientDashboard({
  locale,
  user,
  onLogout,
  isSubmitting,
}: {
  locale: Locale;
  user: CurrentUser;
  onLogout: () => void;
  isSubmitting: boolean;
}) {
  const {
    availableCompanies,
    selectedCompany,
    selectedCompanyId,
    isLoadingCompanies,
    setSelectedCompanyId,
  } = useCompanyContext();

  const [dashboardData, setDashboardData] = useState<DashboardData>({
    applications: [],
    policies: [],
    documents: [],
  });
  const [dashboardErrorCode, setDashboardErrorCode] = useState<string | null>(null);
  const [isDashboardLoading, setIsDashboardLoading] = useState(false);

  useEffect(() => {
    if (!selectedCompanyId) {
      setDashboardData({ applications: [], policies: [], documents: [] });
      return;
    }

    let isMounted = true;

    async function loadDashboardData() {
      setIsDashboardLoading(true);
      setDashboardErrorCode(null);

      const companyQuery = `company_id=${encodeURIComponent(String(selectedCompanyId))}`;

      try {
        const [applicationsResponse, policiesResponse, documentsResponse] = await Promise.all([
          requestJson<unknown>(`/applications?${companyQuery}`),
          requestJson<unknown>(`/policies?${companyQuery}`),
          requestJson<unknown>(`/documents?${companyQuery}`).catch(() => ({ documents: [] })),
        ]);

        if (!isMounted) {
          return;
        }

        setDashboardData({
          applications: normalizeList<DashboardApplication>(applicationsResponse, [
            "applications",
            "items",
            "results",
          ]),
          policies: normalizeList<DashboardPolicy>(policiesResponse, [
            "policies",
            "items",
            "results",
          ]),
          documents: normalizeList<DashboardDocument>(documentsResponse, [
            "documents",
            "items",
            "results",
          ]),
        });
      } catch (error) {
        if (isMounted) {
          setDashboardErrorCode(error instanceof Error ? error.message : "DASHBOARD_LOAD_FAILED");
        }
      } finally {
        if (isMounted) {
          setIsDashboardLoading(false);
        }
      }
    }

    void loadDashboardData();

    return () => {
      isMounted = false;
    };
  }, [selectedCompanyId]);

  const activePolicies = useMemo(
    () => dashboardData.policies.filter(isActivePolicy),
    [dashboardData.policies],
  );

  const applicationsInProgress = useMemo(
    () => dashboardData.applications.filter(isApplicationInProgress),
    [dashboardData.applications],
  );

  const expiringPolicies = useMemo(
    () =>
      dashboardData.policies
        .map((policy) => ({ policy, days: daysUntil(policyExpiryDate(policy)) }))
        .filter((item): item is { policy: DashboardPolicy; days: number } => {
          return item.days !== null && item.days >= 0 && item.days <= 45;
        })
        .sort((a, b) => a.days - b.days),
    [dashboardData.policies],
  );

  const awaitingApproval = useMemo(
    () => dashboardData.applications.filter(isAwaitingApproval),
    [dashboardData.applications],
  );

  const recentApplications = useMemo(
    () =>
      [...dashboardData.applications]
        .sort((a, b) => {
          const left = new Date(applicationDate(a) ?? 0).getTime();
          const right = new Date(applicationDate(b) ?? 0).getTime();
          return right - left;
        })
        .slice(0, 5),
    [dashboardData.applications],
  );

  const recentDocuments = useMemo(
    () =>
      [...dashboardData.documents]
        .sort((a, b) => {
          const left = new Date(a.uploaded_at || a.created_at || 0).getTime();
          const right = new Date(b.uploaded_at || b.created_at || 0).getTime();
          return right - left;
        })
        .slice(0, 5),
    [dashboardData.documents],
  );

  return (
    <div className="portalDashboard">
      <header className="portalHeader">
        <Link href="/" className="portalLogo" aria-label="IBB">
          <span className="portalLogoMark">◎</span>
          <span>IBB</span>
        </Link>

        <div className="portalHeaderCenter">
          {user.user_type === "client" && availableCompanies.length > 0 ? (
            <label className="companySelectorLabel">
              <span className="srOnly">{t(locale, "companies.contextLabel")}</span>
              <select
                className="companySelectorSelect"
                disabled={isLoadingCompanies}
                onChange={(event) => setSelectedCompanyId(event.target.value)}
                value={selectedCompanyId ?? ""}
              >
                {availableCompanies.map((company) => (
                  <option key={company.bitrix_company_id} value={company.bitrix_company_id}>
                    {companyTitle(locale, company)}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <span className="companySelectorReadonly">
              {user.user_type === "partner"
                ? t(locale, "companies.partnerScopeTitle")
                : t(locale, "companies.empty")}
            </span>
          )}
        </div>

        <div className="portalHeaderActions">
          <div className="userMenu">
            <span className="userAvatar">
              {userDisplayName(locale, user).slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{userDisplayName(locale, user)}</strong>
              <small>{t(locale, `roles.${user.role}`)}</small>
            </div>
          </div>

          <button className="secondaryButton" disabled={isSubmitting} onClick={onLogout} type="button">
            {t(locale, "auth.logout")}
          </button>
        </div>
      </header>

      <section className="portalHero">
        <div>
          <h1>
            {t(locale, "auth.welcomeBack")}, {userDisplayName(locale, user)}
          </h1>

          <p>
            {selectedCompany
              ? companyTitle(locale, selectedCompany)
              : t(locale, "companies.scopedDataHint")}
          </p>

          <div className="heroActions">
            <Link className="primaryActionButton" href="/applications/auto/new">
              {t(locale, "navigation.newAutoApplication")}
            </Link>
            <Link className="secondaryLink" href="/applications/cargo/new">
              {t(locale, "navigation.newCargoApplication")}
            </Link>
          </div>
        </div>
      </section>

      {dashboardErrorCode ? (
        <p className="errorText dashboardState" role="alert">
          {errorMessage(locale, dashboardErrorCode)}
        </p>
      ) : null}

      {isDashboardLoading ? (
        <p className="stateText dashboardState">
          {t(locale, "companies.dataRefreshing")}
        </p>
      ) : null}

      <section className="portalStatsGrid" aria-label="Dashboard summary">
        <StatCard
          value={activePolicies.length}
          label={t(locale, "navigation.policies")}
          hint={t(locale, "navigation.viewAll")}
          href="/policies"
        />
        <StatCard
          value={applicationsInProgress.length}
          label={t(locale, "navigation.applications")}
          hint={t(locale, "navigation.viewAll")}
          href="/applications"
        />
        <StatCard
          value={expiringPolicies.length}
          label={t(locale, "dashboard.expiringSoon")}
          hint={t(locale, "dashboard.viewDetails")}
          href="/policies?expiring=true"
        />
        <StatCard
          value={awaitingApproval.length}
          label={t(locale, "dashboard.awaitingApproval")}
          hint={t(locale, "dashboard.viewItems")}
          href="/applications?status=awaiting_approval"
        />
      </section>

      <section className="portalDashboardGrid">
        <article className="dashboardCard recentApplicationsCard">
          <div className="dashboardCardHeader">
            <h2>{t(locale, "dashboard.recentApplications")}</h2>
            <Link href="/applications">{t(locale, "navigation.viewAll")} →</Link>
          </div>

          {recentApplications.length > 0 ? (
            <div className="dashboardTable">
              <div className="dashboardTableHead applicationDashboardRow">
                <span>{t(locale, "dashboard.application")}</span>
                <span>{t(locale, "dashboard.type")}</span>
                <span>{t(locale, "dashboard.submitted")}</span>
                <span>{t(locale, "dashboard.status")}</span>
              </div>

              {recentApplications.map((application) => (
                <Link
                  className="applicationDashboardRow dashboardTableRow"
                  href={`/applications/${application.id}`}
                  key={application.id}
                >
                  <span>
                    <strong>{application.application_number || application.id}</strong>
                    <small>{application.title || application.product_type || "—"}</small>
                  </span>
                  <span>{application.application_type || application.product_type || "—"}</span>
                  <span>{formatDashboardDate(applicationDate(application))}</span>
                  <StatusBadge status={applicationStatus(application)} />
                </Link>
              ))}
            </div>
          ) : (
            <p className="stateText">{t(locale, "dashboard.noRecentApplications")}</p>
          )}

          <Link className="dashboardCardFooterLink" href="/applications">
            {t(locale, "dashboard.viewAllApplications")} →
          </Link>
        </article>

        <article className="dashboardCard expiringPoliciesCard">
          <div className="dashboardCardHeader">
            <h2>{t(locale, "dashboard.expiringPolicies")}</h2>
            <Link href="/policies">{t(locale, "navigation.viewAll")} →</Link>
          </div>

          {expiringPolicies.length > 0 ? (
            <div className="expiringPolicyList">
              {expiringPolicies.slice(0, 3).map(({ policy, days }) => (
                <div className="expiringPolicyItem" key={policy.id}>
                  <div>
                    <strong>{policy.product_type || policy.insured_object || "—"}</strong>
                    <small>{policy.policy_number || policy.id}</small>
                    <span>{t(locale, "dashboard.expiresInDays").replace("{days}", String(days))}</span>
                  </div>

                  <Link className="smallOutlineButton" href={`/policies/${policy.id}`}>
                    {t(locale, "dashboard.renew")}
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <p className="stateText">{t(locale, "dashboard.noExpiringPolicies")}</p>
          )}

          <Link className="dashboardCardFooterLink" href="/policies?expiring=true">
            {t(locale, "dashboard.viewAllExpiring")} →
          </Link>
        </article>

        <article className="dashboardCard recentDocumentsCard">
          <div className="dashboardCardHeader">
            <h2>{t(locale, "dashboard.recentDocuments")}</h2>
            <Link href="/applications">{t(locale, "navigation.viewAll")} →</Link>
          </div>

          {recentDocuments.length > 0 ? (
            <div className="documentDashboardList">
              {recentDocuments.map((document) => (
                <div className="documentDashboardItem" key={document.id}>
                  <span className="documentIcon">□</span>
                  <div>
                    <strong>{document.filename || document.document_type || "—"}</strong>
                    <small>{document.related_number || document.document_type || "—"}</small>
                  </div>
                  <span>{formatDashboardDate(document.uploaded_at || document.created_at)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="stateText">{t(locale, "dashboard.noRecentDocuments")}</p>
          )}
        </article>

        <article className="dashboardCard quickActionsCard">
          <h2>{t(locale, "dashboard.quickActions")}</h2>

          <nav className="quickActionsList">
            <Link href="/applications/auto/new">{t(locale, "navigation.newAutoApplication")}</Link>
            <Link href="/applications/cargo/new">{t(locale, "navigation.newCargoApplication")}</Link>
            <Link href="/applications">{t(locale, "dashboard.uploadDocuments")}</Link>
            <Link href="/policies">{t(locale, "dashboard.requestPolicyByEmail")}</Link>
            <Link href="/support">{t(locale, "dashboard.contactBroker")}</Link>
          </nav>
        </article>
      </section>

      <section className="dashboardHelpBanner">
        <div>
          <span className="helpBannerLogo">◎</span>
          <div>
            <h2>{t(locale, "dashboard.needHelp")}</h2>
            <p>{t(locale, "dashboard.needHelpText")}</p>
          </div>
        </div>

        <Link className="secondaryLink" href="/support">
          {t(locale, "dashboard.contactUs")} →
        </Link>
      </section>

      <footer className="portalFooter">
        <Link href="/">IBB</Link>
        <nav>
          <Link href="#">{t(locale, "footer.about")}</Link>
          <Link href="#">{t(locale, "footer.compliance")}</Link>
          <Link href="#">{t(locale, "footer.privacy")}</Link>
          <Link href="#">{t(locale, "footer.terms")}</Link>
        </nav>
        <span>© {new Date().getFullYear()} IBB. {t(locale, "footer.rights")}</span>
      </footer>
    </div>
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
      <main className={user ? "shell dashboardShell" : "shell"}>
        <section className={user ? "dashboardPagePanel" : "authPanel"} aria-busy={isLoading}>
        {!user ? (
          <>
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
  </>
) : null}

        {isLoading ? <p className="stateText">{t(locale, "auth.checking")}</p> : null}

        {!isLoading && user ? (
          <ClientDashboard locale={locale} user={user} onLogout={handleLogout} isSubmitting={isSubmitting} />
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
