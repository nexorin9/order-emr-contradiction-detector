"""
CLI 单元测试

测试 Python CLI 命令行工具的各个子命令。
"""

import argparse
import json
import os
import sys
import tempfile
import pytest
from pathlib import Path
from datetime import datetime
from io import StringIO

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.py.cli import cmd_detect, cmd_stats, cmd_alert_config
from src.py.data.his_adapter import HisOrder
from src.py.data.emr_adapter import EmrRecord
from src.py.data.merged_loader import PatientVisit
from src.py.engine.contradiction_engine import Contradiction


class MockArgs:
    """模拟命令行参数对象"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCliDetect:
    """测试 detect 命令"""

    def test_detect_missing_his_file(self, tmp_path):
        """测试 HIS 文件不存在的情况"""
        args = MockArgs(
            his=str(tmp_path / "nonexistent.csv"),
            emr=str(tmp_path / "emr.csv"),
            output=str(tmp_path / "output"),
            rules=None,
            time_window=30,
        )

        # 创建一个假的 EMR 文件以避免 EMR 文件不存在错误
        emr_file = tmp_path / "emr.csv"
        emr_file.write_text("record_id,patient_id,doctor_id,department,record_type,content_keywords,create_time\n")

        result = cmd_detect(args)
        assert result == 1

    def test_detect_missing_emr_file(self, tmp_path):
        """测试 EMR 文件不存在的情况"""
        his_file = tmp_path / "his.csv"
        his_file.write_text("order_id,patient_id,doctor_id,department,order_type,item_name,create_time,execute_time,status\n")

        args = MockArgs(
            his=str(his_file),
            emr=str(tmp_path / "nonexistent.csv"),
            output=str(tmp_path / "output"),
            rules=None,
            time_window=30,
        )

        result = cmd_detect(args)
        assert result == 1

    def test_detect_empty_data(self, tmp_path):
        """测试空数据文件"""
        his_file = tmp_path / "his.csv"
        his_file.write_text("order_id,patient_id,doctor_id,department,order_type,item_name,create_time,execute_time,status\n", encoding="utf-8")

        emr_file = tmp_path / "emr.csv"
        emr_file.write_text("record_id,patient_id,doctor_id,department,record_type,content_keywords,create_time\n", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        args = MockArgs(
            his=str(his_file),
            emr=str(emr_file),
            output=str(output_dir),
            rules=None,
            time_window=30,
        )

        result = cmd_detect(args)
        # 空数据会抛出EmptyDataError，CLI返回1表示错误
        assert result == 1

    def test_detect_with_valid_data(self, tmp_path):
        """测试有效数据的矛盾检测"""
        # 创建 HIS 数据
        his_file = tmp_path / "his.csv"
        his_file.write_text(
            "order_id,patient_id,doctor_id,department,order_type,item_name,create_time,execute_time,status\n"
            "ORD001,P001,D001,内科,B超,腹部B超,2024-01-01 10:00:00,2024-01-01 10:30:00,执行中\n",
            encoding="utf-8"
        )

        # 创建 EMR 数据（不同步，会产生矛盾）
        emr_file = tmp_path / "emr.csv"
        emr_file.write_text(
            "record_id,patient_id,doctor_id,department,record_type,content_keywords,create_time\n"
            "REC001,P001,D001,内科,病程记录,X光,2024-01-01 10:00:00\n",
            encoding="utf-8"
        )

        output_dir = tmp_path / "output"

        args = MockArgs(
            his=str(his_file),
            emr=str(emr_file),
            output=str(output_dir),
            rules=None,
            time_window=30,
        )

        result = cmd_detect(args)
        assert result == 0

        # 验证输出文件
        result_files = list(output_dir.glob("contradictions_*.json"))
        assert len(result_files) == 1

        stats_files = list(output_dir.glob("stats_*.json"))
        assert len(stats_files) == 1


class TestCliStats:
    """测试 stats 命令"""

    def test_stats_missing_directory(self, tmp_path):
        """测试目录不存在"""
        nonexistent_dir = tmp_path / "nonexistent"
        args = MockArgs(
            input=str(nonexistent_dir),
            format="csv",
        )

        result = cmd_stats(args)
        assert result == 1

    def test_stats_no_result_files(self, tmp_path):
        """测试目录中没有结果文件"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        args = MockArgs(
            input=str(empty_dir),
            format="csv",
        )

        result = cmd_stats(args)
        assert result == 1

    def test_stats_with_valid_data(self, tmp_path):
        """测试有效数据的统计"""
        # 创建模拟的矛盾结果文件
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result_file = output_dir / "contradictions_20240101_120000.json"
        result_data = {
            "generated_at": datetime.now().isoformat(),
            "total_count": 5,
            "contradictions": [
                {
                    "patient_id": "P001",
                    "doctor_id": "D001",
                    "department": "内科",
                    "rule_type": "ordered_but_not_recorded",
                    "severity": "high",
                    "order_id": "ORD001",
                    "record_id": "",
                    "order_item_name": "B超",
                    "record_keywords": [],
                    "create_time": "2024-01-01T10:00:00",
                    "description": "测试矛盾",
                    "matched_keywords": [],
                    "time_window_minutes": 30,
                },
                {
                    "patient_id": "P002",
                    "doctor_id": "D001",
                    "department": "内科",
                    "rule_type": "recorded_but_not_ordered",
                    "severity": "medium",
                    "order_id": "",
                    "record_id": "REC001",
                    "order_item_name": "",
                    "record_keywords": ["X光"],
                    "create_time": "2024-01-01T10:00:00",
                    "description": "测试矛盾2",
                    "matched_keywords": [],
                    "time_window_minutes": 30,
                },
            ],
        }

        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        # 测试 CSV 格式
        args_csv = MockArgs(
            input=str(output_dir),
            format="csv",
        )

        result = cmd_stats(args_csv)
        assert result == 0

        # 测试 JSON 格式
        args_json = MockArgs(
            input=str(output_dir),
            format="json",
        )

        result = cmd_stats(args_json)
        assert result == 0


