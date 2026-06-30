"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { DEFAULT_LOCALE, Locale, normalizeLocale, t } from "../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CurrentUser = {
  id: string;
  role: string;
  user_type: string;
  language: string | null;
  status: string;
};

type PartnerClient = {
  id: string;
  company_name: string;
  country: string | null;
  registration_number: string | null;
  contact_name: string;
  contact_email: string;
  contact_phone: string | null;
  status: string;
  bitrix_check_entity_id: number | null;
  bitrix_check_status: string;
  bitrix_sync_status: string;
  bitrix_synced_at: string | null;
  confirmed_bitrix_company_id: string | null;
  created_at: string | null;
};

type PartnerClientForm = {
  company_name: string;
  country: string;
  registration_number: string;
  tax_id: string;
  address: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  comment: string;
};

const emptyForm: PartnerClientForm = {
  company_name: "",
  country: "",
  registration_number: "",
  tax_id: "",
  address: "",
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  comment: "",
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

function statusLabel(locale: Locale, status: string) {
  const message = t(locale, `partnerClientStatuses.${status}`);
  return message === `partnerClientStatuses.${status}` ? status : message;
}

function syncStatusLabel(locale: Locale, status: string) {
  const message = t(locale, `partnerClientSyncStatuses.${status}`);
  return message === `partnerClientSyncStatuses.${status}` ? status : message;
}

function formatDate(locale: Locale, value: string | null) {
  if (!value) {
    return "";
  }
  return new Intl.DateTimeFormat(locale === "ka" ? "ka-GE" : "ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function PartnerClientsPage() {
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [items, setItems] = useState<PartnerClient[]>([]);
  const [form, setForm] = useState<PartnerClientForm>(emptyForm);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function loadClients() {
    const data = await requestJson<{ items: PartnerClient[] }>("/partner/clients");
    setItems(data.items);
  }

  useEffect(() => {
    let isMounted = true;

    async function loadPage() {
      try {
        const user = await requestJson<CurrentUser>("/auth/me");
        if (!isMounted) {
          return;
        }
        setLocale(normalizeLocale(user.language));
        if (user.user_type !== "partner") {
          setErrorCode("PARTNER_ROLE_REQUIRED");
          return;
        }
        await loadClients();
      } catch (error) {
        if (isMounted) {
          setErrorCode(error instanceof Error ? error.message : "UNAUTHORIZED");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadPage();
    return () => {
      isMounted = false;
    };
  }, []);

  function updateField(field: keyof PartnerClientForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorCode(null);
    setSuccessMessage(null);
    try {
      await requestJson<{ client: PartnerClient }>("/partner/clients", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm(emptyForm);
      setSuccessMessage(t(locale, "partnerClients.created"));
      await loadClients();
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "UNAUTHORIZED");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="shell">
      <section className="authPanel widePanel" aria-busy={isLoading}>
        <div className="topBar">
          <p className="eyebrow">{t(locale, "partnerClients.sectionLabel")}</p>
          <Link className="secondaryLink" href="/">
            {t(locale, "partnerClients.backToDashboard")}
          </Link>
        </div>
        <h1>{t(locale, "partnerClients.title")}</h1>
        <p className="subtitle">{t(locale, "partnerClients.subtitle")}</p>

        {isLoading ? <p className="stateText">{t(locale, "partnerClients.loading")}</p> : null}

        {errorCode ? (
          <p className="errorText" role="alert">
            {errorMessage(locale, errorCode)}
          </p>
        ) : null}

        {!isLoading ? (
          <div className="partnerClientsLayout">
            <form className="portalForm" onSubmit={handleSubmit}>
              <h2>{t(locale, "partnerClients.createTitle")}</h2>
              <div className="formGrid">
                <label>
                  <span>{t(locale, "partnerClients.companyName")}</span>
                  <input
                    onChange={(event) => updateField("company_name", event.target.value)}
                    required
                    value={form.company_name}
                  />
                </label>
                <label>
                  <span>{t(locale, "partnerClients.country")}</span>
                  <input
                    maxLength={16}
                    onChange={(event) => updateField("country", event.target.value)}
                    value={form.country}
                  />
                </label>
                <label>
                  <span>{t(locale, "partnerClients.registrationNumber")}</span>
                  <input
                    onChange={(event) => updateField("registration_number", event.target.value)}
                    value={form.registration_number}
                  />
                </label>
                <label>
                  <span>{t(locale, "partnerClients.taxId")}</span>
                  <input onChange={(event) => updateField("tax_id", event.target.value)} value={form.tax_id} />
                </label>
                <label className="wideField">
                  <span>{t(locale, "partnerClients.address")}</span>
                  <input onChange={(event) => updateField("address", event.target.value)} value={form.address} />
                </label>
                <label>
                  <span>{t(locale, "partnerClients.contactName")}</span>
                  <input
                    onChange={(event) => updateField("contact_name", event.target.value)}
                    required
                    value={form.contact_name}
                  />
                </label>
                <label>
                  <span>{t(locale, "partnerClients.contactEmail")}</span>
                  <input
                    inputMode="email"
                    onChange={(event) => updateField("contact_email", event.target.value)}
                    required
                    type="email"
                    value={form.contact_email}
                  />
                </label>
                <label>
                  <span>{t(locale, "partnerClients.contactPhone")}</span>
                  <input
                    inputMode="tel"
                    onChange={(event) => updateField("contact_phone", event.target.value)}
                    value={form.contact_phone}
                  />
                </label>
                <label className="wideField">
                  <span>{t(locale, "partnerClients.comment")}</span>
                  <textarea onChange={(event) => updateField("comment", event.target.value)} value={form.comment} />
                </label>
              </div>
              {successMessage ? <p className="stateText">{successMessage}</p> : null}
              <button className="primaryButton" disabled={isSubmitting} type="submit">
                {isSubmitting ? t(locale, "partnerClients.creating") : t(locale, "partnerClients.create")}
              </button>
            </form>

            <section className="partnerClientsList">
              <h2>{t(locale, "partnerClients.listTitle")}</h2>
              {items.length === 0 ? <p className="stateText">{t(locale, "partnerClients.empty")}</p> : null}
              {items.map((client) => {
                const isConfirmed =
                  (client.status === "confirmed" || client.status === "linked_to_existing") &&
                  client.confirmed_bitrix_company_id;
                const applicationQuery = isConfirmed
                  ? `?company_id=${client.confirmed_bitrix_company_id}&partner_client_request_id=${client.id}`
                  : "";
                return (
                  <article className="partnerClientCard" key={client.id}>
                    <div className="partnerClientCardHeader">
                      <div>
                        <h3>{client.company_name}</h3>
                        <p>{formatDate(locale, client.created_at)}</p>
                      </div>
                      <span className={`statusBadge status-${client.status}`}>
                        {statusLabel(locale, client.status)}
                      </span>
                    </div>
                    <dl className="compactMeta">
                      <div>
                        <dt>{t(locale, "partnerClients.status")}</dt>
                        <dd>{statusLabel(locale, client.status)}</dd>
                      </div>
                      <div>
                        <dt>{t(locale, "partnerClients.bitrixCheck")}</dt>
                        <dd>{syncStatusLabel(locale, client.bitrix_sync_status)}</dd>
                      </div>
                      <div>
                        <dt>{t(locale, "partnerClients.checkStatus")}</dt>
                        <dd>{statusLabel(locale, client.bitrix_check_status)}</dd>
                      </div>
                      <div>
                        <dt>{t(locale, "partnerClients.lastSync")}</dt>
                        <dd>
                          {client.bitrix_synced_at
                            ? formatDate(locale, client.bitrix_synced_at)
                            : t(locale, "partnerClients.notSyncedYet")}
                        </dd>
                      </div>
                    </dl>
                    <p className="stateText">
                      {client.status === "linked_to_existing"
                        ? t(locale, "partnerClients.linkedToExistingHint")
                        : isConfirmed
                          ? t(locale, "partnerClients.applicationsReady")
                          : t(locale, "partnerClients.applicationsLocked")}
                    </p>
                    <div className="partnerClientActions">
                      {isConfirmed ? (
                        <>
                          <Link className="secondaryLink" href={`/applications/auto/new${applicationQuery}`}>
                            {t(locale, "partnerClients.createAuto")}
                          </Link>
                          <Link className="secondaryLink" href={`/applications/cargo/new${applicationQuery}`}>
                            {t(locale, "partnerClients.createCargo")}
                          </Link>
                        </>
                      ) : (
                        <>
                          <button className="secondaryButton" disabled type="button">
                            {t(locale, "partnerClients.createAuto")}
                          </button>
                          <button className="secondaryButton" disabled type="button">
                            {t(locale, "partnerClients.createCargo")}
                          </button>
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </section>
          </div>
        ) : null}
      </section>
    </main>
  );
}
