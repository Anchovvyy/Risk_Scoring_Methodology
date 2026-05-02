"""
Global calculations for risk methodology:
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Optional, Tuple

DEFAULT_OSINT_CATEGORIES = (
    "criminal",
    "financial",
    "professional",
    "psychological",
    "reputational",
    "behavioral",
    "ideological",
)

RISK_CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    "criminal": "Отражает наличие признаков противоправной деятельности и прямых угроз безопасности активов и персонала.",
    "financial": "Связан с долговыми обязательствами, судебными спорами и финансовой нестабильностью.",
    "professional": "Отражает несоответствие компетенций, нестабильную трудовую историю или недостоверность заявленных данных.",
    "psychological": "Включает признаки эмоциональной нестабильности, агрессии или деструктивного поведения.",
    "reputational": "Связан с источниками негативной публичной информации.",
    "behavioral": "Описывает аномальную или нетипичную активность в цифровой среде.",
    "ideological": "Характеризует устойчивые радикальные убеждения.",
}

# Запасные веса, если ещё не сгенерирован модуль `generated_ahp_weights.py`
# (запуск: python run_generate_ahp_weights.py).
EXPERT_WEIGHTS_CRITERIA: Dict[str, float] = {
    "criminal": 0.20,
    "financial": 0.22,
    "professional": 0.12,
    "psychological": 0.14,
    "reputational": 0.09,
    "behavioral": 0.08,
    "ideological": 0.15,
}

# Left-skewed Beta
OSINT_BETA_ALPHA = 2.0
OSINT_BETA_BETA = 5.0

INFORMATION_ASSETS: Dict[str, Dict[str, str]] = {
    "A1": {
        "name": "База данных клиентов",
        "impact_level": "very_high",
        "impact_reason": "Конфиденциальность высокая",
    },
    "A2": {
        "name": "Внутренняя wiki",
        "impact_level": "high",
        "impact_reason": "Доступность критична",
    },
    "A3": {
        "name": "Финансовая отчётность",
        "impact_level": "very_high",
        "impact_reason": "Целостность важна",
    },
    "A4": {
        "name": "Исходный код проекта",
        "impact_level": "high",
        "impact_reason": "Коммерческая и технологическая ценность",
    },
    "A5": {
        "name": "Общая папка отдела",
        "impact_level": "moderate",
        "impact_reason": "Влияет на локальные процессы отдела",
    },
}

def get_asset_impact(asset_id: str) -> Dict[str, str]:
    return INFORMATION_ASSETS.get(asset_id, INFORMATION_ASSETS["A5"])


def percentile_95(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(float(v) for v in values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = 0.95 * (n - 1)
    low_idx = int(pos)
    high_idx = min(low_idx + 1, n - 1)
    frac = pos - low_idx
    return sorted_vals[low_idx] * (1.0 - frac) + sorted_vals[high_idx] * frac


def calculate_x95_thresholds(ref_population: Mapping[str, List[float]]) -> Dict[str, float]:
    return {category: percentile_95(values) for category, values in ref_population.items()}


def normalize_weights(weights: Mapping[str, float]) -> Dict[str, float]:
    cleaned = {k: max(0.0, float(v)) for k, v in weights.items()}
    total = sum(cleaned.values())
    if total <= 0:
        size = len(cleaned) or 1
        return {k: 1.0 / size for k in cleaned}
    return {k: v / total for k, v in cleaned.items()}


def resolve_weights_criteria() -> tuple[Dict[str, float], Optional[Dict[str, Any]]]:
    """
    Веса этапа 3: если существует `generated_ahp_weights.py` (однократный МАИ-прогон),
    берём оттуда WEIGHTS_CRITERIA и AHP_REPORT; иначе — EXPERT_WEIGHTS_CRITERIA.
    """
    try:
        from generated_ahp_weights import AHP_REPORT, WEIGHTS_CRITERIA

        return normalize_weights(dict(WEIGHTS_CRITERIA)), dict(AHP_REPORT) if AHP_REPORT else {}
    except ImportError:
        return normalize_weights(EXPERT_WEIGHTS_CRITERIA), None


def calculate_expert_weights() -> Dict[str, float]:
    weights, _meta = resolve_weights_criteria()
    return weights


def osint_population_from_features(employee_osint: List[Mapping[str, float]]) -> Dict[str, List[float]]:
    population: Dict[str, List[float]] = {category: [] for category in DEFAULT_OSINT_CATEGORIES}
    for features in employee_osint:
        for category in DEFAULT_OSINT_CATEGORIES:
            population[category].append(float(features.get(category, 0.0)))
    return population


def build_global_calculation_bundle(
    employee_osint: List[Mapping[str, float]] | None = None,
) -> Dict[str, object]:
    if employee_osint is not None and employee_osint:
        pop = osint_population_from_features(employee_osint)
    else:
        rng = random.Random(42)
        pop = {
            category: [round(rng.betavariate(OSINT_BETA_ALPHA, OSINT_BETA_BETA), 4) for _ in range(100)]
            for category in DEFAULT_OSINT_CATEGORIES
        }
    weights, ahp_report = resolve_weights_criteria()
    x95 = calculate_x95_thresholds(pop)
    return {
        "ref_population": pop,
        "weights_criteria": weights,
        "x95_thresholds": x95,
        "risk_category_descriptions": RISK_CATEGORY_DESCRIPTIONS,
        "information_assets": INFORMATION_ASSETS,
        "ahp_report": ahp_report or {},
    }


def random_osint_metric(rng: random.Random | None = None) -> float:
    """Single OSINT score in [0, 1], skewed toward low values (left-skewed Beta)."""
    generator = rng if rng is not None else random
    return round(generator.betavariate(OSINT_BETA_ALPHA, OSINT_BETA_BETA), 4)


def generate_seeded_osint_features(seed: int, categories: Tuple[str, ...] = DEFAULT_OSINT_CATEGORIES) -> Dict[str, float]:
    rng = random.Random(seed)
    return {category: random_osint_metric(rng) for category in categories}

