from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.document_transfer import cleanup_temporary_documents, process_document_transfer_queue, storage_path
from app.models import audit_logs, document_transfer_logs, portal_applications
from tests.test_auto_applications import auto_payload, create_client, login, seed_users


def prepare_application(monkeypatch, migrated_database: str, tmp_path: Path) -> tuple[str, object]:
    monkeypatch.setenv("DOCUMENT_TEMP_STORAGE_PATH", str(tmp_path / "documents"))
    client = create_client(monkeypatch, migrated_database)
    seed_users(migrated_database)
    login(client, "executor@example.com")
    saved = client.post("/auto/applications/draft", json=auto_payload())
    assert saved.status_code == 200
    return saved.json()["id"], client


def upload_pdf(client, application_id: str, *, document_type: str = "vehicle_registration_certificate"):
    return client.post(
        f"/applications/{application_id}/documents",
        data={"document_type": document_type},
        files={"file": ("registration.pdf", b"%PDF-1.4 safe", "application/pdf")},
    )


def test_upload_list_download_and_delete_are_application_scoped(
    monkeypatch,
    migrated_database: str,
    tmp_path: Path,
) -> None:
    application_id, client = prepare_application(monkeypatch, migrated_database, tmp_path)

    upload = upload_pdf(client, application_id)
    assert upload.status_code == 200
    document = upload.json()["document"]
    document_id = document["id"]
    assert document["transfer_status"] == "uploaded"
    assert document["file_size"] == len(b"%PDF-1.4 safe")
    assert document["is_download_available"] is True
    assert "storage_key" not in document
    assert "temporary_storage_path" not in document
    assert "bitrix_file_id" not in document
    assert "filename" not in str(document).lower()

    listed = client.get(f"/applications/{application_id}/documents")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == document_id

    direct_download = client.get(f"/documents/{document_id}/download")
    assert direct_download.status_code == 404
    assert direct_download.json()["error_code"] == "DOCUMENT_NOT_FOUND"

    scoped_download = client.get(f"/applications/{application_id}/documents/{document_id}/download")
    assert scoped_download.status_code == 200
    assert scoped_download.content == b"%PDF-1.4 safe"
    assert "registration" not in scoped_download.headers["content-disposition"].lower()

    deleted = client.delete(f"/applications/{application_id}/documents/{document_id}")
    assert deleted.status_code == 200

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(document_transfer_logs)).mappings().one()
            assert row.transfer_status == "deleted"
            assert row.local_deleted_at is not None
            assert not storage_path(row.storage_key).exists()
    finally:
        engine.dispose()


