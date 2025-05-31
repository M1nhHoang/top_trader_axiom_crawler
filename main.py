"""
Main script to use Solana RPC instead of Selenium scraping
"""
from solana_trading_service import get_trading_history, get_axiom_traders
import json
from datetime import datetime

# ====================================
# ========= Get Axiom traders ========
# ====================================

addresses = get_axiom_traders(10)

if addresses:
    with open('axiom_traders.txt', 'w', encoding='utf-8') as f:
        f.write(f"Axiom Traders - Fetched via RPC\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total found: {len(addresses)}\n")
        f.write("=" * 50 + "\n\n")
        
        for i, address in enumerate(addresses, 1):
            f.write(f"{i:3d}. {address}\n")
    
    print(f"Results saved to: axiom_traders.txt")

# ====================================
# === Get address trading history ====
# ====================================

address = "6xspgTx3zS1iYvFy73fWhbRTVtLfCqbAVJHxUxhurHvC"

result = get_trading_history(address)

if result:
    # Save to file
    filename = f"address_trading_history_{address[:10]}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to: {filename}")