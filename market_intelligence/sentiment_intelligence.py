from datetime import datetime
from typing import List, Dict, Optional
import random

try:
    from .models import (
        SourceType, SentimentBias, EmotionalTone, TimeHorizon,
        RawSourceData, SourceClassification, SentimentAnalysis,
        MarketDivergence, SmartMoneyInference, DecisionImpact, IntelligenceReport
    )
    from .config import (
        RETAIL_WEIGHT, SEMI_PROFESSIONAL_WEIGHT, PROFESSIONAL_ANALYST_WEIGHT,
        INSTITUTIONAL_MACRO_WEIGHT, NOISE_WEIGHT, HIGH_DIVERGENCE_THRESHOLD
    )
except (ImportError, ValueError):
    from market_intelligence.models import (
        SourceType, SentimentBias, EmotionalTone, TimeHorizon,
        RawSourceData, SourceClassification, SentimentAnalysis,
        MarketDivergence, SmartMoneyInference, DecisionImpact, IntelligenceReport
    )
    from market_intelligence.config import (
        RETAIL_WEIGHT, SEMI_PROFESSIONAL_WEIGHT, PROFESSIONAL_ANALYST_WEIGHT,
        INSTITUTIONAL_MACRO_WEIGHT, NOISE_WEIGHT, HIGH_DIVERGENCE_THRESHOLD
    )

