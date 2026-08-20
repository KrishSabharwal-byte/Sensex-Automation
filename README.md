# 📈 SENSEX Trading Automation

An automated market-analysis system built to monitor **SENSEX market data**, process technical indicators, generate structured trading signals, and automate different parts of the market-analysis workflow.

The project is designed with a modular architecture so that market data fetching, indicator calculations, signal generation, risk management, database operations, and broker integrations can be handled independently.

> ⚠️ **Disclaimer:** This project is developed for educational, research, and automation purposes. It does not provide financial advice or guarantee trading profits.

---

## 🚀 Project Overview

The **SENSEX Automation System** continuously collects market data and processes it through multiple analytical components to identify potential market conditions.

Instead of manually monitoring charts throughout the trading session, the system automates the complete analysis pipeline.

### 🔄 Workflow

```text
Market Data
     ↓
Data Processing
     ↓
Technical Indicators
     ↓
Signal Analysis
     ↓
Decision Engine
     ↓
Risk Management
     ↓
Trade / Alert / Database
```

---

## ✨ Features

- 📡 Real-time SENSEX market data monitoring
- 📊 Historical candle data processing
- 🧮 Automated technical indicator calculations
- 🤖 Rule-based automated decision engine
- ⚡ Real-time signal generation
- 🎯 Dynamic strike-selection logic
- 🛡️ Risk-management controls
- ⏰ Time-based trade management
- 💾 MongoDB integration for storing market data and signals
- 🔌 Broker API integration support
- 🔐 Secure environment-variable configuration
- 📝 Automated logging and error tracking
- 🧩 Modular Python architecture
- 🌐 API-ready backend architecture
- 📈 Easily extendable for additional indices and strategies

---

## 📊 Technical Indicators

The automation architecture can process multiple technical indicators, including:

- 📈 **EMA — Exponential Moving Average**
- 📊 **RSI — Relative Strength Index**
- 💪 **ADX — Average Directional Index**
- 🔄 **MACD — Moving Average Convergence Divergence**
- 📦 **Volume Analysis**
- 📉 Price-action based calculations

Multiple indicators can be processed together by the decision engine instead of relying on a single market signal.

---

## 🎯 Strike Selection

The system contains automated strike-selection logic for identifying suitable option strikes based on the current market price.

The module dynamically evaluates the **SENSEX LTP** and determines appropriate:

```text
📈 CALL Strike
📉 PUT Strike
```

Strike-selection rules can be configured independently without modifying the rest of the trading system.

---

## 🤖 Automation Engine

The automation engine continuously performs the following operations:

```text
1️⃣ Fetch Market Data
        ↓
2️⃣ Validate Data
        ↓
3️⃣ Calculate Indicators
        ↓
4️⃣ Analyze Market Conditions
        ↓
5️⃣ Generate Signal
        ↓
6️⃣ Select Relevant Instrument
        ↓
7️⃣ Apply Risk Rules
        ↓
8️⃣ Execute / Simulate / Store Decision
```

This separation makes the system easier to test, debug, maintain, and upgrade.

---

## 🏗️ Project Architecture

```text
sensex-automation/
│
├── main.py
│
├── config.py
│
├── requirements.txt
├── README.md
├── .env
├── .gitignore
│
├── data/
│   ├── market_data.py
│   └── historical_data.py
│
├── indicators/
│   ├── rsi.py
│   ├── ema.py
│   ├── adx.py
│   ├── macd.py
│   └── volume.py
│
├── strategy/
│   ├── signal_engine.py
│   └── strike_selector.py
│
├── risk/
│   └── risk_manager.py
│
├── broker/
│   ├── authentication.py
│   └── broker_api.py
│
├── database/
│   └── mongodb.py
│
├── services/
│   └── automation_service.py
│
├── utils/
│   ├── logger.py
│   └── helpers.py
│
└── logs/
```

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| 🐍 Python | Core automation |
| 🐼 Pandas | Market-data processing |
| 🔢 NumPy | Numerical calculations |
| 📊 Technical Indicators | Market analysis |
| 🌐 REST APIs | Market/Broker communication |
| 🍃 MongoDB | Market and signal storage |
| 🔐 Python Dotenv | Environment management |
| ⚡ FastAPI / Flask | Backend API support |
| 📝 Python Logging | Monitoring and debugging |

---

## ⚙️ Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/yourusername/sensex-automation.git
```

Move inside the project:

```bash
cd sensex-automation
```

---

### 2️⃣ Create a Virtual Environment

```bash
python -m venv venv
```

#### Windows PowerShell

```powershell
.\venv\Scripts\Activate.ps1
```

#### macOS / Linux

```bash
source venv/bin/activate
```

---

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔐 Environment Configuration

Create a `.env` file inside the root directory.

Example:

```env
BROKER_API_KEY=your_api_key
BROKER_CLIENT_ID=your_client_id
BROKER_MPIN=your_mpin
BROKER_TOTP_SECRET=your_totp_secret

MONGO_URI=your_mongodb_connection_string
MONGO_DB_NAME=SensexAutomation

