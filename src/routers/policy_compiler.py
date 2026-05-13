from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import yaml

from src.core.config import get_settings
from src.core.dependencies import get_db
from src.database.connection import SessionLocal
from src.database.models import (
    AgentModel,
    PolicyConversionLogModel,
    PolicyGroupMemberModel,
    PolicyModel,
    PolicyVersionModel,
    QueryAuditLogModel,
    ResponseAuditLogModel,
)
from src.schemas.doc_parser import PolicyConvertResponse
from src.schemas.policy import Policy
from src.utils.policy_cache import get_policy_cache
from src.workflows.doc_parser_workflow import build_doc_parser_graph

router = APIRouter(prefix="/v1/policy-compiler", tags=["policy-compiler"])
logger = logging.getLogger(__name__)
_POLICY_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,79}$")


class PolicyDraftResponse(BaseModel):
    policy_id: str
    version: str
    yaml_path: str
    raw_yaml: str
    needs_review: bool
    is_active: bool


class PolicyDraftUpdate(BaseModel):
    raw_yaml: str = Field(min_length=1)


def _validate_requested_policy_id(policy_id: str) -> str:
    value = policy_id.strip()
    if not _POLICY_ID_RE.fullmatch(value):
        raise HTTPException(
            status_code=422,
            detail=(
                "policy_id must be 3-80 characters using only uppercase letters, "
                "numbers, underscores, or hyphens."
            ),
        )
    return value


def _today_in_app_timezone() -> date:
    settings = get_settings()
    try:
        return date.today() if not settings.app_timezone else datetime.now(
            ZoneInfo(settings.app_timezone)
        ).date()
    except ZoneInfoNotFoundError:
        if settings.app_timezone == "Asia/Seoul":
            return datetime.now(timezone(timedelta(hours=9))).date()
        logger.warning("Unknown APP_TIMEZONE=%s; falling back to local date", settings.app_timezone)
        return date.today()


def _safe_write_policy_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".tmp",
        prefix=f".{path.stem}.",
        dir=path.parent,
        delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def _load_policy_yaml(row: PolicyModel) -> tuple[Path, str, dict]:
    yaml_path = Path(row.yaml_path)
    if not yaml_path.exists():
        raise HTTPException(
            status_code=410,
            detail=f"YAML 파일 누락 (DB는 존재하나 파일 없음): {row.yaml_path}",
        )
    raw_yaml = yaml_path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"YAML 파싱 실패: {e}") from e
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="YAML root must be an object")
    return yaml_path, raw_yaml, parsed


def _yaml_needs_review(raw_yaml: str, parsed: dict | None = None) -> bool:
    lowered = raw_yaml.lower()
    if "needs_review: true" in lowered or "검토 필요: true" in raw_yaml:
        return True

    def walk(value) -> bool:
        if isinstance(value, dict):
            if value.get("needs_review") is True:
                return True
            return any(walk(v) for v in value.values())
        if isinstance(value, list):
            return any(walk(item) for item in value)
        if isinstance(value, str):
            v = value.lower()
            return "needs_review: true" in v or "검토 필요: true" in value
        return False

    return walk(parsed or {})


def _next_policy_version(db: Session, policy_id: str, current_version: str | None) -> str:
    existing = {
        row[0]
        for row in db.query(PolicyVersionModel.version)
        .filter(PolicyVersionModel.policy_id == policy_id)
        .all()
    }
    base = current_version or "1.0"
    parts = base.split(".")
    if len(parts) >= 2 and all(part.isdigit() for part in parts):
        major = int(parts[0])
        minor = int(parts[1])
        for bump in range(minor + 1, minor + 1000):
            candidate = f"{major}.{bump}"
            if candidate not in existing:
                return candidate
    suffix = 1
    while f"{base}.{suffix}" in existing:
        suffix += 1
    return f"{base}.{suffix}"


