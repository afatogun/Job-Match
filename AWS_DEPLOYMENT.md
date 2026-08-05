# AWS deployment guide for JobMatch

## Recommended approach

Use a containerized backend on AWS ECS Fargate with persistent storage on EFS and a static frontend on S3 + CloudFront.

### 1. Build and push the backend image

```bash
aws ecr create-repository --repository-name jobmatch-backend
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com

docker build -t jobmatch-backend .
docker tag jobmatch-backend:latest <account-id>.dkr.ecr.<region>.amazonaws.com/jobmatch-backend:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/jobmatch-backend:latest
```

### 2. Prepare AWS resources

- ECS cluster
- ECS service on Fargate
- EFS filesystem mounted at /data
- Secrets Manager entry for OPENAI_API_KEY
- Public ALB or NLB for the backend

### 3. Deploy the backend

- Use [aws-ecs-task-definition.json](aws-ecs-task-definition.json) as the starting point.
- Replace the placeholder values for execution role, task role, ECR image, region, and EFS filesystem ID.
- Set `OPENAI_API_KEY` from Secrets Manager or a secure parameter.

### 4. Deploy the frontend

Build the frontend for production and upload it to S3:

```bash
cd frontend
npm install
npm run build
aws s3 sync dist s3://<your-bucket-name> --delete
```

Then configure CloudFront to serve the S3 bucket.

### 5. Configure environment

Set the frontend production API base URL:

```env
VITE_API_URL=https://<your-backend-domain>/api
```

For the backend, set:

```env
OPENAI_API_KEY=<value>
JOBMATCH_DATA_DIR=/data
ALLOWED_ORIGINS=https://<your-frontend-domain>
```

## Notes

- The backend writes uploaded CVs, generated documents, and SQLite data under /data.
- EFS is the simplest way to preserve state across container restarts.
- For a single-user prototype, ECS Fargate + EFS + CloudFront is a sensible first deployment.

## EC2 + PM2 option

If you are running a micro instance, EC2 + PM2 is simpler than ECS.

1. Clone the repository onto the instance.
2. Run `deploy-ec2-pm2.sh` from the repo root.
3. Open inbound HTTP (port 80) on the EC2 security group.

The script configures PM2 for backend/frontend and installs Nginx as a reverse proxy.

## Storage controls for micro instances

Use these backend environment variables to avoid disk growth:

```env
JOBMATCH_AUTO_CLEANUP_ON_START=true
JOBMATCH_VACUUM_ON_CLEANUP=true
JOBMATCH_RETENTION_REFRESH_RUNS_DAYS=30
JOBMATCH_RETENTION_GENERATED_DAYS=21
JOBMATCH_RETENTION_UPLOADS_DAYS=14
```

You can also trigger cleanup manually:

`POST /api/settings/maintenance/cleanup`

This removes old refresh logs, old generated document folders, and stale uploaded CV files.

## Should you switch to MongoDB?

MongoDB will not reduce the biggest storage pressure in this app, because most growth comes from files (generated DOCX/PDF and uploads), not relational query limits.

Use this order of optimizations first:

1. Keep SQLite, enable retention cleanup (already supported in backend).
2. Move `data/` to a larger EBS volume or EFS.
3. Offload generated files/uploads to S3 with lifecycle rules.

MongoDB only makes sense if you need multi-user concurrency and document-query flexibility beyond SQLite.
