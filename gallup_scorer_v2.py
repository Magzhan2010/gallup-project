"""
gallup_scorer_v2.py
===================
Скоренг по реальной методологии Gallup (из технического отчёта 2014).

Реализовано:
  1. MEAN вместо SUM  ("calculation of scores is based on the mean of the intensity")
  2. Reliability shrinkage — "theme reliabilities used as subsidiary ranking factors"
  3. Ipsativity: если обе стороны пары привязаны к темам, не-выбранная тема
     получает 0 (а не отрицательный вклад)
  4. Нормализация по z-score внутри человека (убирает response bias)
  5. Разные формулы value для response category

Проверка на 10 размеченных людях + сравнение с baseline.
"""

import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT = Path(r"C:\Users\User\gallup-project")
sys.path.insert(0, str(PROJECT))

from gallup_psychometrics import (  # noqa: E402
    ALPHA_SAMPLE1,
    ALPHA_SAMPLE3,
    GALLUP_ITEM_COUNTS,
    TEST_RETEST_M1,
    TEST_RETEST_M3,
    TEST_RETEST_M6,
)

MAPPING_XLSX = PROJECT / "Gallup_Talent_Mapping_Balanced.xlsx"
MAPPING_SHEET = "400 строк - баланс 11-12"
DATASET_CSV = PROJECT / "my_dataset.csv"
ANSWERS_DIR = Path(r"C:\Users\User\Downloads\Telegram Desktop")
MISSING_RANK = 2000

THEMES = sorted(GALLUP_ITEM_COUNTS.keys())


# ============================================================================
# ЗАГРУЗКА
# ============================================================================

def normalize_theme(name):
    if not name:
        return ""
    n = str(name).strip()
    if "-" in n:
        return "-".join(p.capitalize() for p in n.split("-"))
    return n


def load_mapping():
    wb = openpyxl.load_workbook(MAPPING_XLSX, read_only=True)
    ws = wb[MAPPING_SHEET]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    pair_stmts = defaultdict(list)
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
        pair_stmts[pair_num].append(theme)
    pairs, broken = [], []
    for pn in sorted(pair_stmts.keys()):
        stmts = pair_stmts[pn]
        if len(stmts) != 2:
            continue
        if stmts[0] == stmts[1]:
            broken.append(pn)
            continue
        pairs.append({"q": pn, "A": stmts[0], "B": stmts[1]})
    print(f"[OK] {len(pairs)} валидных пар, {len(broken)} сломанных исключено")
    return pairs


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
        ranks = {}
        for theme in df.columns:
            if theme == "name":
                continue
            r = row[theme]
            if pd.notna(r) and int(r) != MISSING_RANK:
                ranks[normalize_theme(theme)] = int(r)
        result[name] = ranks
    return result


# ============================================================================
# ФОРМУЛЫ VALUE ДЛЯ RESPONSE CATEGORY
# ============================================================================

def response_value(answer: int, formula: str, invert: bool = True) -> float:
    """
    Value для одного ответа (1..5) — «интенсивность самоописания».
    invert=True соответствует нашим данным (5 = правое утверждение).
    """
    if formula == "linear":
        v = answer - 3          # 5→+2, 4→+1, 3→0, 2→-1, 1→-2
    elif formula == "guttman":
        # Классическая Гутмановская шкала: 1,2,3,4,5 с нарастающим весом
        v = {1: -2.0, 2: -1.0, 3: 0.0, 4: 1.0, 5: 2.0}[answer]
    elif formula == "sigmoid":
        v = float(np.tanh((answer - 3) / 1.2))
    elif formula == "step":
        # Бинарно: только крайние ответы дают сигнал
        v = {1: -2.0, 2: -0.5, 3: 0.0, 4: 0.5, 5: 2.0}[answer]
    elif formula == "weighted":
        # Вес ответа пропорционален вероятности быть "верным" (максимум на 5)
        v = {1: -1.0, 2: -0.7, 3: 0.0, 4: 0.7, 5: 1.0}[answer]
    elif formula == "noneutral_half":
        # Нейтральный ответ = 0, но 3.5 промежуточных
        v = {1: -2.0, 2: -1.0, 3: 0.0, 4: 1.0, 5: 2.0}[answer]
    else:
        v = answer - 3
    return -v if invert else v


# ============================================================================
# СКОРИНГ
# ============================================================================

