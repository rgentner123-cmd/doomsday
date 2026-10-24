#!/usr/bin/env python3
"""
doomsday_airdrop.py

Poll GitHub stargazers for the doomsday-network/doomsday repository every 90 seconds
and dispense 500 wDOOM tokens on Base Mainnet (chain ID 8453) to new stargazers.
"""

import os
import sys
import json
import time
import logging
from typing import Set, List, Dict

import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_typing import ChecksumAddress

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
GITHUB_REPO = "doomsday-network/doomsday"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/stargazers"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # optional: for higher rate limits
POLL_INTERVAL = 90  # seconds

BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://base-mainnet.public.blastapi.io")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")  # account that holds wDOOM
WDoom_ADDRESS = Web3.to_checksum_address(
    os.getenv("WDoom_ADDRESS", "0x623c84A5E04bF715018203334b0eFE41696eBC3E")
)

# ERC20 minimal ABI (balanceOf, transfer)
ERC20_ABI = json.loads(
    """[
        {"constant":true,"inputs":[{"name":"account","type":"address"}],
         "name":"balanceOf","outputs":[{"name":"","type":"uint256"}],
         "type":"function"},
        {"constant":false,"inputs":[{"name":"recipient","type":"address"},
                                    {"name":"amount","type":"uint256"}],
         "name":"transfer","outputs":[{"name":"","type":"bool"}],
         "type":"function"}
    ]"""
)

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("doomsday_airdrop")

# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
def get_github_headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3.star+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def fetch_all_stargazers() -> List[Dict]:
    """Return list of stargazer dicts from GitHub (includes `user` field)."""
    stargazers: List[Dict] = []
    page = 1
    per_page = 100
    session = requests.Session()
    while True:
        params = {"page": page, "per_page": per_page}
        resp = session.get(
            GITHUB_API_URL, headers=get_github_headers(), params=params, timeout=10
        )
        if resp.status_code != 200:
            logger.error(
                "GitHub API error %s: %s", resp.status_code, resp.text
            )
            raise RuntimeError("Failed to fetch stargazers")
        batch = resp.json()
        if not batch:
            break
        stargazers.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return stargazers


def load_processed_set(path: str) -> Set[str]:
    """Load set of GitHub usernames already airdropped."""
    if not os.path.isfile(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_processed_set(path: str, users: Set[str]) -> None:
    """Persist processed usernames, one per line."""
    with open(path, "w", encoding="utf-8") as f:
        for user in sorted(users):
            f.write(f"{user}\n")


def eth_address_from_github(user: Dict) -> ChecksumAddress | None:
    """
    Attempt to resolve an Ethereum address from a GitHub user profile.
    The function looks for a public email that matches an ENS reverse record
    or checks for a `wallet` field in the user's bio if present.
    This implementation is a placeholder; in production replace with a reliable method.
    """
    # Example placeholder: use `user["login"]` as ENS name and resolve
    ens_name = f"{user['login']}.eth"
    try:
        address = w3.ens.address(ens_name)
        if address:
            return Web3.to_checksum_address(address)
    except Exception:
        pass
    return None


def send_wdoom(to_address: ChecksumAddress, amount_wei: int) -> str:
    """Transfer wDOOM tokens and return the transaction hash."""
    nonce = w3.eth.get_transaction_count(account.address)
    tx = wdoom_contract.functions.transfer(to_address, amount_wei).build_transaction(
        {
            "chainId": 8453,
            "gas": 100_000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    logger.info("Sent %s wei to %s, tx hash %s", amount_wei, to_address, tx_hash.hex())
    return tx_hash.hex()


# --------------------------------------------------------------------------- #
# Main execution
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if not PRIVATE_KEY:
        logger.critical("PRIVATE_KEY environment variable not set")
        sys.exit(1)

    # Initialise Web3
    w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)  # Base uses PoA
    if not w3.is_connected():
        logger.critical("Unable to connect to Base RPC at %s", BASE_RPC_URL)
        sys.exit(1)

    account = Account.from_key(PRIVATE_KEY)
    wdoom_contract = w3.eth.contract(address=WDoom_ADDRESS, abi=ERC20_ABI)

    processed_path = "processed_stargazers.txt"
    processed_users = load_processed_set(processed_path)

    logger.info("Starting doomsday airdrop service (poll every %s sec)", POLL_INTERVAL)

    try:
        while True:
            try:
                stargazers = fetch_all_stargazers()
            except Exception as exc:
                logger.exception("Failed to fetch stargazers: %s", exc)
                time.sleep(POLL_INTERVAL)
                continue

            new_users = [
                sg["user"]["login"]
                for sg in stargazers
                if sg["user"]["login"] not in processed_users
            ]

            if new_users:
                logger.info("Found %d new stargazer(s): %s", len(new_users), ", ".join(new_users))
            else:
                logger.debug("No new stargazers found")

            for login in new_users:
                # Retrieve the full user object for address resolution
                user_resp = requests.get(
                    f"https://api.github.com/users/{login}",
                    headers=get_github_headers(),
                    timeout=10,
                )
                if user_resp.status_code != 200:
                    logger.warning("Unable to fetch user %s: %s", login, user_resp.text)
                    continue
                user_data = user_resp.json()
                recipient = eth_address_from_github(user_data)
                if not recipient:
                    logger.warning("No Ethereum address resolvable for GitHub user %s", login)
                    continue

                try:
                    send_wdoom(recipient, w3.to_wei(500, "ether"))
                    processed_users.add(login)
                except Exception as exc:
                    logger.exception("Token transfer failed for %s: %s", login, exc)

            # Persist state after each cycle
            save_processed_set(processed_path, processed_users)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Shutting down doomsday airdrop service")
        save_processed_set(processed_path, processed_users)