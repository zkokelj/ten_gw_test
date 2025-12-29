# Gateway Testing

Python client library for testing Ten Gateway functionality.

## Setup

This project uses [uv](https://github.com/astral-sh/uv) for dependency management. Dependencies are defined in `pyproject.toml`.

## Running Scenarios

Scenarios are located in the `scenarios/` directory and can be run using `uv run`:

### Basic Authentication

Test the basic authentication flow (join, sign, authenticate):

```bash
uv run python -m scenarios.basic_auth
```

### Session Key Management

Test session key creation and deletion:

```bash
uv run python -m scenarios.basic_session_key_scenario
```

This scenario will:

1. Authenticate with the gateway
2. Create a session key
3. Check the session key balance
4. Delete the session key

### Session Key Transactions

Test the full transaction flow with session keys:

```bash
uv run python -m scenarios.session_key_transaction_scenario
```

This scenario will:

1. Create an account and authenticate
2. Wait for you to send funds to the account (5 minute timeout)
3. Transfer majority of funds to a session key account
4. Verify funds are on the session key account
5. Send funds back to the original account using the session key
6. Verify that funds are returned
7. Clean up by deleting the session key

**Note:** You'll need to send funds to the displayed address during step 2. The scenario will wait up to 5 minutes for funds to arrive.

## Available Environments

The scenarios use the `Environment` class from `gateway.config` which includes:

- `Environment.SEPOLIA` - Sepolia testnet
- `Environment.DEXYNTH` - DEXYNTH gateway
- `Environment.UAT` - UAT testnet
- `Environment.LOCAL` - Local development (default: http://127.0.0.1:3000/v1)

You can modify the environment in each scenario file by changing the `env` variable.

## Project Structure

```
gw_testing/
├── gateway/           # Gateway client library
│   ├── client.py     # GatewayClient implementation
│   └── config.py     # Network configuration
├── scenarios/        # Test scenarios
│   ├── basic_auth.py
│   ├── basic_session_key_scenario.py
│   └── session_key_transaction_scenario.py
└── pyproject.toml     # Project dependencies
```
