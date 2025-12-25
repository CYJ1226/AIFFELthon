import json
import re
import os

STATE_FILE = "downloads_gamsa/state_gamsa.json"
OUT_FILE = "downloads_gamsa/failed_gamsa_re.json"


def normalize_file_id(doc_code: str) -> str:
    return re.sub(r"_a\d+$", "", doc_code)


def run():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    downloads = data.get("download", [])
    failed_ids = set()

    for item in downloads:
        meta = item.get("doc_metadata")
        if not isinstance(meta, dict):
            continue

        if meta.get("parser_state") != "fail":
            continue

        doc_code = meta.get("doc_code")
        if not doc_code:
            continue

        file_id = normalize_file_id(doc_code)
        failed_ids.add(file_id)

    failed_list = [{"fileId": fid} for fid in sorted(failed_ids)]

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"failed": failed_list}, f, ensure_ascii=False, indent=2)

    print(f"[DONE] failed_gamsa.json 생성 ({len(failed_list)}건)")


if __name__ == "__main__":
    run()
