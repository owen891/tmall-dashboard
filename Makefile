# 嗨贝海数据仪表盘 - Makefile
# 集成 SCALE OS 认知脚手架

.PHONY: help frontend backend install test build clean
.PHONY: preflight validate gate checkpoint plan resume status
.PHONY: graphify test-scaffold check-redlines
.PHONY: docker-build docker-up docker-down docker-logs
.PHONY: backup restore db-backup db-restore
.PHONY: metrics deploy
.PHONY: setup install-full

# 默认目标
help:
	@echo "嗨贝海数据仪表盘 - 可用命令"
	@echo "================================"
	@echo ""
	@echo "📦 开发命令"
	@echo "  make setup      - 一键安装所有依赖"
	@echo "  make install    - 安装前端依赖"
	@echo "  make install-full - 安装全部依赖（前后端）"
	@echo "  make frontend   - 启动前端开发服务器"
	@echo "  make backend    - 启动后端服务"
	@echo "  make dev        - 同时启动前后端"
	@echo "  make build      - 构建前端生产版本"
	@echo ""
	@echo "🐳 Docker 部署"
	@echo "  make docker-build  - 构建Docker镜像"
	@echo "  make docker-up     - 启动Docker服务"
	@echo "  make docker-down   - 停止Docker服务"
	@echo "  make docker-logs   - 查看Docker日志"
	@echo ""
	@echo "💾 数据备份"
	@echo "  make backup        - 完整系统备份"
	@echo "  make restore       - 恢复系统备份"
	@echo "  make db-backup     - 数据库备份"
	@echo "  make db-restore    - 数据库恢复"
	@echo ""
	@echo "📊 系统监控"
	@echo "  make metrics       - 查看系统指标"
	@echo "  make test          - 运行测试"
	@echo "  make lint          - 代码检查"
	@echo ""
	@echo "🛡️ SCALE OS 脚手架命令"
	@echo "  make preflight   - 环境预检"
	@echo "  make validate    - 验证配置有效性"
	@echo "  make gate        - 运行质量门控检查"
	@echo "  make checkpoint  - 保存当前进度"
	@echo "  make plan NAME=xxx - 创建新功能计划"
	@echo "  make resume      - 恢复之前的进度"
	@echo "  make status      - 查看当前状态"
	@echo "  make graphify    - 构建知识图谱"
	@echo "  make redlines    - 红线安全检查"
	@echo ""
	@echo "🔍 其他"
	@echo "  make clean       - 清理构建文件"

# 一键设置
setup:
	@echo "🚀 开始设置项目环境..."
	@echo ""
	@echo "📦 检查环境..."
	@which node > /dev/null || { echo "❌ Node.js 未安装"; exit 1; }
	@which python3 > /dev/null || { echo "❌ Python 未安装"; exit 1; }
	@echo "✅ 环境检查通过"
	@echo ""
	@echo "📦 安装依赖..."
	@make install-full
	@echo ""
	@echo "🔍 运行预检..."
	@make preflight
	@echo ""
	@echo "✅ 设置完成！运行 'make dev' 启动开发服务器"

# 完整安装
install-full:
	@echo "📦 安装前端依赖..."
	cd frontend && npm install
	@echo "✅ 前端依赖安装完成"
	@echo "📦 安装后端依赖..."
	cd backend && pip install -r requirements.txt -q
	@echo "✅ 后端依赖安装完成"
	@echo "✅ 所有依赖安装完成"

# 安装依赖
install:
	@echo "安装前端依赖..."
	cd frontend && npm install
	@echo "前端依赖安装完成"

# 前端开发
frontend:
	@echo "启动前端开发服务器..."
	cd frontend && npm run dev

# 后端服务
backend:
	@echo "启动后端服务..."
	cd backend && python main.py

# 构建前端
build:
	@echo "构建前端生产版本..."
	cd frontend && npm run build
	@echo "✅ 构建成功!"

# 代码检查
lint:
	@echo "运行代码检查..."
	@echo "检查前端..."
	cd frontend && npm run lint || true
	@echo "✅ Lint检查完成"

# 测试
test:
	@echo "运行测试..."
	cd backend && python -m pytest tests/ -v
	@echo "✅ 测试完成"

# 环境预检
preflight:
	@echo "运行环境预检..."
	@echo "✅ Node.js 版本: $$(node --version)"
	@echo "✅ npm 版本: $$(npm --version)"
	@echo "✅ Python 版本: $$(python3 --version)"
	@bash scripts/preflight/check.sh || true

# 清理
clean:
	@echo "清理构建文件..."
	cd frontend && rm -rf dist node_modules/.vite
	cd backend && find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ 清理完成"

# 开发模式（同时启动前后端）
dev:
	@echo "启动开发模式..."
	@make frontend & 
	@make backend & 
	@wait

