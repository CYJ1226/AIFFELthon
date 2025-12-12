import os
import json
import sys
import time
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.alio.go.kr"
ORG_API = f"{BASE_URL}/item/itemOrganListJung.json"   
DOWNLOAD_API = f"{BASE_URL}/download/file.json"       

SAVE_DIR = "downloads_alio"
STATE_FILE = os.path.join(SAVE_DIR, "state_alio.json")
FAILED_FILE = os.path.join(SAVE_DIR, "failed_alio.json")

MAX_WORKERS = 5
LIMIT = 99999

# def log(msg: str):
#     return 

MINISTRY_TO_FIELD = {
# 재정/금융
    "기획재정부": "재정",
    "금융위원회": "금융",
    
#세무
    "관세청": "관세",

# 산업
    "산업통상자원부": "산업자원",
    "중소벤처기업부": "산업자원",
    "지식재산처": "산업자원",
    "농촌진흥원": "농림수산해양",
    "농림축산식품부": "농림수산해양",
    "해양수산부": "농림수산해양",
    "산림청": "환경",
    "기후에너지환경부": "환경",
    
# 정보통신/과학
    "과학기술정보통신부": "과학기술",
    "기상청": "과학기술",
    "원자력안전위원회": "과학기술",
    "우주항공청": "과학기술",
    "방송미디어통신위원회": "정보통신",
    "국가데이터처": "정보통신",

# 건설/교통
    "국토교통부": "교통/물류",
    "행정중심복합도시건설청": "건설/주택",
    "새만금개발청": "해양",

# 교육/문화
    "교육부": "교육",
    "문화체육관광부": "문화/관광/체육",
    "국가유산청": "문화/관광/체육",

# 보건/복지/노동
    "보건복지부": "보건/복지",
    "질병관리청": "보건/복지",
    "식품의약품안전처": "보건/복지",
    "국가보훈부": "보건/복지",
    "성평등가족부": "보건/복지",
    "고용노동부": "노동",

# 외교/안보
    "외교부": "외교",
    "재외동포청": "외교",
    "통일부": "외교",
    "국방부": "국방",
    "방위사업청": "국방",
    "경찰청": "치안/법무",
    "해양경찰청": "치안/법무",
    "법무부": "치안/법무",

# 지방행정
    "행정안전부": "지방행정",
    "소방청": "지방행정",
    
#헌법기관
    "법제처": "입법",

# 공직기강/기타
    "인사혁신처": "공직기강",
    "국무조정실": "공직기강",
    
}

def log(msg: str):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()

def now_str() -> str:
    return datetime.datetime.now().isoformat()

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"download": [], "failed": [], "limit": LIMIT}
    return {"download": [], "failed": [], "limit": LIMIT}

def save_state(state: dict):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def save_failed(failed_list: list):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump({"failed": failed_list}, f, ensure_ascii=False,indent=2 )

def fetch_organ_list() -> list:
    payload = {
        "apbaType": [],
        "jidtDptm": [],
        "area": [],
        "apbaId": "",
        "reportFormRootNo": "32301",
        "quart": ""
    }
    log("[ALIO] 기관 목록 요청")
    res = requests.post(ORG_API, json=payload, timeout=20)
    res.raise_for_status()
    return res.json().get("data", {}).get("organList", [])


def parse_files(files_str: str) -> list:
    out = []
    if not files_str:
        return out

    for part in files_str.split("|"):
        if "@" in part:
            f, title = part.split("@", 1)
            out.append({"f": f.strip(), "title": title.strip()})
    return out

def download_pdf(meta: dict, session: requests.Session):
    log(f"[DL] START {meta['fileId']}")

    url = f"{DOWNLOAD_API}?f={meta['f']}&d={meta['d']}"
    filepath = os.path.join(SAVE_DIR, meta["filename"])

    try:
        r = session.get(url, timeout=10)
        r.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(r.content)

        log(f"[DL] OK {meta['fileId']} -> {filepath}")
        return True, filepath, url, now_str(), None

    except Exception as e:
        log(f"[DL] FAIL {meta['fileId']} | {e}")
        return False, None, None, now_str(), str(e)

