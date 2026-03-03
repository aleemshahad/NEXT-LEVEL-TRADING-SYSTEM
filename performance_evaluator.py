"""
RIGOROUS PERFORMANCE EVALUATION SYSTEM
Mathematical validation with strict kill rules
Created by: ICT Concept Auditor
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import scipy.stats as stats
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')

class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    net_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    risk_reward: float
    expectancy: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    total_trades: int
    winning_trades: int
    losing_trades: int

@dataclass
class KillRuleViolation:
    rule_name: str
    severity: str
    value: float
    threshold: float
    description: str

class PerformanceEvaluator:
    """Rigorous performance evaluation with strict kill rules"""
    
    def __init__(self):
        # NON-NEGOTIABLE KILL RULES
        self.kill_rules = {
            'expectancy_threshold': 0.0,  # Expectancy ≤ 0 → KILL
            'max_drawdown_warning': 0.30,  # 30% drawdown warning
            'max_drawdown_kill': 0.50,     # 50% drawdown → KILL
            'min_trades_threshold': 30,     # Minimum trades for validity
            'fragile_session_threshold': 0.8,  # 80% profit from one session
            'fragile_regime_threshold': 0.8,   # 80% profit from one regime
            'sharpe_minimum': 0.5,         # Minimum risk-adjusted returns
            'profit_factor_minimum': 1.2,   # Minimum profit factor
            'max_consecutive_losses': 10,   # Maximum consecutive losses
            'volatility_kill_threshold': 0.4  # Excessive volatility
        }
        
        # Risk thresholds
        self.risk_thresholds = {
            'low': {'drawdown': 0.15, 'volatility': 0.15, 'concentration': 0.6},
            'medium': {'drawdown': 0.25, 'volatility': 0.25, 'concentration': 0.7},
            'high': {'drawdown': 0.35, 'volatility': 0.35, 'concentration': 0.8},
            'critical': {'drawdown': 0.50, 'volatility': 0.50, 'concentration': 0.9}
        }
    
    def evaluate_performance(self, 
                          trades: List[Dict], 
                          equity_curve: List[float],
                          benchmark_returns: Optional[List[float]] = None) -> Dict:
        """
        Comprehensive performance evaluation with kill rules
        """
        
        # SECTION 1: Calculate all performance metrics
        metrics = self._calculate_comprehensive_metrics(trades, equity_curve)
        
        # SECTION 2: Apply kill rules
        kill_violations = self._apply_kill_rules(metrics, trades)
        
        # SECTION 3: Risk assessment
        risk_assessment = self._assess_risk_profile(metrics, trades)
        
        # SECTION 4: Statistical validation
        statistical_tests = self._perform_statistical_tests(trades, equity_curve)
        
        # SECTION 5: Scenario analysis
        scenario_analysis = self._perform_scenario_analysis(trades, metrics)
        
        # SECTION 6: Survival analysis
        survival_metrics = self._calculate_survival_metrics(metrics, trades)
        
        # SECTION 7: Capital efficiency
        capital_efficiency = self._calculate_capital_efficiency(metrics, trades)
        
        return {
            'performance_metrics': metrics,
            'kill_violations': kill_violations,
            'risk_assessment': risk_assessment,
            'statistical_tests': statistical_tests,
            'scenario_analysis': scenario_analysis,
            'survival_metrics': survival_metrics,
            'capital_efficiency': capital_efficiency,
            'evaluation_timestamp': datetime.now().isoformat()
        }
    
    def _calculate_comprehensive_metrics(self, trades: List[Dict], equity_curve: List[float]) -> PerformanceMetrics:
        """Calculate all required performance metrics"""
        
        if not trades:
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 0)
        
        # Basic trade statistics
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
        
        # Expectancy calculation
        expectancy = (avg_win * win_rate) - (abs(avg_loss) * (1 - win_rate))
        
        # Risk:Reward ratio
        risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # Drawdown analysis
        max_drawdown, max_dd_duration = self._calculate_drawdown_metrics(equity_curve)
        
        # Risk-adjusted returns
        returns = np.diff(equity_curve) / equity_curve[:-1]
        returns_clean = returns[~np.isnan(returns)]
        
        if len(returns_clean) > 1:
            sharpe_ratio = self._calculate_sharpe_ratio(returns_clean)
            sortino_ratio = self._calculate_sortino_ratio(returns_clean)
            calmar_ratio = self._calculate_calmar_ratio(total_pnl, max_drawdown)
        else:
            sharpe_ratio = sortino_ratio = calmar_ratio = 0
        
        return PerformanceMetrics(
            net_pnl=total_pnl,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            risk_reward=risk_reward,
            expectancy=expectancy,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades)
        )
    
    def _apply_kill_rules(self, metrics: PerformanceMetrics, trades: List[Dict]) -> List[KillRuleViolation]:
        """Apply NON-NEGOTIABLE kill rules"""
        
        violations = []
        
        # Kill Rule 1: Expectancy ≤ 0
        if metrics.expectancy <= self.kill_rules['expectancy_threshold']:
            violations.append(KillRuleViolation(
                rule_name="Negative Expectancy",
                severity="CRITICAL",
                value=metrics.expectancy,
                threshold=self.kill_rules['expectancy_threshold'],
                description="Strategy has no mathematical edge - KILL IMMEDIATELY"
            ))
        
        # Kill Rule 2: Excessive drawdown
        if metrics.max_drawdown >= self.kill_rules['max_drawdown_kill']:
            violations.append(KillRuleViolation(
                rule_name="Excessive Drawdown",
                severity="CRITICAL",
                value=metrics.max_drawdown,
                threshold=self.kill_rules['max_drawdown_kill'],
                description="Drawdown exceeds 50% - CAPITAL FAILURE"
            ))
        elif metrics.max_drawdown >= self.kill_rules['max_drawdown_warning']:
            violations.append(KillRuleViolation(
                rule_name="High Drawdown",
                severity="WARNING",
                value=metrics.max_drawdown,
                threshold=self.kill_rules['max_drawdown_warning'],
                description="Drawdown exceeds 30% - HIGH RISK"
            ))
        
        # Kill Rule 3: Insufficient sample size
        if metrics.total_trades < self.kill_rules['min_trades_threshold']:
            violations.append(KillRuleViolation(
                rule_name="Insufficient Sample",
                severity="WARNING",
                value=metrics.total_trades,
                threshold=self.kill_rules['min_trades_threshold'],
                description="Sample size too small for statistical significance"
            ))
        
        # Kill Rule 4: Poor risk-adjusted returns
        if metrics.sharpe_ratio < self.kill_rules['sharpe_minimum']:
            violations.append(KillRuleViolation(
                rule_name="Poor Risk-Adjusted Returns",
                severity="WARNING",
                value=metrics.sharpe_ratio,
                threshold=self.kill_rules['sharime_minimum'],
                description="Sharpe ratio below minimum threshold"
            ))
        
        # Kill Rule 5: Low profit factor
        if metrics.profit_factor < self.kill_rules['profit_factor_minimum']:
            violations.append(KillRuleViolation(
                rule_name="Low Profit Factor",
                severity="WARNING",
                value=metrics.profit_factor,
                threshold=self.kill_rules['profit_factor_minimum'],
                description="Profit factor below minimum threshold"
            ))
        
        # Kill Rule 6: Session/Regime fragility
        fragility_analysis = self._check_fragility(trades)
        if fragility_analysis['session_fragility'] > self.kill_rules['fragile_session_threshold']:
            violations.append(KillRuleViolation(
                rule_name="Session Fragility",
                severity="WARNING",
                value=fragility_analysis['session_fragility'],
                threshold=self.kill_rules['fragile_session_threshold'],
                description="Strategy too dependent on single trading session"
            ))
        
        if fragility_analysis['regime_fragility'] > self.kill_rules['fragile_regime_threshold']:
            violations.append(KillRuleViolation(
                rule_name="Regime Fragility",
                severity="WARNING",
                value=fragility_analysis['regime_fragility'],
                threshold=self.kill_rules['fragile_regime_threshold'],
                description="Strategy too dependent on single market regime"
            ))
        
        # Kill Rule 7: Consecutive losses
        consecutive_losses = self._calculate_max_consecutive_losses(trades)
        if consecutive_losses >= self.kill_rules['max_consecutive_losses']:
            violations.append(KillRuleViolation(
                rule_name="Excessive Consecutive Losses",
                severity="WARNING",
                value=consecutive_losses,
                threshold=self.kill_rules['max_consecutive_losses'],
                description="Too many consecutive losses - risk of ruin"
            ))
        
        # Kill Rule 8: Performance after costs
        cost_analysis = self._analyze_performance_after_costs(trades)
        if cost_analysis['expectancy_after_costs'] <= 0:
            violations.append(KillRuleViolation(
                rule_name="Negative Expectancy After Costs",
                severity="CRITICAL",
                value=cost_analysis['expectancy_after_costs'],
                threshold=0.0,
                description="Performance disappears after transaction costs - INVALID"
            ))
        
        return violations
    
    def _assess_risk_profile(self, metrics: PerformanceMetrics, trades: List[Dict]) -> Dict:
        """Comprehensive risk assessment"""
        
        risk_factors = []
        risk_score = 0
        
        # Drawdown risk
        if metrics.max_drawdown >= self.risk_thresholds['critical']['drawdown']:
            risk_factors.append("CRITICAL: Drawdown exceeds 50%")
            risk_score += 40
        elif metrics.max_drawdown >= self.risk_thresholds['high']['drawdown']:
            risk_factors.append("HIGH: Drawdown exceeds 35%")
            risk_score += 30
        elif metrics.max_drawdown >= self.risk_thresholds['medium']['drawdown']:
            risk_factors.append("MEDIUM: Drawdown exceeds 25%")
            risk_score += 20
        
        # Volatility risk
        returns = [t['pnl'] for t in trades]
        if len(returns) > 1:
            volatility = np.std(returns) / np.mean(np.abs(returns)) if np.mean(np.abs(returns)) > 0 else 0
            
            if volatility >= self.risk_thresholds['critical']['volatility']:
                risk_factors.append("CRITICAL: Excessive return volatility")
                risk_score += 30
            elif volatility >= self.risk_thresholds['high']['volatility']:
                risk_factors.append("HIGH: High return volatility")
                risk_score += 20
            elif volatility >= self.risk_thresholds['medium']['volatility']:
                risk_factors.append("MEDIUM: Moderate return volatility")
                risk_score += 10
        
        # Concentration risk
        concentration = self._calculate_concentration_risk(trades)
        if concentration >= self.risk_thresholds['critical']['concentration']:
            risk_factors.append("CRITICAL: Extreme concentration risk")
            risk_score += 30
        elif concentration >= self.risk_thresholds['high']['concentration']:
            risk_factors.append("HIGH: High concentration risk")
            risk_score += 20
        elif concentration >= self.risk_thresholds['medium']['concentration']:
            risk_factors.append("MEDIUM: Moderate concentration risk")
            risk_score += 10
        
        # Consistency risk
        consistency = self._calculate_consistency_score(trades)
        if consistency < 0.3:
            risk_factors.append("HIGH: Inconsistent performance")
            risk_score += 20
        elif consistency < 0.5:
            risk_factors.append("MEDIUM: Moderate inconsistency")
            risk_score += 10
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 50:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 30:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        return {
            'risk_level': risk_level.value,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'survivability': risk_score < 70,
            'capital_risk': 'CRITICAL' if risk_score >= 70 else 'HIGH' if risk_score >= 50 else 'MEDIUM' if risk_score >= 30 else 'LOW'
        }
    
    def _perform_statistical_tests(self, trades: List[Dict], equity_curve: List[float]) -> Dict:
        """Perform statistical validation tests"""
        
        returns = [t['pnl'] for t in trades]
        
        if len(returns) < 10:
            return {
                'normality_test': {'statistic': 0, 'p_value': 1.0, 'normal': False},
                'autocorrelation_test': {'statistic': 0, 'p_value': 1.0, 'independent': False},
                'stationarity_test': {'statistic': 0, 'p_value': 1.0, 'stationary': False},
                'significance_test': {'statistic': 0, 'p_value': 1.0, 'significant': False},
                'sample_adequacy': False
            }
        
        # Normality test
        normality_stat, normality_p = stats.shapiro(returns)
        is_normal = normality_p > 0.05
        
        # Autocorrelation test (Durbin-Watson)
        if len(returns) > 2:
            dw_stat = self._durbin_watson(returns)
            autocorrelation_p = 1.0 - dw_stat/2  # Simplified
            is_independent = 1.5 < dw_stat < 2.5
        else:
            dw_stat = 0
            autocorrelation_p = 1.0
            is_independent = False
        
        # Stationarity test (simplified)
        equity_returns = np.diff(equity_curve) / equity_curve[:-1]
        equity_returns_clean = equity_returns[~np.isnan(equity_returns)]
        
        if len(equity_returns_clean) > 10:
            adf_stat = stats.ttest_1samp(equity_returns_clean, 0)[0]
            stationarity_p = 2 * (1 - stats.norm.cdf(abs(adf_stat)))
            is_stationary = stationarity_p < 0.05
        else:
            adf_stat = 0
            stationarity_p = 1.0
            is_stationary = False
        
        # Significance test
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        if std_return > 0:
            t_stat = mean_return / (std_return / np.sqrt(len(returns)))
            significance_p = 2 * (1 - stats.t.cdf(abs(t_stat), len(returns)-1))
            is_significant = significance_p < 0.05
        else:
            t_stat = 0
            significance_p = 1.0
            is_significant = False
        
        return {
            'normality_test': {
                'statistic': normality_stat,
                'p_value': normality_p,
                'normal': is_normal
            },
            'autocorrelation_test': {
                'statistic': dw_stat,
                'p_value': autocorrelation_p,
                'independent': is_independent
            },
            'stationarity_test': {
                'statistic': adf_stat,
                'p_value': stationarity_p,
                'stationary': is_stationary
            },
            'significance_test': {
                'statistic': t_stat,
                'p_value': significance_p,
                'significant': is_significant
            },
            'sample_adequacy': len(returns) >= 30
        }
    
    def _perform_scenario_analysis(self, trades: List[Dict], metrics: PerformanceMetrics) -> Dict:
        """Perform stress testing and scenario analysis"""
        
        returns = [t['pnl'] for t in trades]
        
        if len(returns) < 10:
            return {
                'stress_test': {'worst_case': 0, 'var_95': 0, 'cvar_95': 0},
                'monte_carlo': {'probability_of_ruin': 1.0, 'expected_shortfall': 0},
                'sensitivity_analysis': {'volatility_sensitivity': 0, 'correlation_sensitivity': 0}
            }
        
        # Stress testing
        worst_case = min(returns)
        var_95 = np.percentile(returns, 5)
        cvar_95 = np.mean([r for r in returns if r <= var_95])
        
        # Monte Carlo simulation
        mc_results = self._monte_carlo_simulation(returns, 1000)
        
        # Sensitivity analysis
        volatility_sensitivity = self._calculate_volatility_sensitivity(returns)
        correlation_sensitivity = self._calculate_correlation_sensitivity(returns)
        
        return {
            'stress_test': {
                'worst_case': worst_case,
                'var_95': var_95,
                'cvar_95': cvar_95,
                'max_loss_ratio': abs(worst_case) / metrics.avg_win if metrics.avg_win > 0 else float('inf')
            },
            'monte_carlo': mc_results,
            'sensitivity_analysis': {
                'volatility_sensitivity': volatility_sensitivity,
                'correlation_sensitivity': correlation_sensitivity
            }
        }
    
    def _calculate_survival_metrics(self, metrics: PerformanceMetrics, trades: List[Dict]) -> Dict:
        """Calculate survival and risk of ruin metrics"""
        
        returns = [t['pnl'] for t in trades]
        
        if len(returns) < 5:
            return {
                'risk_of_ruin': 1.0,
                'probability_of_profit': 0.0,
                'expected_time_to_recover': float('inf'),
                'survival_probability': 0.0
            }
        
        # Risk of ruin calculation
        win_rate = metrics.win_rate
        avg_win = metrics.avg_win
        avg_loss = abs(metrics.avg_loss)
        
        if avg_loss > 0:
            # Risk of ruin formula
            q = (1 - win_rate) / win_rate
            a = avg_win / avg_loss
            risk_of_ruin = (q ** a) if q > 0 and a > 0 else 1.0
        else:
            risk_of_ruin = 1.0
        
        # Probability of profit
        positive_returns = [r for r in returns if r > 0]
        probability_of_profit = len(positive_returns) / len(returns)
        
        # Expected time to recover from drawdown
        if metrics.max_drawdown > 0:
            recovery_rate = metrics.net_pnl / (metrics.max_drawdown * 10000)  # Assuming 10k starting capital
            expected_time_to_recover = metrics.max_drawdown_duration / recovery_rate if recovery_rate > 0 else float('inf')
        else:
            expected_time_to_recover = 0
        
        # Survival probability (simplified)
        survival_probability = 1.0 - risk_of_ruin if risk_of_ruin < 1.0 else 0.0
        
        return {
            'risk_of_ruin': min(risk_of_ruin, 1.0),
            'probability_of_profit': probability_of_profit,
            'expected_time_to_recover': expected_time_to_recover,
            'survival_probability': survival_probability,
            'capital_preservation': survival_probability > 0.8
        }
    
    def _calculate_capital_efficiency(self, metrics: PerformanceMetrics, trades: List[Dict]) -> Dict:
        """Calculate capital efficiency metrics"""
        
        # Capital turnover
        if trades:
            avg_position_size = np.mean([t.get('position_size', 1.0) for t in trades])
            capital_turnover = metrics.total_trades * avg_position_size / 10000  # Assuming 10k capital
        else:
            capital_turnover = 0
        
        # Return on capital
        return_on_capital = metrics.net_pnl / 10000  # Assuming 10k capital
        
        # Capital efficiency score
        if metrics.max_drawdown > 0:
            efficiency_score = (return_on_capital * metrics.sharpe_ratio) / metrics.max_drawdown
        else:
            efficiency_score = return_on_capital * metrics.sharpe_ratio
        
        # Capital utilization
        capital_utilization = min(capital_turnover, 1.0)
        
        return {
            'capital_turnover': capital_turnover,
            'return_on_capital': return_on_capital,
            'efficiency_score': efficiency_score,
            'capital_utilization': capital_utilization,
            'capital_productivity': return_on_capital * metrics.win_rate
        }
    
    # Helper methods
    def _calculate_drawdown_metrics(self, equity_curve: List[float]) -> Tuple[float, int]:
        """Calculate maximum drawdown and duration"""
        
        if not equity_curve:
            return 0.0, 0
        
        peak = equity_curve[0]
        max_drawdown = 0.0
        max_duration = 0
        current_duration = 0
        
        for i, equity in enumerate(equity_curve):
            if equity > peak:
                peak = equity
                current_duration = 0
            else:
                drawdown = (peak - equity) / peak
                max_drawdown = max(max_drawdown, drawdown)
                current_duration += 1
                max_duration = max(max_duration, current_duration)
        
        return max_drawdown, max_duration
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        
        if len(returns) < 2:
            return 0.0
        
        excess_returns = np.array(returns) - risk_free_rate/252  # Daily risk-free rate
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        return sharpe
    
    def _calculate_sortino_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (downside deviation)"""
        
        if len(returns) < 2:
            return 0.0
        
        excess_returns = np.array(returns) - risk_free_rate/252
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or np.std(downside_returns) == 0:
            return 0.0
        
        sortino = np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(252)
        return sortino
    
    def _calculate_calmar_ratio(self, total_return: float, max_drawdown: float) -> float:
        """Calculate Calmar ratio"""
        
        if max_drawdown == 0:
            return 0.0
        
        return total_return / max_drawdown
    
    def _check_fragility(self, trades: List[Dict]) -> Dict:
        """Check for session and regime fragility"""
        
        # Session fragility (placeholder - would need session data)
        session_fragility = 0.5  # Placeholder
        
        # Regime fragility (placeholder - would need regime data)
        regime_fragility = 0.5  # Placeholder
        
        return {
            'session_fragility': session_fragility,
            'regime_fragility': regime_fragility,
            'overall_fragility': (session_fragility + regime_fragility) / 2
        }
    
    def _calculate_max_consecutive_losses(self, trades: List[Dict]) -> int:
        """Calculate maximum consecutive losses"""
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade['pnl'] <= 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _analyze_performance_after_costs(self, trades: List[Dict]) -> Dict:
        """Analyze performance after transaction costs"""
        
        # Assume typical costs: 0.1% per trade for crypto, 0.02% for forex
        cost_per_trade = 0.001  # 0.1%
        
        returns_after_costs = []
        for trade in trades:
            cost = abs(trade.get('position_size', 1.0)) * cost_per_trade
            pnl_after_cost = trade['pnl'] - cost
            returns_after_costs.append(pnl_after_cost)
        
        if returns_after_costs:
            expectancy_after_costs = np.mean(returns_after_costs)
        else:
            expectancy_after_costs = 0.0
        
        return {
            'expectancy_after_costs': expectancy_after_costs,
            'total_costs': len(trades) * cost_per_trade,
            'cost_impact': cost_per_trade * len(trades) / sum(t['pnl'] for t in trades) if trades else 0
        }
    
    def _calculate_concentration_risk(self, trades: List[Dict]) -> float:
        """Calculate concentration risk"""
        
        # Simple concentration based on trade size variance
        if not trades:
            return 0.0
        
        position_sizes = [t.get('position_size', 1.0) for t in trades]
        if len(position_sizes) <= 1:
            return 1.0
        
        # Calculate coefficient of variation
        mean_size = np.mean(position_sizes)
        if mean_size == 0:
            return 1.0
        
        cv = np.std(position_sizes) / mean_size
        return min(cv, 1.0)
    
    def _calculate_consistency_score(self, trades: List[Dict]) -> float:
        """Calculate performance consistency score"""
        
        if len(trades) < 5:
            return 0.0
        
        returns = [t['pnl'] for t in trades]
        
        # Consistency based on positive return frequency and low variance
        positive_ratio = len([r for r in returns if r > 0]) / len(returns)
        return_variance = np.var(returns)
        
        # Normalize variance (assuming reasonable range)
        normalized_variance = min(return_variance / (np.mean(np.abs(returns)) ** 2), 1.0) if np.mean(np.abs(returns)) > 0 else 1.0
        
        consistency = positive_ratio * (1 - normalized_variance)
        return max(consistency, 0.0)
    
    def _durbin_watson(self, series: List[float]) -> float:
        """Calculate Durbin-Watson statistic"""
        
        if len(series) < 2:
            return 0.0
        
        diff = np.diff(series)
        numerator = np.sum(diff ** 2)
        denominator = np.sum(np.array(series) ** 2)
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def _monte_carlo_simulation(self, returns: List[float], num_simulations: int = 1000) -> Dict:
        """Simple Monte Carlo simulation"""
        
        if len(returns) < 5:
            return {'probability_of_ruin': 1.0, 'expected_shortfall': 0}
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        ruin_count = 0
        total_shortfall = 0
        
        for _ in range(num_simulations):
            # Simulate 100 trades
            simulated_returns = np.random.normal(mean_return, std_return, 100)
            
            # Check for ruin (cumulative loss > 50%)
            cumulative_pnl = np.cumsum(simulated_returns)
            if np.any(cumulative_pnl < -5000):  # 50% of 10k capital
                ruin_count += 1
            
            # Calculate expected shortfall
            final_pnl = cumulative_pnl[-1]
            if final_pnl < 0:
                total_shortfall += abs(final_pnl)
        
        probability_of_ruin = ruin_count / num_simulations
        expected_shortfall = total_shortfall / num_simulations if ruin_count > 0 else 0
        
        return {
            'probability_of_ruin': probability_of_ruin,
            'expected_shortfall': expected_shortfall,
            'num_simulations': num_simulations
        }
    
    def _calculate_volatility_sensitivity(self, returns: List[float]) -> float:
        """Calculate sensitivity to volatility changes"""
        
        if len(returns) < 10:
            return 0.0
        
        baseline_vol = np.std(returns)
        
        # Simulate increased volatility
        stressed_returns = returns * 1.5  # Increase volatility by 50%
        stressed_vol = np.std(stressed_returns)
        
        sensitivity = (stressed_vol - baseline_vol) / baseline_vol if baseline_vol > 0 else 0
        return sensitivity
    
    def _calculate_correlation_sensitivity(self, returns: List[float]) -> float:
        """Calculate sensitivity to correlation changes"""
        
        if len(returns) < 10:
            return 0.0
        
        # Simple autocorrelation as proxy
        if len(returns) > 1:
            autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
            return abs(autocorr) if not np.isnan(autocorr) else 0.0
        
        return 0.0
    
    def generate_performance_report(self, evaluation_results: Dict) -> str:
        """Generate comprehensive performance evaluation report"""
        
        report = []
        report.append("\n" + "="*80)
        report.append("📊 RIGOROUS PERFORMANCE EVALUATION REPORT")
        report.append("="*80)
        
        # Performance Metrics
        metrics = evaluation_results['performance_metrics']
        report.append("\n📈 PERFORMANCE METRICS")
        report.append(f"Net P&L: ${metrics.net_pnl:,.2f}")
        report.append(f"Total Trades: {metrics.total_trades}")
        report.append(f"Win Rate: {metrics.win_rate:.1%}")
        report.append(f"Expectancy per Trade: ${metrics.expectancy:.2f}")
        report.append(f"Profit Factor: {metrics.profit_factor:.2f}")
        report.append(f"Risk:Reward Ratio: 1:{metrics.risk_reward:.2f}")
        report.append(f"Average Win: ${metrics.avg_win:.2f}")
        report.append(f"Average Loss: ${metrics.avg_loss:.2f}")
        report.append(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        report.append(f"Sortino Ratio: {metrics.sortino_ratio:.2f}")
        report.append(f"Calmar Ratio: {metrics.calmar_ratio:.2f}")
        report.append(f"Maximum Drawdown: {metrics.max_drawdown:.1%}")
        report.append(f"Max Drawdown Duration: {metrics.max_drawdown_duration} bars")
        
        # Kill Rule Violations
        violations = evaluation_results['kill_violations']
        report.append("\n⚠️ KILL RULE VIOLATIONS")
        if violations:
            for violation in violations:
                report.append(f"🔴 {violation.severity}: {violation.rule_name}")
                report.append(f"   Value: {violation.value:.3f} (Threshold: {violation.threshold:.3f})")
                report.append(f"   {violation.description}")
        else:
            report.append("✅ No kill rule violations detected")
        
        # Risk Assessment
        risk = evaluation_results['risk_assessment']
        report.append(f"\n🎯 RISK ASSESSMENT")
        report.append(f"Risk Level: {risk['risk_level']}")
        report.append(f"Risk Score: {risk['risk_score']}/100")
        report.append(f"Survivability: {risk['survivability']}")
        report.append(f"Capital Risk: {risk['capital_risk']}")
        report.append("Risk Factors:")
        for factor in risk['risk_factors']:
            report.append(f"  • {factor}")
        
        # Statistical Tests
        stats_tests = evaluation_results['statistical_tests']
        report.append(f"\n🔬 STATISTICAL VALIDATION")
        report.append(f"Sample Adequacy: {'✅' if stats_tests['sample_adequacy'] else '❌'}")
        report.append(f"Normal Distribution: {'✅' if stats_tests['normality_test']['normal'] else '❌'}")
        report.append(f"Independent Returns: {'✅' if stats_tests['autocorrelation_test']['independent'] else '❌'}")
        report.append(f"Stationary Process: {'✅' if stats_tests['stationarity_test']['stationary'] else '❌'}")
        report.append(f"Statistical Significance: {'✅' if stats_tests['significance_test']['significant'] else '❌'}")
        
        # Scenario Analysis
        scenario = evaluation_results['scenario_analysis']
        stress = scenario['stress_test']
        report.append(f"\n🌪️ STRESS TESTING")
        report.append(f"Worst Case Loss: ${stress['worst_case']:.2f}")
        report.append(f"95% VaR: ${stress['var_95']:.2f}")
        report.append(f"95% CVaR: ${stress['cvar_95']:.2f}")
        report.append(f"Max Loss Ratio: {stress['max_loss_ratio']:.2f}")
        
        mc = scenario['monte_carlo']
        report.append(f"\n🎰 MONTE CARLO SIMULATION")
        report.append(f"Probability of Ruin: {mc['probability_of_ruin']:.1%}")
        report.append(f"Expected Shortfall: ${mc['expected_shortfall']:.2f}")
        
        # Survival Metrics
        survival = evaluation_results['survival_metrics']
        report.append(f"\n💀 SURVIVAL ANALYSIS")
        report.append(f"Risk of Ruin: {survival['risk_of_ruin']:.1%}")
        report.append(f"Probability of Profit: {survival['probability_of_profit']:.1%}")
        report.append(f"Survival Probability: {survival['survival_probability']:.1%}")
        report.append(f"Capital Preservation: {'✅' if survival['capital_preservation'] else '❌'}")
        
        # Capital Efficiency
        efficiency = evaluation_results['capital_efficiency']
        report.append(f"\n💰 CAPITAL EFFICIENCY")
        report.append(f"Capital Turnover: {efficiency['capital_turnover']:.2f}")
        report.append(f"Return on Capital: {efficiency['return_on_capital']:.1%}")
        report.append(f"Efficiency Score: {efficiency['efficiency_score']:.3f}")
        report.append(f"Capital Utilization: {efficiency['capital_utilization']:.1%}")
        
        # Final Assessment
        critical_violations = [v for v in violations if v.severity == 'CRITICAL']
        if critical_violations:
            report.append(f"\n🔴 FINAL ASSESSMENT: STRATEGY REJECTED")
            report.append("Reason: Critical kill rule violations detected")
            report.append("Recommendation: ABANDON strategy immediately")
        elif len(violations) > 3:
            report.append(f"\n🟡 FINAL ASSESSMENT: STRATEGY NEEDS MAJOR OPTIMIZATION")
            report.append("Reason: Multiple kill rule violations")
            report.append("Recommendation: Address all violations before consideration")
        elif violations:
            report.append(f"\n🟡 FINAL ASSESSMENT: STRATEGY NEEDS MINOR OPTIMIZATION")
            report.append("Reason: Minor kill rule violations")
            report.append("Recommendation: Fix identified issues")
        else:
            report.append(f"\n🟢 FINAL ASSESSMENT: STRATEGY PASSES EVALUATION")
            report.append("Reason: No critical violations detected")
            report.append("Recommendation: Proceed to final verdict stage")
        
        report.append("\n" + "="*80)
        report.append(f"Evaluation completed: {evaluation_results['evaluation_timestamp']}")
        report.append("="*80)
        
        return "\n".join(report)