def _validate_policy_yaml_for_update(policy_id: str, raw_yaml: str, version: str) -> str:
    try:
        parsed = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"YAML 파싱 실패: {e}") from e
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="YAML root must be an object")
    parsed["id"] = policy_id
    parsed["version"] = version
    parsed["enabled"] = False
    try:
        Policy(**parsed)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Policy schema validation failed: {e}") from e
    return yaml.safe_dump(parsed, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _policy_delete_blockers(db: Session, policy_id: str) -> dict[str, int]:
    checks = {
        "agents": db.query(AgentModel).filter(AgentModel.policy_id == policy_id).count(),
        "policy_groups": db.query(PolicyGroupMemberModel)
        .filter(PolicyGroupMemberModel.policy_id == policy_id)
        .count(),
        "query_audits": db.query(QueryAuditLogModel)
        .filter(QueryAuditLogModel.policy_id == policy_id)
        .count(),
        "response_audits": db.query(ResponseAuditLogModel)
        .filter(ResponseAuditLogModel.policy_id == policy_id)
        .count(),
    }
    return {name: count for name, count in checks.items() if count}


def _safe_delete_policy_yaml(yaml_path: Path, policy_id: str) -> None:
    settings = get_settings()
    policy_dir = Path(settings.policy_dir).resolve()
    try:
        resolved_path = yaml_path.resolve()
    except OSError:
        return
    if resolved_path.parent != policy_dir or resolved_path.name != f"{policy_id}.yaml":
        raise HTTPException(
            status_code=409,
            detail=f"YAML 삭제 거부: policy_dir 내부의 {policy_id}.yaml 파일이 아닙니다.",
        )
    try:
        resolved_path.unlink(missing_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"YAML 파일 삭제 실패: {e}") from e


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
    requested_policy_id: str | None = None,
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
            requested_policy_id=requested_policy_id,
            fail_marker=fail_marker, # 추적용 ID 는 별도 컬럼에 저장
            original_filename=original_filename or "unknown.docx",
            parsed_rules_count=0,
            conversion_status="FAILED",
            warnings=list(warnings) + [
                f"요청 policy_id: {requested_policy_id or '(없음)'}",
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
    policy_id: str = Form(
        ...,
        description="Required readable policy ID. Use uppercase letters, numbers, '_' or '-'. Example: COMPANY_TRADE_SECRET_V1",
    ),
    policy_name: str = Form(..., description="Human-readable policy name."),
    db: Session = Depends(get_db),
) -> PolicyConvertResponse:
    """
    .docx 파일을 YAML 정책으로 변환.
    변환된 정책은 is_active=FALSE → PUT /activate 호출 전까지 Feature 1/2 미적용.

    PRD 5.3.6 보장:
    - 정상 변환: status=SUCCESS / PARTIAL
    - 변환 실패: 원본 .docx 가 {policy_dir}/failed_uploads/ 에 보존되고
                 PolicyConversionLogModel 에도 실패 기록이 남음.
    """
    requested_policy_id = _validate_requested_policy_id(policy_id)
    if db.query(PolicyModel).filter(PolicyModel.id == requested_policy_id).first():
        raise HTTPException(
            status_code=409,
            detail=f"policy_id={requested_policy_id} already exists",
        )
    requested_yaml_path = Path(get_settings().policy_dir) / f"{requested_policy_id}.yaml"
    if requested_yaml_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"policy yaml already exists for policy_id={requested_policy_id}",
        )

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
                    "policy_id":      requested_policy_id,
                    "policy_name":    policy_name,
                    "effective_date": _today_in_app_timezone().isoformat(),
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
                requested_policy_id=requested_policy_id,
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
                requested_policy_id=requested_policy_id,
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


@router.get("/{policy_id}", summary="정책 메타데이터 조회")
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


@router.get("/{policy_id}/draft", response_model=PolicyDraftResponse, summary="Draft YAML 조회 (검토용)")
def get_policy_draft(policy_id: str, db: Session = Depends(get_db)) -> PolicyDraftResponse:
    row = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")
    yaml_path, raw_yaml, parsed = _load_policy_yaml(row)
    return PolicyDraftResponse(
        policy_id=row.id,
        version=row.version,
        yaml_path=str(yaml_path),
        raw_yaml=raw_yaml,
        needs_review=_yaml_needs_review(raw_yaml, parsed),
        is_active=row.is_active,
    )