class SentimentIntelligenceEngine:
    def __init__(self, ai_api_client=None):
        self.ai_client = ai_api_client
        self.retail_sentiment_history: List[float] = []
        self.institutional_sentiment_history: List[float] = []

    def classify_source(self, raw_data: RawSourceData) -> SourceClassification:
        """
        Classify the source of the data into Retail, Semi-pro, Pro Analyst, Institutional, or Noise.
        This uses heuristics or an AI agent to determine the source type.
        """
        # Placeholder logic: Simulate classification based on keywords or AI model
        text = raw_data.content.lower()
        classification = SourceType.RETAIL
        confidence = 0.5
        reasoning = "Default classification (Retail)"

        if "cpi" in text or "fed" in text or "liquidity" in text:
             classification = SourceType.INSTITUTIONAL_MACRO
             confidence = 0.8
             reasoning = "Mentions key macro indicators"
        elif "moon" in text or "pump" in text or "hodl" in text:
             classification = SourceType.RETAIL
             confidence = 0.9
             reasoning = "Retail slang detected"
        elif "technical analysis" in text or "fibonacci" in text:
             classification = SourceType.SEMI_PROFESSIONAL
             confidence = 0.7
             reasoning = "Uses technical terminology"
        
        # In a real implementation with AI Client:
        # prompt = f"Classify this source: {raw_data.content}"
        # response = self.ai_client.evaluate(prompt)
        # classification = parse_response(response)

        return SourceClassification(
            source_type=classification,
            confidence=confidence,
            reasoning=reasoning
        )

    def extract_sentiment(self, raw_data: RawSourceData, classification: SourceClassification) -> SentimentAnalysis:
        """
        Extract numeric sentiment scores, emotional tone, and conviction.
        """
        text = raw_data.content.lower()
        score = 0.0
        tone = EmotionalTone.CAUTION
        bias = SentimentBias.NEUTRAL
        
        # Simple keyword based logic for demonstration
        if "bull" in text or "buy" in text or "long" in text:
            score = 0.6
            bias = SentimentBias.BULLISH
            tone = EmotionalTone.CONFIDENCE
        elif "bear" in text or "sell" in text or "short" in text:
            score = -0.6
            bias = SentimentBias.BEARISH
            tone = EmotionalTone.FEAR
        
        if classification.source_type == SourceType.RETAIL:
            # Down-weight retail sentiment magnitude
            score *= 0.5

        return SentimentAnalysis(
            bias=bias,
            conviction_score=0.7, # Should be dynamic based on language intensity
            emotional_tone=tone,
            time_horizon=TimeHorizon.INTRADAY, # Default
            sentiment_score=score,
            crowd_density=0.4 # Placeholder
        )

    def analyze_market_divergence(self, extracted_sentiment: List[SentimentAnalysis]) -> MarketDivergence:
        """
        Compute divergence between retail and institutional sentiment.
        """
        retail_scores = [s.sentiment_score for s in extracted_sentiment if s.crowd_density > 0.6] # Example filter
        inst_scores = [s.sentiment_score for s in extracted_sentiment if abs(s.sentiment_score) > 0.5] # Example filter

        # Proper logic: iterate inputs and check classification if passed in context, 
        # but here we simplify as this method usually takes a list of processed results.
        # Let's assume we store history or aggregate the passed batch.
        
        avg_retail = sum(retail_scores) / len(retail_scores) if retail_scores else 0.0
        avg_inst = sum(inst_scores) / len(inst_scores) if inst_scores else 0.0
        
        divergence = avg_inst - avg_retail
        direction = "Neutral"
        if divergence > 0.3:
            direction = "Institutional Bullish / Retail Bearish"
        elif divergence < -0.3:
            direction = "Institutional Bearish / Retail Bullish"
            
        is_contrarian = abs(divergence) >= HIGH_DIVERGENCE_THRESHOLD

        return MarketDivergence(
            retail_score=avg_retail,
            institutional_score=avg_inst,
            divergence_magnitude=abs(divergence),
            divergence_direction=direction,
            contrarian_opportunity=is_contrarian
        )

    def infer_smart_money(self, sentiments: List[SentimentAnalysis]) -> SmartMoneyInference:
        """
        Infer smart money behavior from aggregate sentiment patterns.
        """
        # Logic: High conviction + Low emotion + Macro/Institutional source = High Smart Money Probability
        # For this example, we return a mocked high probability inference
        return SmartMoneyInference(
            probability_smart_money_active=0.75,
            detected_narratives=["Risk-off due to CPI data", "Sector rotation into defensive"],
            liquidity_focus_score=0.8,
            risk_alignment="Defensive"
        )
    
    def generate_decision(self, sentiment: SentimentAnalysis, divergence: MarketDivergence) -> DecisionImpact:
        """
        Generate trading decision impact based on sentiment and divergence.
        """
        action = "ALLOW"
        reason = "Sentiment aligns with market structure"
        risk_modifier = 1.0

        if divergence.contrarian_opportunity:
            action = "REDUCE"
            reason = "High retail/institutional divergence detected. Caution advised."
            risk_modifier = 0.5
        
        if sentiment.emotional_tone == EmotionalTone.EUPHORIA or sentiment.emotional_tone == EmotionalTone.PANIC:
            if divergence.divergence_magnitude < 0.2: # Crowd is confirming the move
                 action = "CAUTION"
                 reason = "Extreme sentiment - potential reversal zone."
                 risk_modifier = 0.7

        return DecisionImpact(
            action=action,
            reason=reason,
            risk_modifier=risk_modifier
        )

    def run_analysis_cycle(self, raw_data_batch: List[RawSourceData]) -> IntelligenceReport:
        """
        Main entry point: Process a batch of raw data and return a full intelligence report.
        """
        processed_sentiments = []
        retail_sentiments = []
        institutional_sentiments = []

        for data in raw_data_batch:
            classification = self.classify_source(data)
            sentiment = self.extract_sentiment(data, classification)
            processed_sentiments.append(sentiment)
            
            if classification.source_type == SourceType.RETAIL:
                retail_sentiments.append(sentiment)
            elif classification.source_type in [SourceType.INSTITUTIONAL_MACRO, SourceType.PROFESSIONAL_ANALYST]:
                 institutional_sentiments.append(sentiment)

        # Aggregate for divergence
        # Recalculate based on the categorized lists
        avg_retail = sum([s.sentiment_score for s in retail_sentiments]) / len(retail_sentiments) if retail_sentiments else 0.0
        avg_inst = sum([s.sentiment_score for s in institutional_sentiments]) / len(institutional_sentiments) if institutional_sentiments else 0.0
        
        divergence_val = avg_inst - avg_retail
        divergence_dir = "Neutral"
        if divergence_val > 0.2: divergence_dir = "Inst > Retail (Bullish Bias)"
        elif divergence_val < -0.2: divergence_dir = "Inst < Retail (Bearish Bias)"
        
        divergence_metrics = MarketDivergence(
             retail_score=avg_retail,
             institutional_score=avg_inst,
             divergence_magnitude=abs(divergence_val),
             divergence_direction=divergence_dir,
             contrarian_opportunity=(abs(divergence_val) > HIGH_DIVERGENCE_THRESHOLD)
        )

        smart_money = self.infer_smart_money(institutional_sentiments)
        
        # Aggregate overall sentiment (weighted)
        overall_score = (avg_retail * RETAIL_WEIGHT + avg_inst * INSTITUTIONAL_MACRO_WEIGHT) / (RETAIL_WEIGHT + INSTITUTIONAL_MACRO_WEIGHT)
        overall_sentiment = SentimentAnalysis(
            bias=SentimentBias.BULLISH if overall_score > 0 else SentimentBias.BEARISH,
            conviction_score=abs(overall_score),
            emotional_tone=EmotionalTone.CAUTION, # Simplify aggregation
            time_horizon=TimeHorizon.INTRADAY,
            sentiment_score=overall_score,
            crowd_density=0.5 # Placeholder
        )

        decision = self.generate_decision(overall_sentiment, divergence_metrics)

        return IntelligenceReport(
            timestamp=datetime.now(),
            sentiment_summary=overall_sentiment,
            divergence_analysis=divergence_metrics,
            smart_money_inference=smart_money,
            decision_impact=decision,
            narrative_risk_score=0.4 # Placeholder
        )
