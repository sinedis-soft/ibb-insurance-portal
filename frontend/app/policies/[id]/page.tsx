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
  language: string | null;
  status: string;
};

type PolicyDocument = {
  id: string;
  document_type: string;
  label: string;
  is_policy_file: boolean;
  transfer_status: string;
  is_download_available: boolean;
};

type PolicyDetail = {
  id: string;
  application_id: string;
  bitrix_company_id: string;
  policy_number: string;
  product_type_code: string | null;
  product_label: string | null;
  valid_from: string | null;
  valid_to: string | null;
  premium_amount: string | null;
  premium_currency: string | null;
  policy_status: string;
  status_label: string;
  is_expiring_soon: boolean;
  documents: PolicyDocument[];
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

function formatDate(locale: Locale, value: string | null) {
  return value ? new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(value)) : "";
}

function formatPremium(policy: PolicyDetail) {
  if (!policy.premium_amount) {
    return "";
  }
  return policy.premium_currency ? `${policy.premium_amount} ${policy.premium_currency}` : policy.premium_amount;
}

function productName(locale: Locale, policy: PolicyDetail) {
  if (!policy.product_type_code) {
    return policy.product_label ?? "";
  }
  const key = `applicationTypes.${policy.product_type_code}`;
  const label = t(locale, key);
  return label === key ? policy.product_label ?? policy.product_type_code : label;
}

async function downloadDocument(documentId: string) {
  const response = await fetch(`${apiBaseUrl}/documents/${documentId}/download`, {
    credentials: "include",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.error_code === "string" ? data.error_code : "DOCUMENT_DOWNLOAD_NOT_ALLOWED");
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = `${documentId}.bin`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

function PolicyCard({ locale, policyId }: { locale: Locale; policyId: string }) {
  const { selectedCompanyId, contextVersion } = useCompanyContext();
  const [policy, setPolicy] = useState<PolicyDetail | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [downloadErrorCode, setDownloadErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function loadPolicy() {
      setPolicy(null);
      setErrorCode(null);
      setDownloadErrorCode(null);
      setIsLoading(true);
      try {
        const data = await requestJson<PolicyDetail>(`/policies/${policyId}`);
        if (isMounted) {
          setPolicy(data);
        }
      } catch (error) {
        if (isMounted) {
          setErrorCode(error instanceof Error ? error.message : "POLICY_NOT_FOUND");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }
    void loadPolicy();
    return () => {
      isMounted = false;
    };
  }, [contextVersion, policyId]);

  const wrongContext = policy && selectedCompanyId && selectedCompanyId !== policy.bitrix_company_id;

  return (
    <section className="workspacePanel">
      <div className="sectionHeader">
        <div>
          <p className="sectionLabel">{t(locale, "policies.sectionLabel")}</p>
          <h1>{policy?.policy_number ?? t(locale, "policies.detailTitle")}</h1>
        </div>
        <Link className="secondaryLink" href="/policies">
          {t(locale, "applications.backToList")}
        </Link>
      </div>

      {isLoading ? <p className="stateText">{t(locale, "policies.loading")}</p> : null}
      {errorCode ? (
        <p className="errorText" role="alert">
          {errorMessage(locale, errorCode)}
        </p>
      ) : null}
      {downloadErrorCode ? (
        <p className="errorText" role="alert">
          {errorMessage(locale, downloadErrorCode)}
        </p>
      ) : null}
      {wrongContext ? <p className="errorText">{t(locale, "policies.wrongCompanyContext")}</p> : null}

      {policy && !wrongContext ? (
        <>
          <dl className="detailGrid">
            <div>
              <dt>{t(locale, "policies.policyNumber")}</dt>
              <dd>{policy.policy_number}</dd>
            </div>
            <div>
              <dt>{t(locale, "policies.status")}</dt>
              <dd>{t(locale, `policyStatuses.${policy.policy_status}`)}</dd>
            </div>
            <div>
              <dt>{t(locale, "policies.product")}</dt>
              <dd>{productName(locale, policy)}</dd>
            </div>
            <div>
              <dt>{t(locale, "policies.validFrom")}</dt>
              <dd>{formatDate(locale, policy.valid_from)}</dd>
            </div>
            <div>
              <dt>{t(locale, "policies.validTo")}</dt>
              <dd>{formatDate(locale, policy.valid_to)}</dd>
            </div>
            <div>
              <dt>{t(locale, "policies.premium")}</dt>
              <dd>{formatPremium(policy)}</dd>
            </div>
            <div>
              <dt>{t(locale, "policies.relatedApplication")}</dt>
              <dd>
                <Link className="textLink" href={`/applications/${policy.application_id}`}>
                  {policy.application_id}
                </Link>
              </dd>
            </div>
          </dl>

          <section className="preparedBlock">
            <h2>{t(locale, "policies.documents")}</h2>
            {policy.documents.length > 0 ? (
              <div className="documentList">
                {policy.documents.map((document) => (
                  <div className="documentRow" key={document.id}>
                    <span>
                      <strong>{t(locale, `documentTypes.${document.document_type}`)}</strong>
                      <small>{t(locale, `documentStatuses.${document.transfer_status}`)}</small>
                    </span>
                    {document.is_download_available ? (
                      <button
                        className="secondaryButton"
                        onClick={() => {
                          setDownloadErrorCode(null);
                          void downloadDocument(document.id).catch((error) => {
                            setDownloadErrorCode(
                              error instanceof Error ? error.message : "DOCUMENT_DOWNLOAD_NOT_ALLOWED",
                            );
                          });
                        }}
                        type="button"
                      >
                        {t(locale, "policies.download")}
                      </button>
                    ) : (
                      <span className="statusBadge">{t(locale, "policies.downloadNotAllowed")}</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="stateText">{t(locale, "policies.documentsEmpty")}</p>
            )}
          </section>
        </>
      ) : null}
    </section>
  );
}

export default function PolicyDetailPage() {
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
        {!isLoading && user ? <PolicyCard locale={locale} policyId={params.id} /> : null}
      </main>
    </CompanyContextProvider>
  );
}
