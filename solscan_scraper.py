from selenium_manager import SeleniumManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
import re
from datetime import datetime, timedelta, timezone
from typing import List, Set, Dict, Any

AXIOM_PROGRAM_ID = ["AxiomfHaWDemCFBLBayqnEnNwE6b7B2Qz3UmzMpgbMG6", "AxiomxSitiyXyPjKgJ9XSrdhsydtZsskZTEDam3PxKcC"]

def extract_table_data_task(driver, program_id: str, max_addresses: int = 10):
    """
    Task function to extract transaction data from Solscan account page
    """
    url = f"https://solscan.io/account/{program_id}"
    
    # Navigate to URL
    driver.get(url)
    
    # Wait for page to load
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    
    # Additional wait for dynamic content
    time.sleep(5)
    
    unique_addresses = set()
    page_count = 0
    max_pages = 50  # Safety limit
    
    print(f"Starting to scrape transaction data for program: {program_id}")
    print(f"Target: {max_addresses} unique addresses")
    
    while len(unique_addresses) < max_addresses and page_count < max_pages:
        page_count += 1
        print(f"\n=== Processing page {page_count} ===")
        
        # Wait for table to load
        time.sleep(3)
        
        try:
            # Find the transaction table
            table_selector = "table.w-full.border-separate.caption-bottom.border-spacing-0"
            table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, table_selector)))
            print("Found transaction table")
            
            # Find all rows in the table body
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            print(f"Found {len(rows)} transaction rows")
            
            for i, row in enumerate(rows):
                try:
                    # Extract "By" column (6th column - index 5)
                    by_cell = row.find_elements(By.CSS_SELECTOR, "td")[5]
                    by_link = by_cell.find_element(By.CSS_SELECTOR, "a")
                    by_address = by_link.get_attribute("href").split("/account/")[-1]
                    
                    # Extract "Programs" column (9th column - index 8)
                    programs_cell = row.find_elements(By.CSS_SELECTOR, "td")[8]
                    
                    # Check if this row contains the Axiom program
                    axiom_found = False
                    program_links = programs_cell.find_elements(By.CSS_SELECTOR, "a")
                    
                    for link in program_links:
                        href = link.get_attribute("href")
                        if any(program_id in href for program_id in AXIOM_PROGRAM_ID):
                            axiom_found = True
                            break

                    if axiom_found and by_address not in unique_addresses:
                        unique_addresses.add(by_address)
                        print(f"  Found address {len(unique_addresses)}: {by_address}")
                        
                        if len(unique_addresses) >= max_addresses:
                            print(f"Reached target of {max_addresses} addresses!")
                            break
                            
                except Exception as e:
                    print(f"  Error processing row {i}: {str(e)}")
                    continue
            
            # If we need more addresses, try to go to next page
            if len(unique_addresses) < max_addresses:
                try:
                    # Find and click next page button
                    next_button_selector = "#radix-\\:r1s\\:-content-transactions > div > div > div > div.px-4.pb-4.pt-4.bg-neutral0.border-t.border-border > div > div:nth-child(2) > button:nth-child(3)"
                    next_button = driver.find_element(By.CSS_SELECTOR, next_button_selector)
                    
                    if next_button.is_enabled():
                        print("Clicking next page button...")
                        driver.execute_script("arguments[0].click();", next_button)
                        time.sleep(3)  # Wait for page transition
                    else:
                        print("Next button is disabled - reached last page")
                        break
                        
                except NoSuchElementException:
                    print("Next page button not found - might be on last page")
                    break
                except Exception as e:
                    print(f"Error clicking next page: {str(e)}")
                    break
            
        except TimeoutException:
            print("Timeout waiting for table to load")
            break
        except Exception as e:
            print(f"Error processing page {page_count}: {str(e)}")
            break
    
    result = {
        'program_id': program_id,
        'unique_addresses': list(unique_addresses),
        'total_found': len(unique_addresses),
        'pages_processed': page_count,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'target_count': max_addresses
    }
    
    print(f"\n=== Scraping Complete ===")
    print(f"Total unique addresses found: {len(unique_addresses)}")
    print(f"Pages processed: {page_count}")
    
    return result

