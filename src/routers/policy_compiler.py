from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.dependencies import get_db
from src.database.connection import SessionLocal
from src.database.models import PolicyConversionLogModel, PolicyModel
from src.schemas.doc_parser import PolicyConvertResponse
from src.utils.policy_cache import get_policy_cache
from src.workflows.doc_parser_workflow import build_doc_parser_graph

router = APIRouter(prefix="/v1/policy-compiler", tags=["policy-compiler"])
logger = logging.getLogger(__name__)


def _preserve_failed_upload(tmp_path: str, original_filename: str) -> Path:
    """
    PRD 5.3.6: "변환 실패 시 원본 파일과 오류 로그가 보존된다".
    임시파일을 {policy_dir}/failed_uploads/ 로 영구 이동.
    """
    settings = get_settings()
    failed_dir = Path(settings.policy_dir) / "failed_uploads"
    failed_dir.mkdir(parents=True, exist_ok=True)
    preserved_id = uuid.uuid4().hex[:8]
    safe_name = (original_filename or "unknown.docx").replace("/", "_").replace("\\", "_")
    preserved_path = failed_dir / f"failed-{preserved_id}-{safe_name}"
    shutil.copy2(tmp_path, preserved_path)
    return preserved_path


def _log_failed_conversion(
    original_filename: str,
    preserved_path: Path,
    warnings: list[str],
    error_message: str | None,
) -> str:
    """
    F3-2: 실패 케이스도 PolicyConversionLogModel 에 추적 로그 생성.
    storage_writer_node 가 실행되지 않은 경우 라우터에서 직접 INSERT.
    Returns: log id (이게 policy_id 자리에 응답으로 노출됨)
    """
    log_id = str(uuid.uuid4())
    fail_marker = f"failed-{log_id[:8]}"

    session = SessionLocal()
    try:
        session.add(PolicyConversionLogModel(
            id=log_id,
            policy_id=None,         # 실제 정책 미생성 → FK 위반 방지를 위해 NULL
            fail_marker=fail_marker, # 추적용 ID 는 별도 컬럼에 저장
            original_filename=original_filename or "unknown.docx",
            parsed_rules_count=0,
            conversion_status="FAILED",
            warnings=list(warnings) + [
                f"원본 보존 위치: {preserved_path}",
                f"오류: {error_message or '알 수 없음'}",
            ],
        ))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()

    return fail_marker


