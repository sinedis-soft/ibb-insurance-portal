"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

const storageKey = "ibb.selectedCompanyId";

export type CompanyAccess = {
  id: string;
  user_id: string;
  bitrix_company_id: string;
  role_code: string;
  access_status: string;
  bitrix_link_status?: string | null;
  company_title?: string | null;
  company_country_code?: string | null;
  confirmed_at?: string | null;
  revoked_at?: string | null;
  created_at?: string | null;
};

type CompanyContextValue = {
  availableCompanies: CompanyAccess[];
  selectedCompany: CompanyAccess | null;
  selectedCompanyId: string | null;
  isLoadingCompanies: boolean;
  companyErrorCode: string | null;
  contextVersion: number;
  reloadCompanies: () => Promise<void>;
  setSelectedCompanyId: (companyId: string | null) => void;
  clearCompanyContext: () => void;
};

const CompanyContext = createContext<CompanyContextValue | null>(null);

type ProviderProps = {
  children: ReactNode;
  isAuthenticated: boolean;
  isClientUser: boolean;
  requestJson: <T>(path: string, options?: RequestInit) => Promise<T>;
};

export function CompanyContextProvider({
  children,
  isAuthenticated,
  isClientUser,
  requestJson,
}: ProviderProps) {
  const [availableCompanies, setAvailableCompanies] = useState<CompanyAccess[]>([]);
  const [selectedCompanyId, setSelectedCompanyIdState] = useState<string | null>(null);
  const [isLoadingCompanies, setIsLoadingCompanies] = useState(false);
  const [companyErrorCode, setCompanyErrorCode] = useState<string | null>(null);
  const [contextVersion, setContextVersion] = useState(0);

  useEffect(() => {
    setSelectedCompanyIdState(window.localStorage.getItem(storageKey));
  }, []);

  const clearCompanyContext = useCallback(() => {
    window.localStorage.removeItem(storageKey);
    setSelectedCompanyIdState(null);
    setAvailableCompanies([]);
    setCompanyErrorCode(null);
    setContextVersion((value) => value + 1);
  }, []);

  const setSelectedCompanyId = useCallback(
    (companyId: string | null) => {
      if (companyId === null) {
        clearCompanyContext();
        return;
      }
      const isAvailable = availableCompanies.some((company) => company.bitrix_company_id === companyId);
      if (!isAvailable) {
        window.localStorage.removeItem(storageKey);
        setSelectedCompanyIdState(null);
        setCompanyErrorCode("COMPANY_ACCESS_DENIED");
        setContextVersion((value) => value + 1);
        return;
      }
      window.localStorage.setItem(storageKey, companyId);
      setSelectedCompanyIdState(companyId);
      setCompanyErrorCode(null);
      setContextVersion((value) => value + 1);
    },
    [availableCompanies, clearCompanyContext],
  );

  const reloadCompanies = useCallback(async () => {
    if (!isAuthenticated || !isClientUser) {
      clearCompanyContext();
      return;
    }
    setIsLoadingCompanies(true);
    setCompanyErrorCode(null);
    try {
      const data = await requestJson<{ items: CompanyAccess[] }>("/me/companies");
      const items = data.items.filter((company) => company.access_status === "active");
      const storedCompanyId = window.localStorage.getItem(storageKey);
      const storedCompany = storedCompanyId
        ? items.find((company) => company.bitrix_company_id === storedCompanyId)
        : null;
      const nextSelectedCompany = storedCompany ?? (items.length === 1 ? items[0] : null);
      setAvailableCompanies(items);
      if (nextSelectedCompany) {
        window.localStorage.setItem(storageKey, nextSelectedCompany.bitrix_company_id);
        setSelectedCompanyIdState(nextSelectedCompany.bitrix_company_id);
      } else {
        window.localStorage.removeItem(storageKey);
        setSelectedCompanyIdState(null);
      }
      if (storedCompanyId && !storedCompany && items.length !== 1) {
        setCompanyErrorCode("COMPANY_ACCESS_DENIED");
      }
      setContextVersion((value) => value + 1);
    } catch (error) {
      setAvailableCompanies([]);
      setSelectedCompanyIdState(null);
      window.localStorage.removeItem(storageKey);
      setCompanyErrorCode(error instanceof Error ? error.message : "COMPANY_ACCESS_DENIED");
      setContextVersion((value) => value + 1);
    } finally {
      setIsLoadingCompanies(false);
    }
  }, [clearCompanyContext, isAuthenticated, isClientUser, requestJson]);

  useEffect(() => {
    void reloadCompanies();
  }, [reloadCompanies]);

  const selectedCompany = useMemo(
    () => availableCompanies.find((company) => company.bitrix_company_id === selectedCompanyId) ?? null,
    [availableCompanies, selectedCompanyId],
  );

  const value = useMemo(
    () => ({
      availableCompanies,
      selectedCompany,
      selectedCompanyId,
      isLoadingCompanies,
      companyErrorCode,
      contextVersion,
      reloadCompanies,
      setSelectedCompanyId,
      clearCompanyContext,
    }),
    [
      availableCompanies,
      clearCompanyContext,
      companyErrorCode,
      contextVersion,
      isLoadingCompanies,
      reloadCompanies,
      selectedCompany,
      selectedCompanyId,
      setSelectedCompanyId,
    ],
  );

  return <CompanyContext.Provider value={value}>{children}</CompanyContext.Provider>;
}

export function useCompanyContext() {
  const context = useContext(CompanyContext);
  if (!context) {
    throw new Error("CompanyContextProvider is missing");
  }
  return context;
}
