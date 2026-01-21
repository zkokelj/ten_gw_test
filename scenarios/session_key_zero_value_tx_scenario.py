import logging
import time
from gateway import GatewayClient, Environment

logging.basicConfig(
    format='%(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO
)

def wait_for_tx_receipt(client: GatewayClient, tx_hash: str, timeout_seconds: int = 60, check_interval: int = 2) -> dict:
    """Wait for a transaction to be included in the blockchain.

    Args:
        client: The gateway client
        tx_hash: The transaction hash to check
        timeout_seconds: Maximum time to wait in seconds (default: 60)
        check_interval: How often to check in seconds (default: 2)

    Returns:
        dict: The transaction receipt

    Raises:
        TimeoutError: If the transaction is not included within the timeout period
    """
    logging.info(f'Waiting for transaction {tx_hash} to be included...')

    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        try:
            result = client._rpc_call("eth_getTransactionReceipt", [tx_hash])
            if "result" in result and result["result"] is not None:
                receipt = result["result"]
                logging.info(f'Transaction included in block {receipt.get("blockNumber")}')
                return receipt
        except Exception as e:
            logging.debug(f'Error checking receipt: {e}')

        time.sleep(check_interval)

    raise TimeoutError(f'Transaction {tx_hash} not included within {timeout_seconds} seconds')

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

    logging.info(f'Starting session key zero value transaction test against {env.url}')
    logging.info('=' * 60)

    # Step 1: Create an account
    logging.info('Step 1: Creating account...')
    client = GatewayClient(env)

    logging.info(f'Account address: {client.account.address}')
    logging.info(f'Private key: {client.account.key.hex()}')

    # Authenticate
    logging.info('Authenticating...')
    client.full_auth_flow()
    logging.info('Authentication successful')

    # Step 2: Wait for funds
    logging.info('=' * 60)
    logging.info('Step 2: Waiting for funds...')
    logging.info(f'Please send funds to: {client.account.address}')

    initial_balance = wait_for_funds(client, client.account.address, timeout_seconds=300)
    initial_balance_eth = format_wei_to_eth(initial_balance)
    logging.info(f'Initial balance received: {initial_balance} wei ({initial_balance_eth} ETH)')

    # Step 3: Create session key and transfer funds to it
    logging.info('=' * 60)
    logging.info('Step 3: Creating session key and transferring funds...')

    session_key_address = client.create_session_key()
    logging.info(f'Session key created: {session_key_address}')

    # Get current gas price and estimate gas for the transfer
    gas_price = client.get_gas_price()
    estimated_gas = client.estimate_gas(
        client.account.address,
        session_key_address,
        value_wei=initial_balance
    )

    # Calculate gas cost
    gas_cost = estimated_gas * gas_price

    # Transfer majority of funds to session key (leave enough for gas)
    transfer_amount = (initial_balance * 95) // 100

    # Make sure we have enough for gas
    if transfer_amount + gas_cost > initial_balance:
        transfer_amount = initial_balance - gas_cost - (initial_balance // 1000)

    transfer_amount_eth = format_wei_to_eth(transfer_amount)
    logging.info(f'Transferring {transfer_amount} wei ({transfer_amount_eth} ETH) to session key')
    logging.info(f'Gas estimate: {estimated_gas}, Gas price: {gas_price} wei, Gas cost: {gas_cost} wei')

    tx_hash = client.send_transaction(
        to_address=session_key_address,
        value_wei=transfer_amount,
        gas=estimated_gas,
        gas_price=gas_price
    )
    logging.info(f'Transfer transaction sent: {tx_hash}')

    # Wait for the transaction to be mined
    logging.info('Waiting for transaction to be mined...')
    time.sleep(5)

    # Step 4: Verify funds are on session key account
    logging.info('=' * 60)
    logging.info('Step 4: Verifying session key balance...')

    session_key_balance = client.get_balance(session_key_address)
    session_key_balance_eth = format_wei_to_eth(session_key_balance)
    logging.info(f'Session key balance: {session_key_balance} wei ({session_key_balance_eth} ETH)')

    if session_key_balance >= transfer_amount * 99 // 100:
        logging.info('Funds successfully transferred to session key')
    else:
        logging.error(f'Transfer verification failed. Expected ~{transfer_amount} wei, got {session_key_balance} wei')
        return

    # Step 5: Send a zero value transaction from session key (only paying gas)
    logging.info('=' * 60)
    logging.info('Step 5: Sending ZERO VALUE transaction from session key...')
    logging.info('This transaction transfers 0 ETH and only pays for gas')

    # Send zero value transaction
    zero_tx_hash = client.send_transaction_from_session_key(
        session_key_address=session_key_address,
        to_address=client.account.address,
        value_wei=0  # Zero value - only paying gas
    )
    logging.info(f'Zero value transaction sent: {zero_tx_hash}')

    # Step 6: Verify the transaction is included in the blockchain
    logging.info('=' * 60)
    logging.info('Step 6: Verifying zero value transaction is included in blockchain...')

    receipt = wait_for_tx_receipt(client, zero_tx_hash)
    status = int(receipt.get("status", "0x0"), 16)

    if status == 1:
        logging.info('Zero value transaction included and successful!')
        logging.info(f'Block: {receipt.get("blockNumber")}')
        logging.info(f'Gas used: {int(receipt.get("gasUsed", "0x0"), 16)}')
    else:
        raise Exception(f'Zero value transaction failed with status {status}')

    # Cleanup: Delete session key
    logging.info('=' * 60)
    logging.info('Cleaning up: Deleting session key...')
    deleted = client.delete_session_key(session_key_address)

    if deleted:
        logging.info('Session key deleted successfully')
    else:
        logging.warning('Session key deletion may have failed')

    logging.info('=' * 60)
    logging.info('Session key zero value transaction scenario completed!')

if __name__ == "__main__":
    main()