def test_upload_rejects_type_extension_mime_and_limit(
    monkeypatch,
    migrated_database: str,
    tmp_path: Path,
) -> None:
    application_id, client = prepare_application(monkeypatch, migrated_database, tmp_path)

    invalid_type = client.post(
        f"/applications/{application_id}/documents",
        data={"document_type": "passport"},
        files={"file": ("registration.pdf", b"%PDF-1.4 safe", "application/pdf")},
    )
    invalid_extension = client.post(
        f"/applications/{application_id}/documents",
        data={"document_type": "vehicle_registration_certificate"},
        files={"file": ("registration.exe", b"binary", "application/octet-stream")},
    )
    invalid_mime = client.post(
        f"/applications/{application_id}/documents",
        data={"document_type": "vehicle_registration_certificate"},
        files={"file": ("registration.pdf", b"%PDF-1.4 safe", "text/plain")},
    )

    assert invalid_type.status_code == 400
    assert invalid_type.json()["error_code"] == "DOCUMENT_TYPE_INVALID"
    assert invalid_extension.status_code == 400
    assert invalid_extension.json()["error_code"] == "DOCUMENT_EXTENSION_NOT_ALLOWED"
    assert invalid_mime.status_code == 400
    assert invalid_mime.json()["error_code"] == "DOCUMENT_MIME_NOT_ALLOWED"

    for index in range(10):
        response = client.post(
            f"/applications/{application_id}/documents",
            data={"document_type": "other"},
            files={"file": (f"doc-{index}.pdf", b"%PDF-1.4 safe", "application/pdf")},
        )
        assert response.status_code == 200
    over_limit = client.post(
        f"/applications/{application_id}/documents",
        data={"document_type": "other"},
        files={"file": ("doc-limit.pdf", b"%PDF-1.4 safe", "application/pdf")},
    )
    assert over_limit.status_code == 400
    assert over_limit.json()["error_code"] == "DOCUMENT_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_transfer_worker_success_deletes_local_file_and_marks_sent(
    monkeypatch,
    migrated_database: str,
    tmp_path: Path,
) -> None:
    application_id, client = prepare_application(monkeypatch, migrated_database, tmp_path)
    upload = upload_pdf(client, application_id)
    assert upload.status_code == 200
    parsed_application_id = int(application_id.removeprefix("app_"))

    async def fake_uploader(document_row, application_row, file_path: Path) -> str:
        assert file_path.exists()
        assert document_row.original_filename == "registration.pdf"
        assert application_row.bitrix_deal_id == 99101
        return "B24-FILE-99101"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(
                update(portal_applications)
                .where(portal_applications.c.id == parsed_application_id)
                .values(bitrix_deal_id=99101)
            )
            session.execute(
                update(document_transfer_logs)
                .where(document_transfer_logs.c.application_id == parsed_application_id)
                .values(bitrix_deal_id=99101)
            )
            session.commit()
            processed = await process_document_transfer_queue(session, uploader=fake_uploader)
            assert processed == 1
            row = session.execute(select(document_transfer_logs)).mappings().one()
            assert row.transfer_status == "sent"
            assert row.bitrix_file_id == "B24-FILE-99101"
            assert row.local_deleted_at is not None
            assert not storage_path(row.storage_key).exists()
            actions = list(session.execute(select(audit_logs.c.action)).scalars())
            assert "document_transferred_to_bitrix" in actions
            assert "document_temporary_file_deleted" in actions
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_transfer_failure_keeps_file_and_cleanup_expires_it(
    monkeypatch,
    migrated_database: str,
    tmp_path: Path,
) -> None:
    application_id, client = prepare_application(monkeypatch, migrated_database, tmp_path)
    upload = upload_pdf(client, application_id)
    assert upload.status_code == 200
    parsed_application_id = int(application_id.removeprefix("app_"))

    async def failing_uploader(_document_row, _application_row, _file_path: Path) -> str:
        raise RuntimeError("transport failed")

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(
                update(portal_applications)
                .where(portal_applications.c.id == parsed_application_id)
                .values(bitrix_deal_id=99102)
            )
            session.execute(
                update(document_transfer_logs)
                .where(document_transfer_logs.c.application_id == parsed_application_id)
                .values(bitrix_deal_id=99102)
            )
            session.commit()
            processed = await process_document_transfer_queue(session, uploader=failing_uploader)
            assert processed == 1
            failed = session.execute(select(document_transfer_logs)).mappings().one()
            assert failed.transfer_status == "retry_required"
            assert failed.retry_count == 1
            assert storage_path(failed.storage_key).exists()

            session.execute(
                update(document_transfer_logs)
                .where(document_transfer_logs.c.id == failed.id)
                .values(expires_at=datetime(2000, 1, 1, tzinfo=UTC))
            )
            session.commit()
            cleaned = await cleanup_temporary_documents(session)
            assert cleaned == 1
            expired = session.execute(select(document_transfer_logs)).mappings().one()
            assert expired.transfer_status == "expired"
            assert expired.local_deleted_at is not None
            assert not storage_path(expired.storage_key).exists()
    finally:
        engine.dispose()


def test_sent_document_cannot_be_deleted(monkeypatch, migrated_database: str, tmp_path: Path) -> None:
    application_id, client = prepare_application(monkeypatch, migrated_database, tmp_path)
    upload = upload_pdf(client, application_id)
    assert upload.status_code == 200
    document_id = upload.json()["document"]["id"]

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(update(document_transfer_logs).values(transfer_status="sent", bitrix_file_id="B24-FILE-1"))
            session.commit()
    finally:
        engine.dispose()

    response = client.delete(f"/applications/{application_id}/documents/{document_id}")
    assert response.status_code == 400
    assert response.json()["error_code"] == "DOCUMENT_ALREADY_SENT"