@router.put(
    "/{policy_id}/draft",
    response_model=PolicyDraftResponse,
    summary="Draft YAML 수정 (비활성 정책만 가능, 새 버전 자동 생성)",
)
def update_policy_draft(
    policy_id: str,
    payload: PolicyDraftUpdate,
    db: Session = Depends(get_db),
) -> PolicyDraftResponse:
    row = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")
    if row.is_active:
        raise HTTPException(status_code=409, detail="활성 정책은 draft API로 직접 수정할 수 없습니다.")

    yaml_path, _, _ = _load_policy_yaml(row)
    next_version = _next_policy_version(db, policy_id, row.version)
    duplicate = db.query(PolicyVersionModel).filter(
        PolicyVersionModel.policy_id == policy_id,
        PolicyVersionModel.version == next_version,
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"버전 중복: policy_id={policy_id}, version={next_version}",
        )

    normalized_yaml = _validate_policy_yaml_for_update(policy_id, payload.raw_yaml, next_version)
    parsed = yaml.safe_load(normalized_yaml) or {}
    try:
        _safe_write_policy_yaml(yaml_path, normalized_yaml)
        row.version = next_version
        row.is_active = False
        db.add(PolicyVersionModel(
            id=str(uuid.uuid4()),
            policy_id=policy_id,
            version=next_version,
            yaml_path=str(yaml_path),
            yaml_snapshot=normalized_yaml,
            is_current=False,
            activated_at=None,
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"draft 저장 실패: {e}") from e

    get_policy_cache().invalidate(policy_id)
    return PolicyDraftResponse(
        policy_id=row.id,
        version=row.version,
        yaml_path=str(yaml_path),
        raw_yaml=normalized_yaml,
        needs_review=_yaml_needs_review(normalized_yaml, parsed),
        is_active=row.is_active,
    )


@router.get(
    "/{policy_id}/yaml",
    response_class=PlainTextResponse,
    summary="정책 YAML 원문 다운로드",
)
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


@router.put(
    "/{policy_id}/activate",
    summary="[상태 변경] 정책 활성화 — 활성화 즉시 Feature 1/2 게이트에 적용",
)
def activate_policy(policy_id: str, db: Session = Depends(get_db)) -> dict:
    """
    정책을 활성화 (is_active=TRUE).
    활성화 후 Feature 1/2의 policy_loader_node에서 즉시 사용 가능.
    needs_review 표시가 남아 있으면 활성화 거부 (422).
    """
    row = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")
    _, raw_yaml, parsed = _load_policy_yaml(row)
    if _yaml_needs_review(raw_yaml, parsed):
        raise HTTPException(
            status_code=422,
            detail="needs_review 표시가 남아 있어 활성화할 수 없습니다. draft를 검토/수정한 뒤 다시 시도하세요.",
        )

    now = datetime.now(timezone.utc)
    current_rows = db.query(PolicyVersionModel).filter(
        PolicyVersionModel.policy_id == policy_id,
        PolicyVersionModel.is_current == True,
    ).all()
    for current in current_rows:
        current.is_current = False
        current.deactivated_at = now

    target_version = row.version or str(parsed.get("version") or "1.0")
    target = db.query(PolicyVersionModel).filter(
        PolicyVersionModel.policy_id == policy_id,
        PolicyVersionModel.version == target_version,
    ).first()
    if target:
        target.is_current = True
        target.activated_at = now
        target.deactivated_at = None
    row.is_active = True
    db.commit()
    get_policy_cache().invalidate(policy_id)
    return {"policy_id": policy_id, "is_active": True, "name": row.name}


@router.put(
    "/{policy_id}/deactivate",
    summary="[상태 변경] 정책 비활성화 — 다음 요청부터 게이트 미적용",
)
def deactivate_policy(policy_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")

    now = datetime.now(timezone.utc)
    current_rows = db.query(PolicyVersionModel).filter(
        PolicyVersionModel.policy_id == policy_id,
        PolicyVersionModel.is_current == True,
    ).all()
    for current in current_rows:
        current.is_current = False
        current.deactivated_at = now
    row.is_active = False
    db.commit()
    get_policy_cache().invalidate(policy_id)
    return {"policy_id": policy_id, "is_active": False, "name": row.name}


@router.delete(
    "/{policy_id}",
    summary="[파괴적] 정책 영구 삭제 — 비활성 + 미사용 정책만 가능 (DB row + YAML 파일 동시 삭제)",
)
def delete_unused_policy(policy_id: str, db: Session = Depends(get_db)) -> dict:
    """
    정책을 영구 삭제. 호출 전 반드시 deactivate 필요.
    agents/policy_groups에 연결되어 있거나 감사 이력이 있으면 409로 거부.
    삭제 시 DB row(PolicyModel, PolicyVersionModel, PolicyConversionLogModel)와
    {policy_dir}/{policy_id}.yaml 파일이 함께 제거됨.
    """
    row = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")
    if row.is_active:
        raise HTTPException(status_code=409, detail="활성 정책은 삭제할 수 없습니다. 먼저 deactivate 하세요.")

    blockers = _policy_delete_blockers(db, policy_id)
    if blockers:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "정책이 사용 중이거나 감사 이력이 있어 삭제할 수 없습니다.",
                "blockers": blockers,
            },
        )

    yaml_path = Path(row.yaml_path)
    try:
        db.query(PolicyVersionModel).filter(
            PolicyVersionModel.policy_id == policy_id
        ).delete(synchronize_session=False)
        db.query(PolicyConversionLogModel).filter(
            PolicyConversionLogModel.policy_id == policy_id
        ).delete(synchronize_session=False)
        db.delete(row)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"정책 DB 삭제 실패: {e}") from e

    _safe_delete_policy_yaml(yaml_path, policy_id)
    get_policy_cache().invalidate(policy_id)
    return {"policy_id": policy_id, "deleted": True, "yaml_deleted": True}
