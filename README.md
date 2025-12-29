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
│   └── basic_session_key_scenario.py
└── pyproject.toml     # Project dependencies
```
