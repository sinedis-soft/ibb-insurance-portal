"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Delegation = { id: string; company_id: string; delegator_user_id: string; delegate_user_id: string; starts_at: string | null; ends_at: string | null; status: string; reason: string | null; items: Array<{ application_id: string; status: string }> };
async function requestJson<T = unknown>(path: string, options: RequestInit = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, { ...options, credentials: "include", headers: { "content-type": "application/json", ...options.headers } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.error_code === "string" ? data.error_code : "UNAUTHORIZED");
  return data as T;
}
function errorMessage(locale: Locale, code: string) { const message = t(locale, `errors.${code}`); return message === `errors.${code}` ? t(locale, "errors.fallback") : message; }

export default function DelegationDetailPage() {
  const params = useParams<{ id: string }>();
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [delegation, setDelegation] = useState<Delegation | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  async function load() {
    setErrorCode(null);
    try {
      const user = await requestJson<{ language: string | null }>("/auth/me");
      setLocale(normalizeLocale(user.language));
      const data = await requestJson<{ delegation: Delegation }>(`/delegations/${params.id}`);
      setDelegation(data.delegation);
    } catch (error) { setErrorCode(error instanceof Error ? error.message : "DELEGATION_NOT_FOUND"); }
    finally { setIsLoading(false); }
  }
  useEffect(() => { void load(); }, [params.id]);
  async function cancel() {
    if (!confirm(t(locale, "delegations.cancelConfirm"))) return;
    await requestJson(`/delegations/${params.id}/cancel`, { method: "POST", body: JSON.stringify({ reason: "manual" }) });
    await load();
  }
  return (
    <main className="shell workspaceShell"><section className="workspacePanel">
      <div className="sectionHeader"><div><p className="sectionLabel">{t(locale, "delegations.sectionLabel")}</p><h1>{t(locale, "delegations.detailTitle")}</h1></div><div className="buttonRow"><Link className="secondaryLink" href="/delegations">{t(locale, "delegations.title")}</Link><Link className="secondaryLink" href={`/superadmin/audit-log?delegation_id=${params.id}`}>{t(locale, "auditLog.title")}</Link></div></div>
      {errorCode ? <p className="errorText" role="alert">{errorMessage(locale, errorCode)}</p> : null}
      {isLoading ? <p className="stateText">{t(locale, "delegations.loading")}</p> : null}
      {delegation ? <><dl className="detailGrid">
        <div><dt>{t(locale, "delegations.companyId")}</dt><dd>{delegation.company_id}</dd></div>
        <div><dt>{t(locale, "delegations.delegator")}</dt><dd>{delegation.delegator_user_id}</dd></div>
        <div><dt>{t(locale, "delegations.delegate")}</dt><dd>{delegation.delegate_user_id}</dd></div>
        <div><dt>{t(locale, "delegations.status")}</dt><dd>{t(locale, `delegationStatuses.${delegation.status}`)}</dd></div>
        <div><dt>{t(locale, "delegations.startsAt")}</dt><dd>{delegation.starts_at}</dd></div>
        <div><dt>{t(locale, "delegations.endsAt")}</dt><dd>{delegation.ends_at}</dd></div>
      </dl><section className="preparedBlock"><h2>{t(locale, "delegations.applications")}</h2>{delegation.items.map((item) => <p className="stateText" key={item.application_id}>{item.application_id} · {t(locale, `delegationStatuses.${item.status}`)}</p>)}</section>{["active", "scheduled"].includes(delegation.status) ? <button className="secondaryButton" onClick={() => void cancel()} type="button">{t(locale, "delegations.cancel")}</button> : null}</> : null}
    </section></main>
  );
}
