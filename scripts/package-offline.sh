#!/bin/bash
# Langflow 离线环境打包脚本
# 用途：将完整的开发环境打包，用于离线服务器部署

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION=$(date +%Y%m%d-%H%M%S)
PACKAGE_NAME="langflow-offline-${VERSION}"
PACKAGE_DIR="$PROJECT_ROOT/$PACKAGE_NAME"

# 函数：打印信息
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# 检查是否在项目根目录
if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    error "未找到 pyproject.toml，请确保在项目根目录运行此脚本"
fi

info "开始打包 Langflow 离线环境..."
info "项目根目录: $PROJECT_ROOT"
info "打包目录: $PACKAGE_DIR"

# 创建打包目录
mkdir -p "$PACKAGE_DIR"
cd "$PACKAGE_DIR"

# 1. 检查虚拟环境是否存在
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    error "未找到 .venv 目录，请先运行 'make init'"
fi

# 2. 打包 Python 虚拟环境
info "打包 Python 虚拟环境..."
VENV_SIZE=$(du -sh "$PROJECT_ROOT/.venv" | cut -f1)
info "虚拟环境大小: $VENV_SIZE"

tar -czf langflow-venv.tar.gz \
    -C "$PROJECT_ROOT" \
    --exclude='.venv/__pycache__' \
    --exclude='.venv/lib/python*/test' \
    --exclude='.venv/lib/python*/distutils' \
    --exclude='.venv/lib/python*/idlelib' \
    --exclude='.venv/lib/python*/tkinter' \
    --exclude='.venv/lib/python*/turtledemo' \
    .venv

VENV_PACKAGE_SIZE=$(du -sh langflow-venv.tar.gz | cut -f1)
info "虚拟环境打包完成，大小: $VENV_PACKAGE_SIZE"

# 3. 打包前端 node_modules
if [ -d "$PROJECT_ROOT/src/frontend/node_modules" ]; then
    info "打包前端 node_modules..."
    NODE_SIZE=$(du -sh "$PROJECT_ROOT/src/frontend/node_modules" | cut -f1)
    info "node_modules 大小: $NODE_SIZE"

    tar -czf langflow-node_modules.tar.gz \
        -C "$PROJECT_ROOT/src/frontend" \
        node_modules

    NODE_PACKAGE_SIZE=$(du -sh langflow-node_modules.tar.gz | cut -f1)
    info "node_modules 打包完成，大小: $NODE_PACKAGE_SIZE"
else
    warn "未找到 node_modules 目录，跳过前端依赖打包"
fi

# 4. 打包项目源代码（排除已打包的目录）
info "打包项目源代码..."
tar -czf langflow-source.tar.gz \
    -C "$PROJECT_ROOT" \
    --exclude='.venv' \
    --exclude='src/frontend/node_modules' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='test-results' \
    --exclude='*.log' \
    --exclude='.mypy_cache' \
    --exclude='dist' \
    --exclude='build' \
    --exclude='*.egg-info' \
    --exclude='node_modules' \
    --exclude='langflow-offline-*' \
    .

SOURCE_SIZE=$(du -sh langflow-source.tar.gz | cut -f1)
info "源代码打包完成，大小: $SOURCE_SIZE"

# 5. 打包 uv Python 解释器（可选）
if [ -d "$HOME/.local/share/uv/python" ]; then
    info "打包 uv Python 解释器..."
    tar -czf uv-python.tar.gz \
        -C "$HOME/.local/share/uv" \
        python 2>/dev/null || warn "无法打包 Python 解释器（可能需要 root 权限）"

    if [ -f "uv-python.tar.gz" ]; then
        PYTHON_SIZE=$(du -sh uv-python.tar.gz | cut -f1)
        info "Python 解释器打包完成，大小: $PYTHON_SIZE"
    fi
else
    warn "未找到 uv Python 解释器目录，跳过"
fi

# 6. 创建部署脚本
info "创建部署脚本..."
cat > deploy.sh << 'DEPLOY_EOF'
#!/bin/bash
# Langflow 离线部署脚本

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# 配置
PROJECT_DIR="${1:-/opt/langflow}"
VENV_DIR="$PROJECT_DIR/.venv"
FRONTEND_DIR="$PROJECT_DIR/src/frontend"

