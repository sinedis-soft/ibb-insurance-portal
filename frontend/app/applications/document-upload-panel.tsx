"use client";

import { useEffect, useState } from "react";

import { type Locale, t } from "../../lib/i18n";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type DocumentTypeOption = {
  code: string;
  label: string;
};

type PortalDocument = {
  id: string;
  document_type: string;
  mime_type: string | null;
  file_size: number | null;
  transfer_status: string;
  uploaded_at: string | null;
  is_download_available: boolean;
};

type DocumentUploadPanelProps = {
  applicationId: string | null;
  documentTypes: DocumentTypeOption[];
  initialDocumentType: string;
  locale: Locale;
  onDocumentCountChange?: (count: number) => void;
  requestJson: <T = unknown>(path: string, options?: RequestInit) => Promise<T>;
  requestForm: <T = unknown>(path: string, body: FormData, options?: RequestInit) => Promise<T>;
};

function errorMessage(locale: Locale, code: string) {
  const message = t(locale, `errors.${code}`);
  return message === `errors.${code}` ? t(locale, "errors.fallback") : message;
}

function documentTypeLabel(documentTypes: DocumentTypeOption[], code: string) {
  return documentTypes.find((item) => item.code === code)?.label ?? code;
}

export function DocumentUploadPanel({
  applicationId,
  documentTypes,
  initialDocumentType,
  locale,
  onDocumentCountChange,
  requestJson,
  requestForm,
}: DocumentUploadPanelProps) {
  const [documentType, setDocumentType] = useState(initialDocumentType);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [documents, setDocuments] = useState<PortalDocument[]>([]);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);

  async function loadDocuments() {
    if (!applicationId) {
      setDocuments([]);
      onDocumentCountChange?.(0);
      return;
    }
    setIsLoading(true);
    setErrorCode(null);
    try {
      const data = await requestJson<{ items: PortalDocument[] }>(`/applications/${applicationId}/documents`);
      setDocuments(data.items);
      onDocumentCountChange?.(data.items.filter((item) => item.transfer_status !== "deleted").length);
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "DOCUMENT_UPLOAD_FAILED");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadDocuments();
  }, [applicationId]);

  async function uploadDocument() {
    if (!applicationId || !documentFile) {
      return;
    }
    setIsUploading(true);
    setErrorCode(null);
    const formData = new FormData();
    formData.set("document_type", documentType);
    formData.set("file", documentFile);
    try {
      await requestForm(`/applications/${applicationId}/documents`, formData);
      setDocumentFile(null);
      await loadDocuments();
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "DOCUMENT_UPLOAD_FAILED");
    } finally {
      setIsUploading(false);
    }
  }

  async function deleteDocument(documentId: string) {
    if (!applicationId) {
      return;
    }
    setDeletingDocumentId(documentId);
    setErrorCode(null);
    try {
      await requestJson(`/applications/${applicationId}/documents/${documentId}`, { method: "DELETE" });
      await loadDocuments();
    } catch (error) {
      setErrorCode(error instanceof Error ? error.message : "DOCUMENT_DELETE_NOT_ALLOWED");
    } finally {
      setDeletingDocumentId(null);
    }
  }

  return (
    <section className="preparedBlock">
      <h2>{t(locale, "documentsPanel.title")}</h2>
      {errorCode ? (
        <p className="errorText" role="alert">
          {errorMessage(locale, errorCode)}
        </p>
      ) : null}
      <div className="filtersBar">
        <label>
          <span>{t(locale, "documentsPanel.documentType")}</span>
          <select onChange={(event) => setDocumentType(event.target.value)} value={documentType}>
            {documentTypes.map((item) => (
              <option key={item.code} value={item.code}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t(locale, "documentsPanel.documentFile")}</span>
          <input onChange={(event) => setDocumentFile(event.target.files?.[0] ?? null)} type="file" />
        </label>
      </div>
      <button
        className="secondaryButton"
        disabled={!applicationId || !documentFile || isUploading}
        onClick={uploadDocument}
        type="button"
      >
        {t(locale, "documentsPanel.upload")}
      </button>
      {isLoading ? <p className="stateText">{t(locale, "documentsPanel.loading")}</p> : null}
      {documents.length > 0 ? (
        <div className="documentList">
          {documents.map((document) => (
            <div className="documentListItem" key={document.id}>
              <div>
                <strong>{documentTypeLabel(documentTypes, document.document_type)}</strong>
                <small>
                  {t(locale, `documentStatuses.${document.transfer_status}`)} · {document.file_size ?? 0} B
                </small>
              </div>
              <div className="inlineActions">
                {document.is_download_available ? (
                  <a
                    className="secondaryLink"
                    href={`${apiBaseUrl}/applications/${applicationId}/documents/${document.id}/download`}
                  >
                    {t(locale, "documentsPanel.download")}
                  </a>
                ) : null}
                {document.transfer_status !== "sent" && document.transfer_status !== "deleted" ? (
                  <button
                    className="secondaryButton"
                    disabled={deletingDocumentId === document.id}
                    onClick={() => deleteDocument(document.id)}
                    type="button"
                  >
                    {t(locale, "documentsPanel.delete")}
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="stateText">{t(locale, "documentsPanel.empty")}</p>
      )}
    </section>
  );
}
