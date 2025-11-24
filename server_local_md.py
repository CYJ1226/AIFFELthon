import os
import time
import traceback
import sys
import tempfile
import re
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

# Marker 라이브러리 임포트
try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser
    print("✅ Marker 라이브러리 로드 성공")
except ImportError:
    print("❌ Marker 라이브러리가 설치되지 않았습니다.")
    sys.exit(1)

app = FastAPI()
converter = None

OUTPUT_DIR = os.path.abspath("./output_server_md")

# ----------------------------------------------------------------
# 마크다운 정제 함수
# ----------------------------------------------------------------
def clean_markdown_text(md_text):
    lines = md_text.split('\n')
    cleaned_lines = []
    
    in_table = False
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
            line = re.sub(r'<br\s*/?>', ' ', line, flags=re.IGNORECASE)
            cells = line.split('|')
            cleaned_cells = [re.sub(r'\s+', ' ', c).strip() for c in cells]
            line = '|'.join(cleaned_cells)
        else:
            in_table = False
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)

# ----------------------------------------------------------------
# 모델 로드
# ----------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    global converter
    print(f"🚀 서버 시작... 저장 경로: {OUTPUT_DIR}")
    
    # 시작 시 폴더 생성 (권한 확인용)
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
    try:
        config_parser = ConfigParser({
            "output_format": "markdown",
            "use_llm": False,
            "force_ocr": False,        
            "ocr_all_pages": False,
            "disable_image_extraction": True,
            "batch_multiplier": 8
        })
        
        model_dict = create_model_dict()
        
        converter = PdfConverter(
            artifact_dict=model_dict,
            config=config_parser.generate_config_dict(),
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer()
        )
        print("✅ 모델 로딩 완료! n8n 요청 대기 중...")
    except Exception as e:
        print(f"❌ 모델 로딩 실패: {e}")
        traceback.print_exc()
        sys.exit(1)

class ConversionResponse(BaseModel):
    filename: str
    markdown: str
    metadata: dict

# ----------------------------------------------------------------
# API 엔드포인트
# ----------------------------------------------------------------
@app.post("/convert", response_model=ConversionResponse)
async def convert_pdf(file: UploadFile = File(...)):
    if not converter:
        raise HTTPException(status_code=503, detail="Server is initializing")

    suffix = ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name

    try:
        # 1. Marker 변환 실행
        rendered = converter(tmp_path)
        
        full_text = rendered.markdown
        metadata = rendered.metadata or {}

        # 2. [후처리] 마크다운 정제
        cleaned_text = clean_markdown_text(full_text)


        # 3. 파일명에서 경로(슬래시 등) 제거하고 순수 파일명만 추출 (Sanitize)
        safe_filename = os.path.basename(file.filename)
        file_base = os.path.splitext(safe_filename)[0]
        
        # 4. 저장 경로 생성
        save_path = os.path.join(OUTPUT_DIR, f"{file_base}.md")
        
        # 5. 폴더가 혹시 없으면 다시 생성
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(cleaned_text)
            
        print(f"💾 파일 저장 완료: {save_path}")
        # ---------------------------------------------------------

        return {
            "filename": safe_filename,
            "markdown": cleaned_text, 
            "metadata": metadata
        }

    except Exception as e:
        print(f"❌ 변환 에러: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": "Local Native", "output_dir": OUTPUT_DIR}