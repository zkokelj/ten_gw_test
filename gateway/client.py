import requests
import logging
import json
from web3 import Web3
from .config import NetworkConfig

logging.basicConfig(
    format='%(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO
)

class GatewayClient:
    def __init__(self, env: NetworkConfig, account=None):
        self.base_url = env.url
        self.chain_id = env.chain_id
        self.w3 = Web3()
        self.account = account or self.w3.eth.account.create()
        self.token = None

    def join(self) -> str:
        """Join the Ten network and get a token."""
        logging.info(f'Joining {self.base_url}')
        response = requests.get(
            f"{self.base_url}/join/",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        self.token = response.text
        logging.info(f'Got token: {self.token}')
        return self.token

    def sign(self) -> str:
        """Sign the authentication message with the account's private key."""
        logging.info(f'Signing for {self.account.address}')
        
        domain = {
            "name": "Ten",
            "version": "1.0",
            "chainId": self.chain_id,
            "verifyingContract": "0x0000000000000000000000000000000000000000"
        }
        
        types = {
            "Authentication": [
                {"name": "Encryption Token", "type": "address"}
            ]
        }
        
        message = {
            "Encryption Token": f"0x{self.token}"
        }
        
        signed = self.w3.eth.account.sign_typed_data(
            private_key=self.account.key,
            domain_data=domain,
            message_types=types,
            message_data=message
        )
        return "0x" + signed.signature.hex()

    def authenticate(self, signature: str) -> bool:
        """Authenticate the account with the signed message.
        
        Returns:
            bool: True if authentication was successful (response == "success"), False otherwise
            
        Raises:
            requests.HTTPError: If the HTTP request failed (network errors, server errors, etc.)
        """
        logging.info(f'Authenticating {self.account.address}')
        
        response = requests.post(
            f"{self.base_url}/authenticate/?token={self.token}",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "signature": signature,
                "address": self.account.address
            }
        )
        response.raise_for_status()  # Raise an exception for bad HTTP status codes
        logging.info(f'Auth response: {response.text}')
        
        if response.text == "success":
            logging.info('Authentication successful')
            return True
        
        logging.warning(f'Authentication failed. Expected "success", got: {response.text}')
        return False

    def full_auth_flow(self) -> bool:
        """Convenience method: join -> sign -> authenticate
        
        Returns:
            bool: True if authentication was successful, False otherwise
        """
        self.join()
        signature = self.sign()
        return self.authenticate(signature)

    def _rpc_call(self, method: str, params: list) -> dict:
        """Make an RPC call to the gateway.
        
        Args:
            method: The RPC method name (e.g., "eth_getBalance")
            params: The parameters for the RPC method
            
        Returns:
            dict: The JSON-RPC response
            
        Raises:
            requests.HTTPError: If the HTTP request failed
            ValueError: If the RPC call failed or returned an error
        """
        if self.token is None:
            raise ValueError("Must authenticate first (call join() and authenticate())")
        
        url = f"{self.base_url}/?token={self.token}"
        headers = {"Content-Type": "application/json"}
        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        
        response = requests.post(url, data=json.dumps(data), headers=headers)
        response.raise_for_status()
        
        result = response.json()
        if "error" in result:
            raise ValueError(f"RPC error: {result['error']}")
        
        return result

    def get_transaction_count(self, address: str, block_parameter: str = "latest") -> int:
        """Get the transaction count (nonce) for an address.
        
        Args:
            address: The address to query
            block_parameter: The block parameter (default: "latest")
            
        Returns:
            int: The transaction count as an integer
        """
        logging.info(f'Getting transaction count for address: {address}')
        
        result = self._rpc_call(
            "eth_getTransactionCount",
            [address, block_parameter]
        )
        
        if "result" in result:
            tx_count_hex = result["result"]
            tx_count_decimal = int(tx_count_hex, 16)
            logging.info(f'Transaction count: {tx_count_decimal}')
            return tx_count_decimal
        
        raise ValueError(f"Failed to get transaction count: {result}")

    def get_balance(self, address: str, block_parameter: str = "latest") -> int:
        """Get the balance for an address in wei.
        
        Args:
            address: The address to query
            block_parameter: The block parameter (default: "latest")
            
        Returns:
            int: The balance in wei
        """
        logging.info(f'Getting balance for address: {address}')
        
        result = self._rpc_call(
            "eth_getBalance",
            [address, block_parameter]
        )
        
        if "result" in result:
            balance_hex = result["result"]
            balance_wei = int(balance_hex, 16)
            balance_eth = balance_wei / 10**18
            logging.info(f'Balance: {balance_wei} wei ({balance_eth:.6f} ETH)')
            return balance_wei
        
        raise ValueError(f"Failed to get balance: {result}")

    def send_transaction(self, to_address: str, value_wei: int, gas: int = 25000, gas_price: int = 20000000000) -> str:
        """Send a transaction from the account to another address.
        
        Args:
            to_address: The recipient address
            value_wei: The amount to send in wei
            gas: Gas limit (default: 25000)
            gas_price: Gas price in wei (default: 20000000000 = 20 gwei)
            
        Returns:
            str: The transaction hash
        """
        logging.info(f'Sending transaction from {self.account.address} to {to_address}')
        
        # Get transaction count for nonce
        nonce = self.get_transaction_count(self.account.address)
        
        # Create transaction
        transaction = {
            'to': self.w3.to_checksum_address(to_address),
            'value': value_wei,
            'gas': gas,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': self.chain_id
        }
        
        # Sign transaction
        signed_txn = self.w3.eth.account.sign_transaction(transaction, self.account.key)
        
        # Ensure the hex string has proper format
        raw_tx_hex = signed_txn.raw_transaction.hex()
        if not raw_tx_hex.startswith('0x'):
            raw_tx_hex = '0x' + raw_tx_hex
        
        # Send raw transaction
        result = self._rpc_call(
            "eth_sendRawTransaction",
            [raw_tx_hex]
        )
        
        if "result" in result:
            tx_hash = result["result"]
            logging.info(f'Transaction sent: {tx_hash}')
            return tx_hash
        
        raise ValueError(f"Failed to send transaction: {result}")