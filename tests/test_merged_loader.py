"""
合并加载器单元测试
"""

import csv
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.py.data.his_adapter import HisOrder, HisOrderReader
from src.py.data.emr_adapter import EmrRecord, EmrRecordReader
from src.py.data.merged_loader import (
    PatientVisit,
    MergedDataLoader,
    VisitStatistics,
)
from src.py.exceptions import EmptyDataError


class TestPatientVisit:
    """PatientVisit数据类测试"""

    def test_create_patient_visit(self):
        """测试创建PatientVisit对象"""
        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
        )

        assert visit.patient_id == "P001"
        assert visit.visit_date == datetime(2024, 1, 15, 0, 0, 0)
        assert visit.orders == []
        assert visit.records == []

    def test_create_patient_visit_with_orders_and_records(self):
        """测试创建带医嘱和病程记录的PatientVisit"""
        order = HisOrder(
            order_id="ORD001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time="2024-01-15 10:30:00",
        )
        record = EmrRecord(
            record_id="REC001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            record_type="首次病程",
            content_keywords=["B超"],
            create_time="2024-01-15 11:00:00",
        )

        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            orders=[order],
            records=[record],
        )

        assert len(visit.orders) == 1
        assert len(visit.records) == 1
        assert visit.orders[0].order_id == "ORD001"
        assert visit.records[0].record_id == "REC001"

    def test_visit_date_time_component_removed(self):
        """测试visit_date的时间部分被去除"""
        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15, 14, 30, 45),
        )

        assert visit.visit_date == datetime(2024, 1, 15, 0, 0, 0)

    def test_visit_date_string_parsing(self):
        """测试字符串日期解析"""
        visit = PatientVisit(
            patient_id="P001",
            visit_date="2024-01-15",
        )

        assert visit.visit_date == datetime(2024, 1, 15, 0, 0, 0)

    def test_get_orders_by_type(self):
        """测试按类型获取医嘱"""
        orders = [
            HisOrder(
                order_id="ORD001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time="2024-01-15 10:00:00",
            ),
            HisOrder(
                order_id="ORD002",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检验",
                item_name="血常规",
                create_time="2024-01-15 10:30:00",
            ),
            HisOrder(
                order_id="ORD003",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="CT",
                create_time="2024-01-15 11:00:00",
            ),
        ]

        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            orders=orders,
        )

        check_orders = visit.get_orders_by_type("检查")
        assert len(check_orders) == 2
        assert all(o.order_type == "检查" for o in check_orders)

        lab_orders = visit.get_orders_by_type("检验")
        assert len(lab_orders) == 1
        assert lab_orders[0].item_name == "血常规"

    def test_get_records_by_type(self):
        """测试按类型获取病程记录"""
        records = [
            EmrRecord(
                record_id="REC001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="首次病程",
                content_keywords=["入院"],
                create_time="2024-01-15 09:00:00",
            ),
            EmrRecord(
                record_id="REC002",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["检查"],
                create_time="2024-01-15 15:00:00",
            ),
        ]

        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            records=records,
        )

        first_visits = visit.get_records_by_type("首次病程")
        assert len(first_visits) == 1
        assert first_visits[0].record_id == "REC001"

        daily_visits = visit.get_records_by_type("日常病程")
        assert len(daily_visits) == 1
        assert daily_visits[0].record_id == "REC002"

    def test_get_all_keywords(self):
        """测试获取所有关键词"""
        records = [
            EmrRecord(
                record_id="REC001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="首次病程",
                content_keywords=["B超", "血常规"],
                create_time="2024-01-15 09:00:00",
            ),
            EmrRecord(
                record_id="REC002",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["B超", "CT"],
                create_time="2024-01-15 15:00:00",
            ),
        ]

        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            records=records,
        )

        keywords = visit.get_all_keywords()
        assert len(keywords) == 3
        assert set(keywords) == {"B超", "血常规", "CT"}

    def test_to_dict(self):
        """测试转换为字典"""
        order = HisOrder(
            order_id="ORD001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time="2024-01-15 10:00:00",
        )

        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            orders=[order],
        )

        d = visit.to_dict()
        assert d["patient_id"] == "P001"
        assert d["visit_date"] == "2024-01-15T00:00:00"
        assert d["order_count"] == 1
        assert d["record_count"] == 0