info "开始部署 Langflow 到: $PROJECT_DIR"

# 检查必需文件
if [ ! -f "langflow-source.tar.gz" ]; then
    error "未找到 langflow-source.tar.gz"
fi

if [ ! -f "langflow-venv.tar.gz" ]; then
    error "未找到 langflow-venv.tar.gz"
fi

# 创建项目目录
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# 解压源代码
info "解压源代码..."
tar -xzf "$(dirname "$0")/langflow-source.tar.gz"

# 解压虚拟环境
info "解压 Python 虚拟环境..."
mkdir -p "$VENV_DIR"
tar -xzf "$(dirname "$0")/langflow-venv.tar.gz" -C "$PROJECT_DIR"

# 解压前端依赖
if [ -f "$(dirname "$0")/langflow-node_modules.tar.gz" ]; then
    info "解压前端依赖..."
    mkdir -p "$FRONTEND_DIR"
    tar -xzf "$(dirname "$0")/langflow-node_modules.tar.gz" -C "$FRONTEND_DIR"
else
    warn "未找到前端依赖包，需要手动安装: cd $FRONTEND_DIR && npm install"
fi

# 解压 Python 解释器（如果存在）
if [ -f "$(dirname "$0")/uv-python.tar.gz" ]; then
    info "解压 Python 解释器..."
    mkdir -p ~/.local/share/uv
    tar -xzf "$(dirname "$0")/uv-python.tar.gz" -C ~/.local/share/uv
fi

# 修复虚拟环境中的路径
info "修复虚拟环境路径..."
cd "$VENV_DIR"

# 获取旧的 Python 路径
OLD_PYTHON=$(head -1 bin/python 2>/dev/null | sed 's/#!//' | tr -d ' ' || echo "")
if [ -n "$OLD_PYTHON" ] && [ "$OLD_PYTHON" != "$VENV_DIR/bin/python" ]; then
    info "更新 Python 路径: $OLD_PYTHON -> $VENV_DIR/bin/python"
    find bin -type f -exec sed -i "s|$OLD_PYTHON|$VENV_DIR/bin/python|g" {} \; 2>/dev/null || true
fi

