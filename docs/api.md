# API 接口文档

## 目录

- [Web API](#web-api)
  - [健康检查](#健康检查)
  - [执行矛盾检测](#执行矛盾检测)
  - [获取矛盾列表](#获取矛盾列表)
  - [标记矛盾已整改](#标记矛盾已整改)
  - [获取统计汇总](#获取统计汇总)
  - [获取告警配置](#获取告警配置)
  - [更新告警配置](#更新告警配置)
  - [测试Webhook](#测试webhook)
- [数据类型](#数据类型)
- [错误代码](#错误代码)

---

## Web API

基础URL: `http://localhost:3000`

### 健康检查

检查服务是否正常运行。

**端点**: `GET /health`

**响应示例**:
```json
{
  "status": "ok",
  "timestamp": "2026-04-12T22:18:36.000Z",
  "service": "order-emr-detect-api"
}
```

---

### 执行矛盾检测

接收HIS和EMR数据文件路径，执行矛盾检测，返回检测结果。

**端点**: `POST /api/detect`

**请求体**:
| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| his_path | string | 是 | HIS医嘱数据文件路径 (CSV或JSON) |
| emr_path | string | 是 | EMR病程记录数据文件路径 (CSV或JSON) |
| output_dir | string | 否 | 输出目录路径，默认 `data/output` |

**响应示例**:
```json
{
  "success": true,
  "data": {
    "count": 15,
    "contradictions": [
      {
        "id": "c_001",
        "patient_id": "P12345",
        "doctor_id": "D001",
        "department": "内科",
        "rule_type": "ordered_but_not_recorded",
        "order_id": "ORD20260412001",
        "item_name": "B超检查",
        "execute_time": "2026-04-12T09:30:00",
        "create_time": "2026-04-12T10:05:00",
        "severity": "high",
        "resolved": false
      }
    ]
  }
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "缺少必需参数：his_path 和 emr_path",
  "error_code": "MISSING_PARAMS"
}
```

---

### 获取矛盾列表

支持分页和过滤获取矛盾记录列表。

**端点**: `GET /api/contradictions`

**查询参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | integer | 1 | 页码 |
| limit | integer | 20 | 每页数量 |
| department | string | - | 按科室过滤 |
| doctor_id | string | - | 按医生ID过滤 |
| severity | string | - | 按严重程度过滤 (high/medium/low) |
| start_date | string | - | 开始日期 (ISO格式) |
| end_date | string | - | 结束日期 (ISO格式) |
| resolved | string | - | 按整改状态过滤 (true/false) |

**响应示例**:
```json
{
  "success": true,
  "data": {
    "contradictions": [...],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 45,
      "total_pages": 3
    }
  }
}
```

---

### 标记矛盾已整改

将指定矛盾记录标记为已整改或未整改。

**端点**: `PUT /api/contradictions/:id/resolve`

**路径参数**:
| 参数 | 说明 |
|------|------|
| id | 矛盾记录ID |

**请求体**:
| 字段 | 类型 | 说明 |
|------|------|------|
| resolved | boolean | 整改状态 (true=已整改, false=未整改) |
| resolution_note | string | 整改备注 (可选) |

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "c_001",
    "resolved": true,
    "resolved_time": "2026-04-12T22:20:00.000Z",
    "resolution_note": "已补录病程记录"
  },
  "message": "矛盾已标记为已整改"
}
```

**错误响应** (404):
```json
{
  "success": false,
  "error": "未找到指定的矛盾记录",
  "error_code": "NOT_FOUND"
}
```

---

### 获取统计汇总

获取科室级矛盾统计汇总和告警级别。

**端点**: `GET /api/stats/summary`

**响应示例**:
```json
{
  "success": true,
  "data": {
    "summary": [
      {
        "department": "内科",
        "total": 15,
        "high": 3,
        "medium": 7,
        "low": 5,
        "resolved": 8,
        "unresolved": 7
      }
    ],
    "alert_summaries": [
      {
        "doctor_id": "",
        "department": "内科",
        "contradiction_count": 15,
        "high_severity_count": 3,
        "alert_level": "warning"
      }
    ],
    "overall": {
      "total_contradictions": 45,
      "total_departments": 5,
      "critical_departments": 1,
      "warning_departments": 3
    }
  }
}
```

**告警级别说明**:
| 级别 | 条件 | 说明 |
|------|------|------|
| critical | 高危矛盾 >= 5 | 紧急处理 |
| warning | 矛盾总数 >= 10 | 需要关注 |
| info | 其他 | 正常 |

---

### 获取告警配置

获取当前告警配置。

**端点**: `GET /api/alerts/config`

**响应示例**:
```json
{
  "success": true,
  "data": {
    "time_window_minutes": 30,
    "alert_threshold": 5,
    "severity_thresholds": {
      "high": 3,
      "medium": 5,
      "low": 10
    },
    "webhook_url": "https://example.com/webhook",
    "webhook_enabled": true,
    "auto_resolve_days": 7
  }
}
```

---

### 更新告警配置

更新告警阈值和相关配置。

**端点**: `PUT /api/alerts/config`

**请求体** (所有字段可选):
| 字段 | 类型 | 说明 |
|------|------|------|
| time_window_minutes | integer | 时间窗口（分钟） |
| alert_threshold | integer | 告警阈值 |
| webhook_url | string | Webhook URL |
| webhook_enabled | boolean | 是否启用Webhook |
| auto_resolve_days | integer | 自动整改天数 |
| severity_thresholds.high | integer | 高危阈值 |
| severity_thresholds.medium | integer | 中危阈值 |
| severity_thresholds.low | integer | 低危阈值 |

**响应示例**:
```json
{
  "success": true,
  "data": {
    "time_window_minutes": 30,
    "alert_threshold": 3,
    "severity_thresholds": {
      "high": 3,
      "medium": 5,
      "low": 10
    },
    "webhook_url": "https://example.com/webhook",
    "webhook_enabled": true,
    "auto_resolve_days": 7
  },
  "message": "告警配置已更新"
}
```

---

### 测试Webhook

发送测试Webhook请求，验证Webhook配置是否正确。

**端点**: `POST /api/alerts/test`

**请求体**:
| 字段 | 类型 | 说明 |
|------|------|------|
| webhook_url | string | Webhook URL (可选，使用当前配置) |

**响应示例** (成功):
```json
{
  "success": true,
  "data": {
    "webhook_url": "https://example.com/webhook",
    "status_code": 200,
    "response_body": "OK"
  },
  "message": "测试Webhook发送成功"
}
```

**响应示例** (失败):
```json
{
  "success": false,
  "error": "Webhook请求失败: Connection timeout",
  "error_code": "WEBHOOK_REQUEST_FAILED"
}
```

**错误响应** (未配置URL):
```json
{
  "success": false,
  "error": "未配置Webhook URL",
  "error_code": "WEBHOOK_URL_MISSING"
}
```

---

## 数据类型

### Contradiction (矛盾记录)

```typescript
interface Contradiction {
  id: string;                                      // 矛盾记录唯一ID
  patient_id: string;                             // 患者ID
  doctor_id: string;                              // 医生ID
  department: string;                              // 科室
  rule_type: 'ordered_but_not_recorded' | 'recorded_but_not_ordered';  // 矛盾类型
  order_id?: string;                              // 医嘱ID (ordered_but_not_recorded时)
  record_id?: string;                             // 病程记录ID (recorded_but_not_ordered时)
  record_type?: string;                           // 病程记录类型
  item_name?: string;                             // 医嘱项目名称
  keywords?: string;                              // EMR记录关键词
  execute_time?: string;                          // 医嘱执行时间
  create_time: string;                            // 矛盾记录创建时间
  severity: 'high' | 'medium' | 'low';            // 严重程度
  resolved: boolean;                              // 是否已整改
  resolved_time?: string;                         // 整改时间
  resolution_note?: string;                        // 整改备注
}
```

### AlertSummary (告警汇总)

```typescript
interface AlertSummary {
  doctor_id: string;                              // 医生ID
  department: string;                             // 科室
  contradiction_count: number;                   // 矛盾总数
  high_severity_count: number;                   // 高危矛盾数
  alert_level: 'critical' | 'warning' | 'info';  // 告警级别
}
```

### AlertConfig (告警配置)

```typescript
interface AlertConfig {
  time_window_minutes: number;                   // 时间窗口（分钟）
  alert_threshold: number;                       // 告警阈值
  severity_thresholds: {                         // 严重程度阈值
    high: number;
    medium: number;
    low: number;
  };
  webhook_url: string;                           // Webhook URL
  webhook_enabled: boolean;                     // 是否启用Webhook
  auto_resolve_days: number;                    // 自动整改天数
}
```

### ApiResponse (通用响应)

```typescript
interface ApiResponse<T> {
  success: boolean;                              // 请求是否成功
  data?: T;                                      // 响应数据
  error?: string;                                 // 错误信息
  error_code?: string;                           // 错误代码
  message?: string;                              // 附加消息
}
```

---

## 错误代码

| 代码 | 说明 |
|------|------|
| `MISSING_PARAMS` | 缺少必需参数 |
| `DETECTION_FAILED` | 矛盾检测执行失败 |
| `INTERNAL_ERROR` | 内部服务器错误 |
| `NOT_FOUND` | 资源不存在 |
| `UPDATE_CONFIG_FAILED` | 配置更新失败 |
| `WEBHOOK_URL_MISSING` | 未配置Webhook URL |
| `WEBHOOK_REQUEST_FAILED` | Webhook请求失败 |
| `WEBHOOK_TEST_FAILED` | Webhook测试失败 |
| `SERVER_ERROR` | 服务器错误 |
