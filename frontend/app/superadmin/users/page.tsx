"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CurrentUser = {
  id: string;
  role: string;
  user_type: string;
  language: string | null;
  status: string;
};

type AdminUser = {
  id: string;
  email: string;
  display_name: string | null;
  role_code: string | null;
  roles: string[];
  user_type: string;
  status: string;
  bitrix_contact_id: number | null;
  is_partner: boolean;
  is_blocked: boolean;
  has_integration_errors: boolean;
  company_links: Array<{ bitrix_company_id: string; company_title: string | null; access_status: string; bitrix_link_status: string }>;
  created_at: string | null;
  last_login_at: string | null;
};

async function requestJson<T = unknown>(path: string, options: RequestInit = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    credentials: "include",
    headers: { "content-type": "application/json", ...options.headers },
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

function formatDate(locale: Locale, value: string | null) {
  if (!value) {
    return "";
  }
  return new Intl.DateTimeFormat(locale === "ka" ? "ka-GE" : "ru-RU", { dateStyle: "medium" }).format(
    new Date(value),
  );
}

export default function SuperadminUsersPage() {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [items, setItems] = useState<AdminUser[]>([]);
  const [role, setRole] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [hasBitrixId, setHasBitrixId] = useState("");
  const [hasErrors, setHasErrors] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  async function loadUsers() {
    setIsLoading(true);
    setErrorCode(null);
    const params = new URLSearchParams();
    if (role) params.set("role", role);
    if (statusFilter) params.set("status", statusFilter);
    if (email) params.set("email", email);
    if (name) params.set("name", name);
    if (companyId) params.set("company_id", companyId);
    if (hasBitrixId) params.set("has_bitrix_id", hasBitrixId);
    if (hasErrors) params.set("has_integration_errors", hasErrors);
    params.set("sort_by", sortBy);
    params.set("sort_dir", sortDir);
    params.set("page", String(page));
    params.set("page_size", "10");
    const suffix = params.toString() ? `?${params.toString()}` : "";
    try {
      const data = await requestJson<{ items: AdminUser[]; pagination: { total: number; pages: number; page: number } }>(`/superadmin/users${suffix}`);
      setItems(data.items);
      setPages(data.pagination.pages || 1);
      setPage(data.pagination.page);
      setTotal(data.pagination.total);
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "SUPERADMIN_REQUIRED");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    let isMounted = true;
    async function loadCurrentUser() {
      try {
        const user = await requestJson<CurrentUser>("/auth/me");
        if (isMounted) {
          setLocale(normalizeLocale(user.language));
        }
      } catch {
        if (isMounted) {
          setErrorCode("UNAUTHORIZED");
        }
      }
      if (isMounted) {
        await loadUsers();
      }
    }
    void loadCurrentUser();
    return () => {
      isMounted = false;
    };
    // Initial load only; filters submit explicitly.
  }, []);

  useEffect(() => {
    if (!isLoading) {
      void loadUsers();
    }
  }, [page]);

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    void loadUsers();
  }

  return (
    <main className="shell workspaceShell">
      <section className="workspacePanel adminPanel" aria-busy={isLoading}>
        <div className="sectionHeader">
          <div>
            <p className="sectionLabel">{t(locale, "superadmin.sectionLabel")}</p>
            <h1>{t(locale, "superadmin.usersTitle")}</h1>
          </div>
          <Link className="secondaryLink" href="/superadmin/integration-errors">
            {t(locale, "superadmin.integrationErrors")}
          </Link>
        </div>

        <form className="filtersBar adminFilters" onSubmit={submitFilters}>
          <label>
            <span>{t(locale, "superadmin.role")}</span>
            <select onChange={(event) => setRole(event.target.value)} value={role}>
              <option value="">{t(locale, "superadmin.all")}</option>
              {["client_executor", "client_admin", "client_viewer", "partner", "superadmin"].map((value) => (
                <option key={value} value={value}>
                  {t(locale, `roles.${value}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t(locale, "superadmin.status")}</span>
            <select onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}>
              <option value="">{t(locale, "superadmin.all")}</option>
              {["pending", "active", "blocked"].map((value) => (
                <option key={value} value={value}>
                  {t(locale, `userStatuses.${value}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t(locale, "app.email")}</span>
            <input onChange={(event) => setEmail(event.target.value)} value={email} />
          </label>
          <label>
            <span>{t(locale, "superadmin.name")}</span>
            <input onChange={(event) => setName(event.target.value)} value={name} />
          </label>
          <label>
            <span>{t(locale, "superadmin.companyId")}</span>
            <input inputMode="numeric" onChange={(event) => setCompanyId(event.target.value)} value={companyId} />
          </label>
          <label>
            <span>{t(locale, "superadmin.bitrix24Id")}</span>
            <select onChange={(event) => setHasBitrixId(event.target.value)} value={hasBitrixId}>
              <option value="">{t(locale, "superadmin.all")}</option>
              <option value="true">{t(locale, "superadmin.present")}</option>
              <option value="false">{t(locale, "superadmin.missing")}</option>
            </select>
          </label>
          <label>
            <span>{t(locale, "superadmin.integrationErrors")}</span>
            <select onChange={(event) => setHasErrors(event.target.value)} value={hasErrors}>
              <option value="">{t(locale, "superadmin.all")}</option>
              <option value="true">{t(locale, "superadmin.present")}</option>
              <option value="false">{t(locale, "superadmin.missing")}</option>
            </select>
          </label>

          <label>
            <span>{t(locale, "superadmin.sortBy")}</span>
            <select onChange={(event) => setSortBy(event.target.value)} value={sortBy}>
              <option value="created_at">{t(locale, "superadmin.createdAt")}</option>
              <option value="last_login_at">{t(locale, "superadmin.lastLoginAt")}</option>
            </select>
          </label>
          <label>
            <span>{t(locale, "superadmin.sortBy")}</span>
            <select onChange={(event) => setSortDir(event.target.value)} value={sortDir}>
              <option value="desc">↓</option>
              <option value="asc">↑</option>
            </select>
          </label>
          <button className="primaryButton" type="submit">
            {t(locale, "superadmin.applyFilters")}
          </button>
        </form>

        {errorCode ? (
          <p className="errorText" role="alert">
            {errorMessage(locale, errorCode)}
          </p>
        ) : null}
        {isLoading ? <p className="stateText">{t(locale, "superadmin.loadingUsers")}</p> : null}
        {!isLoading && !errorCode && items.length === 0 ? (
          <p className="stateText">{t(locale, "superadmin.emptyUsers")}</p>
        ) : null}

        {!isLoading && !errorCode ? <p className="stateText">{total} · {t(locale, "superadmin.page")} {page}/{pages}</p> : null}

        {items.length > 0 ? (
          <div className="adminTable">
            {items.map((item) => (
              <Link className="adminRow adminUserRow" href={`/superadmin/users/${item.id}`} key={item.id}>
                <span>
                  <strong>{item.email}</strong>
                  <small>{item.display_name || item.id}</small>
                </span>
                <span>{item.roles.map((value) => t(locale, `roles.${value}`)).join(", ") || item.user_type}</span>
                <span className={`statusBadge status-${item.status}`}>{t(locale, `userStatuses.${item.status}`)}</span>
                <span>{item.bitrix_contact_id ?? t(locale, "superadmin.missing")}</span>
                <span>{item.company_links.length}</span>
                <span>{item.company_links.map((link) => link.company_title || link.bitrix_company_id).join(", ")}</span>
                <span>{item.bitrix_contact_id ? t(locale, "superadmin.present") : t(locale, "superadmin.missing")}</span>
                <span>{item.has_integration_errors ? t(locale, "superadmin.present") : t(locale, "superadmin.missing")}</span>
                <span>{formatDate(locale, item.created_at)}</span>
              </Link>
            ))}
          </div>
        ) : null}

        {!isLoading && !errorCode ? (
          <div className="filtersBar">
            <button className="secondaryButton" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} type="button">
              {t(locale, "superadmin.previous")}
            </button>
            <button className="secondaryButton" disabled={page >= pages} onClick={() => setPage((value) => value + 1)} type="button">
              {t(locale, "superadmin.next")}
            </button>
          </div>
        ) : null}
      </section>
    </main>
  );
}
