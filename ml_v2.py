"""
ml_v2.py
========
Улучшенная версия алгоритма. Пробуем:
  1. Исключение 10 сломанных пар
  2. Per-person centering (вычитание mean)
  3. Ridge regression для обучения весов пар
  4. Per-pair weight regularization
  5. Подбор оптимальной формулы скоринга через CV
"""

import json
import sys
import warnings
from collections import defaultdict
from itertools import product
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.model_selection import LeaveOneOut, KFold

warnings.filterwarnings('ignore')

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT = Path(r"C:\Users\User\gallup-project")
MAPPING_XLSX = PROJECT / "Gallup_Talent_Mapping_Balanced.xlsx"
MAPPING_SHEET = "400 строк - баланс 11-12"
DATASET_CSV = PROJECT / "my_dataset.csv"
ANSWERS_DIR = Path(r"C:\Users\User\Downloads\Telegram Desktop")
MISSING_RANK = 2000

GALLUP_THEMES = [
    "Achiever", "Discipline", "Activator", "Maximizer", "Adaptability",
    "Includer", "Analytical", "Input", "Arranger", "Focus",
    "Command", "Self-Assurance", "Connectedness", "Individualization", "Context",
    "Intellection", "Belief", "Responsibility", "Communication", "Significance",
    "Developer", "Positivity", "Futuristic", "Learner", "Consistency",
    "Restorative", "Competition", "Woo", "Empathy", "Relator",
    "Ideation", "Strategic", "Deliberative", "Harmony",
]


# ============================================================================
# ЗАГРУЗКА
# ============================================================================

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
            pair_num = int(str(row[1]).strip())
        except (ValueError, TypeError):
            continue
        text = str(row[2] or "").strip()
        theme = normalize_theme(row[3])
        if not text or not theme:
            continue
        pair_statements[pair_num].append((stmt_num, theme) if False else theme)

    pairs = []
    broken = []
    for pair_num in sorted(pair_statements.keys()):
        stmts = pair_statements[pair_num]
        if len(stmts) != 2:
            continue
        if stmts[0] == stmts[1]:
            broken.append(pair_num)
            continue  # пропускаем сломанные
        pairs.append({
            'q': pair_num,
            'A': stmts[0],
            'B': stmts[1],
        })
    print(f"[OK] Загружено {len(pairs)} валидных пар (исключено {len(broken)} сломанных: {broken})")
    return pairs, broken


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


# ============================================================================
# ДЕТЕРМИНИРОВАННЫЙ АЛГОРИТМ (разные варианты)
# ============================================================================

def get_shift(ans, formula='linear', invert=True):
    """ans = 1..5 → сдвиг в сторону A (или -shift если invert)."""
    if formula == 'linear':
        s = (3 - ans) if invert else (ans - 3)
    elif formula == 'soft':
        s = ((3 - ans) if invert else (ans - 3)) * 0.5
    elif formula == 'strict':
        raw = (3 - ans) if invert else (ans - 3)
        s = raw * 1.5
    elif formula == 'sigmoid':
        raw = (3 - ans) if invert else (ans - 3)
        s = np.tanh(raw / 1.0) * 2
    elif formula == 'step':
        # 5 → +2, 4 → +1, 3 → 0, 2 → -1, 1 → -2 (или инверсия)
        s = (3 - ans) if invert else (ans - 3)
    return s


def deterministic_score(answers, mapping, formula='linear', invert=True, center=False):
    scores = defaultdict(float)
    for entry in mapping:
        q_idx = entry['q'] - 1
        if q_idx < 0 or q_idx >= len(answers):
            continue
        ans = answers[q_idx]
        if ans is None:
            continue
        s = get_shift(ans, formula=formula, invert=invert)
        scores[entry['A']] += s
        scores[entry['B']] -= s
    if center and scores:
        m = np.mean(list(scores.values()))
        for k in scores:
            scores[k] -= m
    return dict(scores)


def ranks_from_scores(scores):
    sorted_items = sorted(scores.items(), key=lambda x: -x[1])
    return {t: i + 1 for i, (t, _) in enumerate(sorted_items)}


def evaluate(answers, mapping, gt, formula, invert, center):
    scores = deterministic_score(answers, mapping, formula, invert, center)
    pred = ranks_from_scores(scores)
    common = sorted(set(pred) & set(gt))
    if len(common) < 5:
        return None
    p = [pred[t] for t in common]
    t = [gt[t] for t in common]
    rho, _ = spearmanr(p, t)
    pred_top5 = set(t for t, r in pred.items() if r <= 5)
    true_top5 = set(t for t, r in gt.items() if r <= 5)
    overlap5 = len(pred_top5 & true_top5) / 5
    pred_top10 = set(t for t, r in pred.items() if r <= 10)
    true_top10 = set(t for t, r in gt.items() if r <= 10)
    overlap10 = len(pred_top10 & true_top10) / 10
    return {'rho': rho, 'top5': overlap5, 'top10': overlap10, 'n': len(common)}


