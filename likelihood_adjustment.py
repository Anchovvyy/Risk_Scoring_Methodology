"""
methodology stage 4
Adjusts base likelihood using personal vulnerability level.
"""

from typing import Dict

ADJUSTMENT_MATRIX: Dict[str, Dict[str, str]] = {
    "very_high": {
        "very_low": "very_high", 
        "low": "very_high", 
        "moderate": "very_high", 
        "high": "very_high", 
        "very_high": "very_high"
    },
    "high": {
        "very_low": "high", 
        "low": "high", 
        "moderate": "high",
        "high": "high",
        "very_high": "very_high"
    },
    "moderate": {
        "very_low": "moderate", 
        "low": "moderate", 
        "moderate": "moderate", 
        "high": "high", 
        "very_high": "very_high"
    },
    "low": {
        "very_low": "low", 
        "low": "low", 
        "moderate": "moderate", 
        "high": "high", 
        "very_high": "very_high"
    },
    "very_low": {
        "very_low": "very_low", 
        "low": "low", 
        "moderate": "moderate", 
        "high": "high", 
        "very_high": "very_high"
    },
}

LEVEL_TO_NUMERIC = {
    "very_low": 0.1,
    "low": 0.3,
    "moderate": 0.5,
    "high": 0.7,
    "very_high": 0.9,
}


def adjust_likelihood(l_base_level: str, vulnerability_level: str) -> Dict[str, object]:
    base = l_base_level if l_base_level in ADJUSTMENT_MATRIX else "moderate"
    adjusted_level = ADJUSTMENT_MATRIX[base].get(vulnerability_level, "moderate")
    return {
        "l_adj_level": adjusted_level,
        "l_adj_numeric": LEVEL_TO_NUMERIC.get(adjusted_level, 0.5),
    }

