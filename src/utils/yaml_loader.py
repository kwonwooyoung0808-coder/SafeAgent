import logging
from pathlib import Path
from typing import List, Union

import yaml
from pydantic import ValidationError

from src.schemas.policy import Policy

# 로깅 설정 (실무 환경에서 에러 추적을 위해 필수)
logger = logging.getLogger(__name__)

class PolicyLoaderError(Exception):
    """정책 로딩 과정에서 발생하는 표준 예외 클래스 (PRD 8.2 반영)"""
    pass

def load_policy(path: Union[str, Path]) -> Policy:
    """
    단일 YAML 파일을 읽어 Policy 스키마 객체로 변환합니다.
    Pydantic 모델의 model_validate를 통해 필드 누락 및 타입 유효성을 검증합니다.
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise PolicyLoaderError(f"Policy file not found: {path_obj}")

    try:
        with path_obj.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        if data is None:
            raise PolicyLoaderError(f"Policy file is empty: {path_obj.name}")

        # PRD 8.2: Pydantic 스키마 검증 수행
        return Policy.model_validate(data)

    except yaml.YAMLError as exc:
        raise PolicyLoaderError(f"Invalid YAML syntax in '{path_obj.name}': {exc}")
    except ValidationError as exc:
        # 스키마 검증 실패 시 구체적인 필드 에러 정보를 포함 (A-2 해소)
        error_detail = exc.errors()
        raise PolicyLoaderError(f"Schema validation failed for '{path_obj.name}': {error_detail}")
    except Exception as exc:
        raise PolicyLoaderError(f"Unexpected error loading '{path_obj.name}': {exc}")

def load_policies(policy_dir: Union[str, Path]) -> List[Policy]:
    """
    지정된 디렉토리 내의 모든 *.yaml 파일을 로드하고 enabled=True인 정책만 반환합니다.
    """
    policies: List[Policy] = []
    base_path = Path(policy_dir)

    if not base_path.exists() or not base_path.is_dir():
        logger.warning(f"Policy directory does not exist: {policy_dir}")
        return policies

    # 알파벳 순 정렬 로딩 (우선순위 제어 일관성 확보)
    for path in sorted(base_path.glob("*.yaml")):
        try:
            policy = load_policy(path)
            if policy.enabled:
                policies.append(policy)
        except PolicyLoaderError as e:
            # 특정 정책 로딩 실패가 전체 시스템 비정상 종료로 이어지지 않도록 처리 (PRD 8.2)
            logger.error(e)
            continue

    return policies
