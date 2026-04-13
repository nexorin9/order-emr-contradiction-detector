"""
告警引擎单元测试

测试 AlertEngine 类的核心功能：
1. 按医生维度生成告警汇总
2. 按科室维度生成告警汇总
3. 告警级别判断（info/warning/error/critical）
4. Webhook推送功能
5. 文件输出功能
"""

import json
import os
import tempfile
import pytest
from datetime import datetime, timedelta

from src.py.engine.alert_engine import (
    AlertConfig,
    AlertEngine,
    AlertSummary,
    generate_alerts,
)
from src.py.engine.contradiction_engine import Contradiction


class TestAlertConfig:
    """AlertConfig配置类测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = AlertConfig()
        assert config.enabled is True
        assert config.doctor_daily_threshold == 3
        assert config.department_daily_threshold == 10
        assert config.high_severity_threshold == 1

    def test_from_dict(self):
        """测试从字典创建配置"""
        config_dict = {
            "enabled": True,
            "doctor_daily_threshold": 5,
            "department_daily_threshold": 15,
            "high_severity_threshold": 2,
            "webhook_enabled": True,
            "webhook_url": "https://example.com/webhook",
            "file_output_enabled": True,
            "output_dir": "data/alerts",
        }
        config = AlertConfig.from_dict(config_dict)
        assert config.doctor_daily_threshold == 5
        assert config.department_daily_threshold == 15
        assert config.high_severity_threshold == 2
        assert config.webhook_url == "https://example.com/webhook"

    def test_alert_levels_default(self):
        """测试默认告警级别阈值"""
        config = AlertConfig()
        assert config.alert_levels["info"] == 0
        assert config.alert_levels["warning"] == 1
        assert config.alert_levels["error"] == 3
        assert config.alert_levels["critical"] == 5


class TestAlertSummary:
    """AlertSummary数据类测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        summary = AlertSummary(
            doctor_id="D001",
            doctor_name="张医生",
            department="内科",
            contradiction_count=5,
            high_severity_count=2,
            medium_severity_count=2,
            low_severity_count=1,
            alert_level="error",
            triggered_rules=["ordered_but_not_recorded"],
            detection_date="2024-01-15",
        )
        d = summary.to_dict()
        assert d["doctor_id"] == "D001"
        assert d["department"] == "内科"
        assert d["contradiction_count"] == 5
        assert d["high_severity_count"] == 2
        assert d["alert_level"] == "error"

    def test_to_summary_dict(self):
        """测试转换为简化摘要（不含详情）"""
        summary = AlertSummary(
            doctor_id="D001",
            department="内科",
            contradiction_count=5,
            high_severity_count=2,
            medium_severity_count=2,
            low_severity_count=1,
            alert_level="warning",
            details=[{"patient_id": "P001"}],  # 详情数据
        )
        d = summary.to_summary_dict()
        assert "details" not in d
        assert d["contradiction_count"] == 5


