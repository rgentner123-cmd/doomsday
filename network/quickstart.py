#!/usr/bin/env python3
"""
Verify Doomsday Proof‑of‑Escrow details on‑chain.

Escrow ID: escrow_doom_0010
Expected reward: 1,500.00 wDOOM (18 decimals)
Vault address: 0xdoom1caea0957fb471c2b83940cc2feb421abad938dfbdef662de
"""

import json
import os
import sys
from decimal import Decimal

from web3 import Web3
from web3.middleware import geth_poa_middleware

# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------
# Replace with your own RPC endpoint (Infura, Alchemy, etc.)
RPC_URL = os.getenv("ETH_RPC_URL", "https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID")

# Escrow contract address (replace with the actual address)
ESCROW_CONTRACT_ADDRESS = Web3.to_checksum_address(
    "0x623c84A5E04bF715018203334b0eFE41696eBC3E"
)

# Minimal ABI containing only the function we need.
# Adjust the function name/types according to the real contract.
ESCROW_ABI = json.loads(
    """
    [
        {
            "inputs": [
                {"internalType":"bytes32","name":"escrowId","type":"bytes32"}
            ],
            "name":"getEscrow",
            "outputs":[
                {"internalType":"address","name":"vault","type":"address"},
                {"internalType":"address","name":"token","type":"address"},
                {"internalType":"uint256","name":"reward","type":"uint256"},
                {"internalType":"address","name":"miner","type":"address"},
                {"internalType":"address","name":"referrer","type":"address"}
            ],
            "stateMutability":"view",
            "type":"function"
        }
    ]
    """
)

# Expected values
EXPECTED_ESCROW_ID = "escrow_doom_0010"
EXPECTED_REWARD_WDOOM = Decimal("1500")
TOKEN_WDOOM_ADDRESS = Web3.to_checksum_address(
    "0x623c84A5E04bF715018203334b0eFE41696eBC3E"
)  # same as escrow vault token address in description
VAULT_ADDRESS = Web3.to_checksum_address(
    "0xdoom1caea0957fb471c2b83940cc2feb421abad938dfbdef662de".replace("doom", "0x")
)

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def to_bytes32(text: str) -> bytes:
    """Convert a string to a bytes32 hex value."""
    return Web3.keccak(text=text)  # using keccak as example identifier
    # If the contract stores the raw string, use:
    # return text.encode("utf-8").ljust(32, b"\0")

def format_wei_to_decimal(value_wei: int, decimals: int = 18) -> Decimal:
    return Decimal(value_wei) / Decimal(10**decimals)


# -------------------------------------------------
# MAIN LOGIC
# -------------------------------------------------
def main() -> None:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    # Some L2 networks (e.g., Arbitrum, Optimism) need POA middleware
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    if not w3.is_connected():
        sys.exit("❌ Unable to connect to Ethereum node.")

    escrow_contract = w3.eth.contract(
        address=ESCROW_CONTRACT_ADDRESS,
        abi=ESCROW_ABI,
    )

    # Build escrowId (bytes32). Adjust if contract expects plain string hash.
    escrow_id_bytes = to_bytes32(EXPECTED_ESCROW_ID)

    try:
        vault, token, reward_wei, miner, referrer = escrow_contract.functions.getEscrow(
            escrow_id_bytes
        ).call()
    except Exception as e:
        sys.exit(f"❌ Call to getEscrow failed: {e}")

    # --------------------
    # VALIDATION
    # --------------------
    errors = []

    # Vault address check
    if vault.lower() != VAULT_ADDRESS.lower():
        errors.append(
            f"Vault mismatch: on‑chain {vault} vs expected {VAULT_ADDRESS}"
        )

    # Token address check
    if token.lower() != TOKEN_WDOOM_ADDRESS.lower():
        errors.append(
            f"Token mismatch: on‑chain {token} vs expected {TOKEN_WDOOM_ADDRESS}"
        )

    # Reward amount check
    reward_decimal = format_wei_to_decimal(reward_wei, 18)
    if reward_decimal != EXPECTED_REWARD_WDOOM:
        errors.append(
            f"Reward mismatch: on‑chain {reward_decimal} wDOOM vs expected {EXPECTED_REWARD_WDOOM}"
        )

    # Output results
    if errors:
        print("❌ Escrow verification FAILED:")
        for err in errors:
            print(f"   • {err}")
        sys.exit(1)
    else:
        print("✅ Escrow verification PASSED")
        print(f"   • Vault: {vault}")
        print(f"   • Token: {token}")
        print(f"   • Reward: {reward_decimal} wDOOM")
        print(f"   • Miner: {miner}")
        print(f"   • Referrer: {referrer}")


if __name__ == "__main__":
    main()