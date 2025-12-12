from fastapi import FastAPI, Request
from pydantic import BaseModel
import psycopg2
import json
import sys

# 한글 출력 방지
sys.stdout.reconfigure(encoding='utf-8')

app = FastAPI()

# ---------------------------
# Payload 모델 (팀원 JSON 100% 대응)
# ---------------------------
class Payload(BaseModel):
    title: str | None = None
    site: str | None = None
    category: str | None = None
    audit_start_date: str | None = None
    audit_end_date: str | None = None
    sub_order: int | None = None
    keyword_list: list[str] | None = None
    problem: str | None = None
    action: str | None = None
    action_type: list[str] | None = None
    fiscal_amount: int | None = None
    opinion: str | None = None
    criteria: str | None = None
    related_laws: list[str] | None = None


# ---------------------------
# DB 연결 함수
# ---------------------------
def get_db():
    conn = psycopg2.connect(
        host="postgres",
        port=5432,
        user="n8n",
        password="n8nthankyou",
        dbname="n8n"
    )
    return conn


# ---------------------------
# JSON 적재 API
# ---------------------------
@app.post("/receive")
async def receive(payload: Payload, request: Request):
    try:
        body_raw = await request.body()
        print("\n=== RAW JSON ===")
        print(body_raw.decode("utf-8"))

        conn = get_db()
        cur = conn.cursor()

        # 배열은 문자열(JSON)로 변환하여 저장
        cur.execute("""
            INSERT INTO audit_data (
                title, site, category,
                audit_start_date, audit_end_date,
                sub_order, keyword_list,
                problem, action,
                action_type, fiscal_amount,
                opinion, criteria, related_laws
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            payload.title,
            payload.site,
            payload.category,
            payload.audit_start_date,
            payload.audit_end_date,
            payload.sub_order,
            json.dumps(payload.keyword_list) if payload.keyword_list else None,
            payload.problem,
            payload.action,
            json.dumps(payload.action_type) if payload.action_type else None,
            payload.fiscal_amount,
            payload.opinion,
            payload.criteria,
            json.dumps(payload.related_laws) if payload.related_laws else None
        ))

        conn.commit()
        cur.close()
        conn.close()

        return {"status": "success", "msg": "DB 저장 완료"}

    except Exception as e:
        print("[ERROR]", e)
        return {"status": "error", "detail": str(e)}


# ---------------------------
# DB 조회 API
# ---------------------------
@app.get("/list")
async def list_all():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM audit_data ORDER BY id DESC;")
        rows = cur.fetchall()

        cur.close()
        conn.close()

        return {"status": "success", "data": rows}

    except Exception as e:
        print("[ERROR]", e)
        return {"status": "error", "detail": str(e)}
