import time
import requests
import json
import os
from typing import Optional, Dict, Any, Tuple

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

class CryptoService:
    def __init__(self):
        cfg = load_config()
        self.wallet_address = cfg.get("crypto", {}).get("ltc_wallet_address", "LM9NsXJGYdCzK6nPWPS4tHXZTKKUknERRc").strip()
        self.currency = "LTC"
        self._cached_rate: float = 75.0 # Fallback 1 LTC = ~75 EUR
        self._last_rate_time: float = 0.0

    def get_ltc_eur_rate(self) -> float:
        """Returns the current exchange rate: 1 LTC = X EUR"""
        now = time.time()
        if now - self._last_rate_time < 120 and self._cached_rate > 0:
            return self._cached_rate

        # 1. Try Binance API
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=LTCEUR", timeout=5)
            if r.status_code == 200:
                price = float(r.json().get("price", 0))
                if price > 0:
                    self._cached_rate = round(price, 2)
                    self._last_rate_time = now
                    return self._cached_rate
        except Exception:
            pass

        # 2. Try CoinGecko API
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=eur", timeout=5)
            if r.status_code == 200:
                price = float(r.json().get("litecoin", {}).get("eur", 0))
                if price > 0:
                    self._cached_rate = round(price, 2)
                    self._last_rate_time = now
                    return self._cached_rate
        except Exception:
            pass

        return self._cached_rate

    def eur_to_ltc(self, eur_amount: float) -> float:
        rate = self.get_ltc_eur_rate()
        if rate <= 0:
            rate = 75.0
        return round(eur_amount / rate, 8)

    def ltc_to_eur(self, ltc_amount: float) -> float:
        rate = self.get_ltc_eur_rate()
        return round(ltc_amount * rate, 2)

    def get_payment_info(self, amount_eur: float = 0.20) -> Dict[str, Any]:
        rate = self.get_ltc_eur_rate()
        ltc_amount = self.eur_to_ltc(amount_eur)
        
        # Standard BIP21 URI for crypto wallets and QR code scanning
        uri = f"litecoin:{self.wallet_address}?amount={ltc_amount}&label=12b00%20Marketplace"
        
        return {
            "wallet_address": self.wallet_address,
            "currency": "LTC",
            "amount_eur": round(amount_eur, 2),
            "amount_ltc": ltc_amount,
            "exchange_rate_eur": rate,
            "uri": uri,
            "instructions": "Send the exact LTC amount to the address above. Verification takes 1-2 minutes."
        }

    def get_recent_incoming_transactions(self, limit: int = 15) -> list:
        """
        Fetches latest incoming transactions to the official LTC wallet from blockchain.
        Filters OUT outgoing/self-spending change transactions where inputs come from our wallet.
        Returns: list of dicts [{'tx_hash', 'amount_ltc', 'amount_eur', 'timestamp', 'confirmed'}]
        """
        results = []
        try:
            url = f"https://litecoinspace.org/api/address/{self.wallet_address}/txs"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            if r.status_code == 200:
                txs = r.json()
                for tx in txs[:limit]:
                    txid = tx.get("txid", "").strip().lower()
                    if not txid:
                        continue

                    # 1. Skip outgoing/internal change transactions where inputs originate from our wallet
                    vin = tx.get("vin", [])
                    is_outgoing = any(
                        in_tx.get("prevout", {}).get("scriptpubkey_address") == self.wallet_address
                        for in_tx in vin
                    )
                    if is_outgoing:
                        continue

                    # 2. Check outputs directed to our wallet address
                    vout = tx.get("vout", [])
                    amount_sat = 0
                    for out in vout:
                        if out.get("scriptpubkey_address") == self.wallet_address:
                            amount_sat += out.get("value", 0)
                    if amount_sat > 0:
                        amount_ltc = amount_sat / 100_000_000.0
                        amount_eur = self.ltc_to_eur(amount_ltc)
                        status_data = tx.get("status", {})
                        confirmed = bool(status_data.get("confirmed", False))
                        block_time = status_data.get("block_time", 0) or 0
                        
                        results.append({
                            "tx_hash": txid,
                            "amount_ltc": amount_ltc,
                            "amount_eur": amount_eur,
                            "timestamp": int(block_time),
                            "confirmed": confirmed
                        })
        except Exception:
            pass
        return results

    def verify_tx_on_chain(self, tx_hash: str) -> Tuple[bool, float, str]:
        """
        Queries public Litecoin block explorer API to verify transaction.
        Returns: (success, credited_eur, message)
        """
        clean_tx = tx_hash.strip().lower()
        if len(clean_tx) < 20:
            return False, 0.0, "Invalid transaction hash format."

        # Query litecoinspace.org API
        try:
            url = f"https://litecoinspace.org/api/tx/{clean_tx}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()

                # Check if this transaction is an outgoing / self-spend transaction from our wallet
                vin = data.get("vin", [])
                if any(in_tx.get("prevout", {}).get("scriptpubkey_address") == self.wallet_address for in_tx in vin):
                    return False, 0.0, "This is an outgoing transaction from the wallet, not an incoming payment."

                vout = data.get("vout", [])
                amount_sat = 0
                for out in vout:
                    if out.get("scriptpubkey_address") == self.wallet_address:
                        amount_sat += out.get("value", 0)
                
                if amount_sat > 0:
                    amount_ltc = amount_sat / 100_000_000.0
                    amount_eur = self.ltc_to_eur(amount_ltc)
                    return True, amount_eur, f"Transaction verified! Detected {amount_ltc:.6f} LTC (~{amount_eur:.2f} €)."
                else:
                    return False, 0.0, f"Transaction found, but no output sent to wallet {self.wallet_address}."
            elif r.status_code == 404:
                # Try BlockCypher API as fallback
                bc_url = f"https://api.blockcypher.com/v1/ltc/main/txs/{clean_tx}"
                bc_r = requests.get(bc_url, timeout=10)
                if bc_r.status_code == 200:
                    bc_data = bc_r.json()

                    inputs = bc_data.get("inputs", [])
                    if any(self.wallet_address in i.get("addresses", []) for i in inputs):
                        return False, 0.0, "This is an outgoing transaction from the wallet, not an incoming payment."

                    outputs = bc_data.get("outputs", [])
                    amount_sat = 0
                    for o in outputs:
                        if self.wallet_address in o.get("addresses", []):
                            amount_sat += o.get("value", 0)
                    if amount_sat > 0:
                        amount_ltc = amount_sat / 100_000_000.0
                        amount_eur = self.ltc_to_eur(amount_ltc)
                        return True, amount_eur, f"Transaction verified! Detected {amount_ltc:.6f} LTC (~{amount_eur:.2f} €)."
                    else:
                        return False, 0.0, f"Transaction found, but no output to wallet {self.wallet_address}."
                return False, 0.0, "Transaction not found on Litecoin network yet. Please wait a few seconds and retry."
            else:
                return False, 0.0, f"Blockchain API returned status {r.status_code}"
        except Exception as e:
            return False, 0.0, f"Error contacting Litecoin blockchain: {str(e)}"

crypto_service = CryptoService()
