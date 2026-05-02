from __future__ import annotations
import argparse
import json
import random
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from start_calculations import DEFAULT_OSINT_CATEGORIES  # noqa: E402
#from stage3_ahp import format_generated_python_module, generate_ahp_bundle  # noqa: E402

"""
Stage 3 (МАИ / AHP): построение матрицы парных сравнений по шкале Саати,
случайное «реалистичное» ослабление согласованности с сохранением a_ji = 1/a_ij,
расчёт весов (собственный вектор), λ_max, CI, CR.

вызывается отдельным скриптом.
"""

#from __future__ import annotations
import random
from bisect import bisect_left
from typing import Any, Dict, List, Sequence, Tuple
import numpy as np

SAATY_SCALE: Tuple[float, ...] = tuple(
    sorted(
        set(
            [1.0 / float(k) for k in range(1, 10)]
            + [float(k) for k in range(1, 10)]
        )
    )
)

# Индекс случайной согласованности RI(n), Saaty (для CR)
RI_BY_N: Dict[int, float] = {
    1: 0.0,
    2: 0.0,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
}


def nearest_saaty(value: float) -> float:
    """Ближайшее значение на дискретной шкале Саати."""
    if value <= SAATY_SCALE[0]:
        return SAATY_SCALE[0]
    if value >= SAATY_SCALE[-1]:
        return SAATY_SCALE[-1]
    pos = bisect_left(SAATY_SCALE, value)
    if pos == 0:
        return SAATY_SCALE[0]
    before = SAATY_SCALE[pos - 1]
    after = SAATY_SCALE[pos]
    return before if abs(value - before) <= abs(value - after) else after


def _build_perfectly_consistent_matrix(priorities: Sequence[float]) -> np.ndarray:
    """a_ij = p_i / p_j — идеально согласованная положительная матрица."""
    p = np.array(priorities, dtype=float)
    p = np.where(p <= 0, 1e-9, p)
    col = p.reshape(-1, 1)
    row = p.reshape(1, -1)
    return row / col


