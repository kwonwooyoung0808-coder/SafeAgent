"""
Phase 0-B: Ollama 기반 합성 한국 기업 내규 .docx 생성기

이미 배포된 Ollama 인프라를 활용해 현실적인 합성 내규 문서를 대량 생성한다.
생성된 .docx는 policy compiler 테스트 데이터로 사용된다.

사용법:
    python scripts/generate_synthetic_policies.py
    python scripts/generate_synthetic_policies.py --count 5 --output-dir tests/fixtures/docx
    python scripts/generate_synthetic_policies.py --ollama-url http://localhost:11434 --model qwen2.5:7b
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError:
    print("ERROR: httpx 패키지가 필요합니다. pip install httpx")
    sys.exit(1)

try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    print("ERROR: python-docx 패키지가 필요합니다. pip install python-docx")
    sys.exit(1)


# ── 합성 내규 시나리오 정의 ──────────────────────────────────────────────
SCENARIOS: list[dict] = [
    {
        "id": "TRADE_SECRET_POL",
        "name": "영업비밀 보호 정책",
        "forbidden_targets": ["영업비밀", "내부 기술자료", "고객 명단", "핵심 인력 정보"],
        "action": "즉시 차단하고 법무팀에 보고한다",
        "severity": "HIGH",
        "dept": "법무팀",
    },
    {
        "id": "PERSONAL_INFO_POL",
        "name": "개인정보 처리 방침",
        "forbidden_targets": ["주민등록번호", "계좌번호", "신용카드 번호", "의료 기록"],
        "action": "처리를 중단하고 개인정보보호 담당자에게 즉시 보고한다",
        "severity": "HIGH",
        "dept": "개인정보보호팀",
    },
    {
        "id": "WORKPLACE_ETHICS_POL",
        "name": "직장 내 윤리 준수 규정",
        "forbidden_targets": ["성희롱", "직장 내 괴롭힘", "부당 대우", "차별 발언"],
        "action": "즉시 차단하고 인사팀 및 감사팀에 통보한다",
        "severity": "HIGH",
        "dept": "인사팀",
    },
    {
        "id": "INFO_SECURITY_POL",
        "name": "정보보안 규정",
        "forbidden_targets": ["해킹 시도", "악성코드", "무단 접근", "시스템 침해"],
        "action": "차단하고 즉시 CERT에 신고한다",
        "severity": "HIGH",
        "dept": "정보보안팀",
    },
    {
        "id": "FINANCIAL_COMPLIANCE_POL",
        "name": "재무 컴플라이언스 규정",
        "forbidden_targets": ["횡령", "배임", "분식회계", "내부자 거래"],
        "action": "즉시 차단하고 감사위원회에 보고한다",
        "severity": "HIGH",
        "dept": "감사팀",
    },
    {
        "id": "COMPETITIVE_INTEL_POL",
        "name": "경쟁사 정보 취급 규정",
        "forbidden_targets": ["경쟁사 기밀", "불법 취득 정보", "산업스파이", "기술 유출"],
        "action": "기록하고 준법감시팀에 보고한다",
        "severity": "MEDIUM",
        "dept": "준법감시팀",
    },
    {
        "id": "CUSTOMER_DATA_POL",
        "name": "고객 데이터 보호 규정",
        "forbidden_targets": ["고객 연락처 무단 공개", "고객 구매 내역 유출", "고객 PII 노출"],
        "action": "즉시 차단하고 고객보호팀에 통보한다",
        "severity": "HIGH",
        "dept": "고객보호팀",
    },
    {
        "id": "AI_USAGE_POL",
        "name": "AI 시스템 사용 규정",
        "forbidden_targets": ["허위 정보 생성", "딥페이크", "저작권 침해 콘텐츠", "편향된 판단 유도"],
        "action": "생성을 차단하고 AI거버넌스팀에 보고한다",
        "severity": "MEDIUM",
        "dept": "AI거버넌스팀",
    },
]


_GENERATION_PROMPT = """당신은 한국 대기업의 내부 법무 담당자입니다.
다음 주제로 실제 기업에서 사용하는 형태의 내규(내부 규정) 문서를 작성하세요.

[정책명] {name}
[소관부서] {dept}
[금지 대상] {forbidden_targets}
[위반 처리] {action}
[심각도] {severity}

요구사항:
1. 반드시 아래 조문 구조를 따르세요:
   제1조(목적), 제2조(적용범위), 제3조(용어의 정의), 제4조(금지사항), 제5조(준수사항), 제6조(위반 시 처리)
2. 제4조(금지사항)에서 금지 대상 표현을 반드시 「」 또는 큰따옴표로 명시하세요
   예: 임직원은 「영업비밀」, 「내부 기술자료」를 외부에 유출하여서는 안 된다.
