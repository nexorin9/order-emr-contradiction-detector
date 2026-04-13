# 系统架构文档

## 概述

门诊医嘱-病程矛盾实时检测与整改推送系统是一套用于检测HIS医嘱与EMR病程记录之间存在性矛盾的工具。系统通过时间对齐引擎对比医嘱数据和病程记录，自动检测「开了没写」和「写了没开」两类矛盾，并在就诊结束前推送整改提醒。

---

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         客户端层 (Client Layer)                      │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  Python CLI  │  │  TypeScript  │  │   Web UI    │               │
│  │              │  │     CLI      │  │  仪表盘      │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                 │                       │
│         └─────────────────┼─────────────────┘                       │
│                           │                                           │
├───────────────────────────┼─────────────────────────────────────────┤
│                      API 网关层 (API Gateway)                        │
│                           │                                           │
│  ┌────────────────────────┴────────────────────────┐                │
│  │              Express.js Web API                   │                │
│  │  /health  /api/detect  /api/contradictions       │                │
│  │  /api/stats/summary  /api/alerts/*               │                │
│  └────────────────────────┬────────────────────────┘                │
│                           │                                           │
├───────────────────────────┼─────────────────────────────────────────┤
│                      业务引擎层 (Business Engine)                    │
│                           │                                           │
│  ┌────────────┐  ┌────────┴───────┐  ┌────────────┐                   │
│  │  矛盾检测  │  │    告警引擎    │  │  时间对齐  │                   │
│  │   引擎     │  │   AlertEngine  │  │ TimeAligner│                   │
│  └────────────┘  └────────────────┘  └────────────┘                   │
│                           │                                           │
├───────────────────────────┼─────────────────────────────────────────┤
│                      数据适配层 (Data Adapter Layer)                  │
│                           │                                           │
│  ┌────────────┐  ┌────────┴───────┐  ┌────────────┐                   │
│  │ HIS适配器  │  │  EMR适配器     │  │  合并加载器 │                   │
│  │HisOrderReader│ │EmrRecordReader│  │MergedLoader│                   │
│  └────────────┘  └────────────────┘  └────────────┘                   │
│                           │                                           │
├───────────────────────────┼─────────────────────────────────────────┤
│                      规则引擎层 (Rules Engine)                        │
│                           │                                           │
│  ┌────────────────────────┴────────────────────────┐                │
│  │         contradiction_rules.yaml                   │                │
│  │    ordered_but_not_recorded (开了没写)             │                │
│  │    recorded_but_not_ordered (写了没开)             │                │
│  └───────────────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 模块依赖关系

```
src/py/
├── cli.py                    # Python CLI 入口
├── exceptions.py             # 自定义异常
├── logging_config.py         # 日志配置
│
├── data/                     # 数据适配层
│   ├── his_adapter.py        # HIS 数据读取
│   ├── emr_adapter.py        # EMR 数据读取
│   └── merged_loader.py     # 数据合并加载
│
├── rules/                    # 规则引擎
│   ├── contradiction_rules.yaml  # 规则定义
│   └── rule_definitions.py  # 规则加载器
│
└── engine/                   # 业务引擎
    ├── time_aligner.py      # 时间对齐引擎
    ├── contradiction_engine.py  # 矛盾检测引擎
    └── alert_engine.py       # 告警引擎

src/ts/
├── index.ts                  # TypeScript CLI 入口
├── api/
│   ├── server.ts             # Express 服务器
│   ├── client.ts             # Python 后端客户端
│   ├── routes/
│   │   ├── contradictions.ts  # 矛盾相关路由
│   │   └── alerts.ts         # 告警相关路由
│   └── types/
│       └── index.ts          # 共享类型定义
└── cli/commands/
    ├── detect.ts             # detect 命令
    ├── query.ts              # query 命令
    └── stats.ts              # stats 命令
```

---

## 数据流

### 检测流程

```
1. 用户输入
   │
   ├── Python CLI: python -m src.py.cli detect --his <file> --emr <file> --output <dir>
   ├── TypeScript CLI: order-emr-detect detect --his <file> --emr <file> --output <dir>
   └── Web API: POST /api/detect { his_path, emr_path }
   │
2. 数据加载
   │
   ├── HisOrderReader 读取 HIS 医嘱数据 (CSV/JSON)
   ├── EmrRecordReader 读取 EMR 病程记录 (CSV/JSON)
   └── MergedDataLoader 按 patient_id + visit_date 合并
   │
3. 矛盾检测
   │
   ├── TimeAligner 时间对齐 (默认30分钟窗口)
   ├── ContradictionDetector 执行规则检测
   │   ├── ordered_but_not_recorded (开了没写)
   │   └── recorded_but_not_ordered (写了没开)
   └── 按严重程度分级 (high/medium/low)
   │
4. 告警生成
   │
   ├── AlertEngine 按科室/医生汇总
   ├── 超过阈值时触发告警
   └── 支持 Webhook 推送
   │
5. 结果输出
   │
   ├── JSON 文件输出 (data/output/contradictions_*.json)
   ├── 统计报表 (data/output/stats_*.json)
   ├── 告警文件 (data/output/alerts/alerts_*.json)
   └── Web API 实时返回
```

---

## 技术栈

### 后端 (Python)

| 组件 | 技术 | 说明 |
|------|------|------|
| 核心语言 | Python 3.10+ | 核心业务逻辑 |
| 数据格式 | CSV, JSON | 数据存储和交换 |
| 规则配置 | YAML | 矛盾检测规则定义 |
| 日志 | Python logging | 日志记录 |
| 测试 | pytest | 单元测试 |

### 前端/CLI (TypeScript/Node.js)

| 组件 | 技术 | 说明 |
|------|------|------|
| 核心语言 | TypeScript | 类型安全 |
| CLI框架 | Commander.js | 命令行工具 |
| Web框架 | Express.js | REST API |
| HTTP客户端 | Axios | Webhook推送 |
| 可视化 | Chart.js | 图表展示 |
| 构建工具 | ts-node, tsc | TypeScript编译 |

### 容器化

| 组件 | 技术 | 说明 |
|------|------|------|
| 镜像构建 | Dockerfile | 多阶段构建 |
| 容器编排 | docker-compose | 本地开发 |

---

## 核心模块说明

### 1. 数据适配层

#### HisOrderReader
- 支持 CSV 和 JSON 格式
- 标准化输出：order_id, patient_id, doctor_id, department, order_type, item_name, create_time, execute_time, status

#### EmrRecordReader
- 支持 CSV 和 JSON 格式
- 提取 content_keywords 关键词列表
- 标准化输出：record_id, patient_id, doctor_id, department, record_type, content_keywords, create_time

#### MergedDataLoader
- 按 patient_id + visit_date 合并 HIS 和 EMR 数据
- 输出 PatientVisit 统一视图

### 2. 规则引擎

#### contradiction_rules.yaml
- 定义两种矛盾类型：
  - `ordered_but_not_recorded`: 开了医嘱但病程记录中无对应描述
  - `recorded_but_not_ordered`: 病程记录中有描述但无对应医嘱
- 包含时间窗口配置、关键词匹配规则

### 3. 业务引擎

#### TimeAligner
- 按时间窗口对齐 HIS 医嘱和 EMR 记录
- 支持模糊匹配和同义词
- 输出 AlignedOrderRecord 对列表

#### ContradictionDetector
- 加载规则定义和时间对齐器
- 执行矛盾检测逻辑
- 严重程度分级：
  - **高危**: 关键药品/检查项目漏记
  - **中危**: 一般项目漏记
  - **低危**: 辅助性内容漏记

#### AlertEngine
- 按科室/医生汇总矛盾数
- 超过阈值时触发告警
- 支持 Webhook 推送和文件输出

---

## 部署架构

### 开发环境
```
本地机器
├── Python 3.10+
├── Node.js 16+
└── Docker (可选)
```

### 生产环境
```
容器化部署
├── order-emr-detector (Node.js API)
│   └── 端口: 3000
└── Python CLI (Sidecar)
```

---

## 配置文件

### config.yaml
```yaml
detection:
  time_window_minutes: 30  # 时间对齐窗口

alert:
  enabled: true
  doctor_daily_threshold: 5   # 医生日告警阈值
  department_daily_threshold: 10  # 科室日告警阈值
  high_severity_threshold: 3   # 高危阈值
  webhook_enabled: false
  webhook_url: ""
  file_output_enabled: true
  output_dir: "data/output/alerts"

severity:
  high: 3
  medium: 5
  low: 10
```

### 环境变量
| 变量 | 说明 | 默认值 |
|------|------|--------|
| PORT | Web API 端口 | 3000 |
| PYTHON_BACKEND_URL | Python 后端地址 | localhost |
| HIS_DATA_PATH | 默认 HIS 数据路径 | - |
| EMR_DATA_PATH | 默认 EMR 数据路径 | - |
| OUTPUT_DIR | 默认输出目录 | data/output |
