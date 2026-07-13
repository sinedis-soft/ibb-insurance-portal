"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CompanyLink = {
  id: string;
  bitrix_company_id: string;
  role_code: string;
  access_status: string;
  bitrix_link_status: string;
  bitrix_company_verified_at: string | null;
  company_title: string | null;
  created_at: string | null;
};

type AdminUser = {
  id: string;
  email: string;
  display_name: string | null;
  role_code: string | null;
  roles: string[];
  user_type: string;
  status: string;
  bitrix_contact_id: number | null;
  bitrix_contact_link_status: string;
  bitrix_contact_verified_at: string | null;
  blocked_reason: string | null;
  blocked_at: string | null;
  blocked_by_user_id: string | null;
  created_at: string | null;
  last_login_at: string | null;
  updated_at: string | null;
};

type UserCard = {
  user: AdminUser;
  company_links: CompanyLink[];
  partner_client_links: Array<{ id: string; bitrix_company_id: string; status: string }>;
  audit_events: Array<{ id: string; action: string; created_at: string | null }>;
  integration_errors: Array<{ id: string; error_code: string; status: string; safe_message: string | null }>;
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

export default function SuperadminUserDetailPage() {
  const params = useParams<{ id: string }>();
  const userId = params.id;
  const [locale, setLocale] = useState<Locale>(DEFAULT_LOCALE);
  const [card, setCard] = useState<UserCard | null>(null);
  const [roleCode, setRoleCode] = useState("");
  const [bitrixContactId, setBitrixContactId] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [companyRole, setCompanyRole] = useState("client_executor");
  const [companyBitrixIds, setCompanyBitrixIds] = useState<Record<string, string>>({});
  const [companyRoles, setCompanyRoles] = useState<Record<string, string>>({});
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [successKey, setSuccessKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function loadCard() {
    setErrorCode(null);
    const user = await requestJson<{ language: string | null }>("/auth/me");
    setLocale(normalizeLocale(user.language));
    const data = await requestJson<UserCard>(`/superadmin/users/${userId}`);
    setCard(data);
    setRoleCode(data.user.role_code ?? (data.user.user_type === "partner" ? "partner" : ""));
    setBitrixContactId(data.user.bitrix_contact_id ? String(data.user.bitrix_contact_id) : "");
    setCompanyBitrixIds(Object.fromEntries(data.company_links.map((link) => [link.id, link.bitrix_company_id])));
    setCompanyRoles(Object.fromEntries(data.company_links.map((link) => [link.id, link.role_code])));
  }

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        await loadCard();
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
  }, [userId]);

  async function submitRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await requestJson(`/superadmin/users/${userId}/roles`, {
      method: "PATCH",
      body: JSON.stringify({ role_code: roleCode || null }),
    });
    setSuccessKey("superadmin.roleUpdated");
    await loadCard();
  }

  async function submitBitrix(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await requestJson(`/superadmin/users/${userId}/bitrix-links`, {
      method: "PATCH",
      body: JSON.stringify({ bitrix_contact_id: bitrixContactId ? Number(bitrixContactId) : null }),
    });
    setSuccessKey("superadmin.linkUpdated");
    await loadCard();
  }

  async function submitCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await requestJson(`/superadmin/users/${userId}/company-links`, {
      method: "POST",
      body: JSON.stringify({ bitrix_company_id: companyId, role_code: companyRole }),
    });
    setCompanyId("");
    setSuccessKey("superadmin.linkUpdated");
    await loadCard();
  }

  async function verifyContact() {
    await requestJson(`/superadmin/users/${userId}/bitrix-links/verify-contact`, { method: "POST", body: "{}" });
    setSuccessKey("superadmin.linkUpdated");
    await loadCard();
  }

  async function updateCompanyRole(linkId: string) {
    await requestJson(`/superadmin/users/${userId}/company-links/${linkId}`, {
      method: "PATCH",
      body: JSON.stringify({ role_code: companyRoles[linkId] }),
    });
    setSuccessKey("superadmin.roleUpdated");
    await loadCard();
  }

  async function updateCompanyBitrix(linkId: string) {
    await requestJson(`/superadmin/users/${userId}/company-links/${linkId}/bitrix-company`, {
      method: "PATCH",
      body: JSON.stringify({ bitrix_company_id: companyBitrixIds[linkId] }),
    });
    setSuccessKey("superadmin.linkUpdated");
    await loadCard();
  }

  async function verifyCompany(linkId: string) {
    await requestJson(`/superadmin/users/${userId}/company-links/${linkId}/verify-bitrix-company`, { method: "POST", body: "{}" });
    setSuccessKey("superadmin.linkUpdated");
    await loadCard();
  }

  async function revokeCompany(linkId: string) {
    await requestJson(`/superadmin/users/${userId}/company-links/${linkId}`, { method: "DELETE" });
    setSuccessKey("superadmin.linkUpdated");
    await loadCard();
  }

  return (
    <main className="shell workspaceShell">
      <section className="workspacePanel adminPanel" aria-busy={isLoading}>
        <div className="sectionHeader">
          <div>
            <p className="sectionLabel">{t(locale, "superadmin.sectionLabel")}</p>
            <h1>{t(locale, "superadmin.userCard")}</h1>
          </div>
          <div className="buttonRow"><Link className="secondaryLink" href="/superadmin/users">
            {t(locale, "superadmin.usersTitle")}
          </Link><Link className="secondaryLink" href={`/superadmin/audit-log?actor_user_id=${userId}`}>{t(locale, "auditLog.title")}</Link></div>
        </div>

        {errorCode ? <p className="errorText">{errorMessage(locale, errorCode)}</p> : null}
        {successKey ? <p className="stateText success">{t(locale, successKey)}</p> : null}
        {isLoading ? <p className="stateText">{t(locale, "superadmin.loadingUsers")}</p> : null}

        {card ? (
          <>
            <div className="detailGrid">
              <div>
                <dt>{t(locale, "app.email")}</dt>
                <dd>{card.user.email}</dd>
              </div>
              <div>
                <dt>{t(locale, "superadmin.status")}</dt>
                <dd>{t(locale, `userStatuses.${card.user.status}`)}</dd>
              </div>
              <div>
                <dt>{t(locale, "superadmin.role")}</dt>
                <dd>{card.user.roles.map((value) => t(locale, `roles.${value}`)).join(", ")}</dd>
              </div>
              <div>
                <dt>{t(locale, "superadmin.bitrixContactId")}</dt>
                <dd>{card.user.bitrix_contact_id ?? t(locale, "superadmin.missing")}</dd>
              </div>
              <div>
                <dt>{t(locale, "superadmin.bitrixStatus")}</dt>
                <dd>{t(locale, `bitrixLinkStatuses.${card.user.bitrix_contact_link_status}`)}</dd>
              </div>
              <div>
                <dt>{t(locale, "superadmin.updatedAt")}</dt>
                <dd>{card.user.updated_at ?? t(locale, "superadmin.missing")}</dd>
              </div>
              <div>
                <dt>{t(locale, "superadmin.blockedReason")}</dt>
                <dd>{card.user.blocked_reason ?? t(locale, "superadmin.missing")}</dd>
              </div>
            </div>

            <div className="adminGrid">
              <form className="portalForm" onSubmit={(event) => void submitRole(event)}>
                <h2>{t(locale, "superadmin.roles")}</h2>
                <label>
                  <span>{t(locale, "superadmin.role")}</span>
                  <select onChange={(event) => setRoleCode(event.target.value)} value={roleCode}>
                    <option value="">{t(locale, "superadmin.revokeRole")}</option>
                    {["client_executor", "client_admin", "client_viewer", "partner", "superadmin"].map((value) => (
                      <option key={value} value={value}>
                        {t(locale, `roles.${value}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <button className="primaryButton" type="submit">
                  {t(locale, "superadmin.assignRole")}
                </button>
              </form>

              <form className="portalForm" onSubmit={(event) => void submitBitrix(event)}>
                <h2>{t(locale, "superadmin.bitrixLinks")}</h2>
                <label>
                  <span>{t(locale, "superadmin.bitrixContactId")}</span>
                  <input
                    inputMode="numeric"
                    onChange={(event) => setBitrixContactId(event.target.value)}
                    value={bitrixContactId}
                  />
                </label>
                <button className="primaryButton" type="submit">
                  {t(locale, "superadmin.updateBitrixLinks")}
                </button>
                <button className="secondaryButton" onClick={() => void verifyContact()} type="button">
                  {t(locale, "superadmin.verifyContact")}
                </button>
              </form>
            </div>

            <form className="portalForm" onSubmit={(event) => void submitCompany(event)}>
              <h2>{t(locale, "superadmin.companies")}</h2>
              <div className="formGrid">
                <label>
                  <span>{t(locale, "superadmin.companyId")}</span>
                  <input required inputMode="numeric" onChange={(event) => setCompanyId(event.target.value)} value={companyId} />
                </label>
                <label>
                  <span>{t(locale, "superadmin.role")}</span>
                  <select onChange={(event) => setCompanyRole(event.target.value)} value={companyRole}>
                    {["client_executor", "client_admin", "client_viewer"].map((value) => (
                      <option key={value} value={value}>
                        {t(locale, `roles.${value}`)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <button className="primaryButton" type="submit">
                {t(locale, "superadmin.assignCompany")}
              </button>
            </form>

            <div className="adminTable">
              {card.company_links.map((link) => (
                <div className="adminRow companyRoleRow" key={link.id}>
                  <span>
                    <strong>{link.company_title || link.bitrix_company_id}</strong>
                    <small>{link.bitrix_company_id}</small>
                  </span>
                  <span>
                    <select onChange={(event) => setCompanyRoles((value) => ({ ...value, [link.id]: event.target.value }))} value={companyRoles[link.id] ?? link.role_code}>
                      {["client_executor", "client_admin", "client_viewer"].map((value) => (
                        <option key={value} value={value}>{t(locale, `roles.${value}`)}</option>
                      ))}
                    </select>
                    <button className="secondaryButton" onClick={() => void updateCompanyRole(link.id)} type="button">
                      {t(locale, "superadmin.updateCompanyRole")}
                    </button>
                  </span>
                  <span className={`statusBadge status-${link.access_status}`}>{t(locale, `accessStatuses.${link.access_status}`)}</span>
                  <span>{t(locale, `bitrixLinkStatuses.${link.bitrix_link_status}`)}</span>
                  <span>
                    <input inputMode="numeric" onChange={(event) => setCompanyBitrixIds((value) => ({ ...value, [link.id]: event.target.value }))} value={companyBitrixIds[link.id] ?? link.bitrix_company_id} />
                    <button className="secondaryButton" onClick={() => void updateCompanyBitrix(link.id)} type="button">
                      {t(locale, "superadmin.updateCompanyBitrix")}
                    </button>
                    <button className="secondaryButton" onClick={() => void verifyCompany(link.id)} type="button">
                      {t(locale, "superadmin.verifyCompany")}
                    </button>
                  </span>
                  <button className="secondaryButton" onClick={() => void revokeCompany(link.id)} type="button">
                    {t(locale, "superadmin.revokeCompany")}
                  </button>
                </div>
              ))}
            </div>

            <div className="adminGrid">
              <section className="portalForm">
                <h2>{t(locale, "superadmin.auditLog")}</h2>
                {card.audit_events.map((event) => (
                  <p className="stateText" key={event.id}>{event.action}</p>
                ))}
              </section>
              <section className="portalForm">
                <h2>{t(locale, "superadmin.integrationErrors")}</h2>
                {card.integration_errors.map((error) => (
                  <p className="errorText" key={error.id}>{error.error_code}</p>
                ))}
              </section>
            </div>
          </>
        ) : null}
      </section>
    </main>
  );
}
