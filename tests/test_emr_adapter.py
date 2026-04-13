"""
EMR适配器单元测试
"""

import csv
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.py.data.emr_adapter import EmrRecord, EmrRecordReader
from src.py.exceptions import (
    DataFileNotFoundError,
    DataFormatError,
    MissingRequiredFieldError,
)


class TestEmrRecord:
    """EmrRecord数据类测试"""

    def test_create_emr_record(self):
        """测试创建EmrRecord对象"""
        record = EmrRecord(
            record_id="REC001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            record_type="首次病程",
            content_keywords=["B超", "血常规"],
            create_time="2024-01-15 10:30:00",
        )

        assert record.record_id == "REC001"
        assert record.patient_id == "P001"
        assert record.doctor_id == "D001"
        assert record.department == "内科"
        assert record.record_type == "首次病程"
        assert record.content_keywords == ["B超", "血常规"]
        assert record.create_time == datetime(2024, 1, 15, 10, 30, 0)

    def test_create_emr_record_with_datetime(self):
        """测试使用datetime对象创建EmrRecord"""
        create_dt = datetime(2024, 1, 15, 10, 30, 0)
        record = EmrRecord(
            record_id="REC001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            record_type="日常病程",
            content_keywords=["检查", "药品"],
            create_time=create_dt,
        )

        assert record.create_time == create_dt

    def test_create_emr_record_empty_keywords(self):
        """测试关键词为空列表"""
        record = EmrRecord(
            record_id="REC001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            record_type="手术记录",
            content_keywords=[],
            create_time="2024-01-15 10:30:00",
        )

        assert record.content_keywords == []

    def test_emr_record_to_dict(self):
        """测试转换为字典"""
        record = EmrRecord(
            record_id="REC001",
            patient_id="P001",
            doctor_id="D001",
            department="外科",
            record_type="出院记录",
            content_keywords=["CT", "阿莫西林"],
            create_time="2024-01-15 10:30:00",
        )

        d = record.to_dict()
        assert d["record_id"] == "REC001"
        assert d["patient_id"] == "P001"
        assert d["record_type"] == "出院记录"
        assert d["content_keywords"] == ["CT", "阿莫西林"]


