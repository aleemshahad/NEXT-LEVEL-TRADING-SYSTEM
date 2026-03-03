"""
ICT CONCEPT EVALUATION SYSTEM
Rigorous quantitative testing of ICT (Inner Circle Trader) concepts
Created by: ICT Concept Auditor
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from loguru import logger
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix
import cv2
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class Verdict(Enum):
    DEPLOY = "🟢 DEPLOY"
    OPTIMIZE = "🟡 OPTIMIZE" 
    KILL = "🔴 KILL"

@dataclass
class ICTMetrics:
    """Core ICT evaluation metrics"""
    expectancy: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    avg_win: float
    avg_loss: float
    total_trades: int
    net_pnl: float

@dataclass
class ICTFeatures:
    """Quantified ICT concept features"""
    market_structure_score: float
    liquidity_density: float
    fvg_fill_rate: float
    ob_success_rate: float
    session_expectancy: Dict[str, float]
    regime_performance: Dict[str, float]
    liquidity_sweep_success: float
    premium_discount_effectiveness: float

class ICTConceptEvaluator:
    """Rigorous ICT concept evaluation system"""
    
    def __init__(self):
        self.kill_rules = {
            'expectancy_threshold': 0.0,
            'max_drawdown_warning': 0.30,
            'max_drawdown_kill': 0.50,
            'min_trades': 30,
            'fragile_session_threshold': 0.8  # 80% of profit from one session
        }
        
        self.ict_components = {
            'market_structure': False,
            'liquidity_concepts': False,
            'fair_value_gaps': False,
            'order_blocks': False,
            'premium_discount': False,
            'time_based': False,
            'power_of_three': False
        }
        
    def evaluate_ict_strategy(self, 
                            trades: List[Dict], 
                            market_data: pd.DataFrame,
                            strategy_components: List[str],
                            visual_data: Optional[Dict] = None) -> Dict:
        """
        Comprehensive ICT strategy evaluation
        
        Args:
            trades: List of trade dictionaries with full trade data
            market_data: Historical price data
            strategy_components: List of ICT concepts used
            visual_data: Optional computer vision analysis results
        """
        
        logger.info("🔬 Starting ICT Concept Evaluation")
        
        # SECTION 1: Strategy & ICT Components Used
        strategy_analysis = self._analyze_strategy_components(strategy_components)
        
        # SECTION 2: Quantified ICT Features
        ict_features = self._extract_ict_features(trades, market_data)
        
        # SECTION 3: Performance Metrics
        performance_metrics = self._calculate_comprehensive_metrics(trades)
        
        # SECTION 4: CV-Derived Regime & Liquidity Analysis
        cv_analysis = self._analyze_cv_data(visual_data) if visual_data else {}
        
        # SECTION 5: Risk, Drawdown & Fragility Assessment
        risk_assessment = self._assess_risk_fragility(performance_metrics, ict_features)
        
        # SECTION 6: Final Verdict
        verdict = self._generate_final_verdict(
            performance_metrics, 
            ict_features, 
            risk_assessment,
            strategy_analysis
        )
        
        # SECTION 7: Technical Next Steps
        next_steps = self._recommend_next_steps(verdict, performance_metrics, ict_features)
        
        return {
            'strategy_analysis': strategy_analysis,
            'ict_features': ict_features,
            'performance_metrics': performance_metrics,
            'cv_analysis': cv_analysis,
            'risk_assessment': risk_assessment,
            'verdict': verdict,
            'next_steps': next_steps,
            'evaluation_timestamp': datetime.now().isoformat()
        }
    
    def _analyze_strategy_components(self, components: List[str]) -> Dict:
        """Analyze which ICT concepts are being used"""
        component_analysis = {}
        
        for component in components:
            self.ict_components[component] = True
            component_analysis[component] = {
                'used': True,
                'description': self._get_component_description(component),
                'measurable': True,
                'hypothesis': f"{component} provides repeatable edge"
            }
        
        return {
            'total_components': len(components),
            'components': component_analysis,
            'complexity_score': self._calculate_complexity_score(components)
        }
    
    def _extract_ict_features(self, trades: List[Dict], market_data: pd.DataFrame) -> ICTFeatures:
        """Extract and quantify ICT concept features from trades"""
        
        # Market Structure Analysis
        market_structure_score = self._analyze_market_structure_effectiveness(trades, market_data)
        
        # Liquidity Analysis
        liquidity_density = self._calculate_liquidity_density_score(trades)
        
        # FVG Analysis
        fvg_fill_rate = self._calculate_fvg_effectiveness(trades)
        
        # Order Block Analysis
        ob_success_rate = self._calculate_ob_effectiveness(trades)
        
        # Session-based Performance
        session_expectancy = self._calculate_session_expectancy(trades)
        
        # Regime-based Performance
        regime_performance = self._calculate_regime_performance(trades, market_data)
        
        # Liquidity Sweep Success
        liquidity_sweep_success = self._calculate_liquidity_sweep_success(trades)
        
        # Premium/Discount Effectiveness
        premium_discount_effectiveness = self._calculate_premium_discount_effectiveness(trades)
        
        return ICTFeatures(
            market_structure_score=market_structure_score,
            liquidity_density=liquidity_density,
            fvg_fill_rate=fvg_fill_rate,
            ob_success_rate=ob_success_rate,
            session_expectancy=session_expectancy,
            regime_performance=regime_performance,
            liquidity_sweep_success=liquidity_sweep_success,
            premium_discount_effectiveness=premium_discount_effectiveness
        )
    
    def _calculate_comprehensive_metrics(self, trades: List[Dict]) -> ICTMetrics:
        """Calculate all required performance metrics"""
        
        if not trades:
            return ICTMetrics(0, 0, 1.0, 0, 0, 0, 0, 0, 0)
        
        # Basic metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # P&L metrics
        total_pnl = sum(t['pnl'] for t in trades)
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # Risk metrics
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Expectancy per trade
        expectancy = (avg_win * win_rate) - (abs(avg_loss) * (1 - win_rate))
        
        # Drawdown calculation
        equity_curve = self._build_equity_curve(trades)
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        
        # Sharpe ratio
        returns = np.diff(equity_curve) / equity_curve[:-1]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        return ICTMetrics(
            expectancy=expectancy,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_trades=total_trades,
            net_pnl=total_pnl
        )
    
    def _assess_risk_fragility(self, metrics: ICTMetrics, features: ICTFeatures) -> Dict:
        """Assess risk factors and strategy fragility"""
        
        risk_factors = []
        fragility_score = 0
        
        # Kill Rule 1: Expectancy ≤ 0
        if metrics.expectancy <= 0:
            risk_factors.append("CRITICAL: Negative expectancy - no edge")
            fragility_score += 100
        
        # Kill Rule 2: Drawdown assessment
        if metrics.max_drawdown > self.kill_rules['max_drawdown_kill']:
            risk_factors.append(f"CRITICAL: Drawdown {metrics.max_drawdown:.1%} exceeds 50% limit")
            fragility_score += 100
        elif metrics.max_drawdown > self.kill_rules['max_drawdown_warning']:
            risk_factors.append(f"WARNING: High drawdown {metrics.max_drawdown:.1%}")
            fragility_score += 50
        
        # Kill Rule 3: Insufficient trades
        if metrics.total_trades < self.kill_rules['min_trades']:
            risk_factors.append(f"WARNING: Only {metrics.total_trades} trades - insufficient sample")
            fragility_score += 30
        
        # Fragility check: Session dependence
        session_fragility = self._check_session_fragility(features.session_expectancy)
        if session_fragility > self.kill_rules['fragile_session_threshold']:
            risk_factors.append(f"FRAGILE: {session_fragility:.1%} of profit from single session")
            fragility_score += 40
        
        # Fragility check: Regime dependence
        regime_fragility = self._check_regime_fragility(features.regime_performance)
        if regime_fragility > self.kill_rules['fragile_session_threshold']:
            risk_factors.append(f"FRAGILE: {regime_fragility:.1%} of profit from single regime")
            fragility_score += 40
        
        # ICT component failure analysis
        failed_components = self._identify_failed_ict_components(features)
        if failed_components:
            risk_factors.append(f"ICT Components failing: {', '.join(failed_components)}")
            fragility_score += len(failed_components) * 20
        
        return {
            'risk_factors': risk_factors,
            'fragility_score': fragility_score,
            'risk_level': self._classify_risk_level(fragility_score),
            'survivability': fragility_score < 100,
            'capital_risk': 'HIGH' if fragility_score >= 100 else 'MEDIUM' if fragility_score >= 50 else 'LOW'
        }
    
    def _generate_final_verdict(self, 
                              metrics: ICTMetrics, 
                              features: ICTFeatures, 
                              risk_assessment: Dict,
                              strategy_analysis: Dict) -> Dict:
        """Generate final verdict with strict mathematical criteria"""
        
        verdict_score = 0
        verdict_reasons = []
        
        # Positive factors
        if metrics.expectancy > 0:
            verdict_score += 25
            verdict_reasons.append(f"Positive expectancy: {metrics.expectancy:.2f}")
        
        if metrics.profit_factor > 1.5:
            verdict_score += 20
            verdict_reasons.append(f"Strong profit factor: {metrics.profit_factor:.2f}")
        
        if metrics.sharpe_ratio > 1.0:
            verdict_score += 15
            verdict_reasons.append(f"Adequate risk-adjusted returns: Sharpe {metrics.sharpe_ratio:.2f}")
        
        if metrics.max_drawdown < 0.20:
            verdict_score += 15
            verdict_reasons.append(f"Controlled drawdown: {metrics.max_drawdown:.1%}")
        
        if metrics.total_trades >= self.kill_rules['min_trades']:
            verdict_score += 10
            verdict_reasons.append(f"Sufficient sample size: {metrics.total_trades} trades")
        
        # Negative factors (already captured in risk assessment)
        if risk_assessment['fragility_score'] >= 100:
            verdict_score -= 50
        
        # Determine verdict
        if verdict_score >= 70 and risk_assessment['fragility_score'] < 50:
            verdict = Verdict.DEPLOY
            recommendation = "Deploy with small, controlled capital allocation"
        elif verdict_score >= 40 and risk_assessment['fragility_score'] < 80:
            verdict = Verdict.OPTIMIZE
            recommendation = "Optimize specific components before deployment"
        else:
            verdict = Verdict.KILL
            recommendation = "Edge not real - reject strategy"
        
        return {
            'verdict': verdict.value,
            'verdict_score': verdict_score,
            'recommendation': recommendation,
            'reasons': verdict_reasons,
            'failed_ict_components': self._identify_failed_ict_components(features),
            'successful_ict_components': self._identify_successful_ict_components(features),
            'mathematical_justification': {
                'expectancy': metrics.expectancy,
                'profit_factor': metrics.profit_factor,
                'max_drawdown': metrics.max_drawdown,
                'sharpe_ratio': metrics.sharpe_ratio,
                'sample_size': metrics.total_trades
            }
        }
    
    def _recommend_next_steps(self, verdict: Dict, metrics: ICTMetrics, features: ICTFeatures) -> List[str]:
        """Generate technical recommendations based on evaluation"""
        
        steps = []
        
        if verdict['verdict'] == Verdict.KILL.value:
            steps.extend([
                "ABANDON strategy - edge not mathematically valid",
                "Analyze failed ICT components for learning",
                "Consider alternative market approaches",
                "Review data quality and parameter sensitivity"
            ])
        
        elif verdict['verdict'] == Verdict.OPTIMIZE.value:
            failed_components = verdict['failed_ict_components']
            if failed_components:
                steps.append(f"Focus optimization on: {', '.join(failed_components)}")
            
            if metrics.max_drawdown > 0.25:
                steps.append("Implement stricter position sizing and risk controls")
            
            if metrics.expectancy < 0.5:
                steps.append("Improve entry filters and exit conditions")
            
            if metrics.total_trades < 50:
                steps.append("Expand testing period and market conditions")
        
        else:  # DEPLOY
            steps.extend([
                "Deploy with maximum 2-5% of capital",
                "Implement real-time monitoring of all ICT components",
                "Set automated kill switches for drawdown breaches",
                "Track regime-specific performance going forward"
            ])
        
        # Always include data recommendations
        steps.extend([
            "Validate results with out-of-sample data",
            "Test across different market types (crypto/forex)",
            "Include transaction costs and slippage in final validation"
        ])
        
        return steps
    
    # Helper methods for feature extraction
    def _analyze_market_structure_effectiveness(self, trades: List[Dict], market_data: pd.DataFrame) -> float:
        """Quantify market structure concept effectiveness"""
        # Implementation would analyze MSS/BOS success rates
        return 0.65  # Placeholder
    
    def _calculate_liquidity_density_score(self, trades: List[Dict]) -> float:
        """Calculate liquidity density effectiveness"""
        # Implementation would analyze liquidity sweep success
        return 0.58  # Placeholder
    
    def _calculate_fvg_effectiveness(self, trades: List[Dict]) -> float:
        """Calculate FVG fill rate and reaction strength"""
        # Implementation would track FVG detection and outcomes
        return 0.72  # Placeholder
    
    def _calculate_ob_effectiveness(self, trades: List[Dict]) -> float:
        """Calculate order block success rate"""
        # Implementation would track OB mitigation vs invalidation
        return 0.61  # Placeholder
    
    def _calculate_session_expectancy(self, trades: List[Dict]) -> Dict[str, float]:
        """Calculate expectancy by trading session"""
        session_performance = {'Asia': 0.0, 'London': 0.0, 'NewYork': 0.0}
        # Implementation would analyze trades by session
        return session_performance
    
    def _calculate_regime_performance(self, trades: List[Dict], market_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate performance by market regime"""
        regime_performance = {'trend': 0.0, 'range': 0.0, 'expansion': 0.0, 'compression': 0.0}
        # Implementation would detect regimes and analyze performance
        return regime_performance
    
    def _calculate_liquidity_sweep_success(self, trades: List[Dict]) -> float:
        """Calculate liquidity sweep detection success"""
        return 0.68  # Placeholder
    
    def _calculate_premium_discount_effectiveness(self, trades: List[Dict]) -> float:
        """Calculate premium/discount zone effectiveness"""
        return 0.55  # Placeholder
    
    # Additional helper methods
    def _build_equity_curve(self, trades: List[Dict]) -> List[float]:
        """Build equity curve from trades"""
        equity = [10000.0]  # Starting capital
        for trade in trades:
            equity.append(equity[-1] + trade['pnl'])
        return equity
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown"""
        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_dd = max(max_dd, drawdown)
        return max_dd
    
    def _check_session_fragility(self, session_expectancy: Dict[str, float]) -> float:
        """Check if strategy is too dependent on one session"""
        if not session_expectancy:
            return 0.0
        total = sum(abs(v) for v in session_expectancy.values())
        if total == 0:
            return 0.0
        max_session = max(abs(v) for v in session_expectancy.values())
        return max_session / total
    
    def _check_regime_fragility(self, regime_performance: Dict[str, float]) -> float:
        """Check if strategy is too dependent on one regime"""
        if not regime_performance:
            return 0.0
        total = sum(abs(v) for v in regime_performance.values())
        if total == 0:
            return 0.0
        max_regime = max(abs(v) for v in regime_performance.values())
        return max_regime / total
    
    def _identify_failed_ict_components(self, features: ICTFeatures) -> List[str]:
        """Identify which ICT components are failing"""
        failed = []
        if features.market_structure_score < 0.5:
            failed.append('Market Structure')
        if features.liquidity_density < 0.5:
            failed.append('Liquidity Concepts')
        if features.fvg_fill_rate < 0.5:
            failed.append('Fair Value Gaps')
        if features.ob_success_rate < 0.5:
            failed.append('Order Blocks')
        if features.premium_discount_effectiveness < 0.5:
            failed.append('Premium/Discount')
        return failed
    
    def _identify_successful_ict_components(self, features: ICTFeatures) -> List[str]:
        """Identify which ICT components are successful"""
        successful = []
        if features.market_structure_score >= 0.6:
            successful.append('Market Structure')
        if features.liquidity_density >= 0.6:
            successful.append('Liquidity Concepts')
        if features.fvg_fill_rate >= 0.6:
            successful.append('Fair Value Gaps')
        if features.ob_success_rate >= 0.6:
            successful.append('Order Blocks')
        if features.premium_discount_effectiveness >= 0.6:
            successful.append('Premium/Discount')
        return successful
    
    def _classify_risk_level(self, fragility_score: int) -> str:
        """Classify overall risk level"""
        if fragility_score >= 100:
            return 'CRITICAL'
        elif fragility_score >= 70:
            return 'HIGH'
        elif fragility_score >= 40:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _get_component_description(self, component: str) -> str:
        """Get description of ICT component"""
        descriptions = {
            'market_structure': 'Higher highs/lows and market structure shifts',
            'liquidity_concepts': 'Buy/sell liquidity and sweeps',
            'fair_value_gaps': 'Imbalance zones and fill rates',
            'order_blocks': 'Institutional order flow zones',
            'premium_discount': 'Fibonacci-derived entry zones',
            'time_based': 'Session-based trading concepts',
            'power_of_three': 'Accumulation/manipulation/distribution'
        }
        return descriptions.get(component, 'Unknown ICT component')
    
    def _calculate_complexity_score(self, components: List[str]) -> int:
        """Calculate strategy complexity score"""
        return len(components) * 10
    
    def _analyze_cv_data(self, visual_data: Dict) -> Dict:
        """Analyze computer vision derived data"""
        if not visual_data:
            return {}
        
        return {
            'regime_detection_accuracy': visual_data.get('regime_accuracy', 0.0),
            'liquidity_heatmap_effectiveness': visual_data.get('liquidity_effectiveness', 0.0),
            'structural_feature_validation': visual_data.get('structure_validation', 0.0),
            'cv_added_value': visual_data.get('cv_value_score', 0.0)
        }
    
    def generate_evaluation_report(self, evaluation_results: Dict) -> str:
        """Generate comprehensive evaluation report"""
        
        report = []
        report.append("\n" + "="*80)
        report.append("🔬 ICT CONCEPT EVALUATION REPORT")
        report.append("="*80)
        
        # SECTION 1
        report.append("\n📊 SECTION 1: STRATEGY & ICT COMPONENTS USED")
        strategy = evaluation_results['strategy_analysis']
        report.append(f"Total ICT Components: {strategy['total_components']}")
        report.append(f"Complexity Score: {strategy['complexity_score']}")
        for comp, details in strategy['components'].items():
            report.append(f"  • {comp.title()}: {details['description']}")
        
        # SECTION 2
        report.append("\n🔍 SECTION 2: QUANTIFIED ICT FEATURES")
        features = evaluation_results['ict_features']
        report.append(f"Market Structure Score: {features.market_structure_score:.2f}")
        report.append(f"Liquidity Density: {features.liquidity_density:.2f}")
        report.append(f"FVG Fill Rate: {features.fvg_fill_rate:.2f}")
        report.append(f"Order Block Success: {features.ob_success_rate:.2f}")
        report.append(f"Liquidity Sweep Success: {features.liquidity_sweep_success:.2f}")
        report.append(f"Premium/Discount Effectiveness: {features.premium_discount_effectiveness:.2f}")
        
        # SECTION 3
        report.append("\n📈 SECTION 3: PERFORMANCE METRICS")
        metrics = evaluation_results['performance_metrics']
        report.append(f"Net P&L: ${metrics.net_pnl:,.2f}")
        report.append(f"Total Trades: {metrics.total_trades}")
        report.append(f"Win Rate: {metrics.win_rate:.1%}")
        report.append(f"Expectancy per Trade: ${metrics.expectancy:.2f}")
        report.append(f"Profit Factor: {metrics.profit_factor:.2f}")
        report.append(f"Max Drawdown: {metrics.max_drawdown:.1%}")
        report.append(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        report.append(f"Avg Win: ${metrics.avg_win:.2f}")
        report.append(f"Avg Loss: ${metrics.avg_loss:.2f}")
        
        # SECTION 4
        if evaluation_results['cv_analysis']:
            report.append("\n👁️ SECTION 4: CV-DERIVED REGIME & LIQUIDITY ANALYSIS")
            cv = evaluation_results['cv_analysis']
            for key, value in cv.items():
                report.append(f"{key.replace('_', ' ').title()}: {value:.2f}")
        
        # SECTION 5
        report.append("\n⚠️ SECTION 5: RISK, DRAWDOWN & FRAGILITY ASSESSMENT")
        risk = evaluation_results['risk_assessment']
        report.append(f"Risk Level: {risk['risk_level']}")
        report.append(f"Fragility Score: {risk['fragility_score']}")
        report.append(f"Capital Risk: {risk['capital_risk']}")
        report.append(f"Survivability: {risk['survivability']}")
        report.append("Risk Factors:")
        for factor in risk['risk_factors']:
            report.append(f"  • {factor}")
        
        # SECTION 6
        report.append("\n⚖️ SECTION 6: FINAL VERDICT")
        verdict = evaluation_results['verdict']
        report.append(f"VERDICT: {verdict['verdict']}")
        report.append(f"Verdict Score: {verdict['verdict_score']}/100")
        report.append(f"Recommendation: {verdict['recommendation']}")
        report.append("Mathematical Justification:")
        for key, value in verdict['mathematical_justification'].items():
            report.append(f"  • {key.title()}: {value}")
        
        if verdict['failed_ict_components']:
            report.append(f"Failed ICT Components: {', '.join(verdict['failed_ict_components'])}")
        if verdict['successful_ict_components']:
            report.append(f"Successful ICT Components: {', '.join(verdict['successful_ict_components'])}")
        
        # SECTION 7
        report.append("\n🔧 SECTION 7: TECHNICAL NEXT STEPS")
        for i, step in enumerate(evaluation_results['next_steps'], 1):
            report.append(f"{i}. {step}")
        
        report.append("\n" + "="*80)
        report.append(f"Evaluation completed: {evaluation_results['evaluation_timestamp']}")
        report.append("="*80)
        
        return "\n".join(report)
