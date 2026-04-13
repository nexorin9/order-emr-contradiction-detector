"""
规则定义模块单元测试
"""

import os
import tempfile

import pytest
import yaml

from src.py.rules.rule_definitions import (
    AlertConfig,
    AlertThreshold,
    KeywordMatchingConfig,
    RuleDefinition,
    RuleDefinitionsLoader,
    SeverityConfig,
    SeverityDefinition,
    TimeWindowConfig,
)


class TestKeywordMatchingConfig:
    """KeywordMatchingConfig测试"""

    def test_from_dict_with_defaults(self):
        """测试默认值创建"""
        config = KeywordMatchingConfig.from_dict({})

        assert config.fuzzy_match is True
        assert config.synonyms == {}
        assert config.exclusion_keywords == []

    def test_from_dict_with_data(self):
        """测试使用数据创建"""
        data = {
            "fuzzy_match": False,
            "synonyms": {"B超": ["彩超", "超声检查"]},
            "exclusion_keywords": ["拒绝", "暂未"],
        }
        config = KeywordMatchingConfig.from_dict(data)

        assert config.fuzzy_match is False
        assert config.synonyms == {"B超": ["彩超", "超声检查"]}
        assert config.exclusion_keywords == ["拒绝", "暂未"]


class TestTimeWindowConfig:
    """TimeWindowConfig测试"""

    def test_from_dict_defaults(self):
        """测试默认值"""
        config = TimeWindowConfig.from_dict({})

        assert config.minutes == 120
        assert config.description == ""

    def test_from_dict_with_data(self):
        """测试使用数据创建"""
        data = {"minutes": 60, "description": "测试时间窗口"}
        config = TimeWindowConfig.from_dict(data)

        assert config.minutes == 60
        assert config.description == "测试时间窗口"


class TestRuleDefinition:
    """RuleDefinition测试"""

    def test_from_dict(self):
        """测试从字典创建规则定义"""
        data = {
            "rule_id": "RULE_001",
            "rule_type": "ordered_but_not_recorded",
            "display_name": "开了没写",
            "description": "测试规则描述",
            "severity": "high",
            "required_his_fields": ["order_id", "patient_id"],
            "required_emr_fields": ["record_id", "patient_id"],
            "keyword_matching": {
                "fuzzy_match": True,
                "synonyms": {"B超": ["彩超"]},
                "exclusion_keywords": ["拒绝"],
            },
            "time_window": {"minutes": 120, "description": "测试"},
            "applicable_departments": ["内科", "外科"],
            "applicable_order_types": ["检查", "检验"],
        }

        rule = RuleDefinition.from_dict(data)

        assert rule.rule_id == "RULE_001"
        assert rule.rule_type == "ordered_but_not_recorded"
        assert rule.display_name == "开了没写"
        assert rule.severity == "high"
        assert rule.required_his_fields == ["order_id", "patient_id"]
        assert rule.keyword_matching.fuzzy_match is True
        assert rule.time_window.minutes == 120
        assert rule.applicable_departments == ["内科", "外科"]
        assert rule.applicable_order_types == ["检查", "检验"]

    def test_is_applicable_department(self):
        """测试科室适用性判断"""
        data = {
            "rule_id": "RULE_001",
            "rule_type": "ordered_but_not_recorded",
            "display_name": "开了没写",
            "description": "",
            "severity": "high",
            "required_his_fields": [],
            "required_emr_fields": [],
            "keyword_matching": {},
            "time_window": {},
            "applicable_departments": ["内科", "外科"],
        }

        rule = RuleDefinition.from_dict(data)

        assert rule.is_applicable_department("内科") is True
        assert rule.is_applicable_department("外科") is True
        assert rule.is_applicable_department("儿科") is False

    def test_is_applicable_department_empty_list(self):
        """测试空科室列表表示所有科室适用"""
        data = {
            "rule_id": "RULE_001",
            "rule_type": "ordered_but_not_recorded",
            "display_name": "开了没写",
            "description": "",
            "severity": "high",
            "required_his_fields": [],
            "required_emr_fields": [],
            "keyword_matching": {},
            "time_window": {},
            "applicable_departments": [],
        }

        rule = RuleDefinition.from_dict(data)

        assert rule.is_applicable_department("内科") is True
        assert rule.is_applicable_department("任意科室") is True

    def test_is_applicable_order_type(self):
        """测试医嘱类型适用性判断"""
        data = {
            "rule_id": "RULE_001",
            "rule_type": "ordered_but_not_recorded",
            "display_name": "开了没写",
            "description": "",
            "severity": "high",
            "required_his_fields": [],
            "required_emr_fields": [],
            "keyword_matching": {},
            "time_window": {},
            "applicable_order_types": ["检查", "检验"],
        }

        rule = RuleDefinition.from_dict(data)

        assert rule.is_applicable_order_type("检查") is True
        assert rule.is_applicable_order_type("药品") is False

    def test_is_applicable_record_type(self):
        """测试记录类型适用性判断"""
        data = {
            "rule_id": "RULE_001",
            "rule_type": "recorded_but_not_ordered",
            "display_name": "写了没开",
            "description": "",
            "severity": "medium",
            "required_his_fields": [],
            "required_emr_fields": [],
            "keyword_matching": {},
            "time_window": {},
            "applicable_record_types": ["首次病程", "日常病程"],
        }

        rule = RuleDefinition.from_dict(data)

        assert rule.is_applicable_record_type("首次病程") is True
        assert rule.is_applicable_record_type("手术记录") is False