# ============================================================================
# ML: RIDGE REGRESSION
# ============================================================================

def build_feature_matrix(answers_list, mapping):
    """
    Для каждого человека строим вектор фичей:
    - Для каждой пары: shift ∈ {-2,-1,0,1,2} (inverted)
    - Это вход для Ridge
    """
    X = []
    for answers in answers_list:
        row = []
        for entry in mapping:
            q_idx = entry['q'] - 1
            ans = answers[q_idx] if q_idx < len(answers) else None
            shift = (3 - ans) if ans is not None else 0
            # +shift в сторону A, -shift в сторону B
            row.append(shift)
        X.append(row)
    return np.array(X, dtype=float)


def build_target_matrix(gt_list, mapping):
    """
    Для каждого человека - вектор скоров по 34 темам.
    Используем RANK-based target: rank 1 = высший талант → score = 33, rank 34 = низший → score = 0.
    """
    all_themes = sorted(set(GALLUP_THEMES))
    theme_to_idx = {t: i for i, t in enumerate(all_themes)}
    Y = []
    for gt in gt_list:
        # rank → score: 1 → 33, 34 → 0 (или negative для ML)
        theme_scores = np.zeros(len(all_themes))
        for theme, rank in gt.items():
            if theme in theme_to_idx:
                theme_scores[theme_to_idx[theme]] = 35 - rank  # rank 1 → 34
        Y.append(theme_scores)
    return np.array(Y, dtype=float)


def ridge_train_predict(X_train, Y_train, X_test, alpha=1.0):
    """Обучаем Ridge для каждой темы отдельно."""
    n_themes = Y_train.shape[1]
    Y_pred = np.zeros((X_test.shape[0], n_themes))
    for j in range(n_themes):
        model = Ridge(alpha=alpha)
        model.fit(X_train, Y_train[:, j])
        Y_pred[:, j] = model.predict(X_test)
    return Y_pred


def cross_validate_ridge(matched, mapping, alpha_grid):
    """Leave-one-out CV для подбора alpha."""
    n = len(matched)
    X = build_feature_matrix([m[1] for m in matched], mapping)
    Y = build_target_matrix([m[2] for m in matched], mapping)

    best_alpha = None
    best_score = -1
    results_by_alpha = {}

    for alpha in alpha_grid:
        loo = LeaveOneOut()
        scores_per_fold = []
        for train_idx, test_idx in loo.split(X):
            X_tr, X_te = X[train_idx], X[test_idx]
            Y_tr, Y_te = Y[train_idx], Y[test_idx]
            Y_pred = ridge_train_predict(X_tr, Y_tr, X_te, alpha=alpha)
            # Оцениваем по Spearman + top-5
            for k in range(len(test_idx)):
                pred_ranks = ranks_from_scores({GALLUP_THEMES[i]: Y_pred[k, i] for i in range(len(GALLUP_THEMES))})
                gt_dict = matched[test_idx[k]][2]
                common = sorted(set(pred_ranks) & set(gt_dict))
                if len(common) >= 5:
                    p = [pred_ranks[t] for t in common]
                    t = [gt_dict[t] for t in common]
                    rho, _ = spearmanr(p, t)
                    pred_top5 = set(x for x, r in pred_ranks.items() if r <= 5)
                    true_top5 = set(x for x, r in gt_dict.items() if r <= 5)
                    overlap5 = len(pred_top5 & true_top5) / 5
                    scores_per_fold.append({'rho': rho, 'top5': overlap5})
        avg_rho = np.mean([s['rho'] for s in scores_per_fold])
        avg_top5 = np.mean([s['top5'] for s in scores_per_fold])
        results_by_alpha[alpha] = {'rho': avg_rho, 'top5': avg_top5}
        if avg_rho > best_score:
            best_score = avg_rho
            best_alpha = alpha

    return best_alpha, results_by_alpha


