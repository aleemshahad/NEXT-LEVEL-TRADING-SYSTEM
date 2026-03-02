import sys
from datetime import datetime
from typing import List

# Ensure we can import from the local directory
# Ensure we can import from the local directory
import os
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.getcwd())

from market_intelligence.models import (
    IntelligenceReport, SentimentAnalysis, MarketDivergence, 
    SmartMoneyInference, DecisionImpact, SourceType, SentimentBias
)
from market_intelligence.sentiment_intelligence import SentimentIntelligenceEngine
from market_intelligence.data_acquisition import DataAcquisitionService

def format_report(report: IntelligenceReport) -> str:
    """
    Format the IntelligenceReport into the STRICT output format required.
    """
    sentiment = report.sentiment_summary
    divergence = report.divergence_analysis
    smart_money = report.smart_money_inference
    decision = report.decision_impact

    output = []
    output.append("==================================================")
    output.append(f"MARKET INTELLIGENCE REPORT | {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    output.append("==================================================\n")

    # SECTION 1: Market Sentiment Summary (Numeric)
    output.append("SECTION 1: Market Sentiment Summary (Numeric)")
    output.append("-" * 40)
    output.append(f"• Overall Bias:       {sentiment.bias.value.upper()}")
    output.append(f"• Sentiment Score:    {sentiment.sentiment_score:.2f} (-1.0 to +1.0)")
    output.append(f"• Emotional Tone:     {sentiment.emotional_tone.value.upper()}")
    output.append(f"• Conviction Level:   {sentiment.conviction_score:.2f} (0.0 to 1.0)")
    output.append(f"• Time Horizon:       {sentiment.time_horizon.value}")
    output.append("")

    # SECTION 2: Retail vs Institutional Sentiment Comparison
    output.append("SECTION 2: Retail vs Institutional Sentiment Comparison")
    output.append("-" * 40)
    output.append(f"• Retail Score:       {divergence.retail_score:.2f}")
    output.append(f"• Institutional Score:{divergence.institutional_score:.2f}")
    output.append(f"• Divergence Mag:     {divergence.divergence_magnitude:.2f}")
    output.append(f"• Direction:          {divergence.divergence_direction}")
    output.append("")

    # SECTION 3: Crowd Density & Narrative Risk
    output.append("SECTION 3: Crowd Density & Narrative Risk")
    output.append("-" * 40)
    output.append(f"• Crowd Density:      {sentiment.crowd_density:.2f} (0-1)")
    output.append(f"• Narrative Risk:     {report.narrative_risk_score:.2f} (0-1)")
    output.append(f"• Crowdedness Status: {'OVERCROWDED' if sentiment.crowd_density > 0.7 else 'NORMAL'}")
    output.append("")

    # SECTION 4: Smart Money Inference (Probabilistic)
    output.append("SECTION 4: Smart Money Inference (Probabilistic)")
    output.append("-" * 40)
    output.append(f"• Smart Money Prob:   {smart_money.probability_smart_money_active:.2f} (0-1)")
    output.append(f"• Liquidity Focus:    {smart_money.liquidity_focus_score:.2f}")
    output.append(f"• Risk Alignment:     {smart_money.risk_alignment}")
    output.append(f"• Top Narratives:     {', '.join(smart_money.detected_narratives)}")
    output.append("")

    # SECTION 5: Sentiment-Based Risk Adjustments
    output.append("SECTION 5: Sentiment-Based Risk Adjustments")
    output.append("-" * 40)
    output.append(f"• Risk Modifier:      x{decision.risk_modifier:.2f}")
    if divergence.contrarian_opportunity:
        output.append("• ALERT:              POTENTIAL CONTRARIAN ZONE DETECTED")
    output.append("")

    # SECTION 6: AI Decision Impact (Allow / Filter / Reduce / Block)
    output.append("SECTION 6: AI Decision Impact")
    output.append("-" * 40)
    output.append(f"• DECISION:           {decision.action}")
    output.append(f"• REASON:             {decision.reason}")
    output.append("==================================================")
    
    return "\n".join(output)

def main():
    print("Initializing Autonomous Market Intelligence AI...")
    
    # 1. Initialize Components
    acquisition_service = DataAcquisitionService()
    intelligence_engine = SentimentIntelligenceEngine()

    # 2. Acquire Data
    print(" crawling data sources...")
    raw_data = acquisition_service.aggregate_data()
    print(f" collected {len(raw_data)} data points.\n")

    # 3. Process Data
    print(" analyzing sentiment and market structure...")
    report = intelligence_engine.run_analysis_cycle(raw_data)

    # 4. Output Result
    formatted_report = format_report(report)
    print("\n" + formatted_report)
    
    # Optional: Save to file for other systems to pick up
    with open("latest_intelligence_report.txt", "w") as f:
        f.write(formatted_report)

if __name__ == "__main__":
    main()
