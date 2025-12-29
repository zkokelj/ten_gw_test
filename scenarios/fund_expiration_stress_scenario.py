import logging
import sys
import time
from typing import List, Tuple
from gateway import GatewayClient, Environment

logging.basicConfig(
    format='%(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO
)

# Configuration
NUM_USERS = 5  # Number of users to create
SESSION_KEYS_PER_USER = 3  # Number of session keys per user
EXPIRATION_WAIT_SECONDS = 600  # Time to wait for fund expiration (default: 10 minutes)
RETURN_ADDRESS = "0x10DeC2baF2944Ce99710B4319Ec7C7B619E70a0E"  # Address to send remaining funds to

def wait_for_funds(client: GatewayClient, address: str, timeout_seconds: int = 300, check_interval: int = 5) -> int:
    """Wait for funds to arrive at an address.
    
    Args:
        client: The gateway client
        address: The address to check
        timeout_seconds: Maximum time to wait in seconds (default: 300 = 5 minutes)
        check_interval: How often to check in seconds (default: 5)
        
    Returns:
        int: The balance in wei when funds are detected
        
    Raises:
        TimeoutError: If funds don't arrive within the timeout period
    """
    logging.info(f'Waiting for funds to arrive at {address}...')
    logging.info(f'Timeout: {timeout_seconds} seconds, checking every {check_interval} seconds')
    
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        try:
            balance = client.get_balance(address)
            if balance > 0:
                balance_eth = balance / 10**18
                logging.info(f'Funds detected! Balance: {balance} wei ({balance_eth:.6f} ETH)')
                return balance
        except Exception as e:
            logging.debug(f'Error checking balance: {e}')
        
        time.sleep(check_interval)
        elapsed = int(time.time() - start_time)
        logging.info(f'Still waiting... ({elapsed}/{timeout_seconds} seconds)')
    
    raise TimeoutError(f'No funds received at {address} within {timeout_seconds} seconds')

def format_wei_to_eth(wei: int) -> str:
    """Format wei amount to ETH with 6 decimal places."""
    eth = wei / 10**18
    return f"{eth:.6f}"

