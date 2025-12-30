from dataclasses import dataclass

@dataclass(frozen=True)
class NetworkConfig:
    url: str
    chain_id: int

class Environment:
    LOCAL = NetworkConfig("http://127.0.0.1:3000/v1", 443)
    DEXYNTH = NetworkConfig("https://rpc.dexynth-gateway.ten.xyz/v1", 8443)
    SEPOLIA = NetworkConfig("https://testnet-rpc.ten.xyz/v1", 8443)
    UAT = NetworkConfig("https://rpc.uat-gw-testnet.ten.xyz/v1", 7443)

