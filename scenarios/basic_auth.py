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
    
    logging.info(f'Starting basic auth test against {env.url}')
    
    client = GatewayClient(env)
    
    logging.info(f'Created account: {client.account.address}')
    logging.info(f'Private key: {client.account.key.hex()}')
    
    client.full_auth_flow()
    client.create_session_key()
    balance = client.get_balance(client.account.address)
    balance_eth = balance / 10**18
    transaction_count = client.get_transaction_count(client.account.address)

    logging.info('Basic auth scenario completed')



if __name__ == "__main__":
    main()