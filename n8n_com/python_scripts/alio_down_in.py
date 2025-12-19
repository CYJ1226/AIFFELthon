import os
import json
import time
import re
from typing import Optional, Dict
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

METADATA_FILE = "alio_metadata/sorted_metadata.json"
DOWNLOAD_DIR = "downloads_alio_susi"
STATE_FILE = os.path.join(DOWNLOAD_DIR, "state.json")
FAILED_FILE = os.path.join(DOWNLOAD_DIR, "failed.json")

#병렬작업 수
NUM_WORKERS = 5
#타임아웃
DOWNLOAD_TIMEOUT = 30
#총 다운로드파일 개수
MAX_TOTAL_DOWNLOAD = 500
#분야당 다운로드 개수
MAX_PER_FIELD = 100 
#다운로드 분야
TARGET_FIELDS = ["재정", "금융", "산업자원", "교통/물류", "노동"]
EXCLUDE_GITA = True

state_lock = threading.Lock()
log_lock = threading.Lock()
download_lock = threading.Lock() 

def log(msg: str, worker_id: Optional[int] = None):
    with log_lock:
        prefix = f"[W{worker_id}]" if worker_id is not None else ""
        print(f"{prefix} {msg}", flush=True)

def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json_atomic(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)

def safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)
    return s.strip().replace(" ", "_")

def unique_path(dir_path: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    p = os.path.join(dir_path, filename)
    if not os.path.exists(p):
        return p
    n = 1
    while True:
        cand = os.path.join(dir_path, f"{base}_{n}{ext}")
        if not os.path.exists(cand):
            return cand
        n += 1

def build_driver(download_dir: str):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-images")
    
    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "profile.default_content_setting_values.images": 2,
    }
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=options)

def wait_ready(driver, timeout=15):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
    )

def wait_for_download_complete(before_files: set, timeout=DOWNLOAD_TIMEOUT) -> Optional[str]:
    start = time.time()
    last_check_time = start
    
    while time.time() - start < timeout:
        try:
            current = set(os.listdir(DOWNLOAD_DIR))
        except:
            time.sleep(0.5)
            continue
        
        diff = current - before_files
        
        temp_files = [f for f in diff if f.lower().endswith((".tmp", ".crdownload", ".part"))]
        if temp_files:
            last_check_time = time.time()  
            time.sleep(0.5)
            continue
        
        complete_files = [
            f for f in diff 
            if f.endswith((".hwp",".hwpx", ".pdf", ".xlsx", ".docx", ".pptx", ".zip"))
        ]
        
        if complete_files:
            found_file = max(
                complete_files, 
                key=lambda f: os.path.getmtime(os.path.join(DOWNLOAD_DIR, f))
            )
            
            file_path = os.path.join(DOWNLOAD_DIR, found_file)
            
            prev_size = -1
            for _ in range(3):
                time.sleep(0.2)
                try:
                    curr_size = os.path.getsize(file_path)
                    if curr_size == prev_size and curr_size > 0:
                        return found_file
                    prev_size = curr_size
                except:
                    break
            
            if os.path.exists(file_path):
                return found_file
        
        time.sleep(0.3)
    
    return None

def download_single_report(metadata: Dict, worker_id: int) -> Dict:
    driver = None
    result = {"success": False, "data": None, "error": None}
    
    try:
        driver = build_driver(DOWNLOAD_DIR)
        
        submission_no = metadata["submissionNo"]
        url = metadata["url"]
        title = metadata["title"]
        audit_field = metadata["auditField"]
        org_name = metadata["orgName"]
        
        log(f"Start: {submission_no}", worker_id)
        
        driver.get(url)
        wait_ready(driver)
        time.sleep(0.5)

        html = driver.page_source or ""
        m = re.search(r"report_attach_down\s*\(\s*['\"](.+?)['\"]\s*\)", html)
        
        if not m:
            result["error"] = "fileName_not_found"
            return result

        file_name = m.group(1)
        
        with download_lock:
            before = set(os.listdir(DOWNLOAD_DIR))
            
            driver.execute_script("report_attach_down(arguments[0]);", file_name)
            
            saved_name = wait_for_download_complete(before)
            
            if not saved_name:
                result["error"] = "download_timeout"
                return result
            
            log(f"Downloaded: {saved_name}", worker_id)
            
            old_path = os.path.join(DOWNLOAD_DIR, saved_name)
            
            if not os.path.exists(old_path):
                result["error"] = f"file_disappeared: {saved_name}"
                return result
            
            original_name, ext = os.path.splitext(saved_name)
            
            safe_field = safe_filename(audit_field)
            safe_org = safe_filename(org_name)
            safe_original = safe_filename(original_name)
            
            final_name = f"{safe_field}_{safe_org}_{submission_no}_{safe_original}{ext}"
            
            if len(final_name) > 200:
                max_original_len = 200 - len(safe_field) - len(safe_org) - len(submission_no) - len(ext) - 3
                if max_original_len > 0:
                    safe_original = safe_original[:max_original_len]
                else:
                    safe_original = safe_original[:50]
                final_name = f"{safe_field}_{safe_org}_{submission_no}_{safe_original}{ext}"
            
            save_path = unique_path(DOWNLOAD_DIR, final_name)
            
            try:
                os.rename(old_path, save_path)
                log(f"Renamed: {os.path.basename(save_path)[:60]}...", worker_id)
            except Exception as e:
                log(f"Rename failed: {e}", worker_id)
                result["error"] = f"rename_failed: {e}"
                return result
        
        result["success"] = True
        result["data"] = {
            "state": "success",
            "fileId": submission_no,
            "filename": os.path.basename(save_path),
            "url": url,
            "filepath": save_path,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "audKind": "수시감사",
            "audField": audit_field,
            "regDate": metadata.get("idate", ""),
            "source": "알리오",
            "orgName": org_name,
            "orgId": metadata.get("orgId", ""),
            "ministry": metadata.get("ministry", ""),
            "title": title,
        }
        
        log(f"OK: {submission_no}", worker_id)
        
    except Exception as ex:
        result["error"] = str(ex)
        log(f"ERROR: {ex}", worker_id)
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return result

