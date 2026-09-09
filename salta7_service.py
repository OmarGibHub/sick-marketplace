import time
import threading
import requests
import json
import os
import re
from typing import Optional, Dict, Any, Tuple, List

from database import update_order_status

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def clean_invite(invite: str) -> str:
    """Extracts raw invite code from discord.gg URLs or codes."""
    if not invite:
        return ""
    clean = str(invite).strip()
    match = re.search(r"(?:discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)?([a-zA-Z0-9_-]+)", clean)
    if match:
        return match.group(1)
    return clean

def extract_clean_token(raw_line: str) -> Optional[str]:
    """
    Extracts valid Discord token from any format:
    - Pure token: 'MTUzOTcx...'
    - Email:Pass:Token: 'user@email.com:Pass:MTUzOTcx...'
    - Email:Pass:Token:Refresh: 'user@email.com:Pass:MTUzOTcx...:refresh'
    """
    if not raw_line or not isinstance(raw_line, str):
        return None

    line = raw_line.strip().strip('"\'`')
    if not line or line.startswith("#"):
        return None

    if ":" in line:
        parts = line.split(":")
        for part in reversed(parts):
            p = part.strip()
            if len(p) >= 50 and "@" not in p and "/" not in p:
                return p
        if len(parts[-1].strip()) >= 24:
            return parts[-1].strip()

    token_match = re.search(r'([A-Za-z0-9_\-]{24,28}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,38})', line)
    if token_match:
        return token_match.group(1)

    if len(line) >= 50:
        return line
    return None

def parse_token_list(raw_text: str) -> List[str]:
    if not raw_text:
        return []
    lines = raw_text.strip().splitlines()
    tokens = []
    seen = set()
    for l in lines:
        tok = extract_clean_token(l)
        if tok and tok not in seen:
            tokens.append(tok)
            seen.add(tok)
    return tokens

class Salta7Service:
    extract_clean_token = staticmethod(extract_clean_token)
    parse_token_list = staticmethod(parse_token_list)

    def __init__(self):
        cfg = load_config()
        salta7_cfg = cfg.get("salta7", {})
        self.api_key = salta7_cfg.get("api_key", "JUHX3K3Z8FZD4FN5C2M6I2KZDMZS2JIG").strip()
        self.base_url = salta7_cfg.get("base_url", "https://salta7.store").strip().rstrip("/")
        self.default_mode = salta7_cfg.get("default_mode", "stock")

    def get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
            "api-key": self.api_key,
            "User-Agent": "PrimeBoosts-Platform/3.0"
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> Tuple[bool, Dict[str, Any]]:
        clean_endpoint = endpoint.lstrip("/")
        urls_to_try = [
            f"{self.base_url}/{clean_endpoint}",
            f"{self.base_url}/api/{clean_endpoint}"
        ]
        
        last_error = "Unknown error"
        for url in urls_to_try:
            try:
                kwargs.setdefault("headers", self.get_headers())
                kwargs.setdefault("timeout", 20)
                resp = requests.request(method, url, **kwargs)

                if resp.status_code in [200, 201]:
                    try:
                        return True, resp.json()
                    except Exception:
                        return True, {"status": "ok", "raw": resp.text}
                elif resp.status_code == 404:
                    continue
                elif resp.status_code == 401:
                    return False, {"error": "Cloud Engine authentication error"}
                elif resp.status_code == 402:
                    return False, {"error": "Cloud Engine capacity reached"}
                else:
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error") or err_json.get("message") or resp.text[:120]
                    except Exception:
                        err_msg = f"HTTP {resp.status_code}: {resp.text[:120]}"
                    return False, {"error": err_msg, "status_code": resp.status_code}
            except Exception as e:
                last_error = str(e)

        return False, {"error": last_error}

    def get_balance(self) -> Tuple[bool, Dict[str, Any]]:
        return self._request("GET", "/balance")

    def get_task_status(self, job_id: str) -> Tuple[bool, Dict[str, Any]]:
        return self._request("GET", f"/task/status?job_id={job_id}")

    def dispatch_boost_order(
        self,
        order_id: int,
        invite: str,
        boosts: int = 14,
        mode: str = "stock",
        tokens: Optional[List[str]] = None,
        boosts_needed: Optional[int] = None,
        humanize: Optional[Dict[str, Any]] = None,
        nickname: str = "",
        **kwargs
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        if nickname:
            if not humanize:
                humanize = {}
            if "nickname" not in humanize:
                humanize["nickname"] = nickname

        code = clean_invite(invite)
        if not code:
            update_order_status(order_id, "failed", error_msg="Invalid Discord invite URL.")
            return False, "Invalid Discord invite link.", None

        clean_mode = "byot" if str(mode).lower() in ["byot", "tokens", "own"] else "stock"

        payload = {
            "tool": "boost",
            "mode": clean_mode,
            "invite": code
        }

        if clean_mode == "stock":
            payload["boosts"] = int(boosts)
        elif clean_mode == "byot":
            payload["tokens"] = tokens or []
            if boosts_needed is not None:
                payload["boosts_needed"] = int(boosts_needed)
            elif boosts:
                payload["boosts_needed"] = int(boosts)

        if humanize and any(humanize.values()):
            clean_humanize = {}
            if humanize.get("nickname"):
                clean_humanize["nickname"] = str(humanize["nickname"]).strip()
            if humanize.get("bio"):
                clean_humanize["bio"] = str(humanize["bio"]).strip()
            if humanize.get("avatar"):
                clean_humanize["avatar"] = str(humanize["avatar"]).strip()
            if humanize.get("banner"):
                clean_humanize["banner"] = str(humanize["banner"]).strip()
            if clean_humanize:
                payload["humanize"] = clean_humanize

        ok, resp = self._request("POST", "/task/create", json=payload)
        if ok:
            job_id = str(resp.get("job_id") or resp.get("task_id") or resp.get("id") or "")
            update_order_status(order_id, "in_progress", salta7_job_id=job_id)
            
            if job_id:
                threading.Thread(target=self._poll_task_worker, args=(order_id, job_id), daemon=True).start()
                
            return True, f"Boost task #{job_id} created successfully ({clean_mode.upper()} mode)!", {"job_id": job_id}
        else:
            err = resp.get("error", "Cloud API dispatch failed.")
            update_order_status(order_id, "failed", error_msg=err)
            return False, err, None

    def _poll_task_worker(self, order_id: int, job_id: str):
        start_time = time.time()
        max_duration = 600 # 10 minutes
        
        while time.time() - start_time < max_duration:
            time.sleep(4)
            ok, data = self.get_task_status(job_id)
            if not ok:
                continue

            status = str(data.get("status", "")).lower()
            if status in ["completed", "success", "finished", "done"]:
                update_order_status(order_id, "completed", salta7_job_id=job_id)
                return
            elif status in ["failed", "error", "cancelled", "canceled"]:
                err = data.get("error", "Cloud boost task failed")
                update_order_status(order_id, "failed", salta7_job_id=job_id, error_msg=err)
                return

        update_order_status(order_id, "timeout", salta7_job_id=job_id, error_msg="Task timed out after 10m.")

salta7_service = Salta7Service()
