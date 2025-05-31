"""
Solana Trading Service Module
Provides high-level functions for querying trading history and finding Axiom traders
"""
from datetime import datetime
from typing import Optional, List
from solana_rpc_client import SolanaRPCClient, AXIOM_PROGRAM_IDS


def get_trading_history(address: str, days: int = 1):
    """
    Main function to get and save address trading history using RPC
    
    Args:
        address: The Solana address to query
        days: Number of days to look back
    """
    print(f"Starting RPC data fetch for address: {address}")
    
    # Initialize RPC client
    client = SolanaRPCClient()
    
    # Get transactions (now includes balance changes)
    tx_result = client.get_address_transactions(address, days)
    
    if tx_result['total_found'] == 0:
        print("No Axiom transactions found")
        return None
    
    # Prepare final result
    total_balance_change_items = 0
    if tx_result.get('transactions'):
        for tx_item in tx_result['transactions']: # Iterate through the transactions list
            if tx_item.get('balance_changes'): # Check if the key exists and is not empty/None
                total_balance_change_items += len(tx_item['balance_changes'])

    result = {
        'address_id': address,
        'days_scraped': days,
        'transactions': tx_result['transactions'],
        # 'balance_changes': tx_result['balance_changes'], # Removed: Redundant as it's empty and changes are embedded
        'summary': {
            'total_transactions': tx_result['total_found'],
            'balance_changes_found': total_balance_change_items,
        },
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return result


def get_axiom_traders(max_addresses: int = 10):
    """
    Main function to get addresses that have traded with Axiom programs
    
    Args:
        max_addresses: Maximum number of addresses to collect
    """
    print("Starting to fetch Axiom traders using RPC")
    
    # Initialize RPC client
    client = SolanaRPCClient()
    
    all_addresses = set()
    
    # Get addresses for each Axiom program
    for program_id in AXIOM_PROGRAM_IDS:
        result = client.get_program_accounts(program_id, max_addresses)
        all_addresses.update(result['unique_addresses'])
        
        if len(all_addresses) >= max_addresses:
            break
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"axiom_traders_{timestamp}.txt"
    
    final_addresses = list(all_addresses)[:max_addresses]
    
    return final_addresses 