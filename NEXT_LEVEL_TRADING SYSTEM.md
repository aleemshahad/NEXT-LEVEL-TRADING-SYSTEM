# NEXT LEVEL TRADING SYSTEM

## Architecture and Flow

### System Initialization
- Interfaces with the MT5 Terminal.
- Trading settings are acquired from `config.yaml`.
- Connection is managed through a shared MT5Broker object to maintain state.

### Operational Modes
Supports execution on specific configured directions:
1. **BUY ONLY**
2. **SELL ONLY**
3. **BOTH** (Hedging enabled)

### Order Management
- **Batching**: System deploys orders in batches of 20 at a time.
- **Threshold**: When 15 orders from an active batch are engaged, a subsequent batch of 20 is configured.
- **Rolling**: As relative market pricing changes, new orders expand outward and the system rolls grid placements accordingly.
- **Recycling**: Closed orders are replaced precisely at their original entry levels to recycle the respective price point.

### Processing
- The internal main loop executes 10 iterations per second (0.1-second intervals).

### Trailing and Exit Logic
- **Individual Closes**: The system exits positions one by one via a trailing feature.
- **Smart Trailing Parameter**:
  - $1 profit target implements a $0.5 lock.
  - $25+ profit target implements an 80% lock of floating value.
- **Log Cleaning**: General logging displays only essential functional details such as finalized trades.
