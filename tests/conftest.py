"""
pytest共享fixtures配置

提供mock HIS医嘱数据、EMR病程记录数据和其他通用fixtures，
供所有测试模块使用。
"""

import csv
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pytest

from src.py.data.his_adapter import HisOrder, HisOrderReader
from src.py.data.emr_adapter import EmrRecord, EmrRecordReader
from src.py.data.merged_loader import PatientVisit, MergedDataLoader
from src.py.engine.contradiction_engine import ContradictionDetector


# ============================================================================
# 基础时间戳 fixtures
# ============================================================================

@pytest.fixture
def base_time():
    """基础时间戳（门诊日）"""
    return datetime(2024, 1, 15, 9, 0, 0)


@pytest.fixture
def time_window_minutes():
    """默认时间窗口（分钟）"""
    return 120


# ============================================================================
# HIS医嘱数据 fixtures
# ============================================================================

@pytest.fixture
def sample_his_orders(base_time) -> List[HisOrder]:
    """示例HIS医嘱数据（正常门诊场景）

    包含：
    - B超（检查）- 已完成，有对应病程记录
    - 血常规（检验）- 已完成，无对应病程记录（开了没写）
    - 阿莫西林（药品）- 已完成，无对应病程记录（开了没写）
    - 雾化（治疗）- 待执行，无对应病程记录（开了没写）
    """
    return [
        HisOrder(
            order_id="ORD001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time=base_time,
            execute_time=base_time + timedelta(minutes=30),
            status="completed",
        ),
        HisOrder(
            order_id="ORD002",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检验",
            item_name="血常规",
            create_time=base_time + timedelta(minutes=10),
            execute_time=base_time + timedelta(minutes=20),
            status="completed",
        ),
        HisOrder(
            order_id="ORD003",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="药品",
            item_name="阿莫西林",
            create_time=base_time + timedelta(minutes=20),
            status="completed",
        ),
        HisOrder(
            order_id="ORD004",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="治疗",
            item_name="雾化",
            create_time=base_time + timedelta(minutes=30),
            status="pending",
        ),
    ]


@pytest.fixture
def sample_his_orders_large(base_time) -> List[HisOrder]:
    """大规模HIS医嘱数据（用于性能测试）

    包含200条医嘱记录，覆盖多个患者、科室和日期。
    """
    orders = []
    departments = ["内科", "外科", "儿科", "妇产科", "骨科"]
    order_types = ["检查", "检验", "药品", "治疗"]
    items = {
        "检查": ["B超", "CT", "X光", "心电图", "胃镜"],
        "检验": ["血常规", "尿常规", "肝功能", "肾功能", "血糖"],
        "药品": ["阿莫西林", "布洛芬", "感冒灵", "板蓝根", "维生素C"],
        "治疗": ["雾化", "输液", "换药", "理疗", "针灸"],
    }

    for i in range(200):
        dept = departments[i % len(departments)]
        order_type = order_types[i % len(order_types)]
        item = items[order_type][i % len(items[order_type])]

        orders.append(
            HisOrder(
                order_id=f"ORD{i:04d}",
                patient_id=f"P{(i % 20) + 1:03d}",
                doctor_id=f"D{(i % 10) + 1:03d}",
                department=dept,
                order_type=order_type,
                item_name=item,
                create_time=base_time + timedelta(hours=i % 8, minutes=i % 60),
                status="completed" if i % 3 != 0 else "pending",
            )
        )
    return orders


@pytest.fixture
def his_orders_csv_path(sample_his_orders, tmp_path) -> str:
    """将示例HIS医嘱数据写入临时CSV文件，返回路径"""
    csv_path = tmp_path / "his_orders.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "order_id", "patient_id", "doctor_id", "department",
                "order_type", "item_name", "create_time", "execute_time", "status",
            ],
        )
        writer.writeheader()
        for order in sample_his_orders:
            writer.writerow({
                "order_id": order.order_id,
                "patient_id": order.patient_id,
                "doctor_id": order.doctor_id,
                "department": order.department,
                "order_type": order.order_type,
                "item_name": order.item_name,
                "create_time": order.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "execute_time": order.execute_time.strftime("%Y-%m-%d %H:%M:%S") if order.execute_time else "",
                "status": order.status,
            })
    return str(csv_path)


@pytest.fixture
def his_orders_json_path(sample_his_orders, tmp_path) -> str:
    """将示例HIS医嘱数据写入临时JSON文件，返回路径"""
    json_path = tmp_path / "his_orders.json"
    data = [
        {
            "order_id": o.order_id,
            "patient_id": o.patient_id,
            "doctor_id": o.doctor_id,
            "department": o.department,
            "order_type": o.order_type,
            "item_name": o.item_name,
            "create_time": o.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "execute_time": o.execute_time.strftime("%Y-%m-%d %H:%M:%S") if o.execute_time else None,
            "status": o.status,
        }
        for o in sample_his_orders
    ]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(json_path)


# ============================================================================
# EMR病程记录 fixtures
# ============================================================================

@pytest.fixture
def sample_emr_records(base_time) -> List[EmrRecord]:
    """示例EMR病程记录数据

    包含：
    - 首次病程记录（包含B超关键词）- 有对应医嘱
    - 日常病程记录（包含布洛芬关键词）- 无对应医嘱（写了没开）
    """
    return [
        EmrRecord(
            record_id="REC001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            record_type="首次病程",
            content_keywords=["B超", "检查"],
            create_time=base_time + timedelta(minutes=5),
        ),
        EmrRecord(
            record_id="REC002",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            record_type="日常病程",
            content_keywords=["布洛芬", "退烧"],
            create_time=base_time + timedelta(minutes=40),
        ),
    ]


