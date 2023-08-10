import random
import time

from loguru import logger
from web3 import Web3
from config import PANCAKE_ROUTER_ABI, PANCAKE_CONTRACTS, ZKSYNC_TOKENS
from .account import Account


class Pancake(Account):
    def __init__(self, private_key: str, proxy: str) -> None:
        super().__init__(private_key=private_key, proxy=proxy, chain="zksync")

        self.swap_contract = self.get_contract(PANCAKE_CONTRACTS["router"], PANCAKE_ROUTER_ABI)
        self.deadline = int(time.time()) + 1000000
        self.tx = {
            "from": self.address,
            "gas": random.randint(2900000, 3100000),
            "gasPrice": Web3.to_wei("0.25", "gwei"),
            "nonce": self.w3.eth.get_transaction_count(self.address)
        }

    def swap_to_token(self, from_token: str, to_token: str, amount: int):
        amount = Web3.to_wei(amount, "ether")
        balance = self.w3.eth.get_balance(self.address)
        self.tx.update({"value": amount})

        contract_txn = self.swap_contract.functions.swapExactETHForTokens(
            0,
            [Web3.to_checksum_address(ZKSYNC_TOKENS[from_token]),
             Web3.to_checksum_address(ZKSYNC_TOKENS[to_token])],
            self.address,
            self.deadline
        ).build_transaction(self.tx)

        return amount, balance, contract_txn

    def swap_to_eth(self, from_token: str, to_token: str, amount: int):
        token_address = Web3.to_checksum_address(ZKSYNC_TOKENS[from_token])
        token_contract = self.get_contract(token_address)
        amount = int(amount * 10 ** token_contract.functions.decimals().call())
        balance = self.get_balance(token_address)["balance_wei"]

        self.approve(amount, token_address, PANCAKE_CONTRACTS["router"])
        self.tx.update({"nonce": self.w3.eth.get_transaction_count(self.address)})

        contract_txn = self.swap_contract.functions.swapExactTokensForETH(
            amount,
            0,
            [Web3.to_checksum_address(ZKSYNC_TOKENS[from_token]),
             Web3.to_checksum_address(ZKSYNC_TOKENS[to_token])],
            self.address,
            self.deadline
        ).build_transaction(self.tx)

        return amount, balance, contract_txn

    def swap(self, from_token: str, to_token: str, min_swap: float, max_swap: float, decimal: int):
        amount = round(random.uniform(min_swap, max_swap), decimal)

        logger.info(f"[{self.address}] Swap – {from_token} -> {to_token} | {amount} {from_token}")

        if from_token == "ETH":
            amount, balance, contract_txn = self.swap_to_token(from_token, to_token, amount)
        else:
            amount, balance, contract_txn = self.swap_to_eth(from_token, to_token, amount)

        if amount < balance:

            signed_txn = self.sign(contract_txn)

            txn_hash = self.send_raw_transaction(signed_txn)

            self.wait_until_tx_finished(txn_hash.hex())
        else:
            logger.error(f"[{self.address}] Insufficient funds!")
