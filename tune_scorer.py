"""
tune_scorer.py
==============
Подбирает параметры детерминированного алгоритма для максимальной точности.
Пробует:
  - полярность (нормальная / инвертированная)
  - формулу скоринга (linear, soft, sigmoid)
  - нормализацию (нет, per-theme, z-score, rank)
  - веса ответов (1=2, 2=1, 3=0, 4=1, 5=2) или другие

Сохраняет лучшую конфигурацию в best_config.json.
"""

import json
import sys
from collections import defaultdict
from itertools import product
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
from scipy.stats import spearmanr

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT = Path(r"C:\Users\User\gallup-project")
MAPPING_XLSX = PROJECT / "Gallup_Talent_Mapping_Balanced.xlsx"
MAPPING_SHEET = "400 строк - баланс 11-12"
DATASET_CSV = PROJECT / "my_dataset.csv"
ANSWERS_DIR = Path(r"C:\Users\User\Downloads\Telegram Desktop")
MISSING_RANK = 2000


def normalize_theme(name):
    if not name:
        return ""
    n = str(name).strip()
    if "-" in n:
        parts = n.split("-")
        n = "-".join(p.capitalize() for p in parts)
    return n


def load_mapping():
    wb = openpyxl.load_workbook(MAPPING_XLSX, read_only=True)
    ws = wb[MAPPING_SHEET]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    pair_statements = defaultdict(list)
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        try:
            stmt_num = int(str(row[0]).strip())
            pair_num = int(str(row[1]).strip())
        except (ValueError, TypeError):
            continue
        text = str(row[2] or "").strip()
        theme = normalize_theme(row[3])
        pair_statements[pair_num].append((stmt_num, theme))
    data = []
    for pair_num in sorted(pair_statements.keys()):
        stmts = sorted(pair_statements[pair_num], key=lambda x: x[0])
        if len(stmts) == 2:
            data.append({"q": pair_num, "talent_A": stmts[0][1], "talent_B": stmts[1][1]})
    return data


