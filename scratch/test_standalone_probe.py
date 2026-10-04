import urllib.request
import json

def test_probe():
    url = "http://127.0.0.1:8765/query"
    payload = json.dumps({"query": "Find Nikhil CS"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("[SUCCESS] POST /query response:")
        print(json.dumps(res, indent=2))
        assert res["success"] is True
        assert res["action"] == "search"
        assert "Nikhil CS" in res["message"]
        print("[VERIFIED] V3 structured contract satisfied.")

if __name__ == "__main__":
    test_probe()
