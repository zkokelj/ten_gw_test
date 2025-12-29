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
    
    logging.info('Basic auth scenario completed')

if __name__ == "__main__":
    main()