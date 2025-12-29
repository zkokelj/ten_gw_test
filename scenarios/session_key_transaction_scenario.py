import logging
import time
from gateway import GatewayClient, Environment

logging.basicConfig(
    format='%(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO
)

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
    
    logging.info(f'Starting session key transaction test against {env.url}')
    logging.info('=' * 60)
    
    # Step 1: Create an account
    logging.info('Step 1: Creating account...')
    client = GatewayClient(env)
    
    logging.info(f'Account address: {client.account.address}')
    logging.info(f'Private key: {client.account.key.hex()}')
    
    # Authenticate
    logging.info('Authenticating...')
    client.full_auth_flow()
    logging.info('✓ Authentication successful')
    
    # Step 2: Wait for funds
    logging.info('=' * 60)
    logging.info('Step 2: Waiting for funds...')
    logging.info(f'Please send funds to: {client.account.address}')
    
    initial_balance = wait_for_funds(client, client.account.address, timeout_seconds=300)
    initial_balance_eth = format_wei_to_eth(initial_balance)
    logging.info(f'✓ Initial balance received: {initial_balance} wei ({initial_balance_eth} ETH)')
    
    # Step 3: Create session key and transfer funds
    logging.info('=' * 60)
    logging.info('Step 3: Creating session key and transferring funds...')
    
    session_key_address = client.create_session_key()
    logging.info(f'✓ Session key created: {session_key_address}')
    
    # Get current gas price and estimate gas for the transfer
    gas_price = client.get_gas_price()
    estimated_gas = client.estimate_gas(
        client.account.address,
        session_key_address,
        value_wei=initial_balance
    )
    
    # Calculate gas cost
    gas_cost = estimated_gas * gas_price
    
    # Transfer majority of funds (leave enough for gas)
    # We'll transfer 95% of the balance, leaving 5% for gas fees
    transfer_amount = (initial_balance * 95) // 100
    
    # Make sure we have enough for gas
    if transfer_amount + gas_cost > initial_balance:
        # If not, transfer less to ensure we can pay for gas
        transfer_amount = initial_balance - gas_cost - (initial_balance // 1000)  # Leave small buffer
    
    transfer_amount_eth = format_wei_to_eth(transfer_amount)
    logging.info(f'Transferring {transfer_amount} wei ({transfer_amount_eth} ETH) to session key')
    logging.info(f'Gas estimate: {estimated_gas}, Gas price: {gas_price} wei, Gas cost: {gas_cost} wei')
    
    tx_hash = client.send_transaction(
        to_address=session_key_address,
        value_wei=transfer_amount,
        gas=estimated_gas,
        gas_price=gas_price
    )
    logging.info(f'✓ Transfer transaction sent: {tx_hash}')
    
    # Wait a bit for the transaction to be mined
    logging.info('Waiting for transaction to be mined...')
    time.sleep(5)
    
    # Step 4: Verify funds are on session key account
    logging.info('=' * 60)
    logging.info('Step 4: Verifying session key balance...')
    
    session_key_balance = client.get_balance(session_key_address)
    session_key_balance_eth = format_wei_to_eth(session_key_balance)
    logging.info(f'Session key balance: {session_key_balance} wei ({session_key_balance_eth} ETH)')
    
    if session_key_balance >= transfer_amount * 99 // 100:  # Allow 1% tolerance for gas variations
        logging.info('✓ Funds successfully transferred to session key')
    else:
        logging.error(f'✗ Transfer verification failed. Expected ~{transfer_amount} wei, got {session_key_balance} wei')
        return
    
    # Step 5: Send funds back to original account using session key
    logging.info('=' * 60)
    logging.info('Step 5: Sending funds back using session key...')
    
    # Get gas price and estimate gas for the return transaction
    return_gas_price = client.get_gas_price()
    return_estimated_gas = client.estimate_gas(
        session_key_address,
        client.account.address,
        value_wei=session_key_balance
    )
    
    # Calculate return amount (leave enough for gas)
    return_gas_cost = return_estimated_gas * return_gas_price
    return_amount = session_key_balance - return_gas_cost - (session_key_balance // 1000)  # Leave small buffer
    
    if return_amount <= 0:
        logging.warning('Not enough balance on session key to cover gas costs for return transaction')
        return_amount = session_key_balance // 2  # Send half if we can't calculate properly
    
    return_amount_eth = format_wei_to_eth(return_amount)
    logging.info(f'Sending {return_amount} wei ({return_amount_eth} ETH) back to original account')
    logging.info(f'Gas estimate: {return_estimated_gas}, Gas price: {return_gas_price} wei')
    
    return_tx_hash = client.send_transaction_from_session_key(
        session_key_address=session_key_address,
        to_address=client.account.address,
        value_wei=return_amount,
        gas=return_estimated_gas,
        gas_price=return_gas_price
    )
    logging.info(f'✓ Return transaction sent: {return_tx_hash}')
    
    # Wait a bit for the transaction to be mined
    logging.info('Waiting for return transaction to be mined...')
    time.sleep(5)
    
    # Step 6: Verify funds are returned
    logging.info('=' * 60)
    logging.info('Step 6: Verifying funds returned to original account...')
    
    final_balance = client.get_balance(client.account.address)
    final_balance_eth = format_wei_to_eth(final_balance)
    logging.info(f'Final balance: {final_balance} wei ({final_balance_eth} ETH)')
    
    # Calculate how much was returned (accounting for gas spent on first transaction)
    expected_final_balance = initial_balance - gas_cost + return_amount - return_gas_cost
    balance_diff = final_balance - initial_balance
    
    if balance_diff > 0:
        logging.info(f'✓ Funds returned! Balance increased by {balance_diff} wei ({format_wei_to_eth(balance_diff)} ETH)')
    else:
        logging.warning(f'Balance decreased by {abs(balance_diff)} wei (likely due to gas costs)')
    
    # Cleanup: Delete session key
    logging.info('=' * 60)
    logging.info('Cleaning up: Deleting session key...')
    deleted = client.delete_session_key(session_key_address)
    
    if deleted:
        logging.info('✓ Session key deleted successfully')
    else:
        logging.warning('Session key deletion may have failed')
    
    logging.info('=' * 60)
    logging.info('Session key transaction scenario completed successfully!')

if __name__ == "__main__":
    main()

