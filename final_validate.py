"""Финальная проверка: broken-пары + bootstrap значимости."""
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
from gallup_psychometrics import GALLUP_ITEM_COUNTS  # noqa: E402

ANSWERS_DIR = Path(r"C:\Users\User\Downloads\Telegram Desktop")
DATASET_CSV = PROJECT / "my_dataset.csv"
MAPPING_XLSX = PROJECT / "Gallup_Talent_Mapping_Balanced.xlsx"
MISSING_RANK = 2000
THEMES = sorted(GALLUP_ITEM_COUNTS.keys())
RNG = np.random.default_rng(11)

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
    pairs = load_pairs()
    prod_data = json.loads((PROJECT / "best_mapping_final.json").read_text(encoding="utf-8"))
    prod = prod_data["mapping"]

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

    print("=" * 78)
    print("ПРОВЕРКА BROKEN-ПАР (обе стороны = одна тема)")
    print("=" * 78)
    pp = {p["q"]: p for p in prod}
    for q in [17, 29, 47, 104, 105, 153, 176, 178, 189, 198]:
        p = pp[q]
        fixed = "✅" if p["A"] != p["B"] else "❌"
        print(f"  #{q:>3} {fixed} {p['A']:<20} / {p['B']}")

    base_pp = [per_person(m[1], pairs, m[2]) for m in matched]
    prod_pp = [per_person(m[1], prod, m[2]) for m in matched]
    n = len(matched)

    print("\n" + "=" * 78)
    print("PER-PERSON")
    print("=" * 78)
    print(f"{'Имя':<14}{'base ρ':>10}{'prod ρ':>10}{'Δ':>8}{'base t5':>9}{'prod t5':>9}"
          f"{'base t10':>10}{'prod t10':>10}")
    print("-" * 80)
    for i, m in enumerate(matched):
        b, p_ = base_pp[i], prod_pp[i]
        print(f"{m[0]:<14}{b['rho']:>+10.3f}{p_['rho']:>+10.3f}{p_['rho']-b['rho']:>+8.3f}"
              f"{b['t5']:>7}/5{p_['t5']:>7}/5{b['t10']:>8}/10{p_['t10']:>8}/10")

    print("\n" + "=" * 78)
    print("PAIRED BOOTSTRAP (10000 итераций)")
    print("=" * 78)
    for key, label in [("rho", "Δρ"), ("t5", "Δtop5"), ("t10", "Δtop10"), ("t15", "Δtop15")]:
        d = []
        for _ in range(10000):
            idx = RNG.integers(0, n, n)
            d.append(np.mean([prod_pp[i][key] for i in idx]) - np.mean([base_pp[i][key] for i in idx]))
        lo, hi = np.percentile(d, [2.5, 97.5])
        p = np.mean([x > 0 for x in d])
        v = "✅ значимо" if lo > 0 else ("❌ хуже" if hi < 0 else "⚠️ не значимо")
        print(f"  {label:<9} mean={np.mean(d):+.4f}  95% ДИ [{lo:+.3f}, {hi:+.3f}]  "
              f"P(лучше)={p*100:5.1f}%  {v}")

    b = {k: float(np.mean([r[k] for r in base_pp])) for k in ("rho", "t5", "t10", "t15")}
    p_ = {k: float(np.mean([r[k] for r in prod_pp])) for k in ("rho", "t5", "t10", "t15")}
    print("\n" + "=" * 78)
    print("ИТОГ")
    print("=" * 78)
    print(f"  baseline:  ρ={b['rho']:+.3f}  top5={b['t5']:.1f}/5  top10={b['t10']:.1f}/10  top15={b['t15']:.1f}/15")
    print(f"  production: ρ={p_['rho']:+.3f}  top5={p_['t5']:.1f}/5  top10={p_['t10']:.1f}/10  top15={p_['t15']:.1f}/15")


if __name__ == "__main__":
    main()
