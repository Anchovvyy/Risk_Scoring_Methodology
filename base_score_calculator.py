"""
- baseline likelihood (L_base)
- stage 3 personal vulnerability index
- stage 4 adjusted likelihood (L_adj)
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional
from pathlib import Path

from likelihood_adjustment import adjust_likelihood
from final_risk_assessment import calculate_final_risk
from start_calculations import (
    DEFAULT_OSINT_CATEGORIES,
    INFORMATION_ASSETS,
    build_global_calculation_bundle,
    calculate_x95_thresholds,
    generate_seeded_osint_features,
    get_asset_impact,
    normalize_weights,
    resolve_weights_criteria,
)

LIKELIHOOD_LEVELS = ("very_low", "low", "moderate", "high", "very_high")
BASE_DIR = Path(__file__).parent.absolute()
DEFAULT_RESUME_DIR = Path(os.path.join(BASE_DIR, "generated_resumes"))
DEFAULT_RESUME_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_GLOBAL_OUTPUT_JSON = Path(os.path.join(BASE_DIR, "global_calculation_values.json"))

SEMIQUANT_TO_QUAL = (
    (0.0, 0.2, "very_low"),
    (0.2, 0.4, "low"),
    (0.4, 0.6, "moderate"),
    (0.6, 0.8, "high"),
    (0.8, 1.0000001, "very_high"),
)

# NIST G-5:
# L_initiation_level x L_impact_level -> L_base_level.
LBASE_MATRIX: Dict[str, Dict[str, str]] = {
    "very_high": {
        "very_low": "low", 
        "low": "moderate", 
        "moderate": "high", 
        "high": "very_high", 
        "very_high": "very_high"
    },
    "high": {
        "very_low": "low", 
        "low": "moderate", 
        "moderate": "moderate", 
        "high": "high", 
        "very_high": "very_high"
    },
    "moderate": {
        "very_low": "low", 
        "low": "low", 
        "moderate": "moderate", 
        "high": "moderate", 
        "very_high": "high"
    },
    "low": {
        "very_low": "very_low", 
        "low": "low", 
        "moderate": "low", 
        "high": "moderate", 
        "very_high": "moderate"
    },
    "very_low": {
        "very_low": "very_low", 
        "low": "very_low", 
        "moderate": "low", 
        "high": "low", 
        "very_high": "low"},
}

# Optional role/access multipliers for L_initiation  scores
ROLE_ACCESS_MULTIPLIERS: Dict[str, float] = {
    "none": 0.80,
    "read": 0.90,
    "write": 1.00,
    "delete": 1.10,
    "admin": 1.20,
}


@dataclass
class EmployeeRiskInput:
    employee_id: str
    role_access: str
    l_initiation: float
    l_impact_controls: float
    target_asset_id: str = "A5"
    osint_features: Optional[Dict[str, float]] = None


@dataclass
class GlobalRiskInput:
    ref_population: Dict[str, List[float]] = field(default_factory=dict)
    weights_criteria: Dict[str, float] = field(default_factory=dict)
    x95_thresholds: Dict[str, float] = field(default_factory=dict)
    risk_category_descriptions: Dict[str, str] = field(default_factory=dict)
    information_assets: Dict[str, Dict[str, str]] = field(default_factory=lambda: INFORMATION_ASSETS.copy())
    semiquant_to_qual: tuple = SEMIQUANT_TO_QUAL
    lbase_matrix: Mapping[str, Mapping[str, str]] = field(default_factory=lambda: LBASE_MATRIX)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def semiquant_to_qual_level(value: float, scale: tuple = SEMIQUANT_TO_QUAL) -> str:
    v = clamp01(value)
    for left, right, label in scale:
        if left <= v < right:
            return label
    return "very_high"


def level_to_numeric(level: str) -> float:
    mapping = {
        "very_low": 0.1,
        "low": 0.3,
        "moderate": 0.5,
        "high": 0.7,
        "very_high": 0.9,
    }
    return mapping.get(level, 0.5)


def apply_role_access_adjustment(l_initiation: float, role_access: str) -> float:
    multiplier = ROLE_ACCESS_MULTIPLIERS.get(role_access, 1.0)
    return clamp01(l_initiation * multiplier)


def combine_to_lbase(
    l_initiation_level: str,
    l_impact_level: str,
    matrix: Mapping[str, Mapping[str, str]] = LBASE_MATRIX,
) -> str:
    li = l_initiation_level if l_initiation_level in matrix else "moderate"
    row = matrix[li]
    return row.get(l_impact_level, "moderate")


def normalize_by_x95(value: float, x95: float) -> float:
    v = max(0.0, float(value))
    if x95 <= 0:
        return 0.0 if v == 0 else 1.0
    return 1.0 if v >= x95 else v / x95


def calculate_personal_vulnerability(
    osint_features: Mapping[str, float],
    x95_thresholds: Mapping[str, float],
    weights_criteria: Mapping[str, float],
) -> Dict[str, Any]:
    weights = normalize_weights(weights_criteria)

    xi: Dict[str, float] = {}
    for category in weights:
        raw_value = float(osint_features.get(category, 0.0))
        xi[category] = normalize_by_x95(raw_value, x95_thresholds.get(category, 0.0))

    vulnerability_index = sum(xi[cat] * weights[cat] for cat in weights)
    vulnerability_index = clamp01(vulnerability_index)
    vulnerability_level = semiquant_to_qual_level(vulnerability_index)

    return {
        "x95_thresholds": dict(x95_thresholds),
        "weights_criteria": weights,
        "xi_intensities": xi,
        "vulnerability_index": vulnerability_index,
        "vulnerability_level": vulnerability_level,
    }


def calculate_base_score_for_employee(
    employee: EmployeeRiskInput,
    global_data: GlobalRiskInput,
) -> Dict[str, Any]:
    adjusted_l_initiation = apply_role_access_adjustment(employee.l_initiation, employee.role_access)
    l_initiation_level = semiquant_to_qual_level(adjusted_l_initiation, global_data.semiquant_to_qual)
    l_impact_level = semiquant_to_qual_level(employee.l_impact_controls, global_data.semiquant_to_qual)
    l_base_level = combine_to_lbase(l_initiation_level, l_impact_level, global_data.lbase_matrix)
    l_base_numeric = level_to_numeric(l_base_level)
    vulnerability_data = calculate_personal_vulnerability(
        osint_features=employee.osint_features or {},
        x95_thresholds=global_data.x95_thresholds,
        weights_criteria=global_data.weights_criteria,
    )
    l_adjustment = adjust_likelihood(l_base_level, vulnerability_data["vulnerability_level"])
    impact_data = get_asset_impact(str(employee.target_asset_id))
    impact_level = impact_data["impact_level"]
    final_risk = calculate_final_risk(
        l_initiation_like_level=l_adjustment["l_adj_level"],
        l_impact_like_level=impact_level,
    )

    return {
        "employee_id": employee.employee_id,
        "role_access": employee.role_access,
        "l_initiation_raw": clamp01(employee.l_initiation),
        "l_initiation_adjusted": adjusted_l_initiation,
        "l_initiation_level": l_initiation_level,
        "l_impact_controls": clamp01(employee.l_impact_controls),
        "l_impact_level": l_impact_level,
        "l_base_numeric": l_base_numeric,
        "l_base_level": l_base_level,
        "osint_features": employee.osint_features or {},
        "stage3_personal_vulnerability": vulnerability_data,
        "likelihood_adjustment": l_adjustment,
        "impact_assessment": {
            "asset_id": employee.target_asset_id,
            "asset_name": impact_data["name"],
            "impact_level": impact_level,
            "impact_reason": impact_data["impact_reason"],
        },
        "final_risk_assessment": final_risk,
    }


def calculate_base_scores(
    employees: List[EmployeeRiskInput],
    global_data: GlobalRiskInput,
) -> List[Dict[str, Any]]:
    return [calculate_base_score_for_employee(employee, global_data) for employee in employees]


def calculate_base_scores_from_resume_dicts(
    resumes: List[Dict[str, Any]],
    ref_population: Optional[Dict[str, List[float]]] = None,
    weights_criteria: Optional[Dict[str, float]] = None,
    generate_random_osint: bool = True,
    random_seed: int = 42,
    global_values: Optional[Dict[str, Any]] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    generated_osint: List[Dict[str, float]] = []
    for idx, resume in enumerate(resumes):
        if generate_random_osint:
            generated_osint.append(
                generate_seeded_osint_features(
                    seed=random_seed + idx,
                    categories=DEFAULT_OSINT_CATEGORIES,
                )
            )
        else:
            generated_osint.append(
                {
                    category: float(resume.get("osint_features", {}).get(category, 0.0))
                    for category in DEFAULT_OSINT_CATEGORIES
                }
            )

    if global_values is not None:
        global_bundle = {
            "ref_population": global_values.get("ref_population", {}),
            "weights_criteria": normalize_weights(global_values.get("weights_criteria", {})),
            "x95_thresholds": global_values.get("x95_thresholds", {}),
            "risk_category_descriptions": global_values.get("risk_category_descriptions", {}),
            "information_assets": global_values.get("information_assets", INFORMATION_ASSETS),
            "ahp_report": global_values.get("ahp_report", {}),
        }
    else:
        global_bundle = build_global_calculation_bundle(employee_osint=generated_osint)
        if ref_population is not None:
            global_bundle["ref_population"] = dict(ref_population)
            global_bundle["x95_thresholds"] = calculate_x95_thresholds(global_bundle["ref_population"])
        if weights_criteria is not None:
            global_bundle["weights_criteria"] = normalize_weights(weights_criteria)

    global_data = GlobalRiskInput(
        ref_population=global_bundle["ref_population"],
        weights_criteria=global_bundle["weights_criteria"],
        x95_thresholds=global_bundle["x95_thresholds"],
        risk_category_descriptions=global_bundle["risk_category_descriptions"],
        information_assets=global_bundle["information_assets"],
    )

    employees: List[EmployeeRiskInput] = []
    for resume, osint_features in zip(resumes, generated_osint):
        employees.append(
            EmployeeRiskInput(
                employee_id=str(resume.get("id", "")),
                role_access=str(resume.get("role_access", "write")),
                l_initiation=float(resume.get("l_initiation", 0.5)),
                l_impact_controls=float(resume.get("l_impact_controls", 0.5)),
                target_asset_id=str(resume.get("target_asset", {}).get("asset_id", "A5")),
                osint_features=osint_features,
            )
        )
    results = calculate_base_scores(employees, global_data)
    ahp_report_out = global_bundle.get("ahp_report") or {}
    if not ahp_report_out:
        _, ahp_report_out = resolve_weights_criteria()
        ahp_report_out = ahp_report_out or {}
    global_values = {
        "weights_criteria": global_data.weights_criteria,
        "x95_thresholds": global_data.x95_thresholds,
        "risk_category_descriptions": global_data.risk_category_descriptions,
        "information_assets": global_data.information_assets,
        "ahp_report": ahp_report_out,
    }
    return results, global_values


def process_resume_files(
    resume_dir: str = DEFAULT_RESUME_DIR,
    random_seed: int = 42,
    generate_random_osint: bool = True,
    global_values: Optional[Dict[str, Any]] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    file_paths = sorted(glob.glob(os.path.join(resume_dir, "*.json")))
    resumes: List[Dict[str, Any]] = []
    for path in file_paths:
        with open(path, "r", encoding="utf-8") as file:
            resumes.append(json.load(file))

    results, global_values = calculate_base_scores_from_resume_dicts(
        resumes=resumes,
        generate_random_osint=generate_random_osint,
        random_seed=random_seed,
        global_values=global_values,
    )

    by_id = {item["employee_id"]: item for item in results}
    for path, resume in zip(file_paths, resumes):
        employee_id = str(resume.get("id", ""))
        calculation = by_id.get(employee_id, {})
        resume["risk_calculations"] = calculation
        with open(path, "w", encoding="utf-8") as file:
            json.dump(resume, file, ensure_ascii=False, indent=2)
    return results, global_values


def print_global_calculation_values(global_values: Dict[str, Any]) -> None:
    if not global_values:
        print("No results to print.")
        return
    print("Global values used:")
    print(json.dumps(global_values, ensure_ascii=False, indent=2))


def save_global_calculation_values(
    global_values: Dict[str, Any],
    output_path: str = DEFAULT_GLOBAL_OUTPUT_JSON,
) -> str:
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(global_values, file, ensure_ascii=False, indent=2)
    return output_path


def load_global_calculation_values(
    input_path: str = DEFAULT_GLOBAL_OUTPUT_JSON,
) -> Optional[Dict[str, Any]]:
    if not os.path.exists(input_path):
        return None
    with open(input_path, "r", encoding="utf-8") as file:
        return json.load(file)


if __name__ == "__main__":
    calculated, global_values = process_resume_files()
    print(f"Processed resumes: {len(calculated)}")
    print_global_calculation_values(global_values)
    output_file = save_global_calculation_values(global_values)
    print(f"Saved global values to: {output_file}")
