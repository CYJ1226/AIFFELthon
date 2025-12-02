FROM docker.n8n.io/n8nio/n8n:latest

# 1. 관리자 권한으로 전환
USER root

# 2. 파이썬 및 필수 빌드 도구 설치 (Alpine 명령어인 apk 사용)
# build-base: pandas 같은 라이브러리가 설치될 때 필요한 컴파일 도구들입니다.
RUN apk add --update --no-cache python3 py3-pip build-base python3-dev libffi-dev

# 3. 가상 환경 생성 (시스템 충돌 방지)
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 4. 라이브러리 설치
RUN pip install --upgrade pip && \
    pip install requests pandas beautifulsoup4

# 5. 보안을 위해 다시 node 유저로 전환
USER node

