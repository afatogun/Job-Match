# AWS Deployment Guide for JobMatch

This repository currently deploys on AWS using EC2 + PM2 + Nginx.
That is the active path reflected by these files:

- [deploy-ec2-pm2.sh](deploy-ec2-pm2.sh)
- [ecosystem.config.cjs](ecosystem.config.cjs)
- [nginx-ec2.conf](nginx-ec2.conf)

## Current Production Pattern (What We Use)

- One EC2 instance (Amazon Linux or Ubuntu)
- Backend process: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` (PM2)
- Frontend process: `npx serve -s dist -l 3000` (PM2)
- Nginx reverse proxy:
	- `/api/` -> `127.0.0.1:8000`
	- `/` -> `127.0.0.1:3000`

## 1. EC2 Prerequisites

Recommended instance for personal use:

- t3.small minimum (t2.micro works but is tight)
- 20-30 GB EBS
- Security group inbound:
	- TCP 22 from your IP
	- TCP 80 from 0.0.0.0/0
	- TCP 443 from 0.0.0.0/0 (if adding TLS)

## 2. Clone and Run the Deployment Script

On the EC2 instance:

```bash
git clone https://github.com/afatogun/Job-Match.git
cd Job-Match
bash deploy-ec2-pm2.sh
```

What the script does:

- installs base packages (`git`, `curl`, `nginx`, Node.js 20)
- installs `uv`
- installs PM2 and `serve`
- installs backend/frontend dependencies
- builds frontend assets
- configures PM2 apps
- configures Nginx reverse proxy
- enables PM2 startup and Nginx systemd services

## 3. Environment Configuration

The app expects `.env` at repo root. Start from `.env.example` and set:

```env
OPENAI_API_KEY=<your-key>
```

Optional for constrained instances:

```env
JOBMATCH_AUTO_CLEANUP_ON_START=true
JOBMATCH_VACUUM_ON_CLEANUP=true
JOBMATCH_RETENTION_REFRESH_RUNS_DAYS=30
JOBMATCH_RETENTION_GENERATED_DAYS=21
JOBMATCH_RETENTION_UPLOADS_DAYS=14
```

If you want data on another volume:

```env
JOBMATCH_DATA_DIR=/path/on/ebs-or-efs
```

## 4. Verify Services

```bash
pm2 status
pm2 logs jobmatch-backend --lines 100
pm2 logs jobmatch-frontend --lines 100
sudo nginx -t
sudo systemctl status nginx
curl -I http://127.0.0.1:8000/docs
curl -I http://127.0.0.1
```

## 5. Updating an Existing EC2 Deployment

```bash
cd ~/Job-Match
git pull
cd backend && ~/.local/bin/uv sync && cd ..
cd frontend && npm install && npm run build && cd ..
pm2 restart jobmatch-backend
pm2 restart jobmatch-frontend
pm2 save
sudo systemctl reload nginx
```

## 6. TLS (Recommended)

If you attach a domain, add HTTPS with Certbot:

```bash
sudo dnf install -y certbot python3-certbot-nginx || sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <your-domain>
```

## 7. Storage and Cleanup Notes

- SQLite DB, uploads and generated documents live under `data/` (or `JOBMATCH_DATA_DIR`).
- Most growth is file storage (generated DOCX/PDF, uploads), not relational row count.
- Manual cleanup endpoint:

`POST /api/settings/maintenance/cleanup`

## 8. Optional ECS/Fargate Path (Not Current Default)

If you need managed container orchestration, use ECS as an alternative.
Starter task definition is available at:

- [aws-ecs-task-definition.json](aws-ecs-task-definition.json)

For ECS, use EFS or another persistent store for `data/`.
This path is currently secondary to EC2 + PM2.
