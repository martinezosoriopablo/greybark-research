"""
Grey Bark - Regime Classifier
Main module that orchestrates regime classification
"""

from datetime import datetime
from typing import Dict, List, Optional

from .indicators import fetch_all_indicators
from .scoring import calculate_indicator_scores


# =============================================================================
# REGIME CLASSIFICATION THRESHOLDS
# =============================================================================

REGIME_THRESHOLDS = {
    'RECESSION': (float('-inf'), -1.5),
    'SLOWDOWN': (-1.5, -0.5),
    'MODERATE_GROWTH': (-0.5, 0.5),
    'EXPANSION': (0.5, 1.5),
    'LATE_CYCLE_BOOM': (1.5, float('inf')),
}

REGIME_DESCRIPTIONS = {
    'RECESSION': 'Contracción económica. Risk-off, defensivo.',
    'SLOWDOWN': 'Desaceleración. Cautela, calidad sobre crecimiento.',
    'MODERATE_GROWTH': 'Crecimiento moderado. Neutral, diversificado.',
    'EXPANSION': 'Expansión. Risk-on, cíclicos y crecimiento.',
    'LATE_CYCLE_BOOM': 'Boom tardío. Cautela ante posible reversión.',
}

REGIME_ASSET_ALLOCATION = {
    'RECESSION': {
        'equities': 'STRONG_UNDERWEIGHT',
        'bonds': 'OVERWEIGHT',
        'cash': 'OVERWEIGHT',
        'sectors': ['Utilities', 'Healthcare', 'Consumer Staples'],
    },
    'SLOWDOWN': {
        'equities': 'SLIGHT_UNDERWEIGHT',
        'bonds': 'OVERWEIGHT',
        'cash': 'NEUTRAL',
        'sectors': ['Healthcare', 'Utilities', 'Consumer Staples', 'Financials', 'Technology'],
    },
    'MODERATE_GROWTH': {
        'equities': 'NEUTRAL',
        'bonds': 'NEUTRAL',
        'cash': 'NEUTRAL',
        'sectors': ['Technology', 'Healthcare', 'Financials', 'Industrials'],
    },
    'EXPANSION': {
        'equities': 'OVERWEIGHT',
        'bonds': 'UNDERWEIGHT',
        'cash': 'UNDERWEIGHT',
        'sectors': ['Technology', 'Industrials', 'Financials', 'Consumer Discretionary'],
    },
    'LATE_CYCLE_BOOM': {
        'equities': 'NEUTRAL',
        'bonds': 'UNDERWEIGHT',
        'cash': 'SLIGHT_OVERWEIGHT',
        'sectors': ['Energy', 'Materials', 'Financials'],
    },
}


# =============================================================================
# CLASSIFICATION FUNCTIONS
# =============================================================================

def score_to_regime(score: float) -> str:
    """
    Convert weighted score to regime classification
    
    Args:
        score: Weighted score from -3 to +3
    
    Returns:
        Regime name
    """
    for regime, (min_val, max_val) in REGIME_THRESHOLDS.items():
        if min_val <= score < max_val:
            return regime
    return 'MODERATE_GROWTH'  # Default


def calculate_regime_probabilities(score: float) -> Dict[str, float]:
    """
    Calculate probability distribution across regimes
    
    Uses a simple linear interpolation approach
    """
    probabilities = {}
    
    # Distance-based probability
    total_inv_dist = 0
    midpoints = {
        'RECESSION': -2.0,
        'SLOWDOWN': -1.0,
        'MODERATE_GROWTH': 0.0,
        'EXPANSION': 1.0,
        'LATE_CYCLE_BOOM': 2.0,
    }
    
    for regime, midpoint in midpoints.items():
        dist = abs(score - midpoint)
        if dist < 0.01:
            dist = 0.01  # Avoid division by zero
        inv_dist = 1.0 / dist
        probabilities[regime] = inv_dist
        total_inv_dist += inv_dist
    
    # Normalize to sum to 100%
    for regime in probabilities:
        probabilities[regime] = round((probabilities[regime] / total_inv_dist) * 100, 1)
    
    return probabilities


