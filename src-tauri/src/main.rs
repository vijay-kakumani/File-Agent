// Prevents additional console window on Windows in release builds, do NOT remove!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{Manager, RunEvent};

#[cfg(target_os = "windows")]
mod win_job {
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;

    type HANDLE = *mut std::ffi::c_void;
    type BOOL = i32;
    type DWORD = u32;

    #[repr(C)]
    struct JOBOBJECT_BASIC_LIMIT_INFORMATION {
        per_process_user_time_limit: i64,
        per_job_user_time_limit: i64,
        limit_flags: DWORD,
        minimum_working_set_size: usize,
        maximum_working_set_size: usize,
        active_process_limit: DWORD,
        affinity: usize,
        priority_class: DWORD,
        scheduling_class: DWORD,
    }

    #[repr(C)]
    struct IO_COUNTERS {
        read_operation_count: u64,
        write_operation_count: u64,
        other_operation_count: u64,
        read_transfer_count: u64,
        write_transfer_count: u64,
        other_transfer_count: u64,
    }

    #[repr(C)]
    struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
        basic_limit_information: JOBOBJECT_BASIC_LIMIT_INFORMATION,
        io_info: IO_COUNTERS,
        process_memory_limit: usize,
        job_memory_limit: usize,
        peak_process_memory_limit: usize,
        peak_job_memory_limit: usize,
    }

    const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: DWORD = 0x2000;
    const JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: i32 = 9;

    extern "system" {
        fn CreateJobObjectW(lp_job_attributes: *mut std::ffi::c_void, lp_name: *const u16) -> HANDLE;
        fn SetInformationJobObject(
            h_job: HANDLE,
            job_object_info_class: i32,
            lp_job_object_info: *const std::ffi::c_void,
            cb_job_object_info_length: DWORD,
        ) -> BOOL;
        fn AssignProcessToJobObject(h_job: HANDLE, h_process: HANDLE) -> BOOL;
    }

    pub struct JobHandle(pub HANDLE);
    unsafe impl Send for JobHandle {}
    unsafe impl Sync for JobHandle {}

    pub fn create_kill_on_close_job() -> Option<JobHandle> {
        unsafe {
            let job = CreateJobObjectW(std::ptr::null_mut(), std::ptr::null());
            if job.is_null() {
                return None;
            }
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            info.basic_limit_information.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            let res = SetInformationJobObject(
                job,
                JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                &info as *const _ as *const std::ffi::c_void,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as DWORD,
            );
            if res == 0 {
                return None;
            }
            Some(JobHandle(job))
        }
    }

    pub fn assign_child(job: &JobHandle, child: &Child) -> bool {
        unsafe {
            let handle = child.as_raw_handle() as HANDLE;
            AssignProcessToJobObject(job.0, handle) != 0
        }
    }
}

struct BackendProcess {
    child: Mutex<Option<Child>>,
    #[cfg(target_os = "windows")]
    _job: Option<win_job::JobHandle>,
}

#[derive(Debug)]
enum BackendTarget {
    Standalone(std::path::PathBuf),
    DevPython {
        python_bin: String,
        root_dir: std::path::PathBuf,
        backend_dir: std::path::PathBuf,
    },
}

