"""
final_choice.py
===============
Финальный выбор варианта: пороги -0.05, 0.10, 0.25 vs baseline.
Bootstrap по ВСЕМ метрикам + per-theme + распределение.
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
RNG = np.random.default_rng(7)

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


def theme_corr(mapping, matched):
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


def build_hybrid(pairs, weak):
    out = []
    for p in pairs:
        a, b = p["A"], p["B"]
        if p["q"] in CORRECTIONS:
            ca, cb = CORRECTIONS[p["q"]]
            if a in weak: a = ca
            if b in weak: b = cb
        if a == b:
            b = "Focus" if a != "Focus" else "Adaptability"
        out.append({**p, "A": a, "B": b})
    return out


def main():
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

    base_corr = theme_corr(pairs, matched)
    base_pp = [per_person(m[1], pairs, m[2]) for m in matched]
    n = len(matched)

    print("=" * 96)
    print("ФИНАЛЬНОЕ СРАВНЕНИЕ ВАРИАНТОВ (bootstrap 5000 итераций по людям)")
    print("=" * 96)
    print(f"{'вариант':<18}{'ρ':>8}{'Δρ CI':>20}{'P(ρ)':>8}"
          f"{'top5':>10}{'top10':>10}{'top15':>10}{'Δt15 CI':>18}")
    print("-" * 96)

    candidates = {"BASELINE": pairs}
    for thr in [-0.05, 0.10, 0.25]:
        weak = {t for t in THEMES if base_corr.get(t, 0) < thr}
        candidates[f"hybrid thr={thr:+.2f}"] = build_hybrid(pairs, weak)

    weak_sets = {}
    for thr in [-0.05, 0.10, 0.25]:
        weak_sets[thr] = {t for t in THEMES if base_corr.get(t, 0) < thr}

    best_variant = None
    best_score = None
    for name, mp in candidates.items():
        pp = [per_person(m[1], mp, m[2]) for m in matched]
        rho = float(np.mean([r["rho"] for r in pp]))
        t5 = float(np.mean([r["t5"] for r in pp]))
        t10 = float(np.mean([r["t10"] for r in pp]))
        t15 = float(np.mean([r["t15"] for r in pp]))
        d_rho, d_t15, d_t5 = [], [], []
        for _ in range(5000):
            idx = RNG.integers(0, n, n)
            d_rho.append(np.mean([pp[i]["rho"] for i in idx]) - np.mean([base_pp[i]["rho"] for i in idx]))
            d_t15.append(np.mean([pp[i]["t15"] for i in idx]) - np.mean([base_pp[i]["t15"] for i in idx]))
            d_t5.append(np.mean([pp[i]["t5"] for i in idx]) - np.mean([base_pp[i]["t5"] for i in idx]))
        lo_r, hi_r = np.percentile(d_rho, [2.5, 97.5])
        lo_15, hi_15 = np.percentile(d_t15, [2.5, 97.5])
        p_rho = float(np.mean([x > 0 for x in d_rho]))
        print(f"{name:<18}{rho:>+8.3f}   [{lo_r:+.3f},{hi_r:+.3f}]{p_rho*100:>7.1f}%"
              f"{t5:>8.1f}/5{t10:>8.1f}/10{t15:>8.1f}/15   [{lo_15:+.2f},{hi_15:+.2f}]")

        # Критерий выбора: ρ лучше baseline (P>=0.9) И top-5 не хуже И top-15 лучше
        if p_rho >= 0.90 and t5 >= float(np.mean([r["t5"] for r in base_pp])) - 0.001 \
                and t15 > float(np.mean([r["t15"] for r in base_pp])):
            score = (rho, t15)
            if best_score is None or score > best_score:
                best_score = score
                best_variant = (name, mp, rho, t5, t10, t15, weak_sets)

    print()
    if best_variant:
        name, mp, rho, t5, t10, t15, weak = best_variant
        print(f">>> ВЫБРАН: {name}")
        print(f"    ρ={rho:+.3f}  top5={t5:.1f}/5  top10={t10:.1f}/10  top15={t15:.1f}/15")
        print(f"    Заменено тем: {len(weak)}")
    else:
        name = "BASELINE"
        mp = pairs
        print(">>> Ни один гибрид не удовлетворяет критериям → оставляем BASELINE")

    # per-theme итог
    cb = theme_corr(pairs, matched)
    cn = theme_corr(mp, matched)
    imp = sum(1 for t in THEMES if cn.get(t, 0) - cb.get(t, 0) > 0.01)
    wor = sum(1 for t in THEMES if cn.get(t, 0) - cb.get(t, 0) < -0.01)
    print(f"\n    Корреляции тем: улучшено {imp}/34, ухудшено {wor}/34")

    # распределение
    def dist(mp2):
        c = defaultdict(int)
        for p in mp2:
            c[p["A"]] += 1; c[p["B"]] += 1
        return c
    db, dn = dist(pairs), dist(mp)
    dev_b = sum(abs(db.get(t, 0) - GALLUP_ITEM_COUNTS[t]) for t in THEMES)
    dev_n = sum(abs(dn.get(t, 0) - GALLUP_ITEM_COUNTS[t]) for t in THEMES)
    print(f"    Отклонение распределения от Table 1: {dev_b} → {dev_n}")

    # сохраняем
    out_map = [{k: p[k] for k in ("q", "A", "B", "A_text", "B_text")} for p in mp]
    with open(PROJECT / "mapping_revised_final.json", "w", encoding="utf-8") as f:
        json.dump({
            "variant": name,
            "weak_themes": sorted(weak) if weak else [],
            "metrics": {"rho": rho, "top5": t5, "top10": t10, "top15": t15},
            "pairs": out_map,
        }, f, indent=2, ensure_ascii=False)
    print("\n[OK] Сохранено: mapping_revised_final.json")


if __name__ == "__main__":
    main()