def run():
    log("[STEP 3] DOWNLOAD FROM SORTED METADATA")
    log("="*80)
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    if not os.path.exists(METADATA_FILE):
        log(f"[ERROR] Metadata file not found: {METADATA_FILE}")
        return
    
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    all_metadata = data.get("metadata", [])
    log(f"\nLoaded {len(all_metadata)} reports")
    
    valid_metadata = [item for item in all_metadata if item.get("submissionNo")]
    log(f"Valid items: {len(valid_metadata)}")
    
    filtered = []
    field_counter = defaultdict(int)

    state = load_json(STATE_FILE, {"downloaded": []})
    downloaded_ids = {item.get("fileId") for item in state.get("downloaded", [])}
    state_field_counter = defaultdict(int)
    for item in state.get("downloaded", []):
        field = item.get("audField", "기타")
        state_field_counter[field] += 1

    log(f"\n[STATE] Already downloaded by field: {dict(state_field_counter)}")
    log(f"[STATE] Total already downloaded: {len(downloaded_ids)}")
    for item in valid_metadata:
        audit_field = item.get("auditField", "기타")
        submission_no = item.get("submissionNo")
        
        # 이미 다운받은 것 스킵
        if submission_no in downloaded_ids:
            continue
        
        if EXCLUDE_GITA and audit_field == "기타":
            continue
        
        if TARGET_FIELDS and audit_field not in TARGET_FIELDS:
            continue
        
        # ★★★ state + 현재 필터링 개수 합산해서 체크 ★★★
        total_in_field = state_field_counter.get(audit_field, 0) + field_counter[audit_field]
        if MAX_PER_FIELD and total_in_field >= MAX_PER_FIELD:
            continue
        
        # ★★★ 전체 개수도 state + 현재 합산 ★★★
        total_count = len(downloaded_ids) + len(filtered)
        if MAX_TOTAL_DOWNLOAD and total_count >= MAX_TOTAL_DOWNLOAD:
            break
        
        filtered.append(item)
        field_counter[audit_field] += 1

    log(f"\n[FILTER] {len(filtered)} to download")
    log(f"[FILTER] New downloads by field: {dict(field_counter)}")
    
    to_download = filtered
    
    log(f"\n[STATUS] To download: {len(to_download)}")
    
    if not to_download:
        log("\n[DONE] Nothing to download!")
        print_statistics()
        return
    
    success_count = 0
    failed_count = 0
    failed_list = load_json(FAILED_FILE, {"failed": []})
    
    log(f"\n[DOWNLOAD] Starting with {NUM_WORKERS} workers...")
    log("="*80)
    
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {
            executor.submit(download_single_report, item, i % NUM_WORKERS): item
            for i, item in enumerate(to_download)
        }
        
        for future in as_completed(futures):
            result = future.result()
            
            with state_lock:
                if result["success"]:
                    state["downloaded"].append(result["data"])
                    save_json_atomic(STATE_FILE, state)
                    success_count += 1
                else:
                    failed_list["failed"].append({
                        "fileId": futures[future]["submissionNo"],
                        "title": futures[future]["title"],
                        "url": futures[future]["url"],
                        "audField": futures[future]["auditField"],
                        "error": result["error"],
                        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "알리오",
                    })
                    save_json_atomic(FAILED_FILE, failed_list)
                    failed_count += 1
            
            if (success_count + failed_count) % 10 == 0:
                log(f"\n[PROGRESS] {success_count + failed_count}/{len(to_download)} (✓{success_count} ✗{failed_count})")
    
    log("\n" + "="*80)
    log("[STEP 3] DONE")
    log("="*80)
    log(f"\n[RESULT] Success: {success_count}")
    log(f"[RESULT] Failed: {failed_count}")
    
    print_statistics()

def print_statistics():
    log("\n" + "="*80)
    log("[STATISTICS] Download Summary")
    log("="*80)
    
    state = load_json(STATE_FILE, {"downloaded": []})
    downloaded = state.get("downloaded", [])
    
    if not downloaded:
        log("\nNo downloads yet.")
        return
    
    field_counter = defaultdict(int)
    source_counter = defaultdict(int)
    
    for item in downloaded:
        field = item.get("audField", "UNKNOWN")
        source = item.get("source", "UNKNOWN")
        field_counter[field] += 1
        source_counter[source] += 1
    
    log(f"\n[TOTAL] {len(downloaded)} files downloaded")
    
    log("\n[BY SOURCE]")
    for source, count in sorted(source_counter.items(), key=lambda x: -x[1]):
        log(f"  {source}: {count} files")
    
    log("\n[BY FIELD]")
    for field, count in sorted(field_counter.items(), key=lambda x: -x[1]):
        log(f"  {field}: {count} files")
    
    if os.path.exists(DOWNLOAD_DIR):
        actual_files = [
            f for f in os.listdir(DOWNLOAD_DIR) 
            if f.endswith((".hwp",".hwpx", ".pdf", ".xlsx", ".docx"))
            and re.search(r'\d{10}', f)
        ]
        
        log(f"\n[FILES] {len(actual_files)} files in directory")

if __name__ == "__main__":
    run()