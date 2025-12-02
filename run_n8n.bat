@echo off
cd /d C:\stockauto\code\n8n\n8n_com
echo Starting n8n server...
docker compose -f n8n_docker_compose.yml up -d
echo n8n started.
echo http://localhost:5678
pause
