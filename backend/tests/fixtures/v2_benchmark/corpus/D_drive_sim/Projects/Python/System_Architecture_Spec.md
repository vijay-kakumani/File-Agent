# System Architecture Specification

## Overview
High-level architectural blueprint for local desktop AI systems, describing inter-process communication, local SQLite caches, and vector indexing.

## Components
1. Tauri v2 Desktop Shell (Rust + WebView2)
2. FastAPI Localhost Microservice (Python 3.12)
3. SQLite FTS5 Full-Text Database
4. ChromaDB Vector Database
5. Sentence-Transformers Local Embedding Pipeline
