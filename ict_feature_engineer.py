"""
ICT FEATURE ENGINEERING MODULE
Quantitative extraction of ICT concepts from market data
Created by: ICT Concept Auditor
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import talib
from scipy import stats
from scipy.signal import find_peaks
import warnings
warnings.filterwarnings('ignore')

class MarketStructure(Enum):
    UPTREND = "Higher Highs Higher Lows"
    DOWNTREND = "Lower Highs Lower Lows"
    RANGE = "Ranging"
    STRUCTURE_SHIFT = "Market Structure Shift"

@dataclass
class SwingPoint:
    timestamp: datetime
    price: float
    point_type: str  # 'high' or 'low'
    strength: float
    index: int

@dataclass
class LiquidityLevel:
    price: float
    timestamp: datetime
    level_type: str  # 'buy_side' or 'sell_side'
    strength: float
    touched_count: int
    swept: bool

@dataclass
class FairValueGap:
    high: float
    low: float
    timestamp: datetime
    gap_type: str  # 'bullish' or 'bearish'
    size: float
    filled: bool
    fill_time: Optional[datetime]
    reaction_strength: float

@dataclass
class OrderBlock:
    high: float
    low: float
    timestamp: datetime
    block_type: str  # 'bullish' or 'bearish'
    strength: float
    mitigated: bool
    mitigation_time: Optional[datetime]

class ICTFeatureEngineer:
    """Extract and quantify ICT concepts from market data"""
    
    def __init__(self, min_swing_strength: float = 0.02):
        self.min_swing_strength = min_swing_strength
        self.swing_points: List[SwingPoint] = []
        self.liquidity_levels: List[LiquidityLevel] = []
        self.fvg_history: List[FairValueGap] = []
        self.order_blocks: List[OrderBlock] = []
        
    def extract_all_features(self, df: pd.DataFrame) -> Dict:
        """Extract all ICT features from price data"""
        
        features = {}
        
        # 1. Market Structure Analysis
        features['market_structure'] = self._analyze_market_structure(df)
        
        # 2. Liquidity Analysis
        features['liquidity'] = self._analyze_liquidity(df)
        
        # 3. Fair Value Gap Analysis
        features['fvg'] = self._analyze_fair_value_gaps(df)
        
        # 4. Order Block Analysis
        features['order_blocks'] = self._analyze_order_blocks(df)
        
        # 5. Premium/Discount Analysis
        features['premium_discount'] = self._analyze_premium_discount(df)
        
        # 6. Session Analysis
        features['sessions'] = self._analyze_sessions(df)
        
        # 7. Power of Three Analysis
        features['power_of_three'] = self._analyze_power_of_three(df)
        
        return features
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> Dict:
        """Comprehensive market structure analysis"""
        
        # Find swing highs and lows
        swing_highs, swing_lows = self._find_swing_points(df)
        
        # Determine current market structure
        current_structure = self._determine_structure_state(df, swing_highs, swing_lows)
        
        # Check for market structure shift
        mss_detected = self._detect_market_structure_shift(df, swing_highs, swing_lows)
        
        # Calculate structure strength metrics
        structure_metrics = self._calculate_structure_metrics(df, swing_highs, swing_lows)
        
        return {
            'current_structure': current_structure,
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'mss_detected': mss_detected,
            'structure_metrics': structure_metrics,
            'trend_strength': structure_metrics['trend_strength'],
            'structure_quality': structure_metrics['quality_score']
        }
    
    def _analyze_liquidity(self, df: pd.DataFrame) -> Dict:
        """Analyze liquidity levels and sweeps"""
        
        # Identify key liquidity levels
        liquidity_levels = self._identify_liquidity_levels(df)
        
        # Detect liquidity sweeps
        sweeps = self._detect_liquidity_sweeps(df, liquidity_levels)
        
        # Calculate liquidity density
        liquidity_density = self._calculate_liquidity_density(df, liquidity_levels)
        
        # Equal highs/lows analysis
        equal_levels = self._find_equal_highs_lows(df)
        
        return {
            'liquidity_levels': liquidity_levels,
            'sweeps': sweeps,
            'liquidity_density': liquidity_density,
            'equal_highs_lows': equal_levels,
            'buy_side_liquidity': [l for l in liquidity_levels if l.level_type == 'buy_side'],
            'sell_side_liquidity': [l for l in liquidity_levels if l.level_type == 'sell_side'],
            'sweep_success_rate': self._calculate_sweep_success_rate(sweeps)
        }
    
    def _analyze_fair_value_gaps(self, df: pd.DataFrame) -> Dict:
        """Analyze Fair Value Gaps (imbalances)"""
        
        # Detect FVGs
        fvg_list = self._detect_fvgs(df)
        
        # Track FVG fills
        filled_fvgs = self._track_fvg_fills(df, fvg_list)
        
        # Calculate FVG metrics
        fvg_metrics = self._calculate_fvg_metrics(fvg_list, filled_fvgs)
        
        # Reaction strength analysis
        reaction_strength = self._analyze_fvg_reactions(df, fvg_list)
        
        return {
            'detected_fvgs': fvg_list,
            'filled_fvgs': filled_fvgs,
            'fill_rate': fvg_metrics['fill_rate'],
            'avg_fvg_size': fvg_metrics['avg_size'],
            'reaction_strength': reaction_strength,
            'partial_fills': fvg_metrics['partial_fills'],
            'time_to_fill': fvg_metrics['avg_time_to_fill']
        }
    
    def _analyze_order_blocks(self, df: pd.DataFrame) -> Dict:
        """Analyze institutional order blocks"""
        
        # Detect order blocks
        ob_list = self._detect_order_blocks(df)
        
        # Track OB mitigation
        mitigated_obs = self._track_ob_mitigation(df, ob_list)
        
        # Calculate OB metrics
        ob_metrics = self._calculate_ob_metrics(ob_list, mitigated_obs)
        
        return {
            'detected_obs': ob_list,
            'mitigated_obs': mitigated_obs,
            'mitigation_rate': ob_metrics['mitigation_rate'],
            'failure_rate': ob_metrics['failure_rate'],
            'avg_ob_strength': ob_metrics['avg_strength'],
            'reaction_quality': ob_metrics['reaction_quality']
        }
    
    def _analyze_premium_discount(self, df: pd.DataFrame) -> Dict:
        """Analyze premium and discount zones"""
        
        # Calculate dealing range
        dealing_range = self._calculate_dealing_range(df)
        
        # Fibonacci equilibrium levels
        fib_levels = self._calculate_fibonacci_levels(df)
        
        # Current zone analysis
        current_zone = self._determine_current_zone(df, dealing_range, fib_levels)
        
        # Zone effectiveness
        zone_effectiveness = self._calculate_zone_effectiveness(df, current_zone)
        
        return {
            'dealing_range': dealing_range,
            'fibonacci_levels': fib_levels,
            'current_zone': current_zone,
            'zone_effectiveness': zone_effectiveness,
            'discount_zone': dealing_range['discount_zone'],
            'premium_zone': dealing_range['premium_zone'],
            'equilibrium': dealing_range['equilibrium']
        }
    
    def _analyze_sessions(self, df: pd.DataFrame) -> Dict:
        """Analyze session-based performance"""
        
        # Identify trading sessions
        sessions = self._identify_sessions(df)
        
        # Session-based volatility
        session_volatility = self._calculate_session_volatility(df, sessions)
        
        # Killzone analysis
        killzones = self._identify_killzones(df, sessions)
        
        return {
            'sessions': sessions,
            'session_volatility': session_volatility,
            'killzones': killzones,
            'session_performance': self._calculate_session_performance(df, sessions),
            'overlapping_sessions': self._find_overlapping_sessions(sessions)
        }
    
    def _analyze_power_of_three(self, df: pd.DataFrame) -> Dict:
        """Analyze Power of Three patterns"""
        
        # Detect PO3 patterns
        po3_patterns = self._detect_po3_patterns(df)
        
        # Phase analysis
        phases = self._analyze_po3_phases(df, po3_patterns)
        
        return {
            'po3_patterns': po3_patterns,
            'accumulation_phases': phases['accumulation'],
            'manipulation_phases': phases['manipulation'],
            'distribution_phases': phases['distribution'],
            'pattern_validity': self._validate_po3_patterns(po3_patterns)
        }
    
    # Helper methods for market structure
    def _find_swing_points(self, df: pd.DataFrame) -> Tuple[List[SwingPoint], List[SwingPoint]]:
        """Find swing highs and lows using peak detection"""
        
        swing_highs = []
        swing_lows = []
        
        # Use scipy for peak detection
        high_peaks, high_properties = find_peaks(df['high'].values, distance=5, prominence=df['high'].std()*0.5)
        low_peaks, low_properties = find_peaks(-df['low'].values, distance=5, prominence=df['low'].std()*0.5)
        
        for peak_idx in high_peaks:
            if peak_idx < len(df):
                swing_highs.append(SwingPoint(
                    timestamp=df.index[peak_idx],
                    price=df.iloc[peak_idx]['high'],
                    point_type='high',
                    strength=high_properties['prominences'][np.where(high_peaks == peak_idx)[0][0]],
                    index=peak_idx
                ))
        
        for peak_idx in low_peaks:
            if peak_idx < len(df):
                swing_lows.append(SwingPoint(
                    timestamp=df.index[peak_idx],
                    price=df.iloc[peak_idx]['low'],
                    point_type='low',
                    strength=low_properties['prominences'][np.where(low_peaks == peak_idx)[0][0]],
                    index=peak_idx
                ))
        
        return swing_highs, swing_lows
    
    def _determine_structure_state(self, df: pd.DataFrame, swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> str:
        """Determine current market structure state"""
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return MarketStructure.RANGE.value
        
        # Get recent swing points
        recent_highs = sorted(swing_highs, key=lambda x: x.timestamp)[-3:]
        recent_lows = sorted(swing_lows, key=lambda x: x.timestamp)[-3:]
        
        current_price = df.iloc[-1]['close']
        
        # Check for higher highs and higher lows
        hh_condition = all(recent_highs[i].price > recent_highs[i-1].price for i in range(1, len(recent_highs)))
        hl_condition = all(recent_lows[i].price > recent_lows[i-1].price for i in range(1, len(recent_lows)))
        
        if hh_condition and hl_condition and current_price > recent_highs[-1].price:
            return MarketStructure.UPTREND.value
        
        # Check for lower highs and lower lows
        lh_condition = all(recent_highs[i].price < recent_highs[i-1].price for i in range(1, len(recent_highs)))
        ll_condition = all(recent_lows[i].price < recent_lows[i-1].price for i in range(1, len(recent_lows)))
        
        if lh_condition and ll_condition and current_price < recent_lows[-1].price:
            return MarketStructure.DOWNTREND.value
        
        return MarketStructure.RANGE.value
    
    def _detect_market_structure_shift(self, df: pd.DataFrame, swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> bool:
        """Detect market structure shift (MSS)"""
        
        if len(swing_highs) < 3 or len(swing_lows) < 3:
            return False
        
        # Look for recent structure break
        recent_highs = sorted(swing_highs, key=lambda x: x.timestamp)[-4:]
        recent_lows = sorted(swing_lows, key=lambda x: x.timestamp)[-4:]
        
        current_price = df.iloc[-1]['close']
        
        # Bullish MSS: Break of recent low with bullish structure
        if current_price > recent_highs[-1].price:
            # Check if we recently broke below a significant low
            for low in recent_lows[:-1]:
                if df['low'].min() < low.price:
                    return True
        
        # Bearish MSS: Break of recent high with bearish structure
        elif current_price < recent_lows[-1].price:
            # Check if we recently broke above a significant high
            for high in recent_highs[:-1]:
                if df['high'].max() > high.price:
                    return True
        
        return False
    
    def _calculate_structure_metrics(self, df: pd.DataFrame, swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> Dict:
        """Calculate structure quality metrics"""
        
        if not swing_highs or not swing_lows:
            return {'trend_strength': 0, 'quality_score': 0}
        
        # Trend strength based on angle of trend lines
        trend_strength = self._calculate_trend_strength(swing_highs, swing_lows)
        
        # Quality score based on structure clarity
        quality_score = self._calculate_structure_quality(swing_highs, swing_lows)
        
        return {
            'trend_strength': trend_strength,
            'quality_score': quality_score,
            'structure_clarity': quality_score,
            'momentum_alignment': self._check_momentum_alignment(df, swing_highs, swing_lows)
        }
    
    def _calculate_trend_strength(self, swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> float:
        """Calculate trend strength from swing points"""
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 0.0
        
        # Calculate slope of trend lines
        high_slope = self._calculate_slope(swing_highs[-2:])
        low_slope = self._calculate_slope(swing_lows[-2:])
        
        # Trend strength is consistency of slopes
        avg_slope = (high_slope + low_slope) / 2
        return min(abs(avg_slope) * 100, 1.0)  # Normalize to 0-1
    
    def _calculate_slope(self, points: List[SwingPoint]) -> float:
        """Calculate slope between points"""
        if len(points) < 2:
            return 0.0
        
        p1, p2 = points[-2], points[-1]
        time_diff = (p2.timestamp - p1.timestamp).total_seconds() / 3600  # hours
        if time_diff == 0:
            return 0.0
        
        return (p2.price - p1.price) / time_diff
    
    def _calculate_structure_quality(self, swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> float:
        """Calculate market structure quality score"""
        
        if len(swing_highs) < 3 or len(swing_lows) < 3:
            return 0.0
        
        # Check for consistent structure
        high_consistency = self._check_point_consistency(swing_highs)
        low_consistency = self._check_point_consistency(swing_lows)
        
        # Check for proper alternation
        alternation_score = self._check_swing_alternation(swing_highs, swing_lows)
        
        return (high_consistency + low_consistency + alternation_score) / 3
    
    def _check_point_consistency(self, points: List[SwingPoint]) -> float:
        """Check consistency of swing points"""
        if len(points) < 3:
            return 0.0
        
        # Calculate how well points follow the expected pattern
        consistent = 0
        total_checks = len(points) - 2
        
        for i in range(1, len(points) - 1):
            prev_point, current_point, next_point = points[i-1], points[i], points[i+1]
            
            if current_point.point_type == 'high':
                # Highs should be higher than surrounding lows
                if current_point.price > prev_point.price and current_point.price > next_point.price:
                    consistent += 1
            else:  # low
                # Lows should be lower than surrounding highs
                if current_point.price < prev_point.price and current_point.price < next_point.price:
                    consistent += 1
        
        return consistent / total_checks if total_checks > 0 else 0.0
    
    def _check_swing_alternation(self, swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> float:
        """Check proper alternation of highs and lows"""
        
        all_points = sorted(swing_highs + swing_lows, key=lambda x: x.timestamp)
        if len(all_points) < 3:
            return 0.0
        
        # Check for proper high-low-high-low alternation
        alternations = 0
        for i in range(1, len(all_points) - 1):
            if all_points[i].point_type != all_points[i-1].point_type and \
               all_points[i].point_type != all_points[i+1].point_type:
                alternations += 1
        
        return alternations / (len(all_points) - 2) if len(all_points) > 2 else 0.0
    
    def _check_momentum_alignment(self, df: pd.DataFrame, swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> float:
        """Check if momentum aligns with structure"""
        
        if len(df) < 20:
            return 0.0
        
        # Calculate momentum indicators
        rsi = talib.RSI(df['close'].values, timeperiod=14)[-1]
        macd, macd_signal, macd_hist = talib.MACD(df['close'].values)
        
        # Current structure direction
        current_structure = self._determine_structure_state(df, swing_highs, swing_lows)
        
        # Check alignment
        if current_structure == MarketStructure.UPTREND.value:
            alignment = (rsi > 50) and (macd_hist[-1] > 0 if len(macd_hist) > 0 else False)
        elif current_structure == MarketStructure.DOWNTREND.value:
            alignment = (rsi < 50) and (macd_hist[-1] < 0 if len(macd_hist) > 0 else False)
        else:
            alignment = abs(rsi - 50) < 10  # Neutral for ranging
        
        return float(alignment)
    
    # Helper methods for liquidity analysis
    def _identify_liquidity_levels(self, df: pd.DataFrame) -> List[LiquidityLevel]:
        """Identify key liquidity levels"""
        
        levels = []
        
        # Find significant swing points as liquidity levels
        swing_highs, swing_lows = self._find_swing_points(df)
        
        for swing_high in swing_highs:
            levels.append(LiquidityLevel(
                price=swing_high.price,
                timestamp=swing_high.timestamp,
                level_type='sell_side',
                strength=swing_high.strength,
                touched_count=self._count_level_touches(df, swing_high.price),
                swept=False
            ))
        
        for swing_low in swing_lows:
            levels.append(LiquidityLevel(
                price=swing_low.price,
                timestamp=swing_low.timestamp,
                level_type='buy_side',
                strength=swing_low.strength,
                touched_count=self._count_level_touches(df, swing_low.price),
                swept=False
            ))
        
        return levels
    
    def _count_level_touches(self, df: pd.DataFrame, level_price: float, tolerance: float = 0.001) -> int:
        """Count how many times a price level was touched"""
        
        touches = 0
        tolerance_amount = level_price * tolerance
        
        for _, row in df.iterrows():
            if (row['low'] <= level_price + tolerance_amount and 
                row['high'] >= level_price - tolerance_amount):
                touches += 1
        
        return touches
    
    def _detect_liquidity_sweeps(self, df: pd.DataFrame, liquidity_levels: List[LiquidityLevel]) -> List[Dict]:
        """Detect liquidity sweeps"""
        
        sweeps = []
        
        for level in liquidity_levels:
            # Check if level was swept
            sweep_detected = self._check_level_sweep(df, level)
            
            if sweep_detected['swept']:
                sweeps.append({
                    'level': level,
                    'sweep_time': sweep_detected['time'],
                    'sweep_type': level.level_type,
                    'reaction_strength': sweep_detected['reaction_strength']
                })
                level.swept = True
        
        return sweeps
    
    def _check_level_sweep(self, df: pd.DataFrame, level: LiquidityLevel) -> Dict:
        """Check if a liquidity level was swept"""
        
        tolerance = level.price * 0.001
        
        for i, row in df.iterrows():
            if row['low'] <= level.price + tolerance and row['high'] >= level.price - tolerance:
                # Check if this was a sweep (broke through and reversed)
                if self._is_sweep_pattern(df, i, level):
                    return {
                        'swept': True,
                        'time': i,
                        'reaction_strength': self._calculate_reaction_strength(df, i)
                    }
        
        return {'swept': False}
    
    def _is_sweep_pattern(self, df: pd.DataFrame, index: int, level: LiquidityLevel) -> bool:
        """Determine if price action represents a sweep pattern"""
        
        if index < 5 or index >= len(df) - 5:
            return False
        
        # Get context around the potential sweep
        before = df.iloc[index-5:index]
        sweep_bar = df.iloc[index]
        after = df.iloc[index+1:index+6]
        
        # Sweep pattern: Break level then reverse
        if level.level_type == 'sell_side':
            # Sweep above high then reverse down
            broke_above = sweep_bar['high'] > level.price
            reversed_down = after['close'].min() < sweep_bar['close']
            return broke_above and reversed_down
        else:
            # Sweep below low then reverse up
            broke_below = sweep_bar['low'] < level.price
            reversed_up = after['close'].max() > sweep_bar['close']
            return broke_below and reversed_up
    
    def _calculate_reaction_strength(self, df: pd.DataFrame, sweep_index: int) -> float:
        """Calculate strength of reaction after sweep"""
        
        if sweep_index >= len(df) - 10:
            return 0.0
        
        sweep_price = df.iloc[sweep_index]['close']
        
        # Look at next 10 bars
        reaction_bars = df.iloc[sweep_index+1:sweep_index+11]
        
        if len(reaction_bars) == 0:
            return 0.0
        
        # Calculate maximum move away from sweep level
        max_move = 0.0
        for _, bar in reaction_bars.iterrows():
            move = abs(bar['close'] - sweep_price) / sweep_price
            max_move = max(max_move, move)
        
        return min(max_move, 1.0)  # Normalize to 0-1
    
    def _calculate_liquidity_density(self, df: pd.DataFrame, liquidity_levels: List[LiquidityLevel]) -> float:
        """Calculate liquidity density score"""
        
        if not liquidity_levels:
            return 0.0
        
        # Count liquidity levels in recent price range
        current_price = df.iloc[-1]['close']
        price_range = df['high'].max() - df['low'].min()
        
        nearby_levels = sum(1 for level in liquidity_levels 
                          if abs(level.price - current_price) < price_range * 0.1)
        
        # Normalize by total levels
        density = nearby_levels / len(liquidity_levels)
        return min(density * 2, 1.0)  # Scale to 0-1
    
    def _find_equal_highs_lows(self, df: pd.DataFrame) -> Dict:
        """Find equal highs and equal lows patterns"""
        
        equal_highs = []
        equal_lows = []
        
        # Find equal highs within tolerance
        tolerance = df['high'].std() * 0.5
        for i in range(len(df) - 10):
            for j in range(i + 5, min(i + 20, len(df))):
                if abs(df.iloc[i]['high'] - df.iloc[j]['high']) < tolerance:
                    equal_highs.append({
                        'first_high': df.iloc[i]['high'],
                        'second_high': df.iloc[j]['high'],
                        'first_time': df.index[i],
                        'second_time': df.index[j]
                    })
        
        # Find equal lows within tolerance
        tolerance = df['low'].std() * 0.5
        for i in range(len(df) - 10):
            for j in range(i + 5, min(i + 20, len(df))):
                if abs(df.iloc[i]['low'] - df.iloc[j]['low']) < tolerance:
                    equal_lows.append({
                        'first_low': df.iloc[i]['low'],
                        'second_low': df.iloc[j]['low'],
                        'first_time': df.index[i],
                        'second_time': df.index[j]
                    })
        
        return {
            'equal_highs': equal_highs,
            'equal_lows': equal_lows,
            'total_equal_levels': len(equal_highs) + len(equal_lows)
        }
    
    def _calculate_sweep_success_rate(self, sweeps: List[Dict]) -> float:
        """Calculate success rate of liquidity sweeps"""
        
        if not sweeps:
            return 0.0
        
        successful_sweeps = sum(1 for sweep in sweeps 
                              if sweep['reaction_strength'] > 0.5)
        
        return successful_sweeps / len(sweeps)
    
    # Placeholder implementations for remaining methods
    def _detect_fvgs(self, df: pd.DataFrame) -> List[FairValueGap]:
        """Detect Fair Value Gaps"""
        fvgs = []
        for i in range(2, len(df)):
            bar1, bar2, bar3 = df.iloc[i-2], df.iloc[i-1], df.iloc[i]
            
            # Bullish FVG
            if bar1['high'] < bar3['low']:
                gap_size = bar3['low'] - bar1['high']
                if gap_size > bar2['close'] * 0.0005:
                    fvgs.append(FairValueGap(
                        high=bar3['low'],
                        low=bar1['high'],
                        timestamp=df.index[i],
                        gap_type='bullish',
                        size=gap_size,
                        filled=False,
                        fill_time=None,
                        reaction_strength=0.0
                    ))
            
            # Bearish FVG
            elif bar1['low'] > bar3['high']:
                gap_size = bar1['low'] - bar3['high']
                if gap_size > bar2['close'] * 0.0005:
                    fvgs.append(FairValueGap(
                        high=bar1['low'],
                        low=bar3['high'],
                        timestamp=df.index[i],
                        gap_type='bearish',
                        size=gap_size,
                        filled=False,
                        fill_time=None,
                        reaction_strength=0.0
                    ))
        
        return fvgs
    
    def _track_fvg_fills(self, df: pd.DataFrame, fvg_list: List[FairValueGap]) -> List[FairValueGap]:
        """Track which FVGs get filled"""
        
        for fvg in fvg_list:
            if fvg.filled:
                continue
                
            # Check if FVG has been filled
            for i, bar in df.iterrows():
                if i > fvg.timestamp:
                    if fvg.gap_type == 'bullish' and bar['low'] <= fvg.low:
                        fvg.filled = True
                        fvg.fill_time = i
                        break
                    elif fvg.gap_type == 'bearish' and bar['high'] >= fvg.high:
                        fvg.filled = True
                        fvg.fill_time = i
                        break
        
        return fvg_list
    
    def _calculate_fvg_metrics(self, fvg_list: List[FairValueGap], filled_fvgs: List[FairValueGap]) -> Dict:
        """Calculate FVG performance metrics"""
        
        if not fvg_list:
            return {'fill_rate': 0, 'avg_size': 0, 'partial_fills': 0, 'avg_time_to_fill': 0}
        
        filled_count = sum(1 for fvg in fvg_list if fvg.filled)
        fill_rate = filled_count / len(fvg_list)
        
        avg_size = np.mean([fvg.size for fvg in fvg_list])
        
        # Calculate average time to fill
        filled_times = []
        for fvg in fvg_list:
            if fvg.filled and fvg.fill_time:
                fill_time = (fvg.fill_time - fvg.timestamp).total_seconds() / 3600
                filled_times.append(fill_time)
        
        avg_time_to_fill = np.mean(filled_times) if filled_times else 0
        
        return {
            'fill_rate': fill_rate,
            'avg_size': avg_size,
            'partial_fills': 0,  # Placeholder
            'avg_time_to_fill': avg_time_to_fill
        }
    
    def _analyze_fvg_reactions(self, df: pd.DataFrame, fvg_list: List[FairValueGap]) -> float:
        """Analyze reaction strength at FVG levels"""
        # Placeholder implementation
        return 0.65
    
    def _detect_order_blocks(self, df: pd.DataFrame) -> List[OrderBlock]:
        """Detect institutional order blocks"""
        obs = []
        
        for i in range(1, len(df)):
            prev_bar = df.iloc[i-1]
            current_bar = df.iloc[i]
            
            # Strong move down (potential bullish order block)
            price_change = (current_bar['close'] - prev_bar['close']) / prev_bar['close']
            if price_change < -0.002:  # 0.2% move down
                obs.append(OrderBlock(
                    high=prev_bar['high'],
                    low=prev_bar['low'],
                    timestamp=df.index[i-1],
                    block_type='bullish',
                    strength=abs(price_change),
                    mitigated=False,
                    mitigation_time=None
                ))
            
            # Strong move up (potential bearish order block)
            elif price_change > 0.002:  # 0.2% move up
                obs.append(OrderBlock(
                    high=prev_bar['high'],
                    low=prev_bar['low'],
                    timestamp=df.index[i-1],
                    block_type='bearish',
                    strength=price_change,
                    mitigated=False,
                    mitigation_time=None
                ))
        
        return obs
    
    def _track_ob_mitigation(self, df: pd.DataFrame, ob_list: List[OrderBlock]) -> List[OrderBlock]:
        """Track order block mitigation"""
        for ob in ob_list:
            if ob.mitigated:
                continue
                
            # Check if OB has been mitigated
            for i, bar in df.iterrows():
                if i > ob.timestamp:
                    if ob.block_type == 'bullish' and bar['low'] <= ob.low:
                        ob.mitigated = True
                        ob.mitigation_time = i
                        break
                    elif ob.block_type == 'bearish' and bar['high'] >= ob.high:
                        ob.mitigated = True
                        ob.mitigation_time = i
                        break
        
        return ob_list
    
    def _calculate_ob_metrics(self, ob_list: List[OrderBlock], mitigated_obs: List[OrderBlock]) -> Dict:
        """Calculate order block performance metrics"""
        
        if not ob_list:
            return {'mitigation_rate': 0, 'failure_rate': 0, 'avg_strength': 0, 'reaction_quality': 0}
        
        mitigated_count = sum(1 for ob in ob_list if ob.mitigated)
        mitigation_rate = mitigated_count / len(ob_list)
        
        # Failure rate = OBs that were mitigated but didn't lead to expected move
        failure_rate = 0.2  # Placeholder
        
        avg_strength = np.mean([ob.strength for ob in ob_list])
        
        return {
            'mitigation_rate': mitigation_rate,
            'failure_rate': failure_rate,
            'avg_strength': avg_strength,
            'reaction_quality': 0.7  # Placeholder
        }
    
    def _calculate_dealing_range(self, df: pd.DataFrame) -> Dict:
        """Calculate dealing range and premium/discount zones"""
        
        lookback = min(100, len(df))
        recent_data = df.iloc[-lookback:]
        
        range_high = recent_data['high'].max()
        range_low = recent_data['low'].min()
        range_mid = (range_high + range_low) / 2
        
        return {
            'range_high': range_high,
            'range_low': range_low,
            'equilibrium': range_mid,
            'discount_zone': (range_low, range_mid),
            'premium_zone': (range_mid, range_high),
            'range_size': range_high - range_low
        }
    
    def _calculate_fibonacci_levels(self, df: pd.DataFrame) -> Dict:
        """Calculate Fibonacci retracement levels"""
        
        lookback = min(100, len(df))
        recent_data = df.iloc[-lookback:]
        
        high = recent_data['high'].max()
        low = recent_data['low'].min()
        diff = high - low
        
        fib_levels = {
            '0%': low,
            '23.6%': low + diff * 0.236,
            '38.2%': low + diff * 0.382,
            '50%': low + diff * 0.5,
            '61.8%': low + diff * 0.618,
            '78.6%': low + diff * 0.786,
            '100%': high
        }
        
        return fib_levels
    
    def _determine_current_zone(self, df: pd.DataFrame, dealing_range: Dict, fib_levels: Dict) -> str:
        """Determine if price is in premium or discount zone"""
        
        current_price = df.iloc[-1]['close']
        equilibrium = dealing_range['equilibrium']
        
        if current_price < equilibrium:
            return 'DISCOUNT'
        else:
            return 'PREMIUM'
    
    def _calculate_zone_effectiveness(self, df: pd.DataFrame, current_zone: str) -> float:
        """Calculate effectiveness of premium/discount zones"""
        # Placeholder implementation
        return 0.6
    
    def _identify_sessions(self, df: pd.DataFrame) -> Dict:
        """Identify trading sessions for each bar"""
        sessions = {}
        
        for timestamp in df.index:
            hour = timestamp.hour
            
            if 0 <= hour < 8:
                session = 'Asia'
            elif 8 <= hour < 16:
                session = 'London'
            elif 16 <= hour < 24:
                session = 'NewYork'
            else:
                session = 'Asia'
            
            sessions[timestamp] = session
        
        return sessions
    
    def _calculate_session_volatility(self, df: pd.DataFrame, sessions: Dict) -> Dict:
        """Calculate volatility by session"""
        session_vol = {'Asia': [], 'London': [], 'NewYork': []}
        
        for timestamp, session in sessions.items():
            if timestamp in df.index:
                bar = df.loc[timestamp]
                volatility = (bar['high'] - bar['low']) / bar['close']
                session_vol[session].append(volatility)
        
        # Calculate average volatility per session
        avg_vol = {}
        for session, vols in session_vol.items():
            avg_vol[session] = np.mean(vols) if vols else 0.0
        
        return avg_vol
    
    def _identify_killzones(self, df: pd.DataFrame, sessions: Dict) -> List[Dict]:
        """Identify high-probability killzones"""
        killzones = []
        
        # London open killzone (7:00-9:00 UTC)
        # New York open killzone (13:00-15:00 UTC)
        # London close killzone (15:00-17:00 UTC)
        
        return killzones
    
    def _calculate_session_performance(self, df: pd.DataFrame, sessions: Dict) -> Dict:
        """Calculate performance metrics by session"""
        # Placeholder - would need trade data to calculate
        return {'Asia': 0.0, 'London': 0.0, 'NewYork': 0.0}
    
    def _find_overlapping_sessions(self, sessions: Dict) -> List[str]:
        """Find overlapping trading sessions"""
        return ['London/NewYork']  # Simplified
    
    def _detect_po3_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Detect Power of Three patterns"""
        patterns = []
        # Placeholder implementation
        return patterns
    
    def _analyze_po3_phases(self, df: pd.DataFrame, patterns: List[Dict]) -> Dict:
        """Analyze PO3 phases"""
        return {
            'accumulation': [],
            'manipulation': [],
            'distribution': []
        }
    
    def _validate_po3_patterns(self, patterns: List[Dict]) -> float:
        """Validate PO3 pattern effectiveness"""
        return 0.5  # Placeholder
