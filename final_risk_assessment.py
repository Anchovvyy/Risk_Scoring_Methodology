"""
methodology stage 5
"""

from typing import Dict

FINAL_RISK_MATRIX: Dict[str, Dict[str, str]] = {
    "very_high": {
        "very_low": "very_low", 
        "low": "low", 
        "moderate": "moderate", 
        "high": "high", 
        "very_high": "very_high"
    },
    "high": {
        "very_low": "very_low", 
        "low": "low", 
        "moderate": "moderate", 
        "high": "moderate", 
        "very_high": "high"
    },
    "moderate": {
        "very_low": "very_low", 
        "low": "low", 
        "moderate": "low", 
        "high": "low", 
        "very_high": "moderate"
    },
    "low": {
        "very_low": "very_low", 
        "low": "very_low", 
        "moderate": "very_low", 
        "high": "low", 
        "very_high": "moderate"
    },
    "very_low": {
        "very_low": "very_low", 
        "low": "very_low", 
        "moderate": "very_low", 
        "high": "low", 
        "very_high": "low"},
}

RISK_SCALE = {
    "very_high": {
        "range_0_100": "96-100",
        "semiquant_value": 10,
        "description": "Очень высокий риск означает, что угроза может иметь множество серьезных или катастрофических негативных последствий для организации, активов, отдельных лиц, других организаций или страны.",
    },
    "high": {
        "range_0_100": "80-95",
        "semiquant_value": 8,
        "description": "Высокий риск означает, что угроза может иметь серьезные или катастрофические негативные последствия для организации, активов, отдельных лиц, других организаций или страны.",
    },
    "moderate": {
        "range_0_100": "21-79",
        "semiquant_value": 5,
        "description": "Умеренный риск означает, что угроза может иметь серьезные негативные последствия для организации, активов, отдельных лиц, других организаций или страны.",
    },
    "low": {
        "range_0_100": "5-20",
        "semiquant_value": 2,
        "description": "Низкий риск означает, что угроза может иметь ограниченные негативные последствия для организации, активов, отдельных лиц, других организаций или страны.",
    },
    "very_low": {
        "range_0_100": "0-4",
        "semiquant_value": 0,
        "description": "Очень низкий риск означает, что угроза может иметь незначительные негативные последствия для организации, активов, отдельных лиц, других организаций или страны.",
    },
}


def calculate_final_risk(
    l_initiation_like_level: str,
    l_impact_like_level: str,
) -> Dict[str, object]:
    initiation = l_initiation_like_level if l_initiation_like_level in FINAL_RISK_MATRIX else "moderate"
    final_level = FINAL_RISK_MATRIX[initiation].get(l_impact_like_level, "moderate")
    scale_data = RISK_SCALE[final_level]
    return {
        "final_risk_level": final_level,
        "final_risk_range_0_100": scale_data["range_0_100"],
        "final_risk_semiquant_value": scale_data["semiquant_value"],
        "final_risk_description": scale_data["description"],
    }

