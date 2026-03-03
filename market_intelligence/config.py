RETAIL_WEIGHT = 0.2
SEMI_PROFESSIONAL_WEIGHT = 0.5
PROFESSIONAL_ANALYST_WEIGHT = 0.8
INSTITUTIONAL_MACRO_WEIGHT = 1.0
NOISE_WEIGHT = 0.0

# Sentiment thresholds
EXTREME_OPTIMISM = 0.8
EXTREME_PESSIMISM = -0.8
NEUTRAL_ZONE_LOW = -0.2
NEUTRAL_ZONE_HIGH = 0.2

# Divergence thresholds
HIGH_DIVERGENCE_THRESHOLD = 0.5  # If retail vs Inst difference > 0.5
CONTRARIAN_OPPORTUNITY_SCORE = 0.7

# Risk Limits
MAX_SENTIMENT_EXPOSURE = 1.0
MIN_CONTRARIAN_CONFIDENCE = 0.6

import os

# AI / LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # Options: "openai", "anthropic", "groq", "local"
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "openai/gpt-oss-120b") # Default model

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Groq Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-120b")

# Data Source APIs
# Twitter / X (Tweepy)
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")

# Reddit (PRAW)
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "market_intelligence_bot/1.0")

