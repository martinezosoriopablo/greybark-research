"""
Grey Bark - Regime Classification Scoring
Convert indicator values to discrete scores (-3 to +3)
"""

from typing import Dict, Optional

# =============================================================================
# THRESHOLDS CONFIGURATION
# =============================================================================

# Yield Curve 2s10s (basis points)
# Positive = steep curve (good), Negative = inverted (recession signal)
YIELD_CURVE_THRESHOLDS = {
    3: (150, float('inf')),     # > +150bp
    2: (100, 150),              # +100 to +150bp
    1: (50, 100),               # +50 to +100bp
    0: (-50, 50),               # -50 to +50bp (flat)
    -1: (-100, -50),            # -50 to -100bp
    -2: (-150, -100),           # -100 to -150bp
    -3: (float('-inf'), -150),  # < -150bp
}

# HY Spreads (percentage)
# Lower = risk-on, Higher = stress
HY_SPREADS_THRESHOLDS = {
    3: (0, 2.5),                # < 2.5% (tight)
    2: (2.5, 3.0),
    1: (3.0, 3.5),
    0: (3.5, 4.0),              # Neutral
    -1: (4.0, 5.0),
    -2: (5.0, 6.0),
    -3: (6.0, float('inf')),    # > 6% (stress)
}

# MOVE Index
# Lower = calm, Higher = bond volatility
MOVE_THRESHOLDS = {
    3: (0, 80),                 # < 80 (very calm)
    2: (80, 100),
    1: (100, 120),
    0: (120, 140),              # Neutral
    -1: (140, 160),
    -2: (160, 200),
    -3: (200, float('inf')),    # > 200 (panic)
}

# VIX
# Lower = complacency, Higher = fear
VIX_THRESHOLDS = {
    3: (0, 12),                 # < 12 (complacency, could be negative!)
    2: (12, 15),
    1: (15, 18),
    0: (18, 22),                # Neutral
    -1: (22, 28),
    -2: (28, 35),
    -3: (35, float('inf')),     # > 35 (panic)
}

# Consumer Confidence
# Higher = optimistic
CONSUMER_CONFIDENCE_THRESHOLDS = {
    3: (102, float('inf')),     # > 102
    2: (100, 102),
    1: (98, 100),
    0: (96, 98),                # Neutral
    -1: (94, 96),
    -2: (92, 94),
    -3: (0, 92),                # < 92
}

# ISM New Orders
# Higher = expansion
ISM_NEW_ORDERS_THRESHOLDS = {
    3: (60, float('inf')),      # > 60
    2: (55, 60),
    1: (52, 55),
    0: (48, 52),                # Neutral (50 = no change)
    -1: (45, 48),
    -2: (42, 45),
    -3: (0, 42),                # < 42
}

# Fed Expectations 12M (basis points change)
# Positive = hawkish (expecting hikes), Negative = dovish (expecting cuts)
FED_EXPECTATIONS_THRESHOLDS = {
    3: (100, float('inf')),     # Pricing +100bp+ hikes
    2: (50, 100),               # Pricing +50bp hikes
    1: (25, 50),                # Pricing +25bp
    0: (-25, 25),               # Stable
    -1: (-50, -25),             # Pricing -25 to -50bp
    -2: (-100, -50),            # Pricing -50 to -100bp
    -3: (float('-inf'), -100),  # Pricing -100bp+ cuts
}

# M2 Growth YoY (percentage)
# Higher = more liquidity
M2_GROWTH_THRESHOLDS = {
    3: (15, float('inf')),      # > 15%
    2: (10, 15),
    1: (5, 10),
    0: (0, 5),                  # Low growth
    -1: (-2, 0),
    -2: (-5, -2),
    -3: (float('-inf'), -5),    # Contraction
}

# Initial Claims (thousands)
# Lower = strong labor market
INITIAL_CLAIMS_THRESHOLDS = {
    3: (0, 200),                # < 200K (very strong)
    2: (200, 220),
    1: (220, 240),
    0: (240, 260),              # Neutral
    -1: (260, 280),
    -2: (280, 320),
    -3: (320, float('inf')),    # > 320K (weak)
}

# Copper/Gold Ratio (normalized)
# Higher = risk-on, growth expectations
COPPER_GOLD_THRESHOLDS = {
    3: (2.5, float('inf')),     # > 2.5 (risk-on)
    2: (2.2, 2.5),
    1: (2.0, 2.2),
    0: (1.8, 2.0),              # Neutral
    -1: (1.6, 1.8),
    -2: (1.4, 1.6),
    -3: (0, 1.4),               # < 1.4 (risk-off)
}