def _discretize_upper_triangle(matrix: np.ndarray) -> np.ndarray:
    """Верхний треугольник (i<j): проекция на ближайшее значение шкалы Саати, диагональ 1."""
    n = matrix.shape[0]
    out = np.eye(n, dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            out[i, j] = nearest_saaty(float(matrix[i, j]))
            out[j, i] = 1.0 / out[i, j]
    return out


def _adjacent_scale_ratios(rng: random.Random) -> List[float]:
    """Множители «на шаг по шкале» вверх/вниз: s_{k+1}/s_k или s_k/s_{k+1}."""
    ratios: List[float] = []
    for k in range(len(SAATY_SCALE) - 1):
        a, b = SAATY_SCALE[k], SAATY_SCALE[k + 1]
        if a > 0:
            ratios.append(b / a)
            ratios.append(a / b)
    rng.shuffle(ratios)
    return ratios


def perturb_reciprocal_matrix(
    matrix: np.ndarray,
    rng: random.Random,
    perturbation_probability: float = 0.35,
    perturbations_max: int | None = None,
) -> Tuple[np.ndarray, int]:
    """
    Случайно ослабляет согласованность: для части пар (i<j) умножает a_ij
    на отношение двух соседних значений шкалы, затем снова проецирует на Saaty.
    Симметрия обратности сохраняется: a_ji = 1 / a_ij.
    """
    n = matrix.shape[0]
    out = np.array(matrix, dtype=float, copy=True)
    ratios = _adjacent_scale_ratios(rng)
    if not ratios:
        return out, 0
    applied = 0
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(pairs)
    for i, j in pairs:
        if perturbations_max is not None and applied >= perturbations_max:
            break
        if rng.random() > perturbation_probability:
            continue
        factor = rng.choice(ratios)
        if rng.random() < 0.5:
            factor = 1.0 / factor
        new_val = float(out[i, j]) * factor
        new_val = max(SAATY_SCALE[0], min(SAATY_SCALE[-1], new_val))
        new_val = nearest_saaty(new_val)
        out[i, j] = new_val
        out[j, i] = 1.0 / new_val
        applied += 1
    return out, applied


def principal_eigenvector_weights(matrix: np.ndarray) -> Tuple[np.ndarray, float]:
    """Главный собственный вектор (положительная часть), нормализация в сумму 1; λ_max."""
    eigenvalues, eigenvectors = np.linalg.eig(matrix)
    max_idx = int(np.argmax(eigenvalues.real))
    lambda_max = float(eigenvalues[max_idx].real)
    vec = np.abs(eigenvectors[:, max_idx].real)
    s = float(vec.sum())
    if s <= 0:
        uniform = np.ones(matrix.shape[0], dtype=float) / matrix.shape[0]
        return uniform, lambda_max
    return vec / s, lambda_max


def consistency_indices(matrix: np.ndarray, lambda_max: float) -> Dict[str, float]:
    n = int(matrix.shape[0])
    ci = 0.0 if n <= 2 else (lambda_max - n) / (n - 1)
    ri = RI_BY_N.get(n, 1.49)
    cr = 0.0 if ri == 0 else ci / ri
    return {"lambda_max": lambda_max, "ci": ci, "ri": ri, "cr": cr, "n": float(n)}


def generate_ahp_bundle(
    category_order: Sequence[str],
    rng: random.Random,
    perturbation_probability: float = 0.35,
    perturbations_max: int | None = 12,
    max_resamples: int = 80,
    cr_threshold: float = 0.12,
) -> Dict[str, Any]:
    """
    Полный цикл: идеальная матрица из случайных приоритетов → дискретизация Saaty
    → случайные возмущения с сохранением обратности → веса и CR.

    Если CR слишком велик, повторяет генерацию (до max_resamples).
    """
    categories = tuple(category_order)
    n = len(categories)
    last_report: Dict[str, Any] = {}

    for attempt in range(max_resamples):
        priorities = [rng.lognormvariate(0.0, 0.55) for _ in range(n)]
        consistent = _build_perfectly_consistent_matrix(priorities)
        discrete = _discretize_upper_triangle(consistent)
        perturbed, n_pert = perturb_reciprocal_matrix(
            discrete,
            rng,
            perturbation_probability=perturbation_probability,
            perturbations_max=perturbations_max,
        )
        weights_vec, lambda_max = principal_eigenvector_weights(perturbed)
        diag = consistency_indices(perturbed, lambda_max)
        weights_dict = {categories[i]: float(weights_vec[i]) for i in range(n)}
        total = sum(weights_dict.values()) or 1.0
        weights_dict = {k: v / total for k, v in weights_dict.items()}

        last_report = {
            "attempt": attempt + 1,
            "priorities_sample": [float(p) for p in priorities],
            "perturbations_applied": n_pert,
            **diag,
            "acceptable_cr_lt": cr_threshold,
            "acceptable": diag["cr"] < cr_threshold,
        }

        if diag["cr"] < cr_threshold:
            return {
                "categories": list(categories),
                "pairwise_matrix": perturbed.tolist(),
                "weights_criteria": weights_dict,
                "ahp_report": last_report,
            }

    return {
        "categories": list(categories),
        "pairwise_matrix": np.eye(n).tolist(),
        "weights_criteria": {c: 1.0 / n for c in categories},
        "ahp_report": {
            **last_report,
            "fallback": "uniform_weights_due_to_high_cr",
        },
    }


def format_generated_python_module(bundle: Dict[str, Any], seed: int) -> str:
    """Текст модуля для записи в generated_ahp_weights.py"""
    import json as _json

    matrix = bundle["pairwise_matrix"]
    weights = bundle["weights_criteria"]
    report = bundle.get("ahp_report", {})
    categories = bundle["categories"]
    lines = [
        '"""',
        "AUTO-GENERATED FILE — do not edit by hand.",
        f"Produced by run_generate_ahp_weights.py (seed={seed}).",
        "Weights replace EXPERT_WEIGHTS_CRITERIA when imported by start_calculations.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "CATEGORIES: tuple[str, ...] = " + repr(tuple(categories)),
        "",
        "PAIRWISE_MATRIX: list[list[float]] = " + _json.dumps(matrix, indent=4),
        "",
        "WEIGHTS_CRITERIA: dict[str, float] = " + _json.dumps(weights, indent=4, ensure_ascii=False),
        "",
        # json.dumps даёт true/false — в .py нужен валидный Python; repr сохраняет True/False.
        "AHP_REPORT: dict = " + repr(report),
        "",
    ]
    return "\n".join(lines)



def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AHP weights module (stage 3, one-off).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument(
        "--py-out",
        type=Path,
        default=THIS_DIR / "generated_ahp_weights.py",
        help="Output Python module path.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=THIS_DIR / "generated_ahp_weights.json",
        help="Output JSON path (same content as bundle).",
    )
    parser.add_argument("--cr-threshold", type=float, default=0.12, help="Target CR upper bound.")
    parser.add_argument("--perturb-prob", type=float, default=0.35, help="Probability to perturb each pair.")
    parser.add_argument("--perturb-max", type=int, default=12, help="Max number of perturbations.")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    bundle = generate_ahp_bundle(
        DEFAULT_OSINT_CATEGORIES,
        rng,
        perturbation_probability=args.perturb_prob,
        perturbations_max=args.perturb_max,
        cr_threshold=args.cr_threshold,
    )

    py_text = format_generated_python_module(bundle, args.seed)
    args.py_out.write_text(py_text, encoding="utf-8")
    args.json_out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    report = bundle.get("ahp_report", {})
    print(f"Written: {args.py_out}")
    print(f"Written: {args.json_out}")
    print(f"CR={report.get('cr'):.4f}  lambda_max={report.get('lambda_max'):.4f}  acceptable={report.get('acceptable')}")


if __name__ == "__main__":
    main()
