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

### Session Key Return Funds on Delete

Test that funds are automatically returned when a session key is deleted:

```bash
uv run python -m scenarios.session_key_return_funds_on_delete_scenario
```

This scenario will:

1. Create an account and authenticate
2. Wait for you to send funds to the account (5 minute timeout)
3. Transfer majority of funds to a session key account
4. Verify funds are on the session key account
5. Delete the session key (funds should be automatically returned)
6. Verify that funds are automatically returned to the original account

**Note:** You'll need to send funds to the displayed address during step 2. The scenario will wait up to 5 minutes for funds to arrive. Unlike the session key transaction scenario, this one tests automatic fund return when deleting a session key, rather than manually sending funds back.

### Fund Expiration Stress Test

Test fund expiration with multiple users and session keys:

```bash
uv run python -m scenarios.fund_expiration_stress_scenario
```

This scenario will:

1. Create a main account and wait for funds
2. Create multiple users (configurable, default: 5)
3. Create multiple session keys per user (configurable, default: 3)
4. Distribute funds from main account to all session keys
5. Wait for fund expiration (configurable, default: 10 minutes)
6. Verify that funds expired and returned to main account
7. Verify that session key balances are zero or close to zero
8. Send all remaining funds back to a configurable return address (default: `0x10DeC2baF2944Ce99710B4319Ec7C7B619E70a0E`)

**Configuration:** You can modify the following constants at the top of the scenario file:

- `NUM_USERS` - Number of users to create (default: 5)
- `SESSION_KEYS_PER_USER` - Number of session keys per user (default: 3)
- `EXPIRATION_WAIT_SECONDS` - Time to wait for fund expiration in seconds (default: 600 = 10 minutes)
- `RETURN_ADDRESS` - Address to send remaining funds to (default: `0x10DeC2baF2944Ce99710B4319Ec7C7B619E70a0E`)

**Note:** You'll need to send funds to the displayed main account address. The scenario will wait up to 5 minutes for funds to arrive. This is a stress test that creates many session keys and tests fund expiration behavior.

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
│   ├── session_key_transaction_scenario.py
│   ├── session_key_return_funds_on_delete_scenario.py
│   └── fund_expiration_stress_scenario.py
└── pyproject.toml     # Project dependencies
```
