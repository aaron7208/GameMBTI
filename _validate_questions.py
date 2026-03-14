# -*- coding: utf-8 -*-
"""
题库检验与题组优化 - 合并自 _expectation_calc、_balance_advisor、_build_best_sets
用法: python _validate_questions.py          # 仅检验并输出报告
      python _validate_questions.py --update # 检验后计算最优题组并写回 questions.json
"""
import json
import math
import os
import random
import sys

DIR = os.path.dirname(__file__)
QUESTIONS_PATH = os.path.join(DIR, "questions.json")

TYPES = {
    "INTJ": {"Ni": 4, "Te": 3, "Fi": 2, "Se": 1}, "INTP": {"Ti": 4, "Ne": 3, "Si": 2, "Fe": 1},
    "ENTJ": {"Te": 4, "Ni": 3, "Se": 2, "Fi": 1}, "ENTP": {"Ne": 4, "Ti": 3, "Fe": 2, "Si": 1},
    "INFJ": {"Ni": 4, "Fe": 3, "Ti": 2, "Se": 1}, "INFP": {"Fi": 4, "Ne": 3, "Si": 2, "Te": 1},
    "ENFJ": {"Fe": 4, "Ni": 3, "Se": 2, "Ti": 1}, "ENFP": {"Ne": 4, "Fi": 3, "Te": 2, "Si": 1},
    "ISTJ": {"Si": 4, "Te": 3, "Fi": 2, "Ne": 1}, "ISFJ": {"Si": 4, "Fe": 3, "Ti": 2, "Ne": 1},
    "ESTJ": {"Te": 4, "Si": 3, "Ne": 2, "Fi": 1}, "ESFJ": {"Fe": 4, "Si": 3, "Ne": 2, "Ti": 1},
    "ISTP": {"Ti": 4, "Se": 3, "Ni": 2, "Fe": 1}, "ISFP": {"Fi": 4, "Se": 3, "Ni": 2, "Te": 1},
    "ESTP": {"Se": 4, "Ti": 3, "Fe": 2, "Ni": 1}, "ESFP": {"Se": 4, "Fi": 3, "Te": 2, "Ni": 1},
}
F = ["Te", "Ti", "Fe", "Fi", "Ne", "Ni", "Se", "Si"]
DOM_BONUS = 2
QUICK_COUNTS = [15, 16, 17, 18]
ACCU_COUNTS = [25, 26, 27, 28, 29, 30]


