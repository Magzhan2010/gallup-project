"""
baseline_scorer.py
=================
Детерминированный алгоритм подсчёта баллов по Gallup CliftonStrengths.

ВХОД:
  - smart_mapping.json: [{q: 1..200, talent_A: 'Theme1', talent_B: 'Theme2'}, ...]
  - <person>.xlsx: ответы 1-5 на 200 пар (столбец 'Answer')
  - my_dataset.csv: ground truth - ранг каждой из 34 тем (1=топ, 34=слабейшая)

АЛГОРИТМ:
  Для каждого ответа (1..5):
    shift = ответ - 3              # 5→+2, 4→+1, 3→0, 2→-1, 1→-2
    talent_A  += shift
    talent_B  -= shift

  Затем ранжируем все 34 темы по сумме. Чем больше - тем сильнее.

МЕТРИКИ:
  - top-5 совпадение с ground truth
  - top-10 совпадение
  - Spearman rank correlation по всем 34 темам
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
from scipy.stats import spearmanr


# ============================================================================
# КОНФИГ
# ============================================================================

PROJECT_DIR = Path(__file__).resolve().parent
# Правильный сбалансированный маппинг — в первом листе Gallup_Talent_Mapping_Balanced.xlsx
# ("400 строк - баланс 11-12"): каждое из 200 пар имеет 2 утверждения, каждое со своей темой.
# Идеал Gallup: 26 тем × 12 пар + 8 тем × 11 пар = 400 утверждений.
MAPPING_XLSX = PROJECT_DIR / "Gallup_Talent_Mapping_Balanced.xlsx"
MAPPING_SHEET = "400 строк - баланс 11-12"
DATASET_CSV = PROJECT_DIR / "my_dataset.csv"
ANSWERS_DIR = Path(r"C:\Users\User\Downloads\Telegram Desktop")  # где лежат *.xlsx

# Sentinel для отсутствующего ранга в my_dataset.csv
MISSING_RANK = 2000

# 34 темы Gallup (из gallup_talents.pkl)
GALLUP_THEMES = [
    "Achiever", "Discipline", "Activator", "Maximizer", "Adaptability",
    "Includer", "Analytical", "Input", "Arranger", "Focus",
    "Command", "Self-Assurance", "Connectedness", "Individualization", "Context",
    "Intellection", "Belief", "Responsibility", "Communication", "Significance",
    "Developer", "Positivity", "Futuristic", "Learner", "Consistency",
    "Restorative", "Competition", "Woo", "Empathy", "Relator",
    "Ideation", "Strategic", "Deliberative", "Harmony",
]
assert len(GALLUP_THEMES) == 34


# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================

def load_mapping(path: Path) -> list[dict]:
    """
    Загрузить маппинг из листа "400 строк - баланс 11-12".
    Формат листа: (№утверждения, №пары, текст, тема).
    Возвращает [{q: int, talent_A: str, talent_B: str}, ...].
    """
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[MAPPING_SHEET]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    # Группируем утверждения по парам
    pair_statements: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        try:
            stmt_num = int(str(row[0]).strip())
            pair_num = int(str(row[1]).strip()) if row[1] else None
        except (ValueError, TypeError):
            continue
        if not pair_num or not (1 <= pair_num <= 200):
            continue
        text = str(row[2] or "").strip()
        theme = normalize_theme_str(row[3])
        if not text or not theme:
            continue
        pair_statements[pair_num].append((stmt_num, theme))

    data = []
    for pair_num in sorted(pair_statements.keys()):
        stmts = pair_statements[pair_num]
        if len(stmts) != 2:
            continue
        stmts = sorted(stmts, key=lambda x: x[0])  # по номеру утверждения
        data.append({
            "q": pair_num,
            "talent_A": stmts[0][1],
            "talent_B": stmts[1][1],
        })

    print(f"[OK] Маппинг загружен из '{MAPPING_SHEET}': {len(data)} пар")
    themes_in_mapping = set()
    for entry in data:
        themes_in_mapping.add(entry["talent_A"])
        themes_in_mapping.add(entry["talent_B"])
    print(f"[OK] Уникальных тем в маппинге: {len(themes_in_mapping)}")
    missing = set(GALLUP_THEMES) - themes_in_mapping
    if missing:
        print(f"[WARN] В маппинге НЕТ тем: {sorted(missing)}")
    bad = [e for e in data if e["talent_A"] == e["talent_B"]]
    if bad:
        print(f"[WARN] Пар с одной темой с обеих сторон: {len(bad)} "
              f"(вопросы: {[e['q'] for e in bad]})")
    return data


def normalize_theme_str(theme) -> str:
    """Нормализует название темы к единому виду ('Self-Assurance')."""
    if not theme:
        return ""
    n = str(theme).strip()
    if "-" in n:
        parts = n.split("-")
        n = "-".join(p.capitalize() for p in parts)
    return n


def load_answers_from_xlsx(path: Path) -> list[int | None]:
    """
    Загрузить ответы из xlsx. Возвращает список длиной 200, где значение:
      - int от 1 до 5 для ответа
      - None для пропущенного вопроса
    """
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    # Найти колонку с ответами: ищем колонку с >= 50 целочисленных значений 1..5
    answer_col = None
    for col_idx in range(len(rows[0])):
        col_vals = [r[col_idx] for r in rows[1:] if r[col_idx] is not None]
        nums = []
        for v in col_vals:
            try:
                n = int(str(v).strip())
                if 1 <= n <= 5:
                    nums.append(n)
            except (ValueError, TypeError):
                pass
        if len(nums) >= 50:
            answer_col = col_idx
            break

    if answer_col is None:
        wb.close()
        raise ValueError(f"Не нашёл колонку с ответами в {path.name}")

    # Собираем ответы по 200 строкам (индекс вопроса = номер строки - 1)
    answers: list[int | None] = [None] * 200
    for row in rows[1:]:
        # Используем первую колонку как номер вопроса (если она числовая)
        q_num = None
        if row[0] is not None:
            try:
                q_num = int(str(row[0]).strip())
            except (ValueError, TypeError):
                pass
        if q_num is None or not (1 <= q_num <= 200):
            continue
        ans = row[answer_col]
        if ans is None:
            continue
        try:
            n = int(str(ans).strip())
            if 1 <= n <= 5:
                answers[q_num - 1] = n
        except (ValueError, TypeError):
            continue

    wb.close()
    return answers


def load_ground_truth(path: Path) -> dict[str, dict[str, int]]:
    """
    Загрузить my_dataset.csv. Возвращает {person_name: {theme: rank}}.
    Пропущенные ранги (2000) исключаются.
    """
    df = pd.read_csv(path, encoding="utf-8")
    result = {}
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        if name.endswith(".pdf"):
            name = name[:-4]  # убираем .pdf
        themes_ranks = {}
        for theme in GALLUP_THEMES:
            if theme in df.columns:
                rank = row[theme]
                if pd.notna(rank) and int(rank) != MISSING_RANK:
                    themes_ranks[theme] = int(rank)
        result[name] = themes_ranks
    return result


# ============================================================================
# АЛГОРИТМ ПОДСЧЁТА
# ============================================================================

def score_person(answers: list[int | None], mapping: list[dict]) -> dict[str, float]:
    """
    Подсчитать сырые баллы по каждой теме для одного человека.

    Логика:
      - Для каждой пары (q, talent_A, talent_B):
        - ответ 5 → +2 к A, -2 к B
        - ответ 4 → +1 к A, -1 к B
        - ответ 3 → 0
        - ответ 2 → -1 к A, +1 к B
        - ответ 1 → -2 к A, +2 к B
        - пропуск → 0
      - Итог: словарь {theme: суммарный_балл}
    """
    scores: dict[str, float] = defaultdict(float)
    for entry in mapping:
        q_idx = entry["q"] - 1  # 0-based
        if q_idx < 0 or q_idx >= len(answers):
            continue
        ans = answers[q_idx]
        if ans is None:
            continue
        shift = ans - 3  # 5→+2, ..., 1→-2
        scores[entry["talent_A"]] += shift
        scores[entry["talent_B"]] -= shift
    return dict(scores)


def ranks_from_scores(scores: dict[str, float]) -> dict[str, int]:
    """
    Преобразовать сырые баллы в ранги (1 = самый сильный, 34 = самый слабый).
    Темы, которых нет в scores, попадают в хвост с наименьшим рангом (или вообще исключаются).
    """
    # Сортируем темы по убыванию балла
    sorted_themes = sorted(scores.items(), key=lambda x: -x[1])
    ranks = {}
    for i, (theme, _) in enumerate(sorted_themes, start=1):
        ranks[theme] = i
    return ranks


# ============================================================================
# МЕТРИКИ
# ============================================================================

def top_n_overlap(predicted_ranks: dict[str, int],
                  true_ranks: dict[str, int], n: int = 5) -> float:
    """Jaccard overlap: |intersection of top-N| / N."""
    pred_top = set(t for t, r in predicted_ranks.items() if r <= n)
    true_top = set(t for t, r in true_ranks.items() if r <= n)
    if not true_top:
        return 0.0
    return len(pred_top & true_top) / n


def top_n_exact_match(predicted_ranks: dict[str, int],
                      true_ranks: dict[str, int], n: int = 5) -> float:
    """Сколько из топ-N предсказанных совпали с топ-N истинными (порядок не важен)."""
    pred_top = set(t for t, r in predicted_ranks.items() if r <= n)
    true_top = set(t for t, r in true_ranks.items() if r <= n)
    if not true_top:
        return 0.0
    return len(pred_top & true_top) / n


def rank_set_overlap(predicted_ranks: dict[str, int],
                     true_ranks: dict[str, int]) -> float:
    """Пересечение предсказанного и истинного ранга для каждой темы (0..1)."""
    common = set(predicted_ranks) & set(true_ranks)
    if not common:
        return 0.0
    matches = sum(1 for t in common if predicted_ranks[t] == true_ranks[t])
    return matches / len(common)


def spearman_corr(predicted_ranks: dict[str, int],
                  true_ranks: dict[str, int]) -> float:
    """Spearman rank correlation по всем общим темам."""
    common = sorted(set(predicted_ranks) & set(true_ranks))
    if len(common) < 3:
        return float("nan")
    p = [predicted_ranks[t] for t in common]
    t = [true_ranks[t] for t in common]
    rho, _ = spearmanr(p, t)
    return rho


# ============================================================================
# ГЛАВНЫЙ ПРОГОН
# ============================================================================

def main():
    print("=" * 70)
    print("Gallup CliftonStrengths - детерминированный скоринг")
    print("=" * 70)

    mapping = load_mapping(MAPPING_XLSX)
    ground_truth = load_ground_truth(DATASET_CSV)
    print(f"[OK] Ground truth загружен: {len(ground_truth)} людей")
    for name in list(ground_truth.keys())[:3]:
        print(f"     {name}: {len(ground_truth[name])} тем с рангами")

    # Найти все xlsx с ответами
    answer_files = {}
    for f in ANSWERS_DIR.iterdir():
        if f.suffix.lower() == ".xlsx" and f.stem not in ("Gallup_200pairs_4columns",
                                                          "Gallup_Talent_Mapping_Balanced"):
            # Маппинг имени файла на ключ в ground truth
            stem = f.stem  # Alexandr, Ardak, ...
            answer_files[stem] = f

    print(f"[OK] Найдено {len(answer_files)} файлов с ответами")

    # Прогон по каждому человеку
    results = []
    matched_names = set()
    for name, path in sorted(answer_files.items()):
        # Найти ground truth по имени (с учётом вариаций)
        gt = None
        for gt_name in ground_truth:
            # Alexandr ↔ Alexandr-34.pdf → Alexandr
            if gt_name == name or gt_name.startswith(name + "-") or gt_name.startswith(name):
                gt = ground_truth[gt_name]
                matched_names.add(gt_name)
                break
        if gt is None:
            print(f"[SKIP] {name}: нет ground truth в my_dataset.csv")
            continue

        answers = load_answers_from_xlsx(path)
        scores = score_person(answers, mapping)
        pred_ranks = ranks_from_scores(scores)

        # Метрики
        top5 = top_n_exact_match(pred_ranks, gt, 5)
        top10 = top_n_exact_match(pred_ranks, gt, 10)
        top15 = top_n_exact_match(pred_ranks, gt, 15)
        exact = rank_set_overlap(pred_ranks, gt)
        rho = spearman_corr(pred_ranks, gt)

        results.append({
            "name": name,
            "n_answers": sum(1 for a in answers if a is not None),
            "n_gt_themes": len(gt),
            "top5": top5,
            "top10": top10,
            "top15": top15,
            "exact_rank": exact,
            "spearman": rho,
        })

        print(f"\n  {name}: answers={sum(1 for a in answers if a is not None)}, "
              f"gt_themes={len(gt)}")
        print(f"    Top-5: {top5*100:.1f}%   Top-10: {top10*100:.1f}%   "
              f"Top-15: {top15*100:.1f}%   Exact rank: {exact*100:.1f}%   "
              f"Spearman: {rho:.3f}")

        # Показать различия в топ-10
        pred_top10 = sorted([(t, r) for t, r in pred_ranks.items()], key=lambda x: x[1])[:10]
        true_top10 = sorted([(t, r) for t, r in gt.items()], key=lambda x: x[1])[:10]
        print(f"    Pred top-10: {[t for t, _ in pred_top10]}")
        print(f"    True top-10: {[t for t, _ in true_top10]}")

    # Итоговая таблица
    if results:
        df = pd.DataFrame(results)
        print("\n" + "=" * 70)
        print("ИТОГО (среднее по людям):")
        print("=" * 70)
        for col in ["top5", "top10", "top15", "exact_rank", "spearman"]:
            v = df[col].mean()
            print(f"  {col:<14}: {v*100 if 'spearman' not in col else v:.3f}")

        # Какая точность считается успехом?
        print("\n" + "=" * 70)
        print("ПРОВЕРКА ЦЕЛИ 96%:")
        print("=" * 70)
        for n, label in [(5, "top-5"), (10, "top-10"), (15, "top-15")]:
            avg = df[f"top{n}"].mean() * 100
            ok = "✅" if avg >= 96 else "❌"
            print(f"  {label}: {avg:.1f}%  {ok}")
        avg_sp = df["spearman"].mean()
        print(f"  Spearman: {avg_sp:.3f}  {'✅' if avg_sp >= 0.96 else '❌'}")


if __name__ == "__main__":
    main()
