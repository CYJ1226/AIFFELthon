import requests
import os
import json
import time
import sys

BASE_API = "https://www.bai.go.kr/api/bak/dar/AWUBAKDAR001E"
DOWNLOAD_API = "https://www.bai.go.kr/api/files/downloadZip"

SAVE_DIR = "/home/node/python_scripts/downloads" 
STATE_FILE = "/home/node/python_scripts/state.json"

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
    
    # [로그] 진행 상황은 stderr로 출력 (n8n 데이터 간섭 방지)
    sys.stderr.write(f"요청 중: page={page}\n")
    
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    res.raise_for_status()

    data = res.json()
    embedded = data.get("_embedded", {})
    items = embedded.get("aWUBAKDAR001EDtoList", [])

    return items, data["page"]["totalPages"]

def download_pdf(fileId):
    sys.stderr.write(f"다운로드 요청: {fileId}\n")

    try:
        res = requests.post(DOWNLOAD_API, json={"fileId": fileId})
        
        if res.status_code != 200:
            sys.stderr.write(f"다운로드 실패: {fileId} (status={res.status_code})\n")
            return None

        filename = fileId.replace(" ", "_") + ".pdf"
        os.makedirs(SAVE_DIR, exist_ok=True)
        
        file_path = os.path.join(SAVE_DIR, filename)

        with open(file_path, "wb") as f:
            f.write(res.content)

        sys.stderr.write(f"저장 완료: {filename}\n")
        return file_path
        
    except Exception as e:
        sys.stderr.write(f"에러 발생: {e}\n")
        return None

def run():
    downloaded = load_state()
    results = [] 
    
    items, total_pages = fetch_page(0) 
    
    for item in items:
        fileId = item.get("openDocId")

        if not fileId or not fileId.startswith("jj"):
            continue

        if fileId not in downloaded:
            file_path = download_pdf(fileId)
            
            # [결과 데이터 구조 생성]
            result_item = {
                "event": "add",
                "state": "failure",  # 기본값 실패로 설정
                "FilePath": None
            }

            if file_path:
                # 성공 시 값 업데이트
                result_item["state"] = "Success"
                result_item["FilePath"] = file_path
                
                # 성공했을 때만 상태 저장
                downloaded.add(fileId)
                save_state(downloaded)
            
            # 성공이든 실패든 결과 리스트에 추가 (n8n으로 전달)
            results.append(result_item)
            
            time.sleep(0.3)

    # [최종 출력] stdout으로 JSON 데이터만 내보냄
    print(json.dumps(results, ensure_ascii=False))

if __name__ == "__main__":
    run()