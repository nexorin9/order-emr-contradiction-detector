"""
矛盾检测引擎单元测试

测试 ContradictionDetector 类的核心功能：
1. ordered_but_not_recorded（开了没写）检测
2. recorded_but_not_ordered（写了没开）检测
3. 严重程度分级
4. 统计功能
"""

import pytest
from datetime import datetime, timedelta

from src.py.data.his_adapter import HisOrder
from src.py.data.emr_adapter import EmrRecord
from src.py.data.merged_loader import PatientVisit
from src.py.engine.contradiction_engine import (
    Contradiction,
    ContradictionDetector,
    detect_contradictions,
)


class TestContradictionDetector:
    """矛盾检测器测试类"""

    @pytest.fixture
    def sample_orders(self):
        """创建示例医嘱数据"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)
        return [
            HisOrder(
                order_id="ORD001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time,
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
    def sample_records(self):
        """创建示例病程记录数据"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)
        return [
            EmrRecord(
                record_id="REC001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="首次病程",
                content_keywords=["B超"],
                create_time=base_time + timedelta(minutes=5),
            ),
            # 缺少对"血常规"和"阿莫西林"的记录（开了没写）
            # 缺少对"雾化"的记录（开了没写）
            EmrRecord(
                record_id="REC002",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["布洛芬"],  # 写了没开
                create_time=base_time + timedelta(minutes=40),
            ),
        ]

    @pytest.fixture
    def patient_visit(self, sample_orders, sample_records):
        """创建患者就诊记录"""
        return PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            orders=sample_orders,
            records=sample_records,
        )

    def test_detect_ordered_but_not_recorded(self, patient_visit):
        """测试开了没写检测"""
        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([patient_visit])

        # 筛选 ordered_but_not_recorded 类型
        ordered_not_recorded = [
            c for c in contradictions if c.rule_type == "ordered_but_not_recorded"
        ]

        # 应该检测到：血常规、阿莫西林、雾化（3条开了没写）
        assert len(ordered_not_recorded) == 3

        # 检查是否包含正确的医嘱项目
        order_items = {c.order_item_name for c in ordered_not_recorded}
        assert "血常规" in order_items
        assert "阿莫西林" in order_items
        assert "雾化" in order_items

        # B超应该被检测到（因为有时间匹配的病程记录）
        assert "B超" not in order_items

    def test_detect_recorded_but_not_ordered(self, patient_visit):
        """测试写了没开检测"""
        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([patient_visit])

        # 筛选 recorded_but_not_ordered 类型
        recorded_not_ordered = [
            c for c in contradictions if c.rule_type == "recorded_but_not_ordered"
        ]

        # 应该检测到：布洛芬（1条写了没开）
        assert len(recorded_not_ordered) == 1
        assert "布洛芬" in recorded_not_ordered[0].record_keywords

    def test_severity_classification(self, patient_visit):
        """测试严重程度分级"""
        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([patient_visit])

        # 检查各类严重程度
        high_severity = [c for c in contradictions if c.severity == "high"]
        medium_severity = [c for c in contradictions if c.severity == "medium"]
        low_severity = [c for c in contradictions if c.severity == "low"]

        # 检查类（检查、检验）应该是高危
        # 血常规（检验）-> high, 布洛芬（药品）-> medium, 雾化（治疗）-> low
        assert len(high_severity) >= 1  # 血常规（检验）
        assert len(medium_severity) >= 1  # 布洛芬（药品）
        assert len(low_severity) >= 1  # 雾化（治疗）

    def test_contradiction_to_dict(self, patient_visit):
        """测试矛盾结果转换为字典"""
        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([patient_visit])

        if contradictions:
            c = contradictions[0]
            d = c.to_dict()

            assert "patient_id" in d
            assert "doctor_id" in d
            assert "department" in d
            assert "rule_type" in d
            assert "severity" in d
            assert "description" in d

    def test_get_summary_stats(self, patient_visit):
        """测试统计摘要功能"""
        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([patient_visit])

        stats = detector.get_summary_stats(contradictions)

        assert "total" in stats
        assert "by_severity" in stats
        assert "by_rule_type" in stats
        assert "by_department" in stats
        assert stats["total"] == len(contradictions)

    def test_get_contradictions_by_department(self, patient_visit):
        """测试按科室分组"""
        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([patient_visit])

        by_dept = detector.get_contradictions_by_department(contradictions)

        assert "内科" in by_dept
        assert len(by_dept["内科"]) == len(contradictions)

    def test_get_contradictions_by_doctor(self, patient_visit):
        """测试按医生分组"""
        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([patient_visit])

        by_doctor = detector.get_contradictions_by_doctor(contradictions)

        assert "D001" in by_doctor
        assert len(by_doctor["D001"]) == len(contradictions)

    def test_no_contradiction_when_matched(self):
        """测试完全匹配时无矛盾"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            HisOrder(
                order_id="ORD001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time,
                status="completed",
            ),
        ]

        records = [
            EmrRecord(
                record_id="REC001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="首次病程",
                content_keywords=["B超"],
                create_time=base_time + timedelta(minutes=10),
            ),
        ]

        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            orders=orders,
            records=records,
        )

        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([visit])

        # 应该没有矛盾
        assert len(contradictions) == 0

    def test_empty_patient_visit(self):
        """测试空就诊记录"""
        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            orders=[],
            records=[],
        )

        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([visit])

        assert len(contradictions) == 0

    def test_only_orders_no_records(self):
        """测试只有医嘱没有病程记录"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            HisOrder(
                order_id="ORD001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time,
                status="completed",
            ),
        ]

        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            orders=orders,
            records=[],
        )

        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([visit])

        # 应该检测到开了没写
        assert len(contradictions) == 1
        assert contradictions[0].rule_type == "ordered_but_not_recorded"

    def test_only_records_no_orders(self):
        """测试只有病程记录没有医嘱"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        records = [
            EmrRecord(
                record_id="REC001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="首次病程",
                content_keywords=["B超"],
                create_time=base_time,
            ),
        ]

        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            orders=[],
            records=records,
        )

        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([visit])

        # 应该检测到写了没开
        assert len(contradictions) == 1
        assert contradictions[0].rule_type == "recorded_but_not_ordered"

    def test_convenience_function(self):
        """测试便捷函数"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            HisOrder(
                order_id="ORD001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time,
                status="completed",
            ),
        ]

        records = [
            EmrRecord(
                record_id="REC001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="首次病程",
                content_keywords=["CT"],  # 写了没开
                create_time=base_time + timedelta(minutes=10),
            ),
        ]

        visit = PatientVisit(
            patient_id="P001",
            visit_date=datetime(2024, 1, 15),
            orders=orders,
            records=records,
        )

        # 使用便捷函数
        contradictions = detect_contradictions([visit], time_window_minutes=120)

        # 应该检测到：开了没写（B超） + 写了没开（CT）
        assert len(contradictions) == 2

    def test_multiple_patients(self):
        """测试多个患者"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        # 患者1：有矛盾 - B超开了没写 + CT写了没开
        visit1 = PatientVisit(
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
                    create_time=base_time,
                    status="completed",
                ),
            ],
            records=[
                EmrRecord(
                    record_id="REC001",
                    patient_id="P001",
                    doctor_id="D001",
                    department="内科",
                    record_type="首次病程",
                    content_keywords=["CT"],  # 写了没开
                    create_time=base_time + timedelta(minutes=10),
                ),
            ],
        )

        # 患者2：完全正常
        visit2 = PatientVisit(
            patient_id="P002",
            visit_date=datetime(2024, 1, 15),
            orders=[
                HisOrder(
                    order_id="ORD002",
                    patient_id="P002",
                    doctor_id="D002",
                    department="外科",
                    order_type="检查",
                    item_name="X光",
                    create_time=base_time,
                    status="completed",
                ),
            ],
            records=[
                EmrRecord(
                    record_id="REC002",
                    patient_id="P002",
                    doctor_id="D002",
                    department="外科",
                    record_type="首次病程",
                    content_keywords=["X光"],
                    create_time=base_time + timedelta(minutes=5),
                ),
            ],
        )

        detector = ContradictionDetector(time_window_minutes=120)
        contradictions = detector.detect([visit1, visit2])

        # 患者1有2个矛盾：开了没写(B超) + 写了没开(CT)
        # 患者2没有矛盾（X光医嘱和记录都匹配）
        assert len(contradictions) == 2
        p001_contradictions = [c for c in contradictions if c.patient_id == "P001"]
        assert len(p001_contradictions) == 2
        # 验证矛盾类型
        rule_types = {c.rule_type for c in p001_contradictions}
        assert "ordered_but_not_recorded" in rule_types
        assert "recorded_but_not_ordered" in rule_types


class TestContradictionDataClass:
    """Contradiction 数据类测试"""

    def test_contradiction_creation(self):
        """测试矛盾对象创建"""
        now = datetime.now()
        c = Contradiction(
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            rule_type="ordered_but_not_recorded",
            order_id="ORD001",
            record_id="",
            order_item_name="B超",
            record_keywords=[],
            create_time=now,
            severity="high",
            description="开了B超但没写病程记录",
            matched_keywords=["B超"],
            time_window_minutes=120,
        )

        assert c.patient_id == "P001"
        assert c.rule_type == "ordered_but_not_recorded"
        assert c.severity == "high"
        assert c.time_window_minutes == 120

    def test_contradiction_to_dict_complete(self):
        """测试完整转换"""
        now = datetime(2024, 1, 15, 10, 0, 0)
        c = Contradiction(
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            rule_type="recorded_but_not_ordered",
            order_id="",
            record_id="REC001",
            order_item_name="",
            record_keywords=["布洛芬", "退烧药"],
            create_time=now,
            severity="medium",
            description="写了布洛芬但没开医嘱",
            matched_keywords=[],
            time_window_minutes=120,
        )

        d = c.to_dict()

        assert d["patient_id"] == "P001"
        assert d["rule_type"] == "recorded_but_not_ordered"
        assert d["record_keywords"] == ["布洛芬", "退烧药"]
        assert d["severity"] == "medium"
        assert d["create_time"] == "2024-01-15T10:00:00"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])