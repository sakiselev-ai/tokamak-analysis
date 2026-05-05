from __future__ import annotations
"""Generate deposited source code for Rospatent registration.

Rospatent requires: first 25 pages + last 25 pages of source code,
or full source if <= 50 pages. Each page = 70 lines.

Usage:
    python deposited_code.py --output deposited_materials.txt
"""
import os
import argparse

LINES_PER_PAGE = 70
TOTAL_PAGES = 50

HEADER = """
================================================================================
ДЕПОНИРУЕМЫЕ МАТЕРИАЛЫ
Программа для ЭВМ: Tokamak Analysis
Правообладатель: НИЯУ МИФИ
Год создания: 2026
================================================================================

"""

# Key source files to include (ordered by importance)
KEY_FILES = [
    "backend/app/main.py",
    "backend/app/config.py",
    "backend/app/database.py",
    "backend/app/core/security.py",
    "backend/app/models/user.py",
    "backend/app/models/experiment.py",
    "backend/app/models/ml_model.py",
    "backend/app/api/auth.py",
    "backend/app/api/experiments.py",
    "backend/app/api/predictions.py",
    "backend/app/services/fair_mast.py",
    "backend/app/services/recommendations.py",
    "backend/app/services/preprocessing.py",
    "ml_service/service/server.py",
    "ml_service/service/models/interface.py",
    "ml_service/service/models/random_forest.py",
    "ml_service/service/models/lstm_attention.py",
    "ml_service/service/models/transformer.py",
    "ml_service/service/data/preprocessing.py",
    "ml_service/service/data/dataset.py",
    "frontend/src/App.tsx",
    "frontend/src/pages/LoginPage.tsx",
    "frontend/src/pages/DashboardPage.tsx",
    "frontend/src/pages/ExperimentPage.tsx",
    "frontend/src/components/TimeSeriesChart.tsx",
    "docker-compose.yml",
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="rospatent/deposited_materials.txt")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    all_lines = [HEADER]

    for filepath in KEY_FILES:
        full_path = os.path.join(args.project_root, filepath)
        if not os.path.exists(full_path):
            continue

        all_lines.append(f"\n{'='*80}\n")
        all_lines.append(f"ФАЙЛ: {filepath}\n")
        all_lines.append(f"{'='*80}\n\n")

        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        all_lines.append(content)
        all_lines.append("\n")

    full_text = "".join(all_lines)
    lines = full_text.split("\n")
    total_lines = len(lines)
    total_pages = total_lines // LINES_PER_PAGE + 1

    if total_pages <= TOTAL_PAGES:
        output_lines = lines
    else:
        first_n = 25 * LINES_PER_PAGE
        last_n = 25 * LINES_PER_PAGE
        output_lines = lines[:first_n]
        output_lines.append(f"\n\n... [пропущено {total_lines - first_n - last_n} строк] ...\n\n")
        output_lines.extend(lines[-last_n:])

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write("\n".join(output_lines))

    print(f"Deposited materials: {len(output_lines)} lines, ~{len(output_lines)//LINES_PER_PAGE + 1} pages")
    print(f"Saved to {args.output}")

if __name__ == "__main__":
    main()
