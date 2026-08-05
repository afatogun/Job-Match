module.exports = {
  apps: [
    {
      name: 'jobmatch-backend',
      cwd: './backend',
      script: 'uv',
      args: 'run uvicorn app.main:app --host 0.0.0.0 --port 8000',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      env: {
        PORT: 8000,
      },
    },
    {
      name: 'jobmatch-frontend',
      cwd: './frontend',
      script: 'npx',
      args: 'serve -s dist -l 3000',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      env: {
        PORT: 3000,
      },
    },
  ],
}
