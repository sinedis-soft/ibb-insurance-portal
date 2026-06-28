"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { CompanyContextProvider, useCompanyContext } from "../../../../lib/company-context";
import { DEFAULT_LOCALE, type Locale, normalizeLocale, t } from "../../../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const countryCodes = ["PL", "KZ", "GE", "BY", "RU", "LV", "LT", "EU", "OTHER"];

type CurrentUser = {
  id: string;
  role: string;
  user_type: string;
  language: Locale;
  status: string;
};

type AutoProduct = {
  code: string;
  label: string;
  description: string;
  can_create: boolean;
  requires_manual_review: boolean;
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

function AutoApplicationForm({ locale }: { locale: Locale }) {
  const { selectedCompany, selectedCompanyId, isLoadingCompanies, contextVersion } = useCompanyContext();
  const [vehicleCountry, setVehicleCountry] = useState("GE");
  const [coverageCountry, setCoverageCountry] = useState("PL");
  const [coverageZone, setCoverageZone] = useState("EU");
  const [products, setProducts] = useState<AutoProduct[]>([]);
  const [productCode, setProductCode] = useState("");
  const [plateNumber, setPlateNumber] = useState("");
  const [vin, setVin] = useState("");
  const [vehicleType, setVehicleType] = useState("");
  const [brandModel, setBrandModel] = useState("");
  const [productionYear, setProductionYear] = useState("");
  const [engineVolume, setEngineVolume] = useState("");
  const [powerKw, setPowerKw] = useState("");
  const [isLeased, setIsLeased] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [durationDays, setDurationDays] = useState("30");
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [successApplicationId, setSuccessApplicationId] = useState<string | null>(null);
  const [documentType, setDocumentType] = useState("vehicle_registration_certificate");
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [uploadedDocuments, setUploadedDocuments] = useState<string[]>([]);
  const [isLoadingProducts, setIsLoadingProducts] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function loadProducts() {
      setProducts([]);
      setValidationErrors([]);
      setErrorCode(null);
      setSuccessApplicationId(null);
      if (isLoadingCompanies || !selectedCompanyId || !vehicleCountry) {
        return;
      }
      setIsLoadingProducts(true);
      const params = new URLSearchParams({
        company_id: selectedCompanyId,
        vehicle_registration_country_code: vehicleCountry,
      });
      if (coverageCountry) {
        params.set("coverage_country_code", coverageCountry);
      }
      if (coverageZone) {
        params.set("coverage_zone_code", coverageZone);
      }
      try {
        const data = await requestJson<{ items: AutoProduct[] }>(`/auto/products/available?${params.toString()}`);
        if (isMounted) {
          setProducts(data.items);
          if (productCode && !data.items.some((item) => item.code === productCode)) {
            setProductCode("");
            setValidationErrors([
              {
                field: "product_code",
                error_code: "AUTO_PRODUCT_NOT_AVAILABLE",
                message: errorMessage(locale, "AUTO_PRODUCT_NOT_AVAILABLE"),
              },
            ]);
          }
        }
      } catch (error) {
        if (isMounted) {
          setErrorCode(error instanceof Error ? error.message : "AUTO_PRODUCT_NOT_AVAILABLE");
        }
      } finally {
        if (isMounted) {
          setIsLoadingProducts(false);
        }
      }
    }
    void loadProducts();
    return () => {
      isMounted = false;
    };
  }, [
    contextVersion,
    coverageCountry,
    coverageZone,
    isLoadingCompanies,
    locale,
    productCode,
    selectedCompanyId,
    vehicleCountry,
  ]);

  const canSave = useMemo(
    () => Boolean(selectedCompanyId && productCode && plateNumber && startDate && durationDays),
    [durationDays, plateNumber, productCode, selectedCompanyId, startDate],
  );

  function payload() {
    return {
      company_id: selectedCompanyId,
      product_code: productCode,
      vehicle_registration_country_code: vehicleCountry,
      coverage_country_code: coverageCountry || null,
      coverage_zone_code: coverageZone || null,
      vehicle: {
        plate_number: plateNumber,
        vin: vin || null,
        vehicle_type: vehicleType || null,
        brand_model: brandModel || null,
        production_year: productionYear ? Number(productionYear) : null,
        engine_volume: engineVolume ? Number(engineVolume) : null,
        power_kw: powerKw ? Number(powerKw) : null,
        is_leased: isLeased,
      },
      period: {
        start_date: startDate || null,
        duration_days: durationDays ? Number(durationDays) : null,
      },
    };
  }

  async function saveDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setErrorCode(null);
    setValidationErrors([]);
    setSuccessApplicationId(null);
    try {
      const validation = await requestJson<{ status: string; errors: ValidationError[] }>("/auto/applications/validate", {
        method: "POST",
        body: JSON.stringify(payload()),
      });
      if (validation.status !== "ok") {
        setValidationErrors(validation.errors);
        return;
      }
      const saved = await requestJson<{ status: string; id?: string; errors?: ValidationError[] }>(
        "/auto/applications/draft",
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
      setUploadedDocuments([]);
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "AUTO_APPLICATION_VALIDATION_FAILED");
    } finally {
      setIsSaving(false);
    }
  }

  async function uploadDocument() {
    if (!successApplicationId || !documentFile) {
      return;
    }
    setIsUploading(true);
    setErrorCode(null);
    const formData = new FormData();
    formData.set("document_type", documentType);
    formData.set("file", documentFile);
    try {
      const uploaded = await requestForm<{ document: { id: string; document_type: string } }>(
        `/applications/${successApplicationId}/documents`,
        formData,
      );
      setUploadedDocuments((items) => [...items, uploaded.document.document_type]);
      setDocumentFile(null);
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "DOCUMENT_UPLOAD_FAILED");
    } finally {
      setIsUploading(false);
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
        `/auto/applications/${successApplicationId}/submit`,
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

  return (
    <section className="workspacePanel autoFormPanel">
      <div className="sectionHeader">
        <div>
          <p className="sectionLabel">{t(locale, "autoApplication.sectionLabel")}</p>
          <h1>{t(locale, "autoApplication.title")}</h1>
        </div>
        <Link className="secondaryLink" href="/applications">
          {t(locale, "applications.backToList")}
        </Link>
      </div>

      {!selectedCompany ? <p className="stateText">{t(locale, "autoApplication.companyRequired")}</p> : null}
      {selectedCompany ? (
        <p className="stateText">
          {t(locale, "autoApplication.selectedCompany")}: {selectedCompany.company_title || selectedCompany.bitrix_company_id}
        </p>
      ) : null}
      {isLoadingProducts ? <p className="stateText">{t(locale, "autoApplication.loadingProducts")}</p> : null}
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
          {t(locale, "autoApplication.saved")}: {successApplicationId}
        </p>
      ) : null}

      <form className="autoApplicationForm" onSubmit={saveDraft}>
        <section className="preparedBlock">
          <h2>{t(locale, "autoApplication.coverageSection")}</h2>
          <div className="filtersBar">
            <label>
              <span>{t(locale, "autoApplication.vehicleCountry")}</span>
              <select onChange={(event) => setVehicleCountry(event.target.value)} value={vehicleCountry}>
                {countryCodes.map((code) => (
                  <option key={code} value={code}>
                    {t(locale, `countries.${code}`)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>{t(locale, "autoApplication.coverageCountry")}</span>
              <select onChange={(event) => setCoverageCountry(event.target.value)} value={coverageCountry}>
                <option value="">{t(locale, "autoApplication.notSelected")}</option>
                {countryCodes.map((code) => (
                  <option key={code} value={code}>
                    {t(locale, `countries.${code}`)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>{t(locale, "autoApplication.coverageZone")}</span>
              <select onChange={(event) => setCoverageZone(event.target.value)} value={coverageZone}>
                <option value="">{t(locale, "autoApplication.notSelected")}</option>
                <option value="EU">{t(locale, "countries.EU")}</option>
                <option value="OTHER">{t(locale, "countries.OTHER")}</option>
              </select>
            </label>
            <label>
              <span>{t(locale, "autoApplication.startDate")}</span>
              <input onChange={(event) => setStartDate(event.target.value)} type="date" value={startDate} />
            </label>
            <label>
              <span>{t(locale, "autoApplication.durationDays")}</span>
              <input
                min="1"
                max="366"
                onChange={(event) => setDurationDays(event.target.value)}
                type="number"
                value={durationDays}
              />
            </label>
          </div>
        </section>

        <section className="preparedBlock">
          <h2>{t(locale, "autoApplication.productSection")}</h2>
          {products.length === 0 ? <p className="stateText">{t(locale, "autoApplication.noProducts")}</p> : null}
          <div className="productChoiceGrid">
            {products.map((product) => (
              <button
                className={productCode === product.code ? "productChoice selected" : "productChoice"}
                key={product.code}
                onClick={() => setProductCode(product.code)}
                type="button"
              >
                <strong>{product.label}</strong>
                <small>{product.description}</small>
                {product.requires_manual_review ? <span>{t(locale, "autoApplication.manualReview")}</span> : null}
              </button>
            ))}
          </div>
        </section>

        <section className="preparedBlock">
          <h2>{t(locale, "autoApplication.vehicleSection")}</h2>
          <div className="filtersBar">
            <label>
              <span>{t(locale, "autoApplication.plateNumber")}</span>
              <input onChange={(event) => setPlateNumber(event.target.value)} value={plateNumber} />
            </label>
            <label>
              <span>{t(locale, "autoApplication.vin")}</span>
              <input onChange={(event) => setVin(event.target.value)} value={vin} />
            </label>
            <label>
              <span>{t(locale, "autoApplication.vehicleType")}</span>
              <input onChange={(event) => setVehicleType(event.target.value)} value={vehicleType} />
            </label>
            <label>
              <span>{t(locale, "autoApplication.brandModel")}</span>
              <input onChange={(event) => setBrandModel(event.target.value)} value={brandModel} />
            </label>
            <label>
              <span>{t(locale, "autoApplication.productionYear")}</span>
              <input onChange={(event) => setProductionYear(event.target.value)} type="number" value={productionYear} />
            </label>
            <label>
              <span>{t(locale, "autoApplication.engineVolume")}</span>
              <input onChange={(event) => setEngineVolume(event.target.value)} type="number" value={engineVolume} />
            </label>
            <label>
              <span>{t(locale, "autoApplication.powerKw")}</span>
              <input onChange={(event) => setPowerKw(event.target.value)} type="number" value={powerKw} />
            </label>
            <label className="toggleFilter">
              <input checked={isLeased} onChange={(event) => setIsLeased(event.target.checked)} type="checkbox" />
              <span>{t(locale, "autoApplication.isLeased")}</span>
            </label>
          </div>
        </section>

        <section className="preparedBlock">
          <h2>{t(locale, "autoApplication.documentsSection")}</h2>
          <div className="filtersBar">
            <label>
              <span>{t(locale, "autoApplication.documentType")}</span>
              <select onChange={(event) => setDocumentType(event.target.value)} value={documentType}>
                <option value="vehicle_registration_certificate">
                  {t(locale, "autoApplication.vehicleRegistrationCertificate")}
                </option>
                <option value="lease_agreement">{t(locale, "autoApplication.leaseAgreement")}</option>
                <option value="previous_policy">{t(locale, "autoApplication.previousPolicy")}</option>
                <option value="other">{t(locale, "autoApplication.otherDocument")}</option>
              </select>
            </label>
            <label>
              <span>{t(locale, "autoApplication.documentFile")}</span>
              <input onChange={(event) => setDocumentFile(event.target.files?.[0] ?? null)} type="file" />
            </label>
          </div>
          <button
            className="secondaryButton"
            disabled={!successApplicationId || !documentFile || isUploading}
            onClick={uploadDocument}
            type="button"
          >
            {t(locale, "autoApplication.uploadDocument")}
          </button>
          {uploadedDocuments.length > 0 ? (
            <p className="stateText success">
              {t(locale, "autoApplication.uploadedDocuments")}: {uploadedDocuments.length}
            </p>
          ) : null}
        </section>

        <div className="formActions">
          <button className="primaryButton" disabled={!canSave || isSaving} type="submit">
            {t(locale, "autoApplication.saveDraft")}
          </button>
          <button
            className="secondaryButton"
            disabled={!successApplicationId || uploadedDocuments.length === 0 || isSubmitting}
            onClick={submitApplication}
            type="button"
          >
            {t(locale, "autoApplication.submit")}
          </button>
        </div>
      </form>
    </section>
  );
}

export default function NewAutoApplicationPage() {
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
        {!isLoading && user ? <AutoApplicationForm locale={locale} /> : null}
      </main>
    </CompanyContextProvider>
  );
}
