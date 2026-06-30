"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { CompanyContextProvider, useCompanyContext } from "../../lib/company-context";
import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../lib/i18n";

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

type PolicyListItem = {
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

function formatPremium(item: PolicyListItem) {
  if (!item.premium_amount) {
    return "";
  }
  return item.premium_currency ? `${item.premium_amount} ${item.premium_currency}` : item.premium_amount;
}

function productName(locale: Locale, item: PolicyListItem) {
  if (!item.product_type_code) {
    return item.product_label ?? "";
  }
  const key = `applicationTypes.${item.product_type_code}`;
  const label = t(locale, key);
  return label === key ? item.product_label ?? item.product_type_code : label;
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

function PoliciesList({ locale }: { locale: Locale }) {
  const { selectedCompanyId, contextVersion, isLoadingCompanies } = useCompanyContext();
  const [items, setItems] = useState<PolicyListItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [productFilter, setProductFilter] = useState("");
  const [expiresSoonOnly, setExpiresSoonOnly] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [downloadErrorCode, setDownloadErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadPolicies() {
      setItems([]);
      setErrorCode(null);
      if (isLoadingCompanies) {
        return;
      }
      setIsLoading(true);
      const params = new URLSearchParams();
      if (selectedCompanyId) {
        params.set("company_id", selectedCompanyId);
      }
      if (searchQuery.trim()) {
        params.set("q", searchQuery.trim());
      }
      if (productFilter) {
        params.set("product_type", productFilter);
      }
      if (expiresSoonOnly) {
        params.set("expires_within_days", "30");
      }
      try {
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const data = await requestJson<{ items: PolicyListItem[] }>(`/policies${suffix}`);
        if (isMounted) {
          setItems(data.items);
        }
      } catch (error) {
        if (isMounted) {
          setErrorCode(error instanceof Error ? error.message : "POLICY_ACCESS_DENIED");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadPolicies();
    return () => {
      isMounted = false;
    };
  }, [contextVersion, expiresSoonOnly, isLoadingCompanies, productFilter, searchQuery, selectedCompanyId]);

  return (
    <section className="workspacePanel">
      <div className="sectionHeader">
        <div>
          <p className="sectionLabel">{t(locale, "policies.sectionLabel")}</p>
          <h1>{t(locale, "policies.title")}</h1>
        </div>
        <Link className="secondaryLink" href="/">
          {t(locale, "applications.backToDashboard")}
        </Link>
      </div>

      <div className="filtersBar policiesFilters">
        <label>
          <span>{t(locale, "policies.search")}</span>
          <input
            onChange={(event) => setSearchQuery(event.target.value)}
            type="search"
            value={searchQuery}
          />
        </label>
        <label>
          <span>{t(locale, "policies.product")}</span>
          <select onChange={(event) => setProductFilter(event.target.value)} value={productFilter}>
            <option value="">{t(locale, "policies.allProducts")}</option>
            <option value="auto">{t(locale, "applicationTypes.auto")}</option>
            <option value="cargo">{t(locale, "applicationTypes.cargo")}</option>
          </select>
        </label>
        <label className="toggleFilter">
          <input
            checked={expiresSoonOnly}
            onChange={(event) => setExpiresSoonOnly(event.target.checked)}
            type="checkbox"
          />
          <span>{t(locale, "policies.expiresSoonOnly")}</span>
        </label>
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
      {!isLoading && !errorCode && items.length === 0 ? (
        <p className="stateText">{t(locale, "policies.empty")}</p>
      ) : null}

      {items.length > 0 ? (
        <div className="applicationList policyList">
          {items.map((item) => (
            <article className="applicationRow policyRow" key={item.id}>
              <span>
                <strong>{item.policy_number}</strong>
                <small>{productName(locale, item)}</small>
              </span>
              <span className="statusBadge">{t(locale, `policyStatuses.${item.policy_status}`)}</span>
              <span className="dateStack">
                <small>{t(locale, "policies.validTo")}</small>
                {formatDate(locale, item.valid_to)}
              </span>
              <span className="dateStack">
                <small>{t(locale, "policies.premium")}</small>
                {formatPremium(item)}
              </span>
              <span className="dateStack">
                <small>{t(locale, "policies.documents")}</small>
                {item.documents.length > 0 ? t(locale, "policies.documentsReady") : t(locale, "policies.documentsEmpty")}
              </span>
              <span className="policyActions">
                <Link className="secondaryLink" href={`/policies/${item.id}`}>
                  {t(locale, "policies.openPolicy")}
                </Link>
                {item.documents
                  .filter((document) => document.is_download_available)
                  .map((document) => (
                    <button
                      className="secondaryButton"
                      key={document.id}
                      onClick={() => {
                        setDownloadErrorCode(null);
                        void downloadDocument(document.id).catch((error) => {
                          setDownloadErrorCode(error instanceof Error ? error.message : "DOCUMENT_DOWNLOAD_NOT_ALLOWED");
                        });
                      }}
                      type="button"
                    >
                      {t(locale, "policies.download")}
                    </button>
                  ))}
              </span>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export default function PoliciesPage() {
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
        {!isLoading && user ? <PoliciesList locale={locale} /> : null}
      </main>
    </CompanyContextProvider>
  );
}
