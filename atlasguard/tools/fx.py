"""Exchange rates: REAL mid-market data fetched at runtime, with honest fallbacks.

Order: live API -> recent local cache -> clearly-labelled offline snapshot.
The returned `source` field is always shown to the user, so a stale or offline
rate is never presented as live.
"""
import json
import os
import time

import requests

CACHE_FILE = os.environ.get("AG_FX_CACHE", "fx_cache.json")
CACHE_MAX_AGE_S = 6 * 3600
API = "https://open.er-api.com/v6/latest/{base}"

# Last-resort approximate values (units of quote per 1 base). Used ONLY when
# there is no network and no cache; labelled OFFLINE_SNAPSHOT in the output.
_OFFLINE = {
    "PKR": {"EUR": 0.0033, "USD": 0.0036, "GBP": 0.0028, "CAD": 0.0050, "AUD": 0.0055},
}


def _read_cache() -> dict:
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def get_rate(base: str, quote: str) -> dict:
    base, quote = base.upper(), quote.upper()
    if base == quote:
        return {"rate": 1.0, "source": "identity", "as_of": None}
    if os.environ.get("AG_OFFLINE") != "1":
        try:
            r = requests.get(API.format(base=base), timeout=6)
            r.raise_for_status()
            data = r.json()
            if data.get("result") == "success" and quote in data["rates"]:
                cache = _read_cache()
                cache[base] = {"ts": time.time(), "rates": data["rates"],
                               "as_of": data.get("time_last_update_utc")}
                with open(CACHE_FILE, "w") as f:
                    json.dump(cache, f)
                return {"rate": float(data["rates"][quote]), "source": "LIVE",
                        "as_of": data.get("time_last_update_utc")}
        except Exception:
            pass
        cached = _read_cache().get(base)
        if cached and quote in cached["rates"]:
            age_h = (time.time() - cached["ts"]) / 3600
            label = "CACHED (%.1fh old)" % age_h
            return {"rate": float(cached["rates"][quote]), "source": label, "as_of": cached["as_of"]}
    snap = _OFFLINE.get(base, {}).get(quote)
    if snap is None:
        inverse = _OFFLINE.get(quote, {}).get(base)
        if inverse:
            snap = 1.0 / inverse
    if snap is None:
        raise ValueError(f"No rate available for {base}->{quote}")
    return {"rate": snap, "source": "OFFLINE_SNAPSHOT (approximate)", "as_of": None}
