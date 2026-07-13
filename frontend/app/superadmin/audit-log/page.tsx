"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";

import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type AuditEvent = {
  id: string;
  event_type: string;
  category: string;
  actor_user_id: string | null;
  effective_user_id: string | null;
  target_type: string;
  target_id: string | null;
  company_id: number | null;
  application_id: string | null;
  result: string;
  reason_code: string | null;
  correlation_id: string | null;
  created_at: string | null;
};

async function requestJson<T = unknown>(path: string, options: RequestInit = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    credentials: "include",
    headers: { "content-type": "application/json", ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.error_code === "string" ? data.error_code : "UNAUTHORIZED");
  return data as T;
}

function errorMessage(locale: Locale, code: string) {
  const message = t(locale, `errors.${code}`);
  return message === `errors.${code}` ? t(locale, "errors.fallback") : message;
}

function SuperadminAuditLogContent() {
  const searchParams = useSearchParams();
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [items, setItems] = useState<AuditEvent[]>([]);
  const [category, setCategory] = useState("");
  const [eventType, setEventType] = useState("");
  const [result, setResult] = useState("");
  const [actorUserId, setActorUserId] = useState(searchParams.get("actor_user_id") ?? "");
  const [companyId, setCompanyId] = useState("");
  const [correlationId, setCorrelationId] = useState(searchParams.get("correlation_id") ?? "");
  const [delegationId] = useState(searchParams.get("delegation_id") ?? "");
  const [integrationErrorId] = useState(searchParams.get("integration_error_id") ?? "");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  async function loadEvents(nextPage = page) {
    setIsLoading(true);
    setErrorCode(null);
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (eventType) params.set("event_type", eventType);
    if (result) params.set("result", result);
    if (actorUserId) params.set("actor_user_id", actorUserId);
    if (companyId) params.set("company_id", companyId);
    if (correlationId) params.set("correlation_id", correlationId);
    if (delegationId) params.set("delegation_id", delegationId);
    if (integrationErrorId) params.set("integration_error_id", integrationErrorId);
    if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
    if (dateTo) params.set("date_to", new Date(dateTo).toISOString());
    params.set("page", String(nextPage));
    params.set("page_size", "20");
    try {
      const user = await requestJson<{ language: string | null }>("/auth/me");
      setLocale(normalizeLocale(user.language));
      const data = await requestJson<{ items: AuditEvent[]; pagination: { total: number; pages: number; page: number } }>(`/superadmin/audit-events?${params.toString()}`);
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

  useEffect(() => { void loadEvents(1); }, []);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadEvents(1);
  }

  return (
    <main className="shell workspaceShell">
      <section className="workspacePanel adminPanel" aria-busy={isLoading}>
        <div className="sectionHeader">
          <div>
            <p className="sectionLabel">{t(locale, "superadmin.sectionLabel")}</p>
            <h1>{t(locale, "auditLog.title")}</h1>
          </div>
          <Link className="secondaryLink" href="/superadmin/users">{t(locale, "superadmin.usersTitle")}</Link>
        </div>

        <form className="filtersBar adminFilters" onSubmit={applyFilters}>
          <label><span>{t(locale, "auditLog.category")}</span><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="">{t(locale, "superadmin.all")}</option>{["authentication", "access_control", "user_management", "application", "document", "delegation", "impersonation", "integration", "system"].map((value) => <option key={value} value={value}>{t(locale, `auditCategories.${value}`)}</option>)}</select></label>
          <label><span>{t(locale, "auditLog.eventType")}</span><input value={eventType} onChange={(event) => setEventType(event.target.value)} placeholder="login_succeeded" /></label>
          <label><span>{t(locale, "auditLog.result")}</span><select value={result} onChange={(event) => setResult(event.target.value)}><option value="">{t(locale, "superadmin.all")}</option>{["success", "denied", "failed", "cancelled"].map((value) => <option key={value} value={value}>{t(locale, `auditResults.${value}`)}</option>)}</select></label>
          <label><span>{t(locale, "auditLog.actor")}</span><input value={actorUserId} onChange={(event) => setActorUserId(event.target.value)} placeholder="usr_1" /></label>
          <label><span>{t(locale, "auditLog.company")}</span><input inputMode="numeric" value={companyId} onChange={(event) => setCompanyId(event.target.value)} /></label>
          <label><span>{t(locale, "auditLog.correlationId")}</span><input value={correlationId} onChange={(event) => setCorrelationId(event.target.value)} /></label>
          <label><span>{t(locale, "auditLog.dateFrom")}</span><input type="datetime-local" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
          <label><span>{t(locale, "auditLog.dateTo")}</span><input type="datetime-local" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label>
          <button className="primaryButton" type="submit">{t(locale, "superadmin.applyFilters")}</button>
        </form>

        {errorCode ? <p className="errorText">{errorMessage(locale, errorCode)}</p> : null}
        {isLoading ? <p className="stateText">{t(locale, "auditLog.loading")}</p> : null}
        {!isLoading && !errorCode && items.length === 0 ? <p className="stateText">{t(locale, "auditLog.empty")}</p> : null}

        {items.length > 0 ? <div className="tableWrapper"><table className="adminTable"><thead><tr><th>{t(locale, "auditLog.createdAt")}</th><th>{t(locale, "auditLog.category")}</th><th>{t(locale, "auditLog.eventType")}</th><th>{t(locale, "auditLog.actor")}</th><th>{t(locale, "auditLog.result")}</th><th>{t(locale, "auditLog.correlationId")}</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><Link href={`/superadmin/audit-log/${item.id}`}>{item.created_at ?? item.id}</Link></td><td>{t(locale, `auditCategories.${item.category}`)}</td><td>{item.event_type}</td><td>{item.actor_user_id ?? t(locale, "superadmin.missing")}{item.effective_user_id ? ` → ${item.effective_user_id}` : ""}</td><td>{t(locale, `auditResults.${item.result}`)}</td><td>{item.correlation_id ?? t(locale, "superadmin.missing")}</td></tr>)}</tbody></table></div> : null}

        <div className="paginationBar"><button className="secondaryButton" disabled={page <= 1 || isLoading} onClick={() => void loadEvents(page - 1)} type="button">{t(locale, "superadmin.previous")}</button><span>{`${page} / ${pages} · ${total}`}</span><button className="secondaryButton" disabled={page >= pages || isLoading} onClick={() => void loadEvents(page + 1)} type="button">{t(locale, "superadmin.next")}</button></div>
      </section>
    </main>
  );
}

export default function SuperadminAuditLogPage() {
  return (
    <Suspense fallback={<main className="shell workspaceShell"><section className="workspacePanel adminPanel"><p className="stateText">…</p></section></main>}>
      <SuperadminAuditLogContent />
    </Suspense>
  );
}
