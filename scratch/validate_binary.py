import os
import subprocess
import time
import requests
import sys

exe_path = r"D:\one piece\jimbe\FA\backend-dist\document-agent-backend\document-agent-backend.exe"
print(f"Launching {exe_path}...")

env = os.environ.copy()
env["DOCUMENT_AGENT_PORT"] = "8765"

proc = subprocess.Popen([exe_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)

success = False
for i in range(12):
    time.sleep(1)
    # Check 8765 first, then 8000
    for p in [8765, 8000]:
        try:
            r = requests.get(f"http://127.0.0.1:{p}/health", timeout=1)
            if r.status_code == 200:
                print(f"Backend responded successfully on port {p}:", r.json())
                success = True
                break
        except Exception:
            pass
    if success:
        break
    print(f"Waiting for backend... ({i+1})")

proc.terminate()
try:
    stdout, stderr = proc.communicate(timeout=5)
    print("STDOUT:\n", stdout)
    print("STDERR:\n", stderr)
except Exception as e:
    print("Communicate error:", e)
    proc.kill()

if success:
    print("VALIDATION SUCCESSFUL!")
    sys.exit(0)
else:
    print("VALIDATION FAILED!")
    sys.exit(1)
