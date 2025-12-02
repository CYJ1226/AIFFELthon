@echo off
REM ========== UTF-8 출력 설정 ==========
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ========== BAT 파일 위치를 기준으로 실행 ==========
cd /d "%~dp0"

title N8N 자동 실행 (빠른 재사용 모드)

echo ===========================================
echo        🚀 N8N 자동 실행 시스템 (B 모드)
echo ===========================================
echo  - 기존 도커 컨테이너가 있으면 빠르게 시작합니다
echo  - 없으면 자동으로 설치 후 실행합니다
echo ===========================================
echo.

REM 1) Docker 설치 여부 확인
echo [1/6] Docker 설치 여부 확인 중...
docker --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker Desktop이 설치되어 있지 않습니다.
    echo 👉 https://www.docker.com/products/docker-desktop 설치 후 다시 실행해주세요.
    pause
    exit /b
)
echo ✅ Docker 설치 확인됨.
echo.

REM 2) Docker Desktop 실행 상태 확인
echo [2/6] Docker Desktop 실행 상태 확인 중...
docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo 🔸 Docker Desktop이 실행되고 있지 않습니다. 자동 실행합니다...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo ⏳ Docker Desktop이 실행될 때까지 대기합니다...
)

:wait_docker
docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    timeout /t 3 >nul
    goto wait_docker
)
echo ✅ Docker Desktop 실행됨.
echo.

REM 3) python_scripts 폴더 확인
echo [3/6] python_scripts 폴더 확인 중...
IF NOT EXIST python_scripts (
    echo ❌ python_scripts 폴더가 없습니다. 자동 생성합니다.
    mkdir python_scripts
)
echo ⭐ python_scripts 폴더 확인됨.

REM Python 스크립트 검사
set scripts=alio_downloader.py gamsa_downloader.py laws_downloader.py download_all.py
set missing=0

echo [3-1] Python 파일 검사 중...
for %%F in (%scripts%) do (
    if NOT EXIST python_scripts\%%F (
        echo ❌ python_scripts\%%F 파일이 없습니다.
        set missing=1
    )
)
if %missing%==1 (
    echo.
    echo ❗필수 Python 파일이 누락되어 있습니다.
    echo 👉 C:\stockauto\code\n8n\python_scripts 에 4개 파일을 넣고 다시 실행하세요.
    pause
    exit /b
)
echo ✅ Python 파일 정상.
echo.

REM 4) docker-compose.yml 자동 생성 확인
echo [4/6] docker-compose.yml 확인...
IF NOT EXIST docker-compose.yml (
    echo 🔸 docker-compose.yml 없음 → 자동 생성합니다.

(
echo version: '3.8'
echo.
echo volumes:
echo   db_storage:
echo   n8n_storage:
echo.
echo services:
echo   postgres:
echo     image: postgres:16
echo     restart: always
echo     environment:
echo       - POSTGRES_USER=n8n
echo       - POSTGRES_PASSWORD=n8npw
echo       - POSTGRES_DB=n8n
echo       - POSTGRES_NON_ROOT_USER=n8n
echo       - POSTGRES_NON_ROOT_PASSWORD=n8npw
echo     volumes:
echo       - db_storage:/var/lib/postgresql/data
echo     healthcheck:
echo       test: ['CMD-SHELL', 'pg_isready -h localhost -U n8n -d n8n']
echo       interval: 5s
echo       timeout: 5s
echo       retries: 10
echo.
echo   n8n:
echo     build: .
echo     restart: always
echo     environment:
echo       - DB_TYPE=postgresdb
echo       - DB_POSTGRESDB_HOST=postgres
echo       - DB_POSTGRESDB_PORT=5432
echo       - DB_POSTGRESDB_DATABASE=n8n
echo       - DB_POSTGRESDB_USER=n8n
echo       - DB_POSTGRESDB_PASSWORD=n8npw
echo     ports:
echo       - "5678:5678"
echo     volumes:
echo       - ./python_scripts:/home/node/python_scripts
echo     depends_on:
echo       postgres:
echo         condition: service_healthy
)> docker-compose.yml
)
echo ✅ docker-compose.yml 정상 확인됨.
echo.

REM 5) Dockerfile 자동 생성 확인
echo [5/6] Dockerfile 확인...
IF NOT EXIST Dockerfile (
    echo 🔸 Dockerfile 없음 → 자동 생성합니다.

(
echo FROM n8nio/n8n:latest
echo RUN apk add --no-cache python3 py3-pip
echo RUN pip install requests pandas beautifulsoup4
)> Dockerfile
)
echo ✅ Dockerfile 정상 확인됨.
echo.

REM 6) 컨테이너 존재 여부 검사
echo [6/6] 기존 컨테이너 존재 확인 중...

docker ps -a --format "{{.Names}}" | findstr /i "n8n-n8n-1" >nul
IF %ERRORLEVEL% EQU 0 (
    echo ⭐ 기존 n8n 컨테이너 발견 → 빠르게 시작합니다
    docker start n8n-postgres-1
    docker start n8n-n8n-1
) ELSE (
    echo 🔸 기존 컨테이너 없음 → 새로 설치합니다
    docker-compose up -d --build
)

echo.
echo ===========================================
echo      🎉 N8N 실행 준비 완료!
echo ===========================================
echo  브라우저가 자동으로 열립니다...
echo http://localhost:5678
echo.

start "" http://localhost:5678

pause
