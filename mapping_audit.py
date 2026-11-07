"""
mapping_audit.py
================
Аудит маппинга на основе официальной методологии Gallup (отчёт 2014).

1. Сравнение распределения наших пар с реальной структурой Gallup (Table 1).
2. Эмпирическая проверка КАЖДОЙ темы: корреляция между ответами,
   «голосующими» за эту тему, и её реальным рангом в Gallup.
   Если корреляция отрицательная → тема смэплена неверно.
3. Поиск «подозрительных» пар, которые тянут темы вниз.
4. Пересчёт с отключением подозрительных тем.
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

from gallup_psychometrics import GALLUP_ITEM_COUNTS, DOMAINS  # noqa: E402

MAPPING_XLSX = PROJECT / "Gallup_Talent_Mapping_Balanced.xlsx"
MAPPING_SHEET = "400 строк - баланс 11-12"
DATASET_CSV = PROJECT / "my_dataset.csv"
ANSWERS_DIR = Path(r"C:\Users\User\Downloads\Telegram Desktop")
MISSING_RANK = 2000

THEMES = sorted(GALLUP_ITEM_COUNTS.keys())


def normalize_theme(name):
    if not name:
        return ""
    n = str(name).strip()
    if "-" in n:
        return "-".join(p.capitalize() for p in n.split("-"))
    return n


def load_mapping(with_text=True):
    wb = openpyxl.load_workbook(MAPPING_XLSX, read_only=True)
    ws = wb[MAPPING_SHEET]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    pair_stmts = defaultdict(list)
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
        pair_stmts[pair_num].append({"num": stmt_num, "text": text, "theme": theme})
    pairs, broken = [], []
    for pn in sorted(pair_stmts.keys()):
        stmts = sorted(pair_stmts[pn], key=lambda x: x["num"])
        if len(stmts) != 2:
            continue
        if stmts[0]["theme"] == stmts[1]["theme"]:
            broken.append(pn)
            continue
        pairs.append({
            "q": pn,
            "A": stmts[0]["theme"], "B": stmts[1]["theme"],
            "A_text": stmts[0]["text"], "B_text": stmts[1]["text"],
        })
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
        ranks = {}
        for theme in df.columns:
            if theme == "name":
                continue
            r = row[theme]
            if pd.notna(r) and int(r) != MISSING_RANK:
                ranks[normalize_theme(theme)] = int(r)
        result[name] = ranks
    return result


def ranks_from_scores(scores):
    sorted_items = sorted(scores.items(), key=lambda x: -x[1])
    return {t: i + 1 for i, (t, _) in enumerate(sorted_items)}


def score(answers, mapping, invert=True):
    scores = defaultdict(float)
    for entry in mapping:
        q_idx = entry["q"] - 1
        if q_idx < 0 or q_idx >= len(answers):
            continue
        ans = answers[q_idx]
        if ans is None:
            continue
        v = (3 - ans) if invert else (ans - 3)
        scores[entry["A"]] += v
        scores[entry["B"]] -= v
    for t in THEMES:
        scores.setdefault(t, 0.0)
    return dict(scores)


def evaluate(answers, mapping, gt):
    sc = score(answers, mapping)
    pred = ranks_from_scores(sc)
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
    return {"rho": rho, "top5": len(pred5 & true5) / 5,
            "top10": len(pred10 & true10) / 10, "top15": len(pred15 & true15) / 15}


def main():
    print("=" * 78)
    print("АУДИТ МАППИНГА vs МЕТОДОЛОГИЯ GALLUP")
    print("=" * 78)

    pairs, broken = load_mapping()
    gt = load_gt()
    print(f"[OK] {len(pairs)} валидных пар, {len(broken)} сломанных: {broken}\n")

    # ------------------------------------------------------------------
    # 1. Распределение: наше vs Gallup Table 1
    # ------------------------------------------------------------------
    our_counts = defaultdict(int)
    for p in pairs:
        our_counts[p["A"]] += 1
        our_counts[p["B"]] += 1

    print("=" * 78)
    print("1. РАСПРЕДЕЛЕНИЕ УТВЕРЖДЕНИЙ: наше vs Gallup (Table 1)")
    print("=" * 78)
    print(f"{'Theme':<22}{'Gallup':>8}{'Наше':>8}{'Δ':>7}   {'Gallup-тема':<20}")
    print("-" * 78)
    deviations = []
    for t in THEMES:
        g = GALLUP_ITEM_COUNTS[t]
        o = our_counts.get(t, 0)
        d = o - g
        deviations.append((abs(d), t, g, o, d))
        flag = ""
        if abs(d) > 3:
            flag = " ⚠️"
        print(f"{t:<22}{g:>8}{o:>8}{d:>+7}   {', '.join(x for x in [t] if t in DOMAINS):<20}{flag}")
    deviations.sort(reverse=True)
    print(f"\nВсего у нас: {sum(our_counts.values())} утверждений (в Gallup: {sum(GALLUP_ITEM_COUNTS.values())})")

    # ------------------------------------------------------------------
    # 2. Эмпирическая проверка тем
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("2. ЭМПИРИЧЕСКАЯ ПРОВЕРКА ТЕМ (корреляция ответов с реальным рангом)")
    print("=" * 78)
    print("Для каждой темы: по всем парам, где тема стоит на стороне A, берём")
    print("(подпись ответа) vs (обратный ранг темы в Gallup). Ожидаем +.")
    print()

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

    # Для каждой пары: список (signed_response, truth_score_of_that_side)
    # truth_score = 35 - rank (больше = лучше)
    theme_obs = defaultdict(list)  # theme -> [(signed, truth_score)]
    pair_obs = defaultdict(list)   # pair -> [(signed, truth_side_score)]

    for name, answers, g in matched:
        for p in pairs:
            q_idx = p["q"] - 1
            if q_idx >= len(answers) or answers[q_idx] is None:
                continue
            ans = answers[q_idx]
            signed = (3 - ans)  # >0 → выбрана левая (A)
            if signed == 0:
                continue
            truth_A = 35 - g.get(p["A"], 17)
            truth_B = 35 - g.get(p["B"], 17)
            # Если выбрана A: наблюдение для темы A = signed vs truth_A
            if signed > 0:
                theme_obs[p["A"]].append((signed, truth_A))
                theme_obs[p["B"]].append((-signed, truth_B))
            else:
                theme_obs[p["A"]].append((signed, truth_A))
                theme_obs[p["B"]].append((-signed, truth_B))
            pair_obs[p["q"]].append((signed, truth_A, truth_B))

    theme_corr = {}
    print(f"{'Theme':<22}{'n':>5}{'ρ(answers,rank)':>17}{'вердикт':>14}")
    print("-" * 62)
    for t in THEMES:
        obs = theme_obs.get(t, [])
        if len(obs) < 10:
            theme_corr[t] = 0.0
            continue
        x = [o[0] for o in obs]
        y = [o[1] for o in obs]
        rho, _ = spearmanr(x, y)
        theme_corr[t] = rho
        verdict = ""
        if rho < -0.10:
            verdict = "❌ ПЕРЕВЕРНУТА"
        elif rho < 0:
            verdict = "⚠️ отриц."
        elif rho > 0.15:
            verdict = "✅ ок"
        print(f"{t:<22}{len(obs):>5}{rho:>+17.3f}{verdict:>14}")

    # ------------------------------------------------------------------
    # 3. Пер-парная проверка (самые подозрительные пары)
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("3. САМЫЕ ПОДОЗРИТЕЛЬНЫЕ ПАРЫ (ρ < 0)")
    print("=" * 78)
    pair_corr = []
    for p in pairs:
        obs = pair_obs.get(p["q"], [])
        if len(obs) < 6:
            continue
        # signed response vs truth of the side that was chosen
        xs, ys = [], []
        for signed, tA, tB in obs:
            chosen_truth = tA if signed > 0 else tB
            xs.append(abs(signed))
            ys.append(chosen_truth)
        if len(set(xs)) < 2:
            continue
        rho, _ = spearmanr(xs, ys)
        pair_corr.append((rho, p))

    pair_corr.sort(key=lambda x: x[0])
    print(f"{'#':>4}{'ρ':>8}  {'Тема A':<20}{'Тема B':<20}")
    print("-" * 60)
    for rho, p in pair_corr[:15]:
        print(f"{p['q']:>4}{rho:>+8.3f}  {p['A']:<20}{p['B']:<20}")

    n_neg = sum(1 for rho, _ in pair_corr if rho < 0)
    print(f"\nПар с отрицательной корреляцией: {n_neg} из {len(pair_corr)} ({n_neg/len(pair_corr)*100:.0f}%)")
    print("Ожидаемо ~50% при случайном маппинге → значит маппинг в целом рабочий,")
    print("но часть пар действительно смэплена неверно.")

    # ------------------------------------------------------------------
    # 4. Пересчёт без подозрительных пар
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("4. ЭКСПЕРИМЕНТЫ: отключение подозрительных тем/пар")
    print("=" * 78)

    def run(pairs_subset, label):
        results = [evaluate(m[1], pairs_subset, m[2]) for m in matched]
        results = [r for r in results if r]
        if not results:
            print(f"  {label}: нет данных")
            return
        print(f"  {label:<52}ρ={np.mean([r['rho'] for r in results]):+.3f} "
              f"top5={np.mean([r['top5'] for r in results])*100:>3.0f}% "
              f"top10={np.mean([r['top10'] for r in results])*100:>3.0f}% "
              f"top15={np.mean([r['top15'] for r in results])*100:>3.0f}%")

    run(pairs, "baseline (все пары)")

    # Отключить пары с ρ < 0
    for thr in [-0.3, -0.2, -0.1, 0.0, 0.1]:
        subset = [p for rho, p in pair_corr if rho >= thr]
        # пары без данных оставляем
        have = {p["q"] for _, p in pair_corr}
        subset += [p for p in pairs if p["q"] not in have]
        run(subset, f"только пары с ρ >= {thr:+.1f} ({len(subset)} пар)")

    # Отключить темы с отрицательной корреляцией (их пары)
    neg_themes = {t for t in THEMES if theme_corr.get(t, 0) < -0.10}
    subset = [p for p in pairs if p["A"] not in neg_themes and p["B"] not in neg_themes]
    run(subset, f"без тем с ρ<-0.10 ({len(neg_themes)} тем: {sorted(neg_themes)})")

    # Перевзвесить темы по Gallup item counts (Table 1)
    print("\n  --- Перевзвешивание по Gallup Table 1 (item counts) ---")
    for alpha in [0.0, 0.3, 0.6, 1.0]:
        def score_w(answers, mapping, alpha=alpha):
            sc = defaultdict(float)
            for entry in mapping:
                q_idx = entry["q"] - 1
                if q_idx < 0 or q_idx >= len(answers):
                    continue
                ans = answers[q_idx]
                if ans is None:
                    continue
                v = (3 - ans)
                sc[entry["A"]] += v
                sc[entry["B"]] -= v
            for t in THEMES:
                sc.setdefault(t, 0.0)
            # нормируем по числу наших утверждений, потом домножаем на (1 + alpha*log(Gallup_count/our_count))
            our = defaultdict(int)
            for entry in mapping:
                our[entry["A"]] += 1
                our[entry["B"]] += 1
            out = {}
            for t in THEMES:
                base = sc[t] / max(1, our[t])
                ratio = GALLUP_ITEM_COUNTS[t] / max(1, our[t])
                out[t] = base * (1.0 + alpha * np.log(ratio))
            return out
        results = []
        for name, ans, g in matched:
            sc = score_w(ans, pairs)
            pred = ranks_from_scores(sc)
            common = sorted(set(pred) & set(g))
            p = [pred[t] for t in common]
            t = [g[t] for t in common]
            rho, _ = spearmanr(p, t)
            pred5 = set(x for x, r in pred.items() if r <= 5)
            true5 = set(x for x, r in g.items() if r <= 5)
            pred10 = set(x for x, r in pred.items() if r <= 10)
            true10 = set(x for x, r in g.items() if r <= 10)
            pred15 = set(x for x, r in pred.items() if r <= 15)
            true15 = set(x for x, r in g.items() if r <= 15)
            results.append({"rho": rho, "top5": len(pred5 & true5) / 5,
                            "top10": len(pred10 & true10) / 10, "top15": len(pred15 & true15) / 15})
        print(f"  alpha={alpha:<44}ρ={np.mean([r['rho'] for r in results]):+.3f} "
              f"top5={np.mean([r['top5'] for r in results])*100:>3.0f}% "
              f"top10={np.mean([r['top10'] for r in results])*100:>3.0f}% "
              f"top15={np.mean([r['top15'] for r in results])*100:>3.0f}%")


if __name__ == "__main__":
    main()