def identify_top_concerns(indicators: Dict, scores: Dict, n: int = 3) -> List[Dict]:
    """
    Identify top concerns (most negative indicators)
    """
    all_scores = []
    
    for category in ['financial_markets', 'expectations', 'monetary', 'real_economy']:
        for indicator, score in scores.get(category, {}).items():
            value = None
            if category in indicators and indicator in indicators[category]:
                value = indicators[category][indicator].get('value')
            
            all_scores.append({
                'indicator': indicator,
                'category': category,
                'score': score,
                'value': value,
            })
    
    # Sort by score ascending (most negative first)
    all_scores.sort(key=lambda x: x['score'])
    
    return all_scores[:n]


def identify_top_supports(indicators: Dict, scores: Dict, n: int = 3) -> List[Dict]:
    """
    Identify top supports (most positive indicators)
    """
    all_scores = []
    
    for category in ['financial_markets', 'expectations', 'monetary', 'real_economy']:
        for indicator, score in scores.get(category, {}).items():
            value = None
            if category in indicators and indicator in indicators[category]:
                value = indicators[category][indicator].get('value')
            
            all_scores.append({
                'indicator': indicator,
                'category': category,
                'score': score,
                'value': value,
            })
    
    # Sort by score descending (most positive first)
    all_scores.sort(key=lambda x: x['score'], reverse=True)
    
    return all_scores[:n]


def classify_regime() -> Dict:
    """
    Main function: Classify current macro regime
    
    Returns:
        Dict with:
            - timestamp
            - classification: Regime name
            - score: Weighted score
            - probabilities: Distribution across regimes
            - description: Regime description
            - asset_allocation: Recommended allocation
            - indicators: Raw indicator values
            - scores: Indicator scores
            - top_concerns: Most negative indicators
            - top_supports: Most positive indicators
    """
    print("=" * 70)
    print("GREY BARK REGIME CLASSIFICATION")
    print("=" * 70)
    
    # 1. Fetch indicators
    indicators = fetch_all_indicators()
    
    # 2. Calculate scores
    scores = calculate_indicator_scores(indicators)
    
    # 3. Classify regime
    weighted_score = scores['weighted_score']
    regime = score_to_regime(weighted_score)
    
    # 4. Calculate probabilities
    probabilities = calculate_regime_probabilities(weighted_score)
    
    # 5. Identify concerns and supports
    top_concerns = identify_top_concerns(indicators, scores)
    top_supports = identify_top_supports(indicators, scores)
    
    # 6. Build result
    result = {
        'timestamp': datetime.now().isoformat(),
        'classification': regime,
        'score': weighted_score,
        'probabilities': probabilities,
        'description': REGIME_DESCRIPTIONS[regime],
        'asset_allocation': REGIME_ASSET_ALLOCATION[regime],
        'category_scores': scores['category_scores'],
        'indicators': indicators,
        'scores': scores,
        'top_concerns': top_concerns,
        'top_supports': top_supports,
    }
    
    # Print summary
    print("\n" + "=" * 70)
    print(f"RÉGIMEN: {regime}")
    print(f"Score: {weighted_score:+.2f}")
    print(f"Descripción: {REGIME_DESCRIPTIONS[regime]}")
    print("\nProbabilidades:")
    for r, p in sorted(probabilities.items(), key=lambda x: -x[1]):
        print(f"  {r:20} {p:5.1f}%")
    print("\nTop Concerns:")
    for c in top_concerns:
        print(f"  • {c['indicator']}: {c['score']:+d}")
    print("\nTop Supports:")
    for s in top_supports:
        print(f"  • {s['indicator']}: {s['score']:+d}")
    print("=" * 70)
    
    return result


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    result = classify_regime()
    
    import json
    print("\n\nJSON Output (summary):")
    summary = {
        'timestamp': result['timestamp'],
        'classification': result['classification'],
        'score': result['score'],
        'probabilities': result['probabilities'],
        'category_scores': result['category_scores'],
        'asset_allocation': result['asset_allocation'],
    }
    print(json.dumps(summary, indent=2))
