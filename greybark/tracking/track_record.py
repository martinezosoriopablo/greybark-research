"""
Greybark Research - Track Record System
Mejora #11 del AI Council

System for tracking and evaluating investment recommendations:
- Record recommendations with timestamps
- Calculate hit rates and returns
- Generate performance attribution
- Store persistent track record

Storage: JSON file-based for simplicity
Can be upgraded to SQLite/PostgreSQL for production

Author: Greybark Research
Date: January 2026
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd
import numpy as np


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class RecommendationType(Enum):
    """Types of recommendations"""
    ASSET_ALLOCATION = "asset_allocation"
    SECTOR = "sector"
    STOCK = "stock"
    DURATION = "duration"
    CREDIT = "credit"
    FX = "fx"
    REGIME = "regime"


class RecommendationDirection(Enum):
    """Direction of recommendation"""
    OVERWEIGHT = "overweight"
    UNDERWEIGHT = "underweight"
    NEUTRAL = "neutral"
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class RecommendationStatus(Enum):
    """Status of recommendation"""
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


@dataclass
class Recommendation:
    """Individual recommendation record"""
    id: str
    timestamp: str
    type: str                      # RecommendationType
    direction: str                 # RecommendationDirection
    target: str                    # What is being recommended (ticker, sector, etc.)
    rationale: str
    entry_price: Optional[float]
    target_price: Optional[float]
    stop_price: Optional[float]
    horizon_days: int
    confidence: str                # HIGH, MEDIUM, LOW
    status: str                    # RecommendationStatus
    
    # Outcome fields (filled when closed)
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    return_pct: Optional[float] = None
    outcome: Optional[str] = None  # WIN, LOSS, NEUTRAL


@dataclass
class TrackRecordSummary:
    """Summary statistics of track record"""
    total_recommendations: int
    active_recommendations: int
    closed_recommendations: int
    hit_rate: float                # % of winning recommendations
    avg_return: float              # Average return of closed recs
    avg_holding_period: float      # Days
    best_recommendation: Optional[Dict]
    worst_recommendation: Optional[Dict]
    by_type: Dict[str, Dict]       # Stats by recommendation type


# =============================================================================
# MAIN CLASS
# =============================================================================

class TrackRecordSystem:
    """
    Track Record System
    
    Records and evaluates investment recommendations:
    - Add new recommendations
    - Update with outcomes
    - Calculate performance metrics
    - Generate attribution reports
    
    Usage:
        tracker = TrackRecordSystem()
        
        # Add recommendation
        tracker.add_recommendation(
            type='sector',
            direction='overweight',
            target='XLK',
            rationale='Tech momentum strong',
            entry_price=200.0,
            target_price=220.0,
            horizon_days=90
        )
        
        # Close recommendation
        tracker.close_recommendation(rec_id, exit_price=215.0)
        
        # Get summary
        summary = tracker.get_track_record_summary()
    """
    
    def __init__(self, storage_path: str = None):
        """
        Initialize track record system
        
        Args:
            storage_path: Path to JSON storage file
        """
        if storage_path is None:
            # Default to home directory
            storage_path = os.path.expanduser("~/.greybark_track_record.json")
        
        self.storage_path = storage_path
        self.recommendations: List[Recommendation] = []
        
        # Load existing data
        self._load()
    
    # =========================================================================
    # STORAGE
    # =========================================================================
    
    def _load(self):
        """Load recommendations from storage"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.recommendations = [
                        Recommendation(**rec) for rec in data.get('recommendations', [])
                    ]
                print(f"[TrackRecord] Loaded {len(self.recommendations)} recommendations")
            except Exception as e:
                print(f"[TrackRecord] Error loading: {e}")
                self.recommendations = []
        else:
            self.recommendations = []
    
    def _save(self):
        """Save recommendations to storage"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'recommendations': [asdict(rec) for rec in self.recommendations]
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[TrackRecord] Error saving: {e}")
    
    # =========================================================================
    # RECOMMENDATION MANAGEMENT
    # =========================================================================
    
    def add_recommendation(self,
                           type: str,
                           direction: str,
                           target: str,
                           rationale: str,
                           entry_price: float = None,
                           target_price: float = None,
                           stop_price: float = None,
                           horizon_days: int = 90,
                           confidence: str = 'MEDIUM') -> str:
        """
        Add a new recommendation
        
        Args:
            type: Type of recommendation (sector, stock, duration, etc.)
            direction: overweight, underweight, buy, sell, etc.
            target: What is being recommended (XLK, AAPL, etc.)
            rationale: Reason for recommendation
            entry_price: Current/entry price
            target_price: Price target
            stop_price: Stop loss price
            horizon_days: Investment horizon
            confidence: HIGH, MEDIUM, LOW
        
        Returns:
            Recommendation ID
        """
        # Generate unique ID
        rec_id = f"{type[:3].upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        rec = Recommendation(
            id=rec_id,
            timestamp=datetime.now().isoformat(),
            type=type,
            direction=direction,
            target=target,
            rationale=rationale,
            entry_price=entry_price,
            target_price=target_price,
            stop_price=stop_price,
            horizon_days=horizon_days,
            confidence=confidence,
            status=RecommendationStatus.ACTIVE.value
        )
        
        self.recommendations.append(rec)
        self._save()
        
        print(f"[TrackRecord] Added recommendation: {rec_id}")
        print(f"  Type: {type}, Direction: {direction}, Target: {target}")
        
        return rec_id
    
    def close_recommendation(self,
                             rec_id: str,
                             exit_price: float = None,
                             outcome: str = None) -> bool:
        """
        Close a recommendation with outcome
        
        Args:
            rec_id: Recommendation ID
            exit_price: Exit/closing price
            outcome: WIN, LOSS, NEUTRAL (auto-calculated if not provided)
        
        Returns:
            Success status
        """
        for rec in self.recommendations:
            if rec.id == rec_id and rec.status == RecommendationStatus.ACTIVE.value:
                rec.exit_timestamp = datetime.now().isoformat()
                rec.exit_price = exit_price
                rec.status = RecommendationStatus.CLOSED.value
                
                # Calculate return
                if rec.entry_price and exit_price:
                    if rec.direction in ['overweight', 'buy']:
                        rec.return_pct = (exit_price / rec.entry_price - 1) * 100
                    elif rec.direction in ['underweight', 'sell']:
                        rec.return_pct = (rec.entry_price / exit_price - 1) * 100
                    else:
                        rec.return_pct = 0
                
                # Determine outcome
                if outcome:
                    rec.outcome = outcome
                elif rec.return_pct is not None:
                    if rec.return_pct > 1:
                        rec.outcome = 'WIN'
                    elif rec.return_pct < -1:
                        rec.outcome = 'LOSS'
                    else:
                        rec.outcome = 'NEUTRAL'
                
                self._save()
                print(f"[TrackRecord] Closed {rec_id}: {rec.return_pct:+.1f}% ({rec.outcome})")
                return True
        
        print(f"[TrackRecord] Recommendation {rec_id} not found or already closed")
        return False
    
    def expire_old_recommendations(self):
        """Mark expired recommendations based on horizon"""
        now = datetime.now()
        expired_count = 0
        
        for rec in self.recommendations:
            if rec.status == RecommendationStatus.ACTIVE.value:
                rec_date = datetime.fromisoformat(rec.timestamp)
                if (now - rec_date).days > rec.horizon_days:
                    rec.status = RecommendationStatus.EXPIRED.value
                    rec.exit_timestamp = now.isoformat()
                    expired_count += 1
        
        if expired_count > 0:
            self._save()
            print(f"[TrackRecord] Expired {expired_count} recommendations")
    
    # =========================================================================
    # QUERYING
    # =========================================================================
    
    def get_active_recommendations(self) -> List[Dict]:
        """Get all active recommendations"""
        return [
            asdict(rec) for rec in self.recommendations 
            if rec.status == RecommendationStatus.ACTIVE.value
        ]
    
    def get_recommendations_by_type(self, rec_type: str) -> List[Dict]:
        """Get recommendations by type"""
        return [
            asdict(rec) for rec in self.recommendations 
            if rec.type == rec_type
        ]
    
    def get_closed_recommendations(self, 
                                    days_back: int = None) -> List[Dict]:
        """Get closed recommendations, optionally filtered by time"""
        closed = [
            rec for rec in self.recommendations 
            if rec.status == RecommendationStatus.CLOSED.value
        ]
        
        if days_back:
            cutoff = datetime.now() - timedelta(days=days_back)
            closed = [
                rec for rec in closed 
                if datetime.fromisoformat(rec.exit_timestamp) >= cutoff
            ]
        
        return [asdict(rec) for rec in closed]
    
    # =========================================================================
    # PERFORMANCE ANALYSIS
    # =========================================================================
    
    def get_track_record_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive track record summary
        
        Returns:
            Summary statistics and performance metrics
        """
        print("[TrackRecord] Generating summary...")
        
        total = len(self.recommendations)
        active = [r for r in self.recommendations if r.status == RecommendationStatus.ACTIVE.value]
        closed = [r for r in self.recommendations if r.status == RecommendationStatus.CLOSED.value]
        
        # Calculate metrics for closed recommendations
        wins = [r for r in closed if r.outcome == 'WIN']
        losses = [r for r in closed if r.outcome == 'LOSS']
        
        hit_rate = len(wins) / len(closed) * 100 if closed else 0
        
        returns = [r.return_pct for r in closed if r.return_pct is not None]
        avg_return = np.mean(returns) if returns else 0
        
        # Holding periods
        holding_periods = []
        for r in closed:
            if r.exit_timestamp and r.timestamp:
                entry = datetime.fromisoformat(r.timestamp)
                exit = datetime.fromisoformat(r.exit_timestamp)
                holding_periods.append((exit - entry).days)
        
        avg_holding = np.mean(holding_periods) if holding_periods else 0
        
        # Best and worst
        if returns:
            best_idx = np.argmax(returns)
            worst_idx = np.argmin(returns)
            best = asdict(closed[best_idx])
            worst = asdict(closed[worst_idx])
        else:
            best = None
            worst = None
        
        # By type
        by_type = {}
        types = set(r.type for r in self.recommendations)
        
        for t in types:
            type_recs = [r for r in closed if r.type == t]
            type_wins = [r for r in type_recs if r.outcome == 'WIN']
            type_returns = [r.return_pct for r in type_recs if r.return_pct is not None]
            
            by_type[t] = {
                'total': len([r for r in self.recommendations if r.type == t]),
                'closed': len(type_recs),
                'hit_rate': len(type_wins) / len(type_recs) * 100 if type_recs else 0,
                'avg_return': np.mean(type_returns) if type_returns else 0
            }
        
        return {
            'total_recommendations': total,
            'active_recommendations': len(active),
            'closed_recommendations': len(closed),
            'expired_recommendations': len([r for r in self.recommendations if r.status == 'expired']),
            'hit_rate_pct': round(hit_rate, 1),
            'avg_return_pct': round(avg_return, 2),
            'avg_holding_period_days': round(avg_holding, 1),
            'total_wins': len(wins),
            'total_losses': len(losses),
            'best_recommendation': best,
            'worst_recommendation': worst,
            'by_type': by_type,
            'as_of': datetime.now().isoformat()
        }
    
    def get_performance_attribution(self) -> Dict[str, Any]:
        """
        Get performance attribution by various dimensions
        
        Returns:
            Attribution analysis
        """
        closed = [r for r in self.recommendations if r.status == RecommendationStatus.CLOSED.value]
        
        if not closed:
            return {'error': 'No closed recommendations for attribution'}
        
        attribution = {
            'by_direction': {},
            'by_confidence': {},
            'by_type': {},
            'monthly': {}
        }
        
        # By direction
        for direction in ['overweight', 'underweight', 'buy', 'sell', 'neutral']:
            dir_recs = [r for r in closed if r.direction == direction]
            if dir_recs:
                returns = [r.return_pct for r in dir_recs if r.return_pct is not None]
                wins = [r for r in dir_recs if r.outcome == 'WIN']
                attribution['by_direction'][direction] = {
                    'count': len(dir_recs),
                    'avg_return': round(np.mean(returns), 2) if returns else 0,
                    'hit_rate': round(len(wins) / len(dir_recs) * 100, 1)
                }
        
        # By confidence
        for conf in ['HIGH', 'MEDIUM', 'LOW']:
            conf_recs = [r for r in closed if r.confidence == conf]
            if conf_recs:
                returns = [r.return_pct for r in conf_recs if r.return_pct is not None]
                wins = [r for r in conf_recs if r.outcome == 'WIN']
                attribution['by_confidence'][conf] = {
                    'count': len(conf_recs),
                    'avg_return': round(np.mean(returns), 2) if returns else 0,
                    'hit_rate': round(len(wins) / len(conf_recs) * 100, 1)
                }
        
        # Monthly
        for rec in closed:
            if rec.exit_timestamp:
                month = datetime.fromisoformat(rec.exit_timestamp).strftime('%Y-%m')
                if month not in attribution['monthly']:
                    attribution['monthly'][month] = {'count': 0, 'returns': []}
                attribution['monthly'][month]['count'] += 1
                if rec.return_pct is not None:
                    attribution['monthly'][month]['returns'].append(rec.return_pct)
        
        # Calculate monthly averages
        for month, data in attribution['monthly'].items():
            data['avg_return'] = round(np.mean(data['returns']), 2) if data['returns'] else 0
            del data['returns']  # Remove raw data
        
        return attribution
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    def generate_report(self) -> str:
        """Generate text report of track record"""
        summary = self.get_track_record_summary()
        
        report = []
        report.append("=" * 60)
        report.append("GREYBARK RESEARCH - TRACK RECORD REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("=" * 60)
        
        report.append(f"\nTOTAL RECOMMENDATIONS: {summary['total_recommendations']}")
        report.append(f"  Active: {summary['active_recommendations']}")
        report.append(f"  Closed: {summary['closed_recommendations']}")
        report.append(f"  Expired: {summary['expired_recommendations']}")
        
        report.append(f"\nPERFORMANCE METRICS:")
        report.append(f"  Hit Rate: {summary['hit_rate_pct']:.1f}%")
        report.append(f"  Avg Return: {summary['avg_return_pct']:+.2f}%")
        report.append(f"  Avg Holding Period: {summary['avg_holding_period_days']:.0f} days")
        report.append(f"  Wins/Losses: {summary['total_wins']}/{summary['total_losses']}")
        
        if summary['by_type']:
            report.append(f"\nBY TYPE:")
            for type_name, stats in summary['by_type'].items():
                report.append(f"  {type_name}: {stats['hit_rate']:.1f}% hit rate, {stats['avg_return']:+.2f}% avg")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GREY BARK - TRACK RECORD SYSTEM TEST")
    print("=" * 60)
    
    tracker = TrackRecordSystem()
    
    print("\n--- Available Methods ---")
    print("  • add_recommendation(type, direction, target, ...)")
    print("  • close_recommendation(rec_id, exit_price)")
    print("  • get_active_recommendations()")
    print("  • get_track_record_summary()")
    print("  • get_performance_attribution()")
    print("  • generate_report()")
    
    print("\n--- Storage ---")
    print(f"  Location: {tracker.storage_path}")
    print(f"  Recommendations loaded: {len(tracker.recommendations)}")
    
    print("\n✅ Track Record System module loaded successfully")
