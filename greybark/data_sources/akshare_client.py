# -*- coding: utf-8 -*-
"""
Grey Bark - AKShare Client
China Monthly Macro Data via NBS / Eastmoney / Investing.com

Covers: PMI, CPI, PPI, M2, TSF, LPR, RRR, Trade, Property, Industrial Production
"""
import logging
from typing import Dict, Optional

import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None  # type: ignore
    raise ImportError("Please install akshare: pip install akshare")

logger = logging.getLogger(__name__)


class AKShareClient:
    """Client for China macro data via AKShare (NBS, Eastmoney, Investing.com)."""

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #
    def _fetch_investing_style(self, func_name: str) -> Optional[Dict]:
        """
        Fetch data from AKShare functions that return investing.com-style
        columns: [商品, 日期, 今值, 预测值, 前值].
        Returns {'value': float, 'previous': float, 'date': str} or None.
        """
        try:
            fn = getattr(ak, func_name)
            df = fn()
            if df is None or df.empty:
                return None
            df = df.dropna(subset=["今值"])
            if df.empty:
                return None
            row = df.iloc[-1]
            result: Dict = {}
            result["value"] = self._safe_float(row.get("今值"))
            prev = row.get("前值")
            if pd.notna(prev):
                result["previous"] = self._safe_float(prev)
            else:
                result["previous"] = None
            result["date"] = str(row.get("日期", ""))
            return result
        except Exception as e:
            logger.warning("AKShare %s failed: %s", func_name, e)
            return None

    @staticmethod
    def _safe_float(v) -> Optional[float]:
        if pd.isna(v):
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------ #
    #  PMI                                                                #
    # ------------------------------------------------------------------ #
    def get_pmi(self) -> Dict:
        """NBS Official + Caixin PMI (Manufacturing + Services)."""
        result: Dict = {}
        # NBS Manufacturing PMI
        d = self._fetch_investing_style("macro_china_pmi_yearly")
        if d:
            result["pmi_mfg"] = d.get("value")
            result["pmi_mfg_prev"] = d.get("previous")

        # NBS Non-Manufacturing (Services) PMI
        d = self._fetch_investing_style("macro_china_non_man_pmi")
        if d:
            result["pmi_svc"] = d.get("value")
            result["pmi_svc_prev"] = d.get("previous")

        # Caixin Manufacturing PMI
        d = self._fetch_investing_style("macro_china_cx_pmi_yearly")
        if d:
            result["caixin_mfg"] = d.get("value")
            result["caixin_mfg_prev"] = d.get("previous")

        # Caixin Services PMI
        d = self._fetch_investing_style("macro_china_cx_services_pmi_yearly")
        if d:
            result["caixin_svc"] = d.get("value")
            result["caixin_svc_prev"] = d.get("previous")

        return result

    # ------------------------------------------------------------------ #
    #  Prices (CPI / PPI)                                                 #
    # ------------------------------------------------------------------ #
    def get_prices(self) -> Dict:
        """CPI and PPI YoY."""
        result: Dict = {}
        d = self._fetch_investing_style("macro_china_cpi_yearly")
        if d:
            result["cpi_yoy"] = d.get("value")
            result["cpi_yoy_prev"] = d.get("previous")

        d = self._fetch_investing_style("macro_china_ppi_yearly")
        if d:
            result["ppi_yoy"] = d.get("value")
            result["ppi_yoy_prev"] = d.get("previous")

        return result

    # ------------------------------------------------------------------ #
    #  Money & Credit                                                     #
    # ------------------------------------------------------------------ #
    def get_money_credit(self) -> Dict:
        """M2 YoY and TSF (Social Financing)."""
        result: Dict = {}
        # M2
        d = self._fetch_investing_style("macro_china_m2_yearly")
        if d:
            result["m2_yoy"] = d.get("value")
            result["m2_yoy_prev"] = d.get("previous")

        # TSF + New Loans (different format: raw table)
        try:
            df = ak.macro_china_shrzgm()
            if df is not None and not df.empty:
                row = df.iloc[-1]
                result["tsf"] = self._safe_float(row.get("社会融资规模增量"))
                result["new_loans"] = self._safe_float(row.get("其中-人民币贷款"))
                if len(df) >= 2:
                    prev = df.iloc[-2]
                    result["tsf_prev"] = self._safe_float(prev.get("社会融资规模增量"))
                    result["new_loans_prev"] = self._safe_float(prev.get("其中-人民币贷款"))
        except Exception as e:
            logger.warning("AKShare TSF failed: %s", e)

        return result

    # ------------------------------------------------------------------ #
    #  Trade                                                              #
    # ------------------------------------------------------------------ #
    def get_trade(self) -> Dict:
        """Exports YoY, Imports YoY, Trade Balance (USD bn)."""
        result: Dict = {}
        d = self._fetch_investing_style("macro_china_exports_yoy")
        if d:
            result["exp_yoy"] = d.get("value")
            result["exp_yoy_prev"] = d.get("previous")

        d = self._fetch_investing_style("macro_china_imports_yoy")
        if d:
            result["imp_yoy"] = d.get("value")
            result["imp_yoy_prev"] = d.get("previous")

        d = self._fetch_investing_style("macro_china_trade_balance")
        if d:
            result["trade_bal"] = d.get("value")
            result["trade_bal_prev"] = d.get("previous")

        return result

    # ------------------------------------------------------------------ #
    #  Policy Rates                                                       #
    # ------------------------------------------------------------------ #
    def get_policy_rates(self) -> Dict:
        """LPR 1Y/5Y and RRR (large banks)."""
        result: Dict = {}

        # LPR
        try:
            df = ak.macro_china_lpr()
            if df is not None and not df.empty:
                row = df.iloc[-1]
                result["lpr_1y"] = self._safe_float(row.get("LPR1Y"))
                result["lpr_5y"] = self._safe_float(row.get("LPR5Y"))
                if len(df) >= 2:
                    prev = df.iloc[-2]
                    result["lpr_1y_prev"] = self._safe_float(prev.get("LPR1Y"))
                    result["lpr_5y_prev"] = self._safe_float(prev.get("LPR5Y"))
        except Exception as e:
            logger.warning("AKShare LPR failed: %s", e)

        # RRR
        try:
            df = ak.macro_china_reserve_requirement_ratio()
            if df is not None and not df.empty:
                row = df.iloc[0]  # Most recent is first row
                result["rrr"] = self._safe_float(row.get("大型金融机构-调整后"))
                if len(df) >= 2:
                    result["rrr_prev"] = self._safe_float(df.iloc[1].get("大型金融机构-调整后"))
        except Exception as e:
            logger.warning("AKShare RRR failed: %s", e)

        return result

    # ------------------------------------------------------------------ #
    #  Property                                                           #
    # ------------------------------------------------------------------ #
    def get_property(self) -> Dict:
        """New house price indices (70-city avg or Tier 1 cities)."""
        result: Dict = {}
        try:
            df = ak.macro_china_new_house_price()
            if df is not None and not df.empty:
                # Latest date
                max_date = df["日期"].max()
                latest = df[df["日期"] == max_date]

                # Beijing (同比 is index base 100, convert to YoY%)
                bj = latest[latest["城市"] == "北京"]
                if not bj.empty:
                    v = self._safe_float(bj.iloc[0].get("新建商品住宅价格指数-同比"))
                    result["home_price_yoy_bj"] = round(v - 100, 1) if v is not None else None

                # Shanghai
                sh = latest[latest["城市"] == "上海"]
                if not sh.empty:
                    v = self._safe_float(sh.iloc[0].get("新建商品住宅价格指数-同比"))
                    result["home_price_yoy_sh"] = round(v - 100, 1) if v is not None else None

                # Tier 1 average (Beijing, Shanghai, Guangzhou, Shenzhen)
                tier1_cities = ["北京", "上海", "广州", "深圳"]
                tier1 = latest[latest["城市"].isin(tier1_cities)]
                if not tier1.empty:
                    yoy_vals = []
                    for _, row in tier1.iterrows():
                        v = self._safe_float(row.get("新建商品住宅价格指数-同比"))
                        if v is not None:
                            yoy_vals.append(v - 100)  # index → YoY%
                    if yoy_vals:
                        result["home_price_yoy_tier1"] = round(
                            sum(yoy_vals) / len(yoy_vals), 1
                        )

                # Previous month for tier1
                dates = sorted(df["日期"].unique())
                if len(dates) >= 2:
                    prev_date = dates[-2]
                    prev_df = df[df["日期"] == prev_date]
                    prev_tier1 = prev_df[prev_df["城市"].isin(tier1_cities)]
                    if not prev_tier1.empty:
                        prev_vals = []
                        for _, row in prev_tier1.iterrows():
                            v = self._safe_float(row.get("新建商品住宅价格指数-同比"))
                            if v is not None:
                                prev_vals.append(v - 100)  # index → YoY%
                        if prev_vals:
                            result["home_price_yoy_tier1_prev"] = round(
                                sum(prev_vals) / len(prev_vals), 1
                            )
        except Exception as e:
            logger.warning("AKShare property failed: %s", e)

        return result

    # ------------------------------------------------------------------ #
    #  Activity                                                           #
    # ------------------------------------------------------------------ #
    def get_activity(self) -> Dict:
        """Industrial Production YoY and Retail Sales YoY."""
        result: Dict = {}

        # Industrial Production
        d = self._fetch_investing_style("macro_china_industrial_production_yoy")
        if d:
            result["industrial_prod_yoy"] = d.get("value")
            result["industrial_prod_yoy_prev"] = d.get("previous")

        # Retail Sales (different format)
        try:
            df = ak.macro_china_consumer_goods_retail()
            if df is not None and not df.empty:
                df = df.dropna(subset=["同比增长"])
                if not df.empty and len(df) >= 2:
                    # Data is reverse-chronological in some versions
                    row = df.iloc[0]
                    result["retail_sales_yoy"] = self._safe_float(row.get("同比增长"))
                    if len(df) >= 2:
                        result["retail_sales_yoy_prev"] = self._safe_float(
                            df.iloc[1].get("同比增长")
                        )
        except Exception as e:
            logger.warning("AKShare retail sales failed: %s", e)

        return result

    # ------------------------------------------------------------------ #
    #  Combined                                                           #
    # ------------------------------------------------------------------ #
    def get_china_monthly(self) -> Dict:
        """
        Fetch all China monthly indicators in one call.

        Returns dict with keys:
            PMI: pmi_mfg, pmi_svc, caixin_mfg, caixin_svc (+ _prev)
            Prices: cpi_yoy, ppi_yoy (+ _prev)
            Money: m2_yoy, tsf, new_loans (+ _prev)
            Trade: exp_yoy, imp_yoy, trade_bal (+ _prev)
            Policy: lpr_1y, lpr_5y, rrr (+ _prev)
            Property: home_price_yoy_tier1, home_price_yoy_bj/sh (+ _prev)
            Activity: industrial_prod_yoy, retail_sales_yoy (+ _prev)
        """
        result: Dict = {}
        fetchers = [
            ("get_pmi", self.get_pmi),
            ("get_prices", self.get_prices),
            ("get_money_credit", self.get_money_credit),
            ("get_trade", self.get_trade),
            ("get_policy_rates", self.get_policy_rates),
            ("get_property", self.get_property),
            ("get_activity", self.get_activity),
        ]
        for name, fn in fetchers:
            try:
                result.update(fn())
            except Exception as e:
                logger.warning("AKShare %s failed: %s", name, e)

        return result
