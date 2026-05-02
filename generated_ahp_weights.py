from __future__ import annotations

CATEGORIES: tuple[str, ...] = ('criminal', 'financial', 'professional', 'psychological', 'reputational', 'behavioral', 'ideological')

PAIRWISE_MATRIX: list[list[float]] = [
    [
        1.0,
        0.5,
        2.0,
        1.0,
        0.5,
        1.0,
        0.5
    ],
    [
        2.0,
        1.0,
        3.0,
        1.0,
        1.0,
        2.0,
        0.5
    ],
    [
        0.5,
        0.3333333333333333,
        1.0,
        0.5,
        0.3333333333333333,
        0.5,
        0.25
    ],
    [
        1.0,
        1.0,
        2.0,
        1.0,
        0.5,
        0.5,
        0.5
    ],
    [
        2.0,
        1.0,
        3.0,
        2.0,
        1.0,
        2.0,
        1.0
    ],
    [
        1.0,
        0.5,
        2.0,
        2.0,
        0.5,
        1.0,
        0.3333333333333333
    ],
    [
        2.0,
        2.0,
        4.0,
        2.0,
        1.0,
        3.0,
        1.0
    ]
]

WEIGHTS_CRITERIA: dict[str, float] = {
    "criminal": 0.10435359532913259,
    "financial": 0.16842302659285488,
    "professional": 0.0564707369516998,
    "psychological": 0.1081732360248065,
    "reputational": 0.2008269380647641,
    "behavioral": 0.11367911517222412,
    "ideological": 0.24807335186451807
}

AHP_REPORT: dict = {'attempt': 1, 'priorities_sample': [1.1444560835493547, 0.7608915353568229, 1.9939792436486956, 0.926878783123475, 0.584673806312119, 1.3644857524749898, 0.5261311526916403], 'perturbations_applied': 8, 'lambda_max': 7.166107466944787, 'ci': 0.02768457782413118, 'ri': 1.32, 'cr': 0.020973165018281194, 'n': 7.0, 'acceptable_cr_lt': 0.12, 'acceptable': True}
