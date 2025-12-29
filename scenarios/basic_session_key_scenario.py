import logging
from gateway import GatewayClient, Environment

logging.basicConfig(
    format='%(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO
)

def main():
    # Pick your environment
    env = Environment.SEPOLIA
    
    logging.info(f'Starting basic session key test against {env.url}')
    
    client = GatewayClient(env)
    
    logging.info(f'Created account: {client.account.address}')
    logging.info(f'Private key: {client.account.key.hex()}')
    
    # Authenticate first (required before creating session keys)
    logging.info('Authenticating...')
    client.full_auth_flow()
    
    # Create a session key
    logging.info('Creating session key...')
    session_key_address = client.create_session_key()
    
    logging.info(f'Session key created successfully: {session_key_address}')
    
    # Optionally check the balance of the session key (should be 0 initially)
    try:
        balance = client.get_balance(session_key_address)
        balance_eth = balance / 10**18
        logging.info(f'Session key balance: {balance} wei ({balance_eth:.6f} ETH)')
    except Exception as e:
        logging.warning(f'Could not get session key balance: {e}')
    
    # Delete the session key
    logging.info('Deleting session key...')
    deleted = client.delete_session_key(session_key_address)
    
    if deleted:
        logging.info('Session key deleted successfully')
    else:
        logging.warning('Session key deletion may have failed')
    
    logging.info('Basic session key scenario completed')

if __name__ == "__main__":
    main()

