import os
import sys
import time
import subprocess
import requests

def test_standalone():
    port = 8091
    env = os.environ.copy()
    env["DOCUMENT_AGENT_PORT"] = str(port)
    exe_path = os.path.abspath(r"backend-dist\document-agent-backend\document-agent-backend.exe")
    
    print(f"Launching standalone backend: {exe_path} on port {port}")
    proc = subprocess.Popen([exe_path, "--host", "127.0.0.1", "--port", str(port)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    try:
        base_url = f"http://127.0.0.1:{port}"
        # Wait for startup
        healthy = False
        for _ in range(30):
            try:
                r = requests.get(f"{base_url}/health", timeout=1)
                if r.status_code == 200:
                    healthy = True
                    print(f"Standalone /health OK: {r.json()}")
                    break
            except Exception:
                pass
            time.sleep(1)
            
        if not healthy:
            print("Failed to reach standalone /health within 30 seconds.")
            return False

        # Test POST /query (synchronous backwards-compatibility)
        r = requests.post(f"{base_url}/query", json={"query": "Find Nikhil CS"}, timeout=15)
        print(f"POST /query status: {r.status_code}, data: {r.json().get('message')[:60] if r.json().get('message') else ''}")
        assert r.status_code == 200

        # Test POST /query/stream (SSE streaming)
        r = requests.post(f"{base_url}/query/stream", json={"query": "Find Nikhil CS"}, stream=True, timeout=15)
        print(f"POST /query/stream status: {r.status_code}")
        assert r.status_code == 200
        
        events = []
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    events.append(decoded[6:])
        print(f"Received {len(events)} stream events from standalone backend.")
        assert len(events) >= 2
        print("ALL STANDALONE BACKEND TESTS PASSED!")
        return True

    finally:
        print("Terminating standalone backend process...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Standalone backend terminated.")

if __name__ == "__main__":
    success = test_standalone()
    sys.exit(0 if success else 1)
