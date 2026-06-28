"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { CompanyContextProvider, useCompanyContext } from "../../../lib/company-context";
import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CurrentUser = {
  id: string;
  role: string;
  user_type: string;
  language: Locale;
  status: string;
};

type ApplicationDetail = {
  id: string;
  application_type: string;
  bitrix_company_id: string;
  title: string;
  portal_status: string;
  status_label: string;
  product_type_code: string | null;
  client_reference_number: string | null;
  submitted_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  available_actions: string[];
  document_requests: unknown[];
  client_messages: unknown[];
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
  return value ? new Intl.DateTimeFormat("ru", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "";
}

function ApplicationCard({ locale, applicationId }: { locale: Locale; applicationId: string }) {
  const { selectedCompanyId, contextVersion } = useCompanyContext();
  const [application, setApplication] = useState<ApplicationDetail | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function loadApplication() {
      setApplication(null);
      setErrorCode(null);
      setIsLoading(true);
      try {
        const data = await requestJson<ApplicationDetail>(`/applications/${applicationId}`);
        if (isMounted) {
          setApplication(data);
        }
      } catch (error) {
        if (isMounted) {
          setErrorCode(error instanceof Error ? error.message : "APPLICATION_NOT_FOUND");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }
    void loadApplication();
    return () => {
      isMounted = false;
    };
  }, [applicationId, contextVersion]);

  const wrongContext = application && selectedCompanyId && selectedCompanyId !== application.bitrix_company_id;

  return (
    <section className="workspacePanel">
      <div className="sectionHeader">
        <div>
          <p className="sectionLabel">{t(locale, "applications.cardLabel")}</p>
          <h1>{application?.title ?? t(locale, "applications.detailTitle")}</h1>
        </div>
        <Link className="secondaryLink" href="/applications">
          {t(locale, "applications.backToList")}
        </Link>
      </div>

      {isLoading ? <p className="stateText">{t(locale, "applications.loading")}</p> : null}
      {errorCode ? (
        <p className="errorText" role="alert">
          {errorMessage(locale, errorCode)}
        </p>
      ) : null}
      {wrongContext ? <p className="errorText">{t(locale, "applications.wrongCompanyContext")}</p> : null}

      {application && !wrongContext ? (
        <>
          <dl className="detailGrid">
            <div>
              <dt>{t(locale, "applications.status")}</dt>
              <dd>{t(locale, `portalStatuses.${application.portal_status}`)}</dd>
            </div>
            <div>
              <dt>{t(locale, "applications.type")}</dt>
              <dd>{t(locale, `applicationTypes.${application.application_type}`)}</dd>
            </div>
            <div>
              <dt>{t(locale, "applications.createdAt")}</dt>
              <dd>{formatDate(application.created_at)}</dd>
            </div>
            <div>
              <dt>{t(locale, "applications.updatedAt")}</dt>
              <dd>{formatDate(application.updated_at)}</dd>
            </div>
          </dl>

          <section className="preparedBlock">
            <h2>{t(locale, "applications.availableActions")}</h2>
            {application.available_actions.length > 0 ? (
              <div className="actionList">
                {application.available_actions.map((action) => (
                  <span className="statusBadge" key={action}>
                    {t(locale, `applicationActions.${action}`)}
                  </span>
                ))}
              </div>
            ) : (
              <p className="stateText">{t(locale, "applications.noActions")}</p>
            )}
          </section>

          <section className="preparedBlock">
            <h2>{t(locale, "applications.documentRequests")}</h2>
            <p className="stateText">{t(locale, "applications.documentRequestsEmpty")}</p>
          </section>

          <section className="preparedBlock">
            <h2>{t(locale, "applications.clientMessages")}</h2>
            <p className="stateText">{t(locale, "applications.clientMessagesEmpty")}</p>
          </section>
        </>
      ) : null}
    </section>
  );
}

export default function ApplicationDetailPage() {
  const params = useParams<{ id: string }>();
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
        {!isLoading && user ? <ApplicationCard applicationId={params.id} locale={locale} /> : null}
      </main>
    </CompanyContextProvider>
  );
}
