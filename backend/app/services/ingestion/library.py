"""Adding a file to the document library: validate, de-duplicate, store, parse, audit.

Shared by the upload API and the `flask seed-core` command.
"""
from pathlib import Path

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...models import Document, DocumentStatus
from ...utils.audit import record_audit
from ...utils.errors import ConflictError, ValidationError
from .parsers import ParseError, parse_document
from .storage import content_hash, delete_file, save_bytes
from .validation import validate_upload


def add_document(data: bytes, filename: str, category, user_id: int, title: str | None = None) -> Document:
    original_filename = Path(filename).name[:255]
    title = (title or Path(original_filename).stem).strip()[:255]
    if not title:
        raise ValidationError("title is required", details={"title": "Required"})

    file_type = validate_upload(original_filename, data, current_app.config["MAX_DOCUMENT_BYTES"])
    digest = content_hash(data)
    existing = db.session.execute(select(Document).filter_by(content_hash=digest)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(
            "This file has already been uploaded",
            code="DUPLICATE_DOCUMENT",
            details={"document_id": existing.document_id, "title": existing.title},
        )

    path = save_bytes(data, current_app.config["UPLOAD_FOLDER"], file_type.value)
    document = Document(
        user_id=user_id, title=title, file_path=path, file_type=file_type, source_category=category,
        original_filename=original_filename, file_size=len(data), content_hash=digest,
    )
    # Parse immediately so broken files are reported at upload time, not mid-analysis.
    try:
        parsed = parse_document(data, file_type)
    except ParseError as exc:
        document.processing_status = DocumentStatus.FAILED
        document.error_message = str(exc)
    except Exception:
        current_app.logger.exception("Unexpected parser failure for %s", original_filename)
        document.processing_status = DocumentStatus.FAILED
        document.error_message = "Unexpected error while extracting text"
    else:
        document.processing_status = DocumentStatus.PARSED
        document.extracted_text = parsed.text
        document.word_count = parsed.word_count
        document.page_count = parsed.page_count

    db.session.add(document)
    try:
        db.session.flush()
        record_audit(
            "DOCUMENT_UPLOAD", "Document", document.document_id,
            {"title": title, "source_category": category.value, "status": document.processing_status.value},
            user_id=user_id, commit=False,
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()  # lost a race with a concurrent upload of the same file
        delete_file(path)
        raise ConflictError("This file has already been uploaded", code="DUPLICATE_DOCUMENT")
    except Exception:
        db.session.rollback()
        delete_file(path)
        raise
    return document
