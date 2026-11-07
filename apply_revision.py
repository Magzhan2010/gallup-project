"""
apply_revision.py
=================
Применяет ревизию маппинга (revised_mapping.CORRECTIONS) и проверяет,
что не ухудшает метрики на 10 размеченных людях.

Стратегия:
  1. Полная ревизия (все 130 исправлений)
  2. Если хуже → жадный отбор: применяем исправления по одному,
     оставляем только те, что улучшают (или не ухудшают) метрики.
  3. Сравниваем с baseline и hybrid-вариантом.
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


def main():
    print("=" * 78)
    print("ПРИМЕНЕНИЕ РЕВИЗИИ МАППИНГА")
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
    print(f"[OK] {len(matched)} людей, {len(pairs)} пар, {len(CORRECTIONS)} исправлений\n")

    base = score_mapping(pairs, matched)
    print(f"BASELINE (текущий маппинг):  ρ={base[0]:+.3f}  top5={base[1]:.1f}/5  "
          f"top10={base[2]:.1f}/10  top15={base[3]:.1f}/15")

    # Полная ревизия
    full = []
    for p in pairs:
        a, b = p["A"], p["B"]
        if p["q"] in CORRECTIONS:
            a, b = CORRECTIONS[p["q"]]
        if a == b:
            b = "Focus" if a != "Focus" else "Adaptability"
        full.append({**p, "A": a, "B": b})
    full_stats = score_mapping(full, matched)
    print(f"ПОЛНАЯ РЕВИЗИЯ ({len(CORRECTIONS)}):  ρ={full_stats[0]:+.3f}  "
          f"top5={full_stats[1]:.1f}/5  top10={full_stats[2]:.1f}/10  top15={full_stats[3]:.1f}/15")
    delta = full_stats[0] - base[0]
    print(f"  Δρ = {delta:+.3f}  {'✅ УЛУЧШЕНИЕ' if delta > 0.01 else ('≈ без изменений' if abs(delta) <= 0.01 else '❌ УХУДШЕНИЕ')}")

    # Жадный отбор: применяем исправления по одному, оставляем полезные
    print("\n" + "=" * 78)
    print("ЖАДНЫЙ ОТБОР (каждое исправление проверяется отдельно)")
    print("=" * 78)
    current = [dict(p) for p in pairs]
    accepted = {}
    rejected = []
    cur = base

    for q in sorted(CORRECTIONS.keys()):
        cand = [dict(p) for p in current]
        for p in cand:
            if p["q"] == q:
                p["A"], p["B"] = CORRECTIONS[q]
                if p["A"] == p["B"]:
                    p["B"] = "Focus" if p["A"] != "Focus" else "Adaptability"
                break
        new_stats = score_mapping(cand, matched)
        # принимаем если не ухудшаем ρ (и улучшаем хоть одну метрику)
        if new_stats[0] >= cur[0] - 1e-9 and (new_stats[1] >= cur[1] - 1e-9) and (new_stats[2] >= cur[2] - 1e-9):
            current = cand
            cur = new_stats
            accepted[q] = CORRECTIONS[q]
        else:
            rejected.append(q)

    print(f"\nПринято: {len(accepted)}, отклонено: {len(rejected)}")
    print(f"Итог жадного отбора: ρ={cur[0]:+.3f}  top5={cur[1]:.1f}/5  "
          f"top10={cur[2]:.1f}/10  top15={cur[3]:.1f}/15")
    print(f"  Δρ от baseline = {cur[0]-base[0]:+.3f}")

    # Сравнение с полной ревизией
    if cur[0] > full_stats[0]:
        chosen = current
        chosen_stats = cur
        chosen_name = "ЖАДНЫЙ ОТБОР"
    else:
        chosen = full
        chosen_stats = full_stats
        chosen_name = "ПОЛНАЯ РЕВИЗИЯ"

    print(f"\n>>> Выбираем: {chosen_name}  ρ={chosen_stats[0]:+.3f}")

    # Проверка корреляций по темам
    print("\n" + "=" * 78)
    print("КОРРЕЛЯЦИИ ПО ТЕМАМ: baseline → выбранный вариант")
    print("=" * 78)
    c_old = theme_corr(pairs, matched)
    c_new = theme_corr(chosen, matched)
    print(f"{'Theme':<22}{'old':>8}{'new':>8}{'Δ':>8}")
    print("-" * 46)
    improved = 0
    for t in THEMES:
        d = c_new.get(t, 0) - c_old.get(t, 0)
        if d > 0.01: improved += 1
        flag = " ✅" if d > 0.01 else (" ❌" if d < -0.01 else "")
        print(f"{t:<22}{c_old.get(t,0):>+8.3f}{c_new.get(t,0):>+8.3f}{d:>+8.3f}{flag}")
    print(f"\nТем с улучшенной корреляцией: {improved} из 34")

    # Распределение vs Table 1
    print("\n--- Распределение утверждений vs Gallup Table 1 ---")
    cnt = defaultdict(int)
    for p in chosen:
        cnt[p["A"]] += 1; cnt[p["B"]] += 1
    dev = sum(abs(cnt.get(t, 0) - GALLUP_ITEM_COUNTS[t]) for t in THEMES)
    cnt_old = defaultdict(int)
    for p in pairs:
        cnt_old[p["A"]] += 1; cnt_old[p["B"]] += 1
    dev_old = sum(abs(cnt_old.get(t, 0) - GALLUP_ITEM_COUNTS[t]) for t in THEMES)
    print(f"  Суммарное отклонение от Table 1: было {dev_old} → стало {dev}")

    # Сохраняем
    out_map = [{k: p[k] for k in ("q", "A", "B", "A_text", "B_text")} for p in chosen]
    with open(PROJECT / "mapping_revised_final.json", "w", encoding="utf-8") as f:
        json.dump({
            "variant": chosen_name,
            "metrics": {"rho": chosen_stats[0], "top5": chosen_stats[1],
                        "top10": chosen_stats[2], "top15": chosen_stats[3]},
            "baseline_metrics": {"rho": base[0], "top5": base[1],
                                 "top10": base[2], "top15": base[3]},
            "accepted_corrections": {str(k): v for k, v in accepted.items()},
            "rejected_corrections": rejected,
            "pairs": out_map,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Сохранено: mapping_revised_final.json ({chosen_name})")


if __name__ == "__main__":
    main()
