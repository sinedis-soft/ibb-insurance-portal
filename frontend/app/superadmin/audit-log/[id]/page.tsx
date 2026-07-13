"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../../lib/i18n";

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
  document_id: string | null;
  delegation_id: string | null;
  integration_error_id: string | null;
  impersonation_session_id: string | null;
  result: string;
  reason_code: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  correlation_id: string | null;
  created_at: string | null;
};

async function requestJson<T = unknown>(path: string, options: RequestInit = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, { ...options, credentials: "include", headers: { "content-type": "application/json", ...options.headers } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.error_code === "string" ? data.error_code : "UNAUTHORIZED");
  return data as T;
}

function errorMessage(locale: Locale, code: string) {
  const message = t(locale, `errors.${code}`);
  return message === `errors.${code}` ? t(locale, "errors.fallback") : message;
}

export default function SuperadminAuditEventPage() {
  const params = useParams<{ id: string }>();
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [event, setEvent] = useState<AuditEvent | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const user = await requestJson<{ language: string | null }>("/auth/me");
        if (mounted) setLocale(normalizeLocale(user.language));
        const data = await requestJson<{ event: AuditEvent }>(`/superadmin/audit-events/${params.id}`);
        if (mounted) setEvent(data.event);
      } catch (error) {
        if (mounted) setErrorCode(error instanceof Error ? error.message : "SUPERADMIN_REQUIRED");
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    void load();
    return () => { mounted = false; };
  }, [params.id]);

  return (
    <main className="shell workspaceShell">
      <section className="workspacePanel adminPanel" aria-busy={isLoading}>
        <div className="sectionHeader"><div><p className="sectionLabel">{t(locale, "superadmin.sectionLabel")}</p><h1>{t(locale, "auditLog.detailTitle")}</h1></div><Link className="secondaryLink" href="/superadmin/audit-log">{t(locale, "auditLog.title")}</Link></div>
        {errorCode ? <p className="errorText">{errorMessage(locale, errorCode)}</p> : null}
        {isLoading ? <p className="stateText">{t(locale, "auditLog.loading")}</p> : null}
        {event ? <><dl className="detailGrid">
          <div><dt>{t(locale, "auditLog.createdAt")}</dt><dd>{event.created_at ?? t(locale, "superadmin.missing")}</dd></div>
          <div><dt>{t(locale, "auditLog.category")}</dt><dd>{t(locale, `auditCategories.${event.category}`)}</dd></div>
          <div><dt>{t(locale, "auditLog.eventType")}</dt><dd>{event.event_type}</dd></div>
          <div><dt>{t(locale, "auditLog.actor")}</dt><dd>{event.actor_user_id ?? t(locale, "superadmin.missing")}</dd></div>
          <div><dt>{t(locale, "auditLog.effectiveUser")}</dt><dd>{event.effective_user_id ?? t(locale, "superadmin.missing")}</dd></div>
          <div><dt>{t(locale, "auditLog.target")}</dt><dd>{event.target_type}{event.target_id ? ` · ${event.target_id}` : ""}</dd></div>
          <div><dt>{t(locale, "auditLog.company")}</dt><dd>{event.company_id ?? t(locale, "superadmin.missing")}</dd></div>
          <div><dt>{t(locale, "auditLog.result")}</dt><dd>{t(locale, `auditResults.${event.result}`)}</dd></div>
          <div><dt>{t(locale, "auditLog.reasonCode")}</dt><dd>{event.reason_code ?? t(locale, "superadmin.missing")}</dd></div>
          <div><dt>{t(locale, "auditLog.correlationId")}</dt><dd>{event.correlation_id ?? t(locale, "superadmin.missing")}</dd></div>
          <div><dt>{t(locale, "auditLog.impersonationSession")}</dt><dd>{event.impersonation_session_id ?? t(locale, "superadmin.missing")}</dd></div>
          <div><dt>{t(locale, "auditLog.ipAddress")}</dt><dd>{event.ip_address ?? t(locale, "superadmin.missing")}</dd></div>
          <div><dt>{t(locale, "auditLog.userAgent")}</dt><dd>{event.user_agent ?? t(locale, "superadmin.missing")}</dd></div>
        </dl><section className="preparedBlock"><h2>{t(locale, "auditLog.metadata")}</h2><pre>{JSON.stringify(event.metadata, null, 2)}</pre></section></> : null}
      </section>
    </main>
  );
}
