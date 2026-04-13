# 门诊医嘱-病程矛盾实时检测与整改推送系统

对齐HIS医嘱数据和EMR病程记录时间戳，实时检测「开了没写」和「写了没开」的存在性矛盾，在就诊结束前推送整改提醒给门诊医生，输出科室矛盾统计报表。

## 核心问题

在医院信息系统中，门诊医嘱和病程记录是两个独立的数据源：

- **HIS医嘱系统**：记录医生开具的检查、检验、药品、治疗等医嘱
- **EMR病程记录**：记录病程描述、检查结果、操作记录等

当两者之间出现矛盾时：
- **开了没写**：医生开了医嘱但病程记录中没有相应描述
- **写了没开**：病程记录中描述了操作但没有对应医嘱

这些矛盾可能影响：
- 医疗质量与安全
- 医保结算合规性
- 等级评审指标

## 核心功能

### 1. 矛盾检测

- 支持HIS医嘱数据（CSV/JSON格式）
- 支持EMR病程记录数据（CSV/JSON格式）
- 时间窗口对齐：医嘱和病程记录在配置的时间窗口内（默认30分钟）被认为相关
- 关键词模糊匹配：支持同义词、缩写识别
- 两种矛盾类型检测：
  - `ordered_but_not_recorded`：开了没写
  - `recorded_but_not_ordered`：写了没开

### 2. 告警推送

- 按科室/医生汇总矛盾数量
- 阈值触发告警（单个医生每日矛盾数超过配置值）
- 支持Webhook推送
- 支持文件输出

### 3. 统计报表

- 科室级矛盾统计
- 医生级矛盾排名
- 矛盾类型分布
- 趋势分析（近7日）

### 4. 可视化看板