# China EPU (percentile-based, or raw value thresholds)
# Lower = stable, Higher = uncertainty
CHINA_EPU_THRESHOLDS = {
    3: (0, 100),                # Percentile < 20 (low uncertainty)
    2: (100, 150),
    1: (150, 200),
    0: (200, 300),              # Neutral
    -1: (300, 400),
    -2: (400, 500),
    -3: (500, float('inf')),    # Very high uncertainty
}


# =============================================================================
# WEIGHTS
# =============================================================================

WEIGHTS = {
    'yield_curve_2s10s': 0.15,
    'hy_spreads': 0.10,
    'move_index': 0.10,
    'vix': 0.05,
    'consumer_confidence': 0.15,
    'ism_new_orders': 0.10,
    'fed_expectations_12m': 0.10,
    'm2_growth_yoy': 0.10,
    'initial_claims': 0.05,
    'copper_gold_ratio': 0.05,
    'china_epu': 0.05,
}


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================

def value_to_score(value: float, thresholds: Dict[int, tuple]) -> int:
    """
    Convert a value to discrete score based on thresholds
    
    Args:
        value: The indicator value
        thresholds: Dict mapping score to (min, max) tuple
    
    Returns:
        Discrete score from -3 to +3
    """
    for score, (min_val, max_val) in thresholds.items():
        if min_val <= value < max_val:
            return score
    return 0  # Default to neutral