class TestAlertEngine:
    """AlertEngine告警引擎测试类"""

    @pytest.fixture
    def default_config(self):
        """创建默认配置"""
        return AlertConfig(
            enabled=True,
            doctor_daily_threshold=3,
            department_daily_threshold=10,
            high_severity_threshold=1,
            file_output_enabled=False,  # 测试时不写文件
            webhook_enabled=False,
        )

    @pytest.fixture
    def alert_engine(self, default_config):
        """创建告警引擎实例"""
        return AlertEngine(config=default_config)

    @pytest.fixture
    def sample_contradictions(self):
        """创建示例矛盾数据"""
        base_time = datetime(2024, 1, 15, 9, 0, 0)
        return [
            # D001医生的矛盾（3条，高危2条）
            Contradiction(
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                rule_type="ordered_but_not_recorded",
                order_id="ORD001",
                record_id="",
                order_item_name="B超",
                create_time=base_time,
                severity="high",
                description="医嘱项目「B超」未找到对应病程记录",
            ),
            Contradiction(
                patient_id="P002",
                doctor_id="D001",
                department="内科",
                rule_type="ordered_but_not_recorded",
                order_id="ORD002",
                record_id="",
                order_item_name="CT",
                create_time=base_time + timedelta(minutes=10),
                severity="high",
                description="医嘱项目「CT」未找到对应病程记录",
            ),
            Contradiction(
                patient_id="P003",
                doctor_id="D001",
                department="内科",
                rule_type="recorded_but_not_ordered",
                order_id="",
                record_id="REC001",
                order_item_name="",
                record_keywords=["血常规"],
                create_time=base_time + timedelta(minutes=20),
                severity="medium",
                description="病程记录提及了「血常规」",
            ),
            # D002医生的矛盾（2条，中危）
            Contradiction(
                patient_id="P004",
                doctor_id="D002",
                department="外科",
                rule_type="ordered_but_not_recorded",
                order_id="ORD003",
                record_id="",
                order_item_name="换药",
                create_time=base_time + timedelta(minutes=30),
                severity="low",
                description="医嘱项目「换药」未找到对应病程记录",
            ),
            Contradiction(
                patient_id="P005",
                doctor_id="D002",
                department="外科",
                rule_type="recorded_but_not_ordered",
                order_id="",
                record_id="REC002",
                order_item_name="",
                record_keywords=["雾化"],
                create_time=base_time + timedelta(minutes=40),
                severity="medium",
                description="病程记录提及了「雾化」",
            ),
            # D003医生的矛盾（1条，高危）
            Contradiction(
                patient_id="P006",
                doctor_id="D003",
                department="内科",
                rule_type="ordered_but_not_recorded",
                order_id="ORD004",
                record_id="",
                order_item_name="核磁共振",
                create_time=base_time + timedelta(minutes=50),
                severity="high",
                description="医嘱项目「核磁共振」未找到对应病程记录",
            ),
        ]

    def test_generate_alerts_empty(self, alert_engine):
        """测试空矛盾列表不生成告警"""
        alerts = alert_engine.generate_alerts([])
        assert len(alerts) == 0

    def test_generate_alerts_by_doctor(self, alert_engine, sample_contradictions):
        """测试按医生维度生成告警"""
        alerts = alert_engine.generate_alerts(sample_contradictions, "2024-01-15")

        # 过滤出医生维度的告警
        doctor_alerts = [a for a in alerts if a.doctor_id != "DEPT_ALL"]

        # D001: 3条矛盾，2高+1中 -> critical
        d001_alert = next((a for a in doctor_alerts if a.doctor_id == "D001"), None)
        assert d001_alert is not None
        assert d001_alert.contradiction_count == 3
        assert d001_alert.high_severity_count == 2
        assert d001_alert.medium_severity_count == 1
        assert d001_alert.alert_level == "critical"
        assert "ordered_but_not_recorded" in d001_alert.triggered_rules

        # D002: 2条矛盾，0高+1中+1低 -> warning (total=2 >= warning threshold=1, but < error threshold=3)
        d002_alert = next((a for a in doctor_alerts if a.doctor_id == "D002"), None)
        assert d002_alert is not None
        assert d002_alert.contradiction_count == 2
        assert d002_alert.alert_level == "warning"

        # D003: 1条矛盾，1高 -> critical（高危超过阈值）
        d003_alert = next((a for a in doctor_alerts if a.doctor_id == "D003"), None)
        assert d003_alert is not None
        assert d003_alert.contradiction_count == 1
        assert d003_alert.high_severity_count == 1
        assert d003_alert.alert_level == "critical"

    def test_generate_alerts_by_department(self, alert_engine, sample_contradictions):
        """测试按科室维度生成告警"""
        alerts = alert_engine.generate_alerts(sample_contradictions, "2024-01-15")

        # 过滤出科室维度的告警
        dept_alerts = [a for a in alerts if a.doctor_id == "DEPT_ALL"]

        # 内科：6条矛盾（3+1+2）
        internal_dept = next((a for a in dept_alerts if a.department == "内科"), None)
        assert internal_dept is not None
        assert internal_dept.contradiction_count == 4  # D001:3 + D003:1
        assert internal_dept.high_severity_count == 3

        # 外科：2条矛盾
        surgery_dept = next((a for a in dept_alerts if a.department == "外科"), None)
        assert surgery_dept is not None
        assert surgery_dept.contradiction_count == 2

    def test_alert_level_determination(self, alert_engine):
        """测试告警级别判断逻辑"""
        # high_severity_threshold=1 时
        # 1条高危 -> critical (high_count >= threshold)
        assert alert_engine._determine_alert_level(1, 1) == "critical"
        # 3条总量，0高危 -> error（>=3）
        assert alert_engine._determine_alert_level(3, 0) == "error"
        # 2条总量，0高危 -> warning（>=1且<3）
        assert alert_engine._determine_alert_level(2, 0) == "warning"
        # 1条总量，0高危 -> warning（>=1 default warning threshold）
        assert alert_engine._determine_alert_level(1, 0) == "warning"
        # 0条总量 -> info
        assert alert_engine._determine_alert_level(0, 0) == "info"

    def test_process_alerts_disabled(self):
        """测试禁用告警时不处理"""
        config = AlertConfig(enabled=False)
        engine = AlertEngine(config=config)
        contradictions = [
            Contradiction(
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                rule_type="ordered_but_not_recorded",
                order_id="ORD001",
                record_id="",
                order_item_name="B超",
                create_time=datetime.now(),
                severity="high",
            )
        ]
        alerts = engine.generate_alerts(contradictions)
        # enabled=False时仍生成告警（医生+科室），但process_alerts跳过处理
        # D001: 1 high contradiction -> critical (high >= threshold=1)
        # 科室"内科": 1 high -> warning (过滤info，但warning及以上仍生成)
        assert len(alerts) == 2
        results = engine.process_alerts(alerts)
        assert results["file_write_success"] is False
        assert results["webhook_push_success"] is False

    def test_process_alerts_file_output(self, sample_contradictions):
        """测试文件输出功能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = AlertConfig(
                enabled=True,
                file_output_enabled=True,
                output_dir=tmpdir,
                webhook_enabled=False,
            )
            engine = AlertEngine(config=config)
            alerts = engine.generate_alerts(sample_contradictions, "2024-01-15")
            results = engine.process_alerts(alerts)

            # 检查是否有可操作的告警被写入
            if results["file_count"] > 0:
                # 检查文件是否存在
                files = os.listdir(tmpdir)
                assert any(f.startswith("alerts_") and f.endswith(".json") for f in files)

                # 验证文件内容
                alert_file = next(f for f in files if f.startswith("alerts_"))
                filepath = os.path.join(tmpdir, alert_file)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    assert "alerts" in data
                    assert data["alert_count"] > 0

    def test_generate_alerts_convenience_function(self, sample_contradictions):
        """测试便捷函数generate_alerts"""
        config = AlertConfig(
            enabled=True,
            file_output_enabled=False,
            webhook_enabled=False,
        )
        alerts = generate_alerts(
            sample_contradictions,
            config=config,
            push_webhook=False,
            write_file=False,
        )
        assert len(alerts) > 0

    def test_contradiction_to_detail(self, alert_engine):
        """测试矛盾转详情"""
        contradiction = Contradiction(
            patient_id="P001",
            doctor_id="D001",
            department="内科",
            rule_type="ordered_but_not_recorded",
            order_id="ORD001",
            record_id="",
            order_item_name="B超",
            record_keywords=["B超"],
            create_time=datetime(2024, 1, 15, 9, 0, 0),
            severity="high",
            description="测试矛盾",
        )
        detail = alert_engine._contradiction_to_detail(contradiction)
        assert detail["patient_id"] == "P001"
        assert detail["order_item_name"] == "B超"
        assert detail["severity"] == "high"
        assert detail["rule_type"] == "ordered_but_not_recorded"


class TestAlertEngineEdgeCases:
    """告警引擎边界情况测试"""

    def test_no_doctor_alert_when_below_threshold(self):
        """测试矛盾数低于阈值时生成info级别告警（仅记录不推送）"""
        config = AlertConfig(
            enabled=True,
            doctor_daily_threshold=5,  # 阈值为5
            file_output_enabled=False,
            webhook_enabled=False,
        )
        engine = AlertEngine(config=config)

        # 只有1条低危矛盾，总数=1 >= warning阈值=1，所以是warning级别
        contradictions = [
            Contradiction(
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                rule_type="ordered_but_not_recorded",
                order_id="ORD001",
                record_id="",
                order_item_name="换药",
                create_time=datetime.now(),
                severity="low",
            )
        ]

        alerts = engine.generate_alerts(contradictions, "2024-01-15")
        # 1条低危矛盾 -> warning级别（因为总数>=1但<3）
        actionable = [a for a in alerts if a.alert_level != "info" and a.doctor_id != "DEPT_ALL"]
        assert len(actionable) == 1
        assert actionable[0].alert_level == "warning"

    def test_high_severity_triggers_critical(self):
        """测试高危矛盾直接触发critical"""
        config = AlertConfig(
            enabled=True,
            doctor_daily_threshold=10,  # 高阈值
            high_severity_threshold=1,
            file_output_enabled=False,
            webhook_enabled=False,
        )
        engine = AlertEngine(config=config)

        contradictions = [
            Contradiction(
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                rule_type="ordered_but_not_recorded",
                order_id="ORD001",
                record_id="",
                order_item_name="CT",
                create_time=datetime.now(),
                severity="high",
            )
        ]

        alerts = engine.generate_alerts(contradictions, "2024-01-15")
        d001_alert = next(a for a in alerts if a.doctor_id == "D001")
        assert d001_alert.alert_level == "critical"

    def test_multiple_rule_types_in_triggered_rules(self):
        """测试触发规则包含多种类型"""
        config = AlertConfig(
            enabled=True,
            doctor_daily_threshold=1,
            file_output_enabled=False,
            webhook_enabled=False,
        )
        engine = AlertEngine(config=config)

        contradictions = [
            Contradiction(
                patient_id="P001",
                doctor_id="D001",
                department="内科",
                rule_type="ordered_but_not_recorded",
                order_id="ORD001",
                record_id="",
                order_item_name="B超",
                create_time=datetime.now(),
                severity="high",
            ),
            Contradiction(
                patient_id="P002",
                doctor_id="D001",
                department="内科",
                rule_type="recorded_but_not_ordered",
                order_id="",
                record_id="REC001",
                order_item_name="",
                record_keywords=["血常规"],
                create_time=datetime.now(),
                severity="medium",
            ),
        ]

        alerts = engine.generate_alerts(contradictions, "2024-01-15")
        d001_alert = next(a for a in alerts if a.doctor_id == "D001")
        assert "ordered_but_not_recorded" in d001_alert.triggered_rules
        assert "recorded_but_not_ordered" in d001_alert.triggered_rules
