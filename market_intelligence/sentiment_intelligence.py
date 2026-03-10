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
        Classify the source of the data based on metadata and content keywords.
        """
        text = raw_data.content.lower()
        source_type = SourceType.RETAIL
        confidence = 0.6
        reasoning = "General market news"

        # Smarter heuristic classification
        if any(x in text for x in ["fomc", "fed", "cpi", "ecb", "institutional", "macro"]):
             source_type = SourceType.INSTITUTIONAL_MACRO
             confidence = 0.85
             reasoning = "High-impact MACRO keywords detected"
        elif any(x in text for x in ["order block", "liquidity", "sweep", "fvg", "fair value"]):
             source_type = SourceType.PROFESSIONAL_ANALYST
             confidence = 0.8
             reasoning = "ICT/SMC technical terminology detected"
        elif any(x in text for x in ["safe haven", "treasury", "yields", "dollar index"]):
             source_type = SourceType.PROFESSIONAL_ANALYST
             confidence = 0.75
             reasoning = "Intermarket analysis detected"
        elif "twitter" in raw_data.platform.lower() or "reddit" in raw_data.platform.lower():
             source_type = SourceType.RETAIL
             confidence = 0.9
             reasoning = "Social media platform"

        return SourceClassification(
            source_type=source_type,
            confidence=confidence,
            reasoning=reasoning
        )

    def extract_sentiment(self, raw_data: RawSourceData, classification: SourceClassification) -> SentimentAnalysis:
        """
        Extract numeric sentiment scores with focus on Gold (XAU) and Macro.
        """
        text = raw_data.content.lower()
        score = 0.0
        tone = EmotionalTone.CAUTION
        bias = SentimentBias.NEUTRAL
        
        # Bullish Keywords (Gold specific & Macro)
        bullish = ["bull", "buy", "long", "upside", "safe haven", "rally", "inflation hedge", "dovish", "cut rates"]
        # Bearish Keywords
        bearish = ["bear", "sell", "short", "downside", "crash", "hawkish", "hike rates", "yields rising", "strong dollar"]
        
        bull_hits = sum(1 for x in bullish if x in text)
        bear_hits = sum(1 for x in bearish if x in text)
        
        if bull_hits > bear_hits:
            score = 0.2 * bull_hits
            bias = SentimentBias.BULLISH
            tone = EmotionalTone.CONFIDENCE if bull_hits > 2 else EmotionalTone.CAUTION
        elif bear_hits > bull_hits:
            score = -0.2 * bear_hits
            bias = SentimentBias.BEARISH
            tone = EmotionalTone.FEAR if bear_hits > 2 else EmotionalTone.CAUTION
        
        # Cap score
        score = max(-1.0, min(1.0, score))

        # Adjust conviction based on classification
        conviction = classification.confidence
        if classification.source_type == SourceType.INSTITUTIONAL_MACRO:
            conviction *= 1.2
            
        return SentimentAnalysis(
            bias=bias,
            conviction_score=min(1.0, conviction),
            emotional_tone=tone,
            time_horizon=TimeHorizon.INTRADAY,
            sentiment_score=score,
            crowd_density=0.5 if classification.source_type == SourceType.RETAIL else 0.3
        )

    def analyze_market_divergence(self, extracted_sentiment: List[SentimentAnalysis]) -> MarketDivergence:
        """
        Compute divergence between retail and institutional sentiment patterns.
        """
        retail_scores = [s.sentiment_score for s in extracted_sentiment if s.crowd_density >= 0.5]
        inst_scores = [s.sentiment_score for s in extracted_sentiment if s.crowd_density < 0.5]
        
        avg_retail = sum(retail_scores) / len(retail_scores) if retail_scores else 0.0
        avg_inst = sum(inst_scores) / len(inst_scores) if inst_scores else 0.0
        
        divergence = avg_inst - avg_retail
        direction = "Neutral"
        if divergence > 0.15:
            direction = "Inst > Retail (Bullish Divergence)"
        elif divergence < -0.15:
            direction = "Inst < Retail (Bearish Divergence)"
            
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
        Infers smart money focus based on the most frequent themes and high conviction.
        """
        # Logic: If high conviction news points to a direction, smart money is likely active there.
        high_conviction = [s for s in sentiments if s.conviction_score > 0.7]
        avg_prob = 0.5 + (len(high_conviction) * 0.1)
        
        # Detected Narratives (Dynamic extraction - simplified)
        # In a real version, we'd do NLP on the original text here.
        # For now, we'll label it based on the bias of high conviction news.
        bias_counts = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
        for s in high_conviction:
            bias_counts[s.bias.value.upper()] += 1
            
        top_bias = max(bias_counts, key=bias_counts.get)
        narrative = f"Institutional {top_bias} Accumulation" if avg_prob > 0.6 else "Market Indecision / Waiting for Macro"

        return SmartMoneyInference(
            probability_smart_money_active=min(0.95, avg_prob),
            detected_narratives=[narrative],
            liquidity_focus_score=0.7 if avg_prob > 0.6 else 0.4,
            risk_alignment="Defensive" if top_bias == "BEARISH" else "Aggressive" if top_bias == "BULLISH" else "Neutral"
        )
    
    def generate_decision(self, sentiment: SentimentAnalysis, divergence: MarketDivergence) -> DecisionImpact:
        """
        Generate trading decision impact based on cross-sentimental analysis.
        """
        action = "ALLOW"
        reason = "Sentiment aligns with structural bias"
        risk_modifier = 1.0

        if divergence.contrarian_opportunity:
            action = "REDUCE"
            reason = "High Retail/Institutional divergence (Contrarian Risk)"
            risk_modifier = 0.5
        elif abs(sentiment.sentiment_score) > 0.7:
             action = "CAUTION"
             reason = "Extreme sentiment reached - potential exhaustion"
             risk_modifier = 0.8
        
        return DecisionImpact(
            action=action,
            reason=reason,
            risk_modifier=risk_modifier
        )

    def run_analysis_cycle(self, raw_data_batch: List[RawSourceData]) -> IntelligenceReport:
        """
        Main entry point: Process real-time data batch and generate report.
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
            else:
                 institutional_sentiments.append(sentiment)

        divergence_metrics = self.analyze_market_divergence(processed_sentiments)
        smart_money = self.infer_smart_money(institutional_sentiments)
        
        # Weighted aggregate
        # Inst is weighted 5x more than retail for the final bias
        avg_retail = sum([s.sentiment_score for s in retail_sentiments]) / len(retail_sentiments) if retail_sentiments else 0.0
        avg_inst = sum([s.sentiment_score for s in institutional_sentiments]) / len(institutional_sentiments) if institutional_sentiments else 0.0
        
        final_score = (avg_retail * RETAIL_WEIGHT + avg_inst * INSTITUTIONAL_MACRO_WEIGHT) / (RETAIL_WEIGHT + INSTITUTIONAL_MACRO_WEIGHT)
        
        overall_sentiment = SentimentAnalysis(
            bias=SentimentBias.BULLISH if final_score > 0 else SentimentBias.BEARISH if final_score < 0 else SentimentBias.NEUTRAL,
            conviction_score=min(1.0, abs(final_score) * 2),
            emotional_tone=EmotionalTone.CONFIDENCE if abs(final_score) > 0.4 else EmotionalTone.CAUTION,
            time_horizon=TimeHorizon.INTRADAY,
            sentiment_score=final_score,
            crowd_density=0.5
        )

        decision = self.generate_decision(overall_sentiment, divergence_metrics)

        return IntelligenceReport(
            timestamp=datetime.now(),
            sentiment_summary=overall_sentiment,
            divergence_analysis=divergence_metrics,
            smart_money_inference=smart_money,
            decision_impact=decision,
            narrative_risk_score=0.4 + (abs(final_score) * 0.3)
        )