def main():
    print("=" * 70)
    print("Gallup 34 таланта - попытка улучшить алгоритм")
    print("=" * 70)

    mapping, broken = load_mapping()
    gt = load_gt()
    print(f"[OK] GT: {len(gt)} людей")

    # Загружаем ответы
    files = {}
    for f in ANSWERS_DIR.iterdir():
        if f.suffix.lower() == ".xlsx" and not f.stem.startswith(("Gallup_200", "Gallup_Talent")):
            files[f.stem] = f

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
    print(f"[OK] Matched {len(matched)} людей\n")

    # ========================================================================
    # 1. Детерминированные варианты
    # ========================================================================
    print("=" * 70)
    print("1. Детерминированные алгоритмы (с инвертированной полярностью)")
    print("=" * 70)
    print(f"{'formula':<10}{'center':<8}{'ρ':>8}{'top5':>8}{'top10':>8}")
    print("-" * 50)
    for formula in ['linear', 'soft', 'strict', 'sigmoid']:
        for center in [False, True]:
            results = []
            for name, answers, g in matched:
                r = evaluate(answers, mapping, g, formula, invert=True, center=center)
                if r:
                    results.append(r)
            avg_rho = np.mean([r['rho'] for r in results])
            avg_top5 = np.mean([r['top5'] for r in results])
            avg_top10 = np.mean([r['top10'] for r in results])
            print(f"{formula:<10}{str(center):<8}{avg_rho:>+8.3f}{avg_top5*100:>7.0f}%{avg_top10*100:>7.0f}%")

    # ========================================================================
    # 2. Ridge Regression с CV
    # ========================================================================
    print()
    print("=" * 70)
    print("2. Ridge Regression (ML) — leave-one-out CV")
    print("=" * 70)

    alpha_grid = [0.01, 0.1, 1.0, 5.0, 10.0, 50.0, 100.0, 500.0, 1000.0]
    best_alpha, results_by_alpha = cross_validate_ridge(matched, mapping, alpha_grid)

    print(f"{'alpha':<10}{'ρ':>10}{'top5':>10}")
    print("-" * 35)
    for alpha, r in sorted(results_by_alpha.items()):
        marker = " ⭐" if alpha == best_alpha else ""
        print(f"{alpha:<10}{r['rho']:>+10.3f}{r['top5']*100:>9.0f}%{marker}")

    print(f"\nBest alpha: {best_alpha}")
    print(f"  ρ: {results_by_alpha[best_alpha]['rho']:+.3f}")
    print(f"  top-5: {results_by_alpha[best_alpha]['top5']*100:.0f}%")

    # ========================================================================
    # 3. Ensemble: deterministic + ML
    # ========================================================================
    print()
    print("=" * 70)
    print("3. Ensemble: deterministic + ML")
    print("=" * 70)

    X = build_feature_matrix([m[1] for m in matched], mapping)
    Y = build_target_matrix([m[2] for m in matched], mapping)

    # LOOCV ensemble
    loo = LeaveOneOut()
    ensemble_results = []
    for train_idx, test_idx in loo.split(X):
        X_tr, X_te = X[train_idx], X[test_idx]
        Y_tr, Y_te = Y[train_idx], Y[test_idx]

        # Детерминированный
        ans_test = matched[test_idx[0]][1]
        det_scores = deterministic_score(ans_test, mapping, formula='linear', invert=True, center=False)
        det_ranks = ranks_from_scores(det_scores)

        # ML
        ml_pred = ridge_train_predict(X_tr, Y_tr, X_te, alpha=best_alpha)
        ml_ranks = ranks_from_scores({GALLUP_THEMES[i]: ml_pred[0, i] for i in range(len(GALLUP_THEMES))})

        # Ensemble: усреднить rank-ranks (преобразовать обратно в score)
        ensemble_scores = {}
        for theme in GALLUP_THEMES:
            det_rank = det_ranks.get(theme, 17)
            ml_rank = ml_ranks.get(theme, 17)
            # Нижний ранг = выше score; усредняем
            ensemble_scores[theme] = -((det_rank + ml_rank) / 2)
        ens_ranks = ranks_from_scores(ensemble_scores)

        # Оценка
        gt_dict = matched[test_idx[0]][2]
        common = sorted(set(ens_ranks) & set(gt_dict))
        p = [ens_ranks[t] for t in common]
        t = [gt_dict[t] for t in common]
        rho, _ = spearmanr(p, t)
        pred_top5 = set(x for x, r in ens_ranks.items() if r <= 5)
        true_top5 = set(x for x, r in gt_dict.items() if r <= 5)
        overlap5 = len(pred_top5 & true_top5) / 5
        ensemble_results.append({'rho': rho, 'top5': overlap5})

    avg_ens_rho = np.mean([r['rho'] for r in ensemble_results])
    avg_ens_top5 = np.mean([r['top5'] for r in ensemble_results])
    print(f"\nEnsemble (det + ML rank-average):")
    print(f"  ρ: {avg_ens_rho:+.3f}")
    print(f"  top-5: {avg_ens_top5*100:.0f}%")

    # Сравнение
    print()
    print("=" * 70)
    print("ИТОГО (LOOCV):")
    print("=" * 70)
    det_results = []
    for name, answers, g in matched:
        r = evaluate(answers, mapping, g, formula='linear', invert=True, center=False)
        if r:
            det_results.append(r)
    print(f"  Baseline (deterministic):     ρ={np.mean([r['rho'] for r in det_results]):+.3f}  top-5={np.mean([r['top5'] for r in det_results])*100:.0f}%")
    print(f"  ML (Ridge alpha={best_alpha}):       ρ={results_by_alpha[best_alpha]['rho']:+.3f}  top-5={results_by_alpha[best_alpha]['top5']*100:.0f}%")
    print(f"  Ensemble (det + ML):           ρ={avg_ens_rho:+.3f}  top-5={avg_ens_top5*100:.0f}%")


if __name__ == "__main__":
    main()
