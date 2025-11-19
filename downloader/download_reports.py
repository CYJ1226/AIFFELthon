import requests
import os
import json
import time

BASE_API = "https://www.bai.go.kr/api/bak/dar/AWUBAKDAR001E"
DOWNLOAD_API = "https://www.bai.go.kr/api/files/downloadZip"

SAVE_DIR = "downloads"
STATE_FILE = "state.json"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(s), f, ensure_ascii=False, indent=2)


def fetch_page(page):
    url = (
        f"{BASE_API}?searchType=0&searchText=&fromRegiDt=&toRegiDt=&searchYear=&"
        f"audSphCd=&audSphDtlCd=&audKndCd=&size=10&index=0&page={page}"
    )

    print(f" 요청 중: page={page}")
    
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    res.raise_for_status()

    data = res.json()
    embedded = data.get("_embedded", {})
    items = embedded.get("aWUBAKDAR001EDtoList", [])

    return items, data["page"]["totalPages"]


def download_pdf(fileId):
    print(f" 다운로드 요청: {fileId}")

    res = requests.post(DOWNLOAD_API, json={"fileId": fileId})

    if res.status_code != 200:
        print(f" 다운로드 실패: {fileId} (status={res.status_code})")
        return False

    filename = fileId.replace(" ", "_") + ".pdf"
    os.makedirs(SAVE_DIR, exist_ok=True)

    with open(os.path.join(SAVE_DIR, filename), "wb") as f:
        f.write(res.content)

    print(f" 저장 완료: {filename}")
    return True


def run():
    downloaded = load_state()

    
    _, total_pages = fetch_page(0)
    print(f" 전체 페이지 수: {total_pages}")

    for page in range(total_pages):
        items, _ = fetch_page(page)

        for item in items:
            fileId = item.get("openDocId")
            if not fileId:
                continue
            if not fileId.startswith("jj"):
                continue

            if fileId not in downloaded:
                success = download_pdf(fileId)

                if success:
                    downloaded.add(fileId)
                    save_state(downloaded)   

            time.sleep(0.3)  

        save_state(downloaded)  

    save_state(downloaded)      
    print(" 모든 PDF 다운로드 완료")


if __name__ == "__main__":
    run()

# 2003 년 8월~2025 까지 데이터있음