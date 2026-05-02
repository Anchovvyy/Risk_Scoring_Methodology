"""
visual analytics 
"""

from __future__ import annotations

import glob
import json
import os
from collections import Counter
from typing import Any, Dict, List, Tuple
from pathlib import Path
from final_risk_assessment import calculate_final_risk


BASE_DIR = Path(__file__).parent.absolute()
ANALYTICS_DIR = Path(os.path.join(BASE_DIR, "analytics"))
ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR =  Path(os.path.join(BASE_DIR, "generated_resumes"))


# Same five-level scale as in methodology (very_* included for both base and final).
LIKELIHOOD_ORDER = ("very_low", "low", "moderate", "high", "very_high")

RISK_LEVEL_LABEL_RU = {
    "very_low": "Очень низкий",
    "low": "Низкий",
    "moderate": "Умеренный",
    "high": "Высокий",
    "very_high": "Очень высокий",
}

LEVEL_COLORS = {
    "very_low": "#27ae60",
    "low": "#2ecc71",
    "moderate": "#f1c40f",
    "high": "#e67e22",
    "very_high": "#c0392b",
}


def _level_index(level: str) -> int:
    return LIKELIHOOD_ORDER.index(level)


def _build_transition_report(
    transitions: Counter[Tuple[str, str]],
    order: Tuple[str, ...] = LIKELIHOOD_ORDER,
) -> Dict[str, Any]:
    matrix = {
        src: {dst: int(transitions.get((src, dst), 0)) for dst in order}
        for src in order
    }
    nonzero = [
        {"from": src, "to": dst, "count": int(cnt)}
        for (src, dst), cnt in sorted(transitions.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))
        if cnt > 0
    ]
    increased = 0
    decreased = 0
    unchanged = 0
    for (src, dst), cnt in transitions.items():
        if src not in order or dst not in order:
            continue
        if _level_index(dst) > _level_index(src):
            increased += int(cnt)
        elif _level_index(dst) < _level_index(src):
            decreased += int(cnt)
        else:
            unchanged += int(cnt)
    return {
        "matrix": matrix,
        "nonzero_transitions": nonzero,
        "summary": {
            "increased": increased,
            "decreased": decreased,
            "unchanged": unchanged,
        },
    }


def load_resumes(path: str = OUT_DIR) -> List[Dict[str, Any]]:
    files = sorted(glob.glob(os.path.join(path, "*.json")))
    resumes = []
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as file:
            resumes.append(json.load(file))
    return resumes


def build_stats(resumes: List[Dict[str, Any]]) -> Dict[str, Any]:
    final_risk: Counter[str] = Counter()
    base_risk: Counter[str] = Counter()
    impact: Counter[str] = Counter()
    l_base: Counter[str] = Counter()
    l_adjusted: Counter[str] = Counter()
    vulnerability: Counter[str] = Counter()
    category_means: Dict[str, List[float]] = {}
    risk_transitions: Counter[Tuple[str, str]] = Counter()
    likelihood_transitions: Counter[Tuple[str, str]] = Counter()

    for resume in resumes:
        risk = resume.get("risk_calculations", {})
        final_risk_level = risk.get("final_risk_assessment", {}).get("final_risk_level", "unknown")
        impact_level = risk.get("impact_assessment", {}).get("impact_level", "unknown")
        l_base_level = risk.get("l_base_level", "unknown")
        l_adj_level = risk.get("likelihood_adjustment", {}).get("l_adj_level", "unknown")

        final_risk[final_risk_level] += 1
        impact[impact_level] += 1
        l_base[l_base_level] += 1
        l_adjusted[l_adj_level] += 1
        vulnerability[risk.get("stage3_personal_vulnerability", {}).get("vulnerability_level", "unknown")] += 1

        if l_base_level in LIKELIHOOD_ORDER and impact_level in LIKELIHOOD_ORDER:
            base_risk_result = calculate_final_risk(l_base_level, impact_level)
            base_risk_level = str(base_risk_result.get("final_risk_level", "unknown"))
            base_risk[base_risk_level] += 1
            if final_risk_level in LIKELIHOOD_ORDER:
                risk_transitions[(base_risk_level, final_risk_level)] += 1
        else:
            base_risk["unknown"] += 1

        if l_base_level in LIKELIHOOD_ORDER and l_adj_level in LIKELIHOOD_ORDER:
            likelihood_transitions[(l_base_level, l_adj_level)] += 1

        osint = risk.get("osint_features", {})
        for category, value in osint.items():
            category_means.setdefault(category, []).append(float(value))

    avg_by_category = {
        category: round(sum(values) / len(values), 4) if values else 0.0
        for category, values in category_means.items()
    }
    l_base_ordered = {level: int(l_base.get(level, 0)) for level in LIKELIHOOD_ORDER}
    l_adjusted_ordered = {level: int(l_adjusted.get(level, 0)) for level in LIKELIHOOD_ORDER}
    base_risk_ordered = {level: int(base_risk.get(level, 0)) for level in LIKELIHOOD_ORDER}
    final_ordered = {level: int(final_risk.get(level, 0)) for level in LIKELIHOOD_ORDER}
    risk_transition_report = _build_transition_report(risk_transitions)
    likelihood_transition_report = _build_transition_report(likelihood_transitions)
    return {
        "sample_size": len(resumes),
        "final_risk_distribution": dict(final_risk),
        "base_risk_distribution": dict(base_risk),
        "impact_distribution": dict(impact),
        "l_base_distribution": dict(l_base),
        "l_adjusted_distribution": dict(l_adjusted),
        "l_base_counts_ordered": l_base_ordered,
        "l_adjusted_counts_ordered": l_adjusted_ordered,
        "base_risk_counts_ordered": base_risk_ordered,
        "final_risk_counts_ordered": final_ordered,
        "risk_transition_report": risk_transition_report,
        "likelihood_transition_report": likelihood_transition_report,
        "vulnerability_distribution": dict(vulnerability),
        "avg_osint_by_category": avg_by_category,
    }


