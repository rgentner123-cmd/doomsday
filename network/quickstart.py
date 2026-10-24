import json
import os
from web3 import Web3
from eth_account import Account

# -------------------- Configuration --------------------
# RPC endpoint (Infura, Alchemy, or your own node)
RPC_URL = "https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID"

# Escrow contract address (replace with the actual address if known)
ESCROW_CONTRACT_ADDRESS = "0x623c84A5E04bF715018203334b0eFE41696eBC3E"

# ABI snippet for the escrow contract (add the full ABI as needed)
ESCROW_ABI = json.loads("""[
    {
        "inputs": [{"internalType":"bytes32","name":"escrowId","type":"bytes32"}],
        "name":"getEscrowInfo",
        "outputs":[
            {"internalType":"address","name":"rewardToken","type":"address"},
            {"internalType":"uint256","name":"rewardAmount","type":"uint256"},
            {"internalType":"address","name":"beneficiary","type":"address"},
            {"internalType":"bool","name":"claimed","type":"bool"}
        ],
        "stateMutability":"view",
        "type":"function"
    },
    {
        "inputs":[{"internalType":"bytes32","name":"escrowId","type":"bytes32"}],
        "name":"claim",
        "outputs":[],
        "stateMutability":"nonpayable",
        "type":"function"
    }
]""")

# Escrow ID (as hex string, 32 bytes)
ESCROW_ID = Web3.keccak(text="escrow_doom_0010")  # example derivation; replace if exact ID is known

# Your wallet (private key should be stored securely, e.g., in env var)
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
if not PRIVATE_KEY:
    raise EnvironmentError("Set PRIVATE_KEY environment variable with your wallet's private key.")

ACCOUNT = Account.from_key(PRIVATE_KEY)
WALLET_ADDRESS = ACCOUNT.address

# -------------------- Web3 Setup --------------------
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise ConnectionError("Unable to connect to the Ethereum node.")

escrow_contract = w3.eth.contract(address=ESCROW_CONTRACT_ADDRESS, abi=ESCROW_ABI)

# -------------------- Helper Functions --------------------
def get_escrow_info(escrow_id: bytes) -> dict:
    """Fetch escrow details from the contract."""
    info = escrow_contract.functions.getEscrowInfo(escrow_id).call()
    return {
        "reward_token": info[0],
        "reward_amount": w3.from_wei(info[1], "ether"),
        "beneficiary": info[2],
        "claimed": info[3],
    }

def claim_escrow(escrow_id: bytes) -> str:
    """Send a transaction to claim the escrowed reward."""
    nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
    tx = escrow_contract.functions.claim(escrow_id).build_transaction({
        "from": WALLET_ADDRESS,
        "nonce": nonce,
        "gas": 250_000,
        "gasPrice": w3.to_wei("30", "gwei"),
        "chainId": 1,  # Mainnet; use 5 for Goerli, etc.
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    return tx_hash.hex()

# -------------------- Main Flow --------------------
if __name__ == "__main__":
    # 1. Query escrow info
    info = get_escrow_info(ESCROW_ID)
    print("Escrow Info:")
    print(f"  Reward Token : {info['reward_token']}")
    print(f"  Reward Amount: {info['reward_amount']} tokens")
    print(f"  Beneficiary  : {info['beneficiary']}")
    print(f"  Already Claimed? {info['claimed']}")

    # 2. Claim if not yet claimed and you are the beneficiary
    if not info["claimed"] and info["beneficiary"].lower() == WALLET_ADDRESS.lower():
        tx_hash = claim_escrow(ESCROW_ID)
        print(f"Claim transaction submitted. TxHash: {tx_hash}")
    else:
        print("No claim action performed.")