def calculate_indicator_scores(indicators: Dict) -> Dict:
    """
    Calculate discrete scores for all indicators
    
    Args:
        indicators: Dict from fetch_all_indicators()
    
    Returns:
        Dict with scores for each indicator
    """
    scores = {
        'financial_markets': {},
        'expectations': {},
        'monetary': {},
        'real_economy': {},
        'weighted_score': 0,
        'category_scores': {}
    }
    
    total_weight = 0
    weighted_sum = 0
    category_sums = {
        'financial_markets': {'sum': 0, 'weight': 0},
        'expectations': {'sum': 0, 'weight': 0},
        'monetary': {'sum': 0, 'weight': 0},
        'real_economy': {'sum': 0, 'weight': 0},
    }
    
    # Financial Markets
    fm = indicators.get('financial_markets', {})
    
    if 'yield_curve_2s10s' in fm:
        val = fm['yield_curve_2s10s']['value']
        score = value_to_score(val, YIELD_CURVE_THRESHOLDS)
        scores['financial_markets']['yield_curve_2s10s'] = score
        weighted_sum += score * WEIGHTS['yield_curve_2s10s']
        total_weight += WEIGHTS['yield_curve_2s10s']
        category_sums['financial_markets']['sum'] += score * WEIGHTS['yield_curve_2s10s']
        category_sums['financial_markets']['weight'] += WEIGHTS['yield_curve_2s10s']
    
    if 'hy_spreads' in fm:
        val = fm['hy_spreads']['value']
        score = value_to_score(val, HY_SPREADS_THRESHOLDS)
        scores['financial_markets']['hy_spreads'] = score
        weighted_sum += score * WEIGHTS['hy_spreads']
        total_weight += WEIGHTS['hy_spreads']
        category_sums['financial_markets']['sum'] += score * WEIGHTS['hy_spreads']
        category_sums['financial_markets']['weight'] += WEIGHTS['hy_spreads']
    
    if 'move_index' in fm:
        val = fm['move_index']['value']
        score = value_to_score(val, MOVE_THRESHOLDS)
        scores['financial_markets']['move_index'] = score
        weighted_sum += score * WEIGHTS['move_index']
        total_weight += WEIGHTS['move_index']
        category_sums['financial_markets']['sum'] += score * WEIGHTS['move_index']
        category_sums['financial_markets']['weight'] += WEIGHTS['move_index']
    
    if 'vix' in fm:
        val = fm['vix']['value']
        score = value_to_score(val, VIX_THRESHOLDS)
        scores['financial_markets']['vix'] = score
        weighted_sum += score * WEIGHTS['vix']
        total_weight += WEIGHTS['vix']
        category_sums['financial_markets']['sum'] += score * WEIGHTS['vix']
        category_sums['financial_markets']['weight'] += WEIGHTS['vix']
    
    # Expectations
    exp = indicators.get('expectations', {})
    
    if 'consumer_confidence' in exp:
        val = exp['consumer_confidence']['value']
        score = value_to_score(val, CONSUMER_CONFIDENCE_THRESHOLDS)
        scores['expectations']['consumer_confidence'] = score
        weighted_sum += score * WEIGHTS['consumer_confidence']
        total_weight += WEIGHTS['consumer_confidence']
        category_sums['expectations']['sum'] += score * WEIGHTS['consumer_confidence']
        category_sums['expectations']['weight'] += WEIGHTS['consumer_confidence']
    
    if 'ism_new_orders' in exp:
        val = exp['ism_new_orders']['value']
        score = value_to_score(val, ISM_NEW_ORDERS_THRESHOLDS)
        scores['expectations']['ism_new_orders'] = score
        weighted_sum += score * WEIGHTS['ism_new_orders']
        total_weight += WEIGHTS['ism_new_orders']
        category_sums['expectations']['sum'] += score * WEIGHTS['ism_new_orders']
        category_sums['expectations']['weight'] += WEIGHTS['ism_new_orders']
    
    # Monetary
    mon = indicators.get('monetary', {})
    
    if 'fed_expectations_12m' in mon:
        val = mon['fed_expectations_12m']['value']
        score = value_to_score(val, FED_EXPECTATIONS_THRESHOLDS)
        scores['monetary']['fed_expectations_12m'] = score
        weighted_sum += score * WEIGHTS['fed_expectations_12m']
        total_weight += WEIGHTS['fed_expectations_12m']
        category_sums['monetary']['sum'] += score * WEIGHTS['fed_expectations_12m']
        category_sums['monetary']['weight'] += WEIGHTS['fed_expectations_12m']
    
    if 'm2_growth_yoy' in mon:
        val = mon['m2_growth_yoy']['value']
        score = value_to_score(val, M2_GROWTH_THRESHOLDS)
        scores['monetary']['m2_growth_yoy'] = score
        weighted_sum += score * WEIGHTS['m2_growth_yoy']
        total_weight += WEIGHTS['m2_growth_yoy']
        category_sums['monetary']['sum'] += score * WEIGHTS['m2_growth_yoy']
        category_sums['monetary']['weight'] += WEIGHTS['m2_growth_yoy']
    
    # Real Economy
    real = indicators.get('real_economy', {})
    
    if 'initial_claims' in real:
        val = real['initial_claims']['value']
        score = value_to_score(val, INITIAL_CLAIMS_THRESHOLDS)
        scores['real_economy']['initial_claims'] = score
        weighted_sum += score * WEIGHTS['initial_claims']
        total_weight += WEIGHTS['initial_claims']
        category_sums['real_economy']['sum'] += score * WEIGHTS['initial_claims']
        category_sums['real_economy']['weight'] += WEIGHTS['initial_claims']
    
    if 'copper_gold_ratio' in real:
        val = real['copper_gold_ratio']['value']
        score = value_to_score(val, COPPER_GOLD_THRESHOLDS)
        scores['real_economy']['copper_gold_ratio'] = score
        weighted_sum += score * WEIGHTS['copper_gold_ratio']
        total_weight += WEIGHTS['copper_gold_ratio']
        category_sums['real_economy']['sum'] += score * WEIGHTS['copper_gold_ratio']
        category_sums['real_economy']['weight'] += WEIGHTS['copper_gold_ratio']
    
    if 'china_epu' in real:
        val = real['china_epu']['value']
        score = value_to_score(val, CHINA_EPU_THRESHOLDS)
        scores['real_economy']['china_epu'] = score
        weighted_sum += score * WEIGHTS['china_epu']
        total_weight += WEIGHTS['china_epu']
        category_sums['real_economy']['sum'] += score * WEIGHTS['china_epu']
        category_sums['real_economy']['weight'] += WEIGHTS['china_epu']
    
    # Calculate weighted score
    if total_weight > 0:
        scores['weighted_score'] = round(weighted_sum / total_weight, 2)
    
    # Calculate category scores
    for cat, data in category_sums.items():
        if data['weight'] > 0:
            scores['category_scores'][cat] = round(data['sum'] / data['weight'], 2)
    
    return scores


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    # Test with sample data
    sample_indicators = {
        'financial_markets': {
            'yield_curve_2s10s': {'value': 50},
            'hy_spreads': {'value': 3.5},
            'move_index': {'value': 110},
            'vix': {'value': 18},
        },
        'expectations': {
            'consumer_confidence': {'value': 98},
            'ism_new_orders': {'value': 52},
        },
        'monetary': {
            'fed_expectations_12m': {'value': -50},
            'm2_growth_yoy': {'value': 4},
        },
        'real_economy': {
            'initial_claims': {'value': 230},
            'copper_gold_ratio': {'value': 1.9},
            'china_epu': {'value': 250},
        }
    }
    
    scores = calculate_indicator_scores(sample_indicators)
    
    import json
    print(json.dumps(scores, indent=2))
