"""
모델 버전 교체 시 Semantic Drift 탐지 — 회귀 테스트 프레임워크.

사용법:
    pytest tests/benchmarks/evaluator.py -v
    또는
    python tests/benchmarks/evaluator.py

합격 기준 (prompt_model_lock.yaml 기준):
    forbidden_words precision ≥ 0.85
    forbidden_words recall    ≥ 0.80
    severity accuracy         ≥ 0.90
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

MIN_PRECISION    = 0.85
MIN_RECALL       = 0.80
MIN_SEVERITY_ACC = 0.90

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"


class PromptRegressionEvaluator:
    """
    golden_set.json의 테스트 케이스를 실제 LLM으로 실행하고
    정확도를 측정합니다.
    """

    def __init__(self) -> None:
        from src.services.ollama_client import OllamaClient
        self.client = OllamaClient()

    def load_golden_set(self) -> list[dict]:
        data = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
        # _comment, _schema 항목 제외
        return [c for c in data if "id" in c and not c.get("_comment")]

    async def run(self) -> dict:
        from src.engines.doc_parser_engine import run_two_step_llm_parse

        golden = self.load_golden_set()
        if not golden:
            return {
                "error": "golden_set.json에 테스트 케이스가 없습니다. 사용자가 작성해야 합니다.",
                "pass":  False,
            }

        fw_tp = fw_fp = fw_fn = 0
        sev_correct = sev_total = 0

        for case in golden:
            predicted, _ = await run_two_step_llm_parse(
                case["input_text"], client=self.client
            )
            exp = case.get("expected", {})

            # ── forbidden_words 평가 ─────────────────────────
            pred_fw = {w.lower() for w in predicted.get("forbidden_words", [])}
            exp_fw = {w.lower() for w in exp.get("forbidden_words", [])}
            must_not = {
                w.lower()
                for w in case.get("hallucinated_words_must_not_include", [])
            }

            fw_tp += len(pred_fw & exp_fw)
            fw_fp += len(pred_fw - exp_fw) + len(pred_fw & must_not)
            fw_fn += len(exp_fw - pred_fw)

            # ── severity 정확도 평가 ─────────────────────────
            pred_checks = {
                c.get("description", ""): c.get("severity", "")
                for c in predicted.get("compliance_checks", [])
            }
            for exp_check in exp.get("compliance_checks", []):
                sev_total += 1
                pred_sev = pred_checks.get(exp_check.get("description", ""))
                if pred_sev == exp_check.get("severity"):
                    sev_correct += 1

        precision = fw_tp / (fw_tp + fw_fp + 1e-9)
        recall = fw_tp / (fw_tp + fw_fn + 1e-9)
        severity_acc = sev_correct / (sev_total + 1e-9)
        passed = (
            precision    >= MIN_PRECISION
            and recall       >= MIN_RECALL
            and severity_acc >= MIN_SEVERITY_ACC
        )

        return {
            "model":                      self.client.model,
            "total_cases":                len(golden),
            "forbidden_words_precision":  round(precision, 3),
            "forbidden_words_recall":     round(recall, 3),
            "severity_accuracy":          round(severity_acc, 3),
            "pass":                       passed,
            "thresholds": {
                "min_precision":    MIN_PRECISION,
                "min_recall":       MIN_RECALL,
                "min_severity_acc": MIN_SEVERITY_ACC,
            },
        }


# ── pytest 연동 ────────────────────────────────────────────────
try:
    import pytest

    @pytest.mark.asyncio
    async def test_prompt_regression() -> None:
        evaluator = PromptRegressionEvaluator()
        result = await evaluator.run()

        if "error" in result:
            pytest.skip(result["error"])

        assert result["pass"], (
            f"회귀 테스트 실패 (모델: {result['model']}):\n"
            f"  precision={result['forbidden_words_precision']} "
            f"(min={MIN_PRECISION})\n"
            f"  recall   ={result['forbidden_words_recall']} "
            f"(min={MIN_RECALL})\n"
            f"  severity ={result['severity_accuracy']} "
            f"(min={MIN_SEVERITY_ACC})"
        )

except ImportError:
    pass


# ── CLI 직접 실행 ──────────────────────────────────────────────
def main() -> None:
    evaluator = PromptRegressionEvaluator()
    result = asyncio.run(evaluator.run())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("pass"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