fn locate_backend() -> BackendTarget {
    let cwd = std::env::current_dir().unwrap_or_default();
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_else(|| cwd.clone());

    // 1. Look for standalone production binary in install and build directories
    let standalone_candidates = vec![
        exe_dir.join("document-agent-backend.exe"),
        exe_dir.join("document-agent-backend").join("document-agent-backend.exe"),
        exe_dir.join("backend").join("document-agent-backend.exe"),
        exe_dir.join("resources").join("document-agent-backend.exe"),
        exe_dir.join("resources").join("document-agent-backend").join("document-agent-backend.exe"),
        exe_dir.join("resources").join("backend").join("document-agent-backend.exe"),
        exe_dir.join("resources").join("backend-dist").join("document-agent-backend").join("document-agent-backend.exe"),
        exe_dir.join("_up_").join("backend-dist").join("document-agent-backend").join("document-agent-backend.exe"),
        cwd.join("backend-dist").join("document-agent-backend").join("document-agent-backend.exe"),
        exe_dir.join("..").join("backend-dist").join("document-agent-backend").join("document-agent-backend.exe"),
        exe_dir.join("../..").join("backend-dist").join("document-agent-backend").join("document-agent-backend.exe"),
        exe_dir.join("../../..").join("backend-dist").join("document-agent-backend").join("document-agent-backend.exe"),
    ];

    for candidate in standalone_candidates {
        if candidate.exists() {
            let canonical = candidate.canonicalize().unwrap_or(candidate);
            println!("[STARTUP] Detected standalone backend binary at {:?}", canonical);
            return BackendTarget::Standalone(canonical);
        }
    }

    // 2. Fallback to developer virtualenv
    let dev_roots = vec![
        cwd.clone(),
        exe_dir.clone(),
        exe_dir.join(".."),
        exe_dir.join("../.."),
        exe_dir.join("../../.."),
    ];

    for root in dev_roots {
        let py = root.join("venv").join("Scripts").join("python.exe");
        let backend = root.join("backend");
        if py.exists() && backend.exists() {
            let canonical_root = root.canonicalize().unwrap_or(root);
            let canonical_backend = backend.canonicalize().unwrap_or(backend);
            println!("[STARTUP] Detected development Python at {:?}", py);
            return BackendTarget::DevPython {
                python_bin: py.to_string_lossy().to_string(),
                root_dir: canonical_root,
                backend_dir: canonical_backend,
            };
        }
    }

    println!("[STARTUP] No specific backend found, defaulting to system python");
    BackendTarget::DevPython {
        python_bin: "python".to_string(),
        root_dir: cwd.clone(),
        backend_dir: cwd.join("backend"),
    }
}

fn is_backend_healthy() -> bool {
    use std::io::{Read, Write};
    use std::net::TcpStream;

    let port = std::env::var("DOCUMENT_AGENT_PORT").unwrap_or_else(|_| "8000".to_string());
    let addr = match format!("127.0.0.1:{}", port).parse() {
        Ok(a) => a,
        Err(_) => return false,
    };

    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(500)) {
        Ok(s) => s,
        Err(_) => return false,
    };

    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));

    let req = format!("GET /health HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n", port);
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }

    let mut buf = [0u8; 512];
    if let Ok(n) = stream.read(&mut buf) {
        let resp = String::from_utf8_lossy(&buf[..n]);
        return resp.contains("200 OK") && (resp.contains("agent_ready") || resp.contains("active_search_roots_count"));
    }

    false
}

#[cfg(target_os = "windows")]
type JobHandleType = Option<win_job::JobHandle>;
#[cfg(not(target_os = "windows"))]
type JobHandleType = ();

