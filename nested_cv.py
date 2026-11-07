"""
nested_cv.py
============
Честная проверка: для каждого из 10 людей ОТДЕЛЬНО выбираем исправления
на остальных 9, затем проверяем на отложенном.

Это покажет, реально ли жадный отбор обобщается или это переобучение.
"""
import json
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
from revised_mapping import CORRECTIONS  # noqa: E402
from gallup_psychometrics import GALLUP_ITEM_COUNTS  # noqa: E402

ANSWERS_DIR = Path(r"C:\Users\User\Downloads\Telegram Desktop")
DATASET_CSV = PROJECT / "my_dataset.csv"
MAPPING_XLSX = PROJECT / "Gallup_Talent_Mapping_Balanced.xlsx"
MISSING_RANK = 2000
THEMES = sorted(GALLUP_ITEM_COUNTS.keys())

RELIABILITY = {
    "Achiever": 0.68, "Activator": 0.64, "Adaptability": 0.66, "Analytical": 0.75,
    "Arranger": 0.53, "Belief": 0.70, "Command": 0.64, "Communication": 0.70,
    "Competition": 0.67, "Connectedness": 0.71, "Consistency": 0.65, "Context": 0.69,
    "Deliberative": 0.80, "Developer": 0.54, "Discipline": 0.76, "Empathy": 0.65,
    "Focus": 0.60, "Futuristic": 0.61, "Harmony": 0.61, "Ideation": 0.71,
    "Includer": 0.67, "Individualization": 0.58, "Input": 0.75, "Intellection": 0.76,
    "Learner": 0.78, "Maximizer": 0.48, "Positivity": 0.69, "Relator": 0.67,
    "Responsibility": 0.65, "Restorative": 0.51, "Self-Assurance": 0.72,
    "Significance": 0.65, "Strategic": 0.71, "Woo": 0.76,
}


def normalize_theme(name):
    if not name:
        return ""
    n = str(name).strip()
    if "-" in n:
        return "-".join(p.capitalize() for p in n.split("-"))
    return n


