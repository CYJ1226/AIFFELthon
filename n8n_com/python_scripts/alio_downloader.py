import os
import json
import sys
import time
import datetime
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import RequestException

BASE_URL = "https://www.alio.go.kr"
ORG_API = f"{BASE_URL}/item/itemOrganListJung.json"   
DOWNLOAD_API = f"{BASE_URL}/download/file.json"       

SAVE_DIR = "downloads_alio"
STATE_FILE = os.path.join(SAVE_DIR, "state_alio.json")
FAILED_FILE = os.path.join(SAVE_DIR, "failed_alio.json")

MAX_WORKERS = 5
LIMIT = 30


def log(msg: str):
    return 

# def log(msg: str):
#     sys.stderr.write(msg + "\n")
#     sys.stderr.flush()

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
        json.dump(state, f, ensure_ascii=False, )

def save_failed(failed_list: list):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump({"failed": failed_list}, f, ensure_ascii=False, )

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

def download_one(meta: dict, failed_list: list):

    os.makedirs(SAVE_DIR, exist_ok=True)

    url = f"{DOWNLOAD_API}?f={meta['f']}&d={meta['d']}"
    filepath = os.path.join(SAVE_DIR, meta["filename"])

    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(res.content)

        log(f"[ALIO] 저장 완료 → {filepath}")

        download_time = time.strftime("%Y-%m-%d %H:%M:%S")
        return True, filepath, url, download_time

    except Exception as e:
        log(f"[ALIO] 실패: {meta['filename']} | {e}")
        download_time = time.strftime("%Y-%m-%d %H:%M:%S")

        failed_entry = {
            "fileId": meta["fileId"],
            "filename": meta["filename"],
            "reason": str(e),
            "time": download_time,
        }
        failed_list.append(failed_entry)
        save_failed(failed_list)
        return False, None, None, None

def run_alio():

    os.makedirs(SAVE_DIR, exist_ok=True)

    state_list = load_state()
    if len(state_list["download"]) >= LIMIT:
        return {"status": "ok", "results": [], "message": "Limit reached"}
    downloaded_ids = {e["fileId"] for e in state_list["download"]}
    failed_list = []
    results = []

    try:
        organs = fetch_organ_list()
    except Exception as e:
        log(f"[ALIO] 기관 목록 로드 실패: {e}")
        return {"status": "error", "error": "organ_list_failed", "detail": str(e)}

    jobs = []

    for org in organs:
        org_name = org.get("apbaNa")
        d_val = org.get("disclosureNo")
        files_str = org.get("files")

        if not org_name or not d_val or not files_str:
            continue

        for f in parse_files(files_str):
            file_id = f["f"]
            title = f["title"]

            if file_id in downloaded_ids:
                continue

            filename = f"{org_name}_{title}_{file_id}.pdf".replace(" ", "_")

            meta = {
                "fileId": file_id,
                "filename": filename,
                "org": org_name,
                "title": title,
                "d": d_val,
                "f": file_id,
            }

            jobs.append(meta)

    #  병렬 다운로드
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(download_one, j, failed_list): j for j in jobs}

        for fut in as_completed(futures):
            meta = futures[fut]
            ok, filepath, url, t = fut.result()

            entry = {
                "state": "success" if ok else "failure",
                "fileId": meta["fileId"],
                "filename": meta["filename"],
                "url": url,
                "time": t,
                "filepath": filepath,
            }

            results.append(entry)

            if ok:
                state_list["download"].append(entry)
                downloaded_ids.add(meta["fileId"])
                save_state(state_list)  
            
            if len(state_list["download"]) >= LIMIT:
                save_state(state_list)
                for future in futures:
                    future.cancel()
                break

    save_failed(failed_list)

    return {"status": "ok", "results": results}

if __name__ == "__main__":
    run_alio()
    print("done")
    # try:
    #     with open(STATE_FILE, "r", encoding="utf-8") as f:
    #         state = json.load(f)
    # except:
    #     state = {"download": [], "failed": [], "limit": LIMIT}

    # try:
    #     with open(FAILED_FILE, "r", encoding="utf-8") as f:
    #         failed = json.load(f)
    # except:
    #     failed = {"failed": []}

    # RESULT_FILE = os.path.join(SAVE_DIR, "alio_result.json")
    # with open(RESULT_FILE, "w", encoding="utf-8") as f:
    #     json.dump(results, f, ensure_ascii=False,)

    # print(json.dumps({
    #     "status": "ok",
    #     "result_file": RESULT_FILE,
    #     "state_file": STATE_FILE,
    #     "failed_file": FAILED_FILE,
    #     "download_count": len(state["download"]),
    #     "limit": state["limit"]
    # }, ensure_ascii=False))