class TestMergedDataLoader:
    """MergedDataLoader测试"""

    def setup_method(self):
        """每个测试方法前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """每个测试方法后清理"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_his_csv(self, path: str, orders: list):
        """创建HIS CSV文件"""
        with open(path, "w", encoding="utf-8", newline="") as f:
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
            for order in orders:
                writer.writerow(order)

    def _create_emr_csv(self, path: str, records: list):
        """创建EMR CSV文件"""
        with open(path, "w", encoding="utf-8", newline="") as f:
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
            for record in records:
                writer.writerow(record)

    def test_merge_same_patient_same_day(self):
        """测试同一患者同一天的医嘱和病程记录合并"""
        his_csv = os.path.join(self.temp_dir, "his.csv")
        emr_csv = os.path.join(self.temp_dir, "emr.csv")

        self._create_his_csv(
            his_csv,
            [
                {
                    "order_id": "ORD001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "B超",
                    "create_time": "2024-01-15 10:00:00",
                    "status": "pending",
                },
            ],
        )

        self._create_emr_csv(
            emr_csv,
            [
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "首次病程",
                    "content_keywords": "B超",
                    "create_time": "2024-01-15 11:00:00",
                },
            ],
        )

        loader = MergedDataLoader()
        visits = loader.load(his_csv, emr_csv)

        assert len(visits) == 1
        assert visits[0].patient_id == "P001"
        assert visits[0].visit_date == datetime(2024, 1, 15, 0, 0, 0)
        assert len(visits[0].orders) == 1
        assert len(visits[0].records) == 1

    def test_merge_multiple_patients(self):
        """测试多个不同患者的数据合并"""
        his_csv = os.path.join(self.temp_dir, "his.csv")
        emr_csv = os.path.join(self.temp_dir, "emr.csv")

        self._create_his_csv(
            his_csv,
            [
                {
                    "order_id": "ORD001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "B超",
                    "create_time": "2024-01-15 10:00:00",
                    "status": "pending",
                },
                {
                    "order_id": "ORD002",
                    "patient_id": "P002",
                    "doctor_id": "D002",
                    "department": "外科",
                    "order_type": "药品",
                    "item_name": "布洛芬",
                    "create_time": "2024-01-15 14:00:00",
                    "status": "pending",
                },
            ],
        )

        self._create_emr_csv(
            emr_csv,
            [
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "首次病程",
                    "content_keywords": "B超",
                    "create_time": "2024-01-15 11:00:00",
                },
            ],
        )

        loader = MergedDataLoader()
        visits = loader.load(his_csv, emr_csv)

        assert len(visits) == 2

        # 按patient_id排序
        visits.sort(key=lambda v: v.patient_id)

        assert visits[0].patient_id == "P001"
        assert len(visits[0].orders) == 1
        assert len(visits[0].records) == 1

        assert visits[1].patient_id == "P002"
        assert len(visits[1].orders) == 1
        assert len(visits[1].records) == 0

    def test_merge_same_patient_different_days(self):
        """测试同一患者不同日期的数据分别合并"""
        his_csv = os.path.join(self.temp_dir, "his.csv")
        emr_csv = os.path.join(self.temp_dir, "emr.csv")

        self._create_his_csv(
            his_csv,
            [
                {
                    "order_id": "ORD001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "B超",
                    "create_time": "2024-01-15 10:00:00",
                    "status": "pending",
                },
                {
                    "order_id": "ORD002",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "CT",
                    "create_time": "2024-01-16 10:00:00",
                    "status": "pending",
                },
            ],
        )

        self._create_emr_csv(
            emr_csv,
            [
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "首次病程",
                    "content_keywords": "B超",
                    "create_time": "2024-01-15 11:00:00",
                },
            ],
        )

        loader = MergedDataLoader()
        visits = loader.load(his_csv, emr_csv)

        assert len(visits) == 2

        visits.sort(key=lambda v: v.visit_date)

        assert visits[0].visit_date == datetime(2024, 1, 15, 0, 0, 0)
        assert len(visits[0].orders) == 1
        assert visits[0].orders[0].item_name == "B超"

        assert visits[1].visit_date == datetime(2024, 1, 16, 0, 0, 0)
        assert len(visits[1].orders) == 1
        assert visits[1].orders[0].item_name == "CT"
        assert len(visits[1].records) == 0

    def test_merge_with_directory(self):
        """测试从目录加载数据"""
        his_dir = os.path.join(self.temp_dir, "his")
        emr_dir = os.path.join(self.temp_dir, "emr")
        os.makedirs(his_dir)
        os.makedirs(emr_dir)

        his_csv1 = os.path.join(his_dir, "orders1.csv")
        his_csv2 = os.path.join(his_dir, "orders2.csv")

        self._create_his_csv(
            his_csv1,
            [
                {
                    "order_id": "ORD001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "B超",
                    "create_time": "2024-01-15 10:00:00",
                    "status": "pending",
                },
            ],
        )

        self._create_his_csv(
            his_csv2,
            [
                {
                    "order_id": "ORD002",
                    "patient_id": "P002",
                    "doctor_id": "D002",
                    "department": "外科",
                    "order_type": "药品",
                    "item_name": "布洛芬",
                    "create_time": "2024-01-15 14:00:00",
                    "status": "pending",
                },
            ],
        )

        emr_csv = os.path.join(emr_dir, "records.csv")
        self._create_emr_csv(
            emr_csv,
            [
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "首次病程",
                    "content_keywords": "B超",
                    "create_time": "2024-01-15 11:00:00",
                },
            ],
        )

        loader = MergedDataLoader()
        visits = loader.load(his_dir, emr_dir)

        assert len(visits) == 2

    def test_merge_with_json_file(self):
        """测试从JSON文件加载数据"""
        his_json = os.path.join(self.temp_dir, "his.json")
        emr_json = os.path.join(self.temp_dir, "emr.json")

        with open(his_json, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "order_id": "ORD001",
                        "patient_id": "P001",
                        "doctor_id": "D001",
                        "department": "内科",
                        "order_type": "检查",
                        "item_name": "B超",
                        "create_time": "2024-01-15 10:00:00",
                        "status": "pending",
                    }
                ],
                f,
            )

        with open(emr_json, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "record_id": "REC001",
                        "patient_id": "P001",
                        "doctor_id": "D001",
                        "department": "内科",
                        "record_type": "首次病程",
                        "content_keywords": ["B超"],
                        "create_time": "2024-01-15 11:00:00",
                    }
                ],
                f,
            )

        loader = MergedDataLoader()
        visits = loader.load(his_json, emr_json)

        assert len(visits) == 1
        assert visits[0].patient_id == "P001"
        assert len(visits[0].orders) == 1
        assert len(visits[0].records) == 1

    def test_merge_empty_his_data(self):
        """测试只有EMR数据的情况"""
        his_csv = os.path.join(self.temp_dir, "his_empty.csv")
        emr_csv = os.path.join(self.temp_dir, "emr.csv")

        # 创建空的HIS文件
        self._create_his_csv(his_csv, [])

        self._create_emr_csv(
            emr_csv,
            [
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "首次病程",
                    "content_keywords": "入院",
                    "create_time": "2024-01-15 09:00:00",
                },
            ],
        )

        loader = MergedDataLoader()
        # 空HIS数据会抛出EmptyDataError，因为MergedDataLoader.load要求至少有一个数据源有数据
        with pytest.raises(EmptyDataError):
            loader.load(his_csv, emr_csv)

    def test_merge_empty_emr_data(self):
        """测试只有HIS数据的情况"""
        his_csv = os.path.join(self.temp_dir, "his.csv")
        emr_csv = os.path.join(self.temp_dir, "emr_empty.csv")

        self._create_his_csv(
            his_csv,
            [
                {
                    "order_id": "ORD001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "B超",
                    "create_time": "2024-01-15 10:00:00",
                    "status": "pending",
                },
            ],
        )

        # 创建空的EMR文件
        self._create_emr_csv(emr_csv, [])

        loader = MergedDataLoader()
        # 空EMR数据会抛出EmptyDataError
        with pytest.raises(EmptyDataError):
            loader.load(his_csv, emr_csv)

    def test_merge_multiple_orders_and_records(self):
        """测试一个患者有多条医嘱和多条病程记录"""
        his_csv = os.path.join(self.temp_dir, "his.csv")
        emr_csv = os.path.join(self.temp_dir, "emr.csv")

        self._create_his_csv(
            his_csv,
            [
                {
                    "order_id": "ORD001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检查",
                    "item_name": "B超",
                    "create_time": "2024-01-15 10:00:00",
                    "status": "pending",
                },
                {
                    "order_id": "ORD002",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "检验",
                    "item_name": "血常规",
                    "create_time": "2024-01-15 10:30:00",
                    "status": "pending",
                },
                {
                    "order_id": "ORD003",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "order_type": "药品",
                    "item_name": "阿莫西林",
                    "create_time": "2024-01-15 11:00:00",
                    "status": "pending",
                },
            ],
        )

        self._create_emr_csv(
            emr_csv,
            [
                {
                    "record_id": "REC001",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "首次病程",
                    "content_keywords": "入院;检查",
                    "create_time": "2024-01-15 09:00:00",
                },
                {
                    "record_id": "REC002",
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "record_type": "日常病程",
                    "content_keywords": "B超;血常规",
                    "create_time": "2024-01-15 12:00:00",
                },
            ],
        )

        loader = MergedDataLoader()
        visits = loader.load(his_csv, emr_csv)

        assert len(visits) == 1
        assert visits[0].patient_id == "P001"
        assert len(visits[0].orders) == 3
        assert len(visits[0].records) == 2

        # 验证医嘱按时间排序
        order_times = [o.create_time for o in visits[0].orders]
        assert order_times == sorted(order_times)


