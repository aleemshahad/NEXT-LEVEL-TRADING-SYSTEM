"""
ICT CONCEPT AUDITOR - MAIN INTEGRATION SYSTEM
Complete evaluation pipeline for ICT trading strategies
Created by: ICT Concept Auditor
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
from pathlib import Path
from loguru import logger
import sys
import warnings
warnings.filterwarnings('ignore')

# Import all evaluation components
from ict_evaluator import ICTConceptEvaluator, ICTFeatures
from ict_feature_engineer import ICTFeatureEngineer
from computer_vision_analyzer import ComputerVisionAnalyzer
from performance_evaluator import PerformanceEvaluator, PerformanceMetrics
from final_verdict_system import FinalVerdictSystem, Verdict

class ICTConceptAuditor:
    """Main ICT Concept Auditor - Complete evaluation pipeline"""
    
    def __init__(self, config_file: str = "ict_config.json"):
        """
        Initialize the ICT Concept Auditor
        
        CORE PHILOSOPHY (NON-NEGOTIABLE):
        - ICT concepts are HYPOTHESES, not truth
        - Nothing is valid until tested numerically
        - Visual confirmation WITHOUT statistics is INVALID
        - Profit without risk-adjusted survivability is MEANINGLESS
        """
        
        self.config_file = config_file
        self.config = self._load_config()
        
        # Initialize all evaluation components
        self.ict_evaluator = ICTConceptEvaluator()
        self.feature_engineer = ICTFeatureEngineer()
        self.cv_analyzer = ComputerVisionAnalyzer()
        self.performance_evaluator = PerformanceEvaluator()
        self.verdict_system = FinalVerdictSystem()
        
        # Setup logging
        self._setup_logging()
        
        logger.info("🔬 ICT Concept Auditor initialized")
        logger.info("🎯 Mission: Deconstruct, formalize, quantify, and EVALUATE all ICT concepts")
    
    def evaluate_ict_strategy(self, 
                             trades: List[Dict],
                             market_data: pd.DataFrame,
                             strategy_components: List[str],
                             visual_data: Optional[Dict] = None,
                             enable_cv: bool = True) -> Dict:
        """
        Complete ICT strategy evaluation pipeline
        
        Args:
            trades: List of trade dictionaries with complete trade information
            market_data: Historical OHLCV data
            strategy_components: List of ICT concepts used in strategy
            visual_data: Optional pre-computed visual analysis data
            enable_cv: Whether to run computer vision analysis
        """
        
        logger.info("🚀 Starting Complete ICT Strategy Evaluation")
        logger.info(f"📊 Analyzing {len(trades)} trades across {len(market_data)} bars")
        logger.info(f"🔍 ICT Components: {', '.join(strategy_components)}")
        
        # STEP 1: Extract ICT Features
        logger.info("📈 STEP 1: Extracting ICT Features...")
        ict_features = self.feature_engineer.extract_all_features(market_data)
        
        # STEP 2: Computer Vision Analysis (if enabled)
        cv_analysis = None
        if enable_cv:
            logger.info("👁️ STEP 2: Running Computer Vision Analysis...")
            cv_analysis = self._run_cv_analysis(market_data, trades)
        
        # STEP 3: Performance Evaluation
        logger.info("📊 STEP 3: Evaluating Performance...")
        equity_curve = self._build_equity_curve(trades)
        performance_evaluation = self.performance_evaluator.evaluate_performance(
            trades, equity_curve
        )
        
        # STEP 4: ICT Concept Evaluation
        logger.info("🔍 STEP 4: Evaluating ICT Concepts...")
        ict_evaluation = self.ict_evaluator.evaluate_ict_strategy(
            trades, market_data, strategy_components, visual_data or cv_analysis
        )
        
        # STEP 5: Final Verdict
        logger.info("⚖️ STEP 5: Generating Final Verdict...")
        final_verdict = self.verdict_system.generate_final_verdict(
            ict_evaluation=ict_evaluation,
            performance_evaluation=performance_evaluation,
            feature_analysis={'ict_features': ict_features},
            cv_analysis=cv_analysis
        )
        
        # STEP 6: Generate Comprehensive Report
        logger.info("📋 STEP 6: Generating Comprehensive Report...")
        comprehensive_report = self._generate_comprehensive_report(
            ict_evaluation, performance_evaluation, ict_features, cv_analysis, final_verdict
        )
        
        # STEP 7: Save Results
        results = self._compile_results(
            trades, market_data, strategy_components,
            ict_evaluation, performance_evaluation, ict_features,
            cv_analysis, final_verdict, comprehensive_report
        )
        
        # Save to file
        saved_file = self.save_evaluation_results(results)
        
        logger.info(f"✅ ICT Strategy Evaluation Complete!")
        logger.info(f"📁 Results saved to: {saved_file}")
        
        return results
    
    def _run_cv_analysis(self, market_data: pd.DataFrame, trades: List[Dict]) -> Dict:
        """Run complete computer vision analysis"""
        
        # Regime Detection
        regime_analysis = self.cv_analyzer.analyze_market_regime(market_data, visualize=False)
        
        # Liquidity Heatmap
        liquidity_analysis = self.cv_analyzer.analyze_liquidity_heatmap(market_data, visualize=False)
        
        # Execution Validation
        execution_analysis = self.cv_analyzer.validate_execution_conditions(market_data, trades)
        
        # Generate CV Report
        cv_report = self.cv_analyzer.generate_cv_report(regime_analysis, liquidity_analysis, execution_analysis)
        
        return {
            'regime_analysis': regime_analysis,
            'liquidity_analysis': liquidity_analysis,
            'execution_analysis': execution_analysis,
            'cv_report': cv_report,
            'regime_accuracy': regime_analysis.get('cv_accuracy', 0.0),
            'liquidity_effectiveness': liquidity_analysis.get('cv_effectiveness', 0.0),
            'execution_validation': execution_analysis.get('avg_execution_quality', 0.0),
            'cv_value_score': (regime_analysis.get('cv_accuracy', 0.0) + 
                             liquidity_analysis.get('cv_effectiveness', 0.0)) / 2
        }
    
    def _build_equity_curve(self, trades: List[Dict]) -> List[float]:
        """Build equity curve from trades"""
        
        equity = [10000.0]  # Starting capital
        
        for trade in trades:
            pnl = trade.get('pnl', 0.0)
            equity.append(equity[-1] + pnl)
        
        return equity
    
    def _generate_comprehensive_report(self, 
                                     ict_evaluation: Dict,
                                     performance_evaluation: Dict,
                                     ict_features: Dict,
                                     cv_analysis: Optional[Dict],
                                     final_verdict: Dict) -> str:
        """Generate comprehensive evaluation report"""
        
        report = []
        report.append("\n" + "="*100)
        report.append("🔬 ICT CONCEPT AUDITOR - COMPREHENSIVE EVALUATION REPORT")
        report.append("="*100)
        
        # Executive Summary
        verdict = final_verdict['verdict']
        report.append(f"\n🎯 EXECUTIVE SUMMARY")
        report.append(f"Final Verdict: {verdict['verdict']}")
        report.append(f"Overall Score: {verdict['overall_score']:.1f}/100")
        report.append(f"Recommendation: {verdict['recommendation']}")
        
        # SECTION 1: Strategy & ICT Components
        strategy = ict_evaluation['strategy_analysis']
        report.append(f"\n📊 SECTION 1: STRATEGY & ICT COMPONENTS USED")
        report.append(f"Total ICT Components: {strategy['total_components']}")
        report.append(f"Complexity Score: {strategy['complexity_score']}")
        for comp, details in strategy['components'].items():
            status = "✅" if details['used'] else "❌"
            report.append(f"{status} {comp.replace('_', ' ').title()}: {details['description']}")
        
        # SECTION 2: Quantified ICT Features
        report.append(f"\n🔍 SECTION 2: QUANTIFIED ICT FEATURES")
        features = ict_features
        
        # Market Structure
        if 'market_structure' in features:
            ms = features['market_structure']
            report.append(f"Market Structure: {ms.get('current_structure', 'Unknown')}")
            report.append(f"Trend Strength: {ms.get('trend_strength', 0):.2f}")
            report.append(f"Structure Quality: {ms.get('structure_quality', 0):.2f}")
        
        # Liquidity
        if 'liquidity' in features:
            liq = features['liquidity']
            report.append(f"Liquidity Density: {liq.get('liquidity_density', 0):.2f}")
            report.append(f"Sweep Success Rate: {liq.get('sweep_success_rate', 0):.2f}")
            report.append(f"Equal Levels: {liq.get('total_equal_levels', 0)}")
        
        # FVG
        if 'fvg' in features:
            fvg = features['fvg']
            report.append(f"FVG Fill Rate: {fvg.get('fill_rate', 0):.2f}")
            report.append(f"Avg FVG Size: {fvg.get('avg_fvg_size', 0):.6f}")
            report.append(f"Reaction Strength: {fvg.get('reaction_strength', 0):.2f}")
        
        # Order Blocks
        if 'order_blocks' in features:
            ob = features['order_blocks']
            report.append(f"Order Block Mitigation: {ob.get('mitigation_rate', 0):.2f}")
            report.append(f"OB Failure Rate: {ob.get('failure_rate', 0):.2f}")
            report.append(f"Avg OB Strength: {ob.get('avg_ob_strength', 0):.2f}")
        
        # Premium/Discount
        if 'premium_discount' in features:
            pd = features['premium_discount']
            report.append(f"Current Zone: {pd.get('current_zone', 'Unknown')}")
            report.append(f"Zone Effectiveness: {pd.get('zone_effectiveness', 0):.2f}")
        
        # SECTION 3: Performance Metrics
        metrics = performance_evaluation['performance_metrics']
        report.append(f"\n📈 SECTION 3: PERFORMANCE METRICS")
        report.append(f"Net P&L: ${metrics.net_pnl:,.2f}")
        report.append(f"Total Trades: {metrics.total_trades}")
        report.append(f"Win Rate: {metrics.win_rate:.1%}")
        report.append(f"Expectancy per Trade: ${metrics.expectancy:.2f}")
        report.append(f"Profit Factor: {metrics.profit_factor:.2f}")
        report.append(f"Risk:Reward Ratio: 1:{metrics.risk_reward:.2f}")
        report.append(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        report.append(f"Sortino Ratio: {metrics.sortino_ratio:.2f}")
        report.append(f"Calmar Ratio: {metrics.calmar_ratio:.2f}")
        report.append(f"Maximum Drawdown: {metrics.max_drawdown:.1%}")
        report.append(f"Max Drawdown Duration: {metrics.max_drawdown_duration} bars")
        report.append(f"Average Win: ${metrics.avg_win:.2f}")
        report.append(f"Average Loss: ${metrics.avg_loss:.2f}")
        
        # SECTION 4: CV-Derived Analysis
        if cv_analysis:
            report.append(f"\n👁️ SECTION 4: COMPUTER VISION ANALYSIS")
            cv_regime = cv_analysis['regime_analysis']
            cv_liq = cv_analysis['liquidity_analysis']
            cv_exec = cv_analysis['execution_analysis']
            
            report.append(f"Current Regime: {cv_regime.get('current_regime', {}).get('regime', 'Unknown') if cv_regime.get('current_regime') else 'Unknown'}")
            report.append(f"Regime Stability: {cv_regime.get('regime_stability', 0):.2f}")
            report.append(f"CV Accuracy: {cv_regime.get('cv_accuracy', 0):.2f}")
            
            report.append(f"Buy Side Liquidity: {cv_liq.get('buy_side_liquidity', 0):.2f}")
            report.append(f"Sell Side Liquidity: {cv_liq.get('sell_side_liquidity', 0):.2f}")
            report.append(f"Liquidity Imbalance: {cv_liq.get('liquidity_imbalance', 0):.2f}")
            
            report.append(f"Execution Quality: {cv_exec.get('avg_execution_quality', 0):.2f}")
            report.append(f"Liquidity Success: {cv_exec.get('liquidity_success', 0):.2f}")
            report.append(f"Slippage Frequency: {cv_exec.get('slippage_freq', 0):.2f}")
            
            report.append(f"Overall CV Value Score: {cv_analysis.get('cv_value_score', 0):.2f}")
        
        # SECTION 5: Risk, Drawdown & Fragility Assessment
        risk = performance_evaluation['risk_assessment']
        survival = performance_evaluation['survival_metrics']
        report.append(f"\n⚠️ SECTION 5: RISK, DRAWDOWN & FRAGILITY ASSESSMENT")
        report.append(f"Risk Level: {risk['risk_level']}")
        report.append(f"Risk Score: {risk['risk_score']}/100")
        report.append(f"Survivability: {risk['survivability']}")
        report.append(f"Capital Risk: {risk['capital_risk']}")
        report.append(f"Risk of Ruin: {survival['risk_of_ruin']:.1%}")
        report.append(f"Survival Probability: {survival['survival_probability']:.1%}")
        report.append(f"Capital Preservation: {'✅' if survival['capital_preservation'] else '❌'}")
        
        report.append("Risk Factors:")
        for factor in risk['risk_factors']:
            report.append(f"  • {factor}")
        
        # Kill Rule Violations
        violations = performance_evaluation['kill_violations']
        if violations:
            report.append(f"\n🚨 KILL RULE VIOLATIONS:")
            for violation in violations:
                report.append(f"  {violation.severity}: {violation.rule_name}")
                report.append(f"    Value: {violation.value:.3f} (Threshold: {violation.threshold:.3f})")
        else:
            report.append(f"\n✅ No Kill Rule Violations Detected")
        
        # SECTION 6: Final Verdict
        justification = final_verdict['justification']
        report.append(f"\n⚖️ SECTION 6: FINAL VERDICT")
        report.append(f"VERDICT: {final_verdict['verdict']['verdict']}")
        report.append(f"Overall Score: {final_verdict['verdict']['overall_score']:.1f}/100")
        report.append(f"Mathematical Score: {justification.mathematical_score:.1f}/100")
        report.append(f"Risk-Adjusted Score: {justification.risk_adjusted_score:.1f}/100")
        report.append(f"Survivability Score: {justification.survivability_score:.1f}/100")
        report.append(f"CV Value Added: {justification.cv_value_added:.1f}%")
        
        report.append(f"Reason: {final_verdict['verdict']['reason']}")
        report.append(f"Recommendation: {final_verdict['verdict']['recommendation']}")
        
        # ICT Component Analysis
        if justification.ict_effectiveness:
            report.append(f"\n🔍 ICT COMPONENT EFFECTIVENESS:")
            for component, score in justification.ict_effectiveness.items():
                status = "✅" if score >= 0.6 else "🟡" if score >= 0.4 else "❌"
                report.append(f"  {status} {component.replace('_', ' ').title()}: {score:.1%}")
        
        # Strengths and Weaknesses
        if justification.strengths:
            report.append(f"\n💪 STRENGTHS:")
            for strength in justification.strengths:
                report.append(f"  ✅ {strength}")
        
        if justification.weaknesses:
            report.append(f"\n⚠️ WEAKNESSES:")
            for weakness in justification.weaknesses:
                report.append(f"  ❌ {weakness}")
        
        if justification.critical_failures:
            report.append(f"\n🔴 CRITICAL FAILURES:")
            for failure in justification.critical_failures:
                report.append(f"  🚨 {failure}")
        
        # Deployment Plan (if applicable)
        if final_verdict['deployment_plan']:
            plan = final_verdict['deployment_plan']
            report.append(f"\n🚀 DEPLOYMENT PLAN:")
            report.append(f"  Phase: {plan.phase.value}")
            report.append(f"  Capital Allocation: {plan.capital_allocation:.1%}")
            report.append(f"  Max Risk per Trade: {plan.risk_parameters['max_risk_per_trade']:.1%}")
            report.append(f"  Success Criteria: {len(plan.success_criteria)} metrics")
            report.append(f"  Kill Switches: {len(plan.kill_switches)} safeguards")
        
        # SECTION 7: Technical Next Steps
        report.append(f"\n🔧 SECTION 7: TECHNICAL NEXT STEPS")
        for i, step in enumerate(final_verdict['next_steps'], 1):
            report.append(f"{i}. {step}")
        
        # Mathematical Summary
        summary = final_verdict['mathematical_summary']
        report.append(f"\n📊 MATHEMATICAL SUMMARY:")
        report.append(f"Score Interpretation: {summary['score_interpretation']}")
        report.append(f"Mathematical Confidence: {summary['mathematical_confidence']:.1%}")
        report.append(f"Statistical Significance: {'✅' if summary['statistical_significance'] else '❌'}")
        
        # Final Assessment
        report.append(f"\n" + "="*100)
        if final_verdict['verdict']['verdict'] == Verdict.DEPLOY.value:
            report.append("🟢 STRATEGY APPROVED FOR DEPLOYMENT")
            report.append("✅ Mathematical edge confirmed - proceed with controlled deployment")
            report.append("💰 Capital survival + repeatable expectancy validated")
        elif final_verdict['verdict']['verdict'] == Verdict.OPTIMIZE.value:
            report.append("🟡 STRATEGY REQUIRES OPTIMIZATION")
            report.append("⚙️ Mathematical potential exists - optimization required")
            report.append("🎯 Address identified weaknesses before redeployment")
        else:
            report.append("🔴 STRATEGY REJECTED")
            report.append("❌ Mathematical edge does not exist - abandon strategy")
            report.append("🛡️ Capital protection prioritized over false narratives")
        
        report.append("="*100)
        report.append(f"Evaluation completed: {datetime.now().isoformat()}")
        report.append("🔬 ICT Concept Auditor - Protecting capital, not narratives")
        report.append("="*100)
        
        return "\n".join(report)
    
    def _compile_results(self, 
                        trades: List[Dict],
                        market_data: pd.DataFrame,
                        strategy_components: List[str],
                        ict_evaluation: Dict,
                        performance_evaluation: Dict,
                        ict_features: Dict,
                        cv_analysis: Optional[Dict],
                        final_verdict: Dict,
                        comprehensive_report: str) -> Dict:
        """Compile all evaluation results into comprehensive dictionary"""
        
        return {
            'metadata': {
                'evaluation_timestamp': datetime.now().isoformat(),
                'total_trades': len(trades),
                'market_data_bars': len(market_data),
                'strategy_components': strategy_components,
                'ict_components_used': ict_evaluation['strategy_analysis']['components'],
                'cv_enabled': cv_analysis is not None
            },
            'input_data': {
                'trades_summary': {
                    'total_trades': len(trades),
                    'total_pnl': sum(t.get('pnl', 0) for t in trades),
                    'win_rate': len([t for t in trades if t.get('pnl', 0) > 0]) / len(trades) if trades else 0
                },
                'market_data_summary': {
                    'start_date': str(market_data.index[0]) if len(market_data) > 0 else None,
                    'end_date': str(market_data.index[-1]) if len(market_data) > 0 else None,
                    'total_bars': len(market_data)
                }
            },
            'ict_evaluation': ict_evaluation,
            'ict_features': ict_features,
            'performance_evaluation': performance_evaluation,
            'cv_analysis': cv_analysis,
            'final_verdict': final_verdict,
            'comprehensive_report': comprehensive_report
        }
    
    def save_evaluation_results(self, results: Dict, filename: str = None) -> str:
        """Save complete evaluation results to file"""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            verdict = results['final_verdict']['verdict']['verdict'].split()[1]  # Extract DEPLOY/OPTIMIZE/KILL
            filename = f"ict_evaluation_{verdict}_{timestamp}.json"
        
        # Create results directory
        results_dir = Path("ict_evaluation_results")
        results_dir.mkdir(exist_ok=True)
        
        filepath = results_dir / filename
        
        # Save JSON results
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Save text report
        report_filename = filepath.stem + "_report.txt"
        report_path = results_dir / report_filename
        
        with open(report_path, 'w') as f:
            f.write(results['comprehensive_report'])
        
        logger.info(f"📁 Evaluation results saved:")
        logger.info(f"   JSON: {filepath}")
        logger.info(f"   Report: {report_path}")
        
        return str(filepath)
    
    def _load_config(self) -> Dict:
        """Load configuration from file"""
        
        config_path = Path(self.config_file)
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            default_config = {
                'logging_level': 'INFO',
                'enable_cv': True,
                'save_visualizations': False,
                'min_trades': 30,
                'confidence_threshold': 0.05
            }
            
            # Save default config
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            
            return default_config
    
    def _setup_logging(self):
        """Setup logging configuration"""
        
        log_level = self.config.get('logging_level', 'INFO')
        
        # Remove default logger
        logger.remove()
        
        # Console logger
        logger.add(
            sys.stdout,
            format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>",
            level=log_level
        )
        
        # File logger
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logger.add(
            log_dir / "ict_auditor_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )
    
    def quick_evaluate(self, 
                      trades_file: str,
                      market_data_file: str,
                      components: List[str],
                      enable_cv: bool = True) -> Dict:
        """Quick evaluation from files"""
        
        logger.info("🚀 Quick Evaluation Mode")
        
        # Load trades
        trades = self._load_trades(trades_file)
        
        # Load market data
        market_data = self._load_market_data(market_data_file)
        
        # Run evaluation
        return self.evaluate_ict_strategy(trades, market_data, components, enable_cv=enable_cv)
    
    def _load_trades(self, trades_file: str) -> List[Dict]:
        """Load trades from CSV or JSON file"""
        
        file_path = Path(trades_file)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Trades file not found: {trades_file}")
        
        if file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
            return df.to_dict('records')
        elif file_path.suffix.lower() == '.json':
            with open(file_path, 'r') as f:
                return json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
    
    def _load_market_data(self, market_data_file: str) -> pd.DataFrame:
        """Load market data from CSV file"""
        
        file_path = Path(market_data_file)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Market data file not found: {market_data_file}")
        
        df = pd.read_csv(file_path)
        
        # Ensure datetime index
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
        elif 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
        elif df.index.name != 'time' and not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
            df.index.name = 'time'
        
        return df
    
    def generate_sample_data(self, 
                           num_trades: int = 100,
                           num_bars: int = 1000,
                           save_files: bool = True) -> Tuple[List[Dict], pd.DataFrame]:
        """Generate sample data for testing"""
        
        logger.info("🎲 Generating sample data for testing")
        
        # Generate market data
        dates = pd.date_range(start='2023-01-01', periods=num_bars, freq='H')
        
        # Random walk with trend
        np.random.seed(42)
        returns = np.random.normal(0.0001, 0.02, num_bars)
        prices = 100 * np.exp(np.cumsum(returns))
        
        # Create OHLC data
        ohlc_data = []
        for i, (date, close) in enumerate(zip(dates, prices)):
            high = close * (1 + abs(np.random.normal(0, 0.01)))
            low = close * (1 - abs(np.random.normal(0, 0.01)))
            open_price = low + (high - low) * np.random.random()
            volume = np.random.normal(1000000, 200000)
            
            ohlc_data.append({
                'time': date,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': max(volume, 0)
            })
        
        market_data = pd.DataFrame(ohlc_data)
        market_data.set_index('time', inplace=True)
        
        # Generate trades
        trades = []
        for i in range(num_trades):
            entry_time = dates[np.random.randint(50, len(dates) - 50)]
            exit_time = entry_time + pd.Timedelta(hours=np.random.randint(1, 24))
            
            entry_price = market_data.loc[entry_time, 'close']
            price_change = np.random.normal(0.0005, 0.02)
            exit_price = entry_price * (1 + price_change)
            
            pnl = (exit_price - entry_price) * 1000  # Simplified P&L
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': exit_time,
                'type': 'BUY' if price_change > 0 else 'SELL',
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'position_size': 0.1,
                'confidence': np.random.uniform(0.6, 0.9)
            })
        
        if save_files:
            # Save sample files
            market_data.to_csv("sample_market_data.csv")
            
            trades_df = pd.DataFrame(trades)
            trades_df.to_csv("sample_trades.csv", index=False)
            
            logger.info("📁 Sample files saved:")
            logger.info("   Market data: sample_market_data.csv")
            logger.info("   Trades: sample_trades.csv")
        
        return trades, market_data

def main():
    """Main function for running ICT Concept Auditor"""
    
    print("🔬 ICT CONCEPT AUDITOR")
    print("="*50)
    print("Mission: Deconstruct, formalize, quantify, and EVALUATE all ICT concepts")
    print("Philosophy: ICT concepts are HYPOTHESES, not truth")
    print("Approach: Mathematical validation or rejection")
    print("="*50)
    
    # Initialize auditor
    auditor = ICTConceptAuditor()
    
    # Example usage
    print("\n📋 Available options:")
    print("1. Generate sample data and run evaluation")
    print("2. Load existing data and run evaluation")
    print("3. Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == '1':
        # Generate sample data
        trades, market_data = auditor.generate_sample_data(num_trades=100, num_bars=1000)
        
        # Define strategy components
        components = [
            'market_structure',
            'liquidity_concepts',
            'fair_value_gaps',
            'order_blocks',
            'premium_discount'
        ]
        
        # Run evaluation
        results = auditor.evaluate_ict_strategy(trades, market_data, components, enable_cv=True)
        
        # Print summary
        print(f"\n🎯 Final Verdict: {results['final_verdict']['verdict']['verdict']}")
        print(f"📊 Overall Score: {results['final_verdict']['verdict']['overall_score']:.1f}/100")
        print(f"💡 Recommendation: {results['final_verdict']['verdict']['recommendation']}")
        
    elif choice == '2':
        # Load existing data
        trades_file = input("Enter trades file path: ").strip()
        market_data_file = input("Enter market data file path: ").strip()
        
        # Define components
        print("\nAvailable ICT components:")
        components_list = [
            'market_structure',
            'liquidity_concepts', 
            'fair_value_gaps',
            'order_blocks',
            'premium_discount',
            'time_based',
            'power_of_three'
        ]
        
        for i, comp in enumerate(components_list, 1):
            print(f"{i}. {comp}")
        
        selected = input("Enter component numbers (comma-separated): ").strip()
        selected_indices = [int(x.strip()) - 1 for x in selected.split(',')]
        components = [components_list[i] for i in selected_indices]
        
        # Run evaluation
        try:
            results = auditor.quick_evaluate(trades_file, market_data_file, components)
            
            # Print summary
            print(f"\n🎯 Final Verdict: {results['final_verdict']['verdict']['verdict']}")
            print(f"📊 Overall Score: {results['final_verdict']['verdict']['overall_score']:.1f}/100")
            print(f"💡 Recommendation: {results['final_verdict']['verdict']['recommendation']}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    else:
        print("👋 Goodbye!")
        return
    
    print("\n✅ Evaluation complete!")
    print("📁 Check the 'ict_evaluation_results' folder for detailed reports")

if __name__ == "__main__":
    main()
