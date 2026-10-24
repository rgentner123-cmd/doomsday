import os
import json
import sys
import asyncio
from pathlib import Path
from typing import List

import aiohttp
from web3 import Web3
from web3.middleware import geth_poa_middleware

# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
WDOOM_ADDRESS = "0x623c84A5E04bF715018203334b0eFE41696eBC3E"
WDOOM_ABI = json.loads(
    """[
        {"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
        {"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
        {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
        {"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
    ]"""
)

# GitHub settings for the 4‑repo star bounty
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_LIST = [
    "owner1/repoA",
    "owner2/repoB",
    "owner3/repoC",
    "owner4/repoD",
]

# ----------------------------------------------------------------------
# WEB3 HELPERS
# ----------------------------------------------------------------------
w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
wdoom = w3.eth.contract(address=Web3.to_checksum_address(WDOOM_ADDRESS), abi=WDOOM_ABI)


def get_wdoom_info() -> dict:
    """Return name, symbol and decimals of the wDOOM token."""
    return {
        "name": wdoom.functions.name().call(),
        "symbol": wdoom.functions.symbol().call(),
        "decimals": wdoom.functions.decimals().call(),
    }


def get_balance(address: str) -> float:
    """Return the human‑readable wDOOM balance of `address`."""
    checksum = Web3.to_checksum_address(address)
    raw = wdoom.functions.balanceOf(checksum).call()
    decimals = wdoom.functions.decimals().call()
    return raw / (10 ** decimals)


# ----------------------------------------------------------------------
# GITHUB STAR BOUNTY LOGIC
# ----------------------------------------------------------------------
async def star_repo(session: aiohttp.ClientSession, repo: str) -> bool:
    """Star a single GitHub repo. Returns True on success."""
    url = f"https://api.github.com/user/starred/{repo}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with session.put(url, headers=headers) as resp:
        return resp.status in (204, 304)


async def star_all_repos(repos: List[str]) -> dict:
    """Star each repo in `repos`. Returns a mapping of repo -> success."""
    results = {}
    async with aiohttp.ClientSession() as session:
        tasks = [star_repo(session, repo) for repo in repos]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        for repo, outcome in zip(repos, outcomes):
            results[repo] = outcome if isinstance(outcome, bool) else False
    return results


# ----------------------------------------------------------------------
# MAIN ENTRYPOINT
# ----------------------------------------------------------------------
def print_usage() -> None:
    print("Usage:")
    print("  python bounty_tool.py balance <address>")
    print("  python bounty_tool.py info")
    print("  python bounty_tool.py star")
    print("")
    print("Environment variables:")
    print("  BASE_RPC_URL   (default: https://mainnet.base.org)")
    print("  GITHUB_TOKEN   (required for 'star' command)")


def main() -> None:
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "info":
        info = get_wdoom_info()
        print(json.dumps(info, indent=2))

    elif cmd == "balance":
        if len(sys.argv) != 3:
            print("Error: address required for balance command.")
            sys.exit(1)
        address = sys.argv[2]
        try:
            bal = get_balance(address)
            print(f"wDOOM balance of {address}: {bal}")
        except Exception as e:
            print(f"Failed to fetch balance: {e}")

    elif cmd == "star":
        if not GITHUB_TOKEN:
            print("Error: GITHUB_TOKEN environment variable not set.")
            sys.exit(1)
        print("Starring repos for bounty...")
        results = asyncio.run(star_all_repos(REPO_LIST))
        for repo, ok in results.items():
            status = "✅" if ok else "❌"
            print(f"{status} {repo}")

    else:
        print(f"Unknown command: {cmd}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()