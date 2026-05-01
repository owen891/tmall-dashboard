# 天猫数据管理系统 - 部署指南

## 目录
- [本地开发部署](#本地开发部署)
- [Docker 部署](#docker-部署)
- [生产环境部署](#生产环境部署)
- [数据备份与恢复](#数据备份与恢复)
- [常见问题](#常见问题)

---

## 本地开发部署

### 前置要求
- Python 3.10+
- Node.js 18+
- npm 或 yarn

### 1. 克隆项目
```bash
git clone <repository-url>
cd tmall-dashboard
```

### 2. 后端部署

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 初始化数据库（首次运行自动创建）
python run.py
```

后端服务将在 http://localhost:8000 启动

### 3. 前端部署

```bash
cd frontend

# 安装依赖
npm install

# 开发模式启动
npm run dev
```

前端服务将在 http://localhost:5173 启动

### 4. 导入示例数据

```bash
cd backend
python simple_import.py
```

---

## Docker 部署

### 1. 快速启动

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

访问 http://localhost:5173

### 2. 停止服务

```bash
docker-compose down
```

### 3. 重新构建

```bash
docker-compose up -d --build
```

### 4. 数据持久化

Docker 部署会自动挂载以下目录：
- `./backend/data` → `/app/data` (数据库文件)
- `./backend/logs` → `/app/logs` (日志文件)

---

## 生产环境部署

### 1. 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /var/www/tmall-dashboard/dist;
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. 使用 HTTPS

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # ... 其他配置同上
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### 3. 使用 PM2 管理后端

```bash
cd backend
npm install -g pm2

# 启动服务
pm2 start uvicorn -- name "tmall-api" -- app app.main:app --host 0.0.0.0 --port 8000

# 查看状态
pm2 list

# 查看日志
pm2 logs tmall-api

# 重启
pm2 restart tmall-api
```

### 4. 系统服务配置 (systemd)

创建 `/etc/systemd/system/tmall-backend.service`:

```ini
[Unit]
Description=Tmall Dashboard Backend
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/tmall-dashboard/backend
Environment="PATH=/opt/tmall-dashboard/backend/venv/bin"
ExecStart=/opt/tmall-dashboard/backend/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl enable tmall-backend
sudo systemctl start tmall-backend
sudo systemctl status tmall-backend
```

---

## 数据备份与恢复

### 1. 数据库备份

```bash
# 备份
cd backend/data
cp dashboard.db dashboard.db.backup.$(date +%Y%m%d)

# 或使用 sqlite3
sqlite3 dashboard.db ".backup '/path/to/backup.db'"
```

### 2. 恢复数据

```bash
cd backend/data
cp /path/to/backup.db dashboard.db
```

### 3. 自动备份脚本

创建 `/opt/tmall-dashboard/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/tmall-dashboard/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="/opt/tmall-dashboard/backend/data/dashboard.db"

mkdir -p $BACKUP_DIR
cp $DB_FILE "$BACKUP_DIR/dashboard.db.$DATE"

# 保留最近30天的备份
find $BACKUP_DIR -name "dashboard.db.*" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/dashboard.db.$DATE"
```

添加定时任务：
```bash
crontab -e
# 每天凌晨2点备份
0 2 * * * /opt/tmall-dashboard/backup.sh >> /var/log/backup.log 2>&1
```

---

## 常见问题

### 1. 端口被占用

```bash
# 查找占用端口的进程
lsof -i :8000
lsof -i :5173

# 或修改端口
# 后端：uvicorn app.main:app --port 8001
# 前端：npm run dev -- --port 5174
```

### 2. 数据库初始化失败

```bash
cd backend
rm -f data/dashboard.db
python run.py  # 重新初始化
```

### 3. 前端无法连接后端

1. 检查后端是否正常运行
2. 检查 CORS 配置
3. 检查前端 `.env` 中的 API 地址

### 4. 数据导入失败

1. 确保 Excel 文件格式正确
2. 检查文件编码（推荐 UTF-8）
3. 查看后端日志获取详细错误信息

### 5. 性能优化

- 启用数据库索引
- 使用 Redis 缓存（生产环境）
- 启用 gzip 压缩
- 配置 CDN 加速静态资源

---

## 环境变量

| 变量名 | 默认值 | 描述 |
|--------|--------|------|
| `DATABASE_URL` | `sqlite:///./data/dashboard.db` | 数据库连接地址 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `CORS_ORIGINS` | `http://localhost:5173` | 允许的跨域来源 |

---

## 联系方式

如有问题，请提交 Issue 或联系开发团队。
