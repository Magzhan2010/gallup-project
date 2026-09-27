"""Diagnose WHY predictions don't match truth."""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

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
            data.append({
                "q": pair_num,
                "talent_A": stmts[0][1], "talent_B": stmts[1][1],
                "text_A": stmts[0][0], "text_B": stmts[1][0]
            })
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


def main():
    mapping = load_mapping()
    gt = load_gt()

    # Pair -> {side_A: theme, side_B: theme, n_pairs: count}
    pair_info = {m["q"]: m for m in mapping}

    # Analyze one person in detail
    print("=" * 80)
    print("ДЕТАЛЬНАЯ ДИАГНОСТИКА: АЛЕКСАНДР")
    print("=" * 80)

    answers = load_answers(ANSWERS_DIR / "Alexandr.xlsx")
    alex_gt = gt["Alexandr-34"]

    # Compute scores per theme
    theme_scores = defaultdict(float)
    theme_pairs = defaultdict(list)
    for m in mapping:
        q_idx = m["q"] - 1
        if q_idx >= len(answers) or answers[q_idx] is None:
            continue
        ans = answers[q_idx]
        # INVERTED polarity
        shift = 3 - ans
        theme_scores[m["talent_A"]] += shift
        theme_scores[m["talent_B"]] -= shift
        theme_pairs[m["talent_A"]].append((m["q"], ans, "A"))
        theme_pairs[m["talent_B"]].append((m["q"], ans, "B"))

    # Compare top predicted vs top truth
    pred_sorted = sorted(theme_scores.items(), key=lambda x: -x[1])
    truth_sorted = sorted(alex_gt.items(), key=lambda x: x[1])

    print(f"\n{'Theme':<22}{'Score':>8}{'Pred#':>7}{'Truth#':>8}{'Δ':>6}")
    print("-" * 55)
    pred_rank = {t: i+1 for i, (t, _) in enumerate(pred_sorted)}
    for theme, truth_rank in truth_sorted[:15]:
        score = theme_scores.get(theme, 0)
        p_rank = pred_rank.get(theme, 99)
        delta = p_rank - truth_rank
        print(f"{theme:<22}{score:>+8.1f}{p_rank:>7}{truth_rank:>8}{delta:>+6}")

    print(f"\n{'Theme':<22}{'Score':>8}{'Pred#':>7}")
    print("-" * 40)
    for theme, score in pred_sorted[:15]:
        truth_rank = alex_gt.get(theme, 99)
        print(f"{theme:<22}{score:>+8.1f}{pred_rank[theme]:>7}{'(truth: '+str(truth_rank)+')':>15}")

    # Cross-check: look at first few answers and which themes they affect
    print("\n" + "=" * 80)
    print("ПЕРВЫЕ 15 ОТВЕТОВ АЛЕКСАНДРА И КАКИЕ ТЕМЫ ОНИ ЗАТРАГИВАЮТ")
    print("=" * 80)
    print(f"{'#':<4}{'Ans':>5}{'Theme A':<20}{'Theme B':<20}{'+A/-A':<8}{'+B/-B':<8}")
    for m in mapping[:15]:
        q_idx = m["q"] - 1
        ans = answers[q_idx]
        shift = 3 - ans if ans else 0
        a_delta = shift
        b_delta = -shift
        print(f"{m['q']:<4}{str(ans):>5}{m['talent_A']:<20}{m['talent_B']:<20}"
              f"{'+' + str(a_delta) if a_delta >= 0 else str(a_delta):<8}"
              f"{'+' + str(b_delta) if b_delta >= 0 else str(b_delta):<8}")


if __name__ == "__main__":
    main()