def score_gallup_style(
    answers,
    mapping,
    formula="linear",
    invert=True,
    use_mean=True,          # MEAN (Gallup) вместо SUM
    ipsative=True,          # не-выбранная тема в ipsative-паре = 0, не -
    reliability=None,       # словарь {theme: r} для shrinkage
    standardize=True,       # z-score внутри человека
    reliability_mode="multiply",  # 'multiply' | 'shrink' | None
):
    """
    Скоринг в стиле Gallup.

    Логика:
      1. Для каждой пары: value = response_value(answer)
         - если выбрана левая (value>0): +value к теме A
         - если выбрана правая: -value к теме B (т.е. +|value| к B)
      2. Ipsative-коррекция: если обе стороны привязаны к темам,
         не-выбранная тема получает 0 (Gallup: "selection of one statement
         assigns points to the themes aligned with both statements")
      3. Агрегация: MEAN по значениям темы (Gallup) или SUM
      4. Стандартизация внутри человека (убирает response bias)
      5. Reliability shrinkage: оценка истинного балла с учётом надёжности
    """
    # Собираем список значений по каждой теме
    theme_values = defaultdict(list)

    for entry in mapping:
        q_idx = entry["q"] - 1
        if q_idx < 0 or q_idx >= len(answers):
            continue
        ans = answers[q_idx]
        if ans is None:
            continue
        v = response_value(ans, formula=formula, invert=invert)
        if abs(v) < 1e-9:
            continue

        theme_a, theme_b = entry["A"], entry["B"]
        # v > 0 → выбрана левая сторона (при invert=True: answer=1 → v=+2)
        if v > 0:
            theme_values[theme_a].append(v)
            if not ipsative:
                theme_values[theme_b].append(-v)
            # ipsative=True → тема B не получает вклад (0 вместо -v)
        else:
            theme_values[theme_b].append(-v)
            if not ipsative:
                theme_values[theme_a].append(v)

    # Агрегация
    if use_mean:
        raw = {t: float(np.mean(vals)) if vals else 0.0
               for t, vals in theme_values.items()}
    else:
        raw = {t: float(np.sum(vals)) if vals else 0.0
               for t, vals in theme_values.items()}

    # Все темы с нулевым вкладом
    for t in THEMES:
        raw.setdefault(t, 0.0)

    scores = dict(raw)

    # Стандартизация внутри человека (z-score по 34 темам)
    if standardize:
        vals = np.array([scores[t] for t in THEMES])
        m, s = vals.mean(), vals.std()
        if s > 1e-9:
            scores = {t: (scores[t] - m) / s for t in THEMES}

    # Reliability weighting
    if reliability and reliability_mode == "multiply":
        for t in THEMES:
            r = reliability.get(t, 0.65)
            scores[t] *= r
    elif reliability and reliability_mode == "shrink":
        # Классическая reliability correction: best estimate = mean + (obs-mean)*r
        vals = np.array([scores[t] for t in THEMES])
        m = vals.mean()
        for t in THEMES:
            r = reliability.get(t, 0.65)
            scores[t] = m + (scores[t] - m) * r

    return scores


def ranks_from_scores(scores):
    sorted_items = sorted(scores.items(), key=lambda x: -x[1])
    return {t: i + 1 for i, (t, _) in enumerate(sorted_items)}


def evaluate(answers, mapping, gt, **kwargs):
    scores = score_gallup_style(answers, mapping, **kwargs)
    pred = ranks_from_scores(scores)
    common = sorted(set(pred) & set(gt))
    if len(common) < 5:
        return None
    p = [pred[t] for t in common]
    t = [gt[t] for t in common]
    rho, _ = spearmanr(p, t)
    pred5 = set(x for x, r in pred.items() if r <= 5)
    true5 = set(x for x, r in gt.items() if r <= 5)
    pred10 = set(x for x, r in pred.items() if r <= 10)
    true10 = set(x for x, r in gt.items() if r <= 10)
    pred15 = set(x for x, r in pred.items() if r <= 15)
    true15 = set(x for x, r in gt.items() if r <= 15)
    return {
        "rho": rho,
        "top5": len(pred5 & true5) / 5,
        "top10": len(pred10 & true10) / 10,
        "top15": len(pred15 & true15) / 15,
    }


def avg(results, key):
    vals = [r[key] for r in results if r]
    return float(np.mean(vals)) if vals else 0.0


