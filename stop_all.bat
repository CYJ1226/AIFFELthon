@echo off
echo Stopping n8n...
cd /d C:\stockauto\code\n8n
docker compose down

echo Stopping PostgreSQL...
cd /d C:\stockauto\code\db
docker compose down

echo All services stopped.
pause
