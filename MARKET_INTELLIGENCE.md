# Market Intelligence & Decision Support Engine

This module implements an autonomous market intelligence system designed to process unstructured data from social media, news, and analyst reports, extract sentiment, and provide actionable decision support for trading systems.

## Core Components

### 1. Sentiment Intelligence Engine (`market_intelligence/sentiment_intelligence.py`)
- **Source Classification**: Distinguishes between Retail, Professional, and Institutional sources.
- **Sentiment Extraction**: Converts text to numeric scores (-1.0 to +1.0) and emotional tone.
- **Divergence Analysis**: Identifies when Retail and Institutional sentiment conflict (Contrarian Indicators).
- **Smart Money Inference**: Probabilistic assessment of institutional activity.

### 2. Data Acquisition (`market_intelligence/data_acquisition.py`)
- Abstract interface for data sources.
- Simulated crawlers for:
  - Social Platforms (Twitter, Reddit)
  - Analyst Blogs
  - Macro News

### 3. Data Models (`market_intelligence/models.py`)
- Strictly typed data structures for all intelligence artifacts using `dataclasses` and `Enum`.

## Usage

### Running the Intelligence Report

To generate a standalone market intelligence report:

```bash
python run_market_intelligence.py
```

This will output a structured report to the console and save it to `latest_intelligence_report.txt`.

### Integration with Trading System

The engine is designed to be integrated into the `LiveTradingSystem`. 

Example Integration:

```python
from market_intelligence.sentiment_intelligence import SentimentIntelligenceEngine
from market_intelligence.data_acquisition import DataAcquisitionService

# Initialize
acquisition = DataAcquisitionService()
engine = SentimentIntelligenceEngine()

# In your trading loop:
raw_data = acquisition.aggregate_data()
report = engine.run_analysis_cycle(raw_data)

# Use decision impact
if report.decision_impact.action == "BLOCK":
    logger.warning("Trading blocked by Market Intelligence")
    return
elif report.decision_impact.action == "REDUCE":
    position_size *= report.decision_impact.risk_modifier
```

## Configuration

Adjust weights and thresholds in `market_intelligence/config.py`.
