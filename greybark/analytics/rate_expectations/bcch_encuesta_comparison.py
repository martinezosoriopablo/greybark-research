"""
Grey Bark - BCCh Encuesta Comparison
Compare Market expectations (Swaps CAMARA) vs Encuesta BCCh (EEE)
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from ...data_sources import BCChClient
from ...utils.quantlib_helpers import bootstrap_ois_curve_clp


def compare_market_vs_encuesta(current_tpm: float = 5.00) -> Dict:
    """
    Compare market rate expectations vs BCCh Encuesta Expectativas Económicas
    
    Sources:
    - Market: BCCh Swaps Promedio Cámara → QuantLib
    - Encuesta: BCCh EEE (F089.TPM.TAS.*)
    
    Args:
        current_tpm: Current TPM rate
    
    Returns:
        Dict with:
            - timestamp
            - current_rate
            - encuesta: Survey expectations by horizon
            - market_expectations: Market implied rates
            - comparison: Side by side with diff and signal
    """
    print("=" * 70)
    print("TPM: MERCADO vs ENCUESTA BCCh COMPARISON")
    print("=" * 70)
    
    client = BCChClient()
    
    # 1. Fetch Encuesta data
    encuesta = client.get_encuesta_tpm()
    
    # 2. Fetch SPC rates and build curve
    spc_rates = client.get_spc_rates()
    
    if not spc_rates:
        raise ValueError("Could not fetch SPC rates from BCCh")
    
    print("\n[QuantLib] Bootstrapping OIS curve CAMARA...")
    curve = bootstrap_ois_curve_clp(spc_rates)
    
    # 3. Map encuesta horizons to market rates
    # Months ahead → SPC tenor mapping
    horizon_to_tenor = {
        0: '90D',    # siguiente reunión ~ 1 mes
        1: '90D',    # subsiguiente ~ 2 meses
        2: '90D',    # 2 meses
        5: '180D',   # 5 meses
        11: '360D',  # 11 meses
        17: '2Y',    # 17 meses
        23: '2Y',    # 23 meses
        35: '3Y',    # 35 meses
    }
    
    # Build market expectations by horizon
    market_by_horizon = {}
    for months, tenor in horizon_to_tenor.items():
        rate = spc_rates.get(tenor)
        if rate:
            market_by_horizon[months] = rate
    
    # 4. Build comparison table
    comparison = []
    
    print(f"\n{'Horizonte':<30} | {'Mercado':>9} | {'Encuesta':>9} | {'Diff':>8} | {'Señal':<20}")
    print("-" * 85)
    
    for key, eee_data in encuesta['by_horizon'].items():
        months = eee_data['months_ahead']
        desc = eee_data['description']
        eee_rate = eee_data['rate']
        
        # Get corresponding market rate
        market_rate = market_by_horizon.get(months)
        
        if market_rate is not None and eee_rate is not None:
            diff_bp = round((market_rate - eee_rate) * 100)
            
            if diff_bp < -10:
                signal = "Mercado más DOVISH"
            elif diff_bp > 10:
                signal = "Mercado más HAWKISH"
            else:
                signal = "Alineados"
            
            comparison.append({
                'horizon': desc,
                'months_ahead': months,
                'market': market_rate,
                'encuesta': eee_rate,
                'diff_bp': diff_bp,
                'signal': signal,
            })
            
            print(f"{desc:<30} | {market_rate:>8.2f}% | {eee_rate:>8.2f}% | {diff_bp:>+7}bp | {signal:<20}")
    
    print("=" * 85)
    
    # 5. Generate overall signal
    avg_diff = sum(c['diff_bp'] for c in comparison) / len(comparison) if comparison else 0
    
    if avg_diff < -15:
        overall_signal = "Mercado significativamente más DOVISH que analistas"
    elif avg_diff < -5:
        overall_signal = "Mercado ligeramente más DOVISH que analistas"
    elif avg_diff > 15:
        overall_signal = "Mercado significativamente más HAWKISH que analistas"
    elif avg_diff > 5:
        overall_signal = "Mercado ligeramente más HAWKISH que analistas"
    else:
        overall_signal = "Mercado alineado con analistas"
    
    print(f"\nSeñal general: {overall_signal}")
    print(f"Diferencia promedio: {avg_diff:+.0f} bp")
    
    # 6. Identify divergences
    divergences = []
    for c in comparison:
        if abs(c['diff_bp']) > 25:
            divergences.append({
                'horizon': c['horizon'],
                'diff_bp': c['diff_bp'],
                'signal': c['signal']
            })
    
    if divergences:
        print(f"\nDivergencias significativas (>25bp):")
        for d in divergences:
            print(f"  • {d['horizon']}: {d['diff_bp']:+d}bp - {d['signal']}")
    
    return {
        'timestamp': datetime.now().isoformat(),
        'current_rate': current_tpm,
        'encuesta': encuesta,
        'market_expectations': spc_rates,
        'comparison': comparison,
        'overall_signal': overall_signal,
        'avg_diff_bp': round(avg_diff),
        'divergences': divergences,
    }


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    report = compare_market_vs_encuesta(current_tpm=5.00)
    
    import json
    print("\n\nJSON Output:")
    print(json.dumps(report, indent=2, default=str))
