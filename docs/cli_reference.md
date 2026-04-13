# CLI 命令参考

## 目录

- [Python CLI](#python-cli)
  - [detect - 执行矛盾检测](#detect---执行矛盾检测)
  - [stats - 输出统计报表](#stats---输出统计报表)
  - [alert-config - 告警配置管理](#alert-config---告警配置管理)
- [TypeScript/Node.js CLI](#typescriptnodejs-cli)
  - [detect - 执行矛盾检测](#detect---执行矛盾检测-1)
  - [query - 查询矛盾记录](#query---查询矛盾记录)
  - [stats - 输出统计报表](#stats---输出统计报表-1)
- [通用选项](#通用选项)

---

## Python CLI

### 基本用法

```bash
python -m src.py.cli <command> [options]
```

### detect - 执行矛盾检测

执行矛盾检测，对齐HIS医嘱和EMR病程记录时间戳，检测存在性矛盾。

```bash
python -m src.py.cli detect --his <file> --emr <file> --output <dir> [options]
```

**必需参数**:
| 参数 | 说明 |
|------|------|
| --his | HIS医嘱数据文件路径 (CSV或JSON) |
| --emr | EMR病程记录数据文件路径 (CSV或JSON) |
| --output | 输出目录路径 |

**可选参数**:
| 参数 | 说明 | 默认值 |
|------|------|--------|
| --rules | 规则配置文件路径 (YAML) | 使用默认规则 |
| --time-window | 时间窗口（分钟） | 30 |

**示例**:

```bash
# 基本用法
python -m src.py.cli detect --his data/his_orders.csv --emr data/emr_records.csv --output data/output

# 指定规则文件和自定义时间窗口
python -m src.py.cli detect --his data/his_orders.csv --emr data/emr_records.csv --output data/output --rules config/rules.yaml --time-window 60
```

**输出**:

检测完成后，会在输出目录生成两个文件：

1. `contradictions_<timestamp>.json` - 矛盾详情
2. `stats_<timestamp>.json` - 统计摘要

同时在控制台输出摘要：

```
========== 检测结果摘要 ==========
总矛盾数: 15
  - 高危: 3
  - 中危: 7
  - 低危: 5
涉及患者数: 12
涉及医生数: 8
涉及科室数: 3
===================================
```

---

### stats - 输出统计报表

从检测结果生成统计报表。

```bash
python -m src.py.cli stats --input <dir> [options]
```

**必需参数**:
| 参数 | 说明 |
|------|------|
| --input | 包含矛盾结果文件的目录路径 |

**可选参数**:
| 参数 | 说明 | 默认值 |
|------|------|--------|
| --format | 输出格式 (json/csv) | csv |

**示例**:

```bash
# 默认表格格式
python -m src.py.cli stats --input data/output

# JSON 格式
python -m src.py.cli stats --input data/output --format json

# CSV 格式
python -m src.py.cli stats --input data/output --format csv
```

**表格输出示例**:

```
========== 矛盾统计报表 ==========
数据来源: data/output/contradictions_20260412_221836.json
生成时间: 2026-04-12 22:18:36

总矛盾数: 15

按严重程度:
  高危: 3
  中危: 7
  低危: 5

按规则类型:
  ordered_but_not_recorded: 10
  recorded_but_not_ordered: 5

按科室:
  内科: 8
  外科: 4
  儿科: 3

按医生 (前10):
  D001: 3
  D002: 2
  D003: 2
===================================
```

---

### alert-config - 告警配置管理

查看当前告警配置。

```bash
python -m src.py.cli alert-config --show
```

**可选参数**:
| 参数 | 说明 |
|------|------|
| --show | 显示当前告警配置 |

**示例**:

```bash
python -m src.py.cli alert-config --show
```

**输出示例**:

```
[INFO] 加载告警配置...

========== 告警配置 ==========
启用状态: 启用
医生日阈值: 5
科室日阈值: 10
高危阈值: 3
Webhook: 启用
Webhook URL: https://example.com/webhook
文件输出: 启用
输出目录: data/output/alerts
告警级别配置:
  critical: >= 5 条矛盾
  warning: >= 3 条矛盾
  info: 其他
==============================
```

---

## TypeScript/Node.js CLI

### 基本用法

```bash
order-emr-detect <command> [options]
```

或使用 npx:

```bash
npx order-emr-detect <command> [options]
```

### detect - 执行矛盾检测

执行医嘱-病程矛盾检测，调用Python CLI执行实际检测逻辑。

```bash
order-emr-detect detect --his <path> --emr <path> --output <path> [options]
```

**必需参数**:
| 参数 | 说明 |
|------|------|
| --his | HIS医嘱数据文件路径 (CSV或JSON) |
| --emr | EMR病程记录数据文件路径 (CSV或JSON) |

**可选参数**:
| 参数 | 说明 | 默认值 |
|------|------|--------|
| --output | 输出目录 | data/output |
| --rules | 规则配置文件路径 (YAML) | 使用默认规则 |
| --time-window | 时间窗口（分钟） | 30 |
| --verbose | 显示详细输出 | false |

**示例**:

```bash
# 基本用法
order-emr-detect detect --his data/sample/his_orders_sample.csv --emr data/sample/emr_records_sample.csv

# 指定输出目录和详细输出
order-emr-detect detect --his data/sample/his_orders_sample.csv --emr data/sample/emr_records_sample.csv --output data/output --verbose
```

**输出示例**:

```
========== 门诊医嘱-病程矛盾检测 ==========

[1/5] 验证输入文件...
  ✓ HIS文件: data/sample/his_orders_sample.csv
  ✓ EMR文件: data/sample/emr_records_sample.csv

[2/5] 构建检测命令...
  Python: python
  命令: -m src.py.cli detect --his data/sample/his_orders_sample.csv --emr data/sample/emr_records_sample.csv --output data/output

[3/5] 执行矛盾检测...

[4/5] 分析检测结果...
  ✓ 检测完成!

========== 检测结果摘要 ==========
  总矛盾数: 15
    - 高危: 3
    - 中危: 7
    - 低危: 5
  涉及患者数: 12
  涉及医生数: 8
  涉及科室数: 3

  结果文件: data/output/contradictions_20260412_221836.json
  统计文件: data/output/stats_20260412_221836.json
==================================

  科室矛盾排名 (Top 5):
    1. 内科: 8 ████████
    2. 外科: 4 ████
    3. 儿科: 3 ███

  按规则类型:
    - 开了没写: 10
    - 写了没开: 5

检测完成! 耗时: 2.35s
```

---

### query - 查询矛盾记录

查询指定医生指定日期的矛盾记录。

```bash
order-emr-detect query --doctor <id> --date <date> [options]
```

**必需参数**:
| 参数 | 说明 |
|------|------|
| --doctor | 医生ID (使用 `ALL` 查询所有医生) |
| --date | 日期 (YYYY-MM-DD) |

**可选参数**:
| 参数 | 说明 | 默认值 |
|------|------|--------|
| --format | 输出格式 (table/json) | table |
| --input | 输入数据目录或文件路径 | data/output |

**示例**:

```bash
# 查询指定医生的矛盾记录
order-emr-detect query --doctor D001 --date 2026-04-12

# 查询所有医生的矛盾记录
order-emr-detect query --doctor ALL --date 2026-04-12

# JSON 格式输出
order-emr-detect query --doctor D001 --date 2026-04-12 --format json
```

**表格输出示例**:

```
========== 矛盾记录查询结果 ==========

  医生ID: D001
  日期: 2026-04-12
  匹配记录数: 5

  ID   科室          患者ID    类型              严重程度  时间
  ------------------------------------------------------------------------------
   1   内科         P12345    ↓× 开了没写   HIGH     2026-04-12T09:30
   2   内科         P12346    ↑× 写了没开   MEDIUM   2026-04-12T10:15
   3   内科         P12347    ↓× 开了没写   LOW      2026-04-12T11:00
   4   外科         P12348    ↓× 开了没写   HIGH     2026-04-12T14:20
   5   外科         P12349    ↑× 写了没开   LOW      2026-04-12T15:45

  ------------------------------------------------------------------------------

  严重程度分布:
    高危: 2
    中危: 1
    低危: 2

====================================
```

**类型标识说明**:
- `↓×` : ordered_but_not_recorded (开了没写)
- `↑×` : recorded_but_not_ordered (写了没开)

---

### stats - 输出统计报表

输出科室矛盾统计报表。

```bash
order-emr-detect stats --input <path> [options]
```

**必需参数**:
| 参数 | 说明 |
|------|------|
| --input | 输入数据目录或文件路径 |

**可选参数**:
| 参数 | 说明 | 默认值 |
|------|------|--------|
| --format | 输出格式 (json/csv/table) | table |
| --department | 按科室过滤 | - |

**示例**:

```bash
# 默认表格格式
order-emr-detect stats --input data/output

# JSON 格式
order-emr-detect stats --input data/output --format json

# CSV 格式
order-emr-detect stats --input data/output --format csv

# 按科室过滤
order-emr-detect stats --input data/output --department 内科
```

**表格输出示例**:

```
========== 科室矛盾统计报表 ==========

  总体统计:
    涉及科室数: 3
    矛盾总数: 15
      高危: 3
      中危: 7
      低危: 5

  科室明细:

  科室              矛盾数   高危   中危   低危   医生数   患者数
  --------------------------------------------------------------------------
  内科              8         2       4       2       3         6
  外科              4         1       2       1       2         3
  儿科              3         0       1       2       1         2
  --------------------------------------------------------------------------

  高危科室提醒:
    1. 内科: 2 例高危矛盾

====================================
```

---

## 通用选项

### Python CLI 全局选项

| 选项 | 说明 |
|------|------|
| -h, --help | 显示帮助信息 |
| --version | 显示版本信息 |

### TypeScript CLI 全局选项

| 选项 | 说明 |
|------|------|
| -h, --help | 显示帮助信息 |
| -V, --version | 显示版本信息 |
| -d, --debug | 启用调试模式 |

### 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 失败（文件不存在、检测失败、参数错误等） |

### 环境变量

| 变量 | 说明 | 适用 |
|------|------|------|
| `PYTHON_BACKEND_URL` | Python 后端地址 | TypeScript CLI |
| `PORT` | Web API 端口 | Web API |
| `HIS_DATA_PATH` | 默认 HIS 数据路径 | Python CLI |
| `EMR_DATA_PATH` | 默认 EMR 数据路径 | Python CLI |
| `OUTPUT_DIR` | 默认输出目录 | Python CLI |
