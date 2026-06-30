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
  const [isLoading, setIsLoading] = useState(true);

  async function loadErrors() {
    setIsLoading(true);
    setErrorCode(null);
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    if (objectType) params.set("object_type", objectType);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    try {
      const user = await requestJson<{ language: string | null }>("/auth/me");
      setLocale(normalizeLocale(user.language));
      const data = await requestJson<{ items: IntegrationError[] }>(`/superadmin/integration-errors${suffix}`);
      setItems(data.items);
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "SUPERADMIN_REQUIRED");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadErrors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadErrors();
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
              {["pending", "failed", "retrying", "resolved"].map((value) => (
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
          <button className="primaryButton" type="submit">{t(locale, "superadmin.applyFilters")}</button>
        </form>

        {errorCode ? <p className="errorText">{errorMessage(locale, errorCode)}</p> : null}
        {isLoading ? <p className="stateText">{t(locale, "superadmin.loadingErrors")}</p> : null}
        {!isLoading && !errorCode && items.length === 0 ? (
          <p className="stateText">{t(locale, "superadmin.emptyErrors")}</p>
        ) : null}

        {items.length > 0 ? (
          <div className="adminTable">
            {items.map((item) => (
              <div className="adminRow integrationErrorRow" key={item.id}>
                <span>
                  <strong>{item.error_code}</strong>
                  <small>{item.safe_message || item.operation}</small>
                </span>
                <span>{t(locale, `integrationObjectTypes.${item.object_type}`)}</span>
                <span>{item.object_id ?? t(locale, "superadmin.missing")}</span>
                <span>{item.bitrix_entity_id ?? t(locale, "superadmin.missing")}</span>
                <span className={`statusBadge status-${item.status}`}>{t(locale, `integrationErrorStatuses.${item.status}`)}</span>
                {item.object_url ? (
                  <Link className="secondaryLink" href={item.object_url}>{t(locale, "superadmin.openObject")}</Link>
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
      </section>
    </main>
  );
}
