import ctypes
import ctypes.wintypes

EnumWindows = ctypes.windll.user32.EnumWindows
GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
IsWindowVisible = ctypes.windll.user32.IsWindowVisible
GetWindowTextW = ctypes.windll.user32.GetWindowTextW
GetWindowTextLengthW = ctypes.windll.user32.GetWindowTextLengthW
GetClassNameW = ctypes.windll.user32.GetClassNameW

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

windows = []

def enum_windows_callback(hwnd, extra):
    pid = ctypes.wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    
    length = GetWindowTextLengthW(hwnd)
    title_buf = ctypes.create_unicode_buffer(length + 1)
    GetWindowTextW(hwnd, title_buf, length + 1)
    
    class_buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, class_buf, 256)
    
    is_vis = bool(IsWindowVisible(hwnd))
    
    windows.append({
        'hwnd': hwnd,
        'pid': pid.value,
        'title': title_buf.value,
        'class': class_buf.value,
        'visible': is_vis
    })
    return True

EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

print(f"Total top-level windows enumerated: {len(windows)}")
for w in windows:
    if "Document" in w['title'] or "local-ai" in w['title'] or "Tauri" in w['title'] or w['pid'] == 21108:
        print(f"MATCH: HWND={w['hwnd']}, PID={w['pid']}, Visible={w['visible']}, Class='{w['class']}', Title='{w['title']}'")
