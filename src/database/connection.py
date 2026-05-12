import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=not settings.database_url.startswith("sqlite"),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> bool:
    from src.database import models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        seed_existing_policies()
        seed_bootstrap_admin()
        return True
    except SQLAlchemyError as exc:
        logger.warning("Database initialization skipped because the database is unavailable: %s", exc)
        return False


def seed_bootstrap_admin() -> None:
    """Phase 4: 최초 부팅 시 admin 계정이 없으면 자동 생성 (멱등).

    설계:
      - 비밀번호는 BOOTSTRAP_ADMIN_PASSWORD 환경변수 (기본 'changeme').
      - bcrypt 해시는 코드에서 생성 — SQL 마이그레이션에 정적 해시 박지 않음.
      - 운영 환경 (APP_ENV=production) 에서 약한 비밀번호는 _validate_auth_settings
        에서 이미 기동 시점에 차단됨. 여기까지 도달하면 안전한 비밀번호.
      - IntegrityError (다른 워커가 동시에 생성) 는 정상 멱등 케이스 — 무시.
      - 그 외 SQL/일반 오류는 ERROR 로그 후 throw 안 함 (앱 기동은 계속).
    """
    import uuid as _uuid
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError

    from src.core.auth import hash_password
    from src.database.models import UserModel

    session = SessionLocal()
    try:
        existing = (
            session.query(UserModel)
            .filter(UserModel.username == settings.bootstrap_admin_username)
            .first()
        )
        if existing:
            return

        session.add(
            UserModel(
                id=f"user-{_uuid.uuid4()}",
                username=settings.bootstrap_admin_username,
                hashed_password=hash_password(settings.bootstrap_admin_password),
                role="admin",
                policy_groups=[],
                is_active=True,
            )
        )
        session.commit()
        # OWASP A02:2025 권고 — 기본 자격증명 생성은 WARNING 이상으로 기록.
        logger.warning(
            "[SECURITY] Bootstrap admin '%s' created with initial credentials. "
            "MANDATORY: Change password before production use.",
            settings.bootstrap_admin_username,
        )
    except IntegrityError:
        # 동시 다중 워커 환경에서 race — 다른 워커가 먼저 시드함. 정상.
        session.rollback()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error("[SECURITY] Bootstrap admin seed failed (DB error): %s", e)
    except Exception as e:
        session.rollback()
        logger.error("[SECURITY] Bootstrap admin seed failed (unexpected): %s", e)
    finally:
        session.close()


def seed_existing_policies() -> None:
    """
    src/policies/ 의 기존 YAML 파일을 policies 테이블에 자동 등록.
    이미 존재하는 id는 건너뜀 (멱등성 보장).
    Feature 1/2가 기존 정책을 즉시 사용할 수 있도록 is_active=TRUE로 등록.

    Phase 3-A: 새로 등록되는 정책에 대해 PolicyVersionModel 의 첫 버전 (v1.0 또는
    YAML 의 version 필드 그대로) 도 함께 INSERT — is_current=TRUE.
    """
    from datetime import datetime, timezone
    import uuid as _uuid

    from src.database.models import PolicyModel, PolicyVersionModel
    from src.utils.yaml_loader import PolicyLoaderError, load_policy

    try:
        policy_dir = Path(settings.policy_dir)
        if not policy_dir.exists():
            return

        session = SessionLocal()
        try:
            for yaml_path in sorted(policy_dir.glob("*.yaml")):
                try:
                    policy = load_policy(yaml_path)
                except PolicyLoaderError:
                    continue

                exists = session.query(PolicyModel).filter(
                    PolicyModel.id == policy.id
                ).first()
                if exists:
                    continue

                # YAML 의 enabled 플래그를 DB 의 is_active 와 매핑
                # (enabled: false 정책은 등록되지만 비활성 상태로 — 추후 PUT /activate 로 켤 수 있음)
                version_str = policy.version or "1.0"
                session.add(PolicyModel(
                    id=policy.id,
                    name=policy.name,
                    version=version_str,
                    yaml_path=str(yaml_path),
                    is_active=bool(getattr(policy, "enabled", True)),
                ))

                # 첫 버전 row 도 함께 등록 (이 시점 YAML 스냅샷 보존)
                try:
                    snapshot = Path(yaml_path).read_text(encoding="utf-8")
                except OSError:
                    snapshot = None
                now = datetime.now(timezone.utc)
                session.add(PolicyVersionModel(
                    id=str(_uuid.uuid4()),
                    policy_id=policy.id,
                    version=version_str,
                    yaml_path=str(yaml_path),
                    yaml_snapshot=snapshot,
                    is_current=True,
                    activated_at=now,
                ))
            session.commit()
        except Exception as e:
            session.rollback()
            logger.warning("Policy seeding failed: %s", e)
        finally:
            session.close()
    except Exception as e:
        logger.warning("seed_existing_policies skipped: %s", e)