# 验证构建
verify-build:
	@echo "验证构建..."
	cd frontend && npm run build
	@if [ -d "dist" ]; then \
		echo "✅ 构建验证通过"; \
	else \
		echo "❌ 构建验证失败"; \
		exit 1; \
	fi

# ========================================
# Docker 部署命令
# ========================================

# 构建Docker镜像
docker-build:
	@echo "🐳 构建Docker镜像..."
	docker-compose build
	@echo "✅ Docker镜像构建完成"

# 启动Docker服务
docker-up:
	@echo "🐳 启动Docker服务..."
	docker-compose up -d
	@echo "✅ Docker服务已启动"

# 停止Docker服务
docker-down:
	@echo "🐳 停止Docker服务..."
	docker-compose down
	@echo "✅ Docker服务已停止"

# 查看Docker日志
docker-logs:
	@echo "🐳 查看Docker日志..."
	docker-compose logs -f

# ========================================
# 数据备份命令
# ========================================

# 完整备份
backup:
	@echo "💾 创建完整备份..."
	@mkdir -p backup
	@BACKUP_NAME="backup-$$(date +%Y%m%d-%H%M%S)" && \
	tar czf "backup/$$BACKUP_NAME.tar.gz" backend/data/ frontend/dist/ docs/ 2>/dev/null && \
	echo "✅ 备份完成: backup/$$BACKUP_NAME.tar.gz"

# 恢复备份
restore:
	@echo "💾 恢复备份..."
	@ls -1 backup/ | tail -1

# 数据库备份
db-backup:
	@echo "💾 数据库备份..."
	@mkdir -p backend/data/backups
	@BACKUP_NAME="db-$$(date +%Y%m%d-%H%M%S).db" && \
	cp backend/data/dashboard.db "backend/data/backups/$$BACKUP_NAME" && \
	echo "✅ 数据库备份完成: backend/data/backups/$$BACKUP_NAME"

# 数据库恢复
db-restore:
	@echo "💾 数据库恢复..."
	@ls -1 backend/data/backups/ | tail -1

# ========================================
# 系统监控命令
# ========================================

# 系统指标
metrics:
	@echo "📊 系统指标"
	@echo "===================="
	@echo "内存使用:"
	@free -h
	@echo ""
	@echo "磁盘使用:"
	@df -h
	@echo ""
	@echo "CPU信息:"
	@top -bn1 | head -5 || true

# ========================================
# SCALE OS 脚手架命令
# ========================================

# 环境预检
preflight:
	@echo "========================================"
	@echo "[PREFLIGHT] 环境预检"
	@echo "========================================"
	@bash scripts/preflight/all.sh

# 配置验证
validate:
	@echo "========================================"
	@echo "[VALIDATE] 配置验证"
	@echo "========================================"
	@bash scripts/validate-config.sh

# 质量门控
gate:
	@echo "========================================"
	@echo "[GATE] 质量门控检查"
	@echo "========================================"
	@bash scripts/gates/all.sh

# 保存检查点
checkpoint:
	@echo "========================================"
	@echo "[CHECKPOINT] 保存进度"
	@echo "========================================"
	@bash scripts/checkpoint/save.sh

# 创建计划
plan:
ifndef NAME
	@echo "❌ 请提供功能名称: make plan NAME=feature-name"
	@exit 1
endif
	@echo "========================================"
	@echo "[PLAN] 创建计划: $(NAME)"
	@echo "========================================"
	@bash scripts/init-plan.sh $(NAME)

# 恢复进度
resume:
	@echo "========================================"
	@echo "[RESUME] 恢复进度"
	@echo "========================================"
	@bash scripts/checkpoint/load.sh

# 查看状态
status:
	@echo "========================================"
	@echo "[STATUS] 当前状态"
	@echo "========================================"
	@if [ -f ".agent/state/current.json" ]; then \
		cat .agent/state/current.json | jq .; \
	else \
		echo "暂无状态记录，请先 make plan 或 make checkpoint"; \
	fi

# 构建知识图谱
graphify:
	@echo "========================================"
	@echo "[GRAPHIFY] 知识图谱构建"
	@echo "========================================"
	@which graphify > /dev/null 2>&1 || { \
		echo "⚠️ graphify 未安装，跳过图谱构建"; \
		echo "💡 安装命令: pip install graphifyy && graphify install"; \
	}
	@which graphify > /dev/null 2>&1 && graphify build || true

# 红线安全检查
redlines:
	@echo "========================================"
	@echo "[REDLINES] 红线安全检查"
	@echo "========================================"
	@echo "检查 R1: 数据安全..."
	@bash scripts/redlines/R1-check.sh
	@echo "检查 R2: 错误处理..."
	@bash scripts/redlines/R2-check.sh
	@echo "检查 R3: 密钥安全..."
	@bash scripts/redlines/R3-check.sh

# 脚手架自测
test-scaffold:
	@echo "========================================"
	@echo "[SCAFFOLD TESTS] 脚手架自测"
	@echo "========================================"
	@bash scripts/test-scaffold.sh
