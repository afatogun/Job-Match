#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/Job-Match}"
APP_USER="$(whoami)"

install_base_packages() {
  if command -v dnf >/dev/null 2>&1; then
    sudo dnf update -y
    sudo dnf install -y git curl nginx
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
    sudo dnf install -y nodejs
  else
    sudo apt update
    sudo apt install -y git curl nginx
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
  fi
}

install_base_packages
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo npm install -g pm2 serve

if [ ! -d "$APP_DIR/.git" ]; then
  echo "Repository not found at $APP_DIR"
  echo "Clone first: git clone https://github.com/afatogun/Job-Match.git $APP_DIR"
  exit 1
fi

cd "$APP_DIR"
cp .env.example .env 2>/dev/null || true

cd backend
"$HOME/.local/bin/uv" sync
cd ../frontend
npm install
npm run build

cd "$APP_DIR"
cat > ecosystem.config.cjs <<'EOF'
module.exports = {
  apps: [
    {
      name: 'jobmatch-backend',
      cwd: './backend',
      script: process.env.HOME + '/.local/bin/uv',
      args: 'run uvicorn app.main:app --host 0.0.0.0 --port 8000',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      env: {
        JOBMATCH_AUTO_CLEANUP_ON_START: 'true',
        JOBMATCH_VACUUM_ON_CLEANUP: 'true',
        JOBMATCH_RETENTION_REFRESH_RUNS_DAYS: '30',
        JOBMATCH_RETENTION_GENERATED_DAYS: '21',
        JOBMATCH_RETENTION_UPLOADS_DAYS: '14'
      }
    },
    {
      name: 'jobmatch-frontend',
      cwd: './frontend',
      script: 'npx',
      args: 'serve -s dist -l 3000',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false
    }
  ]
}
EOF

cat > /tmp/jobmatch-nginx.conf <<'EOF'
server {
    listen 80;
    server_name _;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo mv /tmp/jobmatch-nginx.conf /etc/nginx/conf.d/jobmatch.conf
sudo rm -f /etc/nginx/conf.d/default.conf
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

pm2 delete all || true
pm2 start ecosystem.config.cjs
pm2 save
sudo env PATH="$PATH:/usr/bin" /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u "$APP_USER" --hp "$HOME"

echo "Deployment complete."
