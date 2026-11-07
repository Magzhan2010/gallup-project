"""
final_tune.py
=============
Финальная оптимизация на основе:
  • гибридного маппинга (старый + семантический фикс для сломанных тем)
  • психометрии Gallup (reliability weighting)
  • разных формул response value

Всё оценивается на 10 размеченных людях.
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
from gallup_psychometrics import (  # noqa: E402
    ALPHA_SAMPLE1, ALPHA_SAMPLE3, TEST_RETEST_M1,
    TEST_RETEST_M3, TEST_RETEST_M6, GALLUP_ITEM_COUNTS,
)

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
            stmt_num = int(str(row[0]).strip())
            pair_num = int(str(row[1]).strip())
        except (ValueError, TypeError):
            continue
        text = str(row[2] or "").strip()
        theme = normalize_theme(row[3])
        if not text or not theme:
            continue
        pair_stmts[pair_num].append({"num": stmt_num, "text": text, "theme": theme})
    pairs = []
    for pn in sorted(pair_stmts.keys()):
        stmts = sorted(pair_stmts[pn], key=lambda x: x["num"])
        if len(stmts) != 2:
            continue
        pairs.append({
            "q": pn, "A": stmts[0]["theme"], "B": stmts[1]["theme"],
            "A_text": stmts[0]["text"], "B_text": stmts[1]["text"],
        })
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


# ---------------------------------------------------------------------------
# Скоринг с настройками
# ---------------------------------------------------------------------------

def response_value(answer, formula, invert=True):
    if formula == "linear":
        v = answer - 3
    elif formula == "sigmoid":
        v = float(np.tanh((answer - 3) / 1.2))
    elif formula == "sigmoid_soft":
        v = float(np.tanh((answer - 3) / 2.0))
    elif formula == "guttman":
        v = {1: -2.0, 2: -1.0, 3: 0.0, 4: 1.0, 5: 2.0}[answer]
    elif formula == "step":
        v = {1: -2.0, 2: -0.5, 3: 0.0, 4: 0.5, 5: 2.0}[answer]
    elif formula == "weighted":
        v = {1: -1.0, 2: -0.7, 3: 0.0, 4: 0.7, 5: 1.0}[answer]
    else:
        v = answer - 3
    return -v if invert else v


def score(answers, mapping, formula="linear", invert=True,
          use_mean=False, ipsative=False, reliability=None,
          standardize=False, rel_mode="multiply"):
    vals = defaultdict(list)
    for e in mapping:
        qi = e["q"] - 1
        if qi < 0 or qi >= len(answers):
            continue
        ans = answers[qi]
        if ans is None:
            continue
        v = response_value(ans, formula, invert)
        if abs(v) < 1e-9:
            continue
        if v > 0:
            vals[e["A"]].append(v)
            if not ipsative:
                vals[e["B"]].append(-v)
        else:
            vals[e["B"]].append(-v)
            if not ipsative:
                vals[e["A"]].append(v)

    if use_mean:
        raw = {t: (float(np.mean(v)) if v else 0.0) for t, v in vals.items()}
    else:
        raw = {t: (float(np.sum(v)) if v else 0.0) for t, v in vals.items()}
    for t in THEMES:
        raw.setdefault(t, 0.0)
    sc = dict(raw)

    if standardize:
        arr = np.array([sc[t] for t in THEMES])
        m, s = arr.mean(), arr.std()
        if s > 1e-9:
            sc = {t: (sc[t] - m) / s for t in THEMES}

    if reliability and rel_mode == "multiply":
        for t in THEMES:
            sc[t] *= reliability.get(t, 0.65)
    elif reliability and rel_mode == "shrink":
        arr = np.array([sc[t] for t in THEMES])
        m = arr.mean()
        for t in THEMES:
            r = reliability.get(t, 0.65)
            sc[t] = m + (sc[t] - m) * r
    return sc


def ranks(sc):
    return {t: i + 1 for i, (t, _) in enumerate(sorted(sc.items(), key=lambda x: -x[1]))}


def evaluate(answers, mapping, gt, **kw):
    pred = ranks(score(answers, mapping, **kw))
    common = sorted(set(pred) & set(gt))
    if len(common) < 5:
        return None
    rho, _ = spearmanr([pred[t] for t in common], [gt[t] for t in common])
    def ov(n):
        p = set(x for x, r in pred.items() if r <= n)
        t = set(x for x, r in gt.items() if r <= n)
        return len(p & t) / n
    return {"rho": rho, "top5": ov(5), "top10": ov(10), "top15": ov(15)}


def theme_corr(mapping, matched):
    obs = defaultdict(list)
    for _, answers, g in matched:
        for p in mapping:
            qi = p["q"] - 1
            if qi >= len(answers) or answers[qi] is None:
                continue
            a = answers[qi]
            s = (3 - a)
            if s == 0:
                continue
            obs[p["A"]].append((s, 35 - g.get(p["A"], 17)))
            obs[p["B"]].append((-s, 35 - g.get(p["B"], 17)))
    out = {}
    for t in THEMES:
        o = obs.get(t, [])
        if len(o) < 8:
            out[t] = 0.0
            continue
        out[t] = spearmanr([x[0] for x in o], [x[1] for x in o])[0]
    return out


def main():
    print("=" * 78)
    print("ФИНАЛЬНАЯ ОПТИМИЗАЦИЯ")
    print("=" * 78)

    pairs = load_mapping()
    gt = load_gt()

    files = {}
    for f in ANSWERS_DIR.iterdir():
        if f.suffix.lower() == ".xlsx" and not f.stem.startswith(("Gallup_200", "Gallup_Talent")):
            files[f.stem] = f
    matched = []
    for stem, path in files.items():
        for g in gt:
            if g == stem or g.startswith(stem + "-") or g.startswith(stem):
                matched.append((stem, load_answers(path), gt[g]))
                break
    print(f"[OK] {len(matched)} людей, {len(pairs)} пар\n")

    # ---------------------------------------------------------------
    # 1. Загружаем семантический маппинг из rebuild_mapping.py
    # ---------------------------------------------------------------
    semantic_path = PROJECT / "mapping_rebuilt.json"
    sem_data = json.loads(semantic_path.read_text(encoding="utf-8"))
    sem_by_q = {m["q"]: m for m in sem_data}

    old_corr = theme_corr(pairs, matched)

    def build_hybrid(threshold, use_semantic_map):
        out = []
        for p in pairs:
            src = sem_by_q.get(p["q"]) if use_semantic_map else None
            a = p["A"]
            b = p["B"]
            if old_corr.get(a, 0) < threshold:
                a = src["A"] if src else a
            if old_corr.get(b, 0) < threshold:
                b = src["B"] if src else b
            if a == b:
                b = p["B"] if p["B"] != a else (src["B"] if src else b)
                if a == b:
                    b = "Adaptability"
            out.append({"q": p["q"], "A": a, "B": b,
                        "A_text": p["A_text"], "B_text": p["B_text"]})
        return out

    def report(mapping, label, **kw):
        res = [evaluate(m[1], mapping, m[2], **kw) for m in matched]
        res = [r for r in res if r]
        rho = np.mean([r["rho"] for r in res])
        t5 = np.mean([r["top5"] for r in res]) * 100
        t10 = np.mean([r["top10"] for r in res]) * 100
        t15 = np.mean([r["top15"] for r in res]) * 100
        print(f"  {label:<50}ρ={rho:+.3f} top5={t5:>3.0f}% top10={t10:>3.0f}% top15={t15:>3.0f}%")
        return rho, t5, t10, t15

    # ---------------------------------------------------------------
    # 2. Свип порога "слабой темы"
    # ---------------------------------------------------------------
    print("=" * 78)
    print("1. ПОРОГ ЗАМЕНЫ СЛАБЫХ ТЕМ (семантический маппинг)")
    print("=" * 78)
    best_thr, best_stats, best_map = None, None, None
    for thr in [-1.0, -0.15, -0.1, -0.05, 0.0, 0.05, 0.1, 0.15, 0.2]:
        m = build_hybrid(thr, True)
        r = report(m, f"порог ρ < {thr:+.2f}")
        if best_stats is None or r[0] > best_stats[0]:
            best_stats, best_thr, best_map = r, thr, m

    print(f"\n>>> Лучший порог: {best_thr:+.2f}  (ρ={best_stats[0]:+.3f})")

    # ---------------------------------------------------------------
    # 3. На лучшем маппинге — reliability weighting + формулы
    # ---------------------------------------------------------------
    print("\n" + "=" * 78)
    print("2. RELIABILITY WEIGHTING + ФОРМУЛЫ (на лучшем маппинге)")
    print("=" * 78)
    REL = {
        "none": None, "alpha1": ALPHA_SAMPLE1, "alpha3": ALPHA_SAMPLE3,
        "retest1": TEST_RETEST_M1, "retest3": TEST_RETEST_M3, "retest6": TEST_RETEST_M6,
    }
    results = []
    for rel_name, rel in REL.items():
        for mode in (["multiply", "shrink"] if rel else [None]):
            for formula in ["linear", "sigmoid", "sigmoid_soft", "guttman", "step", "weighted"]:
                for use_mean in [False, True]:
                    for ipsative in [False, True]:
                        for std in [False, True]:
                            kw = dict(formula=formula, use_mean=use_mean,
                                      ipsative=ipsative, reliability=rel,
                                      standardize=std, rel_mode=mode or "multiply")
                            res = [evaluate(m[1], best_map, m[2], **kw) for m in matched]
                            res = [r for r in res if r]
                            if not res:
                                continue
                            rho = float(np.mean([r["rho"] for r in res]))
                            t5 = float(np.mean([r["top5"] for r in res]) * 100)
                            t10 = float(np.mean([r["top10"] for r in res]) * 100)
                            t15 = float(np.mean([r["top15"] for r in res]) * 100)
                            results.append({
                                "rel": rel_name, "mode": mode, "formula": formula,
                                "mean": use_mean, "ips": ipsative, "std": std,
                                "rho": rho, "top5": t5, "top10": t10, "top15": t15,
                                "kw": kw,
                            })
    results.sort(key=lambda x: (-x["rho"], -x["top10"], -x["top15"]))
    print(f"{'rel':<9}{'mode':<9}{'formula':<13}{'mean':<6}{'ips':<5}{'std':<5}"
          f"{'ρ':>8}{'top5':>7}{'top10':>7}{'top15':>7}")
    print("-" * 78)
    for r in results[:18]:
        print(f"{r['rel']:<9}{str(r['mode']):<9}{r['formula']:<13}{str(r['mean']):<6}"
              f"{str(r['ips']):<5}{str(r['std']):<5}"
              f"{r['rho']:>+8.3f}{r['top5']:>6.0f}%{r['top10']:>6.0f}%{r['top15']:>6.0f}%")

    top = results[0]
    print(f"\n>>> ЛУЧШАЯ КОНФИГУРАЦИЯ:")
    print(f"    rel={top['rel']} mode={top['mode']} formula={top['formula']} "
          f"mean={top['mean']} ipsative={top['ips']} zscore={top['std']}")
    print(f"    ρ={top['rho']:+.3f}  top5={top['top5']:.0f}%  top10={top['top10']:.0f}%  top15={top['top15']:.0f}%")

    # Сравнение с продом
    prod_res = [evaluate(m[1], pairs, m[2]) for m in matched]
    prod_res = [r for r in prod_res if r]
    print(f"\n    Для сравнения — ПРОД (старый маппинг, linear, sum):")
    print(f"    ρ={np.mean([r['rho'] for r in prod_res]):+.3f}  "
          f"top5={np.mean([r['top5'] for r in prod_res])*100:.0f}%  "
          f"top10={np.mean([r['top10'] for r in prod_res])*100:.0f}%  "
          f"top15={np.mean([r['top15'] for r in prod_res])*100:.0f}%")

    # ---------------------------------------------------------------
    # 4. Сохраняем
    # ---------------------------------------------------------------
    with open(PROJECT / "best_mapping_final.json", "w", encoding="utf-8") as f:
        json.dump({
            "mapping": best_map,
            "threshold": best_thr,
            "scoring": {k: v for k, v in top["kw"].items() if k != "reliability"},
            "reliability": top["rel"],
            "reliability_mode": top["mode"],
            "metrics": {"rho": top["rho"], "top5": top["top5"],
                        "top10": top["top10"], "top15": top["top15"]},
        }, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Сохранено: best_mapping_final.json")


if __name__ == "__main__":
    main()
