"""
validate_revision.py
====================
Финальная валидация полной семантической ревизии:
  1. Paired bootstrap по людям — устойчиво ли различие с baseline?
  2. Per-theme корреляции
  3. Распределение vs Gallup Table 1
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
RNG = np.random.default_rng(20261107)

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


def per_person(answers, mapping, gt):
    r = ranks(new_score(answers, mapping))
    common = sorted(set(r) & set(gt))
    rho, _ = spearmanr([r[t] for t in common], [gt[t] for t in common])
    def ov(n):
        ps = set(x for x, rr in r.items() if rr <= n)
        ts = set(x for x, rr in gt.items() if rr <= n)
        return len(ps & ts)
    return {"rho": rho, "t5": ov(5), "t10": ov(10), "t15": ov(15)}


def main():
    print("=" * 78)
    print("ВАЛИДАЦИЯ ПОЛНОЙ СЕМАНТИЧЕСКОЙ РЕВИЗИИ")
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

    # Новая ревизия
    revised = []
    for p in pairs:
        a, b = p["A"], p["B"]
        if p["q"] in CORRECTIONS:
            a, b = CORRECTIONS[p["q"]]
        if a == b:
            b = "Focus" if a != "Focus" else "Adaptability"
        revised.append({**p, "A": a, "B": b})

    base_pp = [per_person(m[1], pairs, m[2]) for m in matched]
    rev_pp = [per_person(m[1], revised, m[2]) for m in matched]

    print(f"\n{'Имя':<14}{'baseline ρ':>12}{'rev ρ':>9}{'Δ':>8}   "
          f"{'base t10':>10}{'rev t10':>9}")
    print("-" * 70)
    for i, m in enumerate(matched):
        b, r = base_pp[i], rev_pp[i]
        print(f"{m[0]:<14}{b['rho']:>+12.3f}{r['rho']:>+9.3f}{r['rho']-b['rho']:>+8.3f}   "
              f"{b['t10']:>8}/10{r['t10']:>7}/10")

    b_rho = float(np.mean([r["rho"] for r in base_pp]))
    r_rho = float(np.mean([r["rho"] for r in rev_pp]))
    b_t5 = float(np.mean([r["t5"] for r in base_pp]))
    r_t5 = float(np.mean([r["t5"] for r in rev_pp]))
    b_t10 = float(np.mean([r["t10"] for r in base_pp]))
    r_t10 = float(np.mean([r["t10"] for r in rev_pp]))
    b_t15 = float(np.mean([r["t15"] for r in base_pp]))
    r_t15 = float(np.mean([r["t15"] for r in rev_pp]))

    print("-" * 70)
    print(f"{'СРЕДНЕЕ':<14}{b_rho:>+12.3f}{r_rho:>+9.3f}{r_rho-b_rho:>+8.3f}   "
          f"{b_t10:>8.1f}/10{r_t10:>7.1f}/10")

    # Paired bootstrap
    print("\n" + "=" * 78)
    print("PAIRED BOOTSTRAP (10000 итераций по людям)")
    print("=" * 78)
    n = len(matched)
    d_rho, d_t5, d_t10, d_t15 = [], [], [], []
    for _ in range(10000):
        idx = RNG.integers(0, n, n)
        b = [base_pp[i] for i in idx]
        r = [rev_pp[i] for i in idx]
        d_rho.append(np.mean([x["rho"] for x in r]) - np.mean([x["rho"] for x in b]))
        d_t5.append(np.mean([x["t5"] for x in r]) - np.mean([x["t5"] for x in b]))
        d_t10.append(np.mean([x["t10"] for x in r]) - np.mean([x["t10"] for x in b]))
        d_t15.append(np.mean([x["t15"] for x in r]) - np.mean([x["t15"] for x in b]))

    for name, d in [("Δρ", d_rho), ("Δtop5", d_t5), ("Δtop10", d_t10), ("Δtop15", d_t15)]:
        lo, hi = np.percentile(d, [2.5, 97.5])
        p_better = np.mean([x > 0 for x in d])
        verdict = "✅ значимо" if (lo > 0) else ("❌ хуже" if (hi < 0) else "⚠️ не значимо")
        print(f"  {name:<8} mean={np.mean(d):+.4f}  95% ДИ [{lo:+.4f}, {hi:+.4f}]  "
              f"P(лучше)={p_better*100:.1f}%  {verdict}")

    # Per-theme
    print("\n" + "=" * 78)
    print("КОРРЕЛЯЦИИ ПО ТЕМАМ (baseline → ревизия)")
    print("=" * 78)
    def theme_corr(mapping):
        obs = defaultdict(list)
        for _, ans, g in matched:
            for p in mapping:
                qi = p["q"] - 1
                if qi >= len(ans) or ans[qi] is None: continue
                s = 3 - ans[qi]
                if s == 0: continue
                obs[p["A"]].append((s, 35 - g.get(p["A"], 17)))
                obs[p["B"]].append((-s, 35 - g.get(p["B"], 17)))
        out = {}
        for t in THEMES:
            o = obs.get(t, [])
            out[t] = spearmanr([x[0] for x in o], [x[1] for x in o])[0] if len(o) >= 8 else 0.0
        return out
    cb, cr = theme_corr(pairs), theme_corr(revised)
    print(f"{'Theme':<22}{'base':>9}{'rev':>9}{'Δ':>9}")
    print("-" * 49)
    imp = 0
    for t in THEMES:
        d = cr.get(t, 0) - cb.get(t, 0)
        if d > 0.01: imp += 1
        print(f"{t:<22}{cb.get(t,0):>+9.3f}{cr.get(t,0):>+9.3f}{d:>+9.3f}"
              f"{' ✅' if d > 0.01 else (' ❌' if d < -0.01 else '')}")
    print(f"\nУлучшено: {imp}/34 | Ухудшено: {sum(1 for t in THEMES if cr.get(t,0)-cb.get(t,0) < -0.01)}/34")

    # Распределение
    def dist(mapping):
        c = defaultdict(int)
        for p in mapping:
            c[p["A"]] += 1; c[p["B"]] += 1
        return c
    db, dr = dist(pairs), dist(revised)
    dev_b = sum(abs(db.get(t, 0) - GALLUP_ITEM_COUNTS[t]) for t in THEMES)
    dev_r = sum(abs(dr.get(t, 0) - GALLUP_ITEM_COUNTS[t]) for t in THEMES)
    print(f"\nОтклонение распределения от Gallup Table 1: {dev_b} → {dev_r}")

    # Сохраняем
    out_map = [{k: p[k] for k in ("q", "A", "B", "A_text", "B_text")} for p in revised]
    with open(PROJECT / "mapping_revised_final.json", "w", encoding="utf-8") as f:
        json.dump({
            "variant": "full-semantic-revision",
            "corrections_applied": {str(k): v for k, v in CORRECTIONS.items()},
            "metrics": {"rho": r_rho, "top5": r_t5, "top10": r_t10, "top15": r_t15},
            "baseline_metrics": {"rho": b_rho, "top5": b_t5, "top10": b_t10, "top15": b_t15},
            "bootstrap_p_better": {
                "rho": float(np.mean([x > 0 for x in d_rho])),
                "top10": float(np.mean([x > 0 for x in d_t10])),
            },
            "pairs": out_map,
        }, f, indent=2, ensure_ascii=False)
    print("\n[OK] Сохранено: mapping_revised_final.json")


if __name__ == "__main__":
    main()