def main():
    # Pick your environment
    env = Environment.SEPOLIA
    
    logging.info(f'Starting fund expiration stress test against {env.url}')
    logging.info(f'Configuration: {NUM_USERS} users, {SESSION_KEYS_PER_USER} session keys per user')
    logging.info(f'Total session keys: {NUM_USERS * SESSION_KEYS_PER_USER}')
    logging.info(f'Expiration wait time: {EXPIRATION_WAIT_SECONDS} seconds ({EXPIRATION_WAIT_SECONDS // 60} minutes)')
    logging.info('=' * 60)
    
    # Step 1: Create main account and wait for funds
    logging.info('Step 1: Creating main account and waiting for funds...')
    main_client = GatewayClient(env)
    
    logging.info(f'Main account address: {main_client.account.address}')
    logging.info(f'Main account private key: {main_client.account.key.hex()}')
    
    # Authenticate main account
    logging.info('Authenticating main account...')
    main_client.full_auth_flow()
    logging.info('✓ Main account authentication successful')
    
    logging.info(f'Please send funds to main account: {main_client.account.address}')
    initial_balance = wait_for_funds(main_client, main_client.account.address, timeout_seconds=300)
    initial_balance_eth = format_wei_to_eth(initial_balance)
    logging.info(f'✓ Initial balance received: {initial_balance} wei ({initial_balance_eth} ETH)')
    
    # Step 2: Create users and session keys
    logging.info('=' * 60)
    logging.info('Step 2: Creating users and session keys...')
    
    users: List[GatewayClient] = []
    all_session_keys: List[Tuple[GatewayClient, str]] = []  # List of (user_client, session_key_address)
    
    for user_idx in range(NUM_USERS):
        logging.info(f'Creating user {user_idx + 1}/{NUM_USERS}...')
        user_client = GatewayClient(env)
        user_client.full_auth_flow()
        users.append(user_client)
        logging.info(f'  User {user_idx + 1} address: {user_client.account.address}')
        
        # Create session keys for this user
        for sk_idx in range(SESSION_KEYS_PER_USER):
            session_key_address = user_client.create_session_key()
            all_session_keys.append((user_client, session_key_address))
            logging.info(f'  User {user_idx + 1}, Session key {sk_idx + 1}: {session_key_address}')
    
    total_session_keys = len(all_session_keys)
    logging.info(f'✓ Created {NUM_USERS} users with {total_session_keys} total session keys')
    
    # Step 3: Distribute funds to all session keys
    logging.info('=' * 60)
    logging.info('Step 3: Distributing funds to all session keys...')
    
    # Get gas price and estimate gas
    gas_price = main_client.get_gas_price()
    
    # Calculate how much to send to each session key
    # We need to leave enough for gas for all transactions
    # Estimate: each transfer needs ~21000 gas (simple transfer)
    estimated_gas_per_transfer = 21000
    total_gas_needed = estimated_gas_per_transfer * gas_price * total_session_keys
    
    # Reserve some extra for safety
    gas_reserve = total_gas_needed * 2  # Double the estimate for safety
    
    # Calculate amount per session key
    available_for_distribution = initial_balance - gas_reserve
    if available_for_distribution <= 0:
        logging.error('=' * 60)
        logging.error('✗ ERROR: Not enough funds to cover gas costs!')
        logging.error(f'✗ Initial balance: {initial_balance} wei')
        logging.error(f'✗ Gas reserve needed: {gas_reserve} wei')
        logging.error('=' * 60)
        sys.exit(1)
    
    amount_per_session_key = available_for_distribution // total_session_keys
    
    logging.info(f'Distributing {amount_per_session_key} wei ({format_wei_to_eth(amount_per_session_key)} ETH) to each session key')
    logging.info(f'Gas price: {gas_price} wei, Estimated gas per transfer: {estimated_gas_per_transfer}')
    
    # Send funds to each session key
    successful_transfers = 0
    failed_transfers = 0
    
    for idx, (user_client, session_key_address) in enumerate(all_session_keys):
        try:
            # Estimate gas for this specific transfer
            estimated_gas = main_client.estimate_gas(
                main_client.account.address,
                session_key_address,
                value_wei=amount_per_session_key
            )
            
            tx_hash = main_client.send_transaction(
                to_address=session_key_address,
                value_wei=amount_per_session_key,
                gas=estimated_gas,
                gas_price=gas_price
            )
            
            successful_transfers += 1
            if (idx + 1) % 10 == 0 or (idx + 1) == total_session_keys:
                logging.info(f'  Sent to {idx + 1}/{total_session_keys} session keys...')
        except Exception as e:
            failed_transfers += 1
            logging.error(f'  ✗ Failed to send to session key {session_key_address}: {e}')
    
    logging.info(f'✓ Transfers completed: {successful_transfers} successful, {failed_transfers} failed')
    
    # Wait a bit for transactions to be mined
    logging.info('Waiting for transactions to be mined...')
    time.sleep(10)
    
    # Step 4: Verify funds are on session keys
    logging.info('=' * 60)
    logging.info('Step 4: Verifying funds on session keys...')
    
    total_session_key_balance = 0
    for user_client, session_key_address in all_session_keys:
        try:
            balance = user_client.get_balance(session_key_address)
            total_session_key_balance += balance
        except Exception as e:
            logging.warning(f'  Could not check balance for {session_key_address}: {e}')
    
    main_balance_after_distribution = main_client.get_balance(main_client.account.address)
    logging.info(f'Main account balance after distribution: {main_balance_after_distribution} wei ({format_wei_to_eth(main_balance_after_distribution)} ETH)')
    logging.info(f'Total session key balance: {total_session_key_balance} wei ({format_wei_to_eth(total_session_key_balance)} ETH)')
    
    # Step 5: Wait for fund expiration
    logging.info('=' * 60)
    logging.info(f'Step 5: Waiting {EXPIRATION_WAIT_SECONDS} seconds for fund expiration...')
    logging.info(f'This is {EXPIRATION_WAIT_SECONDS // 60} minutes and {EXPIRATION_WAIT_SECONDS % 60} seconds')
    
    # Show countdown every minute
    wait_start = time.time()
    last_logged_minute = -1
    
    while time.time() - wait_start < EXPIRATION_WAIT_SECONDS:
        elapsed = int(time.time() - wait_start)
        current_minute = elapsed // 60
        
        if current_minute != last_logged_minute:
            remaining = EXPIRATION_WAIT_SECONDS - elapsed
            remaining_minutes = remaining // 60
            remaining_seconds = remaining % 60
            logging.info(f'  Waiting... {elapsed}/{EXPIRATION_WAIT_SECONDS} seconds elapsed ({remaining_minutes}m {remaining_seconds}s remaining)')
            last_logged_minute = current_minute
        
        time.sleep(10)  # Check every 10 seconds
    
    logging.info('✓ Wait period completed')
    
    # Step 6: Verify fund expiration
    logging.info('=' * 60)
    logging.info('Step 6: Verifying fund expiration...')
    
    main_balance_after_expiration = main_client.get_balance(main_client.account.address)
    main_balance_eth = format_wei_to_eth(main_balance_after_expiration)
    logging.info(f'Main account balance after expiration: {main_balance_after_expiration} wei ({main_balance_eth} ETH)')
    
    # Check session key balances
    total_session_key_balance_after = 0
    non_zero_session_keys = []
    
    for user_client, session_key_address in all_session_keys:
        try:
            balance = user_client.get_balance(session_key_address)
            total_session_key_balance_after += balance
            if balance > 0:
                non_zero_session_keys.append((session_key_address, balance))
        except Exception as e:
            logging.warning(f'  Could not check balance for {session_key_address}: {e}')
    
    logging.info(f'Total session key balance after expiration: {total_session_key_balance_after} wei ({format_wei_to_eth(total_session_key_balance_after)} ETH)')
    
    if non_zero_session_keys:
        logging.warning(f'Found {len(non_zero_session_keys)} session keys with non-zero balance:')
        for sk_address, balance in non_zero_session_keys[:10]:  # Show first 10
            logging.warning(f'  {sk_address}: {balance} wei ({format_wei_to_eth(balance)} ETH)')
        if len(non_zero_session_keys) > 10:
            logging.warning(f'  ... and {len(non_zero_session_keys) - 10} more')
    
    # Verify main balance is close to original (accounting for gas spent)
    # We expect: initial_balance - gas_spent + expired_funds ≈ current_balance
    # Since we don't know exact gas spent, we'll check if balance increased significantly
    balance_increase = main_balance_after_expiration - main_balance_after_distribution
    
    test_passed = True
    
    if balance_increase > 0:
        logging.info(f'✓ Main balance increased by {balance_increase} wei ({format_wei_to_eth(balance_increase)} ETH)')
        # Check if we got back at least 80% of what we sent (accounting for gas)
        expected_minimum_return = total_session_key_balance * 80 // 100
        if balance_increase >= expected_minimum_return:
            logging.info(f'✓ Balance increase meets expected minimum ({expected_minimum_return} wei)')
        else:
            logging.warning(f'⚠ Balance increase ({balance_increase} wei) is less than expected minimum ({expected_minimum_return} wei)')
    else:
        logging.error('=' * 60)
        logging.error('✗ ERROR: Main balance did not increase after expiration!')
        logging.error(f'✗ Balance after distribution: {main_balance_after_distribution} wei')
        logging.error(f'✗ Balance after expiration: {main_balance_after_expiration} wei')
        logging.error('=' * 60)
        test_passed = False
    
    # Check if session key balances are zero or close to zero
    # Allow 1% tolerance for any remaining funds
    tolerance = total_session_key_balance // 100 if total_session_key_balance > 0 else 0
    
    if total_session_key_balance_after <= tolerance:
        logging.info(f'✓ Session key balances cleared (total: {total_session_key_balance_after} wei, tolerance: {tolerance} wei)')
    else:
        logging.warning(f'⚠ Some session keys still have balance (total: {total_session_key_balance_after} wei)')
        if total_session_key_balance_after > tolerance * 5:  # More than 5% remaining
            test_passed = False
    
    # Step 7: Send remaining funds back to return address
    logging.info('=' * 60)
    logging.info('Step 7: Sending remaining funds back to return address...')
    logging.info(f'Return address: {RETURN_ADDRESS}')
    
    final_main_balance = main_client.get_balance(main_client.account.address)
    final_main_balance_eth = format_wei_to_eth(final_main_balance)
    logging.info(f'Current main account balance: {final_main_balance} wei ({final_main_balance_eth} ETH)')
    
    if final_main_balance > 0:
        # Get gas price and estimate gas
        return_gas_price = main_client.get_gas_price()
        return_estimated_gas = main_client.estimate_gas(
            main_client.account.address,
            RETURN_ADDRESS,
            value_wei=final_main_balance
        )
        
        # Calculate return amount (leave enough for gas)
        return_gas_cost = return_estimated_gas * return_gas_price
        return_amount = final_main_balance - return_gas_cost - (final_main_balance // 1000)  # Leave small buffer
        
        if return_amount > 0:
            return_amount_eth = format_wei_to_eth(return_amount)
            logging.info(f'Sending {return_amount} wei ({return_amount_eth} ETH) to return address')
            
            try:
                return_tx_hash = main_client.send_transaction(
                    to_address=RETURN_ADDRESS,
                    value_wei=return_amount,
                    gas=return_estimated_gas,
                    gas_price=return_gas_price
                )
                logging.info(f'✓ Return transaction sent: {return_tx_hash}')
                
                # Wait for transaction to be mined
                time.sleep(5)
                
                # Verify funds were sent
                remaining_balance = main_client.get_balance(main_client.account.address)
                logging.info(f'Remaining balance: {remaining_balance} wei ({format_wei_to_eth(remaining_balance)} ETH)')
            except Exception as e:
                logging.error(f'✗ Failed to send funds to return address: {e}')
        else:
            logging.warning('Not enough balance to cover gas costs for return transaction')
    else:
        logging.info('No funds remaining to return')
    
    # Final summary
    logging.info('=' * 60)
    if test_passed:
        logging.info('✓ Fund expiration stress test completed successfully!')
    else:
        logging.error('✗ Fund expiration stress test FAILED!')
        logging.error('✗ Some funds may not have expired as expected.')
        logging.error('=' * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()