def load_pairs():
    wb = openpyxl.load_workbook(MAPPING_XLSX, read_only=True)
    ws = wb["400 строк - баланс 11-12"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    ps = defaultdict(list)
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        try:
            sn = int(str(row[0]).strip()); pn = int(str(row[1]).strip())
        except (ValueError, TypeError):
            continue
        text = str(row[2] or "").strip()
        th = normalize_theme(row[3])
        if not text or not th:
            continue
        ps[pn].append({"num": sn, "text": text, "theme": th})
    out = []
    for pn in sorted(ps):
        st = sorted(ps[pn], key=lambda x: x["num"])
        if len(st) != 2:
            continue
        out.append({"q": pn, "A": st[0]["theme"], "B": st[1]["theme"],
                    "A_text": st[0]["text"], "B_text": st[1]["text"]})
    return out


def load_answers(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    answers = [None] * 200
    ac = None
    for ci in range(len(rows[0])):
        cv = [r[ci] for r in rows[1:] if r[ci] is not None]
        nums = []
        for v in cv:
            try:
                n = int(str(v).strip())
                if 1 <= n <= 5: nums.append(n)
            except (ValueError, TypeError): pass
        if len(nums) >= 50: ac = ci; break
    for row in rows[1:]:
        if row[0] is None: continue
        try: q = int(str(row[0]).strip())
        except (ValueError, TypeError): continue
        if not (1 <= q <= 200): continue
        ans = row[ac]
        if ans is None: continue
        try:
            n = int(str(ans).strip())
            if 1 <= n <= 5: answers[q - 1] = n
        except (ValueError, TypeError): continue
    return answers


def load_gt():
    df = pd.read_csv(DATASET_CSV, encoding="utf-8")
    out = {}
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        if name.endswith(".pdf"): name = name[:-4]
        ranks = {}
        for theme in df.columns:
            if theme == "name": continue
            r = row[theme]
            if pd.notna(r) and int(r) != MISSING_RANK:
                ranks[normalize_theme(theme)] = int(r)
        out[name] = ranks
    return out


def new_score(answers, mapping):
    vals = defaultdict(list)
    for e in mapping:
        qi = e["q"] - 1
        if qi < 0 or qi >= len(answers): continue
        a = answers[qi]
        if a is None: continue
        v = -float(np.tanh((a - 3) / 2.0))
        if abs(v) < 1e-9: continue
        if v > 0:
            vals[e["A"]].append(v); vals[e["B"]].append(-v)
        else:
            vals[e["B"]].append(-v); vals[e["A"]].append(v)
    sc = {}
    for t in THEMES:
        arr = vals.get(t, [])
        sc[t] = (sum(arr) / len(arr)) if arr else 0.0
    for t in THEMES:
        sc[t] *= RELIABILITY.get(t, 0.65)
    return sc


def ranks(sc):
    return {t: i + 1 for i, (t, _) in enumerate(sorted(sc.items(), key=lambda x: -x[1]))}


def evaluate(answers, mapping, gt):
    r = ranks(new_score(answers, mapping))
    common = sorted(set(r) & set(gt))
    rho, _ = spearmanr([r[t] for t in common], [gt[t] for t in common])
    def ov(n):
        ps = set(x for x, rr in r.items() if rr <= n)
        ts = set(x for x, rr in gt.items() if rr <= n)
        return len(ps & ts)
    return {"rho": rho, "t5": ov(5), "t10": ov(10), "t15": ov(15)}


def score_mapping(mapping, matched):
    res = [evaluate(m[1], mapping, m[2]) for m in matched]
    res = [r for r in res if r]
    return (float(np.mean([r["rho"] for r in res])),
            float(np.mean([r["t5"] for r in res])),
            float(np.mean([r["t10"] for r in res])),
            float(np.mean([r["t15"] for r in res])))


def apply_corr(current, q, corr):
    out = [dict(p) for p in current]
    for p in out:
        if p["q"] == q:
            p["A"], p["B"] = corr
            if p["A"] == p["B"]:
                p["B"] = "Focus" if p["A"] != "Focus" else "Adaptability"
            break
    return out


def greedy(pairs, train, corr_dict):
    """Жадный отбор на обучающей выборке."""
    current = [dict(p) for p in pairs]
    cur = score_mapping(current, train)
    accepted = {}
    for q in sorted(corr_dict.keys()):
        cand = apply_corr(current, q, corr_dict[q])
        new = score_mapping(cand, train)
        if new[0] >= cur[0] - 1e-9 and new[1] >= cur[1] - 1e-9 and new[2] >= cur[2] - 1e-9:
            current = cand
            cur = new
            accepted[q] = corr_dict[q]
    return current, accepted


def main():
    print("=" * 78)
    print("NESTED CROSS-VALIDATION: обобщается ли жадный отбор?")
    print("=" * 78)

    pairs = load_pairs()
    gt = load_gt()
    files = {}
    for f in ANSWERS_DIR.iterdir():
        if f.suffix.lower() == ".xlsx" and not f.stem.startswith(("Gallup_200", "Gallup_Talent")):
            files[f.stem] = f
    matched = []
    for stem, path in sorted(files.items()):
        for g in gt:
            if g == stem or g.startswith(stem + "-") or g.startswith(stem):
                matched.append((stem, load_answers(path), gt[g]))
                break
    print(f"[OK] {len(matched)} людей\n")

    print(f"{'Fold':<14}{'baseline':>26}{'greedy(train=9)':>26}")
    print(f"{'':14}{'ρ / top5 / top10':>26}{'ρ / top5 / top10':>26}")
    print("-" * 68)

    base_holdout, greedy_holdout = [], []
    n_accepted = []

    for i in range(len(matched)):
        test = [matched[i]]
        train = matched[:i] + matched[i+1:]

        # baseline на отложенном
        r_base = evaluate(test[0][1], pairs, test[0][2])

        # greedy на train (9 человек), тест на отложенном
        gmap, acc = greedy(pairs, train, CORRECTIONS)
        r_greedy = evaluate(test[0][1], gmap, test[0][2])
        n_accepted.append(len(acc))

        base_holdout.append(r_base)
        greedy_holdout.append(r_greedy)

        print(f"{test[0][0]:<14}"
              f"{r_base['rho']:>+9.3f} {r_base['t5']:>3}/5 {r_base['t10']:>3}/10"
              f"   {r_greedy['rho']:>+9.3f} {r_greedy['t5']:>3}/5 {r_greedy['t10']:>3}/10"
              f"   (acc {len(acc)})")

    print("-" * 68)
    b_rho = float(np.mean([r["rho"] for r in base_holdout]))
    g_rho = float(np.mean([r["rho"] for r in greedy_holdout]))
    b_t5 = float(np.mean([r["t5"] for r in base_holdout]))
    g_t5 = float(np.mean([r["t5"] for r in greedy_holdout]))
    b_t10 = float(np.mean([r["t10"] for r in base_holdout]))
    g_t10 = float(np.mean([r["t10"] for r in greedy_holdout]))
    b_t15 = float(np.mean([r["t15"] for r in base_holdout]))
    g_t15 = float(np.mean([r["t15"] for r in greedy_holdout]))

    print(f"{'СРЕДНЕЕ (LOO)':<14}"
          f"{b_rho:>+9.3f} {b_t5:>3.0f}/5 {b_t10:>3.0f}/10   "
          f"{g_rho:>+9.3f} {g_t5:>3.0f}/5 {g_t10:>3.0f}/10")
    print()
    print(f"Baseline (hold-out):  ρ={b_rho:+.3f}  top5={b_t5:.1f}/5  top10={b_t10:.1f}/10  top15={b_t15:.1f}/15")
    print(f"Greedy (hold-out):    ρ={g_rho:+.3f}  top5={g_t5:.1f}/5  top10={g_t10:.1f}/10  top15={g_t15:.1f}/15")
    print(f"Δρ = {g_rho - b_rho:+.3f}")
    print(f"Среднее число принятых исправлений: {np.mean(n_accepted):.0f} из {len(CORRECTIONS)}")
    print()
    if g_rho > b_rho + 0.01:
        print("✅ Greedy ОБОБЩАЕТСЯ — реальное улучшение, не переобучение.")
    else:
        print("⚠️ Greedy НЕ обобщается на отложенных — эффект был переобучением.")
        print("   → В этом случае используем ПОЛНУЮ СЕМАНТИЧЕСКУЮ ревизию (без подгонки).")


if __name__ == "__main__":
    main()