@pytest.fixture
def emr_records_csv_path(sample_emr_records, tmp_path) -> str:
    """将示例EMR数据写入临时CSV文件，返回路径"""
    csv_path = tmp_path / "emr_records.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "record_id", "patient_id", "doctor_id", "department",
                "record_type", "content_keywords", "create_time",
            ],
        )
        writer.writeheader()
        for record in sample_emr_records:
            writer.writerow({
                "record_id": record.record_id,
                "patient_id": record.patient_id,
                "doctor_id": record.doctor_id,
                "department": record.department,
                "record_type": record.record_type,
                "content_keywords": ";".join(record.content_keywords),
                "create_time": record.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            })
    return str(csv_path)


@pytest.fixture
def emr_records_json_path(sample_emr_records, tmp_path) -> str:
    """将示例EMR数据写入临时JSON文件，返回路径"""
    json_path = tmp_path / "emr_records.json"
    data = [
        {
            "record_id": r.record_id,
            "patient_id": r.patient_id,
            "doctor_id": r.doctor_id,
            "department": r.department,
            "record_type": r.record_type,
            "content_keywords": r.content_keywords,
            "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for r in sample_emr_records
    ]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(json_path)


# ============================================================================
# PatientVisit fixtures
# ============================================================================

@pytest.fixture
def sample_patient_visit(sample_his_orders, sample_emr_records, base_time) -> PatientVisit:
    """示例患者就诊记录（包含医嘱和病程记录）"""
    return PatientVisit(
        patient_id="P001",
        visit_date=datetime(2024, 1, 15),
        orders=sample_his_orders,
        records=sample_emr_records,
    )


@pytest.fixture
def patient_visits_multiple(sample_his_orders_large, base_time) -> List[PatientVisit]:
    """多个患者就诊记录（用于性能测试）"""
    # 按患者分组
    visits_dict = {}
    for order in sample_his_orders_large:
        if order.patient_id not in visits_dict:
            visits_dict[order.patient_id] = PatientVisit(
                patient_id=order.patient_id,
                visit_date=datetime(2024, 1, 15),
                orders=[],
                records=[],
            )
        visits_dict[order.patient_id].orders.append(order)

    return list(visits_dict.values())


# ============================================================================
# 矛盾检测 fixtures
# ============================================================================

@pytest.fixture
def contradiction_detector(time_window_minutes) -> ContradictionDetector:
    """矛盾检测器实例"""
    return ContradictionDetector(time_window_minutes=time_window_minutes)


@pytest.fixture
def expected_contradictions():
    """期望检测到的矛盾列表

    基于 sample_his_orders 和 sample_emr_records：
    - ordered_but_not_recorded: 血常规、阿莫西林、雾化（开了没写）
    - recorded_but_not_ordered: 布洛芬（写了没开）
    """
    return {
        "ordered_but_not_recorded": ["血常规", "阿莫西林", "雾化"],
        "recorded_but_not_ordered": ["布洛芬"],
    }


# ============================================================================
# 数据加载器 fixtures
# ============================================================================

@pytest.fixture
def merged_data_loader() -> MergedDataLoader:
    """合并数据加载器实例"""
    return MergedDataLoader()


# ============================================================================
# 临时目录 fixtures
# ============================================================================

@pytest.fixture
def temp_data_dir(tmp_path):
    """临时数据目录（包含his和emr子目录）"""
    his_dir = tmp_path / "his"
    emr_dir = tmp_path / "emr"
    his_dir.mkdir()
    emr_dir.mkdir()
    return {"his": str(his_dir), "emr": str(emr_dir), "base": str(tmp_path)}


# ============================================================================
# 配置 fixtures
# ============================================================================

@pytest.fixture
def default_time_window():
    """默认时间窗口配置（分钟）"""
    return 120


@pytest.fixture
def alert_threshold():
    """默认告警阈值"""
    return 5


# ============================================================================
# 辅助函数
# ============================================================================

def create_his_csv(path: str, orders: List[HisOrder]) -> None:
    """辅助函数：创建HIS CSV文件"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "order_id", "patient_id", "doctor_id", "department",
                "order_type", "item_name", "create_time", "execute_time", "status",
            ],
        )
        writer.writeheader()
        for order in orders:
            writer.writerow({
                "order_id": order.order_id,
                "patient_id": order.patient_id,
                "doctor_id": order.doctor_id,
                "department": order.department,
                "order_type": order.order_type,
                "item_name": order.item_name,
                "create_time": order.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "execute_time": order.execute_time.strftime("%Y-%m-%d %H:%M:%S") if order.execute_time else "",
                "status": order.status,
            })


def create_emr_csv(path: str, records: List[EmrRecord]) -> None:
    """辅助函数：创建EMR CSV文件"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "record_id", "patient_id", "doctor_id", "department",
                "record_type", "content_keywords", "create_time",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow({
                "record_id": record.record_id,
                "patient_id": record.patient_id,
                "doctor_id": record.doctor_id,
                "department": record.department,
                "record_type": record.record_type,
                "content_keywords": ";".join(record.content_keywords),
                "create_time": record.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            })