fn start_backend_if_needed() -> (Option<Child>, JobHandleType) {
    println!("[STARTUP] Checking if backend is already healthy...");
    if is_backend_healthy() {
        println!("[STARTUP] Backend is already running and healthy.");
        return (None, None);
    }

    let port = std::env::var("DOCUMENT_AGENT_PORT").unwrap_or_else(|_| "8000".to_string());
    println!("[STARTUP] Locating backend execution target (port: {})...", port);
    let target = locate_backend();

    let mut cmd = match &target {
        BackendTarget::Standalone(bin_path) => {
            let clean_bin_str = bin_path.to_string_lossy().trim_start_matches(r"\\?\").to_string();
            let mut c = Command::new(&clean_bin_str);
            c.args(["--host", "127.0.0.1", "--port", &port]);
            if let Some(parent) = bin_path.parent() {
                let clean_parent = parent.to_string_lossy().trim_start_matches(r"\\?\").to_string();
                c.current_dir(clean_parent);
            }
            c
        }
        BackendTarget::DevPython { python_bin, root_dir, backend_dir } => {
            let clean_root_str = root_dir.to_string_lossy().trim_start_matches(r"\\?\").to_string();
            let clean_root = std::path::PathBuf::from(&clean_root_str);
            let clean_backend = backend_dir.to_string_lossy().trim_start_matches(r"\\?\").to_string();
            let mut c = Command::new(python_bin);
            c.args(["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", &port])
             .env("PYTHONPATH", clean_backend)
             .env("DOCUMENT_AGENT_PORT", &port)
             .current_dir(&clean_root);
            c
        }
    };

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }

    println!("[STARTUP] Spawning backend process...");
    match cmd.spawn() {
        Ok(child) => {
            let pid = child.id();
            println!("[STARTUP] Backend process spawned successfully (PID: {})", pid);

            #[cfg(target_os = "windows")]
            let job_handle = {
                let job = win_job::create_kill_on_close_job();
                if let Some(ref j) = job {
                    let assigned = win_job::assign_child(j, &child);
                    println!("[STARTUP] Assigned backend child to kill-on-close Job Object (assigned: {})", assigned);
                }
                job
            };

            // Poll backend health in a background thread so the GUI window is NOT blocked
            std::thread::spawn(move || {
                let start = Instant::now();
                let mut attempts = 0;
                let timeout = Duration::from_secs(60);
                println!("[STARTUP MONITOR] Background health monitor started (PID: {})...", pid);

                while start.elapsed() < timeout {
                    attempts += 1;
                    if is_backend_healthy() {
                        println!("[STARTUP MONITOR] Backend became healthy! (Attempts: {}, Elapsed: {:?})", attempts, start.elapsed());
                        return;
                    }
                    std::thread::sleep(Duration::from_millis(500));
                }

                eprintln!("[STARTUP MONITOR] WARNING: Backend health poll timed out after {:?}", start.elapsed());
            });

            #[cfg(target_os = "windows")]
            return (Some(child), job_handle);
            #[cfg(not(target_os = "windows"))]
            return (Some(child), ());
        }
        Err(e) => {
            eprintln!("[STARTUP] ERROR: Failed to spawn backend process: {}", e);
            #[cfg(target_os = "windows")]
            return (None, None);
            #[cfg(not(target_os = "windows"))]
            return (None, ());
        }
    }
}

fn cleanup_backend(state: &BackendProcess) {
    if let Ok(mut guard) = state.child.lock() {
        if let Some(mut child) = guard.take() {
            let pid = child.id();
            println!("[SHUTDOWN] Terminating backend process (PID: {})...", pid);
            let _ = child.kill();
            let _ = child.wait();
            println!("[SHUTDOWN] Backend process (PID: {}) terminated cleanly.", pid);
        }
    }
}

fn main() {
    println!("[STARTUP] Starting Local AI Document Agent desktop application...");
    
    let (child, job) = start_backend_if_needed();
    let backend_state = BackendProcess {
        child: Mutex::new(child),
        #[cfg(target_os = "windows")]
        _job: job,
    };

    println!("[STARTUP] Initializing Tauri application window...");
    let app = tauri::Builder::default()
        .setup(|app| {
            println!("[STARTUP] Tauri setup hook executed.");
            let windows = app.webview_windows();
            println!("[STARTUP] Initialized {} webview window(s):", windows.len());
            for (label, win) in &windows {
                let is_vis = win.is_visible().unwrap_or(false);
                let url = win.url();
                println!("[STARTUP] Window label='{}', visible={}, url={:?}", label, is_vis, url);
                
                let _ = win.show();
                let _ = win.set_focus();
            }
            Ok(())
        })
        .manage(backend_state)
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    println!("[STARTUP] Tauri application built successfully. Entering native event loop.");

    app.run(|app_handle, event| {
        match event {
            RunEvent::Ready => {
                println!("[EVENT] Tauri event loop: Ready.");
            }
            RunEvent::WindowEvent { event: tauri::WindowEvent::CloseRequested { .. }, .. } => {
                println!("[EVENT] Window close requested. Triggering backend shutdown...");
                if let Some(state) = app_handle.try_state::<BackendProcess>() {
                    cleanup_backend(&state);
                }
            }
            RunEvent::ExitRequested { .. } | RunEvent::Exit => {
                println!("[EVENT] Application exit requested. Triggering backend shutdown...");
                if let Some(state) = app_handle.try_state::<BackendProcess>() {
                    cleanup_backend(&state);
                }
            }
            _ => {}
        }
    });
}