def main():
    print("=" * 78)
    print("Gallup Copy — Скоринг по официальной методологии Gallup (отчёт 2014)")
    print("=" * 78)

    mapping = load_mapping()
    gt = load_gt()

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
        matched.append((stem, load_answers(path), gt[gt_name]))
    print(f"[OK] {len(matched)} людей с ground truth\n")

    RELIABILITY_SETS = {
        "none": None,
        "alpha1": ALPHA_SAMPLE1,
        "alpha3": ALPHA_SAMPLE3,
        "retest1": TEST_RETEST_M1,
        "retest3": TEST_RETEST_M3,
        "retest6": TEST_RETEST_M6,
    }

    configs = []

    # A. BASELINE (текущий продакшн): sum, linear, no ipsative fix, no reliability
    configs.append({
        "name": "A. BASELINE (сейчас в проде)",
        "kwargs": dict(formula="linear", invert=True, use_mean=False,
                       ipsative=False, reliability=None,
                       standardize=False, reliability_mode="multiply"),
    })

    # B. MEAN вместо SUM (Gallup)
    configs.append({
        "name": "B. MEAN вместо SUM",
        "kwargs": dict(formula="linear", invert=True, use_mean=True,
                       ipsative=False, reliability=None,
                       standardize=False, reliability_mode="multiply"),
    })

    # C. MEAN + Ipsativity fix
    configs.append({
        "name": "C. MEAN + Ipsativity fix",
        "kwargs": dict(formula="linear", invert=True, use_mean=True,
                       ipsative=True, reliability=None,
                       standardize=False, reliability_mode="multiply"),
    })

    # D. MEAN + Ipsativity + Z-score
    configs.append({
        "name": "D. MEAN + Ipsative + Z-score",
        "kwargs": dict(formula="linear", invert=True, use_mean=True,
                       ipsative=True, reliability=None,
                       standardize=True, reliability_mode="multiply"),
    })

    # E. + reliability multiply (test-retest 3 мес)
    for rel_name in ["alpha3", "retest3", "retest6"]:
        configs.append({
            "name": f"E. D + reliability({rel_name}) x multiply",
            "kwargs": dict(formula="linear", invert=True, use_mean=True,
                           ipsative=True, reliability=RELIABILITY_SETS[rel_name],
                           standardize=True, reliability_mode="multiply"),
        })
        configs.append({
            "name": f"F. D + reliability({rel_name}) x shrink",
            "kwargs": dict(formula="linear", invert=True, use_mean=True,
                           ipsative=True, reliability=RELIABILITY_SETS[rel_name],
                           standardize=True, reliability_mode="shrink"),
        })

    # G. Разные формулы value
    for f in ["guttman", "sigmoid", "step", "weighted"]:
        configs.append({
            "name": f"G. formula={f} + mean+ips+z",
            "kwargs": dict(formula=f, invert=True, use_mean=True,
                           ipsative=True, reliability=None,
                           standardize=True, reliability_mode="multiply"),
        })

    print(f"{'Config':<44}{'ρ':>8}{'top5':>8}{'top10':>8}{'top15':>8}")
    print("-" * 78)
    best = None
    for cfg in configs:
        results = [evaluate(m[1], mapping, m[2], **cfg["kwargs"]) for m in matched]
        r = avg(results, "rho")
        line = (f"{cfg['name']:<44}{r:>+8.3f}"
                f"{avg(results,'top5')*100:>7.0f}%"
                f"{avg(results,'top10')*100:>7.0f}%"
                f"{avg(results,'top15')*100:>7.0f}%")
        print(line)
        if best is None or r > best[0]:
            best = (r, cfg, avg(results, "top5"), avg(results, "top10"), avg(results, "top15"))

    print("\n" + "=" * 78)
    print(f"🏆 ЛУЧШАЯ КОНФИГУРАЦИЯ: {best[1]['name']}")
    print(f"   ρ={best[0]:+.3f}  top5={best[2]*100:.0f}%  top10={best[3]*100:.0f}%  top15={best[4]*100:.0f}%")
    print("=" * 78)

    # Детальная раскладка по людям для лучшей конфигурации
    print("\nPer-person (best config):")
    results = []
    for name, ans, g in matched:
        r = evaluate(ans, mapping, g, **best[1]["kwargs"])
        results.append((name, r))
    for name, r in results:
        if r:
            print(f"  {name:<14} ρ={r['rho']:+.3f}  top5={r['top5']*100:>3.0f}%  top10={r['top10']*100:>3.0f}%")

    # Сравнение с baseline по людям
    print("\nPer-person (BASELINE для сравнения):")
    base_kwargs = configs[0]["kwargs"]
    for name, ans, g in matched:
        r = evaluate(ans, mapping, g, **base_kwargs)
        if r:
            print(f"  {name:<14} ρ={r['rho']:+.3f}  top5={r['top5']*100:>3.0f}%  top10={r['top10']*100:>3.0f}%")

    # Сохраняем лучший конфиг
    import json
    with open(PROJECT / "best_config_v2.json", "w", encoding="utf-8") as f:
        json.dump({
            "name": best[1]["name"],
            "kwargs": {k: v for k, v in best[1]["kwargs"].items() if k != "reliability"},
            "reliability_set": next(
                (rn for rn, rv in RELIABILITY_SETS.items()
                 if rv is not None and rv is best[1]["kwargs"].get("reliability")),
                None),
            "metrics": {"rho": best[0], "top5": best[2], "top10": best[3], "top15": best[4]},
        }, f, indent=2, ensure_ascii=False)
    print("\n[OK] Сохранено в best_config_v2.json")


if __name__ == "__main__":
    main()