class TestAlertThreshold:
    """AlertThreshold测试"""

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "name": "warning",
            "threshold": 3,
            "description": "中频告警",
        }
        threshold = AlertThreshold.from_dict(data)

        assert threshold.name == "warning"
        assert threshold.threshold == 3
        assert threshold.description == "中频告警"


class TestAlertConfig:
    """AlertConfig测试"""

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "doctor_daily_threshold": 5,
            "department_daily_threshold": 20,
            "high_severity_threshold": 2,
            "alert_levels": [
                {"name": "info", "threshold": 0, "description": ""},
                {"name": "warning", "threshold": 3, "description": ""},
                {"name": "error", "threshold": 5, "description": ""},
            ],
        }
        config = AlertConfig.from_dict(data)

        assert config.doctor_daily_threshold == 5
        assert config.department_daily_threshold == 20
        assert config.high_severity_threshold == 2
        assert len(config.alert_levels) == 3

    def test_get_alert_level(self):
        """测试获取告警级别"""
        data = {
            "alert_levels": [
                {"name": "info", "threshold": 0, "description": ""},
                {"name": "warning", "threshold": 3, "description": ""},
                {"name": "error", "threshold": 5, "description": ""},
                {"name": "critical", "threshold": 10, "description": ""},
            ],
        }
        config = AlertConfig.from_dict(data)

        assert config.get_alert_level(0) == "info"
        assert config.get_alert_level(2) == "info"  # 2 >= 0, but 2 < 3
        assert config.get_alert_level(3) == "warning"
        assert config.get_alert_level(5) == "error"
        assert config.get_alert_level(10) == "critical"
        assert config.get_alert_level(15) == "critical"


class TestSeverityDefinition:
    """SeverityDefinition测试"""

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "description": "核心医疗文书缺失",
            "examples": ["检查未记录", "药品未记录"],
            "action": "立即整改",
        }
        severity = SeverityDefinition.from_dict(data)

        assert severity.description == "核心医疗文书缺失"
        assert severity.examples == ["检查未记录", "药品未记录"]
        assert severity.action == "立即整改"


class TestSeverityConfig:
    """SeverityConfig测试"""

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "high": {
                "description": "高危",
                "examples": ["example1"],
                "action": "立即整改",
            },
            "medium": {
                "description": "中危",
                "examples": ["example2"],
                "action": "尽快处理",
            },
            "low": {
                "description": "低危",
                "examples": ["example3"],
                "action": "日常改进",
            },
        }
        config = SeverityConfig.from_dict(data)

        assert config.high.description == "高危"
        assert config.medium.description == "中危"
        assert config.low.description == "低危"