def load_questions():
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    arr = data.get("questions", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    return data, arr


def opts_from_q(q):
    return [opt.get("scoreImpact", {}) for opt in q.get("options", [])]


def align(imp, st):
    base = sum((st.get(k, 0) * v for k, v in imp.items()))
    dom = max(st, key=st.get)
    if imp.get(dom, 0) > 0:
        base += DOM_BONUS
    return base


def softmax(arr, t=2):
    e = [math.exp(x * t) for x in arr]
    return [x / sum(e) for x in e]


def to_dim(s):
    return {
        "e_i": (s["Te"] + s["Fe"] + s["Ne"] + s["Se"]) - (s["Ti"] + s["Fi"] + s["Ni"] + s["Si"]),
        "s_n": (s["Se"] + s["Si"]) - (s["Ne"] + s["Ni"]),
        "t_f": (s["Te"] + s["Ti"]) - (s["Fe"] + s["Fi"]),
        "j_p": (s["Te"] + s["Fe"] + s["Ti"] + s["Fi"]) - (s["Ne"] + s["Se"] + s["Ni"] + s["Si"]),
    }


def to_mbti(d):
    return ("E" if d["e_i"] > 0 else "I") + ("S" if d["s_n"] > 0 else "N") + ("T" if d["t_f"] > 0 else "F") + ("J" if d["j_p"] > 0 else "P")


def compute_weights(questions):
    cnt = {f: 0 for f in F}
    for q in questions:
        for imp in opts_from_q(q):
            for k, v in imp.items():
                if k in cnt:
                    cnt[k] += v
    mx = max(1, max(cnt.values()))
    return {f: mx / cnt[f] if cnt[f] > 0 else 1 for f in F}


def run_expectation(questions):
    weights = compute_weights(questions)
    results = []
    for tname, stack in TYPES.items():
        s = {f: 0.0 for f in F}
        for q in questions:
            opts = opts_from_q(q)
            a = [align(imp, stack) for imp in opts]
            p = softmax(a)
            for i, imp in enumerate(opts):
                for k, v in imp.items():
                    if k in s:
                        s[k] += p[i] * v * weights.get(k, 1)
        d = to_dim(s)
        m = to_mbti(d)
        results.append((tname, m, m == tname))
    return results


# ========== 1. 期望检验 ==========
def report_expectation(questions):
    print("\n" + "=" * 60)
    print(f"【1. 期望检验】全题库 {len(questions)} 题，稀缺性加权+主导功能加成")
    print("=" * 60)
    r = run_expectation(questions)
    correct = sum(1 for _, _, ok in r if ok)
    print(f"正确: {correct}/16")
    for tname, m, ok in r:
        match = "✓" if ok else f"-> {m}"
        print(f"  {tname}: {match}")


# ========== 2. 配平建议 ==========
def profile_str(opts):
    p = {f: 0 for f in F}
    for imp in opts:
        for k, v in imp.items():
            if k in p:
                p[k] += v
    return " ".join(f"{k}:{p[k]}" for k in F if p[k] > 0)


def report_balance(questions, titles):
    print("\n" + "=" * 60)
    print("【2. 配平建议】")
    print("=" * 60)
    opts_list = [opts_from_q(q) for q in questions]
    r0 = run_expectation(questions)
    correct0 = sum(1 for _, _, ok in r0 if ok)
    wrong = [(t, m) for t, m, ok in r0 if not ok]

    print(f"当前正确 {correct0}/16")
    for t, m in wrong:
        print(f"  误判: {t} -> {m}")

    # 功能频次
    cnt = {f: 0 for f in F}
    for opts in opts_list:
        for imp in opts:
            for k, v in imp.items():
                if k in cnt:
                    cnt[k] += v
    mx, mn = max(cnt.values()), min(cnt.values())
    print(f"\n功能频次: 最多={mx} 最少={mn}")
    under = [f for f in F if cnt[f] <= mn * 1.5]
    print(f"  稀缺: {', '.join(under)}")

    # 移除单题影响
    removal_effect = []
    for i in range(len(questions)):
        q_new = questions[:i] + questions[i + 1:]
        r = run_expectation(q_new)
        c = sum(1 for _, _, ok in r if ok)
        delta = c - correct0
        name = titles[i] if i < len(titles) else f"Q{i+1}"
        removal_effect.append((i, name, delta, c, profile_str(opts_list[i])))
    removal_effect.sort(key=lambda x: -x[2])
    print(f"\n移除单题影响 (前5):")
    for i, name, delta, c, pf in removal_effect[:5]:
        sign = "+" if delta >= 0 else ""
        print(f"  移除 {name}: {sign}{delta} -> {c}/16  [{pf}]")

    if wrong:
        print(f"\n误判维度缺口:")
        for t, m in wrong:
            need, got = list(t), list(m)
            diffs = [f"{['E/I','S/N','T/F','J/P'][j]}:需{need[j]}得{got[j]}" for j in range(4) if need[j] != got[j]]
            if diffs:
                print(f"  {t}->{m}: {', '.join(diffs)}")


# ========== 3. 最优题组计算 ==========
def find_best_ids_for_n(questions, ids, id_to_q, n, trials=400):
    best_correct, best_ids = 0, None
    for _ in range(trials):
        subset_ids = random.sample(ids, n)
        subset_q = [id_to_q[i] for i in subset_ids]
        correct = sum(1 for _, _, ok in run_expectation(subset_q) if ok)
        if correct > best_correct:
            best_correct, best_ids = correct, sorted(subset_ids)
    return best_ids, best_correct


def compute_best_sets(questions):
    ids = [q["id"] for q in questions]
    id_to_q = {q["id"]: q for q in questions}
    quick_sets, accu_sets = {}, {}

    print("\n【3. 最优题组】题量固定，计算各题组最优 ID 组合")
    print("极速版 15–18 题:")
    for n in QUICK_COUNTS:
        best_ids, correct = find_best_ids_for_n(questions, ids, id_to_q, n)
        quick_sets[str(n)] = best_ids
        print(f"  {n} 题: {correct}/16 ({correct/16*100:.1f}%)  ids={best_ids[:6]}...")

    print("深度版 25–30 题:")
    for n in ACCU_COUNTS:
        best_ids, correct = find_best_ids_for_n(questions, ids, id_to_q, n)
        accu_sets[str(n)] = best_ids
        print(f"  {n} 题: {correct}/16 ({correct/16*100:.1f}%)  ids={best_ids[:6]}...")

    return quick_sets, accu_sets


def write_config(data, quick_sets, accu_sets):
    data["config"] = data.get("config", {})
    data["config"]["quickSets"] = quick_sets
    data["config"]["accuSets"] = accu_sets
    data["config"]["quickCounts"] = QUICK_COUNTS
    data["config"]["accuCounts"] = ACCU_COUNTS
    with open(QUESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\n已写回 questions.json config.quickSets, config.accuSets")


def main():
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    do_update = "--update" in sys.argv

    data, questions = load_questions()
    if not questions:
        print("错误: questions.json 中无题目")
        return 1

    titles = [q.get("title", "").split(" (")[0].strip() for q in questions]

    print("=" * 60)
    print(f"题库检验 - {len(questions)} 题")
    print("=" * 60)

    report_expectation(questions)
    report_balance(questions, titles)
    quick_sets, accu_sets = compute_best_sets(questions)

    if do_update:
        write_config(data, quick_sets, accu_sets)
    else:
        print("\n(未写回。若需更新 config，请加 --update 参数)")

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
