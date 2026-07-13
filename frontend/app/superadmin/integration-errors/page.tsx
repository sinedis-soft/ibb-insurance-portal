"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type IntegrationError = {
  id: string;
  object_type: string;
  object_id: string | null;
  bitrix_entity_type: string | null;
  bitrix_entity_id: number | null;
  operation: string;
  status: string;
  error_code: string;
  safe_message: string | null;
  retry_count: number;
  last_attempt_at: string | null;
  correlation_id: string | null;
  retry_supported: boolean;
  object_url: string | null;
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

export default function SuperadminIntegrationErrorsPage() {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [items, setItems] = useState<IntegrationError[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [objectType, setObjectType] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [operation, setOperation] = useState("");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  async function loadErrors() {
    setIsLoading(true);
    setErrorCode(null);
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    if (objectType) params.set("object_type", objectType);
    if (operation) params.set("operation", operation);
    params.set("page", String(page));
    params.set("page_size", "10");
    const suffix = params.toString() ? `?${params.toString()}` : "";
    try {
      const user = await requestJson<{ language: string | null }>("/auth/me");
      setLocale(normalizeLocale(user.language));
      const data = await requestJson<{ items: IntegrationError[]; pagination: { total: number; pages: number; page: number } }>(`/superadmin/integration-errors${suffix}`);
      setItems(data.items);
      setPage(data.pagination.page);
      setPages(data.pagination.pages || 1);
      setTotal(data.pagination.total);
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "SUPERADMIN_REQUIRED");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadErrors();
  }, []);

  useEffect(() => {
    if (!isLoading) {
      void loadErrors();
    }
  }, [page]);

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    void loadErrors();
  }

  async function retryError(id: string) {
    await requestJson(`/superadmin/integration-errors/${id}/retry`, { method: "POST", body: "{}" });
    await loadErrors();
  }

  async function markResolved(id: string) {
    await requestJson(`/superadmin/integration-errors/${id}/mark-resolved`, { method: "POST", body: "{}" });
    await loadErrors();
  }

  return (
    <main className="shell workspaceShell">
      <section className="workspacePanel adminPanel" aria-busy={isLoading}>
        <div className="sectionHeader">
          <div>
            <p className="sectionLabel">{t(locale, "superadmin.sectionLabel")}</p>
            <h1>{t(locale, "superadmin.integrationErrors")}</h1>
          </div>
          <Link className="secondaryLink" href="/superadmin/users">
            {t(locale, "superadmin.usersTitle")}
          </Link>
        </div>

        <form className="filtersBar adminFilters" onSubmit={submitFilters}>
          <label>
            <span>{t(locale, "superadmin.status")}</span>
            <select onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}>
              <option value="">{t(locale, "superadmin.all")}</option>
              {["pending_retry", "retrying", "requires_attention", "resolved", "cancelled"].map((value) => (
                <option key={value} value={value}>
                  {t(locale, `integrationErrorStatuses.${value}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t(locale, "superadmin.objectType")}</span>
            <select onChange={(event) => setObjectType(event.target.value)} value={objectType}>
              <option value="">{t(locale, "superadmin.all")}</option>
              {["user", "company", "application", "partner_client_request", "document", "bitrix"].map((value) => (
                <option key={value} value={value}>
                  {t(locale, `integrationObjectTypes.${value}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t(locale, "superadmin.syncStatus")}</span>
            <select onChange={(event) => setOperation(event.target.value)} value={operation}>
              <option value="">{t(locale, "superadmin.all")}</option>
              {["create_deal", "update_deal", "sync_company", "sync_contact", "transfer_document", "process_webhook", "sync_policy"].map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <button className="primaryButton" type="submit">{t(locale, "superadmin.applyFilters")}</button>
        </form>

        {errorCode ? <p className="errorText">{errorMessage(locale, errorCode)}</p> : null}
        {isLoading ? <p className="stateText">{t(locale, "superadmin.loadingErrors")}</p> : null}
        {!isLoading && !errorCode && items.length === 0 ? (
          <p className="stateText">{t(locale, "superadmin.emptyErrors")}</p>
        ) : null}

        {!isLoading && !errorCode ? <p className="stateText">{total} · {t(locale, "superadmin.page")} {page}/{pages}</p> : null}

        {items.length > 0 ? (
          <div className="adminTable">
            {items.map((item) => (
              <div className="adminRow integrationErrorRow" key={item.id}>
                <span>
                  <Link href={`/superadmin/integration-errors/${item.id}`}><strong>{item.error_code}</strong></Link>
                  <small>{item.safe_message || item.operation}</small>
                </span>
                <span>{t(locale, `integrationObjectTypes.${item.object_type}`)}</span>
                <span>{item.object_id ?? t(locale, "superadmin.missing")}</span>
                <span>{item.bitrix_entity_id ?? t(locale, "superadmin.missing")}</span>
                <span>{item.correlation_id ?? t(locale, "superadmin.missing")}</span>
                <span className={`statusBadge status-${item.status}`}>{t(locale, `integrationErrorStatuses.${item.status}`)}</span>
                {item.object_url ? (
                  <Link className="secondaryLink" href={item.object_url}>{t(locale, "superadmin.openObject")}</Link>
                ) : null}
                {item.retry_supported ? (
                  <button className="secondaryButton" onClick={() => void retryError(item.id)} type="button">
                    {t(locale, "superadmin.retry")}
                  </button>
                ) : null}
                <button
                  className="secondaryButton"
                  disabled={item.status === "resolved"}
                  onClick={() => void markResolved(item.id)}
                  type="button"
                >
                  {t(locale, "superadmin.markResolved")}
                </button>
              </div>
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