def write_alio_count(state: dict):
    field_count = {}

    for item in state.get("download", []):
        field = item.get("audField") or "기타"
        field_count[field] = field_count.get(field, 0) + 1

    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(os.path.join(SAVE_DIR, "alio_count.json"), "w", encoding="utf-8") as f:
        json.dump(field_count, f, ensure_ascii=False, indent=2)

    return field_count


def run_alio():

    log("[ALIO] RUN START")

    os.makedirs(SAVE_DIR, exist_ok=True)

    state = load_state()
    failed = []
    downloaded_ids = {e["fileId"] for e in state["download"]}

    try:
        organs = fetch_organ_list()
        log(f"[ALIO] ORGAN COUNT = {len(organs)}")
    except Exception as e:
        log(f"[ERROR] FETCH ORGAN LIST FAILED {e}")
        return {"status": "error", "detail": str(e)}

    jobs = []

    for org in organs:
        files = org.get("files")
        d = org.get("disclosureNo")
        if not files or not d:
            continue
        for f in parse_files(files):
            fid = f["f"]
            if fid not in downloaded_ids:
                dept_name = org.get("jidtNa")
                aud_field = MINISTRY_TO_FIELD.get(dept_name, "기타")

                jobs.append({
                    "fileId": fid,
                    "filename": f"{org['apbaNa']}_{f['title']}_{fid}.pdf".replace(" ", "_"),
                    "orgName": org['apbaNa'],
                    "title": f['title'],
                    "d": d,
                    "orgType": org.get("apbaType"),
                    "mainDept": org.get("jidtDptm"),
                    "typeNa": org.get("typeNa"),
                    "jidtNa": dept_name,
                    "audField": aud_field,
                    "f": fid,
                })
                
                log(f"[JOB] ADD {fid}")

    session = requests.Session()

    for i in range(0, len(jobs), MAX_WORKERS):
        chunk = jobs[i:i + MAX_WORKERS]
        log(f"[BATCH] START {i} ~ {i + len(chunk) - 1}")

        successes = []
        failures = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
            futures = {exe.submit(download_pdf, job, session): job for job in chunk}

            for fut in futures:
                job = futures[fut]
                try:
                    ok, fp, url, t, reason = fut.result(timeout=20)
                except Exception as e:
                    log(f"[FUT-ERROR] {job['fileId']} | {e}")
                    ok, fp, url, t, reason = False, None, None, now_str(), str(e)

                entry = {
                    "fileId": job["fileId"],
                    "filename": job["filename"],
                    "filepath": fp,
                    "url": url,
                    "time": t,
                    "orgName": job["orgName"],
                    "title": job["title"],
                    "disclosureNo": job["d"],
                    "orgType": job["orgType"],
                    "mainDept": job["mainDept"],
                    "typeNa": job.get("typeNa"),
                    "parentDept": job.get("jidtNa"),
                    "audField": job.get("audField"),
                    "source": "알리오",
                    "state": "success" if ok else "failure",
                }

                if ok:
                    successes.append(entry)
                else:
                    failures.append({"fileId": job["fileId"], "filename": job["filename"], "reason": reason, "time": t})

        if successes:
            state["download"].extend(successes)
            save_state(state)
            log(f"[STATE] +{len(successes)}")

        if failures:
            failed.extend(failures)
            save_failed(failed)
            log(f"[FAILED] +{len(failures)}")

        log("[BATCH] END")
    log("[ALIO] DONE")
    write_alio_count(state)
    log("[COUNT] 분야별 카운트 저장 완료")

    return {"status": "ok"}



if __name__ == "__main__":
    run_alio()
    print("done")






