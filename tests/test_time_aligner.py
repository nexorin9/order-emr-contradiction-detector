"""
时间对齐引擎单元测试

测试TimeAligner类的对齐功能。
"""

import pytest
from datetime import datetime, timedelta

from src.py.data.his_adapter import HisOrder
from src.py.data.emr_adapter import EmrRecord
from src.py.engine.time_aligner import TimeAligner, AlignedOrderRecord, align_orders_and_records


class TestTimeAligner:
    """TimeAligner单元测试"""

    def setup_method(self):
        """测试前准备"""
        self.aligner = TimeAligner(time_window_minutes=120)

    def _create_order(
        self,
        order_id: str,
        patient_id: str,
        item_name: str,
        create_time: datetime,
        **kwargs
    ) -> HisOrder:
        """创建测试用医嘱"""
        return HisOrder(
            order_id=order_id,
            patient_id=patient_id,
            doctor_id=kwargs.get("doctor_id", "D001"),
            department=kwargs.get("department", "内科"),
            order_type=kwargs.get("order_type", "检查"),
            item_name=item_name,
            create_time=create_time,
            execute_time=kwargs.get("execute_time"),
            status=kwargs.get("status", "pending"),
        )

    def _create_record(
        self,
        record_id: str,
        patient_id: str,
        content_keywords: list,
        create_time: datetime,
        **kwargs
    ) -> EmrRecord:
        """创建测试用病程记录"""
        return EmrRecord(
            record_id=record_id,
            patient_id=patient_id,
            doctor_id=kwargs.get("doctor_id", "D001"),
            department=kwargs.get("department", "内科"),
            record_type=kwargs.get("record_type", "日常病程"),
            content_keywords=content_keywords,
            create_time=create_time,
        )

    def test_align_with_exact_match(self):
        """测试精确匹配"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            self._create_order("O001", "P001", "B超", base_time),
        ]

        records = [
            self._create_record("R001", "P001", ["B超", "血常规"], base_time + timedelta(minutes=30)),
        ]

        results = self.aligner.align(orders, records)

        assert len(results) == 1
        assert results[0].matched is True
        assert results[0].match_type == "exact"
        assert "B超" in results[0].matched_keywords

    def test_align_with_fuzzy_match(self):
        """测试模糊匹配（包含关系）"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            self._create_order("O001", "P001", "B超", base_time),
        ]

        records = [
            self._create_record("R001", "P001", ["腹部B超", "肝胆B超"], base_time + timedelta(minutes=30)),
        ]

        results = self.aligner.align(orders, records)

        assert len(results) == 1
        assert results[0].matched is True
        assert results[0].match_type == "fuzzy"
        assert len(results[0].matched_keywords) > 0

    def test_align_no_match_different_patient(self):
        """测试不同患者不匹配"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            self._create_order("O001", "P001", "B超", base_time),
        ]

        records = [
            self._create_record("R001", "P002", ["B超"], base_time + timedelta(minutes=30)),
        ]

        results = self.aligner.align(orders, records)

        assert len(results) == 1
        assert results[0].matched is False
        assert results[0].match_type == "none"

    def test_align_no_match_outside_time_window(self):
        """测试时间窗口外不匹配"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            self._create_order("O001", "P001", "B超", base_time),
        ]

        # 病程记录在3小时后（超出120分钟窗口）
        records = [
            self._create_record("R001", "P001", ["B超"], base_time + timedelta(hours=3)),
        ]

        results = self.aligner.align(orders, records)

        assert len(results) == 1
        assert results[0].matched is False

    def test_align_multiple_orders_and_records(self):
        """测试多条医嘱和多条病程记录"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            self._create_order("O001", "P001", "B超", base_time),
            self._create_order("O002", "P001", "血常规", base_time + timedelta(minutes=10)),
            self._create_order("O003", "P001", "CT", base_time + timedelta(minutes=20)),
        ]

        records = [
            self._create_record("R001", "P001", ["B超"], base_time + timedelta(minutes=30)),
            self._create_record("R002", "P001", ["血常规"], base_time + timedelta(minutes=40)),
        ]

        results = self.aligner.align(orders, records)

        assert len(results) == 3

        # O001 (B超) 应该匹配
        o001_result = next(r for r in results if r.order.order_id == "O001")
        assert o001_result.matched is True

        # O002 (血常规) 应该匹配
        o002_result = next(r for r in results if r.order.order_id == "O002")
        assert o002_result.matched is True

        # O003 (CT) 不应该匹配（没有病程记录提及CT）
        o003_result = next(r for r in results if r.order.order_id == "O003")
        assert o003_result.matched is False

    def test_align_record_before_order(self):
        """测试病程记录早于医嘱的情况"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            self._create_order("O001", "P001", "B超", base_time + timedelta(minutes=30)),
        ]

        # 病程记录在医嘱之前30分钟
        records = [
            self._create_record("R001", "P001", ["B超"], base_time),
        ]

        results = self.aligner.align(orders, records)

        assert len(results) == 1
        # 应该匹配，因为病程记录在医嘱之前30分钟（时间窗口内）
        assert results[0].matched is True

    def test_align_empty_orders(self):
        """测试空医嘱列表"""
        records = [
            self._create_record("R001", "P001", ["B超"], datetime.now()),
        ]

        results = self.aligner.align([], records)

        assert len(results) == 0

    def test_align_empty_records(self):
        """测试空病程记录列表"""
        orders = [
            self._create_order("O001", "P001", "B超", datetime.now()),
        ]

        results = self.aligner.align(orders, [])

        assert len(results) == 1
        assert results[0].matched is False

    def test_align_time_diff_calculation(self):
        """测试时间差计算"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            self._create_order("O001", "P001", "B超", base_time),
        ]

        records = [
            self._create_record("R001", "P001", ["B超"], base_time + timedelta(minutes=45)),
        ]

        results = self.aligner.align(orders, records)

        assert len(results) == 1
        assert results[0].matched is True
        assert results[0].time_diff_minutes == 45.0

    def test_align_keywords_in_record_only(self):
        """测试病程记录关键词完全匹配"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            self._create_order("O001", "P001", "阿莫西林", base_time),
        ]

        # 病程记录有关键词但医嘱项目是同义词
        records = [
            self._create_record("R001", "P001", ["阿莫西林胶囊", "用药史"], base_time + timedelta(minutes=30)),
        ]

        results = self.aligner.align(orders, records)

        assert len(results) == 1
        # 阿莫西林 应该能匹配到 阿莫西林胶囊
        assert results[0].matched is True


