# Wissh I Get Rich

## Overview
This project provides tools to analyze Solana blockchain trading data, specifically focusing on transactions involving Axiom programs. It supports two methods:
1. **Selenium Web Scraping** (legacy) - Scrapes data from Solscan website
2. **Solana RPC** (recommended) - Direct blockchain queries for faster and more reliable data

## Contents
- `solscan_scraper.py`: Legacy web scraping using Selenium
- `selenium_manager.py`: Selenium WebDriver management utility
- `solana_rpc_client.py`: **NEW** - Direct Solana RPC client for blockchain queries
- `main_rpc.py`: **NEW** - Main script for RPC-based data fetching
- `compare_methods.py`: Performance comparison between methods
- `MIGRATION_GUIDE.md`: Detailed guide for migrating from Selenium to RPC

## Setup

### Basic Setup
1. Install dependencies: 
   ```bash
   pip install -r requirements.txt
   ```

2. Create `.env` file:
   ```env
   # For RPC method (recommended)
   SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
   ```

### For Selenium Method (Legacy)
- Requires Chrome browser and ChromeDriver
- Slower but can handle dynamic web content

### For RPC Method (Recommended)
- No browser required
- Much faster (5-10x speedup)
- Direct blockchain access

## Usage

### Using RPC Method (Recommended)
```bash
# Run interactive script
python main_rpc.py

# Or use directly in Python
from solana_rpc_client import get_axiom_traders, save_address_trading_history

# Get addresses that traded with Axiom
addresses = get_axiom_traders(max_addresses=10)

# Get trading history for an address
result = save_address_trading_history("HwzkpaNPx6aFkeQ5We3JMn77q76dv9tTLEhkS5tQrNgE", days=1)
```

### Using Selenium Method (Legacy)
```bash
# Run the scraper
python solscan_scraper.py
```

### Compare Methods
```bash
# See performance comparison
python compare_methods.py
```

## Features
- Extract addresses that have interacted with Axiom programs
- Get detailed transaction history for specific addresses
- Analyze balance changes in transactions
- Export data in JSON format

## Migration from Selenium to RPC
See `MIGRATION_GUIDE.md` for detailed instructions on migrating from Selenium to RPC method.

### Key Benefits of RPC:
- **5-10x faster** than web scraping
- **More reliable** - no dependency on website changes
- **Lightweight** - no browser needed
- **Real-time data** - direct from blockchain

## Notes
- Public RPC endpoints have rate limits; consider premium endpoints for production use
- Token metadata lookup is simplified in the current implementation
- All timestamps are in UTC

## License
This project is licensed under the MIT License - see the LICENSE file for details (if applicable).
