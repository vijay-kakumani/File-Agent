import os
import sys
from pathlib import Path
from typing import List, Set

# Base directory resolution
if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    APP_DIR = Path(sys.executable).parent
    BACKEND_DIR = BUNDLE_DIR
    ROOT_DIR = APP_DIR
else:
    BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
    ROOT_DIR = BACKEND_DIR.parent
    BUNDLE_DIR = BACKEND_DIR
    APP_DIR = ROOT_DIR


def resolve_data_directory() -> Path:
    """
    Resolves persistent user-writable application data directory.
    - Explicit override: DOCUMENT_AGENT_DATA_DIR environment variable
    - Frozen / Production: %LOCALAPPDATA%/LocalAIDocumentAgent/data
    - Development: ROOT_DIR / "data"
    """
    if "DOCUMENT_AGENT_DATA_DIR" in os.environ:
        d = Path(os.environ["DOCUMENT_AGENT_DATA_DIR"])
    elif getattr(sys, "frozen", False) or os.environ.get("PRODUCTION") == "1":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            d = Path(local_app_data) / "LocalAIDocumentAgent" / "data"
        else:
            d = Path.home() / "AppData" / "Local" / "LocalAIDocumentAgent" / "data"
    else:
        d = ROOT_DIR / "data"

    d.mkdir(parents=True, exist_ok=True)
    return d


# Persistent data directory
DATA_DIR = resolve_data_directory()

# Database & Vector storage paths
SQLITE_DB_PATH = DATA_DIR / "agent_index.db"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"


def resolve_embedding_model_path(model_name: str = "all-MiniLM-L6-v2") -> str:
    """
    Resolves embedding model path:
    1. Bundled model directory in application package
    2. Model directory in user data directory
    3. Hugging Face model identifier fallback
    """
    candidates = [
        BUNDLE_DIR / "models" / model_name,
        APP_DIR / "models" / model_name,
        APP_DIR / "_internal" / "models" / model_name,
        BACKEND_DIR / "models" / model_name,
        DATA_DIR / "models" / model_name,
    ]
    for c in candidates:
        if (c / "model.safetensors").exists() or (c / "pytorch_model.bin").exists() or (c / "modules.json").exists():
            return str(c.resolve())
    return model_name


# Supported file extensions
SUPPORTED_EXTENSIONS: Set[str] = {
    ".pdf",
    ".docx",
    ".txt",
    ".md"
}

# Configurable Search Roots (C: and D: drives)
DEFAULT_SEARCH_ROOTS: List[Path] = [
    # C: Drive User Folders (Dynamically resolved per Windows user)
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Desktop",
    # D: Drive Potential Folders
    Path("D:/College"),
    Path("D:/Projects"),
    Path("D:/Documents"),
    Path("D:/Downloads"),
]

# Add local project test directory in development if it exists
if not getattr(sys, "frozen", False) and (ROOT_DIR / "test_files").exists():
    DEFAULT_SEARCH_ROOTS.append(ROOT_DIR / "test_files")



def get_active_search_roots(custom_roots: List[Path] = None) -> List[Path]:
    """
    Returns a list of existing, accessible search directories.
    If custom_roots is explicitly provided, uses custom_roots.
    Otherwise uses DEFAULT_SEARCH_ROOTS.
    """
    roots_to_check = custom_roots if custom_roots is not None else DEFAULT_SEARCH_ROOTS

    active_roots = []
    seen = set()

    for root in roots_to_check:
        try:
            resolved = root.resolve()
            if resolved.exists() and resolved.is_dir() and str(resolved) not in seen:
                seen.add(str(resolved))
                active_roots.append(resolved)
        except (PermissionError, OSError):
            continue

    return active_roots


# Model Configuration
OLLAMA_MODEL = "qwen2.5:1.5b"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_MODEL_PATH = resolve_embedding_model_path(EMBEDDING_MODEL)

# RAG & Chunking Settings
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# Grounded Q&A Settings
QA_TOP_K = 4
QA_DISTANCE_THRESHOLD = 0.60  # Chroma L2 distance threshold (chunks > 0.60 distance are discarded)

# Size-Aware Map-Reduce Summarization Settings
SUMMARIZATION_DIRECT_CHAR_LIMIT = 12000  # Direct single-pass summarization char limit (~2400 words / ~6-8 pages)
SUMMARIZATION_CHUNK_SIZE = 3000          # Character length for Map chunking (~600 words)
SUMMARIZATION_CHUNK_OVERLAP = 200       # Overlap for Map chunking
SUMMARIZATION_REDUCE_GROUP_SIZE = 4     # Group size for hierarchical reduce stage
SUMMARIZATION_MAX_REDUCE_LEVELS = 3     # Safety limit for recursive reduce passes

# User Identity Configuration
DEFAULT_USER_NAME = os.environ.get("DOCUMENT_AGENT_USER_NAME", "Vijay")

