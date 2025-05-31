from solana.rpc.api import Client
from solders.pubkey import Pubkey
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Set
import time
import random
from dotenv import load_dotenv
import struct
import base58

load_dotenv()

# Axiom Program IDs
AXIOM_PROGRAM_IDS = [
    "AxiomfHaWDemCFBLBayqnEnNwE6b7B2Qz3UmzMpgbMG6",
    "AxiomxSitiyXyPjKgJ9XSrdhsydtZsskZTEDam3PxKcC"
]

# Metaplex Token Metadata Program ID
METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"

SOLANA_RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
]

class SolanaRPCClient:
    def __init__(self):
        """
        Initialize Solana RPC Client with random RPC selection
        """
        self.rpc_urls = SOLANA_RPC_URLS.copy()
        self.current_rpc_url = random.choice(self.rpc_urls)
        self.client = Client(self.current_rpc_url)
        print(f"Initialized Solana RPC Client with endpoint: {self.current_rpc_url}")
    
    def _switch_rpc_url(self):
        """Switch to a different RPC URL"""
        remaining_urls = [url for url in self.rpc_urls if url != self.current_rpc_url]
        if remaining_urls:
            self.current_rpc_url = random.choice(remaining_urls)
            self.client = Client(self.current_rpc_url)
            print(f"Switched to RPC endpoint: {self.current_rpc_url}")
            return True
        return False
    
    def _retry_request(self, request_func, *args, max_retries=3, **kwargs):
        """
        Retry mechanism for RPC requests
        
        Args:
            request_func: The RPC method to call
            max_retries: Maximum number of retry attempts
            *args, **kwargs: Arguments for the request function
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            if attempt > 0:
                wait_time = 2 ** attempt
                print(f"Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(wait_time)
                
                if attempt == 1:
                    # Switch RPC URL on first retry
                    if not self._switch_rpc_url():
                        print("No alternative RPC URLs available")
                        break
            
            try:
                # Handle exceptions during request
                response = request_func(*args, **kwargs)
                if response and response.value is not None:
                    return response

            except Exception as e: 
                pass
                
            
        print(f"All retry attempts failed")
        if last_error:
            print(f"Last error: {type(last_error).__name__}: {str(last_error)}")
        return None
    
    def get_program_accounts(self, program_id: str, max_addresses: int = 10) -> Dict[str, Any]:
        """
        Get accounts that have interacted with a specific program
        
        Args:
            program_id: The Solana program ID
            max_addresses: Maximum number of unique addresses to collect
            
        Returns:
            dict: Results containing unique addresses and metadata
        """
        print(f"Fetching accounts for program: {program_id}")
        print(f"Target addresses: {max_addresses}")
        
        unique_addresses = set()
        
        # Get recent signatures for the program
        program_pubkey = Pubkey.from_string(program_id)
        
        # Fetch transactions for the program
        limit = 1000  # Maximum allowed per request
        before = None
        
        while len(unique_addresses) < max_addresses:
            # Get signatures with retry mechanism
            response = self._retry_request(
                self.client.get_signatures_for_address,
                program_pubkey,
                before=before,
                limit=min(limit, max_addresses - len(unique_addresses))
            )
            
            if not response or not response.value:
                break
            
            # Process each signature to extract addresses
            for sig_info in response.value:
                print(f"Processing signature: {sig_info.signature}")
                # Get transaction details with retry
                tx_response = self._retry_request(
                    self.client.get_transaction,
                    sig_info.signature,
                    encoding="json",
                    max_supported_transaction_version=0
                )
                
                if tx_response and tx_response.value:
                    # Extract addresses from transaction
                    addresses = self._extract_addresses_from_transaction(tx_response.value)
                    unique_addresses.update(addresses)
                    
                    if len(unique_addresses) >= max_addresses:
                        break
            
            # Update before for pagination
            if response.value:
                before = response.value[-1].signature
            else:
                break
            
            print(f"Processed batch, found {len(unique_addresses)} unique addresses so far...")
        
        result = {
            'program_id': program_id,
            'unique_addresses': list(unique_addresses)[:max_addresses],
            'total_found': min(len(unique_addresses), max_addresses),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'target_count': max_addresses
        }
        
        print(f"\n=== Fetching Complete ===")
        print(f"Total unique addresses found: {result['total_found']}")
        
        return result
    
    def get_address_transactions(self, address: str, days: int = 1) -> Dict[str, Any]:
        """
        Get transactions for a specific address that interact with Axiom programs
        
        Args:
            address: The Solana address to query
            days: Number of days to look back
            
        Returns:
            dict: Results containing transactions and metadata
        """
        print(f"Fetching transactions for address: {address}")
        print(f"Looking for transactions from last {days} day(s)")
        
        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        transactions = []
        balance_changes = {}  # Store balance changes by signature
        
        address_pubkey = Pubkey.from_string(address)
        
        # Get signatures for address with retry mechanism
        response = self._retry_request(
            self.client.get_signatures_for_address,
            address_pubkey,
            limit=1000
        )
        
        if not response or not response.value:
            print("No transactions found")
            return self._create_transaction_result(address, transactions, days, balance_changes)
        
        for sig_info in response.value:
            # Check if within time range
            if sig_info.block_time:
                tx_time = datetime.fromtimestamp(sig_info.block_time, tz=timezone.utc)
                if tx_time < cutoff_time:
                    print(f"Reached transactions older than {days} day(s), stopping")
                    break
            
            # Skip failed transactions
            if sig_info.err:
                continue
            
            # Get transaction details with retry
            tx_response = self._retry_request(
                self.client.get_transaction,
                sig_info.signature,
                encoding="json",
                max_supported_transaction_version=0
            )
            
            if tx_response and tx_response.value:
                # Check if transaction involves Axiom programs
                if self._transaction_involves_axiom(tx_response.value):
                    tx_data = self._parse_transaction(tx_response.value, sig_info)
                    if tx_data:
                        current_tx_balance_changes = self._extract_balance_changes(tx_response.value, address)
                        tx_data['balance_changes'] = current_tx_balance_changes if current_tx_balance_changes else []
                        transactions.append(tx_data)
                        
                        print(f"Found Axiom transaction {len(transactions)}: {str(sig_info.signature)[:16]}...")
        
        return self._create_transaction_result(address, transactions, days, {}) # Pass empty dict for balance_changes
    
    
    def _extract_addresses_from_transaction(self, transaction) -> Set[str]:
        """Extract unique addresses from a transaction"""
        addresses = set()
        
        # transaction here is tx_response.value (EncodedConfirmedTransactionWithStatusMeta)
        # Path to account_keys: transaction.transaction.transaction.message.account_keys
        
        account_keys_list = []
        if hasattr(transaction, 'transaction') and \
           hasattr(transaction.transaction, 'transaction') and \
           hasattr(transaction.transaction.transaction, 'message') and \
           transaction.transaction.transaction.message and \
           hasattr(transaction.transaction.transaction.message, 'account_keys'):
            account_keys_list = transaction.transaction.transaction.message.account_keys
        elif isinstance(transaction, dict): # Fallback for dict structure
            try:
                account_keys_list = transaction['transaction']['transaction']['message']['accountKeys']
            except (KeyError, TypeError):
                pass # Could not find in dict structure

        # Find the signer (first account is usually the fee payer/signer)
        if account_keys_list:
            signer = account_keys_list[0]
            signer_address = str(signer) if not isinstance(signer, str) else signer
            
            # Exclude the program itself
            if signer_address and signer_address not in AXIOM_PROGRAM_IDS:
                addresses.add(signer_address)
        
        return addresses
    
    def _transaction_involves_axiom(self, transaction) -> bool:
        """Check if transaction involves Axiom programs"""
        # transaction here is tx_response.value (EncodedConfirmedTransactionWithStatusMeta)
        # Path to account_keys: transaction.transaction.transaction.message.account_keys
        
        account_keys_str_list = []
        if hasattr(transaction, 'transaction') and \
           hasattr(transaction.transaction, 'transaction') and \
           hasattr(transaction.transaction.transaction, 'message') and \
           transaction.transaction.transaction.message and \
           hasattr(transaction.transaction.transaction.message, 'account_keys'):
            raw_keys = transaction.transaction.transaction.message.account_keys
            account_keys_str_list = [str(key) for key in raw_keys]
        elif isinstance(transaction, dict): # Fallback for dict structure
            try:
                keys = transaction['transaction']['transaction']['message']['accountKeys']
                account_keys_str_list = [k if isinstance(k, str) else str(k) for k in keys]
            except (KeyError, TypeError):
                pass # Could not find in dict structure

        # Check if any Axiom program is in account keys
        for key_str in account_keys_str_list:
            if key_str in AXIOM_PROGRAM_IDS:
                return True
        
        return False
    
    def _parse_transaction(self, transaction, sig_info: Any) -> Optional[Dict[str, Any]]:
        """Parse transaction data into the expected format"""
        # transaction here is tx_response.value (EncodedConfirmedTransactionWithStatusMeta)
        
        signature = str(sig_info.signature)
        block = sig_info.slot if sig_info.slot else getattr(transaction, 'slot', 0)
        
        block_time_val = getattr(transaction, 'block_time', None) or getattr(transaction, 'blockTime', None)
        
        if block_time_val:
            tx_time = datetime.fromtimestamp(block_time_val, tz=timezone.utc)
            time_text = self._format_time_ago(tx_time)
            timestamp = tx_time.isoformat()
        else:
            time_text = "Unknown"
            timestamp = None
        
        instructions_list = self._extract_instructions(transaction)
        by_address_str = self._extract_signer(transaction)
        
        fee_lamports = 0
        if hasattr(transaction, 'transaction') and \
           hasattr(transaction.transaction, 'meta') and \
           transaction.transaction.meta:
            fee_lamports = getattr(transaction.transaction.meta, 'fee', 0)
        elif isinstance(transaction, dict): # Fallback
            try:
                fee_lamports = transaction['transaction']['meta']['fee']
            except (KeyError, TypeError):
                pass
        fee_sol = fee_lamports / 1e9
        
        value_sol = self._extract_transaction_value(transaction)
        
        return {
            'signature': signature,
            'block': str(block),
            'time': time_text,
            'timestamp': timestamp,
            'instructions': instructions_list,
            'by': by_address_str,
            'value': f"{value_sol:.6f}" if value_sol else "0",
            'fee': f"{fee_sol:.6f}",
            'page': 1
        }
    
    def _extract_instructions(self, transaction) -> List[str]:
        """Extract instruction types from transaction"""
        # transaction here is tx_response.value (EncodedConfirmedTransactionWithStatusMeta)
        extracted_instructions = []
        
        log_messages_list = []
        # Path to log_messages: transaction.transaction.meta.log_messages
        if hasattr(transaction, 'transaction') and \
           hasattr(transaction.transaction, 'meta') and \
           transaction.transaction.meta:
            meta_obj = transaction.transaction.meta
            log_messages_list = getattr(meta_obj, 'log_messages', []) or getattr(meta_obj, 'logMessages', []) or []
        elif isinstance(transaction, dict): # Fallback
            try:
                log_messages_list = transaction['transaction']['meta'].get('logMessages', []) or []
            except (KeyError, TypeError):
                pass

        found_buy = False
        found_sell = False
        
        for log in log_messages_list:
            log_lower = str(log).lower() # Ensure log is string before lower()
            if 'instruction: buy' in log_lower and not found_buy:
                extracted_instructions.append('buy')
                found_buy = True
            elif 'instruction: sell' in log_lower and not found_sell:
                extracted_instructions.append('sell') 
                found_sell = True
            elif 'swap' in log_lower: # Consider adding a flag to avoid multiple 'swap' if it appears many times
                if 'swap' not in extracted_instructions: # Add only once
                    extracted_instructions.append('swap')
        
        if not extracted_instructions:
            instruction_count = 0
            # Path to instructions list: transaction.transaction.transaction.message.instructions
            if hasattr(transaction, 'transaction') and \
               hasattr(transaction.transaction, 'transaction') and \
               hasattr(transaction.transaction.transaction, 'message') and \
               transaction.transaction.transaction.message and \
               hasattr(transaction.transaction.transaction.message, 'instructions'):
                message_instructions = transaction.transaction.transaction.message.instructions
                instruction_count = len(message_instructions or [])
            elif isinstance(transaction, dict): # Fallback
                try:
                    message_instructions = transaction['transaction']['transaction']['message']['instructions']
                    instruction_count = len(message_instructions or [])
                except (KeyError, TypeError):
                    pass
            
            if instruction_count > 1:
                extracted_instructions.append(f"{instruction_count}+")
        
        return extracted_instructions if extracted_instructions else ['Unknown']
    
    def _extract_signer(self, transaction) -> str:
        """Extract signer address from transaction"""
        # transaction here is tx_response.value (EncodedConfirmedTransactionWithStatusMeta)
        # Path to account_keys: transaction.transaction.transaction.message.account_keys
        
        account_keys_list = []
        if hasattr(transaction, 'transaction') and \
           hasattr(transaction.transaction, 'transaction') and \
           hasattr(transaction.transaction.transaction, 'message') and \
           transaction.transaction.transaction.message and \
           hasattr(transaction.transaction.transaction.message, 'account_keys'):
            account_keys_list = transaction.transaction.transaction.message.account_keys
        elif isinstance(transaction, dict): # Fallback for dict structure
            try:
                account_keys_list = transaction['transaction']['transaction']['message']['accountKeys']
            except (KeyError, TypeError):
                pass

        if account_keys_list:
            signer = account_keys_list[0]
            return str(signer) if not isinstance(signer, str) else signer
        
        return ""
    
    def _extract_transaction_value(self, transaction) -> float:
        """Extract transaction value from pre/post balances"""
        # transaction here is tx_response.value (EncodedConfirmedTransactionWithStatusMeta)
        pre_sols = []
        post_sols = []
        
        # Path to balances: transaction.transaction.meta
        if hasattr(transaction, 'transaction') and \
           hasattr(transaction.transaction, 'meta') and \
           transaction.transaction.meta:
            meta_obj = transaction.transaction.meta
            pre_sols = getattr(meta_obj, 'pre_balances', []) or getattr(meta_obj, 'preBalances', [])
            post_sols = getattr(meta_obj, 'post_balances', []) or getattr(meta_obj, 'postBalances', [])
        elif isinstance(transaction, dict): # Fallback
            try:
                meta_dict = transaction['transaction']['meta']
                pre_sols = meta_dict.get('preBalances', [])
                post_sols = meta_dict.get('postBalances', [])
            except (KeyError, TypeError):
                pass
        
        if pre_sols and post_sols:
            max_change = 0
            for i in range(min(len(pre_sols), len(post_sols))):
                try:
                    # Ensure balances are numbers before subtraction
                    pre_bal = int(pre_sols[i])
                    post_bal = int(post_sols[i])
                    change = abs(post_bal - pre_bal) / 1e9 # Convert lamports to SOL
                    if change > max_change:
                        max_change = change
                except (ValueError, TypeError):
                    print(f"Warning: Could not parse pre/post SOL balance at index {i}")
                    continue # Skip if conversion fails
            return max_change
        
        return 0.0
    
    def _extract_balance_changes(self, transaction, address: str) -> List[Dict[str, Any]]:
        """Extract balance changes for a specific address from transaction"""
        # transaction here is tx_response.value (EncodedConfirmedTransactionWithStatusMeta)
        changes = []
        
        meta_data_obj = None
        ui_tx_obj = None
        account_keys_str_list = []
        raw_sigs = []

        # Object path (primary)
        if hasattr(transaction, 'transaction'):
            encoded_tx_meta_obj = transaction.transaction # This is EncodedTransactionWithStatusMeta
            if hasattr(encoded_tx_meta_obj, 'meta') and encoded_tx_meta_obj.meta:
                meta_data_obj = encoded_tx_meta_obj.meta
            
            if hasattr(encoded_tx_meta_obj, 'transaction') and encoded_tx_meta_obj.transaction:
                ui_tx_obj = encoded_tx_meta_obj.transaction # This is UiTransaction
                if hasattr(ui_tx_obj, 'message') and ui_tx_obj.message and \
                   hasattr(ui_tx_obj.message, 'account_keys'):
                    account_keys_str_list = [str(key) for key in ui_tx_obj.message.account_keys]
                
                if hasattr(ui_tx_obj, 'signatures'):
                    raw_sigs = ui_tx_obj.signatures
        # Fallback for dictionary structure (less likely for this specific response but good for robustness)
        elif isinstance(transaction, dict):
            try:
                meta_data_obj = transaction['transaction']['meta']
                ui_tx_obj = transaction['transaction']['transaction']
                account_keys_str_list = [str(k) for k in ui_tx_obj['message']['accountKeys']]
                raw_sigs = ui_tx_obj['signatures']
            except (KeyError, TypeError):
                meta_data_obj, ui_tx_obj = None, None # Ensure they are None if dict path fails

        pre_token_bals = []
        post_token_bals = []
        pre_sol_bals = []
        post_sol_bals = []

        if meta_data_obj:
            # Correctly fetch pre_token_balances, trying snake_case then camelCase
            _ptb_snake = getattr(meta_data_obj, 'pre_token_balances', None)
            _ptb_camel = getattr(meta_data_obj, 'preTokenBalances', None)
            pre_token_bals = _ptb_snake if _ptb_snake is not None else (_ptb_camel if _ptb_camel is not None else [])

            # Correctly fetch post_token_balances
            _post_ptb_snake = getattr(meta_data_obj, 'post_token_balances', None)
            _post_ptb_camel = getattr(meta_data_obj, 'postTokenBalances', None)
            post_token_bals = _post_ptb_snake if _post_ptb_snake is not None else (_post_ptb_camel if _post_ptb_camel is not None else [])
            
            # Correctly fetch pre_balances (SOL)
            _pb_snake = getattr(meta_data_obj, 'pre_balances', None)
            _pb_camel = getattr(meta_data_obj, 'preBalances', None)
            pre_sol_bals = _pb_snake if _pb_snake is not None else (_pb_camel if _pb_camel is not None else [])

            # Correctly fetch post_balances (SOL)
            _post_pb_snake = getattr(meta_data_obj, 'post_balances', None)
            _post_pb_camel = getattr(meta_data_obj, 'postBalances', None)
            post_sol_bals = _post_pb_snake if _post_pb_snake is not None else (_post_pb_camel if _post_pb_camel is not None else [])


        block_time_val = getattr(transaction, 'block_time', None) or getattr(transaction, 'blockTime', None)
        slot_val = getattr(transaction, 'slot', 0)
        
        signature_val_str = ""
        if raw_sigs:
            sig_obj = raw_sigs[0]
            signature_val_str = str(sig_obj) if hasattr(sig_obj, '__str__') else sig_obj # Ensure string

        address_idx = -1
        for i, key_str in enumerate(account_keys_str_list):
            if key_str == address:
                address_idx = i
                break
        
        time_text_val = "Unknown"
        if block_time_val:
            tx_time_obj = datetime.fromtimestamp(block_time_val, tz=timezone.utc)
            time_text_val = self._format_time_ago(tx_time_obj)
        
        token_bal_changes = {}
        
        for bal_item in pre_token_bals:
            item_dict = {}
            if isinstance(bal_item, dict): # if it's a dict (e.g. from JSON)
                item_dict = {
                    'accountIndex': bal_item.get('accountIndex', -1),
                    'owner': str(bal_item.get('owner', '')),
                    'mint': str(bal_item.get('mint', '')),
                    'uiAmountString': str(bal_item.get('uiTokenAmount', {}).get('uiAmountString', '0'))
                }
            else: # if it's an object (e.g. UiTokenBalance)
                 item_dict = {
                    'accountIndex': getattr(bal_item, 'account_index', -1),
                    'owner': str(getattr(bal_item, 'owner', '')),
                    'mint': str(getattr(bal_item, 'mint', '')),
                    'uiAmountString': str(getattr(getattr(bal_item, 'ui_token_amount', None) or getattr(bal_item, 'uiTokenAmount', None) or {}, 'ui_amount_string', '0')) # handles ui_token_amount or uiTokenAmount
                }

            if item_dict.get('accountIndex') == address_idx or item_dict.get('owner') == address:
                mint_addr = item_dict.get('mint', '')
                try:
                    amount_val = float(item_dict.get('uiAmountString', '0'))
                except ValueError:
                    amount_val = 0.0 # Default to 0 if conversion fails
                token_bal_changes[mint_addr] = {'pre': amount_val, 'post': 0, 'mint': mint_addr}
        
        for bal_item in post_token_bals:
            item_dict = {}
            if isinstance(bal_item, dict):
                item_dict = {
                    'accountIndex': bal_item.get('accountIndex', -1),
                    'owner': str(bal_item.get('owner', '')),
                    'mint': str(bal_item.get('mint', '')),
                    'uiAmountString': str(bal_item.get('uiTokenAmount', {}).get('uiAmountString', '0'))
                }
            else: # Object
                 item_dict = {
                    'accountIndex': getattr(bal_item, 'account_index', -1),
                    'owner': str(getattr(bal_item, 'owner', '')),
                    'mint': str(getattr(bal_item, 'mint', '')),
                    'uiAmountString': str(getattr(getattr(bal_item, 'ui_token_amount', None) or getattr(bal_item, 'uiTokenAmount', None) or {}, 'ui_amount_string', '0'))
                }

            if item_dict.get('accountIndex') == address_idx or item_dict.get('owner') == address:
                mint_addr = item_dict.get('mint', '')
                try:
                    amount_val = float(item_dict.get('uiAmountString', '0'))
                except ValueError:
                    amount_val = 0.0

                if mint_addr in token_bal_changes:
                    token_bal_changes[mint_addr]['post'] = amount_val
                else:
                    token_bal_changes[mint_addr] = {'pre': 0, 'post': amount_val, 'mint': mint_addr}
        
        for mint_addr, bals in token_bal_changes.items():
            change_val = bals['post'] - bals['pre']
            if change_val != 0:
                token_name_str = self._get_token_name(mint_addr)
                changes.append({
                    'signature': signature_val_str,
                    'block': str(slot_val),
                    'time': time_text_val,
                    'amount': f"{change_val:+,.6f}".replace('+', '+' if change_val > 0 else ''), # keep + for positive
                    'post_balance': f"{bals['post']:,.6f}",
                    'token_name': token_name_str,
                    'token_address': mint_addr
                })
        
        if address_idx >= 0 and address_idx < len(pre_sol_bals) and address_idx < len(post_sol_bals):
            try:
                pre_sol_val = int(pre_sol_bals[address_idx]) / 1e9
                post_sol_val = int(post_sol_bals[address_idx]) / 1e9
                sol_change_val = post_sol_val - pre_sol_val
                
                if sol_change_val != 0:
                    changes.append({
                        'signature': signature_val_str,
                        'block': str(slot_val),
                        'time': time_text_val,
                        'amount': f"{sol_change_val:+,.9f}".replace('+', '+' if sol_change_val > 0 else ''),
                        'post_balance': f"{post_sol_val:,.9f}",
                        'token_name': 'SOL',
                        'token_address': 'So11111111111111111111111111111111111111111'
                    })
            except (ValueError, TypeError):
                print(f"Warning: Could not parse SOL balance for address {address} at index {address_idx}")

        return changes
    
    def _format_time_ago(self, dt: datetime) -> str:
        """Format datetime as relative time (e.g., '2 hours ago')"""
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hr{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} min{'s' if minutes > 1 else ''} ago"
        else:
            return "just now"
    
    def _get_token_name(self, mint: str) -> str:
        """Get token name from mint address"""
        try:
            # Get metadata account address
            metadata_account = self._get_metadata_account(mint)
            
            # Fetch metadata account data
            response = self._retry_request(
                self.client.get_account_info,
                Pubkey.from_string(metadata_account)
            )
            
            if response and response.value and response.value.data:
                # Decode the metadata
                metadata = self._decode_metadata(bytes(response.value.data))
                
                # Return symbol if available, otherwise name
                if metadata and metadata.get('data'):
                    token_data = metadata['data']
                    if token_data.get('symbol'):
                        return token_data['symbol'].strip()
                    elif token_data.get('name'):
                        return token_data['name'].strip()
            
        except Exception as e:
            print(f"Error fetching token metadata for {mint}: {e}")
        
        return "Unknown Token"
    
    def _get_metadata_account(self, mint: str) -> str:
        """
        Get the metadata account address for a token mint
        Uses PDA derivation: ["metadata", METADATA_PROGRAM_ID, mint]
        """
        mint_pubkey = Pubkey.from_string(mint)
        metadata_program_pubkey = Pubkey.from_string(METADATA_PROGRAM_ID)
        
        # Derive PDA
        pda, _ = Pubkey.find_program_address(
            [
                b"metadata",
                bytes(metadata_program_pubkey),
                bytes(mint_pubkey)
            ],
            metadata_program_pubkey
        )
        
        return str(pda)
    
    def _decode_metadata(self, data: bytes) -> Optional[Dict[str, Any]]:
        """
        Decode Metaplex metadata from account data
        Based on Metaplex metadata structure
        """
        try:
            # Check if this is metadata account (key = 4)
            if len(data) < 1 or data[0] != 4:
                return None
            
            i = 1
            
            # Skip update_authority (32 bytes)
            i += 32
            
            # Skip mint (32 bytes)
            i += 32
            
            # Read name
            name_len = struct.unpack('<I', data[i:i+4])[0]
            i += 4
            name = data[i:i+name_len].decode('utf-8', errors='ignore')
            i += name_len
            
            # Read symbol
            symbol_len = struct.unpack('<I', data[i:i+4])[0]
            i += 4
            symbol = data[i:i+symbol_len].decode('utf-8', errors='ignore')
            i += symbol_len
            
            # Read URI
            uri_len = struct.unpack('<I', data[i:i+4])[0]
            i += 4
            uri = data[i:i+uri_len].decode('utf-8', errors='ignore')
            i += uri_len
            
            return {
                'data': {
                    'name': name.rstrip('\x00'),
                    'symbol': symbol.rstrip('\x00'),
                    'uri': uri.rstrip('\x00')
                }
            }
            
        except Exception as e:
            print(f"Error decoding metadata: {e}")
            return None
    
    def _create_transaction_result(self, address: str, transactions: List[Dict], days: int, balance_changes: Dict[str, List[Dict[str, Any]]] = None, error: Optional[str] = None) -> Dict[str, Any]:
        """Create standardized transaction result"""
        result = {
            'address_id': address,
            'transactions': transactions,
            'balance_changes': balance_changes or {},
            'total_found': len(transactions),
            'days_scraped': days,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if error:
            result['error'] = error
            
        return result 