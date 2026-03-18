"""
Grey Bark - Regime Classification Indicators
Fetch all 11 leading indicators from various sources
"""

from datetime import date, datetime
from typing import Dict, Optional

from ...data_sources import FREDClient, BCChClient, CommLoanScraper, AlphaVantageClient


def fetch_all_indicators() -> Dict:
    """
    Fetch all 11 leading indicators for regime classification
    
    Indicators:
    1. Yield Curve 2s10s (FRED)
    2. HY Credit Spreads (FRED)
    3. MOVE Index (BCCh)
    4. VIX (BCCh)
    5. Consumer Confidence (FRED)
    6. ISM New Orders (FRED)
    7. Fed Expectations 12M (CommLoan)
    8. M2 Growth YoY (FRED)
    9. Initial Claims (FRED)
    10. Copper/Gold Ratio (BCCh)
    11. China EPU (BCCh)
    
    Returns:
        Dict with all indicator values and metadata
    """
    print("=" * 70)
    print("FETCHING REGIME CLASSIFICATION INDICATORS")
    print("=" * 70)
    
    indicators = {
        'timestamp': datetime.now().isoformat(),
        'financial_markets': {},
        'expectations': {},
        'monetary': {},
        'real_economy': {},
        'errors': []
    }
    
    # Initialize clients
    fred = FREDClient()
    bcch = BCChClient()
    commloan = CommLoanScraper()
    
    # =========================================================================
    # FINANCIAL MARKETS (40%)
    # =========================================================================
    print("\n[Financial Markets]")
    
    # 1. Yield Curve 2s10s
    try:
        spread = fred.get_yield_curve_spread()
        if spread is not None:
            indicators['financial_markets']['yield_curve_2s10s'] = {
                'value': spread,
                'unit': 'bp',
                'source': 'FRED (DGS10 - DGS2)'
            }
            print(f"  ✓ Yield Curve 2s10s: {spread:+.0f} bp")
    except Exception as e:
        indicators['errors'].append(f"yield_curve: {e}")
        print(f"  ✗ Yield Curve 2s10s: Error - {e}")
    
    # 2. HY Spreads
    try:
        hy_spread = fred.get_latest_value('BAMLH0A0HYM2')
        if hy_spread is not None:
            indicators['financial_markets']['hy_spreads'] = {
                'value': hy_spread,
                'unit': '%',
                'source': 'FRED (BAMLH0A0HYM2)'
            }
            print(f"  ✓ HY Spreads: {hy_spread:.2f}%")
    except Exception as e:
        indicators['errors'].append(f"hy_spreads: {e}")
        print(f"  ✗ HY Spreads: Error - {e}")
    
    # 3. MOVE Index
    try:
        move = bcch.get_latest_value('F019.MOVE.IND.90.D')
        if move is not None:
            indicators['financial_markets']['move_index'] = {
                'value': move,
                'unit': 'index',
                'source': 'BCCh (F019.MOVE.IND.90.D)'
            }
            print(f"  ✓ MOVE Index: {move:.1f}")
    except Exception as e:
        indicators['errors'].append(f"move_index: {e}")
        print(f"  ✗ MOVE Index: Error - {e}")
    
    # 4. VIX
    try:
        vix = bcch.get_latest_value('F019.VIX.IND.90.D')
        if vix is not None:
            indicators['financial_markets']['vix'] = {
                'value': vix,
                'unit': 'index',
                'source': 'BCCh (F019.VIX.IND.90.D)'
            }
            print(f"  ✓ VIX: {vix:.1f}")
    except Exception as e:
        indicators['errors'].append(f"vix: {e}")
        print(f"  ✗ VIX: Error - {e}")
    
    # =========================================================================
    # EXPECTATIONS (25%)
    # =========================================================================
    print("\n[Expectations]")
    
    # 5. Consumer Confidence
    try:
        cc = fred.get_latest_value('CSCICP03USM665S')
        if cc is not None:
            indicators['expectations']['consumer_confidence'] = {
                'value': cc,
                'unit': 'index',
                'source': 'FRED (CSCICP03USM665S)'
            }
            print(f"  ✓ Consumer Confidence: {cc:.1f}")
    except Exception as e:
        indicators['errors'].append(f"consumer_confidence: {e}")
        print(f"  ✗ Consumer Confidence: Error - {e}")
    
    # 6. ISM New Orders
    try:
        ism = fred.get_latest_value('NEWORDER')
        if ism is not None:
            # Normalize (FRED reports in thousands)
            ism_normalized = ism / 1000 if ism > 100 else ism
            indicators['expectations']['ism_new_orders'] = {
                'value': ism_normalized,
                'unit': 'index',
                'source': 'FRED (NEWORDER)',
                'note': 'Normalized from FRED format'
            }
            print(f"  ✓ ISM New Orders: {ism_normalized:.1f}")
    except Exception as e:
        indicators['errors'].append(f"ism_new_orders: {e}")
        print(f"  ✗ ISM New Orders: Error - {e}")
    
    # =========================================================================
    # MONETARY (20%)
    # =========================================================================
    print("\n[Monetary]")
    
    # 7. Fed Expectations 12M
    try:
        sofr_rates = commloan.get_sofr_forwards()
        sofr_1y = sofr_rates.get('1Y')
        current_ff = 4.50  # Could be parameterized
        
        if sofr_1y is not None:
            fed_exp_change = (sofr_1y + 0.08) - current_ff  # SOFR + spread - current
            indicators['monetary']['fed_expectations_12m'] = {
                'value': round(fed_exp_change * 100),  # In bp
                'unit': 'bp',
                'source': 'CommLoan SOFR 1Y',
                'implied_rate': round(sofr_1y + 0.08, 2)
            }
            print(f"  ✓ Fed Expectations 12M: {fed_exp_change * 100:+.0f} bp")
    except Exception as e:
        indicators['errors'].append(f"fed_expectations: {e}")
        print(f"  ✗ Fed Expectations 12M: Error - {e}")
    
    # 8. M2 Growth YoY
    try:
        m2_data = fred.get_series('M2SL')
        if m2_data is not None and len(m2_data) > 12:
            current = m2_data.iloc[-1]
            year_ago = m2_data.iloc[-13]
            m2_growth = ((current / year_ago) - 1) * 100
            
            indicators['monetary']['m2_growth_yoy'] = {
                'value': round(m2_growth, 1),
                'unit': '%',
                'source': 'FRED (M2SL)'
            }
            print(f"  ✓ M2 Growth YoY: {m2_growth:.1f}%")
    except Exception as e:
        indicators['errors'].append(f"m2_growth: {e}")
        print(f"  ✗ M2 Growth YoY: Error - {e}")
    
    # =========================================================================
    # REAL ECONOMY (15%)
    # =========================================================================
    print("\n[Real Economy]")
    
    # 9. Initial Claims
    try:
        claims = fred.get_latest_value('IC4WSA')
        if claims is not None:
            # Convert to thousands if needed
            claims_k = claims / 1000 if claims > 1000 else claims
            indicators['real_economy']['initial_claims'] = {
                'value': claims_k,
                'unit': 'K',
                'source': 'FRED (IC4WSA)'
            }
            print(f"  ✓ Initial Claims: {claims_k:.0f}K")
    except Exception as e:
        indicators['errors'].append(f"initial_claims: {e}")
        print(f"  ✗ Initial Claims: Error - {e}")
    
    # 10. Copper/Gold Ratio
    try:
        copper = bcch.get_latest_value('F019.PPB.PRE.40.M')
        gold = bcch.get_latest_value('F019.PPB.PRE.44B.M')
        
        if copper is not None and gold is not None and gold > 0:
            # Normalize: Copper ($/lb) * 1000 / Gold ($/oz)
            # Typical ratio around 0.002 (copper ~4, gold ~2000)
            ratio = (copper * 1000) / gold
            
            indicators['real_economy']['copper_gold_ratio'] = {
                'value': round(ratio, 3),
                'unit': 'ratio',
                'source': 'BCCh (F019.PPB.PRE.40/44B)',
                'copper': copper,
                'gold': gold
            }
            print(f"  ✓ Copper/Gold Ratio: {ratio:.3f}")
    except Exception as e:
        indicators['errors'].append(f"copper_gold: {e}")
        print(f"  ✗ Copper/Gold Ratio: Error - {e}")
    
    # 11. China EPU
    try:
        china_epu = bcch.get_latest_value('F019.EPU.IND.CHN.M')
        if china_epu is not None:
            indicators['real_economy']['china_epu'] = {
                'value': china_epu,
                'unit': 'index',
                'source': 'BCCh (F019.EPU.IND.CHN.M)'
            }
            print(f"  ✓ China EPU: {china_epu:.1f}")
    except Exception as e:
        indicators['errors'].append(f"china_epu: {e}")
        print(f"  ✗ China EPU: Error - {e}")
    
    # Summary
    total_indicators = (
        len(indicators['financial_markets']) +
        len(indicators['expectations']) +
        len(indicators['monetary']) +
        len(indicators['real_economy'])
    )
    
    print("\n" + "=" * 70)
    print(f"Fetched {total_indicators}/11 indicators successfully")
    if indicators['errors']:
        print(f"Errors: {len(indicators['errors'])}")
    print("=" * 70)
    
    return indicators


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    indicators = fetch_all_indicators()
    
    import json
    print("\n\nJSON Output:")
    print(json.dumps(indicators, indent=2))