class TestAlignOrdersAndRecordsFunction:
    """align_orders_and_records便捷函数测试"""

    def test_convenience_function(self):
        """测试便捷函数"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time,
            )
        ]

        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["B超"],
                create_time=base_time + timedelta(minutes=30),
            )
        ]

        results = align_orders_and_records(orders, records, time_window_minutes=120)

        assert len(results) == 1
        assert results[0].matched is True


class TestTimeAlignerEdgeCases:
    """边界情况测试"""

    def setup_method(self):
        """测试前准备"""
        self.aligner = TimeAligner(time_window_minutes=120)

    def test_order_with_none_create_time(self):
        """测试医嘱创建时间为空"""
        order = HisOrder(
            order_id="O001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time=None,  # 无创建时间
        )

        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["B超"],
                create_time=datetime(2024, 1, 15, 9, 30, 0),
            )
        ]

        results = self.aligner.align([order], records)

        assert len(results) == 1
        assert results[0].matched is False
        assert "无效" in results[0].match_basis

    def test_record_with_none_create_time(self):
        """测试病程记录创建时间为空"""
        order = HisOrder(
            order_id="O001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time=datetime(2024, 1, 15, 9, 0, 0),
        )

        record = EmrRecord(
            record_id="R001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            record_type="日常病程",
            content_keywords=["B超"],
            create_time=None,  # 无创建时间
        )

        results = self.aligner.align([order], [record])

        assert len(results) == 1
        # 应该跳过这条病程记录，不影响匹配
        assert results[0].matched is False

    def test_empty_keywords_in_record(self):
        """测试病程记录关键词为空"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        order = HisOrder(
            order_id="O001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            order_type="检查",
            item_name="B超",
            create_time=base_time,
        )

        record = EmrRecord(
            record_id="R001",
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            record_type="日常病程",
            content_keywords=[],  # 空关键词
            create_time=base_time + timedelta(minutes=30),
        )

        results = self.aligner.align([order], [record])

        assert len(results) == 1
        assert results[0].matched is False

    def test_custom_time_window(self):
        """测试自定义时间窗口"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        # 使用30分钟时间窗口
        aligner = TimeAligner(time_window_minutes=30)

        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time,
            )
        ]

        # 病程记录在1小时后（超出30分钟窗口）
        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["B超"],
                create_time=base_time + timedelta(hours=1),
            )
        ]

        results = aligner.align(orders, records)

        assert len(results) == 1
        assert results[0].matched is False


class TestTimeAlignerAlignByRecord:
    """align_by_record方法测试（覆盖写了没开矛盾检测）

    注意：align_by_record 查找在病程记录时间之前的 time_window 分钟内的医嘱。
    病程记录在时间线上早于医嘱（记录反映已发生的事）。
    """

    def setup_method(self):
        """测试前准备"""
        self.aligner = TimeAligner(time_window_minutes=120)

    def test_align_by_record_record_before_order(self):
        """测试病程记录在医嘱之前的情况（正常业务场景）

        医生先为患者做检查（记录），稍后补录医嘱。
        记录早于医嘱，时间差为负。
        """
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        # 病程记录在9:00（记录早于医嘱）
        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["B超"],
                create_time=base_time,
            ),
        ]

        # 医嘱在9:30（医嘱晚于记录）
        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time + timedelta(minutes=30),
            ),
        ]

        results = self.aligner.align_by_record(orders, records)

        assert len(results) == 1
        # 病程记录提及了B超，且在记录之前30分钟内有对应医嘱
        assert results[0].matched is True
        assert results[0].order.order_id == "O001"

    def test_align_by_record_no_matching_order(self):
        """测试写了没开：记录提及了但没有对应医嘱"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["布洛芬", "退烧药"],
                create_time=base_time,
            ),
        ]

        # 医嘱是B超，不是布洛芬
        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time + timedelta(minutes=30),
            ),
        ]

        results = self.aligner.align_by_record(orders, records)

        assert len(results) == 1
        assert results[0].matched is False
        assert "布洛芬" in results[0].record.content_keywords

    def test_align_by_record_outside_time_window(self):
        """测试时间窗口外的不匹配"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["B超"],
                create_time=base_time,
            ),
        ]

        # 医嘱在3小时后（超出120分钟窗口）
        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time + timedelta(hours=3),
            ),
        ]

        results = self.aligner.align_by_record(orders, records)

        assert len(results) == 1
        assert results[0].matched is False

    def test_align_by_record_no_orders(self):
        """测试无医嘱时的不匹配"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["CT", "核磁共振"],
                create_time=base_time,
            ),
        ]

        results = self.aligner.align_by_record([], records)

        assert len(results) == 1
        assert results[0].matched is False

    def test_align_by_record_different_patient(self):
        """测试不同患者的不匹配"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["B超"],
                create_time=base_time,
            ),
        ]

        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P002",  # 不同患者
                doctor_id="D002",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time + timedelta(minutes=30),
            ),
        ]

        results = self.aligner.align_by_record(orders, records)

        assert len(results) == 1
        assert results[0].matched is False

    def test_align_by_record_empty_records(self):
        """测试空病程记录列表"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time,
            ),
        ]

        results = self.aligner.align_by_record(orders, [])

        assert len(results) == 0

    def test_align_by_record_record_none_time(self):
        """测试病程记录时间为空"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["B超"],
                create_time=None,  # 无创建时间
            ),
        ]

        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time,
            ),
        ]

        results = self.aligner.align_by_record(orders, records)

        assert len(results) == 1
        assert results[0].matched is False
        assert "无效" in results[0].match_basis

    def test_align_by_record_multiple_records(self):
        """测试多条病程记录"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="首次病程",
                content_keywords=["B超"],
                create_time=base_time,
            ),
            EmrRecord(
                record_id="R002",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["透视"],
                create_time=base_time + timedelta(minutes=10),
            ),
        ]

        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="B超",
                create_time=base_time + timedelta(minutes=30),
            ),
        ]

        results = self.aligner.align_by_record(orders, records)

        assert len(results) == 2

        matched = [r for r in results if r.matched]
        unmatched = [r for r in results if not r.matched]

        assert len(matched) == 1
        assert len(unmatched) == 1


