#!/bin/bash
set -e

echo "📌 Initializing PostgreSQL: installing pgvector & creating RAG tables..."

# pgvector 설치
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

# documents 테이블 생성
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50),
    title TEXT,
    pdf_path TEXT,
    url TEXT,
    metadata JSONB,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
EOSQL

# embeddings 테이블 생성
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT,
    embedding VECTOR(1536),
    chunk_index INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
EOSQL

echo "✅ PostgreSQL initialization completed!"
