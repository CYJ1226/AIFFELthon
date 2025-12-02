import os
import json
import sys
import time
import requests
from requests.exceptions import RequestException

BASE_API = "https://www.bai.go.kr/api/bak/dar/AWUBAKDAR001E"
DOWNLOAD_API = "https://www.bai.go.kr/api/files/downloadZip"

SAVE_DIR = "downloads_gamsa"
STATE_FILE = os.path.join(SAVE_DIR, "state_gamsa.json")
FAILED_FILE = os.path.join(SAVE_DIR, "failed_gamsa.json")

LIMIT = 30

def log(msg: str):
    return 

# def log(msg: str):
#     sys.stderr.write(msg + "\n")
#     sys.stderr.flush()

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"download": [], "failed": [], "limit": LIMIT}

def save_state(state: dict):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_failed():
    if os.path.exists(FAILED_FILE):
        try:
            with open(FAILED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"failed": []}
    return {"failed": []}

def save_failed(failed_list: list) -> None:
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump({"failed": failed_list}, f, ensure_ascii=False, )

def fetch_page(page: int, retries: int = 3, delay: float = 2.0):
    url = (
        f"{BASE_API}"
        f"?searchType=0&searchText=&fromRegiDt=&toRegiDt=&searchYear="
        f"&audSphCd=&audSphDtlCd=&audKndCd=&size=10&index=0&page={page}"
    )

    last_error = None

    for attempt in range(1, retries + 1):
        try:
            log(f"[GAMSA] 페이지 요청: page={page}, 시도 {attempt}/{retries}")
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)

            if res.status_code != 200:
                log(f"[GAMSA] HTTP {res.status_code} → 재시도")
                last_error = f"status {res.status_code}"

            else:
                try:
                    data = res.json()
                except JSONDecodeError:
                    log(f"[GAMSA] JSON 파싱 실패: {res.text[:200]}")
                    last_error = "json decode error"
                else:
                    items = data.get("_embedded", {}).get("aWUBAKDAR001EDtoList", [])
                    total_pages = data.get("page", {}).get("totalPages", 0)
                    return items, total_pages, "ok"

        except RequestException as e:
            last_error = str(e)
            log(f"[GAMSA] 요청 예외: {e}")

        time.sleep(delay)

    log(f"[GAMSA] 페이지={page} 요청 실패 | 마지막 에러={last_error}")
    return [], 0, "error"

def download_pdf(file_id: str, failed_list: dict):
    log(f"[GAMSA] 다운로드 시도: {file_id}")

    try:
        res = requests.post(DOWNLOAD_API, json={"fileId": file_id}, timeout=30)
    except Exception as e:
        failed_list["failed"].append({
            "fileId": file_id,
            "reason": str(e)
        })
        return False, None, None, None

    if res.status_code != 200:
        failed_list["failed"].append({
            "fileId": file_id,
            "reason": f"HTTP {res.status_code}"
        })
        return False, None, None, None


    os.makedirs(SAVE_DIR, exist_ok=True)
    filename = f"{file_id}.pdf"
    filepath = os.path.join(SAVE_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(res.content)

    t = time.strftime("%Y-%m-%d %H:%M:%S")
    url = f"{DOWNLOAD_API}?fileId={file_id}"
    log(f"[GAMSA] 저장 완료: {filepath}")

    return True, filename,filepath, t, url

def run_gamsa():
    state = load_state()
    if len(state["download"]) >= LIMIT:
        return {"status": "ok", "results": [], "message": "Limit reached"}
    downloaded_ids = {e["fileId"] for e in state["download"]}
    failed = load_failed()
    results = []

    items0, total_pages, ok = fetch_page(0)
    if ok != "ok":
        return {"status": "error", "error": "fetch_failed"}

    log(f"[GAMSA] 전체 페이지 수: {total_pages}")

    for page in range(total_pages):
        log(f"[GAMSA] ==== page {page+1}/{total_pages} ====")

        items = items0 if page == 0 else fetch_page(page)[0]
        should_stop = False

        for item in items:
            file_id = item.get("openDocId")
            if not file_id or not file_id.startswith("jj") or file_id in downloaded_ids:
                continue

            ok2, filename, filepath ,t, url = download_pdf(file_id, failed)

            
            if not ok2 and filename is None and url is None:
                state_val = "no_data"  
            else:
                state_val = "success" if ok2 else "failure"

            entry = {
                "state": state_val,
                "fileId": file_id,
                "filename": filename,
                "url": url,
                "time": t,
                "filepath": filepath,
            }
            results.append(entry)

            if ok2:
                state["download"].append(entry)
                downloaded_ids.add(file_id)
                save_state(state)
            if len(state["download"]) >= LIMIT:
                save_state(state)
                save_failed(failed["failed"])
                return {"status": "ok", "results": results}

            time.sleep(0.1)

    save_failed(failed)
    return {"status": "ok", "results": results}

if __name__ == "__main__":
    results = run_gamsa()  
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

    # print(json.dumps({
    #     "status": "ok",
    #     "results_count": len(results["results"]),
    #     "download_count": len(state["download"]),
    #     "failed_count": len(state["failed"]),
    #     "state_file": STATE_FILE,
    #     "failed_file": FAILED_FILE
    # }, ensure_ascii=False))

