#!/bin/bash
set -e

echo "📌 Initializing PostgreSQL with pgvector + RAG tables + audit tables ..."

#
# 1) pgvector 설치
#
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
CREATE EXTENSION IF NOT EXISTS vector;
EOSQL


#
# 2) documents 테이블 생성
#
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    file_id TEXT,
    text_content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
EOSQL


#
# 3) embeddings 테이블 생성 (벡터 저장)
#
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


#
# 4) audit_data 테이블 생성 (팀원 JSON 저장)
#
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
CREATE TABLE IF NOT EXISTS audit_data (
    id SERIAL PRIMARY KEY,
    title TEXT,
    site TEXT,
    category TEXT,
    audit_start_date TEXT,
    audit_end_date TEXT,
    sub_order INT,
    keyword_list TEXT,
    problem TEXT,
    action TEXT,
    action_type TEXT,
    fiscal_amount INT,
    opinion TEXT,
    criteria TEXT,
    related_laws TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
EOSQL

echo "✅ PostgreSQL initialization completed!"
