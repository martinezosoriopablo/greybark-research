"""
Grey Bark - CLP Rate Expectations
TPM Chile expectations using FedWatch-style methodology

Uses Swaps Promedio Cámara from BCCh + QuantLib bootstrap
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from ...data_sources import BCChClient
from ...utils.dates import get_future_bcch_meetings, days_to_meeting, format_meeting_label
from ...utils.quantlib_helpers import (
    bootstrap_ois_curve_clp,
    get_forward_at_meeting,
    round_to_nearest_quarter,
    calculate_probability_vs_previous,
)


def generate_tpm_expectations(current_tpm: float = 4.50,
                               num_meetings: int = 12) -> Dict:
    """
    Generate TPM (Chile) rate expectations report
    
    Uses FedWatch-style methodology adapted for Chile:
    1. Extract Swaps Promedio Cámara from BCCh REST API
    2. Bootstrap OIS curve with QuantLib
    3. Calculate forward rate at each BCCh meeting
    4. Round to nearest 0.25% for expected rate
    5. Calculate probabilities vs previous meeting rate
    
    Args:
        current_tpm: Current TPM rate
        num_meetings: Number of future meetings to analyze
    
    Returns:
        Dict with:
            - timestamp: ISO format
            - current_rate: Current TPM
            - summary: Direction, recortes/alzas expected, terminal
            - meetings: List of meeting details with probabilities
    """
    print("=" * 70)
    print("TPM CHILE RATE EXPECTATIONS")
    print("=" * 70)
    
    # 1. Fetch SPC rates
    client = BCChClient()
    spc_rates = client.get_spc_rates()
    
    if not spc_rates:
        raise ValueError("Could not fetch SPC rates from BCCh")
    
    # 2. Bootstrap curve
    print("\n[QuantLib] Bootstrapping OIS curve CAMARA...")
    curve = bootstrap_ois_curve_clp(spc_rates)
    print("[QuantLib] ✓ Curve bootstrapped")
    
    # 3. Get future BCCh meetings
    meetings = get_future_bcch_meetings(count=num_meetings)
    
    # 4. Calculate expectations for each meeting
    results = []
    previous_rate = current_tpm
    
    print(f"\n{'Reunión':<12} {'Días':>5} {'Forward':>8} {'Esperada':>9} {'Prev':>8} | "
          f"{'Escenario 1':<18} {'Prob':>6} | {'Escenario 2':<18} {'Prob':>6}")
    print("-" * 110)
    
    for meeting_date in meetings:
        # Get forward rate at meeting date
        forward = get_forward_at_meeting(curve, meeting_date)
        
        # Calculate probabilities
        probs = calculate_probability_vs_previous(forward, previous_rate)
        
        days = days_to_meeting(meeting_date)
        label = format_meeting_label(meeting_date)
        
        # Translate actions to Spanish
        scenario_high_es = probs['scenario_high'].replace('HOLD', 'MANTIENE').replace('HIKE', 'ALZA').replace('CUT', 'RECORTE')
        scenario_low_es = probs['scenario_low'].replace('HOLD', 'MANTIENE').replace('HIKE', 'ALZA').replace('CUT', 'RECORTE')
        
        meeting_result = {
            'date': meeting_date.isoformat(),
            'label': label,
            'days_to_meeting': days,
            'forward_rate': round(forward, 3),
            'expected_rate': probs['expected_rate'],
            'previous_rate': previous_rate,
            'scenario_high': scenario_high_es,
            'scenario_low': scenario_low_es,
            'prob_high': probs['prob_high'],
            'prob_low': probs['prob_low'],
        }
        results.append(meeting_result)
        
        print(f"{label:<12} {days:>5} {forward:>7.3f}% {probs['expected_rate']:>8.2f}% "
              f"{previous_rate:>7.2f}% | {scenario_high_es:<18} {probs['prob_high']:>5.1f}% | "
              f"{scenario_low_es:<18} {probs['prob_low']:>5.1f}%")
        
        # Update previous rate for next iteration
        previous_rate = probs['expected_rate']
    
    # 5. Generate summary
    first_rate = current_tpm
    terminal_rate = results[-1]['expected_rate'] if results else current_tpm
    
    recortes = sum(1 for r in results if r['expected_rate'] < r['previous_rate'])
    alzas = sum(1 for r in results if r['expected_rate'] > r['previous_rate'])
    
    if terminal_rate < first_rate:
        direction = 'RECORTES'
    elif terminal_rate > first_rate:
        direction = 'ALZAS'
    else:
        direction = 'MANTENCIÓN'
    
    summary = {
        'direction': direction,
        'recortes_esperados': recortes,
        'alzas_esperadas': alzas,
        'tasa_terminal': terminal_rate,
        'cambio_total_bp': round((terminal_rate - first_rate) * 100),
    }
    
    print("\n" + "=" * 70)
    print(f"Resumen: {direction}")
    print(f"  Recortes esperados: {recortes}")
    print(f"  Alzas esperadas: {alzas}")
    print(f"  Tasa terminal: {terminal_rate:.2f}%")
    print(f"  Cambio total: {summary['cambio_total_bp']:+d} bp")
    print("=" * 70)
    
    return {
        'timestamp': datetime.now().isoformat(),
        'current_rate': current_tpm,
        'spc_rates': spc_rates,
        'summary': summary,
        'meetings': results,
    }


def get_market_rate_by_months(spc_rates: Dict[str, float], months: int) -> Optional[float]:
    """
    Get implied TPM rate for a given number of months ahead
    
    Args:
        spc_rates: Dict of SPC rates by tenor
        months: Months ahead
    
    Returns:
        Implied rate or None
    """
    # Map months to tenor
    if months <= 3:
        tenor = '90D'
    elif months <= 6:
        tenor = '180D'
    elif months <= 12:
        tenor = '360D'
    elif months <= 24:
        tenor = '2Y'
    elif months <= 36:
        tenor = '3Y'
    else:
        tenor = '5Y'
    
    return spc_rates.get(tenor)


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    report = generate_tpm_expectations(current_tpm=4.50)
    
    import json
    print("\n\nJSON Output:")
    print(json.dumps(report, indent=2, default=str))