def _ordered_likelihood_slices(
    distribution: Dict[str, int],
    order: Tuple[str, ...] = LIKELIHOOD_ORDER,
) -> Tuple[List[str], List[int], List[str]]:
    """Labels (RU), counts, colors for known five-level keys only."""
    labels: List[str] = []
    sizes: List[int] = []
    colors: List[str] = []
    for key in order:
        count = int(distribution.get(key, 0))
        if count <= 0:
            continue
        ru = RISK_LEVEL_LABEL_RU.get(key, key)
        labels.append(f"{ru}\n({key})")
        sizes.append(count)
        colors.append(LEVEL_COLORS.get(key, "#95a5a6"))
    return labels, sizes, colors


def _pie_from_distribution(
    ax: Any,
    distribution: Dict[str, int],
    title: str,
    order: Tuple[str, ...] = LIKELIHOOD_ORDER,
) -> None:
    labels, sizes, colors = _ordered_likelihood_slices(distribution, order=order)
    if not sizes:
        ax.set_title(title)
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
        ax.axis("off")
        return
    total = sum(sizes)

    def autopct(pct: float, total_count: int = total) -> str:
        count = int(round(pct / 100.0 * total_count))
        return f"{pct:.1f}%\n(n={count})"

    ax.pie(
        sizes,
        labels=labels,
        autopct=autopct,
        colors=colors,
        startangle=90,
        counterclock=False,
    )
    ax.set_title(title)


def _pie_generic(ax: Any, data: Dict[str, float], title: str) -> None:
    """Pie for arbitrary string keys (impact, vulnerability, OSINT means)."""
    if not data:
        ax.set_title(title)
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
        ax.axis("off")
        return
    labels = list(data.keys())
    values = [float(v) for v in data.values()]
    total = sum(values)
    if total <= 0:
        ax.set_title(title)
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
        ax.axis("off")
        return
    ax.pie(
        values,
        labels=labels,
        autopct=lambda pct: f"{pct:.1f}%",
        startangle=90,
    )
    ax.set_title(title)


def save_stats_json(stats: Dict[str, Any], target_dir: str = ANALYTICS_DIR) -> str:
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, "stats_summary.json")
    with open(path, "w", encoding="utf-8") as file:
        json.dump(stats, file, ensure_ascii=False, indent=2)
    return path