def scrape_solscan_account(program_id: str, max_addresses: int = 10):
    """
    Scrapes the Solscan account page for transaction data using SeleniumManager
    
    Args:
        program_id (str): The Solana program ID to scrape
        max_addresses (int): Maximum number of unique addresses to collect (default: 10)
    
    Returns:
        dict: Results containing unique addresses and metadata
    """
    print(f"Starting Solscan scraping for program: {program_id}")
    print(f"Target addresses: {max_addresses}")
    
    # Create and start SeleniumManager
    manager = SeleniumManager()
    
    try:
        with manager:
            # Execute the extraction task
            result = manager.execute_task(
                extract_table_data_task, 
                program_id, 
                max_addresses,
                timeout=600  # 10 minutes timeout
            )
            
            # Save results to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"solscan_addresses_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Solscan Address Extraction Results\n")
                f.write(f"Program ID: {result['program_id']}\n")
                f.write(f"Scraped at: {result['timestamp']}\n")
                f.write(f"Target count: {result['target_count']}\n")
                f.write(f"Total found: {result['total_found']}\n")
                f.write(f"Pages processed: {result['pages_processed']}\n")
                f.write("=" * 50 + "\n\n")
                
                f.write("Unique Addresses:\n")
                for i, address in enumerate(result['unique_addresses'], 1):
                    f.write(f"{i:3d}. {address}\n")
            
            print(f"Results saved to: {filename}")
            return result
            
    except Exception as e:
        print(f"Error during scraping: {e}")
        return None