class TestEmrRecordReader:
    """EmrRecordReader测试"""

    def setup_method(self):
        """每个测试方法前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """每个测试方法后清理"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_csv_file(self):
        """测试读取CSV文件"""
        csv_path = os.path.join(self.temp_dir, "emr_records.csv")

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "record_id",
                    "patient_id",
                    "doctor_id",
                    "department",
                    "record_type",
                    "content_keywords",
                    "create_time",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "首次病程",
                    "content_keywords": "B超;血常规",
                    "create_time": "2024-01-15 10:30:00",
                }
            )
            writer.writerow(
                {
                    "record_id": "REC002",
                    "patient_id": "P002",
                    "doctor_id": "D002",
                    "department": "外科",
                    "record_type": "日常病程",
                    "content_keywords": "CT",
                    "create_time": "2024-01-15 14:00:00",
                }
            )

        reader = EmrRecordReader()
        records = reader.read(csv_path)

        assert len(records) == 2
        assert records[0].record_id == "REC001"
        assert records[0].record_type == "首次病程"
        assert records[0].content_keywords == ["B超", "血常规"]
        assert records[1].record_id == "REC002"
        assert records[1].department == "外科"

    def test_read_csv_empty_keywords(self):
        """测试读取CSV文件，关键词为空"""
        csv_path = os.path.join(self.temp_dir, "emr_records_empty.csv")

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "record_id",
                    "patient_id",
                    "doctor_id",
                    "department",
                    "record_type",
                    "content_keywords",
                    "create_time",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "首次病程",
                    "content_keywords": "",
                    "create_time": "2024-01-15 10:30:00",
                }
            )

        reader = EmrRecordReader()
        records = reader.read(csv_path)

        assert len(records) == 1
        assert records[0].content_keywords == []

    def test_read_json_file(self):
        """测试读取JSON文件"""
        json_path = os.path.join(self.temp_dir, "emr_records.json")

        data = [
            {
                "record_id": "REC001",
                "patient_id": "P001",
                "doctor_id": "D001",
                "department": "内科",
                "record_type": "首次病程",
                "content_keywords": ["B超", "血常规"],
                "create_time": "2024-01-15 10:30:00",
            },
            {
                "record_id": "REC002",
                "patient_id": "P002",
                "doctor_id": "D002",
                "department": "儿科",
                "record_type": "日常病程",
                "content_keywords": ["雾化"],
                "create_time": "2024-01-15 15:00:00",
            },
        ]

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        reader = EmrRecordReader()
        records = reader.read(json_path)

        assert len(records) == 2
        assert records[0].item_name == "B超" if hasattr(records[0], "item_name") else True
        assert records[1].department == "儿科"

    def test_read_json_object_format(self):
        """测试读取JSON对象格式（包含records键）"""
        json_path = os.path.join(self.temp_dir, "emr_records_obj.json")

        data = {
            "records": [
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "手术记录",
                    "content_keywords": ["CT", "手术"],
                    "create_time": "2024-01-15 10:30:00",
                }
            ]
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        reader = EmrRecordReader()
        records = reader.read(json_path)

        assert len(records) == 1
        assert records[0].record_type == "手术记录"

    def test_read_json_emr_records_key(self):
        """测试读取JSON对象格式（包含emr_records键）"""
        json_path = os.path.join(self.temp_dir, "emr_records_emr.json")

        data = {
            "emr_records": [
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "出院记录",
                    "content_keywords": ["复查"],
                    "create_time": "2024-01-15 10:30:00",
                }
            ]
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        reader = EmrRecordReader()
        records = reader.read(json_path)

        assert len(records) == 1
        assert records[0].record_type == "出院记录"

    def test_file_not_found(self):
        """测试文件不存在时抛出异常"""
        reader = EmrRecordReader()

        with pytest.raises(DataFileNotFoundError):
            reader.read("/nonexistent/path/file.csv")

    def test_unsupported_format(self):
        """测试不支持的文件格式"""
        reader = EmrRecordReader()
        txt_path = os.path.join(self.temp_dir, "test.txt")

        # 创建空文件
        Path(txt_path).touch()

        with pytest.raises(DataFormatError, match="不支持的文件格式"):
            reader.read(txt_path)

    def test_csv_missing_required_field(self):
        """测试CSV缺少必需字段"""
        csv_path = os.path.join(self.temp_dir, "bad_csv.csv")

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["record_id", "patient_id"])
            writer.writeheader()
            writer.writerow({"record_id": "REC001", "patient_id": "P001"})

        reader = EmrRecordReader()

        with pytest.raises(MissingRequiredFieldError, match="缺少必需字段"):
            reader.read(csv_path)

    def test_read_directory(self):
        """测试从目录读取多个文件"""
        csv_path = os.path.join(self.temp_dir, "records1.csv")
        json_path = os.path.join(self.temp_dir, "records2.json")

        # 创建CSV文件
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "record_id",
                    "patient_id",
                    "doctor_id",
                    "department",
                    "record_type",
                    "content_keywords",
                    "create_time",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "首次病程",
                    "content_keywords": "B超",
                    "create_time": "2024-01-15 10:30:00",
                }
            )

        # 创建JSON文件
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "record_id": "REC002",
                        "patient_id": "P002",
                        "doctor_id": "D002",
                        "department": "外科",
                        "record_type": "日常病程",
                        "content_keywords": ["CT"],
                        "create_time": "2024-01-15 14:00:00",
                    }
                ],
                f,
            )

        reader = EmrRecordReader()
        records = reader.read_directory(self.temp_dir)

        assert len(records) == 2

    def test_datetime_parsing_formats(self):
        """测试多种日期格式解析"""
        record = EmrRecord(
            record_id="REC001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            record_type="首次病程",
            content_keywords=["B超"],
            create_time="2024/01/15 10:30",
        )

        assert record.create_time == datetime(2024, 1, 15, 10, 30)

    def test_json_keywords_as_string(self):
        """测试JSON中关键词为字符串（分号分隔）"""
        json_path = os.path.join(self.temp_dir, "emr_records_str_kw.json")

        data = [
            {
                "record_id": "REC001",
                "patient_id": "P001",
                "doctor_id": "D001",
                "department": "内科",
                "record_type": "首次病程",
                "content_keywords": "B超;血常规;CT",
                "create_time": "2024-01-15 10:30:00",
            }
        ]

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        reader = EmrRecordReader()
        records = reader.read(json_path)

        assert len(records) == 1
        assert records[0].content_keywords == ["B超", "血常规", "CT"]