"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { DocumentUploadPanel } from "../../document-upload-panel";
import { CompanyContextProvider, useCompanyContext } from "../../../../lib/company-context";
import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type CurrentUser = {
  id: string;
  role: string;
  user_type: string;
  language: string | null;
  status: string;
};

type ReferenceItem = {
  code: string;
  label: string;
};

type CargoReferenceData = {
  application_types: Array<ReferenceItem & { product_type_code: string }>;
  cargo_types: ReferenceItem[];
  transport_types: ReferenceItem[];
  currencies: ReferenceItem[];
  countries: ReferenceItem[];
};

type ValidationError = {
  field: string;
  error_code: string;
  message: string;
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

async function requestForm<T = unknown>(path: string, body: FormData, options: RequestInit = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    method: options.method ?? "POST",
    credentials: "include",
    body,
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

function companyTitle(locale: Locale, company: { company_title?: string | null }) {
  return company.company_title?.trim() || t(locale, "companies.unknownTitle");
}

function CargoApplicationForm({ locale }: { locale: Locale }) {
  const { selectedCompany, selectedCompanyId, isLoadingCompanies } = useCompanyContext();
  const [referenceData, setReferenceData] = useState<CargoReferenceData | null>(null);
  const [cargoApplicationType, setCargoApplicationType] = useState("single_shipment");
  const [countryFrom, setCountryFrom] = useState("PL");
  const [countryTo, setCountryTo] = useState("GE");
  const [routeDescription, setRouteDescription] = useState("");
  const [cargoType, setCargoType] = useState("general_cargo");
  const [cargoDescription, setCargoDescription] = useState("");
  const [cargoValue, setCargoValue] = useState("");
  const [currency, setCurrency] = useState("EUR");
  const [transportType, setTransportType] = useState("road");
  const [carrierName, setCarrierName] = useState("");
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [departureDate, setDepartureDate] = useState("");
  const [contractNumber, setContractNumber] = useState("");
  const [contractDealId, setContractDealId] = useState("");
  const [isActiveContract, setIsActiveContract] = useState(false);
  const [isCertificateRequested, setIsCertificateRequested] = useState(false);
  const [hasSupportingDocument, setHasSupportingDocument] = useState(false);
  const [comment, setComment] = useState("");
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [successApplicationId, setSuccessApplicationId] = useState<string | null>(null);
  const [uploadedDocumentCount, setUploadedDocumentCount] = useState(0);
  const [isLoadingReferenceData, setIsLoadingReferenceData] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function loadReferenceData() {
      setIsLoadingReferenceData(true);
      setErrorCode(null);
      try {
        const data = await requestJson<CargoReferenceData>("/cargo/reference-data");
        if (isMounted) {
          setReferenceData(data);
          if (data.application_types.length > 0 && !data.application_types.some((item) => item.code === cargoApplicationType)) {
            setCargoApplicationType(data.application_types[0].code);
          }
        }
      } catch (error) {
        if (isMounted) {
          setErrorCode(error instanceof Error ? error.message : "CARGO_APPLICATION_VALIDATION_FAILED");
        }
      } finally {
        if (isMounted) {
          setIsLoadingReferenceData(false);
        }
      }
    }
    void loadReferenceData();
    return () => {
      isMounted = false;
    };
  }, [cargoApplicationType]);

  const requiresContract = cargoApplicationType === "contract_coverage" || cargoApplicationType === "certificate";
  const canSave = useMemo(
    () => Boolean(selectedCompanyId && cargoApplicationType && referenceData),
    [cargoApplicationType, referenceData, selectedCompanyId],
  );

  function payload() {
    return {
      company_id: selectedCompanyId,
      cargo_application_type: cargoApplicationType,
      route: {
        country_from: countryFrom || null,
        country_to: countryTo || null,
        route_description: routeDescription || null,
      },
      cargo: {
        cargo_type: cargoType || null,
        cargo_description: cargoDescription || null,
        cargo_value: cargoValue || null,
        currency: currency || null,
      },
      transport: {
        transport_type: transportType || null,
        carrier_name: carrierName || null,
        vehicle_plate: vehiclePlate || null,
        departure_date: departureDate || null,
      },
      contract: {
        bitrix_contract_deal_id: contractDealId ? Number(contractDealId) : null,
        contract_number: contractNumber || null,
        is_active_contract: isActiveContract,
      },
      certificate: {
        is_certificate_requested: isCertificateRequested,
      },
      documents: {
        has_supporting_document: hasSupportingDocument,
      },
      comment: comment || null,
    };
  }

  async function saveDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setErrorCode(null);
    setValidationErrors([]);
    setSuccessApplicationId(null);
    try {
      const validation = await requestJson<{ status: string; errors: ValidationError[] }>("/cargo/applications/validate", {
        method: "POST",
        body: JSON.stringify(payload()),
      });
      if (validation.status !== "ok") {
        setValidationErrors(validation.errors);
        return;
      }
      const saved = await requestJson<{ status: string; id?: string; errors?: ValidationError[] }>(
        "/cargo/applications/draft",
        {
          method: "POST",
          body: JSON.stringify(payload()),
        },
      );
      if (saved.status !== "ok") {
        setValidationErrors(saved.errors ?? []);
        return;
      }
      setSuccessApplicationId(saved.id ?? null);
      setUploadedDocumentCount(0);
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "CARGO_APPLICATION_VALIDATION_FAILED");
    } finally {
      setIsSaving(false);
    }
  }

  async function submitApplication() {
    if (!successApplicationId) {
      return;
    }
    setIsSubmitting(true);
    setErrorCode(null);
    setValidationErrors([]);
    try {
      const submitted = await requestJson<{ status: string; errors?: ValidationError[]; id?: string }>(
        `/cargo/applications/${successApplicationId}/submit`,
        { method: "POST" },
      );
      if (submitted.status !== "ok") {
        setValidationErrors(submitted.errors ?? []);
        return;
      }
      window.location.href = `/applications/${submitted.id ?? successApplicationId}`;
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "APPLICATION_SUBMIT_FAILED");
    } finally {
      setIsSubmitting(false);
    }
  }

  const countries = referenceData?.countries ?? [];
  const cargoTypes = referenceData?.cargo_types ?? [];
  const transportTypes = referenceData?.transport_types ?? [];
  const currencies = referenceData?.currencies ?? [];

  return (
    <section className="workspacePanel autoFormPanel">
      <div className="sectionHeader">
        <div>
          <p className="sectionLabel">{t(locale, "cargoApplication.sectionLabel")}</p>
          <h1>{t(locale, "cargoApplication.title")}</h1>
        </div>
        <Link className="secondaryLink" href="/applications">
          {t(locale, "applications.backToList")}
        </Link>
      </div>

      {!selectedCompany ? <p className="stateText">{t(locale, "cargoApplication.companyRequired")}</p> : null}
      {selectedCompany ? (
        <p className="stateText">
          {t(locale, "cargoApplication.selectedCompany")}: {companyTitle(locale, selectedCompany)}
        </p>
      ) : null}
      {isLoadingCompanies || isLoadingReferenceData ? (
        <p className="stateText">{t(locale, "cargoApplication.loadingReferenceData")}</p>
      ) : null}
      {errorCode ? (
        <p className="errorText" role="alert">
          {errorMessage(locale, errorCode)}
        </p>
      ) : null}
      {validationErrors.length > 0 ? (
        <div className="errorText" role="alert">
          {validationErrors.map((error) => (
            <p key={`${error.field}-${error.error_code}`}>{error.message}</p>
          ))}
        </div>
      ) : null}
      {successApplicationId ? (
        <p className="stateText success">
          {t(locale, "cargoApplication.saved")}: {successApplicationId}
        </p>
      ) : null}

      <form className="autoApplicationForm" onSubmit={saveDraft}>
        <section className="preparedBlock">
          <h2>{t(locale, "cargoApplication.typeSection")}</h2>
          <div className="productChoiceGrid">
            {(referenceData?.application_types ?? []).map((item) => (
              <button
                className={cargoApplicationType === item.code ? "productChoice selected" : "productChoice"}
                key={item.code}
                onClick={() => setCargoApplicationType(item.code)}
                type="button"
              >
                <strong>{item.label}</strong>
                <small>{item.product_type_code}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="preparedBlock">
          <h2>{t(locale, "cargoApplication.routeSection")}</h2>
          <div className="filtersBar">
            <label>
              <span>{t(locale, "cargoApplication.countryFrom")}</span>
              <select onChange={(event) => setCountryFrom(event.target.value)} value={countryFrom}>
                <option value="">{t(locale, "cargoApplication.notSelected")}</option>
                {countries.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>{t(locale, "cargoApplication.countryTo")}</span>
              <select onChange={(event) => setCountryTo(event.target.value)} value={countryTo}>
                <option value="">{t(locale, "cargoApplication.notSelected")}</option>
                {countries.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            <span>{t(locale, "cargoApplication.routeDescription")}</span>
            <textarea onChange={(event) => setRouteDescription(event.target.value)} value={routeDescription} />
          </label>
        </section>

        <section className="preparedBlock">
          <h2>{t(locale, "cargoApplication.cargoSection")}</h2>
          <div className="filtersBar">
            <label>
              <span>{t(locale, "cargoApplication.cargoType")}</span>
              <select onChange={(event) => setCargoType(event.target.value)} value={cargoType}>
                <option value="">{t(locale, "cargoApplication.notSelected")}</option>
                {cargoTypes.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>{t(locale, "cargoApplication.cargoValue")}</span>
              <input min="0" onChange={(event) => setCargoValue(event.target.value)} type="number" value={cargoValue} />
            </label>
            <label>
              <span>{t(locale, "cargoApplication.currency")}</span>
              <select onChange={(event) => setCurrency(event.target.value)} value={currency}>
                <option value="">{t(locale, "cargoApplication.notSelected")}</option>
                {currencies.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            <span>{t(locale, "cargoApplication.cargoDescription")}</span>
            <textarea onChange={(event) => setCargoDescription(event.target.value)} value={cargoDescription} />
          </label>
        </section>

        <section className="preparedBlock">
          <h2>{t(locale, "cargoApplication.transportSection")}</h2>
          <div className="filtersBar">
            <label>
              <span>{t(locale, "cargoApplication.transportType")}</span>
              <select onChange={(event) => setTransportType(event.target.value)} value={transportType}>
                <option value="">{t(locale, "cargoApplication.notSelected")}</option>
                {transportTypes.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>{t(locale, "cargoApplication.carrierName")}</span>
              <input onChange={(event) => setCarrierName(event.target.value)} value={carrierName} />
            </label>
            <label>
              <span>{t(locale, "cargoApplication.vehiclePlate")}</span>
              <input onChange={(event) => setVehiclePlate(event.target.value)} value={vehiclePlate} />
            </label>
            <label>
              <span>{t(locale, "cargoApplication.departureDate")}</span>
              <input onChange={(event) => setDepartureDate(event.target.value)} type="date" value={departureDate} />
            </label>
          </div>
        </section>

        {requiresContract ? (
          <section className="preparedBlock">
            <h2>{t(locale, "cargoApplication.contractSection")}</h2>
            <div className="filtersBar">
              <label>
                <span>{t(locale, "cargoApplication.contractNumber")}</span>
                <input onChange={(event) => setContractNumber(event.target.value)} value={contractNumber} />
              </label>
              <label>
                <span>{t(locale, "cargoApplication.contractDealId")}</span>
                <input onChange={(event) => setContractDealId(event.target.value)} type="number" value={contractDealId} />
              </label>
              <label className="toggleFilter">
                <input
                  checked={isActiveContract}
                  onChange={(event) => setIsActiveContract(event.target.checked)}
                  type="checkbox"
                />
                <span>{t(locale, "cargoApplication.activeContract")}</span>
              </label>
              <label className="toggleFilter">
                <input
                  checked={isCertificateRequested}
                  disabled={cargoApplicationType !== "certificate"}
                  onChange={(event) => setIsCertificateRequested(event.target.checked)}
                  type="checkbox"
                />
                <span>{t(locale, "cargoApplication.certificateRequested")}</span>
              </label>
            </div>
          </section>
        ) : null}

        <DocumentUploadPanel
          applicationId={successApplicationId}
          documentTypes={[
            { code: "invoice", label: t(locale, "cargoDocumentTypes.invoice.label") },
            { code: "cmr", label: t(locale, "cargoDocumentTypes.cmr.label") },
            { code: "transport_document", label: t(locale, "cargoApplication.transportDocument") },
            { code: "cargo_description", label: t(locale, "cargoApplication.cargoDescriptionDocument") },
            { code: "contract", label: t(locale, "cargoDocumentTypes.contract.label") },
            { code: "certificate_basis", label: t(locale, "cargoApplication.certificateBasis") },
            { code: "other", label: t(locale, "cargoDocumentTypes.other.label") },
          ]}
          initialDocumentType="invoice"
          locale={locale}
          onDocumentCountChange={(count) => {
            setUploadedDocumentCount(count);
            setHasSupportingDocument(count > 0);
          }}
          requestForm={requestForm}
          requestJson={requestJson}
        />

        <section className="preparedBlock">
          <h2>{t(locale, "cargoApplication.commentSection")}</h2>
          <label>
            <span>{t(locale, "cargoApplication.comment")}</span>
            <textarea onChange={(event) => setComment(event.target.value)} value={comment} />
          </label>
        </section>

        <div className="formActions">
          <button className="primaryButton" disabled={!canSave || isSaving} type="submit">
            {t(locale, "cargoApplication.saveDraft")}
          </button>
          <button
            className="secondaryButton"
            disabled={!successApplicationId || uploadedDocumentCount === 0 || isSubmitting}
            onClick={submitApplication}
            type="button"
          >
            {t(locale, "cargoApplication.submit")}
          </button>
        </div>
      </form>
    </section>
  );
}

export default function NewCargoApplicationPage() {
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
        {!isLoading && user ? <CargoApplicationForm locale={locale} /> : null}
      </main>
    </CompanyContextProvider>
  );
}