3. 각 조문은 최소 2개 이상의 항(①②③)으로 구성하세요
4. 위반 처리 조문에서 심각도를 명시하세요 (예: 심각도: HIGH)
5. 실제 기업 내규처럼 법적 문체(~하여야 한다, ~하여서는 안 된다)를 사용하세요
6. 부칙도 포함하세요

위 조건을 모두 만족하는 내규 문서만 출력하세요. 설명이나 마크다운 없이 조문 텍스트만 출력하세요."""


async def call_ollama(
    prompt: str,
    ollama_url: str,
    model: str,
    timeout: float = 120.0,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7},
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{ollama_url}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")


def _parse_articles(text: str) -> list[dict]:
    """조문 텍스트에서 제N조 단위로 파싱."""
    article_re = re.compile(
        r"^제\s*(\d+)\s*조\s*[\(（]([^)）]*)[\)）]?\s*(.*?)(?=^제\s*\d+\s*조|부칙|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    articles = []
    for m in article_re.finditer(text):
        articles.append({
            "no":    int(m.group(1)),
            "title": m.group(2).strip(),
            "body":  m.group(3).strip(),
        })
    return articles


def _extract_forbidden_from_text(text: str) -> list[str]:
    """「」 또는 "..." 패턴에서 금지어 후보 추출."""
    words = re.findall(r"「([^」]+)」", text)
    words += re.findall(r'"([^"]{2,20})"', text)
    return list(dict.fromkeys(w.strip() for w in words if 2 <= len(w.strip()) <= 20))


def text_to_docx(
    scenario: dict,
    generated_text: str,
    output_path: Path,
) -> tuple[int, int]:
    """생성된 조문 텍스트를 .docx로 변환. (금지어수, 준수항목수) 반환."""
    doc = Document()

    title_para = doc.add_heading(f"{scenario['name']} 내부 규정", level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    meta_para = doc.add_paragraph()
    meta_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    meta_para.add_run(
        f"소관부서: {scenario['dept']}  |  정책 ID: {scenario['id']}"
    ).italic = True
    doc.add_paragraph()

    articles = _parse_articles(generated_text)
    forbidden_words: list[str] = []
    compliance_count = 0

    if articles:
        for article in articles:
            doc.add_heading(f"제{article['no']}조({article['title']})", level=2)
            for line in article["body"].splitlines():
                line = line.strip()
                if line:
                    doc.add_paragraph(line)
            if "금지" in article["title"] or "금지사항" in article["title"]:
                forbidden_words = _extract_forbidden_from_text(article["body"])
            if "준수" in article["title"]:
                compliance_count += article["body"].count("①") + article["body"].count("1.")
    else:
        # 파싱 실패 시 원문 그대로 삽입
        for line in generated_text.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.match(r"^제\s*\d+\s*조", line):
                doc.add_heading(line, level=2)
            else:
                doc.add_paragraph(line)
        forbidden_words = _extract_forbidden_from_text(generated_text)

    # 부칙 (원문에 없을 경우 추가)
    if "부칙" not in generated_text:
        doc.add_heading("부칙", level=2)
        doc.add_paragraph("이 규정은 대표이사가 승인한 날로부터 시행한다.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    return len(forbidden_words), compliance_count


async def generate_one(
    scenario: dict,
    output_dir: Path,
    ollama_url: str,
    model: str,
) -> bool:
    prompt = _GENERATION_PROMPT.format(
        name=scenario["name"],
        dept=scenario["dept"],
        forbidden_targets="、".join(f"「{t}」" for t in scenario["forbidden_targets"]),
        action=scenario["action"],
        severity=scenario["severity"],
    )
    try:
        text = await call_ollama(prompt, ollama_url, model)
        if not text.strip():
            print(f"  SKIP {scenario['id']}: LLM 응답 비어 있음")
            return False

        out_path = output_dir / f"{scenario['id']}_synthetic.docx"
        fw_count, cc_count = text_to_docx(scenario, text, out_path)
        print(f"  생성됨: {out_path.name}  (금지어 {fw_count}개, 준수항목 {cc_count}개)")
        return True
    except Exception as e:
        print(f"  ERROR {scenario['id']}: {e}")
        return False


async def main_async(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = SCENARIOS[: args.count]
    print(f"\n[generate_synthetic_policies] {len(scenarios)}개 시나리오 → .docx 생성 시작")
    print(f"  Ollama: {args.ollama_url}  모델: {args.model}\n")

    tasks = [
        generate_one(sc, output_dir, args.ollama_url, args.model)
        for sc in scenarios
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success = sum(1 for r in results if r is True)
    print(f"\n완료: {success}/{len(scenarios)}개 생성 → {output_dir}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ollama 합성 내규 .docx 생성기")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--model",      default="qwen2.5:7b")
    parser.add_argument("--count",      type=int, default=len(SCENARIOS))
    parser.add_argument("--output-dir", default="tests/fixtures/docx")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