ENVIRONMENT=development
```

> 🚨 Never upload your `.env` file, API keys, passwords, access tokens, MPINs, or TOTP secrets to GitHub.

Add `.env` to `.gitignore`:

```gitignore
.env
venv/
__pycache__/
*.log
```

---

## ▶️ Running the Project

Start the automation:

```bash
python main.py
```

The application can then initialize:

```text
✅ Broker authentication
✅ Market data connection
✅ Database connection
✅ Indicator engine
✅ Signal engine
✅ Risk manager
✅ Automation loop
```

---

## 📡 Market Data Pipeline

Market data passes through several stages before being used by the decision engine.

```text
Broker / Market API
        ↓
Raw OHLCV Data
        ↓
Data Validation
        ↓
DataFrame Processing
        ↓
Indicator Calculation
        ↓
Signal Engine
```

Typical market data includes:

```text
Timestamp
Open
High
Low
Close
Volume
LTP
```

---

## 💾 Database

MongoDB can be used to store information including:

```text
📊 Market candles
📈 Indicator values
🤖 Generated signals
🎯 Selected strikes
💼 Trade information
📝 Execution logs
⚠️ Errors
```

Example document structure:

```json
{
  "symbol": "SENSEX",
  "timestamp": "2026-08-20T10:30:00",
  "ltp": 81250.45,
  "signal": "WAIT",
  "status": "ACTIVE"
}
```

---

## 🛡️ Risk Management

Risk management is handled separately from signal generation.

The system can support controls such as:

- 🛑 Stop-loss management
- 🎯 Profit-target management
- 💰 Position sizing
- ⏱️ Time-based exits
- 🔢 Maximum trades per session
- 🚫 Duplicate-trade prevention
- 📉 Maximum daily loss protection
- ⚠️ Invalid-data protection
- 🔌 Broker/API failure handling

This design prevents the signal engine from directly controlling every trading decision.

---

## 🧠 Decision Engine

The decision engine evaluates multiple pieces of market information before producing an action.

Possible outputs include:

```text
🟢 CALL SIGNAL
🔴 PUT SIGNAL
🟡 WAIT
⚪ NO TRADE
```

The actual strategy conditions are intentionally separated from the public repository documentation.

---

## 🔄 Example Automation Cycle

```python
while market_is_open:

    market_data = fetch_market_data()

    indicators = calculate_indicators(market_data)

    signal = analyze_market(indicators)

    if signal:
        apply_risk_management(signal)

    store_results()

    wait_for_next_cycle()
```

The actual production implementation can include additional validation, authentication, exception handling, retry mechanisms, and execution controls.

---

## 🔒 Security

Sensitive credentials should always be stored using environment variables.

### ❌ Never commit:

```text
API Keys
Passwords
JWT Tokens
Refresh Tokens
TOTP Secrets
MPIN
MongoDB Credentials
Broker Credentials
```

### ✅ Use:

```text
.env
Environment Variables
Secrets Managers
.gitignore
```

---

## 🧪 Development Modes

The system can be expanded to support multiple operating modes.

```text
🧪 Simulation Mode
📊 Paper Trading Mode
📡 Live Data Mode
🚀 Live Execution Mode
```

Development and testing should be performed before enabling any real trading functionality.

---

## 📈 Future Improvements

Planned improvements can include:

- 🤖 Machine Learning based market analysis
- 🧠 AI-assisted signal evaluation
- 📊 Interactive trading dashboard
- 🔔 Telegram / WhatsApp alerts
- 📧 Email notifications
- 📈 Live candlestick visualization
- 🔄 WebSocket market-data streaming
- ⚡ Faster asynchronous processing
- 📉 Backtesting engine
- 🧪 Paper-trading environment
- 📊 Performance analytics
- 💹 Portfolio-level risk management
- 🧠 Adaptive market-condition detection
- 🌐 Cloud deployment
- 🐳 Docker support
- 🔁 Automated recovery mechanisms

---

## 🌐 Supported Expansion

Although the current project focuses on **SENSEX**, the architecture can be expanded to work with other financial instruments such as:

```text
📈 NIFTY 50
🏦 BANK NIFTY
💹 FINNIFTY
📊 Individual Stocks
📉 Futures
📑 Options
```

---

## ⚠️ Disclaimer

This repository is intended for **educational, software-development, automation, and research purposes only**.

Financial markets involve substantial risk. Automated trading systems can experience losses due to market volatility, API failures, network problems, incorrect configuration, execution delays, software bugs, or unexpected market conditions.

Nothing in this repository should be considered financial or investment advice.

---

## 👨‍💻 Author

Developed as part of an **AI/ML and financial-market automation project**, combining:

```text
🐍 Python Development
🤖 AI / ML
📊 Data Analysis
📈 Financial Market Automation
🔌 API Integration
🗄️ Database Engineering
⚡ Backend Development
```

---

## ⭐ Support

If you find this project useful, consider giving the repository a **⭐ Star**.

```text
⭐ Star
🍴 Fork
💻 Build
🧪 Experiment
🚀 Improve
```

---

### 📌 SENSEX Automation

**Turning live market data into structured, automated decision workflows. 📈🤖**
