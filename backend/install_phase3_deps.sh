#!/bin/bash
# Install Phase 3 dependencies if not already present
pip install faiss-cpu sentence-transformers jieba rank-bm25 numpy 2>&1 | tail -5
echo "Phase 3 dependencies installed."
