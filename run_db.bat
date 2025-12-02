@echo off
cd /d C:\stockauto\code\n8n\db_com
echo Starting PostgreSQL server...
docker compose -f db_docker_compose.yml up -d
echo PostgreSQL started.
echo http://localhost:5432
pause