# 设置权限
chmod +x "$VENV_DIR/bin"/* 2>/dev/null || true

# 验证安装
info "验证安装..."
if [ -f "$VENV_DIR/bin/python" ]; then
    PYTHON_VERSION=$("$VENV_DIR/bin/python" --version 2>&1 || echo "未知")
    info "Python 版本: $PYTHON_VERSION"
else
    warn "未找到 Python 解释器"
fi

info "部署完成！"
info "项目目录: $PROJECT_DIR"
info "虚拟环境: $VENV_DIR"
info ""
info "使用方法:"
info "  cd $PROJECT_DIR"
info "  source .venv/bin/activate"
info "  uv run langflow run"
DEPLOY_EOF

chmod +x deploy.sh

# 7. 创建 README
info "创建 README 文档..."
cat > README.md << 'README_EOF'
# Langflow 离线部署包

## 📦 文件说明

- `langflow-source.tar.gz`: 项目源代码（排除虚拟环境和 node_modules）
- `langflow-venv.tar.gz`: Python 虚拟环境（包含所有 Python 依赖包）
- `langflow-node_modules.tar.gz`: 前端 Node.js 依赖（如果存在）
- `uv-python.tar.gz`: uv Python 解释器缓存（可选，如果存在）
- `deploy.sh`: 自动部署脚本
- `README.md`: 本文件

## 🚀 部署步骤

### 方法 1: 使用自动部署脚本（推荐）

```bash
# 1. 将整个目录传输到目标服务器
# 使用 scp, rsync 或其他方式
scp -r langflow-offline-* user@target-server:/tmp/

# 2. 在目标服务器上执行部署
ssh user@target-server
cd /tmp/langflow-offline-*
bash deploy.sh /opt/langflow

# 3. 验证和运行
cd /opt/langflow
source .venv/bin/activate
uv run langflow --version
uv run langflow run
```

### 方法 2: 手动部署

```bash
# 1. 创建项目目录
mkdir -p /opt/langflow
cd /opt/langflow

# 2. 解压文件
tar -xzf langflow-source.tar.gz
tar -xzf langflow-venv.tar.gz
tar -xzf langflow-node_modules.tar.gz -C src/frontend

# 3. 修复虚拟环境路径（如果需要）
cd .venv
# 编辑 bin/activate 和 bin/python 中的路径

# 4. 运行
source .venv/bin/activate
uv run langflow run
```

## ⚠️ 注意事项

1. **系统要求**:
   - 操作系统：Linux（与源服务器相同或兼容）
   - 架构：x86_64 或 arm64（必须匹配源服务器）
   - 磁盘空间：至少 15-20 GB

2. **必需工具**:
   - `tar` 和 `gzip`（解压工具）
   - `bash`（脚本执行）
   - `uv`（如果未打包 Python 解释器，需要安装 uv）

3. **架构兼容性**:
   - 如果源服务器和目标服务器架构不同，部分二进制包可能无法使用
   - 建议在相同架构的服务器间部署，或使用 Docker 容器

4. **路径问题**:
   - 虚拟环境中的脚本可能包含硬编码路径
   - 部署脚本会自动尝试修复，但某些情况下可能需要手动调整

5. **前端构建**:
   - 如果前端需要重新构建，执行：
     ```bash
     cd src/frontend
     npm install  # 如果 node_modules 未正确解压
     npm run build
     ```

## 🔍 验证安装

```bash
# 检查虚拟环境
ls -la .venv/bin/python*
.venv/bin/python --version

# 检查已安装的包
.venv/bin/pip list | head -20

# 检查前端依赖
ls -la src/frontend/node_modules | head -10

# 测试运行
source .venv/bin/activate
uv run langflow --help
```

## 📋 环境信息

- **打包时间**: $(date)
- **源服务器**: $(hostname)
- **Python 版本**: $(python3 --version 2>/dev/null || echo "未知")
- **uv 版本**: $(uv --version 2>/dev/null || echo "未知")
- **npm 版本**: $(npm --version 2>/dev/null || echo "未知")

## 🆘 故障排除

### 问题 1: 虚拟环境路径错误
```bash
# 手动修复
cd .venv
find bin -type f -exec sed -i "s|/old/path|/new/path|g" {} \;
```

### 问题 2: 架构不匹配
```bash
# 在目标服务器上重新安装依赖
cd /opt/langflow
rm -rf .venv
uv sync --frozen --extra "postgresql"
```

### 问题 3: 前端依赖缺失
```bash
cd src/frontend
rm -rf node_modules
npm install
npm run build
```

## 📞 获取帮助

如有问题，请参考项目文档或提交 Issue。
README_EOF

# 8. 创建环境信息文件
info "创建环境信息文件..."
cat > environment-info.txt << EOF
打包时间: $(date)
源服务器: $(hostname)
项目路径: $PROJECT_ROOT
Python 版本: $(python3 --version 2>/dev/null || echo "未知")
uv 版本: $(uv --version 2>/dev/null || echo "未知")
npm 版本: $(npm --version 2>/dev/null || echo "未知")
系统架构: $(uname -m)
操作系统: $(uname -a)
EOF

# 9. 显示打包结果
info ""
info "════════════════════════════════════════════════════════════════"
info "打包完成！"
info "════════════════════════════════════════════════════════════════"
info ""
info "打包目录: $PACKAGE_DIR"
info ""
info "文件列表:"
ls -lh "$PACKAGE_DIR" | tail -n +2
info ""
TOTAL_SIZE=$(du -sh "$PACKAGE_DIR" | cut -f1)
info "总大小: $TOTAL_SIZE"
info ""
info "下一步:"
info "  1. 检查打包文件: ls -lh $PACKAGE_DIR"
info "  2. 传输到目标服务器: scp -r $PACKAGE_DIR user@target:/tmp/"
info "  3. 在目标服务器上运行: bash $PACKAGE_DIR/deploy.sh /opt/langflow"
info ""