class TestVisitStatistics:
    """VisitStatistics测试"""

    def test_total_visits(self):
        """测试总就诊次数"""
        visits = [
            PatientVisit(patient_id="P001", visit_date=datetime(2024, 1, 15)),
            PatientVisit(patient_id="P002", visit_date=datetime(2024, 1, 15)),
        ]
        stats = VisitStatistics(visits)
        assert stats.total_visits == 2

    def test_total_orders(self):
        """测试总医嘱数"""
        visits = [
            PatientVisit(
                patient_id="P001",
                visit_date=datetime(2024, 1, 15),
                orders=[
                    HisOrder(
                        order_id="ORD001",
                        patient_id="P001",
                        doctor_id="D001",
                        department="内科",
                        order_type="检查",
                        item_name="B超",
                        create_time="2024-01-15 10:00:00",
                    )
                ],
            ),
            PatientVisit(
                patient_id="P002",
                visit_date=datetime(2024, 1, 15),
                orders=[
                    HisOrder(
                        order_id="ORD002",
                        patient_id="P002",
                        doctor_id="D002",
                        department="外科",
                        order_type="药品",
                        item_name="布洛芬",
                        create_time="2024-01-15 14:00:00",
                    )
                ],
            ),
        ]
        stats = VisitStatistics(visits)
        assert stats.total_orders == 2

    def test_unique_patients(self):
        """测试独立患者数"""
        visits = [
            PatientVisit(patient_id="P001", visit_date=datetime(2024, 1, 15)),
            PatientVisit(patient_id="P001", visit_date=datetime(2024, 1, 16)),
            PatientVisit(patient_id="P002", visit_date=datetime(2024, 1, 15)),
        ]
        stats = VisitStatistics(visits)
        assert stats.unique_patients == 2

    def test_visits_by_department(self):
        """测试按科室统计就诊次数"""
        visits = [
            PatientVisit(
                patient_id="P001",
                visit_date=datetime(2024, 1, 15),
                orders=[
                    HisOrder(
                        order_id="ORD001",
                        patient_id="P001",
                        doctor_id="D001",
                        department="内科",
                        order_type="检查",
                        item_name="B超",
                        create_time="2024-01-15 10:00:00",
                    )
                ],
            ),
            PatientVisit(
                patient_id="P002",
                visit_date=datetime(2024, 1, 15),
                orders=[
                    HisOrder(
                        order_id="ORD002",
                        patient_id="P002",
                        doctor_id="D002",
                        department="外科",
                        order_type="药品",
                        item_name="布洛芬",
                        create_time="2024-01-15 14:00:00",
                    )
                ],
            ),
            PatientVisit(
                patient_id="P003",
                visit_date=datetime(2024, 1, 16),
                orders=[
                    HisOrder(
                        order_id="ORD003",
                        patient_id="P003",
                        doctor_id="D003",
                        department="内科",
                        order_type="检验",
                        item_name="血常规",
                        create_time="2024-01-16 10:00:00",
                    )
                ],
            ),
        ]
        stats = VisitStatistics(visits)
        dept_counts = stats.visits_by_department
        assert dept_counts["内科"] == 2
        assert dept_counts["外科"] == 1