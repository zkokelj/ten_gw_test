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

    def create_session_key(self) -> str:
        """Create a session key via eth_getStorageAt (CQ method 0x...0003).
        
        This method calls eth_getStorageAt with the special address 0x0000000000000000000000000000000000000003
        to create a new session key. The returned bytes represent the session key address.
        
        Returns:
            str: The session key address (checksummed)
            
        Raises:
            ValueError: If the RPC call failed or returned an error
        """
        logging.info('Creating session key')
        
        # The special address for creating session keys
        create_session_key_addr = "0x0000000000000000000000000000000000000003"
        # Zero hash for the storage position
        position = "0x0000000000000000000000000000000000000000000000000000000000000000"
        
        result = self._rpc_call(
            "eth_getStorageAt",
            [create_session_key_addr, position, "latest"]
        )
        
        if "result" in result:
            # The result is a hex string representing bytes
            sk_bytes_hex = result["result"]
            
            # Remove '0x' prefix if present
            if sk_bytes_hex.startswith('0x'):
                sk_bytes_hex = sk_bytes_hex[2:]
            
            # Handle different return formats:
            # - If exactly 40 chars (20 bytes), use as-is (address returned directly)
            # - If 64 chars (32 bytes), take the first 40 chars (left-aligned, matching Go's BytesToAddress)
            # - Otherwise, pad/truncate to 40 chars
            if len(sk_bytes_hex) == 40:
                # Address returned directly as 20 bytes
                address_hex = sk_bytes_hex
            elif len(sk_bytes_hex) >= 64:
                # 32-byte storage slot, take first 20 bytes (matching Go's BytesToAddress behavior)
                address_hex = sk_bytes_hex[:40]
            else:
                # Pad to 40 characters if shorter, or truncate if longer
                address_hex = sk_bytes_hex.zfill(40)[:40]
            
            # Convert to address format
            sk_address = "0x" + address_hex
            # Convert to checksummed address
            sk_address = self.w3.to_checksum_address(sk_address)
            
            logging.info(f'Session key created: {sk_address}')
            return sk_address
        
        raise ValueError(f"Failed to create session key: {result}")

    def delete_session_key(self, session_key_address: str) -> bool:
        """Delete a session key via eth_getStorageAt (CQ method 0x...0004).
        
        This method calls eth_getStorageAt with the special address 0x0000000000000000000000000000000000000004
        to delete a session key. The session key address is passed as a JSON parameter.
        
        Args:
            session_key_address: The session key address to delete (checksummed or not)
            
        Returns:
            bool: True if deletion was successful (result == 0x01), False otherwise
            
        Raises:
            ValueError: If the RPC call failed or returned an error
        """
        logging.info(f'Deleting session key: {session_key_address}')
        
        # Ensure the address is checksummed
        session_key_address = self.w3.to_checksum_address(session_key_address)
        
        # The special address for deleting session keys
        delete_session_key_addr = "0x0000000000000000000000000000000000000004"
        
        # Create the JSON parameter object
        params_obj = {
            "sessionKeyAddress": session_key_address
        }
        params_json = json.dumps(params_obj)
        
        result = self._rpc_call(
            "eth_getStorageAt",
            [delete_session_key_addr, params_json, "latest"]
        )
        
        if "result" in result:
            # The result should be a hex string representing bytes
            result_hex = result["result"]
            
            # Remove '0x' prefix if present
            if result_hex.startswith('0x'):
                result_hex = result_hex[2:]
            
            # Remove leading zeros to get the actual byte value
            result_hex = result_hex.lstrip('0')
            
            # If empty after stripping zeros, it's 0x00
            if not result_hex:
                result_hex = '0'
            
            # Convert to integer to check the value
            result_value = int(result_hex, 16) if result_hex else 0
            
            if result_value == 1:
                logging.info(f'Session key deleted successfully: {session_key_address}')
                return True
            else:
                logging.warning(f'Session key deletion returned unexpected value: {result_value} (expected 1)')
                return False
        
        raise ValueError(f"Failed to delete session key: {result}")

    def get_gas_price(self) -> int:
        """Get the current gas price in wei.
        
        Returns:
            int: The gas price in wei
            
        Raises:
            ValueError: If the RPC call failed or returned an error
        """
        logging.info('Getting gas price')
        
        result = self._rpc_call("eth_gasPrice", [])
        
        if "result" in result:
            gas_price_hex = result["result"]
            gas_price_wei = int(gas_price_hex, 16)
            logging.info(f'Gas price: {gas_price_wei} wei')
            return gas_price_wei
        
        raise ValueError(f"Failed to get gas price: {result}")

    def estimate_gas(self, from_address: str, to_address: str, value_wei: int = 0, data: str = None) -> int:
        """Estimate the gas required for a transaction.
        
        Args:
            from_address: The sender address
            to_address: The recipient address (or contract address)
            value_wei: The value to send in wei (default: 0)
            data: Optional transaction data (hex string with 0x prefix)
            
        Returns:
            int: The estimated gas limit
            
        Raises:
            ValueError: If the RPC call failed or returned an error
        """
        logging.info(f'Estimating gas for transaction from {from_address} to {to_address}')
        
        call_obj = {
            "from": self.w3.to_checksum_address(from_address),
            "to": self.w3.to_checksum_address(to_address),
            "value": hex(value_wei)
        }
        
        if data:
            call_obj["data"] = data
        
        result = self._rpc_call("eth_estimateGas", [call_obj])
        
        if "result" in result:
            gas_hex = result["result"]
            gas_limit = int(gas_hex, 16)
            logging.info(f'Estimated gas: {gas_limit}')
            return gas_limit
        
        raise ValueError(f"Failed to estimate gas: {result}")

    def send_transaction_from_session_key(
        self,
        session_key_address: str,
        to_address: str,
        value_wei: int,
        gas: int = None,
        gas_price: int = None
    ) -> str:
        """Send a transaction from a session key.
        
        This method uses eth_sendTransaction (not eth_sendRawTransaction) because
        the gateway manages session key signing. The session key address is specified
        in the 'from' field.
        
        Args:
            session_key_address: The session key address to send from
            to_address: The recipient address
            value_wei: The amount to send in wei
            gas: Gas limit (if None, will be estimated)
            gas_price: Gas price in wei (if None, will be fetched)
            
        Returns:
            str: The transaction hash
            
        Raises:
            ValueError: If the RPC call failed or returned an error
        """
        logging.info(f'Sending transaction from session key {session_key_address} to {to_address}')
        
        # Ensure addresses are checksummed
        session_key_address = self.w3.to_checksum_address(session_key_address)
        to_address = self.w3.to_checksum_address(to_address)
        
        # Get nonce for the session key
        nonce = self.get_transaction_count(session_key_address)
        
        # Get gas price if not provided
        if gas_price is None:
            gas_price = self.get_gas_price()
        
        # Estimate gas if not provided
        if gas is None:
            gas = self.estimate_gas(session_key_address, to_address, value_wei)
        
        # Build the transaction object
        transaction = {
            "from": session_key_address,
            "to": to_address,
            "value": hex(value_wei),
            "gas": hex(gas),
            "gasPrice": hex(gas_price),
            "nonce": hex(nonce)
        }
        
        # Send transaction using eth_sendTransaction (gateway handles signing for session keys)
        result = self._rpc_call("eth_sendTransaction", [transaction])
        
        if "result" in result:
            tx_hash = result["result"]
            logging.info(f'Transaction sent from session key: {tx_hash}')
            return tx_hash
        
        raise ValueError(f"Failed to send transaction from session key: {result}")