@router.post("/compile", response_model=PolicyConvertResponse)
async def policy_compile(
    file: UploadFile = File(...),
    policy_name: str = Form(...),
    effective_date: str = Form(...),
) -> PolicyConvertResponse:
    """
    .docx 파일을 YAML 정책으로 변환.
    변환된 정책은 is_active=FALSE → PUT /activate 호출 전까지 Feature 1/2 미적용.

    PRD 5.3.6 보장:
    - 정상 변환: status=SUCCESS / PARTIAL
    - 변환 실패: 원본 .docx 가 {policy_dir}/failed_uploads/ 에 보존되고
                 PolicyConversionLogModel 에도 실패 기록이 남음.
    """
    if not (file.filename or "").endswith(".docx"):
        raise HTTPException(status_code=400, detail=".docx 파일만 허용합니다.")

    max_upload_size = 10 * 1024 * 1024
    written = 0
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_upload_size:
                tmp.close()
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise HTTPException(status_code=413, detail="파일 크기는 10MB 이하여야 합니다.")
            tmp.write(chunk)

    try:
        graph = build_doc_parser_graph()
        settings = get_settings()
        logger.info(
            "Policy compile started filename=%s timeout=%ss",
            file.filename,
            settings.policy_compiler_timeout_seconds,
        )
        try:
            final = await asyncio.wait_for(
                graph.ainvoke({
                    "file_path":      tmp_path,
                    "policy_name":    policy_name,
                    "effective_date": effective_date,
                    "warnings":       [],
                }),
                timeout=settings.policy_compiler_timeout_seconds,
            )
        except asyncio.TimeoutError:
            preserved_path = _preserve_failed_upload(tmp_path, file.filename or "")
            warnings = [
                f"정책 변환 제한 시간 초과: {settings.policy_compiler_timeout_seconds}초",
                f"원본 보존: {preserved_path}",
                "대형 문서는 한국식 조문 draft 또는 더 작은 문서 단위로 나누어 재시도하세요.",
            ]
            fail_marker = _log_failed_conversion(
                original_filename=file.filename or "",
                preserved_path=preserved_path,
                warnings=warnings,
                error_message="policy_compile_timeout",
            )
            return PolicyConvertResponse(
                policy_id=fail_marker,
                yaml_path=None,
                status="FAILED",
                parsed_rules_count=0,
                warnings=warnings,
            )

        has_yaml = bool(final.get("yaml_path"))
        status = "FAILED"
        if has_yaml:
            status = "PARTIAL" if final.get("warnings") else "SUCCESS"

        ext_rules = final.get("extracted_rules", {})
        parsed_count = (
            len(ext_rules.get("compliance_checks", []))
            + len(ext_rules.get("forbidden_words", []))
        )
        warnings = list(final.get("warnings", []))

        if status == "FAILED":
            # F3-1: 원본 보존
            try:
                preserved_path = _preserve_failed_upload(tmp_path, file.filename or "")
                warnings.append(f"원본 보존: {preserved_path}")
            except Exception as e:
                preserved_path = Path("(보존 실패)")
                warnings.append(f"원본 보존 실패: {e}")

            # F3-2: 실패 추적 로그
            fail_marker = _log_failed_conversion(
                original_filename=file.filename or "",
                preserved_path=preserved_path,
                warnings=warnings,
                error_message=final.get("error_message"),
            )

            return PolicyConvertResponse(
                policy_id=fail_marker,  # 실패 추적용 ID
                yaml_path=None,
                status=status,
                parsed_rules_count=parsed_count,
                warnings=warnings,
            )

        return PolicyConvertResponse(
            policy_id=final.get("policy_id"),
            yaml_path=final.get("yaml_path"),
            status=status,
            parsed_rules_count=parsed_count,
            warnings=warnings,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.put("/{policy_id}/activate")
def activate_policy(policy_id: str, db: Session = Depends(get_db)) -> dict:
    """
    정책을 활성화 (is_active=TRUE).
    활성화 후 Feature 1/2의 policy_loader_node에서 즉시 사용 가능.
    """
    row = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")
    row.is_active = True
    db.commit()
    # Phase 3-B: 활성 상태 전환 시 캐시 무효화 (이전 비활성 상태 캐시 잔존 방지)
    get_policy_cache().invalidate(policy_id)
    return {"policy_id": policy_id, "is_active": True, "name": row.name}


@router.get("/{policy_id}")
def get_policy(policy_id: str, db: Session = Depends(get_db)) -> dict:
    """정책 정보 조회."""
    row = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")
    return {
        "policy_id":  row.id,
        "name":       row.name,
        "version":    row.version,
        "yaml_path":  row.yaml_path,
        "is_active":  row.is_active,
        "created_at": str(row.created_at),
    }


# ──────────────────────────────────────────────────────────────
# PRD 9: GET /v1/policy/{policy_id}/yaml — YAML 파일 다운로드
# ──────────────────────────────────────────────────────────────
@router.get("/{policy_id}/yaml", response_class=PlainTextResponse)
def download_policy_yaml(
    policy_id: str,
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    """
    정책 YAML 원문을 다운로드.
    DB의 yaml_path가 가리키는 파일 내용을 그대로 반환.
    """
    row = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")

    yaml_file = Path(row.yaml_path)
    if not yaml_file.exists():
        raise HTTPException(
            status_code=410,
            detail=f"YAML 파일 누락 (DB는 존재하나 파일 없음): {row.yaml_path}",
        )

    content = yaml_file.read_text(encoding="utf-8")
    return PlainTextResponse(
        content=content,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": f'attachment; filename="{policy_id}.yaml"'
        },
    )
