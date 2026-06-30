"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CompanyContextProvider, useCompanyContext } from "../../lib/company-context";
import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CurrentUser = {
  id: string;
  role: string;
  user_type: string;
  language: string | null;
  status: string;
};

type ApplicationListItem = {
  id: string;
  application_type: string;
  bitrix_company_id: string;
  title: string;
  portal_status: string;
  status_label: string;
  product_type_code: string | null;
  created_at: string | null;
  updated_at: string | null;
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

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat("ru", { dateStyle: "medium" }).format(new Date(value)) : "";
}

function ApplicationsList({ locale }: { locale: Locale }) {
  const { selectedCompanyId, contextVersion, isLoadingCompanies } = useCompanyContext();
  const [items, setItems] = useState<ApplicationListItem[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadApplications() {
      setItems([]);
      setErrorCode(null);
      if (isLoadingCompanies) {
        return;
      }
      setIsLoading(true);
      const params = new URLSearchParams();
      if (selectedCompanyId) {
        params.set("company_id", selectedCompanyId);
      }
      if (statusFilter) {
        params.set("status", statusFilter);
      }
      if (typeFilter) {
        params.set("type", typeFilter);
      }
      try {
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const data = await requestJson<{ items: ApplicationListItem[] }>(`/applications${suffix}`);
        if (isMounted) {
          setItems(data.items);
        }
      } catch (error) {
        if (isMounted) {
          setErrorCode(error instanceof Error ? error.message : "APPLICATION_ACCESS_DENIED");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadApplications();
    return () => {
      isMounted = false;
    };
  }, [contextVersion, isLoadingCompanies, selectedCompanyId, statusFilter, typeFilter]);

  const statusOptions = useMemo(
    () => [
      "draft",
      "received",
      "in_work",
      "documents_expected",
      "payment_expected",
      "insurer_review",
      "policy_issuing",
      "policy_issued",
      "rejected",
      "cancelled",
      "annulled",
    ],
    [],
  );

  return (
    <section className="workspacePanel">
      <div className="sectionHeader">
        <div>
          <p className="sectionLabel">{t(locale, "applications.sectionLabel")}</p>
          <h1>{t(locale, "applications.title")}</h1>
        </div>
        <Link className="secondaryLink" href="/">
          {t(locale, "applications.backToDashboard")}
        </Link>
      </div>

      <div className="filtersBar">
        <label>
          <span>{t(locale, "applications.status")}</span>
          <select onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}>
            <option value="">{t(locale, "applications.allStatuses")}</option>
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {t(locale, `portalStatuses.${status}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t(locale, "applications.type")}</span>
          <select onChange={(event) => setTypeFilter(event.target.value)} value={typeFilter}>
            <option value="">{t(locale, "applications.allTypes")}</option>
            <option value="auto">{t(locale, "applicationTypes.auto")}</option>
            <option value="cargo">{t(locale, "applicationTypes.cargo")}</option>
          </select>
        </label>
      </div>

      {isLoading ? <p className="stateText">{t(locale, "applications.loading")}</p> : null}
      {errorCode ? (
        <p className="errorText" role="alert">
          {errorMessage(locale, errorCode)}
        </p>
      ) : null}
      {!isLoading && !errorCode && items.length === 0 ? (
        <p className="stateText">{t(locale, "applications.empty")}</p>
      ) : null}

      {items.length > 0 ? (
        <div className="applicationList">
          {items.map((item) => (
            <Link className="applicationRow" href={`/applications/${item.id}`} key={item.id}>
              <span>
                <strong>{item.title}</strong>
                <small>{t(locale, `applicationTypes.${item.application_type}`)}</small>
              </span>
              <span className="statusBadge">{t(locale, `portalStatuses.${item.portal_status}`)}</span>
              <span className="dateStack">
                <small>{t(locale, "applications.updatedAt")}</small>
                {formatDate(item.updated_at)}
              </span>
            </Link>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export default function ApplicationsPage() {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      const currentUser = await requestJson<CurrentUser>("/auth/me");
      setUser(currentUser);
      setLocale(normalizeLocale(currentUser.language));
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "UNAUTHORIZED");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  return (
    <CompanyContextProvider
      isAuthenticated={Boolean(user)}
      isClientUser={user?.user_type === "client"}
      requestJson={requestJson}
    >
      <main className="shell workspaceShell">
        {isLoading ? <p className="stateText">{t(locale, "auth.checking")}</p> : null}
        {!isLoading && errorCode ? (
          <section className="workspacePanel">
            <p className="errorText" role="alert">
              {errorMessage(locale, errorCode)}
            </p>
          </section>
        ) : null}
        {!isLoading && user ? <ApplicationsList locale={locale} /> : null}
      </main>
    </CompanyContextProvider>
  );
}