def extract_address_transactions_task(driver, address_id: str, days: int = 1):
    """
    Task function to extract transaction data from a specific address with Axiom trades
    
    Args:
        driver: Selenium WebDriver instance
        address_id (str): The Solana address to scrape
        days (int): Number of days to scrape (default: 1)
    
    Returns:
        dict: Results containing transactions and metadata
    """
    url = f"https://solscan.io/account/{address_id}"
    
    # Navigate to URL
    driver.get(url)
    
    # Wait for page to load
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    
    # Additional wait for dynamic content
    time.sleep(5)
    
    # Calculate cutoff time for filtering
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
    
    transactions = []
    page_count = 0
    max_pages = 1  # Safety limit
    
    print(f"Starting to scrape transactions for address: {address_id}")
    print(f"Looking for transactions from last {days} day(s)")
    print(f"Current time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Cutoff time (UTC): {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    while page_count < max_pages:
        page_count += 1
        print(f"\n=== Processing page {page_count} ===")
        
        # Wait for table to load
        time.sleep(3)
        
        try:
            # Find the transaction table
            table_selector = "table.w-full.border-separate.caption-bottom.border-spacing-0"
            table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, table_selector)))
            print("Found transaction table")
            
            # Find all rows in the table body
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            print(f"Found {len(rows)} transaction rows")
            
            should_continue = False
            
            for i, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.CSS_SELECTOR, "td")
                    if len(cells) < 9:
                        continue
                    
                    # Extract signature (column 1 - index 1)
                    signature_cell = cells[1]
                    signature_link = signature_cell.find_element(By.CSS_SELECTOR, "a")
                    signature = signature_link.get_attribute("href").split("/tx/")[-1]
                    
                    # Extract block (column 2 - index 2)
                    block_cell = cells[2]
                    block_link = block_cell.find_element(By.CSS_SELECTOR, "a")
                    block_number = block_link.text.strip()
                    
                    # Extract time (column 3 - index 3)
                    time_text = cells[3].text.strip()
                    
                    # Parse time to check if within our date range
                    transaction_time = parse_time_text(time_text)
                    
                    if transaction_time and transaction_time < cutoff_time:
                        print(f"  Transaction too old ('{time_text}' = {transaction_time.strftime('%Y-%m-%d %H:%M:%S')}), stopping scrape")
                        # Set flag to stop pagination
                        should_continue = False
                        break
                    
                    # Extract instructions (column 4 - index 4)
                    instructions_text = cells[4].text.strip()
                    instructions = [inst.strip() for inst in instructions_text.split('\n') if inst.strip() and inst.strip() != '+']
                    
                    # Extract "By" column (column 5 - index 5)
                    by_text = extract_full_address_from_by_field(cells[5])
                    
                    # Extract Value (column 6 - index 6)
                    value_text = cells[6].text.strip()
                    
                    # Extract Fee (column 7 - index 7)
                    fee_text = cells[7].text.strip()
                    
                    # Extract Programs (column 8 - index 8)
                    programs_cell = cells[8]
                    
                    # Check if this row contains the Axiom program
                    axiom_found = False
                    program_links = programs_cell.find_elements(By.CSS_SELECTOR, "a")
                    
                    for link in program_links:
                        href = link.get_attribute("href")
                        if "AxiomfHaWDemCFBLBayqnEnNwE6b7B2Qz3UmzMpgbMG6" in href:
                            axiom_found = True
                            break
                    
                    # Check if transaction failed (look for failure indicators)
                    is_failed = check_transaction_failed(row)
                    
                    if axiom_found and not is_failed:
                        transaction_data = {
                            'signature': signature,
                            'block': block_number,
                            'time': time_text,
                            'timestamp': transaction_time.isoformat() if transaction_time else None,
                            'instructions': instructions,
                            'by': by_text,
                            'value': value_text,
                            'fee': fee_text,
                            'page': page_count
                        }
                        
                        transactions.append(transaction_data)
                        print(f"  Found Axiom transaction {len(transactions)}: {signature[:16]}... (Value: {value_text} SOL)")
                    
                    should_continue = True
                        
                except Exception as e:
                    print(f"  Error processing row {i}: {str(e)}")
                    continue
            
            # If we found transactions on this page within time range, continue
            if not should_continue and transactions:
                print("No more relevant transactions found within time range, stopping pagination")
                break
            
            # Try to go to next page
            try:
                # Try multiple possible selectors for next button
                next_button_selectors = [
                    # New button format with chevron-right
                    "button:has(svg.lucide-chevron-right)",
                    "button[class*='chevron-right']", 
                    "button svg.lucide-chevron-right",
                    # Generic next button patterns
                    "button:contains('Next')",
                    "button[aria-label*='Next']",
                    "button[title*='Next']",
                ]
                
                next_button = None
                for selector in next_button_selectors:
                    try:
                        if "contains" in selector:
                            # Use XPath for text-based selection
                            xpath_selector = f"//button[contains(text(), 'Next')]"
                            next_button = driver.find_element(By.XPATH, xpath_selector)
                        elif "has" in selector:
                            # Use JavaScript to find button with chevron-right
                            next_button = driver.execute_script("""
                                return Array.from(document.querySelectorAll('button')).find(btn => 
                                    btn.querySelector('svg.lucide-chevron-right')
                                );
                            """)
                        else:
                            next_button = driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if next_button:
                            break
                    except:
                        continue
                
                if next_button and next_button.is_enabled() and not next_button.get_attribute("disabled"):
                    print("Clicking next page button...")
                    driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(3)  # Wait for page transition
                else:
                    print("Next button is disabled or not found - reached last page")
                    break
                    
            except Exception as e:
                print(f"Error with pagination: {str(e)}")
                break
            
        except TimeoutException:
            print("Timeout waiting for table to load")
            break
        except Exception as e:
            print(f"Error processing page {page_count}: {str(e)}")
            break
    
    result = {
        'address_id': address_id,
        'transactions': transactions,
        'total_found': len(transactions),
        'pages_processed': page_count,
        'days_scraped': days,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    print(f"\n=== Transaction Scraping Complete ===")
    print(f"Total Axiom transactions found: {len(transactions)}")
    print(f"Pages processed: {page_count}")
    
    return result

def extract_balance_changes_task(driver, address_id: str, signatures: List[str]):
    """
    Task function to extract balance changes for specific signatures
    
    Args:
        driver: Selenium WebDriver instance
        address_id (str): The Solana address
        signatures (List[str]): List of transaction signatures to lookup
    
    Returns:
        dict: Balance changes data mapped by signature
    """
    # Navigate to base URL first
    url = f"https://solscan.io/account/{address_id}?page=1#balanceChanges"
    driver.get(url)
    
    # Wait for page to load
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    
    # Additional wait for dynamic content
    time.sleep(3)
    
    balance_changes = {}
    page_count = 0
    max_pages = 50  # Safety limit
    
    print(f"Starting to scrape balance changes for address: {address_id}")
    print(f"Looking for {len(signatures)} specific signatures")
    
    signature_set = set(signatures)
    found_signatures = set()
    
    while page_count < max_pages and len(found_signatures) < len(signatures):
        page_count += 1
        print(f"\n=== Processing balance changes page {page_count} ===")
        
        # Wait for table to load
        time.sleep(3)
        
        try:
            # Find the balance changes table
            table_selector = "table.w-full.border-separate.caption-bottom.border-spacing-0"
            table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, table_selector)))
            print("Found balance changes table")
            
            # Find all rows in the table body
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            print(f"Found {len(rows)} balance change rows")
            
            found_on_page = False
            
            for i, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.CSS_SELECTOR, "td")

                    # Extract signature (column 1 - index 1)
                    signature_cell = cells[1]
                    signature_link = signature_cell.find_element(By.CSS_SELECTOR, "a")
                    signature = signature_link.get_attribute("href").split("/tx/")[-1]
                    
                    if signature in signature_set:
                        # Extract block (column 2 - index 2)
                        block_number = cells[2].text.strip()
                        
                        # Extract time (column 3 - index 3)
                        time_text = cells[3].text.strip()
                        
                        # Extract amount (column 4 - index 4)
                        amount_text = cells[4].text.strip()
                        
                        # Extract post balance (column 5 - index 5)
                        post_balance_text = cells[5].text.strip()
                        
                        # Extract token info (column 6 - index 6)
                        token_cell = cells[6]
                        try:
                            # Extract token name from the text content of the link
                            token_link = token_cell.find_element(By.CSS_SELECTOR, "a.text-current")
                            token_name = token_link.text.strip()
                            token_address = token_link.get_attribute("href").split("/token/")[-1]
                        except:
                            token_name = ""
                            token_address = ""
                        
                        if not token_name:
                            print(f"  ERROR: Could not extract token name from row {i}")
                            print(f"  Token cell HTML: {token_cell.get_attribute('innerHTML')}")
                            continue  # Skip this row if no token found
                        
                        balance_change_data = {
                            'signature': signature,
                            'block': block_number,
                            'time': time_text,
                            'amount': amount_text,
                            'post_balance': post_balance_text,
                            'token_name': token_name,
                            'token_address': token_address
                        }
                        
                        if signature not in balance_changes:
                            balance_changes[signature] = []
                        balance_changes[signature].append(balance_change_data)
                        
                        # Track that we found this signature (but don't prevent finding more balance changes for it)
                        found_signatures.add(signature)
                        found_on_page = True
                        print(f"  Found balance change for {signature[:16]}... ({token_name}: {amount_text})")
                        
                except Exception as e:
                    print(f"  Error processing balance change row {i}: {str(e)}")
                    # Debug: print row HTML structure if error occurs
                    try:
                        print(f"  Row {i} cell count: {len(cells)}")
                        if len(cells) >= 7:
                            print(f"  Amount cell HTML: {cells[4].get_attribute('innerHTML')[:200]}...")
                            print(f"  Token cell HTML: {cells[6].get_attribute('innerHTML')[:200]}...")
                    except:
                        pass
                    continue
            
            if not found_on_page:
                print("No relevant balance changes found on this page")
            
            # Try to go to next page - updated selectors
            try:
                # Try multiple possible selectors for next button
                next_button_selectors = [
                    # New button format with chevron-right
                    "button:has(svg.lucide-chevron-right)",
                    "button[class*='chevron-right']",
                    "button svg.lucide-chevron-right",
                    # Generic next button patterns
                    "button:contains('Next')",
                    "button[aria-label*='Next']",
                    "button[title*='Next']",
                ]
                
                next_button = None
                for selector in next_button_selectors:
                    try:
                        if "contains" in selector:
                            # Use XPath for text-based selection
                            xpath_selector = f"//button[contains(text(), 'Next')]"
                            next_button = driver.find_element(By.XPATH, xpath_selector)
                        elif "has" in selector:
                            # Use JavaScript to find button with chevron-right
                            next_button = driver.execute_script("""
                                return Array.from(document.querySelectorAll('button')).find(btn => 
                                    btn.querySelector('svg.lucide-chevron-right')
                                );
                            """)
                        else:
                            next_button = driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if next_button:
                            break
                    except:
                        continue
                
                if next_button and next_button.is_enabled() and not next_button.get_attribute("disabled"):
                    print("Clicking next page button...")
                    driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(3)  # Wait for page transition
                else:
                    print("Next button is disabled or not found - reached last page")
                    break
                    
            except Exception as e:
                print(f"Error with pagination: {str(e)}")
                break
            
        except TimeoutException:
            print("Timeout waiting for balance changes table to load")
            break
        except Exception as e:
            print(f"Error processing balance changes page {page_count}: {str(e)}")
            break
    
    result = {
        'address_id': address_id,
        'balance_changes': balance_changes,
        'signatures_found': len(found_signatures),
        'signatures_total': len(signatures),
        'pages_processed': page_count,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    print(f"\n=== Balance Changes Scraping Complete ===")
    print(f"Found balance changes for {len(found_signatures)}/{len(signatures)} signatures")
    print(f"Pages processed: {page_count}")
    
    return result

def parse_time_text(time_text: str) -> datetime:
    """
    Parse time text like "1 min ago", "2 hours ago", etc. to datetime
    Handles various formats including "Dec 21, 2023 5:30 PM"
    """
    try:
        time_text = time_text.strip()
        now = datetime.now(timezone.utc)
        
        # First try to parse relative time (X ago)
        if 'ago' in time_text.lower():
            time_text_lower = time_text.lower()
            
            if 'just now' in time_text_lower:
                return now
            elif 'sec' in time_text_lower or 'second' in time_text_lower:
                seconds = int(re.findall(r'\d+', time_text)[0])
                return now - timedelta(seconds=seconds)
            elif 'min' in time_text_lower or 'minute' in time_text_lower:
                minutes = int(re.findall(r'\d+', time_text)[0])
                return now - timedelta(minutes=minutes)
            elif 'hr' in time_text_lower:
                hours = int(re.findall(r'\d+', time_text)[0])
                return now - timedelta(hours=hours)
            elif 'day' in time_text_lower:
                days = int(re.findall(r'\d+', time_text)[0])
                return now - timedelta(days=days)
            elif 'week' in time_text_lower:
                weeks = int(re.findall(r'\d+', time_text)[0])
                return now - timedelta(weeks=weeks)
            elif 'month' in time_text_lower:
                months = int(re.findall(r'\d+', time_text)[0])
                return now - timedelta(days=months*30)  # Approximate
            elif 'year' in time_text_lower:
                years = int(re.findall(r'\d+', time_text)[0])
                return now - timedelta(days=years*365)  # Approximate
        
        # Try to parse absolute date/time formats
        # Common formats from Solscan: "Dec 21, 2023 5:30 PM", "2023-12-21 17:30:00"
        date_formats = [
            "%b %d, %Y %I:%M %p",  # Dec 21, 2023 5:30 PM
            "%B %d, %Y %I:%M %p",  # December 21, 2023 5:30 PM
            "%Y-%m-%d %H:%M:%S",   # 2023-12-21 17:30:00
            "%Y-%m-%d %H:%M",      # 2023-12-21 17:30
            "%d/%m/%Y %H:%M:%S",   # 21/12/2023 17:30:00
            "%m/%d/%Y %H:%M:%S",   # 12/21/2023 17:30:00
        ]
        
        for fmt in date_formats:
            try:
                # Parse and assume UTC timezone
                parsed_time = datetime.strptime(time_text, fmt)
                return parsed_time.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        
        # If can't parse, assume it's recent
        print(f"Warning: Could not parse time text '{time_text}', assuming recent")
        return now
        
    except Exception as e:
        print(f"Error parsing time '{time_text}': {e}")
        return datetime.now(timezone.utc)

def check_transaction_failed(row_element):
    """
    Check if a transaction row indicates a failed transaction
    """
    try:
        # Look for failure indicators in the row
        row_html = row_element.get_attribute('outerHTML').lower()
        
        # Common failure indicators
        failure_indicators = ['failed', 'error', 'fail', 'cancelled']
        
        for indicator in failure_indicators:
            if indicator in row_html:
                return True
                
        return False
    except:
        return False

def scrape_address_transactions(address_id: str, days: int = 1):
    """
    Scrapes transaction and balance change data from a specific Solana address
    
    Args:
        address_id (str): The Solana address to scrape
        days (int): Number of days to scrape (default: 1)
    
    Returns:
        dict: Complete trading history with transactions and balance changes
    """
    print(f"Starting comprehensive scraping for address: {address_id}")
    print(f"Scraping last {days} day(s)")
    
    # Create and start SeleniumManager
    manager = SeleniumManager()
    
    try:
        with manager:
            # Step 1: Extract transactions
            print("\n" + "="*50)
            print("STEP 1: Extracting Axiom transactions")
            print("="*50)
            
            transactions_result = manager.execute_task(
                extract_address_transactions_task,
                address_id,
                days,
                timeout=600  # 10 minutes timeout
            )
            
            if not transactions_result or not transactions_result['transactions']:
                print("No Axiom transactions found for this address")
                return None
            
            # Step 2: Extract balance changes for found signatures
            print("\n" + "="*50)
            print("STEP 2: Extracting balance changes")
            print("="*50)
            
            signatures = [tx['signature'] for tx in transactions_result['transactions']]
            
            balance_changes_result = manager.execute_task(
                extract_balance_changes_task,
                address_id,
                signatures,
                timeout=600  # 10 minutes timeout
            )
            
            # Combine results
            final_result = {
                'address_id': address_id,
                'days_scraped': days,
                'transactions': transactions_result['transactions'],
                'balance_changes': balance_changes_result['balance_changes'] if balance_changes_result else {},
                'summary': {
                    'total_transactions': transactions_result['total_found'],
                    'transaction_pages': transactions_result['pages_processed'],
                    'balance_changes_found': balance_changes_result['signatures_found'] if balance_changes_result else 0,
                    'balance_change_pages': balance_changes_result['pages_processed'] if balance_changes_result else 0
                },
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Save results to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"address_trading_history_{address_id[:8]}_{timestamp}.json"
            
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(final_result, f, indent=2, ensure_ascii=False)
            
            print(f"\n" + "="*50)
            print("SCRAPING COMPLETE")
            print("="*50)
            print(f"Results saved to: {filename}")
            print(f"Total Axiom transactions: {final_result['summary']['total_transactions']}")
            print(f"Balance changes found: {final_result['summary']['balance_changes_found']}")
            
            return final_result
            
    except Exception as e:
        print(f"Error during scraping: {e}")
        return None

def extract_full_address_from_by_field(by_cell):
    """
    Extract full address from the 'By' field which might be truncated
    """
    try:
        # Try to find link first (which would give full address)
        by_link = by_cell.find_element(By.CSS_SELECTOR, "a")
        href = by_link.get_attribute("href")
        if "/account/" in href:
            return href.split("/account/")[-1]
    except:
        pass
    
    try:
        # If no link, try to get data-tooltip or title attribute that might have full address
        spans = by_cell.find_elements(By.CSS_SELECTOR, "span")
        for span in spans:
            title = span.get_attribute("title")
            if title and len(title) > 20:  # Solana addresses are 32-44 characters
                return title
            
            data_tooltip = span.get_attribute("data-tooltip")
            if data_tooltip and len(data_tooltip) > 20:
                return data_tooltip
    except:
        pass
    
    # Fallback to truncated text
    try:
        by_span = by_cell.find_element(By.CSS_SELECTOR, "span span")
        return by_span.text.strip()
    except:
        return by_cell.text.strip()

if __name__ == "__main__":
    # Example usage - test với address thật
    
    print("="*70)
    print("SOLSCAN ADDRESS TRANSACTION SCRAPER - UPDATED VERSION")
    print("="*70)
    
    address = "HwzkpaNPx6aFkeQ5We3JMn77q76dv9tTLEhkS5tQrNgE"
    
    print(f"Testing with address: {address}")
    print("Scraping Axiom transactions from last 1 day...")
    print()
    
    try:
        # Scrape transactions từ 1 ngày gần nhất
        result = scrape_address_transactions(address, days=1)
        
        if result:
            print("SCRAPING RESULTS")
            if result['transactions']:
                for i, tx in enumerate(result['transactions'][:3], 1):
                    # Show balance changes for this transaction
                    if tx['signature'] in result['balance_changes']:
                        print(f"   Balance Changes:")
                        for change in result['balance_changes'][tx['signature']]:
                            print(f"     - {change['token_name']}: {change['amount']} (Post: {change['post_balance']})")
                
                print(f"\n... and {len(result['transactions']) - 3} more transactions")
            else:
                print("\nNo Axiom transactions found for this address in the last day.")
                
        else:
            print("\nFailed to scrape data or no transactions found.")
            
    except Exception as e:
        print(f"\nError during scraping: {e}")
        import traceback
        traceback.print_exc()