"""
FINAL VERDICT SYSTEM
DEPLOY/OPTIMIZE/KILL decision engine with mathematical justification
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
import warnings
warnings.filterwarnings('ignore')

class Verdict(Enum):
    DEPLOY = "🟢 DEPLOY"
    OPTIMIZE = "🟡 OPTIMIZE"
    KILL = "🔴 KILL"

class DeploymentPhase(Enum):
    PHASE_1 = "Phase 1: Paper Trading (1-2 weeks)"
    PHASE_2 = "Phase 2: Micro Capital (0.5-1% risk)"
    PHASE_3 = "Phase 3: Small Capital (1-2% risk)"
    PHASE_4 = "Phase 4: Controlled Expansion (2-3% risk)"

@dataclass
class VerdictJustification:
    mathematical_score: float
    risk_adjusted_score: float
    survivability_score: float
    ict_effectiveness: Dict[str, float]
    cv_value_added: float
    critical_failures: List[str]
    strengths: List[str]
    weaknesses: List[str]

@dataclass
class DeploymentPlan:
    phase: DeploymentPhase
    capital_allocation: float
    risk_parameters: Dict[str, float]
    monitoring_requirements: List[str]
    kill_switches: List[str]
    success_criteria: Dict[str, float]

class FinalVerdictSystem:
    """Final verdict system with strict mathematical criteria"""
    
    def __init__(self):
        # Verdict thresholds (NON-NEGOTIABLE)
        self.thresholds = {
            'deploy': {
                'min_score': 70,
                'min_expectancy': 0.5,
                'min_sharpe': 1.0,
                'max_drawdown': 0.20,
                'min_trades': 50,
                'max_fragility': 0.4
            },
            'optimize': {
                'min_score': 40,
                'min_expectancy': 0.0,
                'min_sharpe': 0.5,
                'max_drawdown': 0.35,
                'min_trades': 30,
                'max_fragility': 0.7
            }
        }
        
        # ICT component effectiveness thresholds
        self.ict_thresholds = {
            'market_structure': 0.6,
            'liquidity_concepts': 0.6,
            'fair_value_gaps': 0.6,
            'order_blocks': 0.6,
            'premium_discount': 0.5,
            'time_based': 0.5,
            'power_of_three': 0.4
        }
        
        # CV value thresholds
        self.cv_thresholds = {
            'regime_accuracy': 0.7,
            'liquidity_effectiveness': 0.6,
            'execution_validation': 0.7,
            'overall_cv_value': 0.6
        }
    
    def generate_final_verdict(self, 
                            ict_evaluation: Dict,
                            performance_evaluation: Dict,
                            feature_analysis: Dict,
                            cv_analysis: Optional[Dict] = None) -> Dict:
        """
        Generate final verdict with comprehensive mathematical justification
        
        SECTION 6: Final Verdict (DEPLOY / OPTIMIZE / KILL)
        """
        
        logger.info("⚖️ Generating Final Verdict")
        
        # Calculate mathematical scores
        verdict_scores = self._calculate_verdict_scores(
            ict_evaluation, performance_evaluation, feature_analysis, cv_analysis
        )
        
        # Generate justification
        justification = self._create_justification(
            verdict_scores, ict_evaluation, performance_evaluation, feature_analysis, cv_analysis
        )
        
        # Determine verdict
        verdict = self._determine_verdict(verdict_scores, justification)
        
        # Create deployment plan if DEPLOY
        deployment_plan = None
        if verdict['verdict'] == Verdict.DEPLOY:
            deployment_plan = self._create_deployment_plan(verdict_scores, performance_evaluation)
        
        # Generate technical next steps
        next_steps = self._generate_technical_next_steps(verdict, justification, performance_evaluation)
        
        return {
            'verdict': verdict,
            'justification': justification,
            'deployment_plan': deployment_plan,
            'next_steps': next_steps,
            'verdict_timestamp': datetime.now().isoformat(),
            'mathematical_summary': self._create_mathematical_summary(verdict_scores)
        }
    
    def _calculate_verdict_scores(self, 
                               ict_evaluation: Dict,
                               performance_evaluation: Dict,
                               feature_analysis: Dict,
                               cv_analysis: Optional[Dict]) -> Dict:
        """Calculate all mathematical scores for verdict"""
        
        # Performance score (40% weight)
        performance_score = self._calculate_performance_score(performance_evaluation)
        
        # Risk score (25% weight)
        risk_score = self._calculate_risk_score(performance_evaluation)
        
        # ICT effectiveness score (20% weight)
        # BUG FIX: Use the evaluation object instead of raw feature analysis
        ict_score = self._calculate_ict_effectiveness_score(ict_evaluation)
        
        # Statistical validity score (10% weight)
        statistical_score = self._calculate_statistical_score(performance_evaluation)
        
        # CV value score (5% weight)
        cv_score = self._calculate_cv_score(cv_analysis) if cv_analysis else 0.0
        
        # Overall mathematical score
        overall_score = (
            performance_score * 0.4 +
            risk_score * 0.25 +
            ict_score * 0.20 +
            statistical_score * 0.10 +
            cv_score * 0.05
        )
        
        return {
            'overall_score': overall_score,
            'performance_score': performance_score,
            'risk_score': risk_score,
            'ict_score': ict_score,
            'statistical_score': statistical_score,
            'cv_score': cv_score,
            'component_scores': {
                'performance': performance_score,
                'risk': risk_score,
                'ict': ict_score,
                'statistical': statistical_score,
                'cv': cv_score
            }
        }
    
    def _calculate_performance_score(self, performance_evaluation: Dict) -> float:
        """Calculate performance score (0-100)"""
        
        metrics = performance_evaluation['performance_metrics']
        
        score = 0.0
        
        # Expectancy (25 points)
        if metrics.expectancy >= 1.0:
            score += 25
        elif metrics.expectancy >= 0.5:
            score += 20
        elif metrics.expectancy >= 0.0:
            score += 10
        else:
            score += 0
        
        # Sharpe ratio (20 points)
        if metrics.sharpe_ratio >= 2.0:
            score += 20
        elif metrics.sharpe_ratio >= 1.5:
            score += 15
        elif metrics.sharpe_ratio >= 1.0:
            score += 10
        elif metrics.sharpe_ratio >= 0.5:
            score += 5
        else:
            score += 0
        
        # Profit factor (15 points)
        if metrics.profit_factor >= 2.0:
            score += 15
        elif metrics.profit_factor >= 1.5:
            score += 10
        elif metrics.profit_factor >= 1.2:
            score += 5
        else:
            score += 0
        
        # Win rate (10 points)
        if metrics.win_rate >= 0.6:
            score += 10
        elif metrics.win_rate >= 0.5:
            score += 7
        elif metrics.win_rate >= 0.4:
            score += 4
        else:
            score += 0
        
        # Sample size (15 points)
        if metrics.total_trades >= 100:
            score += 15
        elif metrics.total_trades >= 50:
            score += 10
        elif metrics.total_trades >= 30:
            score += 5
        else:
            score += 0
        
        # Risk:Reward (10 points)
        if metrics.risk_reward >= 2.0:
            score += 10
        elif metrics.risk_reward >= 1.5:
            score += 7
        elif metrics.risk_reward >= 1.0:
            score += 4
        else:
            score += 0
        
        # Drawdown penalty (up to -15 points)
        if metrics.max_drawdown >= 0.5:
            score -= 15
        elif metrics.max_drawdown >= 0.3:
            score -= 10
        elif metrics.max_drawdown >= 0.2:
            score -= 5
        
        return max(0, min(100, score))
    
    def _calculate_risk_score(self, performance_evaluation: Dict) -> float:
        """Calculate risk score (0-100, higher is better)"""
        
        risk_assessment = performance_evaluation['risk_assessment']
        survival_metrics = performance_evaluation['survival_metrics']
        
        score = 100.0
        
        # Risk level penalty
        if risk_assessment['risk_level'] == 'CRITICAL':
            score -= 50
        elif risk_assessment['risk_level'] == 'HIGH':
            score -= 30
        elif risk_assessment['risk_level'] == 'MEDIUM':
            score -= 15
        
        # Risk score penalty
        score -= risk_assessment['risk_score'] * 0.5  # Scale 0-100 to 0-50 penalty
        
        # Survival metrics
        if survival_metrics['risk_of_ruin'] >= 0.3:
            score -= 30
        elif survival_metrics['risk_of_ruin'] >= 0.2:
            score -= 20
        elif survival_metrics['risk_of_ruin'] >= 0.1:
            score -= 10
        
        # Drawdown duration penalty
        metrics = performance_evaluation['performance_metrics']
        if metrics.max_drawdown_duration >= 100:
            score -= 20
        elif metrics.max_drawdown_duration >= 50:
            score -= 10
        elif metrics.max_drawdown_duration >= 25:
            score -= 5
        
        return max(0, score)
    
    def _calculate_ict_effectiveness_score(self, ict_evaluation: Dict) -> float:
        """Calculate ICT component effectiveness score using EVALUATED features"""
        
        # Extract features from evaluation or analysis
        ict_features = ict_evaluation.get('ict_features')
        if not ict_features:
             # Fallback to feature_analysis if eval is missing
             ict_features = ict_evaluation.get('ict_features', {})
        
        if not ict_features:
            return 0.0
        
        scores = []
        
        # Market structure
        ms_score = getattr(ict_features, 'market_structure_score', 0.0)
        scores.append(100 * ms_score if ms_score >= self.ict_thresholds.get('market_structure', 0.6) else 40 * ms_score)
        
        # FVG effectiveness (High weighting in v2.0)
        fvg_score = getattr(ict_features, 'fvg_fill_rate', 0.0)
        scores.append(120 * fvg_score if fvg_score >= self.ict_thresholds.get('fair_value_gaps', 0.6) else 30 * fvg_score)
        
        # Liquidity Sweeps (High weighting in v2.2)
        sweep_score = getattr(ict_features, 'liquidity_sweep_success', 0.0)
        scores.append(120 * sweep_score if sweep_score >= self.ict_thresholds.get('liquidity_concepts', 0.6) else 30 * sweep_score)
        
        # Order block effectiveness
        ob_score = getattr(ict_features, 'ob_success_rate', 0.0)
        scores.append(90 * ob_score if ob_score >= self.ict_thresholds.get('order_blocks', 0.6) else 40 * ob_score)
        
        # Premium/Discount effectiveness
        pd_score = getattr(ict_features, 'premium_discount_effectiveness', 0.0)
        scores.append(80 * pd_score if pd_score >= self.ict_thresholds.get('premium_discount', 0.5) else 40 * pd_score)
        
        return np.mean(scores) if scores else 0.0
    
    def _calculate_statistical_score(self, performance_evaluation: Dict) -> float:
        """Calculate statistical validity score"""
        
        statistical_tests = performance_evaluation['statistical_tests']
        
        score = 0.0
        
        # Sample adequacy (25 points)
        if statistical_tests['sample_adequacy']:
            score += 25
        else:
            score += 5
        
        # Statistical significance (25 points)
        if statistical_tests['significance_test']['significant']:
            score += 25
        else:
            score += 0
        
        # Stationarity (20 points)
        if statistical_tests['stationarity_test']['stationary']:
            score += 20
        else:
            score += 5
        
        # Independence (15 points)
        if statistical_tests['autocorrelation_test']['independent']:
            score += 15
        else:
            score += 0
        
        # Normal distribution (15 points)
        if statistical_tests['normality_test']['normal']:
            score += 15
        else:
            score += 5
        
        return score
    
    def _calculate_cv_score(self, cv_analysis: Dict) -> float:
        """Calculate computer vision value score"""
        
        if not cv_analysis:
            return 0.0
        
        score = 0.0
        
        # Regime detection accuracy (30 points)
        regime_accuracy = cv_analysis.get('regime_accuracy', 0.0)
        if regime_accuracy >= self.cv_thresholds['regime_accuracy']:
            score += 30
        else:
            score += 30 * regime_accuracy
        
        # Liquidity effectiveness (30 points)
        liq_effectiveness = cv_analysis.get('liquidity_effectiveness', 0.0)
        if liq_effectiveness >= self.cv_thresholds['liquidity_effectiveness']:
            score += 30
        else:
            score += 30 * liq_effectiveness
        
        # Execution validation (25 points)
        exec_validation = cv_analysis.get('execution_validation', 0.0)
        if exec_validation >= self.cv_thresholds['execution_validation']:
            score += 25
        else:
            score += 25 * exec_validation
        
        # Overall CV value (15 points)
        overall_value = cv_analysis.get('cv_value_score', 0.0)
        if overall_value >= self.cv_thresholds['overall_cv_value']:
            score += 15
        else:
            score += 15 * overall_value
        
        return score
    
    def _create_justification(self, 
                           verdict_scores: Dict,
                           ict_evaluation: Dict,
                           performance_evaluation: Dict,
                           feature_analysis: Dict,
                           cv_analysis: Optional[Dict]) -> VerdictJustification:
        """Create comprehensive justification for verdict"""
        
        # Identify critical failures
        critical_failures = []
        kill_violations = performance_evaluation['kill_violations']
        
        for violation in kill_violations:
            if violation.severity == 'CRITICAL':
                critical_failures.append(f"{violation.rule_name}: {violation.description}")
        
        # Identify strengths
        strengths = []
        metrics = performance_evaluation['performance_metrics']
        
        if metrics.expectancy >= 1.0:
            strengths.append(f"Strong expectancy: ${metrics.expectancy:.2f}")
        if metrics.sharpe_ratio >= 1.5:
            strengths.append(f"Excellent risk-adjusted returns: Sharpe {metrics.sharpe_ratio:.2f}")
        if metrics.profit_factor >= 1.5:
            strengths.append(f"Solid profit factor: {metrics.profit_factor:.2f}")
        if metrics.max_drawdown <= 0.2:
            strengths.append(f"Controlled drawdown: {metrics.max_drawdown:.1%}")
        if metrics.total_trades >= 50:
            strengths.append(f"Adequate sample size: {metrics.total_trades} trades")
        
        # Identify weaknesses
        weaknesses = []
        
        if metrics.expectancy <= 0:
            weaknesses.append("Negative expectancy - no edge")
        if metrics.sharpe_ratio < 0.5:
            weaknesses.append("Poor risk-adjusted returns")
        if metrics.max_drawdown >= 0.3:
            weaknesses.append(f"High drawdown: {metrics.max_drawdown:.1%}")
        if metrics.total_trades < 30:
            weaknesses.append("Insufficient sample size")
        if metrics.win_rate < 0.4:
            weaknesses.append(f"Low win rate: {metrics.win_rate:.1%}")
        
        # ICT effectiveness (use evaluated metrics)
        ict_effectiveness = self._analyze_ict_effectiveness(ict_evaluation)
        
        # CV value added
        cv_value_added = self._calculate_cv_value_added(cv_analysis) if cv_analysis else 0.0
        
        return VerdictJustification(
            mathematical_score=verdict_scores['overall_score'],
            risk_adjusted_score=verdict_scores['risk_score'],
            survivability_score=performance_evaluation['survival_metrics']['survival_probability'] * 100,
            ict_effectiveness=ict_effectiveness,
            cv_value_added=cv_value_added,
            critical_failures=critical_failures,
            strengths=strengths,
            weaknesses=weaknesses
        )
    
    def _determine_verdict(self, verdict_scores: Dict, justification: VerdictJustification) -> Dict:
        """Determine final verdict with strict criteria"""
        
        overall_score = verdict_scores['overall_score']
        
        # Check for automatic KILL conditions
        if justification.critical_failures:
            verdict = Verdict.KILL
            reason = "Critical kill rule violations detected"
            recommendation = "ABANDON strategy immediately - mathematical edge does not exist"
        elif overall_score >= self.thresholds['deploy']['min_score']:
            # Check all DEPLOY thresholds
            metrics = verdict_scores
            
            deploy_checks = [
                overall_score >= self.thresholds['deploy']['min_score'],
                justification.mathematical_score >= self.thresholds['deploy']['min_score'],
                justification.risk_adjusted_score >= 50,
                justification.survivability_score >= 80,
                len(justification.critical_failures) == 0
            ]
            
            if all(deploy_checks):
                verdict = Verdict.DEPLOY
                reason = "Strategy passes all deployment thresholds"
                recommendation = "Deploy with controlled capital allocation and monitoring"
            else:
                verdict = Verdict.OPTIMIZE
                reason = "Strategy meets minimum criteria but needs optimization"
                recommendation = "Optimize specific components before deployment"
        elif overall_score >= self.thresholds['optimize']['min_score']:
            verdict = Verdict.OPTIMIZE
            reason = "Strategy has potential but requires significant optimization"
            recommendation = "Major optimization required before consideration"
        else:
            verdict = Verdict.KILL
            reason = "Strategy fails minimum mathematical criteria"
            recommendation = "Edge not real - reject strategy"
        
        return {
            'verdict': verdict.value,
            'overall_score': overall_score,
            'reason': reason,
            'recommendation': recommendation,
            'deploy_checks_passed': self._check_deploy_thresholds(verdict_scores, justification),
            'critical_issues': justification.critical_failures,
            'strengths': justification.strengths,
            'weaknesses': justification.weaknesses
        }
    
    def _create_deployment_plan(self, verdict_scores: Dict, performance_evaluation: Dict) -> DeploymentPlan:
        """Create detailed deployment plan for DEPLOY verdict"""
        
        # Determine starting phase based on score
        overall_score = verdict_scores['overall_score']
        
        if overall_score >= 90:
            phase = DeploymentPhase.PHASE_2  # Start with micro capital
            capital_allocation = 0.01  # 1% of total capital
        elif overall_score >= 80:
            phase = DeploymentPhase.PHASE_1  # Start with paper trading
            capital_allocation = 0.0
        else:
            phase = DeploymentPhase.PHASE_1  # Start with paper trading
            capital_allocation = 0.0
        
        # Risk parameters
        risk_parameters = {
            'max_risk_per_trade': 0.02,  # 2% max
            'max_portfolio_risk': 0.05,  # 5% max
            'max_correlation': 0.7,      # Max correlation between positions
            'rebalance_frequency': 'daily',
            'stop_loss_multiplier': 2.0,
            'take_profit_multiplier': 3.0
        }
        
        # Monitoring requirements
        monitoring_requirements = [
            "Real-time performance monitoring",
            "Drawdown alerts at 10%, 15%, 20%",
            "Sharpe ratio monitoring (minimum 0.5)",
            "ICT component effectiveness tracking",
            "Regime-specific performance monitoring",
            "Daily risk exposure reporting",
            "Weekly performance review",
            "Monthly strategy health check"
        ]
        
        # Kill switches
        kill_switches = [
            "Maximum drawdown > 25%",
            "Sharpe ratio < 0.5 for 2 weeks",
            "Expectancy turns negative",
            "ICT component failure > 60%",
            "Regime performance drop > 50%",
            "Volatility exceeds 2x historical",
            "Correlation breakdown > 0.8",
            "Liquidity deterioration > 40%"
        ]
        
        # Success criteria
        success_criteria = {
            'min_expectancy': 0.5,
            'min_sharpe': 1.0,
            'max_drawdown': 0.2,
            'min_win_rate': 0.45,
            'profit_factor_min': 1.5,
            'ict_effectiveness_min': 0.6
        }
        
        return DeploymentPlan(
            phase=phase,
            capital_allocation=capital_allocation,
            risk_parameters=risk_parameters,
            monitoring_requirements=monitoring_requirements,
            kill_switches=kill_switches,
            success_criteria=success_criteria
        )
    
    def _generate_technical_next_steps(self, 
                                     verdict: Dict, 
                                     justification: VerdictJustification,
                                     performance_evaluation: Dict) -> List[str]:
        """Generate technical next steps based on verdict"""
        
        steps = []
        
        if verdict['verdict'] == Verdict.KILL.value:
            steps.extend([
                "🔴 ABANDON strategy - mathematical edge does not exist",
                "📊 Document all failure points for learning",
                "🔬 Analyze which ICT components failed fundamentally",
                "💡 Consider alternative market approaches or concepts",
                "📈 Review data quality and parameter sensitivity",
                "🎯 Focus on capital preservation rather than strategy recovery"
            ])
        
        elif verdict['verdict'] == Verdict.OPTIMIZE.value:
            steps.extend([
                "🟡 OPTIMIZATION REQUIRED - Address identified weaknesses",
                f"🎯 Focus on: {', '.join(justification.weaknesses[:3])}",
                "📊 Increase sample size with additional historical data",
                "🔧 Optimize ICT component thresholds and parameters",
                "⚖️ Improve risk management and position sizing",
                "📈 Enhance entry/exit filters for better win rate",
                "🔬 Validate with out-of-sample testing",
                "💰 Account for realistic transaction costs and slippage"
            ])
        
        else:  # DEPLOY
            steps.extend([
                "🟢 DEPLOYMENT APPROVED - Execute with caution",
                "📋 Implement deployment plan in phases",
                "💰 Start with paper trading to validate live performance",
                "📊 Set up real-time monitoring and alerting systems",
                "⚠️ Implement all kill switches and risk controls",
                "📈 Track ICT component effectiveness in live markets",
                "🔄 Weekly performance reviews and adjustments",
                "🎯 Scale capital only after meeting success criteria"
            ])
        
        # Universal next steps
        steps.extend([
            "📊 Validate results with out-of-sample data",
            "🌍 Test across different market conditions (bull/bear/sideways)",
            "💸 Include realistic transaction costs and slippage",
            "🔍 Perform sensitivity analysis on key parameters",
            "📝 Document all assumptions and limitations",
            "🎓 Continuous learning and improvement process"
        ])
        
        return steps
    
    def _check_deploy_thresholds(self, verdict_scores: Dict, justification: VerdictJustification) -> Dict[str, bool]:
        """Check if all deployment thresholds are met"""
        
        deploy_thresholds = self.thresholds['deploy']
        
        checks = {
            'overall_score': verdict_scores['overall_score'] >= deploy_thresholds['min_score'],
            'mathematical_score': justification.mathematical_score >= deploy_thresholds['min_score'],
            'risk_adjusted_score': justification.risk_adjusted_score >= 50,
            'survivability': justification.survivability_score >= 80,
            'no_critical_failures': len(justification.critical_failures) == 0
        }
        
        return checks
    
    def _analyze_ict_effectiveness(self, ict_evaluation: Dict) -> Dict[str, float]:
        """Analyze effectiveness of each ICT component from evaluation data"""
        
        ict_features = ict_evaluation.get('ict_features')
        if not ict_features:
            return {}
        
        effectiveness = {}
        
        # Extract component scores from the ICTFeatures object
        effectiveness['market_structure'] = getattr(ict_features, 'market_structure_score', 0.0)
        effectiveness['liquidity_concepts'] = getattr(ict_features, 'liquidity_density', 0.0)
        effectiveness['fair_value_gaps'] = getattr(ict_features, 'fvg_fill_rate', 0.0)
        effectiveness['order_blocks'] = getattr(ict_features, 'ob_success_rate', 0.0)
        effectiveness['premium_discount'] = getattr(ict_features, 'premium_discount_effectiveness', 0.0)
        effectiveness['liquidity_sweeps'] = getattr(ict_features, 'liquidity_sweep_success', 0.0)
        
        return effectiveness
    
    def _calculate_cv_value_added(self, cv_analysis: Dict) -> float:
        """Calculate overall CV value added score"""
        
        if not cv_analysis:
            return 0.0
        
        scores = [
            cv_analysis.get('regime_accuracy', 0.0),
            cv_analysis.get('liquidity_effectiveness', 0.0),
            cv_analysis.get('execution_validation', 0.0),
            cv_analysis.get('cv_value_score', 0.0)
        ]
        
        return np.mean(scores)
    
    def _create_mathematical_summary(self, verdict_scores: Dict) -> Dict:
        """Create mathematical summary of verdict"""
        
        return {
            'overall_score': verdict_scores['overall_score'],
            'component_breakdown': verdict_scores['component_scores'],
            'score_interpretation': self._interpret_score(verdict_scores['overall_score']),
            'mathematical_confidence': self._calculate_confidence(verdict_scores),
            'statistical_significance': verdict_scores['statistical_score'] > 70
        }
    
    def _interpret_score(self, score: float) -> str:
        """Interpret verdict score"""
        
        if score >= 90:
            return "Exceptional - Strong mathematical edge"
        elif score >= 80:
            return "Excellent - Solid mathematical edge"
        elif score >= 70:
            return "Good - Acceptable mathematical edge"
        elif score >= 60:
            return "Fair - Marginal mathematical edge"
        elif score >= 50:
            return "Poor - Weak mathematical edge"
        elif score >= 40:
            return "Very Poor - Minimal mathematical edge"
        else:
            return "No Edge - Mathematical failure"
    
    def _calculate_confidence(self, verdict_scores: Dict) -> float:
        """Calculate confidence in verdict"""
        
        # Confidence based on score distribution
        scores = list(verdict_scores['component_scores'].values())
        score_std = np.std(scores)
        score_mean = np.mean(scores)
        
        # Higher confidence for consistent high scores
        if score_mean >= 70 and score_std <= 20:
            return 0.9
        elif score_mean >= 60 and score_std <= 25:
            return 0.8
        elif score_mean >= 50 and score_std <= 30:
            return 0.7
        else:
            return 0.5
    
    def generate_final_report(self, verdict_results: Dict) -> str:
        """Generate comprehensive final verdict report"""
        
        verdict = verdict_results['verdict']
        justification = verdict_results['justification']
        
        report = []
        report.append("\n" + "="*80)
        report.append("⚖️ FINAL VERDICT REPORT")
        report.append("="*80)
        
        # Final Verdict
        report.append(f"\n🎯 FINAL VERDICT: {verdict['verdict']}")
        report.append(f"Overall Score: {verdict['overall_score']:.1f}/100")
        report.append(f"Reason: {verdict['reason']}")
        report.append(f"Recommendation: {verdict['recommendation']}")
        
        # Mathematical Justification
        report.append(f"\n📊 MATHEMATICAL JUSTIFICATION")
        report.append(f"Mathematical Score: {justification.mathematical_score:.1f}/100")
        report.append(f"Risk-Adjusted Score: {justification.risk_adjusted_score:.1f}/100")
        report.append(f"Survivability Score: {justification.survivability_score:.1f}/100")
        report.append(f"CV Value Added: {justification.cv_value_added:.1f}%")
        
        # ICT Component Analysis
        if justification.ict_effectiveness:
            report.append(f"\n🔍 ICT COMPONENT EFFECTIVENESS")
            for component, score in justification.ict_effectiveness.items():
                status = "✅" if score >= 0.6 else "🟡" if score >= 0.4 else "❌"
                report.append(f"{status} {component.replace('_', ' ').title()}: {score:.1%}")
        
        # Strengths
        if justification.strengths:
            report.append(f"\n💪 STRENGTHS")
            for strength in justification.strengths:
                report.append(f"✅ {strength}")
        
        # Weaknesses
        if justification.weaknesses:
            report.append(f"\n⚠️ WEAKNESSES")
            for weakness in justification.weaknesses:
                report.append(f"❌ {weakness}")
        
        # Critical Failures
        if justification.critical_failures:
            report.append(f"\n🔴 CRITICAL FAILURES")
            for failure in justification.critical_failures:
                report.append(f"🚨 {failure}")
        
        # Deployment Plan
        if verdict_results['deployment_plan']:
            plan = verdict_results['deployment_plan']
            report.append(f"\n🚀 DEPLOYMENT PLAN")
            report.append(f"Phase: {plan.phase.value}")
            report.append(f"Capital Allocation: {plan.capital_allocation:.1%}")
            report.append(f"Max Risk per Trade: {plan.risk_parameters['max_risk_per_trade']:.1%}")
            report.append(f"Max Portfolio Risk: {plan.risk_parameters['max_portfolio_risk']:.1%}")
            
            report.append(f"\n📊 SUCCESS CRITERIA")
            for criterion, threshold in plan.success_criteria.items():
                report.append(f"• {criterion.replace('_', ' ').title()}: {threshold}")
            
            report.append(f"\n⚠️ KILL SWITCHES")
            for kill_switch in plan.kill_switches[:5]:  # Show first 5
                report.append(f"• {kill_switch}")
        
        # Technical Next Steps
        report.append(f"\n🔧 TECHNICAL NEXT STEPS")
        for i, step in enumerate(verdict_results['next_steps'], 1):
            report.append(f"{i}. {step}")
        
        # Mathematical Summary
        summary = verdict_results['mathematical_summary']
        report.append(f"\n📈 MATHEMATICAL SUMMARY")
        report.append(f"Score Interpretation: {summary['score_interpretation']}")
        report.append(f"Mathematical Confidence: {summary['mathematical_confidence']:.1%}")
        report.append(f"Statistical Significance: {'✅' if summary['statistical_significance'] else '❌'}")
        
        # Final Assessment
        report.append(f"\n" + "="*80)
        if verdict['verdict'] == Verdict.DEPLOY.value:
            report.append("🟢 STRATEGY APPROVED FOR DEPLOYMENT")
            report.append("Mathematical edge confirmed - proceed with controlled deployment")
        elif verdict['verdict'] == Verdict.OPTIMIZE.value:
            report.append("🟡 STRATEGY REQUIRES OPTIMIZATION")
            report.append("Mathematical potential exists - optimization required")
        else:
            report.append("🔴 STRATEGY REJECTED")
            report.append("Mathematical edge does not exist - abandon strategy")
        
        report.append("="*80)
        report.append(f"Verdict issued: {verdict_results['verdict_timestamp']}")
        report.append("="*80)
        
        return "\n".join(report)
    
    def save_verdict_results(self, verdict_results: Dict, filename: str = None) -> str:
        """Save verdict results to file"""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ict_verdict_{timestamp}.json"
        
        # Create results directory
        results_dir = Path("verdict_results")
        results_dir.mkdir(exist_ok=True)
        
        filepath = results_dir / filename
        
        # Convert to JSON-serializable format
        serializable_results = self._make_serializable(verdict_results)
        
        with open(filepath, 'w') as f:
            json.dump(serializable_results, f, indent=2, default=str)
        
        logger.info(f"📁 Verdict results saved to: {filepath}")
        return str(filepath)
    
    def _make_serializable(self, obj):
        """Convert object to JSON-serializable format"""
        
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (Verdict, DeploymentPhase)):
            return obj.value
        elif isinstance(obj, (VerdictJustification, DeploymentPlan)):
            return obj.__dict__
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
