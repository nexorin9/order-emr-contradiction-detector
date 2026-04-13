# 门诊医嘱-病程矛盾实时检测系统
# 多阶段构建：Python核心引擎 + Node.js CLI/Web

FROM python:3.11-slim AS python-builder

WORKDIR /build

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制Python源代码
COPY src/py/ src/py/
COPY src/rules/ src/rules/
COPY .config/ .config/

FROM node:18-alpine AS node-builder

WORKDIR /build

# 复制package.json
COPY package.json .
RUN npm install

# 复制TypeScript源代码
COPY src/ts/ src/ts/
COPY public/ public/

# 编译TypeScript
RUN npm run build

# 最终镜像
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制Python部分
COPY --from=python-builder /build/src/ src/py/
COPY --from=python-builder /build/src/rules/ src/rules/
COPY --from=python-builder /build/.config/ .config/
COPY --from=python-builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/

# 复制Node.js构建产物
COPY --from=node-builder /build/dist/ dist/
COPY --from=node-builder /build/node_modules/ node_modules/
COPY --from=node-builder /build/public/ public/

# 复制静态资源
COPY buymeacoffee.png .
COPY README.md .
COPY requirements.txt .

# 创建必要目录
RUN mkdir -p data/output logs

# 安装PythonCLI入口
RUN pip install -e .

# 暴露端口
EXPOSE 3000

# 默认命令：启动Web服务器
CMD ["node", "dist/api/server.js"]