class TestTimeAlignerSynonymMatching:
    """同义词匹配测试"""

    def setup_method(self):
        """测试前准备"""
        self.aligner = TimeAligner(time_window_minutes=120)

    def test_align_with_exact_keyword_match(self):
        """测试精确关键词匹配"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="检查",
                item_name="CT",
                create_time=base_time,
            ),
        ]

        # 病程记录使用CT的同义词（如电子计算机断层扫描）
        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["CT", "电子计算机断层扫描"],
                create_time=base_time + timedelta(minutes=30),
            ),
        ]

        results = self.aligner.align(orders, records)

        # CT 能匹配到 CT
        assert len(results) == 1
        assert results[0].matched is True

    def test_check_keyword_match_partial_overlap(self):
        """测试关键词部分重叠匹配"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)

        orders = [
            HisOrder(
                order_id="O001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                order_type="药品",
                item_name="阿莫西林",
                create_time=base_time,
            ),
        ]

        # 病程记录提及阿莫西林相关但不同形态
        records = [
            EmrRecord(
                record_id="R001",
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                record_type="日常病程",
                content_keywords=["阿莫西林胶囊", "抗生素治疗"],
                create_time=base_time + timedelta(minutes=30),
            ),
        ]

        results = self.aligner.align(orders, records)

        # 阿莫西林 应该能匹配到阿莫西林胶囊（包含关系）
        assert len(results) == 1
        assert results[0].matched is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])