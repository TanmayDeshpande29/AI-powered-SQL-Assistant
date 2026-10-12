"""Retrieval-augmented generation building blocks (Phase 3+).

documents.py     what we embed for each table, and its fingerprint
embeddings.py    text -> vectors (dense meaning + sparse keywords), Hugging Face models
vector_store.py  Qdrant: store, filter and search those vectors per user and schema
"""