class TestCliAlertConfig:
    """测试 alert-config 命令"""

    def test_alert_config_show(self):
        """测试显示告警配置"""
        args = MockArgs(
            show=True,
            set_threshold=None,
        )

        result = cmd_alert_config(args)
        assert result == 0

    def test_alert_config_set_threshold_invalid(self):
        """测试设置无效阈值"""
        args = MockArgs(
            show=False,
            set_threshold="invalid",
        )

        result = cmd_alert_config(args)
        assert result == 1

    def test_alert_config_set_threshold_valid(self):
        """测试设置有效阈值（只是提示，不实际修改）"""
        args = MockArgs(
            show=False,
            set_threshold="10",
        )

        result = cmd_alert_config(args)
        assert result == 0


class TestCliIntegration:
    """CLI 集成测试"""

    def test_detect_and_stats_workflow(self, tmp_path):
        """测试完整检测和统计流程"""
        # 创建测试数据
        his_file = tmp_path / "his.csv"
        his_file.write_text(
            "order_id,patient_id,doctor_id,department,order_type,item_name,create_time,execute_time,status\n"
            "ORD001,P001,D001,内科,检查,B超,2024-01-01 10:00:00,2024-01-01 10:30:00,执行中\n"
            "ORD002,P001,D001,内科,药品,阿莫西林,2024-01-01 11:00:00,2024-01-01 11:30:00,执行中\n",
            encoding="utf-8"
        )

        emr_file = tmp_path / "emr.csv"
        emr_file.write_text(
            "record_id,patient_id,doctor_id,department,record_type,content_keywords,create_time\n"
            "REC001,P001,D001,内科,病程记录,血常规,2024-01-01 10:30:00\n",
            encoding="utf-8"
        )

        output_dir = tmp_path / "output"

        # 执行检测
        detect_args = MockArgs(
            his=str(his_file),
            emr=str(emr_file),
            output=str(output_dir),
            rules=None,
            time_window=30,
        )

        detect_result = cmd_detect(detect_args)
        assert detect_result == 0

        # 验证输出文件
        result_files = list(output_dir.glob("contradictions_*.json"))
        assert len(result_files) == 1

        stats_files = list(output_dir.glob("stats_*.json"))
        assert len(stats_files) == 1

        # 读取统计文件
        with open(stats_files[0], "r", encoding="utf-8") as f:
            stats_data = json.load(f)

        # 验证统计数据结构
        assert "total" in stats_data
        assert "by_severity" in stats_data
        assert "by_rule_type" in stats_data
        assert "by_department" in stats_data
        assert "by_doctor" in stats_data

        # 执行统计命令
        stats_args = MockArgs(
            input=str(output_dir),
            format="csv",
        )

        stats_result = cmd_stats(stats_args)
        assert stats_result == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])