from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime

class SourceType(Enum):
    RETAIL = "Retail Trader"
    SEMI_PROFESSIONAL = "Semi-professional"
    PROFESSIONAL_ANALYST = "Professional Analyst"
    INSTITUTIONAL_MACRO = "Institutional / Macro"
    NOISE = "Noise / Promotional / Biased"

class SentimentBias(Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NEUTRAL = "Neutral"

class EmotionalTone(Enum):
    FEAR = "Fear"
    GREED = "Greed"
    EUPHORIA = "Euphoria"
    PANIC = "Panic"
    CAUTION = "Caution"
    CONFIDENCE = "Confidence"

class TimeHorizon(Enum):
    SCALP = "Scalp"
    INTRADAY = "Intraday"
    SWING = "Swing"
    MACRO = "Macro"

@dataclass
class RawSourceData:
    content: str
    source_url: str
    platform: str
    timestamp: datetime
    author_id: str
    metadata: Dict

@dataclass
class SourceClassification:
    source_type: SourceType
    confidence: float
    reasoning: str

@dataclass
class SentimentAnalysis:
    bias: SentimentBias
    conviction_score: float  # 0.0 to 1.0 (Low -> Extreme)
    emotional_tone: EmotionalTone
    time_horizon: TimeHorizon
    sentiment_score: float   # -1.0 to +1.0
    crowd_density: float     # 0.0 to 1.0 (Repetition density)
    
@dataclass
class MarketDivergence:
    retail_score: float
    institutional_score: float
    divergence_magnitude: float
    divergence_direction: str  # e.g., "Retail Bullish / Inst Bearish"
    contrarian_opportunity: bool

@dataclass
class SmartMoneyInference:
    probability_smart_money_active: float
    detected_narratives: List[str]
    liquidity_focus_score: float
    risk_alignment: str

@dataclass
class DecisionImpact:
    action: str  # ALLOW, REDUCE, IGNORE, BLOCK
    reason: str
    risk_modifier: float  # Multiplier for position sizing (e.g., 0.5x, 1.0x, 0.0x)

@dataclass
class IntelligenceReport:
    timestamp: datetime
    sentiment_summary: SentimentAnalysis
    divergence_analysis: MarketDivergence
    smart_money_inference: SmartMoneyInference
    decision_impact: DecisionImpact
    narrative_risk_score: float