def save_plots(stats: Dict[str, Any], target_dir: str = ANALYTICS_DIR) -> List[str]:
    os.makedirs(target_dir, exist_ok=True)
    saved: List[str] = []
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return saved

    # 1) Final risk (five levels) — pie
    fr = stats.get("final_risk_distribution", {})
    plt.figure(figsize=(7, 7))
    ax = plt.gca()
    dist_final = {k: int(fr.get(k, 0)) for k in LIKELIHOOD_ORDER}
    _pie_from_distribution(ax, dist_final, "Итоговый риск (после методики)")
    plt.tight_layout()
    p1 = os.path.join(target_dir, "final_risk_distribution.png")
    plt.savefig(p1, dpi=120)
    plt.close()
    saved.append(p1)

    # 2) Base risk by matrix: Risk(L_base, Impact) — pie
    br = stats.get("base_risk_distribution", {})
    plt.figure(figsize=(7, 7))
    ax = plt.gca()
    dist_base_risk = {k: int(br.get(k, 0)) for k in LIKELIHOOD_ORDER}
    _pie_from_distribution(ax, dist_base_risk, "Базовый риск (по матрице: L_base × Impact)")
    plt.tight_layout()
    p2 = os.path.join(target_dir, "base_risk_distribution.png")
    plt.savefig(p2, dpi=120)
    plt.close()
    saved.append(p2)

    # 3) Base L_base probability — pie
    lb = stats.get("l_base_distribution", {})
    plt.figure(figsize=(7, 7))
    ax = plt.gca()
    dist_base = {k: int(lb.get(k, 0)) for k in LIKELIHOOD_ORDER}
    _pie_from_distribution(ax, dist_base, "Базовая вероятность (L_base)")
    plt.tight_layout()
    p3 = os.path.join(target_dir, "l_base_probability_distribution.png")
    plt.savefig(p3, dpi=120)
    plt.close()
    saved.append(p3)

    # 4) Side-by-side comparison base risk vs final risk
    plt.figure(figsize=(12, 6))
    ax_left = plt.subplot(1, 2, 1)
    _pie_from_distribution(ax_left, dist_base_risk, "Базовый риск (до корректировки вероятности)")
    ax_right = plt.subplot(1, 2, 2)
    _pie_from_distribution(ax_right, dist_final, "Итоговый уровень риска")
    plt.suptitle("Сравнение риска: base risk vs final risk")
    plt.tight_layout(rect=(0, 0.08, 1, 1))
    base_line = ", ".join(f"{k}={dist_base_risk.get(k, 0)}" for k in LIKELIHOOD_ORDER)
    final_line = ", ".join(f"{k}={dist_final.get(k, 0)}" for k in LIKELIHOOD_ORDER)
    plt.figtext(
        0.5,
        0.02,
        f"Base risk (счётчики): {base_line}\n"
        f"Final risk (счётчики): {final_line}\n"
        f"(Уровни very_low / very_high учитываются; нулевые доли на круге не рисуются.)",
        ha="center",
        fontsize=8,
    )
    p4 = os.path.join(target_dir, "risk_base_vs_final_comparison.png")
    plt.savefig(p4, dpi=120)
    plt.close()
    saved.append(p4)

    # 5) L_base vs L_adj comparison (probability growth awareness)
    la = stats.get("l_adjusted_distribution", {})
    dist_adjusted = {k: int(la.get(k, 0)) for k in LIKELIHOOD_ORDER}
    plt.figure(figsize=(12, 6))
    ax_left = plt.subplot(1, 2, 1)
    _pie_from_distribution(ax_left, dist_base, "Базовая вероятность (L_base)")
    ax_right = plt.subplot(1, 2, 2)
    _pie_from_distribution(ax_right, dist_adjusted, "Скорректированная вероятность (L_adj)")
    plt.suptitle("Сравнение вероятности: L_base vs L_adj")
    plt.tight_layout(rect=(0, 0.08, 1, 1))
    base_prob_line = ", ".join(f"{k}={dist_base.get(k, 0)}" for k in LIKELIHOOD_ORDER)
    adj_prob_line = ", ".join(f"{k}={dist_adjusted.get(k, 0)}" for k in LIKELIHOOD_ORDER)
    plt.figtext(
        0.5,
        0.02,
        f"L_base (счётчики): {base_prob_line}\n"
        f"L_adj (счётчики): {adj_prob_line}",
        ha="center",
        fontsize=8,
    )
    p5 = os.path.join(target_dir, "likelihood_base_vs_adjusted_comparison.png")
    plt.savefig(p5, dpi=120)
    plt.close()
    saved.append(p5)

    # 6) Impact — pie (levels may be subset of five)
    impact = stats.get("impact_distribution", {})
    plt.figure(figsize=(7, 7))
    ax = plt.gca()
    _pie_generic(ax, {k: float(v) for k, v in impact.items()}, "Распределение Impact (актив)")
    plt.tight_layout()
    p6 = os.path.join(target_dir, "impact_distribution.png")
    plt.savefig(p6, dpi=120)
    plt.close()
    saved.append(p6)

    # 7) Vulnerability — pie
    vuln = stats.get("vulnerability_distribution", {})
    plt.figure(figsize=(7, 7))
    ax = plt.gca()
    _pie_generic(ax, {k: float(v) for k, v in vuln.items()}, "Личностная уязвимость")
    plt.tight_layout()
    p7 = os.path.join(target_dir, "vulnerability_distribution.png")
    plt.savefig(p7, dpi=120)
    plt.close()
    saved.append(p7)

    # 8) OSINT category means — pie by share of total mean
    avg_osint = stats.get("avg_osint_by_category", {})
    plt.figure(figsize=(8, 8))
    ax = plt.gca()
    if avg_osint:
        total_mean = sum(avg_osint.values()) or 1.0
        shares = {k: float(v) / total_mean for k, v in avg_osint.items()}
        _pie_generic(ax, shares, "Доля средних OSINT-метрик по категориям (нормировка на сумму)")
    else:
        ax.text(0.5, 0.5, "Нет данных", ha="center", va="center")
        ax.axis("off")
    plt.tight_layout()
    p8 = os.path.join(target_dir, "avg_osint_by_category.png")
    plt.savefig(p8, dpi=120)
    plt.close()
    saved.append(p8)

    return saved


if __name__ == "__main__":
    resumes_data = load_resumes()
    stats_data = build_stats(resumes_data)
    stats_path = save_stats_json(stats_data)
    plot_paths = save_plots(stats_data)
    print(f"Saved stats to: {stats_path}")
    if plot_paths:
        print("Saved plots:")
        for p in plot_paths:
            print(f"- {p}")
    else:
        print("matplotlib is unavailable, plots were skipped.")
