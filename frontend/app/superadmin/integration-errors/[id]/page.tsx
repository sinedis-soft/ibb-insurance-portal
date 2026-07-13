"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type IntegrationErrorDetail = {
  error: {
    id: string;
    operation: string;
    object_type: string;
    object_id: string | null;
    bitrix_entity_type: string | null;
    bitrix_entity_id: number | null;
    status: string;
    error_code: string;
    safe_message: string | null;
    retry_count: number;
    first_failed_at: string | null;
    last_failed_at: string | null;
    last_attempt_at: string | null;
    correlation_id: string | null;
    retry_supported: boolean;
    attempt_history: Array<{ at?: string; result?: string }>;
  };
  audit_events: Array<{ id: string; action: string; created_at: string | null }>;
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

export default function SuperadminIntegrationErrorDetailPage() {
  const params = useParams<{ id: string }>();
  const errorId = params.id;
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [detail, setDetail] = useState<IntegrationErrorDetail | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function loadDetail() {
    setErrorCode(null);
    const user = await requestJson<{ language: string | null }>("/auth/me");
    setLocale(normalizeLocale(user.language));
    const data = await requestJson<IntegrationErrorDetail>(`/superadmin/integration-errors/${errorId}`);
    setDetail(data);
  }

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        await loadDetail();
      } catch (error) {
        if (isMounted) setErrorCode(error instanceof Error ? error.message : "SUPERADMIN_REQUIRED");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }
    void load();
    return () => {
      isMounted = false;
    };
  }, [errorId]);

  async function retry() {
    await requestJson(`/superadmin/integration-errors/${errorId}/retry`, { method: "POST", body: "{}" });
    await loadDetail();
  }

  return (
    <main className="shell workspaceShell">
      <section className="workspacePanel adminPanel" aria-busy={isLoading}>
        <div className="sectionHeader">
          <div>
            <p className="sectionLabel">{t(locale, "superadmin.sectionLabel")}</p>
            <h1>{t(locale, "superadmin.integrationErrorCard")}</h1>
          </div>
          <div className="buttonRow"><Link className="secondaryLink" href="/superadmin/integration-errors">
            {t(locale, "superadmin.integrationErrors")}
          </Link><Link className="secondaryLink" href={`/superadmin/audit-log?integration_error_id=${errorId}`}>{t(locale, "auditLog.title")}</Link></div>
        </div>

        {errorCode ? <p className="errorText">{errorMessage(locale, errorCode)}</p> : null}
        {isLoading ? <p className="stateText">{t(locale, "superadmin.loadingErrors")}</p> : null}

        {detail ? (
          <>
            <div className="detailGrid">
              <div><dt>{t(locale, "superadmin.technicalId")}</dt><dd>{detail.error.id}</dd></div>
              <div><dt>{t(locale, "superadmin.status")}</dt><dd>{t(locale, `integrationErrorStatuses.${detail.error.status}`)}</dd></div>
              <div><dt>{t(locale, "superadmin.objectType")}</dt><dd>{t(locale, `integrationObjectTypes.${detail.error.object_type}`)}</dd></div>
              <div><dt>{t(locale, "superadmin.bitrix24Id")}</dt><dd>{detail.error.bitrix_entity_id ?? t(locale, "superadmin.missing")}</dd></div>
              <div><dt>{t(locale, "superadmin.correlationId")}</dt><dd>{detail.error.correlation_id ?? t(locale, "superadmin.missing")}</dd></div>
              <div><dt>{t(locale, "superadmin.firstFailedAt")}</dt><dd>{detail.error.first_failed_at ?? t(locale, "superadmin.missing")}</dd></div>
              <div><dt>{t(locale, "superadmin.lastFailedAt")}</dt><dd>{detail.error.last_failed_at ?? t(locale, "superadmin.missing")}</dd></div>
              <div><dt>{t(locale, "superadmin.attempts")}</dt><dd>{detail.error.retry_count}</dd></div>
            </div>
            <section className="portalForm">
              <h2>{detail.error.error_code}</h2>
              <p className="stateText">{detail.error.safe_message ?? detail.error.operation}</p>
              {detail.error.retry_supported ? (
                <button className="primaryButton" onClick={() => void retry()} type="button">
                  {t(locale, "superadmin.retry")}
                </button>
              ) : (
                <p className="stateText">{t(locale, "superadmin.retryNotSupported")}</p>
              )}
            </section>
            <section className="portalForm">
              <h2>{t(locale, "superadmin.auditLog")}</h2>
              {detail.audit_events.map((event) => (
                <p className="stateText" key={event.id}>{event.action}</p>
              ))}
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}
