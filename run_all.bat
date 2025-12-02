@echo off
echo Starting PostgreSQL and n8n...
cd /d C:\stockauto\code\n8n\n8n_com
docker compose -f n8n_docker_compose.yml up -d
echo http://localhost:5678


cd /d C:\stockauto\code\n8n\db_com
docker compose -f db_docker_compose.yml up -d
echo http://localhost:5432
echo All services started.
pause
