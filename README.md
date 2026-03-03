# 🧠 NEXT LEVEL BRAIN - Simplified AI Trading System

**Created by: Aleem Shahzad**

A streamlined AI-powered trading system with ICT/SMC strategies, Autonomous Market Intelligence, and continuous learning capabilities.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- MetaTrader 5 terminal
- MT5 trading account
- Groq API Key (for Market Intelligence)

### Installation
```bash
pip install -r requirements.txt
```

### Configuration
Edit `config.yaml` with your MT5 credentials:
```yaml
mt5:
  login: your_account_number
  password: your_password
  server: your_server
```

Configure Market Intelligence in `market_intelligence/config.py`:
```python
LLM_PROVIDER = "groq"
GROQ_API_KEY = "your_key"
```

## 📊 Usage

### Live Trading
```bash
python live_trading.py
```

### Market Intelligence Report
Run the autonomous sentiment engine:
```bash
python run_market_intelligence.py
```

### Backtesting & AI Training
```bash
python backtesting.py
```

## ✨ Features

- **AI Trading Brain**: Neural network decision making with continuous learning
- **ICT/SMC Strategies**: Order blocks, fair value gaps, market structure analysis
- **Autonomous Market Intelligence**: 
  - Scrapes social media & news (Twitter, Reddit, Macro)
  - analyzing sentiment using Groq LLMs (Llama 3, Mixtral)
  - Detects smart money divergence & contrarian opportunities
- **Risk Management**: Dynamic position sizing and drawdown protection
- **Multi-Asset Support**: Forex, commodities, and cryptocurrencies

## 📁 File Structure

```
NEXT LEVEL BRAIN/
├── live_trading.py             # Main live trading system
├── run_market_intelligence.py  # Market Intelligence Entry Point
├── market_intelligence/        # Sentiment Analysis Module
│   ├── config.py               # AI & API Configuration
│   ├── sentiment_intelligence.py # Core Logic
│   ├── data_acquisition.py     # Data Crawlers
│   └── models.py               # Data Structures
├── backtesting.py              # Backtesting and AI training
├── config.yaml                 # General System Config
├── requirements.txt            # Dependencies
├── logs/                       # Trading logs
├── models/                     # AI models and memories
└── backtest_results/           # Backtest reports
```

## 🛠️ Configuration Options

### Risk Management
```yaml
risk:
  max_risk_per_trade: 0.02  # 2% per trade
  max_daily_loss: 0.05      # 5% daily loss limit
  max_drawdown: 0.15        # 15% max drawdown
```

### AI Settings
```yaml
ai:
  confidence_threshold: 0.6  # Minimum confidence for trades
  learning_enabled: true     # Enable continuous learning
```

## 🎯 How It Works

1. **Market Intelligence**: The system scans the web for sentiment, filtering retail noise from institutional signals.
2. **AI Analysis**: Neural network analyzes technical market conditions (ICT/SMC).
3. **Decision Synthesis**: Combines technicals with sentiment (e.g., "Bullish Structure" + "Contrarian Buy Signal").
4. **Risk Assessment**: Calculates optimal position sizes based on volatility and sentiment confidence.
5. **Trade Execution**: Places orders through MetaTrader 5.
6. **Continuous Learning**: AI remembers trade outcomes to refine future decisions.

## ⚠️ Disclaimer

This trading system is for educational purposes. Trading involves significant risk of loss. Always test thoroughly on demo accounts before live trading.

---

**© 2026 Aleem Shahzad - Next Level BRAIN Trading System**
