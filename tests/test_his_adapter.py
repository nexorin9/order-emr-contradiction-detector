"""
HIS适配器单元测试
"""

import csv
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.py.data.his_adapter import HisOrder, HisOrderReader
from src.py.exceptions import (
    DataFileNotFoundError,
    DataFormatError,
    MissingRequiredFieldError,
)


class TestHisOrder:
    """HisOrder数据类测试"""

    def test_create_his_order(self):
        """测试创建HisOrder对象"""
        order = HisOrder(
            order_id="ORD001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time="2024-01-15 10:30:00",
            execute_time="2024-01-15 11:00:00",
            status="completed",
        )

        assert order.order_id == "ORD001"
        assert order.patient_id == "P001"
        assert order.doctor_id == "D001"
        assert order.department == "内科"
        assert order.order_type == "检查"
        assert order.item_name == "B超"
        assert order.create_time == datetime(2024, 1, 15, 10, 30, 0)
        assert order.execute_time == datetime(2024, 1, 15, 11, 0, 0)
        assert order.status == "completed"

    def test_create_his_order_with_datetime(self):
        """测试使用datetime对象创建HisOrder"""
        create_dt = datetime(2024, 1, 15, 10, 30, 0)
        order = HisOrder(
            order_id="ORD001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time=create_dt,
        )

        assert order.create_time == create_dt

    def test_his_order_to_dict(self):
        """测试转换为字典"""
        order = HisOrder(
            order_id="ORD001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time="2024-01-15 10:30:00",
            status="pending",
        )

        d = order.to_dict()
        assert d["order_id"] == "ORD001"
        assert d["patient_id"] == "P001"
        assert d["status"] == "pending"

    def test_his_order_default_status(self):
        """测试默认状态为pending"""
        order = HisOrder(
            order_id="ORD001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time="2024-01-15 10:30:00",
        )

        assert order.status == "pending"


class TestHisOrderReader:
    """HisOrderReader测试"""

    def setup_method(self):
        """每个测试方法前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """每个测试方法后清理"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_csv_file(self):
        """测试读取CSV文件"""
        csv_path = os.path.join(self.temp_dir, "his_orders.csv")

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "order_id",
                    "patient_id",
                    "doctor_id",
                    "department",
                    "order_type",
                    "item_name",
                    "create_time",
                    "execute_time",
                    "status",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "order_id": "ORD001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "B超",
                    "create_time": "2024-01-15 10:30:00",
                    "execute_time": "2024-01-15 11:00:00",
                    "status": "completed",
                }
            )
            writer.writerow(
                {
                    "order_id": "ORD002",
                    "patient_id": "P002",
                    "doctor_id": "D002",
                    "department": "外科",
                    "order_type": "药品",
                    "item_name": "阿莫西林",
                    "create_time": "2024-01-15 14:00:00",
                    "execute_time": "",
                    "status": "pending",
                }
            )

        reader = HisOrderReader()
        orders = reader.read(csv_path)

        assert len(orders) == 2
        assert orders[0].order_id == "ORD001"
        assert orders[0].order_type == "检查"
        assert orders[1].order_id == "ORD002"
        assert orders[1].status == "pending"

    def test_read_json_file(self):
        """测试读取JSON文件"""
        json_path = os.path.join(self.temp_dir, "his_orders.json")

        data = [
            {
                "order_id": "ORD001",
                "patient_id": "P001",
                "doctor_id": "D001",
                "department": "内科",
                "order_type": "检验",
                "item_name": "血常规",
                "create_time": "2024-01-15 10:30:00",
                "execute_time": "2024-01-15 10:45:00",
                "status": "completed",
            },
            {
                "order_id": "ORD002",
                "patient_id": "P002",
                "doctor_id": "D002",
                "department": "儿科",
                "order_type": "治疗",
                "item_name": "雾化",
                "create_time": "2024-01-15 15:00:00",
                "status": "pending",
            },
        ]

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        reader = HisOrderReader()
        orders = reader.read(json_path)

        assert len(orders) == 2
        assert orders[0].item_name == "血常规"
        assert orders[1].department == "儿科"

    def test_read_json_object_format(self):
        """测试读取JSON对象格式（包含orders键）"""
        json_path = os.path.join(self.temp_dir, "his_orders_obj.json")

        data = {
            "orders": [
                {
                    "order_id": "ORD001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "CT",
                    "create_time": "2024-01-15 10:30:00",
                    "status": "pending",
                }
            ]
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        reader = HisOrderReader()
        orders = reader.read(json_path)

        assert len(orders) == 1
        assert orders[0].item_name == "CT"

    def test_file_not_found(self):
        """测试文件不存在时抛出异常"""
        reader = HisOrderReader()

        with pytest.raises(DataFileNotFoundError):
            reader.read("/nonexistent/path/file.csv")

    def test_unsupported_format(self):
        """测试不支持的文件格式"""
        reader = HisOrderReader()
        txt_path = os.path.join(self.temp_dir, "test.txt")

        # 创建空文件
        Path(txt_path).touch()

        with pytest.raises(DataFormatError, match="不支持的文件格式"):
            reader.read(txt_path)

    def test_csv_missing_required_field(self):
        """测试CSV缺少必需字段"""
        csv_path = os.path.join(self.temp_dir, "bad_csv.csv")

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["order_id", "patient_id"])
            writer.writeheader()
            writer.writerow({"order_id": "ORD001", "patient_id": "P001"})

        reader = HisOrderReader()

        with pytest.raises(MissingRequiredFieldError, match="缺少必需字段"):
            reader.read(csv_path)

    def test_read_directory(self):
        """测试从目录读取多个文件"""
        csv_path1 = os.path.join(self.temp_dir, "orders1.csv")
        csv_path2 = os.path.join(self.temp_dir, "orders2.json")

        # 创建CSV文件
        with open(csv_path1, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "order_id",
                    "patient_id",
                    "doctor_id",
                    "department",
                    "order_type",
                    "item_name",
                    "create_time",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "order_id": "ORD001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "B超",
                    "create_time": "2024-01-15 10:30:00",
                }
            )

        # 创建JSON文件
        with open(csv_path2, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "order_id": "ORD002",
                        "patient_id": "P002",
                        "doctor_id": "D002",
                        "department": "外科",
                        "order_type": "药品",
                        "item_name": "布洛芬",
                        "create_time": "2024-01-15 14:00:00",
                    }
                ],
                f,
            )

        reader = HisOrderReader()
        orders = reader.read_directory(self.temp_dir)

        assert len(orders) == 2

    def test_datetime_parsing_formats(self):
        """测试多种日期格式解析"""
        order = HisOrder(
            order_id="ORD001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time="2024/01/15 10:30",
            execute_time="2024-01-15",
        )

        assert order.create_time == datetime(2024, 1, 15, 10, 30)
        assert order.execute_time == datetime(2024, 1, 15, 0, 0)