def load_answers(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    answers = [None] * 200
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
    for row in rows[1:]:
        if row[0] is None:
            continue
        try:
            q = int(str(row[0]).strip())
        except (ValueError, TypeError):
            continue
        if not (1 <= q <= 200):
            continue
        ans = row[answer_col]
        if ans is None:
            continue
        try:
            n = int(str(ans).strip())
            if 1 <= n <= 5:
                answers[q - 1] = n
        except (ValueError, TypeError):
            continue
    return answers


def load_gt():
    df = pd.read_csv(DATASET_CSV, encoding="utf-8")
    result = {}
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        if name.endswith(".pdf"):
            name = name[:-4]
        themes_ranks = {}
        for theme in df.columns:
            if theme == "name":
                continue
            rank = row[theme]
            if pd.notna(rank) and int(rank) != MISSING_RANK:
                themes_ranks[normalize_theme(theme)] = int(rank)
        result[name] = themes_ranks
    return result


def get_shift(ans, formula="linear", invert=False):
    """Вычисляет сдвиг для ответа (1..5) → вклад в сторону A.
    formula:
      - linear: 5→+2, 4→+1, 3→0, 2→-1, 1→-2 (или инверсия)
      - soft:   5→+1, 4→+0.5, 3→0, 2→-0.5, 1→-1
      - strict: 5→+3, 4→+1, 3→0, 2→-1, 1→-3 (усиленные крайние)
      - sigmoid: tanh-подобное
    invert: True → 5 даёт ОТРИЦАТЕЛЬНЫЙ вклад в A
    """
    if formula == "linear":
        s = ans - 3  # 5→+2
    elif formula == "soft":
        s = (ans - 3) / 2  # 5→+1
    elif formula == "strict":
        # 5→+3, 4→+1, 3→0, 2→-1, 1→-3 (квадратичнее)
        s = ans - 3
        if s > 0:
            s = s * 1.5
        elif s < 0:
            s = s * 1.5
        s = int(s) if s == int(s) else s
        s = {1: -3, 2: -1, 3: 0, 4: 1, 5: 3}[ans]
    elif formula == "sigmoid":
        # плавная сигмоида около 3
        s = np.tanh((ans - 3) / 1.0)
    else:
        s = ans - 3
    return -s if invert else s


def score(answers, mapping, formula="linear", invert=False, subtract_mean=False):
    scores = defaultdict(float)
    for entry in mapping:
        q_idx = entry["q"] - 1
        if q_idx < 0 or q_idx >= len(answers):
            continue
        ans = answers[q_idx]
        if ans is None:
            continue
        s = get_shift(ans, formula=formula, invert=invert)
        scores[entry["talent_A"]] += s
        scores[entry["talent_B"]] -= s
    # Вычитание среднего по человеку
    if subtract_mean and scores:
        m = np.mean(list(scores.values()))
        for k in scores:
            scores[k] -= m
    return dict(scores)


def normalize_scores(scores, mode="none"):
    if mode == "none":
        return scores
    if mode == "zscore":
        vals = np.array(list(scores.values()))
        m, s = vals.mean(), vals.std() + 1e-9
        return {k: (v - m) / s for k, v in scores.items()}
    if mode == "minmax":
        vals = np.array(list(scores.values()))
        lo, hi = vals.min(), vals.max()
        return {k: (v - lo) / (hi - lo + 1e-9) for k, v in scores.items()}
    if mode == "rank":
        # Ранговая нормализация (1 = низший, N = высший)
        sorted_items = sorted(scores.items(), key=lambda x: x[1])
        n = len(sorted_items)
        return {k: i + 1 for i, (k, _) in enumerate(sorted_items)}
    return scores


def to_ranks(scores):
    sorted_items = sorted(scores.items(), key=lambda x: -x[1])
    return {t: i + 1 for i, (t, _) in enumerate(sorted_items)}


def evaluate(answers, mapping, gt, formula, invert, subtract_mean, norm_mode):
    scores = score(answers, mapping, formula, invert, subtract_mean)
    scores = normalize_scores(scores, mode=norm_mode)
    pred = to_ranks(scores)
    common = sorted(set(pred) & set(gt))
    if len(common) < 3:
        return None
    p = [pred[t] for t in common]
    t = [gt[t] for t in common]
    rho, _ = spearmanr(p, t)

    pred_top = set(t for t, r in pred.items() if r <= 5)
    true_top = set(t for t, r in gt.items() if r <= 5)
    overlap5 = len(pred_top & true_top) / 5
    pred_top10 = set(t for t, r in pred.items() if r <= 10)
    true_top10 = set(t for t, r in gt.items() if r <= 10)
    overlap10 = len(pred_top10 & true_top10) / 10
    # Mean absolute rank error
    diffs = [abs(pred[t] - gt[t]) for t in common]
    mae = np.mean(diffs)
    return {"rho": rho, "top5": overlap5, "top10": overlap10, "mae": mae, "n": len(common)}


def main():
    mapping = load_mapping()
    gt = load_gt()
    print(f"Mapping: {len(mapping)} pairs, GT: {len(gt)} people")

    files = {}
    for f in ANSWERS_DIR.iterdir():
        if f.suffix.lower() == ".xlsx" and not f.stem.startswith(("Gallup_200", "Gallup_Talent")):
            files[f.stem] = f

    # Match files to GT names
    matched = []
    for stem, path in files.items():
        gt_name = None
        for g in gt:
            if g == stem or g.startswith(stem + "-") or g.startswith(stem):
                gt_name = g
                break
        if gt_name is None:
            continue
        answers = load_answers(path)
        matched.append((stem, answers, gt[gt_name]))

    print(f"Matched {len(matched)} people with GT\n")

    # Grid search
    formulas = ["linear", "soft", "strict", "sigmoid"]
    inverts = [False, True]
    subtract_means = [False, True]
    norm_modes = ["none", "zscore", "rank"]

    best = None
    all_results = []

    for formula, invert, subtract_mean, norm_mode in product(formulas, inverts, subtract_means, norm_modes):
        scores_per_person = []
        for name, answers, g in matched:
            r = evaluate(answers, mapping, g, formula, invert, subtract_mean, norm_mode)
            if r:
                scores_per_person.append(r)
        if not scores_per_person:
            continue
        avg = {
            "rho": np.mean([r["rho"] for r in scores_per_person]),
            "top5": np.mean([r["top5"] for r in scores_per_person]),
            "top10": np.mean([r["top10"] for r in scores_per_person]),
            "mae": np.mean([r["mae"] for r in scores_per_person]),
        }
        all_results.append({
            "formula": formula, "invert": invert, "sub_mean": subtract_mean, "norm": norm_mode,
            **avg
        })
        if best is None or avg["rho"] > best["rho"]:
            best = {"formula": formula, "invert": invert, "sub_mean": subtract_mean, "norm": norm_mode, **avg}

    # Sort by rho
    all_results.sort(key=lambda x: -x["rho"])
    print(f"{'formula':<10}{'invert':<8}{'subMean':<10}{'norm':<10}{'ρ':>8}{'top5':>8}{'top10':>8}{'MAE':>8}")
    print("=" * 70)
    for r in all_results[:20]:
        print(f"{r['formula']:<10}{str(r['invert']):<8}{str(r['sub_mean']):<10}{r['norm']:<10}"
              f"{r['rho']:>+8.3f}{r['top5']*100:>7.0f}%{r['top10']*100:>7.0f}%{r['mae']:>8.2f}")

    print(f"\n*** ЛУЧШАЯ КОНФИГУРАЦИЯ ***")
    print(f"  formula:  {best['formula']}")
    print(f"  invert:   {best['invert']}")
    print(f"  sub_mean: {best['sub_mean']}")
    print(f"  norm:     {best['norm']}")
    print(f"  ρ:        {best['rho']:+.3f}")
    print(f"  top-5:    {best['top5']*100:.0f}%")
    print(f"  top-10:   {best['top10']*100:.0f}%")
    print(f"  MAE:      {best['mae']:.2f}")

    # Сохраним лучшую
    with open(PROJECT / "best_config.json", "w", encoding="utf-8") as f:
        json.dump(best, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Сохранено в best_config.json")


if __name__ == "__main__":
    main()
