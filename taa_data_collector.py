"""
TAA Data Collector — Greybark Tactical Asset Allocation
Ejecuta el modelo cuantitativo MOM_MACRO y empaqueta resultados
para el AI Council y el reporte de Asset Allocation.

Integración:
  - run_monthly.py inyecta output via runner.data_collector._taa_data
  - council_data_collector.py distribuye a agentes relevantes
  - asset_allocation_renderer.py renderiza sección TAA
"""
import sys
import os
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Path al proyecto TAA
TAA_PROJECT = Path(os.environ.get(
    "TAA_PROJECT_PATH",
    str(Path(__file__).resolve().parent.parent.parent.parent / "greybark-asset-allocation")
))


class TAADataCollector:
    """Recopila señales del modelo cuantitativo TAA."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._taa_path_ok = TAA_PROJECT.exists()
        if not self._taa_path_ok:
            self._print(f"[TAA] WARN: proyecto no encontrado en {TAA_PROJECT}")

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    # ── Main entry point ─────────────────────────────────────────────

    def collect_all(self) -> Dict[str, Any]:
        """Ejecuta modelo TAA y retorna dict estructurado.

        Returns dict con keys:
            tilts, tilts_by_class, stress, regime, momentum,
            backtest_metrics, recent_excess, saa_weights,
            metadata, formatted (texto para prompts)
        """
        self._print("[TAA] Recopilando señales del modelo cuantitativo...")

        if not self._taa_path_ok:
            return {'error': f'TAA project not found at {TAA_PROJECT}'}

        result = {}

        # Add TAA project to path
        sys.path.insert(0, str(TAA_PROJECT))

        try:
            # Load data ONCE and reuse across sub-modules
            self._print("  -> Cargando datos TAA (cache)...")
            self._cached_data = self._load_taa_data()

            # 1. Current tilts
            result['tilts'] = self._collect_current_tilts()

            # 2. Stress score + components
            result['stress'] = self._collect_stress()

            # 3. Regime
            result['regime'] = self._collect_regime()

            # 4. Momentum rankings
            result['momentum'] = self._collect_momentum()

            # 5. Backtest metrics (from cached results)
            result['backtest_metrics'] = self._collect_backtest_metrics()

            # 6. Recent performance
            result['recent_excess'] = self._collect_recent_excess()

            # 7. SAA weights
            result['saa_weights'] = self._collect_saa_weights()

            # 8. Formatted text for agent prompts
            result['formatted'] = self._format_for_agents(result)

            # Metadata
            modules_ok = sum(1 for k, v in result.items()
                             if isinstance(v, dict) and 'error' not in v
                             and k not in ('formatted', 'metadata'))
            result['metadata'] = {
                'timestamp': datetime.now().isoformat(),
                'model': 'MOM_MACRO',
                'taa_project_path': str(TAA_PROJECT),
                'modules_ok': modules_ok,
                'modules_total': 7,
            }

            self._print(f"[TAA] Completado: {modules_ok}/7 módulos OK")

        except Exception as e:
            self._print(f"[TAA] ERROR general: {e}")
            traceback.print_exc()
            result['error'] = str(e)
        finally:
            # Clean up sys.path
            if str(TAA_PROJECT) in sys.path:
                sys.path.remove(str(TAA_PROJECT))

        return result

    def save(self, data: Dict[str, Any]) -> str:
        """Save TAA output to JSON for cache/audit (matches equity/rf collector pattern)."""
        import json
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        filename = f"taa_data_{datetime.now().strftime('%Y-%m-%d')}.json"
        path = output_dir / filename

        # Make data JSON-serializable
        serializable = {}
        for k, v in data.items():
            if k == 'formatted':
                serializable[k] = {fk: fv[:200] + '...' if len(fv) > 200 else fv
                                   for fk, fv in v.items()} if isinstance(v, dict) else v
            else:
                serializable[k] = v

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)

        self._print(f"[TAA] Guardado -> {path}")
        return str(path)

    # ── Sub-modules ──────────────────────────────────────────────────

    def _load_taa_data(self):
        """Load cached TAA data (prices, returns, macro)."""
        import config as cfg
        from src.data_pipeline import load_data
        return load_data(use_cache=True)

    def _collect_current_tilts(self) -> Dict[str, Any]:
        """Compute current MOM_MACRO tilts."""
        try:
            self._print("  -> TAA tilts actuales...")
            data = self._cached_data
            ret = data['returns_df']
            macro = data['macro_df']

            from src.optimizer import get_tilts, apply_tilts, _saa_series
            import config as cfg

            tilts = get_tilts(ret, method='mom_macro', macro_df=macro)
            final_weights = apply_tilts(tilts)
            saa = _saa_series(ret.columns.tolist())

            # Per-asset tilts
            tilts_dict = {t: round(float(v), 5) for t, v in tilts.items()}

            # Formatted list
            tilts_formatted = []
            for t in sorted(tilts.index, key=lambda x: abs(tilts[x]), reverse=True):
                v = tilts[t]
                direction = "OW" if v > 0.002 else "UW" if v < -0.002 else "N"
                asset_class = self._get_asset_class(t)
                tilts_formatted.append({
                    'asset': t,
                    'tilt_pct': f"{v:+.1%}",
                    'direction': direction,
                    'saa_weight': f"{saa.get(t, 0):.1%}",
                    'active_weight': f"{final_weights.get(t, 0):.1%}",
                    'asset_class': asset_class,
                })

            # By asset class
            tilts_by_class = {}
            for ac in ['US Equity', 'Intl Equity', 'Fixed Income', 'Alternatives', 'Sectors']:
                ac_tilts = {t: tilts[t] for t in tilts.index
                            if self._get_asset_class(t) == ac}
                if ac_tilts:
                    avg = sum(ac_tilts.values()) / len(ac_tilts)
                    top_2 = sorted(ac_tilts.items(), key=lambda x: abs(x[1]), reverse=True)[:2]
                    top_str = ", ".join(f"{t} {v:+.1%}" for t, v in top_2)
                    tilts_by_class[ac] = {
                        'avg_tilt': f"{avg:+.1%}",
                        'avg_tilt_raw': round(avg, 4),
                        'direction': 'OW' if avg > 0.002 else 'UW' if avg < -0.002 else 'N',
                        'top_assets': top_str,
                        'n_assets': len(ac_tilts),
                    }

            return {
                'tilts': tilts_dict,
                'tilts_formatted': tilts_formatted,
                'tilts_by_class': tilts_by_class,
                'gross_tilt': f"{tilts.abs().sum():.1%}",
            }
        except Exception as e:
            self._print(f"  [ERR] TAA tilts: {e}")
            return {'error': str(e)}

    def _collect_stress(self) -> Dict[str, Any]:
        """Compute stress score with component breakdown."""
        try:
            self._print("  -> TAA stress score...")
            data = self._cached_data
            ret = data['returns_df']
            macro = data['macro_df']
            import numpy as np
            import pandas as pd

            from src.optimizer import _stress_score

            score = _stress_score(macro, ret.index[-1])

            # Determine level
            if score > 0.6:
                level = "CRITICAL"
            elif score > 0.4:
                level = "HIGH"
            elif score > 0.25:
                level = "MEDIUM"
            else:
                level = "LOW"

            # Compute individual components for transparency
            monthly = macro.resample("ME").last().ffill()
            valid = monthly.loc[:ret.index[-1]]
            latest = valid.iloc[-1] if len(valid) > 0 else pd.Series()
            prev_6m = valid.iloc[-7] if len(valid) > 6 else latest

            components = {}
            if "VIXCLS" in latest.index and not pd.isna(latest["VIXCLS"]):
                components['vix'] = {
                    'value': round(float(latest["VIXCLS"]), 1),
                    'signal': 'stress' if latest["VIXCLS"] > 25 else 'elevated' if latest["VIXCLS"] > 20 else 'calm',
                }
            if "T10Y2Y" in latest.index and not pd.isna(latest["T10Y2Y"]):
                curve = float(latest["T10Y2Y"])
                components['yield_curve'] = {
                    'value': round(curve, 2),
                    'signal': 'inverted' if curve < 0 else 'flat' if curve < 0.3 else 'positive',
                }
            if "BAMLH0A0HYM2" in latest.index and not pd.isna(latest["BAMLH0A0HYM2"]):
                components['hy_spread'] = {
                    'value': round(float(latest["BAMLH0A0HYM2"]), 2),
                    'signal': 'wide' if latest["BAMLH0A0HYM2"] > 5 else 'normal',
                }
            if "ICSA" in latest.index and not pd.isna(latest["ICSA"]):
                icsa = float(latest["ICSA"])
                icsa_6m = float(prev_6m.get("ICSA", icsa)) if not pd.isna(prev_6m.get("ICSA", np.nan)) else icsa
                chg = (icsa - icsa_6m) / icsa_6m if icsa_6m > 0 else 0
                components['initial_claims'] = {
                    'value': int(icsa),
                    'chg_6m': f"{chg:+.1%}",
                    'signal': 'rising' if chg > 0.15 else 'stable' if chg > -0.05 else 'falling',
                }
            if "USEPUINDXD" in latest.index and not pd.isna(latest["USEPUINDXD"]):
                components['policy_uncertainty'] = {
                    'value': round(float(latest["USEPUINDXD"]), 0),
                    'signal': 'elevated' if latest["USEPUINDXD"] > 150 else 'normal',
                }
            if "NEWORDER" in latest.index and not pd.isna(latest["NEWORDER"]):
                no_now = float(latest["NEWORDER"])
                prev_12m = valid.iloc[-13] if len(valid) > 12 else valid.iloc[-7] if len(valid) > 6 else latest
                no_prev = float(prev_12m.get("NEWORDER", no_now)) if not pd.isna(prev_12m.get("NEWORDER", np.nan)) else no_now
                no_yoy = (no_now - no_prev) / no_prev if no_prev > 0 else 0
                components['new_orders'] = {
                    'value': f"${no_now/1000:.0f}B",
                    'yoy': f"{no_yoy:+.1%}",
                    'signal': 'declining' if no_yoy < -0.05 else 'stable' if no_yoy < 0.03 else 'growing',
                }

            return {
                'score': round(score, 3),
                'level': level,
                'components': components,
            }
        except Exception as e:
            self._print(f"  [ERR] TAA stress: {e}")
            return {'error': str(e)}

    def _collect_regime(self) -> Dict[str, Any]:
        """Detect current economic regime."""
        try:
            self._print("  -> TAA regime...")
            data = self._cached_data
            from src.regime_detector import detect_regimes

            regimes = detect_regimes(data['returns_df'], data['macro_df'], method='rules')
            current = regimes.iloc[-1]

            # Distribution
            dist = regimes.value_counts().to_dict()

            return {
                'current': current,
                'distribution': dist,
                'last_change': None,  # Could compute transition date
            }
        except Exception as e:
            self._print(f"  [ERR] TAA regime: {e}")
            return {'error': str(e)}

    def _collect_momentum(self) -> Dict[str, Any]:
        """Cross-sectional momentum rankings."""
        try:
            self._print("  -> TAA momentum...")
            data = self._cached_data
            ret = data['returns_df']

            # 12-month cumulative return (skip last month)
            if len(ret) < 13:
                return {'error': 'Not enough data for 12m momentum'}

            mom12 = (1 + ret.iloc[-13:-1]).prod() - 1
            mom12_sorted = mom12.sort_values(ascending=False)

            top = [(t, f"{v:+.1%}") for t, v in mom12_sorted.head(5).items()]
            bottom = [(t, f"{v:+.1%}") for t, v in mom12_sorted.tail(5).items()]

            # 6-month
            mom6 = (1 + ret.iloc[-7:-1]).prod() - 1
            mom6_sorted = mom6.sort_values(ascending=False)

            return {
                'mom_12m_top5': top,
                'mom_12m_bottom5': bottom,
                'mom_6m_top3': [(t, f"{v:+.1%}") for t, v in mom6_sorted.head(3).items()],
                'mom_6m_bottom3': [(t, f"{v:+.1%}") for t, v in mom6_sorted.tail(3).items()],
                'dispersion_12m': f"{mom12.std():.1%}",
            }
        except Exception as e:
            self._print(f"  [ERR] TAA momentum: {e}")
            return {'error': str(e)}

    def _collect_backtest_metrics(self) -> Dict[str, Any]:
        """Load backtest track record from cached results."""
        try:
            self._print("  -> TAA backtest metrics...")
            import pandas as pd

            bt_path = TAA_PROJECT / "results" / "backtest_mom_macro.csv"
            if not bt_path.exists():
                return {'error': 'No backtest results cached. Run main.py first.'}

            bt = pd.read_csv(bt_path, index_col=0, parse_dates=True)
            excess = bt['excess_return']
            active = bt['active_return']
            bench = bt['bench_return']

            n = len(bt)
            excess_ann = ((1 + excess).prod()) ** (12 / n) - 1
            te = excess.std() * (12 ** 0.5)
            ir = excess_ann / te if te > 1e-8 else 0

            active_ann = ((1 + active).prod()) ** (12 / n) - 1
            active_vol = active.std() * (12 ** 0.5)
            active_sharpe = active_ann / active_vol if active_vol > 1e-8 else 0

            cum_active = (1 + active).cumprod()
            max_dd = float((cum_active / cum_active.cummax() - 1).min())

            return {
                'excess_return_ann': f"{excess_ann:+.2%}",
                'information_ratio': round(ir, 2),
                'hit_rate': f"{(excess > 0).mean():.1%}",
                'tracking_error': f"{te:.2%}",
                'active_sharpe': round(active_sharpe, 2),
                'max_drawdown_active': f"{max_dd:.2%}",
                'backtest_months': n,
                'period': f"{bt.index[0].strftime('%Y-%m')} to {bt.index[-1].strftime('%Y-%m')}",
                'avg_turnover': f"{bt['turnover'].mean():.1%}",
            }
        except Exception as e:
            self._print(f"  [ERR] TAA backtest: {e}")
            return {'error': str(e)}

    def _collect_recent_excess(self) -> Dict[str, Any]:
        """Recent excess return performance."""
        try:
            import pandas as pd

            bt_path = TAA_PROJECT / "results" / "backtest_mom_macro.csv"
            if not bt_path.exists():
                return {'error': 'No backtest results cached'}

            bt = pd.read_csv(bt_path, index_col=0, parse_dates=True)
            excess = bt['excess_return']

            return {
                'last_1m': f"{excess.iloc[-1]:+.2%}" if len(excess) > 0 else "N/A",
                'last_3m': f"{excess.iloc[-3:].sum():+.2%}" if len(excess) >= 3 else "N/A",
                'last_6m': f"{excess.iloc[-6:].sum():+.2%}" if len(excess) >= 6 else "N/A",
                'last_12m': f"{excess.iloc[-12:].sum():+.2%}" if len(excess) >= 12 else "N/A",
            }
        except Exception as e:
            return {'error': str(e)}

    def _collect_saa_weights(self) -> Dict[str, Any]:
        """Return SAA benchmark weights grouped by asset class."""
        try:
            sys.path.insert(0, str(TAA_PROJECT))
            import config as cfg
            sys.path.remove(str(TAA_PROJECT))

            by_class = {}
            for t, w in cfg.SAA_WEIGHTS.items():
                ac = self._get_asset_class(t)
                by_class.setdefault(ac, {})[t] = f"{w:.1%}"

            totals = {}
            for ac, assets in by_class.items():
                total = sum(cfg.SAA_WEIGHTS[t] for t in assets)
                totals[ac] = f"{total:.0%}"

            return {'by_asset': cfg.SAA_WEIGHTS, 'by_class': by_class, 'class_totals': totals}
        except Exception as e:
            return {'error': str(e)}

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_asset_class(self, ticker: str) -> str:
        us_eq = {"SPY", "IWM", "IVE", "IVW", "VBR", "VUG"}
        intl = {"EFA", "VPL", "EEM"}
        fi = {"AGG", "TLT", "HYG"}
        alt = {"GLD", "VNQ", "DJP"}
        sectors = {"XLK", "XLV", "XLF", "XLE", "XLI", "XLP", "XLU", "XLY", "XLB"}
        if ticker in us_eq:
            return "US Equity"
        elif ticker in intl:
            return "Intl Equity"
        elif ticker in fi:
            return "Fixed Income"
        elif ticker in alt:
            return "Alternatives"
        elif ticker in sectors:
            return "Sectors"
        return "Other"

    def _format_for_agents(self, data: Dict) -> Dict[str, str]:
        """Pre-format text blocks for each agent prompt."""

        tilts_data = data.get('tilts', {})
        stress_data = data.get('stress', {})
        regime_data = data.get('regime', {})
        momentum_data = data.get('momentum', {})
        bt_data = data.get('backtest_metrics', {})

        # Common header
        header = (
            f"Modelo: MOM_MACRO (momentum 12-1 + macro signals + stress circuit breaker)\n"
            f"Track record: IR {bt_data.get('information_ratio', 'N/A')}, "
            f"hit rate {bt_data.get('hit_rate', 'N/A')}, "
            f"{bt_data.get('backtest_months', '?')} meses ({bt_data.get('period', '')})"
        )

        # Stress text
        stress_text = f"Score de estrés: {stress_data.get('score', 'N/A')} ({stress_data.get('level', '?')})"
        components = stress_data.get('components', {})
        if components:
            comp_lines = []
            for name, info in components.items():
                if isinstance(info, dict):
                    comp_lines.append(f"  {name}: {info.get('value', '?')} ({info.get('signal', '?')})")
            stress_text += "\nComponentes:\n" + "\n".join(comp_lines)

        # Regime text
        regime_text = f"Régimen detectado: {regime_data.get('current', 'N/A')}"

        # Tilts by class text
        tilts_class = tilts_data.get('tilts_by_class', {})
        tilts_lines = []
        for ac, info in tilts_class.items():
            if isinstance(info, dict):
                tilts_lines.append(
                    f"  {ac}: {info.get('direction', '?')} {info.get('avg_tilt', '')} "
                    f"(top: {info.get('top_assets', '')})"
                )
        tilts_class_text = "\n".join(tilts_lines) if tilts_lines else "N/A"

        # Momentum text
        mom_text = ""
        if not isinstance(momentum_data, dict) or 'error' in momentum_data:
            mom_text = "N/A"
        else:
            top = momentum_data.get('mom_12m_top5', [])
            bot = momentum_data.get('mom_12m_bottom5', [])
            mom_text = "Top 12m: " + ", ".join(f"{t} {v}" for t, v in top[:3])
            mom_text += "\nBottom 12m: " + ", ".join(f"{t} {v}" for t, v in bot[:3])

        # ── Per-agent formatted blocks ────────────────────────────────

        macro_block = (
            f"## MODELO CUANTITATIVO TAA\n{header}\n\n"
            f"{regime_text}\n{stress_text}\n\n"
            f"Sesgos por clase de activo:\n{tilts_class_text}\n\n"
            f"Este es un input cuantitativo. Puedes confirmarlo, matizarlo o divergir "
            f"con argumentos, pero referéncialo en tu análisis."
        )

        rv_block = (
            f"## SEÑALES CUANTITATIVAS TAA (Equity)\n{header}\n\n"
            f"Sesgos equity del modelo:\n{tilts_class_text}\n\n"
            f"Momentum 12m:\n{mom_text}\n\n"
            f"Usa estos sesgos como referencia cuantitativa complementaria."
        )

        rf_block = (
            f"## SEÑALES TAA RENTA FIJA\n{header}\n\n"
            f"Posicionamiento RF del modelo:\n"
        )
        fi_tilts = tilts_data.get('tilts', {})
        for t in ['AGG', 'TLT', 'HYG']:
            v = fi_tilts.get(t, 0)
            d = 'OW' if v > 0.002 else 'UW' if v < -0.002 else 'N'
            rf_block += f"  {t}: {v:+.1%} ({d})\n"
        curve_comp = components.get('yield_curve', {})
        rf_block += f"\nCurva 10Y-2Y: {curve_comp.get('value', '?')} ({curve_comp.get('signal', '?')})"

        riesgo_block = (
            f"## INDICADORES TAA DE RIESGO\n{header}\n\n"
            f"{stress_text}\n\n"
            f"{regime_text}\n"
            f"Gross tilt: {tilts_data.get('gross_tilt', 'N/A')}\n"
            f"Max drawdown activo: {bt_data.get('max_drawdown_active', 'N/A')}\n"
            f"Tracking error: {bt_data.get('tracking_error', 'N/A')}"
        )

        cio_block = (
            f"## MODELO CUANTITATIVO TAA — REFERENCIA PARA ALLOCATION\n{header}\n\n"
            f"{regime_text}\n{stress_text}\n\n"
            f"Sesgos tácticos vs benchmark SAA:\n{tilts_class_text}\n\n"
            f"Momentum:\n{mom_text}\n\n"
            f"INSTRUCCIÓN: Al generar el bloque [ALLOCATION], considere los sesgos TAA "
            f"como un input cuantitativo más. Puede divergir con argumentos, pero documente "
            f"por qué. Si coincide, referencie la confirmación cuantitativa."
        )

        return {
            'macro': macro_block,
            'rv': rv_block,
            'rf': rf_block,
            'riesgo': riesgo_block,
            'cio': cio_block,
            'header': header,
        }


# ── Self-test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    collector = TAADataCollector(verbose=True)
    result = collector.collect_all()

    if 'error' in result:
        print(f"\nERROR: {result['error']}")
    else:
        print(f"\n=== TAA Data Collector Test ===")
        print(f"Modules OK: {result['metadata']['modules_ok']}/7")

        tilts = result.get('tilts', {})
        if 'error' not in tilts:
            print(f"\nTop OW tilts:")
            for item in tilts['tilts_formatted'][:5]:
                if item['direction'] == 'OW':
                    print(f"  {item['asset']:5s} {item['tilt_pct']:>6s}  ({item['asset_class']})")
            print(f"Top UW tilts:")
            for item in tilts['tilts_formatted']:
                if item['direction'] == 'UW':
                    print(f"  {item['asset']:5s} {item['tilt_pct']:>6s}  ({item['asset_class']})")

        stress = result.get('stress', {})
        if 'error' not in stress:
            print(f"\nStress: {stress['score']} ({stress['level']})")

        regime = result.get('regime', {})
        if 'error' not in regime:
            print(f"Regime: {regime['current']}")

        bt = result.get('backtest_metrics', {})
        if 'error' not in bt:
            print(f"IR: {bt['information_ratio']}, Hit: {bt['hit_rate']}, "
                  f"Excess: {bt['excess_return_ann']}")

        # Show formatted block for CIO
        fmt = result.get('formatted', {})
        if fmt:
            print(f"\n--- CIO prompt block ---")
            print(fmt.get('cio', 'N/A')[:500])

    print("\nDone.")
