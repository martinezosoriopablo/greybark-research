# -*- coding: utf-8 -*-
"""
Grey Bark - BCCh Extended Client
Banco Central de Chile - 93+ Series

Organizado por categoria para dashboards y graficos.
"""

import requests
from datetime import date, timedelta
from typing import Dict, Optional, Any
import pandas as pd

from ..config import config, BCChSeries, DEFAULT_LOOKBACK_DAYS


class BCChExtendedClient:
    """
    Cliente extendido para BCCh REST API con 93+ series.

    Categorias:
    - Chile Macro (TPM, IPC, IMACEC, Desempleo, FX)
    - Actividad Sectorial (Industria, Mineria, Manufactura)
    - Comercio y Consumo (Ventas retail, Autos)
    - Comercio Exterior (Exports, Imports)
    - Tasas Chile (SPC curve, Tasas sistema financiero)
    - Credito (Colocaciones por tipo)
    - Commodities (Cobre, Oro, Petroleo, Litio)
    - Volatilidad (VIX, MOVE, EPU)
    - Internacional (Inflacion, Core, Bonos 10Y, TPM)
    - Bolsas

    Usage:
        client = BCChExtendedClient()

        # Dashboard completo Chile
        chile = client.get_chile_macro()

        # Comparativo internacional
        inflacion = client.get_international_inflation()
        tasas = client.get_international_rates()
    """

    def __init__(self, user: str = None, password: str = None):
        self.user = user or config.bcch.user
        self.password = password or config.bcch.password
        self.base_url = config.bcch.rest_url
        self._cache = {}

    # =========================================================================
    # CORE FETCH METHOD
    # =========================================================================

    def get_series(self,
                   series_id: str,
                   start_date: date = None,
                   end_date: date = None,
                   days_back: int = DEFAULT_LOOKBACK_DAYS) -> Optional[pd.Series]:
        """Fetch series from BCCh REST API"""
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=days_back)

        params = {
            'user': self.user,
            'pass': self.password,
            'function': 'GetSeries',
            'timeseries': series_id,
            'firstdate': start_date.strftime('%Y-%m-%d'),
            'lastdate': end_date.strftime('%Y-%m-%d')
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            if response.status_code != 200:
                return None

            data = response.json()
            obs = data.get('Series', {}).get('Obs', [])

            if not obs:
                return None

            dates = []
            values = []
            for observation in obs:
                date_str = observation.get('indexDateString', '')
                value_str = observation.get('value', '').strip()
                if date_str and value_str:
                    try:
                        dates.append(pd.to_datetime(date_str, dayfirst=True))
                        values.append(float(value_str))
                    except (ValueError, TypeError):
                        continue

            if dates and values:
                return pd.Series(values, index=dates, name=series_id)
            return None

        except Exception:
            return None

    def get_latest(self, series_id: str, days_back: int = DEFAULT_LOOKBACK_DAYS) -> Optional[float]:
        """Get latest value for a series"""
        data = self.get_series(series_id, days_back=days_back)
        if data is not None and len(data) > 0:
            return round(float(data.iloc[-1]), 4)
        return None

    def _fetch_multiple(self, series_dict: Dict[str, str]) -> Dict[str, Optional[float]]:
        """Fetch multiple series and return as dict"""
        result = {}
        for name, series_id in series_dict.items():
            result[name] = self.get_latest(series_id)
        return result

    # =========================================================================
    # CHILE MACRO
    # =========================================================================

    def get_chile_macro(self) -> Dict[str, Any]:
        """
        Dashboard macro Chile completo

        Returns:
            Dict con TPM, IPC, IMACEC, Desempleo, USD/CLP, UF, Confianza
        """
        series = {
            'tpm': BCChSeries.TPM,
            'usd_clp': BCChSeries.USD_CLP,
            'uf': BCChSeries.UF,
            'imacec_yoy': BCChSeries.IMACEC_YOY,
            'imacec_nomin_yoy': BCChSeries.IMACEC_NOMIN_YOY,
            'desempleo': BCChSeries.DESEMPLEO,
            'ipec': BCChSeries.IPEC,
        }

        data = self._fetch_multiple(series)

        # Calcular IPC YoY
        ipc_series = self.get_series(BCChSeries.IPC_VAR, days_back=400)
        if ipc_series is not None and len(ipc_series) >= 12:
            data['ipc_yoy'] = round(float(ipc_series.iloc[-12:].sum()), 1)
        else:
            data['ipc_yoy'] = None

        # Calcular tasa real
        if data['tpm'] and data['ipc_yoy']:
            data['tpm_real'] = round(data['tpm'] - data['ipc_yoy'], 2)
        else:
            data['tpm_real'] = None

        return data

    # =========================================================================
    # ACTIVIDAD SECTORIAL
    # =========================================================================

    def get_sectoral_activity(self) -> Dict[str, Optional[float]]:
        """
        Indicadores de actividad sectorial

        Returns:
            Dict con produccion industrial, manufactura, mineria, electricidad, cobre
        """
        series = {
            'prod_industrial': BCChSeries.PROD_INDUSTRIAL,
            'prod_manufactura': BCChSeries.PROD_MANUFACTURA,
            'prod_mineria': BCChSeries.PROD_MINERIA,
            'prod_electricidad': BCChSeries.PROD_ELECTRICIDAD,
            'prod_cobre_ktm': BCChSeries.PROD_COBRE,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # COMERCIO Y CONSUMO
    # =========================================================================

    def get_consumption(self) -> Dict[str, Optional[float]]:
        """
        Indicadores de comercio y consumo

        Returns:
            Dict con ventas comercio, autos
        """
        series = {
            'ventas_comercio_idx': BCChSeries.VENTAS_COMERCIO_MES,
            'ventas_comercio_yoy': BCChSeries.VENTAS_COMERCIO_YOY,
            'ventas_autos': BCChSeries.VENTAS_AUTOS,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # COMERCIO EXTERIOR
    # =========================================================================

    def get_trade(self) -> Dict[str, Optional[float]]:
        """
        Comercio exterior

        Returns:
            Dict con exportaciones, importaciones, imp bienes capital
        """
        series = {
            'exportaciones_musd': BCChSeries.EXPORTACIONES,
            'importaciones_musd': BCChSeries.IMPORTACIONES,
            'imp_capital_musd': BCChSeries.IMP_CAPITAL,
        }
        data = self._fetch_multiple(series)

        # Calcular balanza
        if data['exportaciones_musd'] and data['importaciones_musd']:
            data['balanza_musd'] = round(data['exportaciones_musd'] - data['importaciones_musd'], 1)
        else:
            data['balanza_musd'] = None

        return data

    # =========================================================================
    # CURVA SPC
    # =========================================================================

    def get_spc_curve(self) -> Dict[str, Optional[float]]:
        """
        Curva Swap Promedio Camara completa

        Returns:
            Dict con tasas por tenor
        """
        series = {
            '30d': BCChSeries.SPC_30D,
            '90d': BCChSeries.SPC_90D,
            '180d': BCChSeries.SPC_180D,
            '1y': BCChSeries.SPC_360D,
            '2y': BCChSeries.SPC_2Y,
            '3y': BCChSeries.SPC_3Y,
            '5y': BCChSeries.SPC_5Y,
            '10y': BCChSeries.SPC_10Y,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # TASAS SISTEMA FINANCIERO
    # =========================================================================

    def get_banking_rates(self) -> Dict[str, Optional[float]]:
        """
        Tasas del sistema financiero

        Returns:
            Dict con tasas consumo, vivienda, comercial
        """
        series = {
            'tasa_consumo': BCChSeries.TASA_CONSUMO,
            'tasa_vivienda_uf': BCChSeries.TASA_VIVIENDA,
            'tasa_comercial_30d': BCChSeries.TASA_COMERCIAL_30D,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # COLOCACIONES (CREDITO)
    # =========================================================================

    def get_credit(self) -> Dict[str, Optional[float]]:
        """
        Stock de colocaciones por tipo

        Returns:
            Dict con colocaciones total, comercial, consumo, vivienda (miles de MM CLP)
        """
        series = {
            'coloc_total': BCChSeries.COLOC_TOTAL,
            'coloc_comercial': BCChSeries.COLOC_COMERCIAL,
            'coloc_consumo': BCChSeries.COLOC_CONSUMO,
            'coloc_vivienda': BCChSeries.COLOC_VIVIENDA,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # COMMODITIES
    # =========================================================================

    def get_commodities(self) -> Dict[str, Optional[float]]:
        """
        Precios de commodities

        Returns:
            Dict con cobre, oro, plata, petroleo, litio, gas
        """
        series = {
            'cobre_usd_lb': BCChSeries.COBRE,
            'oro_usd_oz': BCChSeries.ORO,
            'plata_usd_oz': BCChSeries.PLATA,
            'wti_usd_bbl': BCChSeries.WTI,
            'brent_usd_bbl': BCChSeries.BRENT,
            'litio_usd_kg': BCChSeries.LITIO,
            'gas_natural': BCChSeries.GAS_NATURAL,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # VOLATILIDAD Y RIESGO
    # =========================================================================

    def get_volatility(self) -> Dict[str, Optional[float]]:
        """
        Indices de volatilidad y riesgo

        Returns:
            Dict con VIX, MOVE, EPU por region
        """
        series = {
            'vix': BCChSeries.VIX,
            'move': BCChSeries.MOVE,
            'epu_chile': BCChSeries.EPU_CHILE,
            'epu_usa': BCChSeries.EPU_USA,
            'epu_china': BCChSeries.EPU_CHINA,
            'epu_europa': BCChSeries.EPU_EUROPA,
            'epu_global': BCChSeries.EPU_GLOBAL,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # BOLSAS
    # =========================================================================

    def get_stock_indices(self) -> Dict[str, Optional[float]]:
        """
        Indices bursatiles

        Returns:
            Dict con IPSA, S&P500, Nasdaq, DAX, Shanghai, Bovespa
        """
        series = {
            'ipsa': BCChSeries.IPSA,
            'sp500': BCChSeries.SP500,
            'nasdaq': BCChSeries.NASDAQ,
            'dax': BCChSeries.DAX,
            'shanghai': BCChSeries.SHANGHAI,
            'bovespa': BCChSeries.BOVESPA,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # INFLACION INTERNACIONAL
    # =========================================================================

    def get_international_inflation(self) -> Dict[str, Optional[float]]:
        """
        Inflacion YoY por pais

        Returns:
            Dict con inflacion de principales paises
        """
        series = {
            'usa': BCChSeries.IPC_INTL_USA,
            'eurozona': BCChSeries.IPC_INTL_EUROZONA,
            'china': BCChSeries.IPC_INTL_CHINA,
            'japon': BCChSeries.IPC_INTL_JAPON,
            'uk': BCChSeries.IPC_INTL_UK,
            'brasil': BCChSeries.IPC_INTL_BRASIL,
            'mexico': BCChSeries.IPC_INTL_MEXICO,
            'argentina': BCChSeries.IPC_INTL_ARGENTINA,
            'peru': BCChSeries.IPC_INTL_PERU,
            'colombia': BCChSeries.IPC_INTL_COLOMBIA,
        }
        return self._fetch_multiple(series)

    def get_international_core_inflation(self) -> Dict[str, Optional[float]]:
        """
        Inflacion core YoY por pais

        Returns:
            Dict con inflacion core de principales paises
        """
        series = {
            'usa': BCChSeries.CORE_INTL_USA,
            'eurozona': BCChSeries.CORE_INTL_EUROZONA,
            'china': BCChSeries.CORE_INTL_CHINA,
            'japon': BCChSeries.CORE_INTL_JAPON,
            'uk': BCChSeries.CORE_INTL_UK,
            'brasil': BCChSeries.CORE_INTL_BRASIL,
            'mexico': BCChSeries.CORE_INTL_MEXICO,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # BONOS 10Y INTERNACIONAL
    # =========================================================================

    def get_international_bonds(self) -> Dict[str, Optional[float]]:
        """
        Yields bonos 10Y por pais

        Returns:
            Dict con yields de bonos soberanos
        """
        series = {
            'usa': BCChSeries.BOND10_USA,
            'eurozona': BCChSeries.BOND10_EUROZONA,
            'japon': BCChSeries.BOND10_JAPON,
            'uk': BCChSeries.BOND10_UK,
            'chile': BCChSeries.BOND10_CHILE,
            'brasil': BCChSeries.BOND10_BRASIL,
            'mexico': BCChSeries.BOND10_MEXICO,
            'peru': BCChSeries.BOND10_PERU,
            'colombia': BCChSeries.BOND10_COLOMBIA,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # TPM INTERNACIONAL
    # =========================================================================

    def get_international_policy_rates(self) -> Dict[str, Optional[float]]:
        """
        Tasas de politica monetaria por pais

        Returns:
            Dict con TPM de principales bancos centrales
        """
        series = {
            'usa': BCChSeries.TPM_USA,
            'eurozona': BCChSeries.TPM_EUROZONA,
            'japon': BCChSeries.TPM_JAPON,
            'uk': BCChSeries.TPM_UK,
            'china': BCChSeries.TPM_CHINA,
            'chile': BCChSeries.TPM,
            'brasil': BCChSeries.TPM_BRASIL,
            'mexico': BCChSeries.TPM_MEXICO,
            'peru': BCChSeries.TPM_PERU,
            'colombia': BCChSeries.TPM_COLOMBIA,
            'argentina': BCChSeries.TPM_ARGENTINA,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # GDP INTERNACIONAL
    # =========================================================================

    def get_international_gdp(self) -> Dict[str, Optional[float]]:
        """
        GDP QoQ % por pais (datos trimestrales)

        Returns:
            Dict con GDP de principales paises
        """
        series = {
            'eurozona': BCChSeries.GDP_EUROZONA,
            'alemania': BCChSeries.GDP_ALEMANIA,
            'uk': BCChSeries.GDP_UK,
            'japon': BCChSeries.GDP_JAPON,
            'china': BCChSeries.GDP_CHINA,
        }
        result = {}
        for name, series_id in series.items():
            result[name] = self.get_latest(series_id, days_back=400)
        return result

    # =========================================================================
    # DESEMPLEO INTERNACIONAL
    # =========================================================================

    def get_international_unemployment(self) -> Dict[str, Optional[float]]:
        """
        Tasa de desempleo por pais (%)

        Returns:
            Dict con desempleo de principales paises
        """
        series = {
            'eurozona': BCChSeries.DESEMP_EUROZONA,
            'alemania': BCChSeries.DESEMP_ALEMANIA,
            'uk': BCChSeries.DESEMP_UK,
            'japon': BCChSeries.DESEMP_JAPON,
            'china': BCChSeries.DESEMP_CHINA,
        }
        return self._fetch_multiple(series)

    # =========================================================================
    # DASHBOARDS CONSOLIDADOS
    # =========================================================================

    def get_full_chile_dashboard(self) -> Dict[str, Any]:
        """
        Dashboard completo de Chile

        Returns:
            Dict con todas las categorias Chile
        """
        return {
            'macro': self.get_chile_macro(),
            'sectoral': self.get_sectoral_activity(),
            'consumption': self.get_consumption(),
            'trade': self.get_trade(),
            'spc_curve': self.get_spc_curve(),
            'banking_rates': self.get_banking_rates(),
            'credit': self.get_credit(),
        }

    def get_full_international_dashboard(self) -> Dict[str, Any]:
        """
        Dashboard internacional para comparativos

        Returns:
            Dict con inflacion, core, bonos, TPM por pais
        """
        return {
            'inflation': self.get_international_inflation(),
            'core_inflation': self.get_international_core_inflation(),
            'bonds_10y': self.get_international_bonds(),
            'policy_rates': self.get_international_policy_rates(),
            'gdp': self.get_international_gdp(),
            'unemployment': self.get_international_unemployment(),
        }

    def get_market_dashboard(self) -> Dict[str, Any]:
        """
        Dashboard de mercados (commodities, volatilidad, bolsas)

        Returns:
            Dict con commodities, volatilidad, indices bursatiles
        """
        return {
            'commodities': self.get_commodities(),
            'volatility': self.get_volatility(),
            'stock_indices': self.get_stock_indices(),
        }


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("BCCh Extended Client - Test")
    print("=" * 60)

    client = BCChExtendedClient()

    print("\n--- Chile Macro ---")
    macro = client.get_chile_macro()
    for k, v in macro.items():
        print(f"  {k}: {v}")

    print("\n--- Commodities ---")
    comm = client.get_commodities()
    for k, v in comm.items():
        print(f"  {k}: {v}")

    print("\n--- TPM Internacional ---")
    tpm = client.get_international_policy_rates()
    for k, v in tpm.items():
        print(f"  {k}: {v}%")

    print("\n--- GDP Internacional ---")
    gdp = client.get_international_gdp()
    for k, v in gdp.items():
        print(f"  {k}: {v}%")

    print("\n--- Desempleo Internacional ---")
    desemp = client.get_international_unemployment()
    for k, v in desemp.items():
        print(f"  {k}: {v}%")

    print("\n--- OK ---")
