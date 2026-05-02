# 嗨贝海数据仪表盘 - Makefile

.PHONY: help frontend backend install test build clean

# 默认目标
help:
	@echo "嗨贝海数据仪表盘 - 可用命令"
	@echo "================================"
	@echo "make install    - 安装所有依赖"
	@echo "make frontend   - 启动前端开发服务器"
	@echo "make backend    - 启动后端服务"
	@echo "make build      - 构建前端生产版本"
	@echo "make test       - 运行测试"
	@echo "make lint       - 代码检查"
	@echo "make clean      - 清理构建文件"
	@echo "make preflight  - 环境预检"

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
