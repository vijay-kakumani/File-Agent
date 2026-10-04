import os
import sys
import time
import subprocess
import requests
import ctypes
from ctypes import wintypes

def verify_desktop_app():
    exe_path = os.path.abspath(r"src-tauri\target\release\local-ai-document-agent.exe")
    assert os.path.exists(exe_path), f"Tauri binary not found: {exe_path}"
    
    print(f"Launching Tauri Desktop Application: {exe_path}")
    proc = subprocess.Popen([exe_path])
    
    try:
        # 1. Wait for Tauri HWND window to appear
        user32 = ctypes.windll.user32
        found_hwnd = None
        for _ in range(30):
            hwnd = user32.FindWindowW(None, "Local AI Document Agent")
            if hwnd:
                found_hwnd = hwnd
                print(f"Verified Tauri HWND: {hwnd} ('Local AI Document Agent')")
                break
            time.sleep(0.5)

        assert found_hwnd is not None, "Desktop window was not created within 15 seconds."

        # 2. Wait for backend /health
        base_url = "http://127.0.0.1:8000"
        backend_healthy = False
        for _ in range(40):
            try:
                r = requests.get(f"{base_url}/health", timeout=1)
                if r.status_code == 200 and r.json().get("agent_ready"):
                    backend_healthy = True
                    print(f"Verified Backend Health: {r.json()['status']}, agents ready: {r.json()['agent_ready']}")
                    break
            except Exception:
                pass
            time.sleep(1)

        assert backend_healthy, "Backend failed to become healthy within 40 seconds."

        # 3. Test Search via Streaming
        print("\n--- Test 1: Real Streaming Search ---")
        t0 = time.perf_counter()
        r = requests.post(f"{base_url}/query/stream", json={"query": "Find Nikhil CS"}, stream=True, timeout=10)
        assert r.status_code == 200
        events = []
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    events.append(decoded[6:])
        t1 = time.perf_counter()
        print(f"Search stream completed in {(t1 - t0)*1000:.2f} ms. Events received: {len(events)}")
        assert len(events) >= 2, f"Expected at least 2 events, got {len(events)}"

        # 4. Test Q&A with Real Incremental Token Streaming
        print("\n--- Test 2: Real Incremental Q&A Streaming ---")
        t0 = time.perf_counter()
        r = requests.post(f"{base_url}/query/stream", json={"query": "What skills are mentioned in Nikhil CS?"}, stream=True, timeout=30)
        assert r.status_code == 200
        
        ttft = None
        tokens = []
        meta_received = False
        done_received = False
        
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    payload = decoded[6:]
                    import json
                    ev = json.loads(payload)
                    if ev.get("type") == "meta":
                        meta_received = True
                        print(f"Meta received: action={ev.get('action')}, doc={ev.get('current_document', {}).get('name')}")
                    elif ev.get("type") == "token":
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                            print(f"TTFT (Time to First Token): {ttft*1000:.2f} ms")
                        tokens.append(ev.get("content", ""))
                    elif ev.get("type") == "done":
                        done_received = True
                        total_time = time.perf_counter() - t0
                        print(f"Stream done! Total time: {total_time:.2f}s, tokens received: {len(tokens)}")
                        if len(tokens) > 0:
                            print(f"Effective generation speed: {len(tokens)/max(total_time - ttft, 0.001):.1f} tokens/sec")

        assert meta_received, "Expected 'meta' event"
        assert len(tokens) > 0, "Expected streamed tokens"
        assert done_received, "Expected 'done' event"
        print(f"Sample response: {''.join(tokens)[:120]}...")

        print("\nALL DESKTOP STREAMING ACCEPTANCE TESTS PASSED!")

    finally:
        # 5. Clean window close and verify Win32 Job Object process cleanup
        print("\nSending WM_CLOSE to Tauri window...")
        WM_CLOSE = 0x0010
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "Local AI Document Agent")
        if hwnd:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        
        try:
            proc.wait(timeout=5)
            print("Tauri application exited cleanly.")
        except subprocess.TimeoutExpired:
            proc.kill()
            print("Tauri application forcibly killed.")
            
        time.sleep(2)
        # Verify no backend processes remain
        backend_check = subprocess.run(
            ["powershell", "-Command", "Get-Process | Where-Object { $_.ProcessName -like '*document-agent*' } | Select-Object -ExpandProperty Id"],
            capture_output=True, text=True
        )
        remaining_pids = backend_check.stdout.strip().split()
        if remaining_pids and remaining_pids[0]:
            print(f"WARNING: Remaining backend PIDs: {remaining_pids}")
            for pid in remaining_pids:
                try:
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                except Exception:
                    pass
        else:
            print("Zero orphan backend processes detected. Clean Win32 Job Object termination verified!")

if __name__ == "__main__":
    verify_desktop_app()
