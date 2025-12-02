import os
import sys
import json
import requests
import datetime

PDF_URL = "https://www.law.go.kr/LSW/lsPdfPrint.do?ancYnChk=0"

LAWS = [
    ("50041", "주식회사외부감사법"),
    ("50042", "주식회사외부감사법시행령"),
    ("50043", "주식회사외부감사법시행규칙"),
]

SAVE_DIR = "downloads_laws"
STATE_FILE = os.path.join(SAVE_DIR, "state_laws.json")
FAILED_FILE = os.path.join(SAVE_DIR, "failed_laws.json")

def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()

def now():
    return datetime.datetime.now().isoformat()

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"downloaded": []}
    return {"downloaded": []}

def load_failed():
    if os.path.exists(FAILED_FILE):
        try:
            with open(FAILED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"failed": []}
    return {"failed": []}

def save_state(data):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False,)

def save_failed(data):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False,)

def download_pdf(fileId, title):
    url = f"{PDF_URL}&lsiSeq={fileId}"
    filename = f"{title}_{fileId}.pdf".replace(" ", "_")
    path = os.path.join(SAVE_DIR, filename)

    log(f"[LAWS] 다운로드: {filename}")

    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()

        with open(path, "wb") as f:
            f.write(res.content)

        return True, filename, url, path,None

    except Exception as e:
        log(f"[LAWS] 실패: {filename} | {e}")
        return False, filename, url, path,str(e)

def run_laws():
    state = load_state()
    failed = load_failed()
    results = []

    os.makedirs(SAVE_DIR, exist_ok=True)

    for lsiSeq, title in LAWS:
        success, filename, url,filepath, value = download_pdf(lsiSeq, title)

        entry = {
            "state":success,
            "fileId": lsiSeq,
            "filename": filename,
            "url": url,
            "time": now(),
            "filepath": filepath,
        }

        if success:
            entry["state"] = "success"

            state["downloaded"] = [
                x for x in state["downloaded"] if x["fileId"] != lsiSeq
            ]
            state["downloaded"].append(entry)

        else:
            entry["state"] = "failure"  

            failed["failed"].append(entry)

        results.append(entry)

    save_state(state)
    save_failed(failed)

    return {
        "status": "ok",
        "results": results,
        "state": state,
        "failed": failed
    }

if __name__ == "__main__":
    result = run_laws()  

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state_data = json.load(f)
    except:
        state_data = {"downloaded": []}
    try:
        with open(FAILED_FILE, "r", encoding="utf-8") as f:
            failed_data = json.load(f)
    except:
        failed_data = {"failed": []}

    print(json.dumps({
        "status": "ok",
        "results_count": len(result["results"]),
        "state": state_data,
        "failed": failed_data
    }, ensure_ascii=False))

