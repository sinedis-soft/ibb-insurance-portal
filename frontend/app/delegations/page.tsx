"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Delegation = {
  id: string;
  company_id: string;
  delegator_user_id: string;
  delegate_user_id: string;
  starts_at: string | null;
  ends_at: string | null;
  status: string;
  reason: string | null;
  items: Array<{ application_id: string; status: string }>;
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

export default function DelegationsPage() {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [items, setItems] = useState<Delegation[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [delegateId, setDelegateId] = useState("");
  const [applicationIds, setApplicationIds] = useState("");
  const [allActive, setAllActive] = useState(false);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [reason, setReason] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function loadDelegations() {
    setErrorCode(null);
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    try {
      const user = await requestJson<{ language: string | null }>("/auth/me");
      setLocale(normalizeLocale(user.language));
      const data = await requestJson<{ items: Delegation[] }>(`/delegations${suffix}`);
      setItems(data.items);
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "UNAUTHORIZED");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => { void loadDelegations(); }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = {
      company_id: Number(companyId),
      delegate_user_id: delegateId,
      application_ids: applicationIds.split(",").map((value) => value.trim()).filter(Boolean),
      all_active: allActive,
      starts_at: new Date(startsAt).toISOString(),
      ends_at: new Date(endsAt).toISOString(),
      reason,
      idempotency_key: `ui-${companyId}-${delegateId}-${startsAt}-${endsAt}`,
    };
    try {
      await requestJson("/delegations", { method: "POST", body: JSON.stringify(payload) });
      setApplicationIds("");
      await loadDelegations();
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "DELEGATION_VALIDATION_FAILED");
    }
  }

  return (
    <main className="shell workspaceShell">
      <section className="workspacePanel">
        <div className="sectionHeader">
          <div>
            <p className="sectionLabel">{t(locale, "delegations.sectionLabel")}</p>
            <h1>{t(locale, "delegations.title")}</h1>
          </div>
          <Link className="secondaryLink" href="/applications">{t(locale, "applications.backToList")}</Link>
        </div>
        {errorCode ? <p className="errorText" role="alert">{errorMessage(locale, errorCode)}</p> : null}
        {isLoading ? <p className="stateText">{t(locale, "delegations.loading")}</p> : null}

        <form className="portalForm" onSubmit={(event) => void create(event)}>
          <h2>{t(locale, "delegations.createTitle")}</h2>
          <div className="formGrid">
            <label><span>{t(locale, "delegations.companyId")}</span><input required inputMode="numeric" onChange={(event) => setCompanyId(event.target.value)} value={companyId} /></label>
            <label><span>{t(locale, "delegations.delegateUserId")}</span><input required onChange={(event) => setDelegateId(event.target.value)} placeholder="usr_123" value={delegateId} /></label>
            <label><span>{t(locale, "delegations.applicationIds")}</span><input disabled={allActive} onChange={(event) => setApplicationIds(event.target.value)} placeholder="app_1, app_2" value={applicationIds} /></label>
            <label><span>{t(locale, "delegations.allActive")}</span><input checked={allActive} onChange={(event) => setAllActive(event.target.checked)} type="checkbox" /></label>
            <label><span>{t(locale, "delegations.startsAt")}</span><input required onChange={(event) => setStartsAt(event.target.value)} type="datetime-local" value={startsAt} /></label>
            <label><span>{t(locale, "delegations.endsAt")}</span><input required onChange={(event) => setEndsAt(event.target.value)} type="datetime-local" value={endsAt} /></label>
          </div>
          <label><span>{t(locale, "delegations.reason")}</span><textarea onChange={(event) => setReason(event.target.value)} value={reason} /></label>
          <p className="stateText">{t(locale, "delegations.maxPeriodWarning")}</p>
          <button className="primaryButton" type="submit">{t(locale, "delegations.create")}</button>
        </form>

        <div className="filtersBar">
          <select onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}>
            <option value="">{t(locale, "delegations.allStatuses")}</option>
            {["active", "scheduled", "expired", "cancelled", "terminated", "failed"].map((value) => <option key={value} value={value}>{t(locale, `delegationStatuses.${value}`)}</option>)}
          </select>
          <button className="secondaryButton" onClick={() => void loadDelegations()} type="button">{t(locale, "delegations.applyFilters")}</button>
        </div>

        {!isLoading && items.length === 0 ? <p className="stateText">{t(locale, "delegations.empty")}</p> : null}
        <div className="applicationList">
          {items.map((item) => (
            <Link className="applicationRow" href={`/delegations/${item.id}`} key={item.id}>
              <span><strong>{item.id}</strong><small>{item.items.map((delegated) => delegated.application_id).join(", ")}</small></span>
              <span className="statusBadge">{t(locale, `delegationStatuses.${item.status}`)}</span>
              <span>{item.starts_at} — {item.ends_at}</span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
