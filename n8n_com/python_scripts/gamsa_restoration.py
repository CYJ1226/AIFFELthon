import os
import json
import time
import requests
import re

SAVE_DIR = "downloads_gamsa_restore"
FAILED_FILE = "downloads_gamsa/failed_gamsa_re.json"
RESULT_FAILED_FILE = "downloads_gamsa_restore/failed_restore.json"

POST_API = "https://www.bai.go.kr/api/files/downloadZip"
GET_API = "https://www.bai.go.kr/api/files/downloadZip"

HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "*/*",
    "Referer": "https://www.bai.go.kr/",
}


def load_failed():
    with open(FAILED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["failed"]


def save_failed(items):
    os.makedirs(os.path.dirname(RESULT_FAILED_FILE), exist_ok=True)
    with open(RESULT_FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump({"failed": items}, f, ensure_ascii=False, indent=2)


def guess_ext_from_magic(binary: bytes):
    if binary.startswith(b"%PDF"):
        return ".pdf"
    if binary.startswith(b"PK"):
        return ".zip"   # zip / hwpx / docx
    if binary.startswith(b"HWP Document File"):
        return ".hwp"
    return None


def extract_filename(headers, file_id, binary):
    cd = headers.get("Content-Disposition", "")
    m = re.search(r'filename="?([^"]+)"?', cd)
    if m:
        filename = m.group(1)
        if "." in filename:
            return filename
        return None
    
    ext = guess_ext_from_magic(binary)
    if ext:
        return f"{file_id}{ext}"

    return None


def try_post(file_id):
    try:
        r = requests.post(
            POST_API,
            json={"fileId": file_id},
            timeout=60
        )
        if r.status_code == 200 and r.content:
            return r
    except:
        pass
    return None


def try_get(file_id):
    try:
        r = requests.get(
            GET_API,
            params={"fileId": file_id},
            headers=HEADERS_BROWSER,
            timeout=60
        )
        if r.status_code == 200 and r.content:
            return r
    except:
        pass
    return None


def run():
    failed = load_failed()
    still_failed = []

    os.makedirs(SAVE_DIR, exist_ok=True)

    for item in failed:
        file_id = item["fileId"]
        print(f"[RESTORE] {file_id}")

        resp = try_post(file_id) or try_get(file_id)

        if not resp:
            print("  → FAIL (no response)")
            still_failed.append({
                "fileId": file_id,
                "reason": "no response (post+get failed)"
            })
            continue

        binary = resp.content
        filename = extract_filename(resp.headers, file_id, binary)

        if not filename:
            print("  → FAIL (unknown file extension)")
            still_failed.append({
                "fileId": file_id,
                "reason": "unknown file extension"
            })
            continue

        path = os.path.join(SAVE_DIR, filename)
        with open(path, "wb") as f:
            f.write(binary)

        print(f"  → OK saved: {path}")
        time.sleep(0.3)

    save_failed(still_failed)
    print("\nDONE")


if __name__ == "__main__":
    run()
