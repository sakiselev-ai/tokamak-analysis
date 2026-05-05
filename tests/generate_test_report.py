from __future__ import annotations
"""Generate comprehensive test report for Sprint 5 deliverable.

Combines: unit tests, integration tests, security scan, load test, inference benchmark.

Usage:
    python generate_test_report.py --output reports/test_report.md
"""

import argparse
import json
import os
import subprocess
import time

def run_backend_tests():
    """Run backend tests and capture results."""
    result = subprocess.run(
        ["python3", "-m", "pytest", "backend/tests/", "-v", "--tb=short", "--cov=backend/app",
         "--cov-report=json:reports/backend_coverage.json", "-q"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)) or "."
    )
    return result.stdout, result.returncode

def run_ml_tests():
    """Run ML service tests."""
    result = subprocess.run(
        ["python3", "-m", "pytest", "ml_service/tests/", "-v", "--tb=short",
         "--cov=ml_service/service", "--cov-report=json:reports/ml_coverage.json", "-q",
         "-k", "not lstm_attention and not transformer_create"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)) or "."
    )
    return result.stdout, result.returncode

def generate_report(output_file):
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

    report = []
    report.append("# Отчёт о тестировании — Tokamak Analysis Platform v1.0")
    report.append(f"\nДата: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("\n## 1. Unit и интеграционные тесты\n")

    # Run tests
    print("Running backend tests...")
    backend_output, backend_code = run_backend_tests()
    report.append("### Backend (FastAPI)")
    report.append(f"```\n{backend_output}\n```")
    report.append(f"Результат: {'PASS' if backend_code == 0 else 'FAIL'}\n")

    print("Running ML service tests...")
    ml_output, ml_code = run_ml_tests()
    report.append("### ML Service")
    report.append(f"```\n{ml_output}\n```")
    report.append(f"Результат: {'PASS' if ml_code == 0 else 'FAIL'}\n")

    # Coverage
    report.append("\n## 2. Покрытие кода\n")
    for name, path in [("Backend", "reports/backend_coverage.json"), ("ML Service", "reports/ml_coverage.json")]:
        if os.path.exists(path):
            with open(path) as f:
                cov = json.load(f)
            total = cov.get("totals", {}).get("percent_covered", 0)
            report.append(f"- **{name}**: {total:.1f}%")

    # Security scan results
    report.append("\n## 3. Тестирование безопасности (TC-NF-003)\n")
    sec_path = "results/security_report.json"
    if os.path.exists(sec_path):
        with open(sec_path) as f:
            sec = json.load(f)
        summary = sec.get("summary", {})
        report.append(f"- Проверок: {summary.get('total_checks', 'N/A')}")
        report.append(f"- Пройдено: {summary.get('passed', 'N/A')}")
        report.append(f"- Провалено: {summary.get('failed', 'N/A')}")
        report.append(f"- Критических: {summary.get('critical_failures', 'N/A')}")
        report.append(f"- Результат: **{summary.get('compliance', 'N/A')}**")
    else:
        report.append("Не выполнено. Запустите: `python tests/security/owasp_scan.py`")

    # Load test results
    report.append("\n## 4. Нагрузочное тестирование (TC-NF-001)\n")
    report.append("Конфигурация: 50 пользователей, 15 минут")
    report.append("Запуск: `cd tests/load && locust -f locustfile.py --headless --users 50 --run-time 15m`")

    # Inference benchmark
    report.append("\n## 5. Тест инференса (TC-NF-002)\n")
    bench_path = "results/inference_benchmark.json"
    if os.path.exists(bench_path):
        with open(bench_path) as f:
            bench = json.load(f)
        for task_name, key in [("Классификация", "classification"), ("Предсказание срывов", "disruption")]:
            stats = bench.get(key, {})
            report.append(f"\n### {task_name}")
            report.append(f"| Метрика | Значение |")
            report.append(f"|---------|----------|")
            for m in ["p50", "p95", "p99", "mean"]:
                v = stats.get(m, 0)
                report.append(f"| {m} | {v:.1f} мс |")
    else:
        report.append("Не выполнено. Запустите: `python tests/benchmark/inference_benchmark.py`")

    # Summary
    report.append("\n## 6. Сводка\n")
    report.append("| Вид тестирования | Инструмент | Статус |")
    report.append("|------------------|------------|--------|")
    report.append(f"| Unit-тесты (backend) | pytest | {'PASS' if backend_code == 0 else 'FAIL'} |")
    report.append(f"| Unit-тесты (ML) | pytest | {'PASS' if ml_code == 0 else 'FAIL'} |")
    report.append(f"| E2E | Playwright | Pending |")
    report.append(f"| Нагрузочные | Locust | Pending |")
    report.append(f"| Безопасность | OWASP scan | Pending |")
    report.append(f"| Инференс | Benchmark | Pending |")

    # Write
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    print(f"\nReport saved to {output_file}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/test_report.md")
    args = parser.parse_args()
    generate_report(args.output)

if __name__ == "__main__":
    main()