- Web仪表盘：矛盾概览、分布图、趋势图
- 矛盾详情页：查看矛盾判定依据和整改建议

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    TypeScript/Node.js CLI                    │
│                  (Commander.js 命令行工具)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Express.js Web API                        │
│               (端口3000，/api/* REST接口)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Python 业务引擎                            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ 数据适配层   │→ │ 矛盾检测引擎  │→ │ 告警规则引擎     │  │
│  │ HIS适配器   │  │ 时间对齐      │  │ Webhook推送     │  │
│  │ EMR适配器   │  │ 规则匹配      │  │ 统计汇总        │  │
│  └─────────────┘  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 快速开始指南（5步上手）

**方式一：一键演示（推荐首次使用）**

```bash
# Linux/macOS
bash scripts/quickstart.sh

# Windows (在 Git Bash 或 WSL 中)
bash scripts/quickstart.sh
```

**方式二：手动安装**

```bash
# 1. 安装 Python 依赖
# Linux/macOS
bash scripts/install_dependencies.sh

# Windows
scripts\install_dependencies.bat

# 2. 安装 Node.js 依赖
npm install

# 3. 编译 TypeScript
npm run build

# 4. 运行演示
python -m src.py.cli detect --his data/sample/his_orders_sample.csv --emr data/sample/emr_records_sample.csv --output data/output/

# 5. 启动 Web 服务
npm start
# 访问 http://localhost:3000
```

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 或 yarn
- Docker（可选，用于容器化部署）

### 开发环境要求

#### Python 开发环境

```bash
# 推荐使用虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 验证安装
python -c "import yaml; import pytest; print('OK')"
```

#### Node.js 开发环境

```bash
# 使用 nvm 管理 Node.js 版本（可选）
nvm install 18
nvm use 18

# 安装依赖
npm install

# 验证 TypeScript 编译
npm run build

# 运行测试
npm test
```

#### 开发工具推荐

- **Python**: VS Code + Python 扩展, PyCharm
- **Node.js**: VS Code + TypeScript 扩展, WebStorm
- **数据库/数据查看**: DBeaver, VS Code Data Preview
- **API 测试**: Postman, curl
- **Docker**: Docker Desktop

### 依赖安装

#### Python依赖

```bash
pip install -r requirements.txt
```

或使用自动化脚本：

```bash
# Linux/macOS
bash scripts/install_dependencies.sh

# Windows
scripts\install_dependencies.bat
```

#### Node.js依赖

```bash
npm install
```

### 使用

#### Python CLI

```bash
# 检测矛盾
python -m src.py.cli detect --his data/his_orders.csv --emr data/emr_records.csv --output data/output/

# 查看统计
python -m src.py.cli stats --input data/output/

# 查看告警配置
python -m src.py.cli alert-config --show
```

#### TypeScript CLI

```bash
# 编译
npm run build

# 检测矛盾
order-emr-detect detect --his data/his_orders.csv --emr data/emr_records.csv --output data/output/

# 查询医生矛盾记录
order-emr-detect query --doctor D001 --date 2024-01-15

# 查看统计报表
order-emr-detect stats --input data/output/ --format json
```

#### Web服务

```bash
npm start
# 访问 http://localhost:3000 查看可视化仪表盘
```

#### Docker

```bash
docker-compose up -d
```

## 配置说明

系统支持多种配置方式，配置文件位于 `.config/config.yaml`，环境变量可通过 `.env` 文件设置。

### 配置文件优先级

配置项的优先级从高到低为：

1. **环境变量**（最高优先级）：适用于敏感配置或需要动态设置的值
2. **命令行参数**：CLI运行时指定的参数会覆盖配置文件
3. **`.config/config.yaml`**：项目主配置文件
4. **默认值**（最低优先级）：代码中硬编码的默认值

示例：设置数据源路径
```bash
# 方式1：环境变量（优先级最高）
export HIS_DATA_PATH=/path/to/his.csv
export EMR_DATA_PATH=/path/to/emr.csv

# 方式2：命令行参数（优先级次高）
python -m src.py.cli detect --his /path/to/his.csv --emr /path/to/emr.csv

# 方式3：配置文件（.config/config.yaml）
# data_sources:
#   his:
#     path: "data/his_orders.csv"
#   emr:
#     path: "data/emr_records.csv"
```

### 完整配置项说明

#### 1. 时间对齐配置 (`time_aligner`)

| 配置项 | 说明 | 类型 | 默认值 | 取值范围 |
|--------|------|------|--------|----------|
| `time_window_minutes` | 医嘱与病程记录的时间窗口（分钟），在此窗口内的记录被认为相关 | int | 30 | 1-1440 |
| `fuzzy_matching` | 是否启用模糊匹配（支持同义词、缩写识别） | bool | true | true/false |
| `synonyms` | 同义词映射表，KEY为标准词，VALUE为同义词列表 | dict | 见下方示例 | 自定义 |

**同义词配置示例**：
```yaml
synonyms:
  CT:
    - 计算机断层扫描
    - CAT
  B超:
    - 超声波检查
    - 超声检查
  血常规:
    - 血液常规
    - CBC
```

#### 2. 矛盾检测规则配置 (`detection`)

| 配置项 | 说明 | 类型 | 默认值 | 取值范围 |
|--------|------|------|--------|----------|
| `rules.ordered_but_not_recorded.enabled` | 是否启用"开了没写"检测 | bool | true | true/false |
| `rules.recorded_but_not_ordered.enabled` | 是否启用"写了没开"检测 | bool | true | true/false |

**严重程度权重配置**（`severity_weights`）：

| 配置项 | 说明 | 类型 | 默认值 | 取值范围 |
|--------|------|------|--------|----------|
| `high` | 高危权重（手术、操作类） | int | 3 | 1-10 |
| `medium` | 中危权重（检查检验类） | int | 2 | 1-10 |
| `low` | 低危权重（药品类） | int | 1 | 1-10 |

**严重程度判定规则**：
- 高危矛盾：医嘱类型为手术、操作类（如"门诊手术"、"换药"），权重值 ≥ 高危阈值
- 中危矛盾：医嘱类型为检查检验类（如"B超"、"血常规"），权重值 ≥ 中危阈值
- 低危矛盾：医嘱类型为药品类（如"阿莫西林"），权重值 < 低危阈值

#### 3. 告警配置 (`alerting`)

| 配置项 | 说明 | 类型 | 默认值 | 取值范围 |
|--------|------|------|--------|----------|
| `enabled` | 是否启用告警功能 | bool | true | true/false |
| `threshold` | 单个医生每日矛盾数超过此值时触发告警 | int | 5 | 1-100 |
| `severity_threshold.high_severity` | 高危矛盾数超过此值时，即使总数未达threshold也告警 | int | 2 | 1-50 |
| `cooldown_minutes` | 告警冷却时间（分钟），避免重复告警 | int | 60 | 1-1440 |

**告警方式配置**（`methods`）：

| 配置项 | 说明 | 类型 | 默认值 |
|--------|------|------|--------|
| `type: webhook` | Webhook推送方式 | - | - |
| `type: webhook.enabled` | 是否启用Webhook | bool | false |
| `type: webhook.url` | Webhook接收URL | string | "" |
| `type: webhook.headers` | Webhook请求头 | dict | Content-Type: application/json |
| `type: file` | 文件输出方式 | - | - |
| `type: file.enabled` | 是否启用文件输出 | bool | true |
| `type: file.output_dir` | 告警文件输出目录 | string | data/output/alerts |

#### 4. Web服务配置 (`web`)

| 配置项 | 说明 | 类型 | 默认值 | 取值范围 |
|--------|------|------|--------|----------|
| `host` | Web服务监听地址 | string | "0.0.0.0" | 有效IP地址 |
| `port` | Web服务监听端口 | int | 3000 | 1-65535 |
| `debug` | 调试模式开关 | bool | false | true/false |

#### 5. 数据源配置 (`data_sources`)

**HIS数据源配置**（`data_sources.his`）：

| 配置项 | 说明 | 类型 | 默认值 |
|--------|------|------|--------|
| `type` | 数据文件类型 | string | csv |
| `path` | HIS数据文件路径 | string | data/his_orders.csv |
| `required_columns` | 必需列名列表 | list | order_id, patient_id, doctor_id, department, order_type, item_name, create_time, execute_time, status |

**EMR数据源配置**（`data_sources.emr`）：

| 配置项 | 说明 | 类型 | 默认值 |
|--------|------|------|--------|
| `type` | 数据文件类型 | string | csv |
| `path` | EMR数据文件路径 | string | data/emr_records.csv |
| `required_columns` | 必需列名列表 | list | record_id, patient_id, doctor_id, department, record_type, content_keywords, create_time |

**数据文件格式要求**：

HIS数据CSV格式示例：
```csv
order_id,patient_id,doctor_id,department,order_type,item_name,create_time,execute_time,status
ORD001,P001,D001,门诊内科,检查,血常规,2024-01-15 09:00:00,2024-01-15 09:30:00,执行中
```

EMR数据CSV格式示例：
```csv
record_id,patient_id,doctor_id,department,record_type,content_keywords,create_time
REC001,P001,D001,门诊内科,病程记录,血常规检查结果正常,2024-01-15 09:15:00
```

#### 6. 日志配置 (`logging`)

| 配置项 | 说明 | 类型 | 默认值 | 取值范围 |
|--------|------|------|--------|----------|
| `level` | 日志级别 | string | INFO | DEBUG/INFO/WARNING/ERROR |
| `format` | 日志格式 | string | 见下方 | Python logging格式 |
| `file` | 日志文件路径 | string | logs/detection.log | 有效文件路径 |
| `console` | 是否输出到控制台 | bool | true | true/false |
| `per_run_log` | 每个检测run是否生成独立日志文件 | bool | true | true/false |

**日志格式说明**：
```
%(asctime)s - 时间戳
%(name)s - 模块名称
%(levelname)s - 日志级别
%(message)s - 日志消息
```

### 环境变量

可通过 `.env` 文件设置以下环境变量：

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `HIS_DATA_PATH` | HIS数据文件路径 | data/his_orders.csv |
| `EMR_DATA_PATH` | EMR数据文件路径 | data/emr_records.csv |
| `OUTPUT_DIR` | 输出目录 | data/output |
| `PYTHON_BACKEND_URL` | Python后端服务URL | http://localhost:8000 |
| `WEB_PORT` | Web服务端口 | 3000 |
| `LOG_LEVEL` | 日志级别 | INFO |

### 配置文件示例

完整配置文件参考 `.config/config.yaml`，详细注释版本见 `.config/config.yaml.example`。

## 示例数据

示例数据位于 `data/sample/` 目录：

- `his_orders_sample.csv`：40条HIS医嘱（含10条会触发矛盾的）
- `emr_records_sample.csv`：EMR病程记录（含5条缺失记录）
- `his_orders_large.csv`：200条数据（压力测试用）

## 项目结构

```
order-emr-contradiction-detector/
├── .config/              # 配置文件
│   └── config.yaml
├── data/                 # 数据目录
│   └── sample/          # 示例数据
├── dist/                # 编译后的JavaScript
├── logs/                # 日志目录
├── public/              # Web静态文件
│   ├── index.html       # 仪表盘
│   ├── detail.html      # 矛盾详情页
│   └── css/style.css
├── scripts/             # 工具脚本
├── src/
│   ├── py/              # Python核心引擎
│   │   ├── data/        # 数据适配层
│   │   ├── engine/      # 业务引擎
│   │   ├── rules/       # 规则定义
│   │   ├── cli.py       # CLI入口
│   │   └── exceptions.py
│   └── ts/              # TypeScript CLI/Web
│       ├── cli/commands/ # CLI命令
│       ├── api/         # Web API
│       └── types/       # 类型定义
├── tests/               # 测试文件
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| /health | GET | 健康检查 |
| /api/detect | POST | 执行矛盾检测 |
| /api/contradictions | GET | 查询矛盾列表 |
| /api/stats/summary | GET | 获取统计汇总 |
| /api/alerts/config | GET/PUT | 告警配置 |

## 更多文档

- [API 接口文档](docs/api.md) - 详细的 REST API 端点说明
- [CLI 命令参考](docs/cli_reference.md) - Python/TypeScript CLI 命令详解
- [系统架构文档](docs/architecture.md) - 系统架构和数据流说明

## 测试

```bash
# Python单元测试
pytest tests/ --cov=src --cov-report=term

# Node.js测试
npm test

# E2E测试
pytest tests/acceptance/
```

## 适用场景

- **质控科**：监控门诊医疗质量，发现漏记或误记
- **医务科**：整改通知推送，确保病历完整性
- **医保办**：合规性检查，避免医保结算纠纷
- **科室主任**：科室医疗质量排名和改进

## License

MIT

---

## 支持作者

如果您觉得这个项目对您有帮助，欢迎打赏支持！
Wechat:gdgdmp
![Buy Me a Coffee](buymeacoffee.png)

**Buy me a coffee (crypto)**

| 币种 | 地址 |
|------|------|
| BTC | `bc1qc0f5tv577z7yt59tw8sqaq3tey98xehy32frzd` |
| ETH / USDT | `0x3b7b6c47491e4778157f0756102f134d05070704` |
| SOL | `6Xuk373zc6x6XWcAAuqvbWW92zabJdCmN3CSwpsVM6sd` |
