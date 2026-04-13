# 示例数据集说明

本目录包含用于测试和演示的示例数据文件。

## 文件列表

### 1. his_orders_sample.csv
HIS医嘱样本数据，包含 **40 条记录**。

**数据分布**：
- 记录 O001-O030：正常医嘱（有对应EMR记录）
- 记录 O031-O040：会触发「开了没写」矛盾的医嘱（无对应EMR记录）

**字段说明**：
| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | string | 医嘱唯一标识 |
| patient_id | string | 患者ID |
| doctor_id | string | 医生ID |
| department | string | 科室 |
| order_type | string | 医嘱类型（检验/检查/药品/治疗） |
| item_name | string | 医嘱项目名称 |
| create_time | datetime | 医嘱创建时间 |
| execute_time | datetime | 执行时间（部分记录） |
| status | string | 状态（completed/pending） |

### 2. emr_records_sample.csv
EMR病程记录样本数据，包含 **20 条记录**。

**数据分布**：
- 记录 R001-R015：正常病程记录，对应患者 P001-P015，与HIS医嘱匹配
- 记录 R016-R020：会触发「写了没开」矛盾的患者 P026-P030，EMR记录了检查项目但无对应HIS医嘱

**字段说明**：
| 字段 | 类型 | 说明 |
|------|------|------|
| record_id | string | 记录唯一标识 |
| patient_id | string | 患者ID |
| doctor_id | string | 医生ID |
| department | string | 科室 |
| record_type | string | 病程记录类型 |
| content_keywords | string | 记录内容关键词（分号分隔） |
| create_time | datetime | 记录创建时间 |

### 3. his_orders_large.csv
HIS医嘱大数据集，包含 **200 条记录**，用于性能基准测试。

**用途**：
- 验证系统处理中等规模数据的能力
- 性能基准测试：测量数据加载、矛盾检测、CLI执行的耗时
- 压力测试：验证系统稳定性

**数据特征**：
- 覆盖 10 个科室（内科、外科、儿科等）
- 20 位医生
- 4 种医嘱类型
- 10 天时间范围（2026-04-01 至 2026-04-10）

## 预期矛盾检测结果

### 使用 his_orders_sample.csv + emr_records_sample.csv

**「开了没写」矛盾（10条）**：
- O031 至 O040：医生开具了医嘱但未书写病程记录

**「写了没开」矛盾（5条）**：
- R016 至 R020：病程记录中提到了检查项目，但HIS中没有对应医嘱

## 使用方法

```bash
# 运行矛盾检测
python -m src.py.cli detect \
  --his data/sample/his_orders_sample.csv \
  --emr data/sample/emr_records_sample.csv \
  --output data/output/

# 查看输出结果
cat data/output/contradictions.json

# 运行统计
python -m src.py.cli stats --input data/output/
```

## 注意事项

- 所有数据均为脱敏模拟数据，不代表真实患者信息
- 数据仅用于系统测试和演示
