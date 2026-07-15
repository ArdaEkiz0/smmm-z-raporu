"""Cloudflare cache otomatik temizleme. Her deploy'da calisir."""
import os
import json
import urllib.request
import urllib.error

CF_TOKEN = os.environ.get("CF_API_TOKEN", "")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID", "9e8d7f67e7da6a88d76b2228e1c1a71c")
CF_ZONE_NAME = os.environ.get("CF_ZONE_NAME", "gurcanekiz.xyz")


def purge_cache():
    if not CF_TOKEN or not CF_ZONE_ID:
        print("[cache_purge] CF_API_TOKEN veya CF_ZONE_ID tanimli degil, atlanıyor.")
        return False

    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/purge_cache"
    payload = json.dumps({"purge_everything": True}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="DELETE")
    req.add_header("Authorization", f"Bearer {CF_TOKEN}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success"):
                print(f"[cache_purge] {CF_ZONE_NAME} cache temizlendi!")
                return True
            else:
                print(f"[cache_purge] Hata: {data.get('errors', [])}")
                return False
    except Exception as e:
        print(f"[cache_purge] Baglanti hatasi: {e}")
        return False


if __name__ == "__main__":
    purge_cache()