class TestRuleDefinitionsLoader:
    """RuleDefinitionsLoader测试"""

    def setup_method(self):
        """每个测试方法前创建临时规则文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.rules_file = os.path.join(self.temp_dir, "test_rules.yaml")

    def teardown_method(self):
        """每个测试方法后清理"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_rules_file(self, content: dict) -> str:
        """创建测试规则文件"""
        with open(self.rules_file, "w", encoding="utf-8") as f:
            yaml.dump(content, f, allow_unicode=True, default_flow_style=False)
        return self.rules_file

    def test_load_rules(self):
        """测试加载规则文件"""
        rules_content = {
            "version": "1.0",
            "rules": {
                "ordered_but_not_recorded": {
                    "rule_id": "RULE_001",
                    "rule_type": "ordered_but_not_recorded",
                    "display_name": "开了没写",
                    "description": "开了医嘱但没写记录",
                    "severity": "high",
                    "required_his_fields": ["order_id"],
                    "required_emr_fields": ["record_id"],
                    "keyword_matching": {},
                    "time_window": {"minutes": 120},
                },
                "recorded_but_not_ordered": {
                    "rule_id": "RULE_002",
                    "rule_type": "recorded_but_not_ordered",
                    "display_name": "写了没开",
                    "description": "写了记录但没开医嘱",
                    "severity": "medium",
                    "required_his_fields": ["order_id"],
                    "required_emr_fields": ["record_id"],
                    "keyword_matching": {},
                    "time_window": {"minutes": 120},
                },
            },
            "alert_thresholds": {
                "doctor_daily_threshold": 3,
                "department_daily_threshold": 10,
                "high_severity_threshold": 1,
                "alert_levels": [
                    {"name": "info", "threshold": 0, "description": ""}
                ],
            },
            "severity_thresholds": {
                "high": {"description": "", "examples": [], "action": ""},
                "medium": {"description": "", "examples": [], "action": ""},
                "low": {"description": "", "examples": [], "action": ""},
            },
        }
        self._create_test_rules_file(rules_content)

        loader = RuleDefinitionsLoader()
        loader.load(self.rules_file)

        assert loader.get_version() == "1.0"
        assert len(loader.get_all_rules()) == 2

        rule1 = loader.get_rule("ordered_but_not_recorded")
        assert rule1 is not None
        assert rule1.display_name == "开了没写"
        assert rule1.severity == "high"

        rule2 = loader.get_rule("recorded_but_not_ordered")
        assert rule2 is not None
        assert rule2.display_name == "写了没开"
        assert rule2.severity == "medium"

    def test_load_file_not_found(self):
        """测试文件不存在"""
        loader = RuleDefinitionsLoader()

        with pytest.raises(FileNotFoundError):
            loader.load("/nonexistent/path/rules.yaml")

    def test_load_empty_file(self):
        """测试空文件"""
        empty_file = os.path.join(self.temp_dir, "empty.yaml")
        with open(empty_file, "w", encoding="utf-8") as f:
            f.write("")

        loader = RuleDefinitionsLoader()

        with pytest.raises(ValueError, match="规则文件为空"):
            loader.load(empty_file)

    def test_get_alert_config(self):
        """测试获取告警配置"""
        rules_content = {
            "version": "1.0",
            "rules": {},
            "alert_thresholds": {
                "doctor_daily_threshold": 5,
                "department_daily_threshold": 15,
                "high_severity_threshold": 2,
                "alert_levels": [
                    {"name": "info", "threshold": 0, "description": ""}
                ],
            },
            "severity_thresholds": {
                "high": {"description": "", "examples": [], "action": ""},
                "medium": {"description": "", "examples": [], "action": ""},
                "low": {"description": "", "examples": [], "action": ""},
            },
        }
        self._create_test_rules_file(rules_content)

        loader = RuleDefinitionsLoader()
        loader.load(self.rules_file)

        alert_config = loader.get_alert_config()
        assert alert_config is not None
        assert alert_config.doctor_daily_threshold == 5
        assert alert_config.department_daily_threshold == 15

    def test_get_severity_config(self):
        """测试获取严重程度配置"""
        rules_content = {
            "version": "1.0",
            "rules": {},
            "alert_thresholds": {},
            "severity_thresholds": {
                "high": {
                    "description": "高危描述",
                    "examples": ["example1"],
                    "action": "立即整改",
                },
                "medium": {
                    "description": "中危描述",
                    "examples": ["example2"],
                    "action": "尽快处理",
                },
                "low": {
                    "description": "低危描述",
                    "examples": ["example3"],
                    "action": "日常改进",
                },
            },
        }
        self._create_test_rules_file(rules_content)

        loader = RuleDefinitionsLoader()
        loader.load(self.rules_file)

        severity_config = loader.get_severity_config()
        assert severity_config is not None
        assert severity_config.high.description == "高危描述"
        assert severity_config.medium.description == "中危描述"
        assert severity_config.low.description == "低危描述"

    def test_get_synonyms_for_item(self):
        """测试获取同义词"""
        rules_content = {
            "version": "1.0",
            "rules": {
                "ordered_but_not_recorded": {
                    "rule_id": "RULE_001",
                    "rule_type": "ordered_but_not_recorded",
                    "display_name": "开了没写",
                    "description": "",
                    "severity": "high",
                    "required_his_fields": [],
                    "required_emr_fields": [],
                    "keyword_matching": {
                        "synonyms": {
                            "B超": ["彩超", "超声检查"],
                            "血常规": ["血细胞分析"],
                        }
                    },
                    "time_window": {"minutes": 120},
                }
            },
            "alert_thresholds": {},
            "severity_thresholds": {
                "high": {"description": "", "examples": [], "action": ""},
                "medium": {"description": "", "examples": [], "action": ""},
                "low": {"description": "", "examples": [], "action": ""},
            },
        }
        self._create_test_rules_file(rules_content)

        loader = RuleDefinitionsLoader()
        loader.load(self.rules_file)

        synonyms = loader.get_synonyms_for_item("B超")
        assert "B超" in synonyms
        assert "彩超" in synonyms
        assert "超声检查" in synonyms

    def test_is_exclusion_keyword(self):
        """测试排除关键词检测"""
        rules_content = {
            "version": "1.0",
            "rules": {
                "ordered_but_not_recorded": {
                    "rule_id": "RULE_001",
                    "rule_type": "ordered_but_not_recorded",
                    "display_name": "开了没写",
                    "description": "",
                    "severity": "high",
                    "required_his_fields": [],
                    "required_emr_fields": [],
                    "keyword_matching": {
                        "exclusion_keywords": ["拒绝", "暂未", "预约"]
                    },
                    "time_window": {"minutes": 120},
                }
            },
            "alert_thresholds": {},
            "severity_thresholds": {
                "high": {"description": "", "examples": [], "action": ""},
                "medium": {"description": "", "examples": [], "action": ""},
                "low": {"description": "", "examples": [], "action": ""},
            },
        }
        self._create_test_rules_file(rules_content)

        loader = RuleDefinitionsLoader()
        loader.load(self.rules_file)

        assert loader.is_exclusion_keyword("患者拒绝检查") is True
        assert loader.is_exclusion_keyword("暂未执行") is True
        assert loader.is_exclusion_keyword("已预约明日检查") is True
        assert loader.is_exclusion_keyword("已完成检查") is False

    def test_get_time_window_minutes(self):
        """测试获取时间窗口分钟数"""
        rules_content = {
            "version": "1.0",
            "rules": {
                "ordered_but_not_recorded": {
                    "rule_id": "RULE_001",
                    "rule_type": "ordered_but_not_recorded",
                    "display_name": "开了没写",
                    "description": "",
                    "severity": "high",
                    "required_his_fields": [],
                    "required_emr_fields": [],
                    "keyword_matching": {},
                    "time_window": {"minutes": 60},
                },
                "recorded_but_not_ordered": {
                    "rule_id": "RULE_002",
                    "rule_type": "recorded_but_not_ordered",
                    "display_name": "写了没开",
                    "description": "",
                    "severity": "medium",
                    "required_his_fields": [],
                    "required_emr_fields": [],
                    "keyword_matching": {},
                    "time_window": {"minutes": 180},
                },
            },
            "alert_thresholds": {},
            "severity_thresholds": {
                "high": {"description": "", "examples": [], "action": ""},
                "medium": {"description": "", "examples": [], "action": ""},
                "low": {"description": "", "examples": [], "action": ""},
            },
        }
        self._create_test_rules_file(rules_content)

        loader = RuleDefinitionsLoader()
        loader.load(self.rules_file)

        assert loader.get_time_window_minutes("ordered_but_not_recorded") == 60
        assert loader.get_time_window_minutes("recorded_but_not_ordered") == 180
        # 不存在的规则类型返回默认值
        assert loader.get_time_window_minutes("nonexistent") == 120

    def test_get_rule_types(self):
        """测试获取所有规则类型"""
        rules_content = {
            "version": "1.0",
            "rules": {
                "ordered_but_not_recorded": {
                    "rule_id": "RULE_001",
                    "rule_type": "ordered_but_not_recorded",
                    "display_name": "开了没写",
                    "description": "",
                    "severity": "high",
                    "required_his_fields": [],
                    "required_emr_fields": [],
                    "keyword_matching": {},
                    "time_window": {"minutes": 120},
                },
                "recorded_but_not_ordered": {
                    "rule_id": "RULE_002",
                    "rule_type": "recorded_but_not_ordered",
                    "display_name": "写了没开",
                    "description": "",
                    "severity": "medium",
                    "required_his_fields": [],
                    "required_emr_fields": [],
                    "keyword_matching": {},
                    "time_window": {"minutes": 120},
                },
            },
            "alert_thresholds": {},
            "severity_thresholds": {
                "high": {"description": "", "examples": [], "action": ""},
                "medium": {"description": "", "examples": [], "action": ""},
                "low": {"description": "", "examples": [], "action": ""},
            },
        }
        self._create_test_rules_file(rules_content)

        loader = RuleDefinitionsLoader()
        loader.load(self.rules_file)

        rule_types = loader.get_rule_types()
        assert "ordered_but_not_recorded" in rule_types
        assert "recorded_but_not_ordered" in rule_types
        assert len(rule_types) == 2
