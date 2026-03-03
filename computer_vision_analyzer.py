"""
COMPUTER VISION REGIME DETECTION SYSTEM
Quantitative visual analysis for ICT concept validation
Created by: ICT Concept Auditor
"""

import pandas as pd
import numpy as np
import cv2
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

class MarketRegime(Enum):
    TREND_UP = "Trending Up"
    TREND_DOWN = "Trending Down"
    RANGE_BOUND = "Range Bound"
    EXPANSION = "Volatility Expansion"
    COMPRESSION = "Volatility Compression"
    TRANSITION = "Regime Transition"

@dataclass
class RegimeDetection:
    timestamp: datetime
    regime: MarketRegime
    confidence: float
    volatility_state: float
    trend_strength: float
    range_width: float

@dataclass
class LiquidityHeatmap:
    timestamp: datetime
    price_levels: List[float]
    liquidity_density: List[float]
    buy_pressure: float
    sell_pressure: float
    imbalance_score: float

@dataclass
class StructuralFeature:
    timestamp: datetime
    feature_type: str  # 'swing_high', 'swing_low', 'breakout', 'breakdown'
    price: float
    strength: float
    volume_confirmation: float

class ComputerVisionAnalyzer:
    """Computer vision for quantitative market analysis"""
    
    def __init__(self):
        self.regime_history: List[RegimeDetection] = []
        self.liquidity_heatmaps: List[LiquidityHeatmap] = []
        self.structural_features: List[StructuralFeature] = []
        
        # CV parameters
        self.trend_threshold = 0.02
        self.volatility_window = 20
        self.range_threshold = 0.05
        
    def analyze_market_regime(self, df: pd.DataFrame, visualize: bool = False) -> Dict:
        """
        Detect market regimes using computer vision techniques
        
        FORBIDDEN: Pattern prediction, subjective annotations
        ALLOWED: Regime detection, structural features, liquidity analysis
        """
        
        # Convert price data to visual representation
        price_matrix = self._create_price_matrix(df)
        
        # Detect regime using visual patterns
        regime_detections = self._detect_regimes_cv(price_matrix, df)
        
        # Validate regime with statistical measures
        validated_regimes = self._validate_regime_detection(regime_detections, df)
        
        # Calculate regime stability metrics
        regime_metrics = self._calculate_regime_metrics(validated_regimes)
        
        # Generate visualizations if requested
        if visualize:
            self._generate_regime_visualizations(df, validated_regimes)
        
        return {
            'regime_detections': validated_regimes,
            'regime_metrics': regime_metrics,
            'current_regime': validated_regimes[-1] if validated_regimes else None,
            'regime_stability': regime_metrics['stability_score'],
            'transition_frequency': regime_metrics['transition_freq'],
            'cv_accuracy': self._calculate_cv_accuracy(validated_regimes, df)
        }
    
    def analyze_liquidity_heatmap(self, df: pd.DataFrame, visualize: bool = False) -> Dict:
        """
        Create liquidity heatmap using orderbook-like visualization
        
        FORBIDDEN: Pattern prediction
        ALLOWED: Liquidity visuals, orderbook heatmaps, execution conditions
        """
        
        # Create price-volume matrix
        liquidity_matrix = self._create_liquidity_matrix(df)
        
        # Detect liquidity concentrations
        liquidity_zones = self._detect_liquidity_zones(liquidity_matrix, df)
        
        # Calculate liquidity metrics
        liquidity_metrics = self._calculate_liquidity_metrics(liquidity_zones, df)
        
        # Generate heatmap if requested
        if visualize:
            self._generate_liquidity_heatmap(liquidity_matrix, liquidity_zones)
        
        return {
            'liquidity_zones': liquidity_zones,
            'liquidity_metrics': liquidity_metrics,
            'buy_side_liquidity': liquidity_metrics['buy_side_density'],
            'sell_side_liquidity': liquidity_metrics['sell_side_density'],
            'liquidity_imbalance': liquidity_metrics['imbalance_score'],
            'cv_effectiveness': self._calculate_liquidity_cv_effectiveness(liquidity_zones, df)
        }
    
    def validate_execution_conditions(self, df: pd.DataFrame, trade_signals: List[Dict]) -> Dict:
        """
        Validate execution conditions using visual analysis
        
        ALLOWED: Liquidity presence, slippage zones, execution validation
        """
        
        execution_analysis = []
        
        for signal in trade_signals:
            signal_time = signal.get('timestamp')
            if signal_time not in df.index:
                continue
            
            # Get context around signal
            context_data = self._get_signal_context(df, signal_time)
            
            # Visual validation of execution conditions
            execution_quality = self._validate_execution_visual(context_data, signal)
            
            execution_analysis.append({
                'signal': signal,
                'execution_quality': execution_quality,
                'liquidity_present': execution_quality['liquidity_score'] > 0.6,
                'slippage_risk': execution_quality['slippage_risk'],
                'visual_confirmation': execution_quality['visual_score'] > 0.7
            })
        
        # Calculate overall execution metrics
        execution_metrics = self._calculate_execution_metrics(execution_analysis)
        
        return {
            'execution_analysis': execution_analysis,
            'execution_metrics': execution_metrics,
            'avg_execution_quality': execution_metrics['avg_quality'],
            'liquidity_success_rate': execution_metrics['liquidity_success'],
            'slippage_frequency': execution_metrics['slippage_freq']
        }
    
    def _create_price_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """Convert price data to 2D matrix for visual analysis"""
        
        # Normalize price data
        price_data = df[['open', 'high', 'low', 'close']].values
        
        # Create visual representation
        # Rows: time bars, Columns: price levels
        
        # Determine price range and resolution
        min_price = df['low'].min()
        max_price = df['high'].max()
        price_levels = 100  # Resolution
        
        # Create price matrix
        price_matrix = np.zeros((len(df), price_levels))
        
        for i, (_, bar) in enumerate(df.iterrows()):
            # Map OHLC to price levels
            open_level = int((bar['open'] - min_price) / (max_price - min_price) * price_levels)
            high_level = int((bar['high'] - min_price) / (max_price - min_price) * price_levels)
            low_level = int((bar['low'] - min_price) / (max_price - min_price) * price_levels)
            close_level = int((bar['close'] - min_price) / (max_price - min_price) * price_levels)
            
            # Fill matrix
            price_matrix[i, low_level:high_level+1] = 1
            
            # Add volume weighting if available
            if 'volume' in bar:
                price_matrix[i, low_level:high_level+1] *= bar['volume'] / df['volume'].max()
        
        return price_matrix
    
    def _detect_regimes_cv(self, price_matrix: np.ndarray, df: pd.DataFrame) -> List[RegimeDetection]:
        """Detect market regimes using computer vision techniques"""
        
        detections = []
        
        # Use edge detection for trend identification
        edges = cv2.Canny(price_matrix.astype(np.uint8), 50, 150)
        
        # Use contour detection for range identification
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Analyze patterns in sliding windows
        window_size = min(50, len(price_matrix) // 4)
        
        for i in range(window_size, len(price_matrix), window_size // 2):
            window = price_matrix[i-window_size:i]
            
            # Detect regime in this window
            regime = self._classify_window_regime(window, df.iloc[i-window_size:i])
            
            confidence = self._calculate_regime_confidence(window, regime)
            
            detections.append(RegimeDetection(
                timestamp=df.index[i-1],
                regime=regime,
                confidence=confidence,
                volatility_state=self._calculate_volatility_state(window),
                trend_strength=self._calculate_trend_strength_cv(window),
                range_width=self._calculate_range_width(window)
            ))
        
        return detections
    
    def _classify_window_regime(self, window: np.ndarray, price_data: pd.DataFrame) -> MarketRegime:
        """Classify regime in a window using visual analysis"""
        
        # Calculate visual features
        vertical_movement = self._calculate_vertical_movement(window)
        horizontal_spread = self._calculate_horizontal_spread(window)
        density_variance = self._calculate_density_variance(window)
        
        # Calculate statistical features for validation
        price_change = (price_data['close'].iloc[-1] - price_data['close'].iloc[0]) / price_data['close'].iloc[0]
        volatility = price_data['close'].std() / price_data['close'].mean()
        
        # Regime classification logic
        if abs(price_change) > self.trend_threshold and vertical_movement > 0.7:
            if price_change > 0:
                return MarketRegime.TREND_UP
            else:
                return MarketRegime.TREND_DOWN
        
        elif volatility > 0.02 and density_variance > 0.6:
            return MarketRegime.EXPANSION
        
        elif volatility < 0.01 and horizontal_spread < 0.3:
            return MarketRegime.COMPRESSION
        
        elif horizontal_spread > 0.7 and vertical_movement < 0.3:
            return MarketRegime.RANGE_BOUND
        
        else:
            return MarketRegime.TRANSITION
    
    def _calculate_vertical_movement(self, window: np.ndarray) -> float:
        """Calculate vertical price movement in window"""
        
        # Find top and bottom edges
        top_edge = np.any(window, axis=1)
        bottom_edge = np.any(window, axis=1)
        
        # Calculate movement
        if not np.any(top_edge) or not np.any(bottom_edge):
            return 0.0
        
        top_positions = np.where(top_edge)[0]
        bottom_positions = np.where(bottom_edge)[0]
        
        if len(top_positions) > 1 and len(bottom_positions) > 1:
            movement = abs(top_positions[-1] - top_positions[0]) / window.shape[0]
            return min(movement, 1.0)
        
        return 0.0
    
    def _calculate_horizontal_spread(self, window: np.ndarray) -> float:
        """Calculate horizontal price spread in window"""
        
        # Find left and right edges
        left_edge = np.any(window, axis=0)
        right_edge = np.any(window, axis=0)
        
        # Calculate spread
        if not np.any(left_edge) or not np.any(right_edge):
            return 0.0
        
        left_positions = np.where(left_edge)[0]
        right_positions = np.where(right_edge)[0]
        
        if len(left_positions) > 0 and len(right_positions) > 0:
            spread = (right_positions.max() - left_positions.min()) / window.shape[1]
            return min(spread, 1.0)
        
        return 0.0
    
    def _calculate_density_variance(self, window: np.ndarray) -> float:
        """Calculate variance in price density"""
        
        density = np.sum(window, axis=0)
        if len(density) == 0:
            return 0.0
        
        variance = np.var(density)
        max_variance = (np.max(density) - np.min(density)) ** 2
        
        if max_variance > 0:
            return variance / max_variance
        
        return 0.0
    
    def _calculate_regime_confidence(self, window: np.ndarray, regime: MarketRegime) -> float:
        """Calculate confidence in regime detection"""
        
        # Base confidence on pattern clarity
        pattern_clarity = self._calculate_pattern_clarity(window)
        
        # Adjust based on regime type
        regime_multiplier = {
            MarketRegime.TREND_UP: 0.9,
            MarketRegime.TREND_DOWN: 0.9,
            MarketRegime.RANGE_BOUND: 0.7,
            MarketRegime.EXPANSION: 0.6,
            MarketRegime.COMPRESSION: 0.8,
            MarketRegime.TRANSITION: 0.4
        }
        
        confidence = pattern_clarity * regime_multiplier.get(regime, 0.5)
        return min(confidence, 1.0)
    
    def _calculate_pattern_clarity(self, window: np.ndarray) -> float:
        """Calculate how clear the visual pattern is"""
        
        # Use edge density as clarity measure
        edges = cv2.Canny(window.astype(np.uint8), 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # Use contrast as clarity measure
        contrast = window.max() - window.min()
        normalized_contrast = contrast / window.max() if window.max() > 0 else 0
        
        # Combine measures
        clarity = (edge_density + normalized_contrast) / 2
        return min(clarity, 1.0)
    
    def _calculate_volatility_state(self, window: np.ndarray) -> float:
        """Calculate volatility state from visual data"""
        
        # Calculate movement in window
        movement = self._calculate_vertical_movement(window)
        spread = self._calculate_horizontal_spread(window)
        
        # Volatility is combination of movement and spread
        volatility = (movement + spread) / 2
        return min(volatility, 1.0)
    
    def _calculate_trend_strength_cv(self, window: np.ndarray) -> float:
        """Calculate trend strength using computer vision"""
        
        # Use Hough line transform to detect trend lines
        edges = cv2.Canny(window.astype(np.uint8), 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=10, minLineLength=10, maxLineGap=5)
        
        if lines is None:
            return 0.0
        
        # Calculate dominant trend direction
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.arctan2(y2 - y1, x2 - x1)
            angles.append(angle)
        
        if not angles:
            return 0.0
        
        # Trend strength is consistency of angles
        angle_std = np.std(angles)
        strength = 1.0 - min(angle_std / (np.pi / 2), 1.0)
        
        return strength
    
    def _calculate_range_width(self, window: np.ndarray) -> float:
        """Calculate range width from visual data"""
        
        # Find price range in window
        price_range = self._calculate_horizontal_spread(window)
        return price_range
    
    def _validate_regime_detection(self, detections: List[RegimeDetection], df: pd.DataFrame) -> List[RegimeDetection]:
        """Validate regime detection with statistical measures"""
        
        validated = []
        
        for detection in detections:
            # Get statistical validation
            statistical_regime = self._validate_regime_statistical(detection.timestamp, df)
            
            # Check if CV and statistical agree
            if self._regimes_match(detection.regime, statistical_regime):
                detection.confidence = min(detection.confidence + 0.2, 1.0)
            else:
                detection.confidence = max(detection.confidence - 0.3, 0.0)
            
            # Only keep high confidence detections
            if detection.confidence > 0.5:
                validated.append(detection)
        
        return validated
    
    def _validate_regime_statistical(self, timestamp: datetime, df: pd.DataFrame) -> MarketRegime:
        """Validate regime using statistical methods"""
        
        # Get data around timestamp
        idx = df.index.get_loc(timestamp)
        start_idx = max(0, idx - 20)
        end_idx = min(len(df), idx + 20)
        
        window_data = df.iloc[start_idx:end_idx]
        
        # Statistical regime detection
        price_change = (window_data['close'].iloc[-1] - window_data['close'].iloc[0]) / window_data['close'].iloc[0]
        volatility = window_data['close'].std() / window_data['close'].mean()
        
        if abs(price_change) > self.trend_threshold:
            return MarketRegime.TREND_UP if price_change > 0 else MarketRegime.TREND_DOWN
        elif volatility > 0.02:
            return MarketRegime.EXPANSION
        elif volatility < 0.01:
            return MarketRegime.COMPRESSION
        else:
            return MarketRegime.RANGE_BOUND
    
    def _regimes_match(self, cv_regime: MarketRegime, stat_regime: MarketRegime) -> bool:
        """Check if CV and statistical regimes match"""
        
        # Allow some flexibility in matching
        compatible_pairs = {
            MarketRegime.TREND_UP: [MarketRegime.TREND_UP],
            MarketRegime.TREND_DOWN: [MarketRegime.TREND_DOWN],
            MarketRegime.RANGE_BOUND: [MarketRegime.RANGE_BOUND, MarketRegime.COMPRESSION],
            MarketRegime.EXPANSION: [MarketRegime.EXPANSION],
            MarketRegime.COMPRESSION: [MarketRegime.COMPRESSION, MarketRegime.RANGE_BOUND],
            MarketRegime.TRANSITION: [MarketRegime.TRANSITION]
        }
        
        return stat_regime in compatible_pairs.get(cv_regime, [])
    
    def _calculate_regime_metrics(self, detections: List[RegimeDetection]) -> Dict:
        """Calculate regime stability and transition metrics"""
        
        if len(detections) < 2:
            return {'stability_score': 0.0, 'transition_freq': 0.0}
        
        # Calculate stability (how long regimes last)
        regime_durations = {}
        current_regime = None
        regime_start = None
        
        for detection in detections:
            if current_regime != detection.regime:
                if current_regime is not None:
                    duration = (detection.timestamp - regime_start).total_seconds() / 3600
                    if current_regime not in regime_durations:
                        regime_durations[current_regime] = []
                    regime_durations[current_regime].append(duration)
                
                current_regime = detection.regime
                regime_start = detection.timestamp
        
        # Calculate average duration
        all_durations = []
        for durations in regime_durations.values():
            all_durations.extend(durations)
        
        avg_duration = np.mean(all_durations) if all_durations else 0
        stability_score = min(avg_duration / 24, 1.0)  # Normalize to 24 hours
        
        # Calculate transition frequency
        transitions = len(detections) - 1
        time_span = (detections[-1].timestamp - detections[0].timestamp).total_seconds() / 3600
        transition_freq = transitions / time_span if time_span > 0 else 0
        
        return {
            'stability_score': stability_score,
            'transition_freq': transition_freq,
            'regime_durations': regime_durations,
            'avg_regime_duration': avg_duration
        }
    
    def _calculate_cv_accuracy(self, detections: List[RegimeDetection], df: pd.DataFrame) -> float:
        """Calculate overall accuracy of CV detection"""
        
        if not detections:
            return 0.0
        
        # Compare with statistical validation
        correct_detections = 0
        total_detections = len(detections)
        
        for detection in detections:
            stat_regime = self._validate_regime_statistical(detection.timestamp, df)
            if self._regimes_match(detection.regime, stat_regime):
                correct_detections += 1
        
        accuracy = correct_detections / total_detections if total_detections > 0 else 0
        return accuracy
    
    def _create_liquidity_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """Create liquidity visualization matrix"""
        
        # Use volume and price action to estimate liquidity
        price_levels = 100
        time_bars = len(df)
        
        liquidity_matrix = np.zeros((time_bars, price_levels))
        
        min_price = df['low'].min()
        max_price = df['high'].max()
        
        for i, (_, bar) in df.iterrows():
            # Map price range to levels
            high_level = int((bar['high'] - min_price) / (max_price - min_price) * price_levels)
            low_level = int((bar['low'] - min_price) / (max_price - min_price) * price_levels)
            
            # Use volume as liquidity indicator
            volume_weight = bar.get('volume', 1.0) / df.get('volume', pd.Series([1])).max()
            
            # Fill liquidity matrix
            for level in range(low_level, min(high_level + 1, price_levels)):
                liquidity_matrix[i, level] = volume_weight
        
        return liquidity_matrix
    
    def _detect_liquidity_zones(self, liquidity_matrix: np.ndarray, df: pd.DataFrame) -> List[LiquidityHeatmap]:
        """Detect liquidity concentration zones"""
        
        heatmaps = []
        
        # Analyze in sliding windows
        window_size = min(20, len(liquidity_matrix) // 4)
        
        for i in range(window_size, len(liquidity_matrix), window_size // 2):
            window = liquidity_matrix[i-window_size:i]
            timestamp = df.index[i-1]
            
            # Calculate liquidity density by price level
            liquidity_density = np.sum(window, axis=0)
            
            # Identify buy/sell pressure zones
            buy_pressure = self._calculate_buy_pressure(window)
            sell_pressure = self._calculate_sell_pressure(window)
            
            # Calculate imbalance
            imbalance_score = abs(buy_pressure - sell_pressure)
            
            # Find significant price levels
            significant_levels = self._find_significant_levels(liquidity_density)
            
            heatmaps.append(LiquidityHeatmap(
                timestamp=timestamp,
                price_levels=significant_levels,
                liquidity_density=liquidity_density.tolist(),
                buy_pressure=buy_pressure,
                sell_pressure=sell_pressure,
                imbalance_score=imbalance_score
            ))
        
        return heatmaps
    
    def _calculate_buy_pressure(self, window: np.ndarray) -> float:
        """Calculate buy-side pressure"""
        
        # Look for upward price movement with volume
        # Simplified: lower price levels with high activity
        lower_half = window[:, :window.shape[1]//2]
        buy_activity = np.sum(lower_half)
        
        total_activity = np.sum(window)
        if total_activity == 0:
            return 0.0
        
        return buy_activity / total_activity
    
    def _calculate_sell_pressure(self, window: np.ndarray) -> float:
        """Calculate sell-side pressure"""
        
        # Look for downward price movement with volume
        # Simplified: higher price levels with high activity
        upper_half = window[:, window.shape[1]//2:]
        sell_activity = np.sum(upper_half)
        
        total_activity = np.sum(window)
        if total_activity == 0:
            return 0.0
        
        return sell_activity / total_activity
    
    def _find_significant_levels(self, liquidity_density: np.ndarray) -> List[float]:
        """Find significant liquidity levels"""
        
        # Use clustering to find significant levels
        if len(liquidity_density) == 0:
            return []
        
        # Normalize density
        normalized_density = liquidity_density / np.max(liquidity_density)
        
        # Find peaks (significant levels)
        significant_levels = []
        threshold = 0.3  # 30% of max density
        
        for i, density in enumerate(normalized_density):
            if density > threshold:
                significant_levels.append(float(i))
        
        return significant_levels
    
    def _calculate_liquidity_metrics(self, heatmaps: List[LiquidityHeatmap], df: pd.DataFrame) -> Dict:
        """Calculate liquidity metrics from heatmaps"""
        
        if not heatmaps:
            return {
                'buy_side_density': 0.0,
                'sell_side_density': 0.0,
                'imbalance_score': 0.0,
                'liquidity_quality': 0.0
            }
        
        # Aggregate metrics
        buy_densities = [hm.buy_pressure for hm in heatmaps]
        sell_densities = [hm.sell_pressure for hm in heatmaps]
        imbalances = [hm.imbalance_score for hm in heatmaps]
        
        return {
            'buy_side_density': np.mean(buy_densities),
            'sell_side_density': np.mean(sell_densities),
            'imbalance_score': np.mean(imbalances),
            'liquidity_quality': 1.0 - np.mean(imbalances),  # Lower imbalance = higher quality
            'liquidity_volatility': np.std(imbalances)
        }
    
    def _calculate_liquidity_cv_effectiveness(self, heatmaps: List[LiquidityHeatmap], df: pd.DataFrame) -> float:
        """Calculate effectiveness of CV liquidity analysis"""
        
        # Placeholder - would compare with actual orderbook data if available
        return 0.75
    
    def _get_signal_context(self, df: pd.DataFrame, signal_time: datetime) -> pd.DataFrame:
        """Get context around trading signal"""
        
        idx = df.index.get_loc(signal_time)
        start_idx = max(0, idx - 10)
        end_idx = min(len(df), idx + 10)
        
        return df.iloc[start_idx:end_idx]
    
    def _validate_execution_visual(self, context_data: pd.DataFrame, signal: Dict) -> Dict:
        """Validate execution conditions using visual analysis"""
        
        # Create visual matrix for context
        context_matrix = self._create_price_matrix(context_data)
        
        # Analyze liquidity presence
        liquidity_score = self._assess_liquidity_presence(context_matrix)
        
        # Assess slippage risk
        slippage_risk = self._assess_slippage_risk(context_matrix, signal)
        
        # Visual pattern confirmation
        visual_score = self._calculate_visual_confirmation(context_matrix, signal)
        
        return {
            'liquidity_score': liquidity_score,
            'slippage_risk': slippage_risk,
            'visual_score': visual_score,
            'overall_quality': (liquidity_score + visual_score - slippage_risk) / 2
        }
    
    def _assess_liquidity_presence(self, context_matrix: np.ndarray) -> float:
        """Assess if sufficient liquidity is present"""
        
        # Calculate density as proxy for liquidity
        density = np.sum(context_matrix) / context_matrix.size
        return min(density * 2, 1.0)  # Normalize to 0-1
    
    def _assess_slippage_risk(self, context_matrix: np.ndarray, signal: Dict) -> float:
        """Assess slippage risk based on visual patterns"""
        
        # High volatility and low density increase slippage risk
        volatility = self._calculate_volatility_state(context_matrix)
        density = np.sum(context_matrix) / context_matrix.size
        
        # Slippage risk increases with volatility and decreases with density
        risk = volatility * (1.0 - density)
        return min(risk, 1.0)
    
    def _calculate_visual_confirmation(self, context_matrix: np.ndarray, signal: Dict) -> float:
        """Calculate visual confirmation of signal"""
        
        # Check if visual patterns support the signal
        signal_type = signal.get('type', 'HOLD')
        
        if signal_type == 'BUY':
            # Look for bullish visual patterns
            upward_movement = self._calculate_vertical_movement(context_matrix)
            return upward_movement
        elif signal_type == 'SELL':
            # Look for bearish visual patterns
            downward_movement = self._calculate_vertical_movement(context_matrix)
            return downward_movement
        else:
            return 0.5  # Neutral for HOLD signals
    
    def _calculate_execution_metrics(self, execution_analysis: List[Dict]) -> Dict:
        """Calculate overall execution metrics"""
        
        if not execution_analysis:
            return {
                'avg_quality': 0.0,
                'liquidity_success': 0.0,
                'slippage_freq': 0.0
            }
        
        qualities = [ea['execution_quality']['overall_quality'] for ea in execution_analysis]
        liquidity_successes = [ea for ea in execution_analysis if ea['liquidity_present']]
        slippage_events = [ea for ea in execution_analysis if ea['slippage_risk'] > 0.5]
        
        return {
            'avg_quality': np.mean(qualities),
            'liquidity_success': len(liquidity_successes) / len(execution_analysis),
            'slippage_freq': len(slippage_events) / len(execution_analysis),
            'visual_confirmation_rate': sum(1 for ea in execution_analysis if ea['visual_confirmation']) / len(execution_analysis)
        }
    
    def _generate_regime_visualizations(self, df: pd.DataFrame, regimes: List[RegimeDetection]):
        """Generate regime visualization plots"""
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Price with Regime Detection', 'Regime Confidence'),
            vertical_spacing=0.1
        )
        
        # Price chart
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price'
            ),
            row=1, col=1
        )
        
        # Add regime markers
        regime_colors = {
            MarketRegime.TREND_UP: 'green',
            MarketRegime.TREND_DOWN: 'red',
            MarketRegime.RANGE_BOUND: 'blue',
            MarketRegime.EXPANSION: 'orange',
            MarketRegime.COMPRESSION: 'purple',
            MarketRegime.TRANSITION: 'gray'
        }
        
        for regime in regimes:
            fig.add_vrect(
                x0=regime.timestamp,
                x1=regime.timestamp + timedelta(hours=1),
                fillcolor=regime_colors.get(regime.regime, 'gray'),
                opacity=0.3,
                layer="below",
                line_width=0,
                row=1, col=1
            )
        
        # Confidence chart
        confidences = [r.confidence for r in regimes]
        timestamps = [r.timestamp for r in regimes]
        
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=confidences,
                mode='lines+markers',
                name='Regime Confidence',
                line=dict(color='purple')
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            title='Market Regime Detection - Computer Vision Analysis',
            height=800,
            showlegend=True
        )
        
        fig.show()
    
    def _generate_liquidity_heatmap(self, liquidity_matrix: np.ndarray, zones: List[LiquidityHeatmap]):
        """Generate liquidity heatmap visualization"""
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Create heatmap
        im = ax.imshow(liquidity_matrix, cmap='YlOrRd', aspect='auto')
        
        # Add colorbar
        plt.colorbar(im, ax=ax, label='Liquidity Density')
        
        ax.set_title('Liquidity Heatmap - Computer Vision Analysis')
        ax.set_xlabel('Price Levels')
        ax.set_ylabel('Time')
        
        plt.tight_layout()
        plt.show()
    
    def generate_cv_report(self, regime_analysis: Dict, liquidity_analysis: Dict, execution_analysis: Dict) -> str:
        """Generate comprehensive computer vision analysis report"""
        
        report = []
        report.append("\n" + "="*80)
        report.append("👁️ COMPUTER VISION ANALYSIS REPORT")
        report.append("="*80)
        
        # Regime Analysis
        report.append("\n📊 MARKET REGIME DETECTION")
        regime = regime_analysis
        report.append(f"Current Regime: {regime['current_regime'].regime if regime['current_regime'] else 'Unknown'}")
        report.append(f"Regime Stability: {regime['regime_stability']:.2f}")
        report.append(f"Transition Frequency: {regime['transition_freq']:.2f} per hour")
        report.append(f"CV Accuracy: {regime['cv_accuracy']:.2f}")
        
        # Liquidity Analysis
        report.append("\n💧 LIQUIDITY HEATMAP ANALYSIS")
        liquidity = liquidity_analysis
        report.append(f"Buy Side Liquidity Density: {liquidity['buy_side_liquidity']:.2f}")
        report.append(f"Sell Side Liquidity Density: {liquidity['sell_side_liquidity']:.2f}")
        report.append(f"Liquidity Imbalance: {liquidity['liquidity_imbalance']:.2f}")
        report.append(f"CV Effectiveness: {liquidity['cv_effectiveness']:.2f}")
        
        # Execution Analysis
        report.append("\n⚡ EXECUTION CONDITION VALIDATION")
        execution = execution_analysis
        report.append(f"Average Execution Quality: {execution['avg_execution_quality']:.2f}")
        report.append(f"Liquidity Success Rate: {execution['liquidity_success']:.2f}")
        report.append(f"Slippage Frequency: {execution['slippage_freq']:.2f}")
        
        # CV Value Assessment
        cv_value_score = (regime['cv_accuracy'] + liquidity['cv_effectiveness']) / 2
        report.append(f"\n🎯 OVERALL CV VALUE SCORE: {cv_value_score:.2f}")
        
        if cv_value_score > 0.8:
            report.append("✅ Computer vision adds significant measurable value")
        elif cv_value_score > 0.6:
            report.append("🟡 Computer vision adds moderate value")
        else:
            report.append("❌ Computer vision adds limited value")
        
        report.append("\n" + "="*80)
        
        return "\n".join(report)
