"""
告警规则引擎模块

核心功能：
1. 基于矛盾检测结果和配置规则生成告警事件
2. 按医生/科室维度统计矛盾数
3. 支持Webhook推送和文件输出两种模式
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

from .contradiction_engine import Contradiction

logger = logging.getLogger(__name__)


@dataclass
class AlertSummary:
    """告警汇总数据模型"""

    doctor_id: str  # 医生ID
    department: str  # 科室
    contradiction_count: int  # 矛盾总数
    high_severity_count: int  # 高危矛盾数
    medium_severity_count: int = 0  # 中危矛盾数
    low_severity_count: int = 0  # 低危矛盾数
    alert_level: str = "info"  # 告警级别：info/warning/error/critical
    doctor_name: str = ""  # 医生姓名（可选）
    triggered_rules: List[str] = field(default_factory=list)  # 触发的规则类型列表
    details: List[Dict[str, Any]] = field(default_factory=list)  # 矛盾详情列表
    generated_at: datetime = field(default_factory=datetime.now)  # 生成时间
    detection_date: str = ""  # 检测日期（YYYY-MM-DD格式）

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor_name,
            "department": self.department,
            "contradiction_count": self.contradiction_count,
            "high_severity_count": self.high_severity_count,
            "medium_severity_count": self.medium_severity_count,
            "low_severity_count": self.low_severity_count,
            "alert_level": self.alert_level,
            "triggered_rules": self.triggered_rules,
            "details": self.details,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "detection_date": self.detection_date,
        }

    def to_summary_dict(self) -> dict:
        """转换为简化摘要格式（不含详情）"""
        return {
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor_name,
            "department": self.department,
            "contradiction_count": self.contradiction_count,
            "high_severity_count": self.high_severity_count,
            "medium_severity_count": self.medium_severity_count,
            "low_severity_count": self.low_severity_count,
            "alert_level": self.alert_level,
            "triggered_rules": self.triggered_rules,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "detection_date": self.detection_date,
        }


@dataclass
class AlertConfig:
    """告警配置数据模型"""

    enabled: bool = True  # 是否启用告警
    doctor_daily_threshold: int = 3  # 单个医生每日矛盾数阈值
    department_daily_threshold: int = 10  # 单个科室每日矛盾数阈值
    high_severity_threshold: int = 1  # 高危矛盾数阈值
    alert_levels: Dict[str, int] = field(default_factory=lambda: {
        "info": 0,
        "warning": 1,
        "error": 3,
        "critical": 5,
    })
    webhook_url: str = ""  # Webhook推送URL
    webhook_enabled: bool = False  # 是否启用Webhook
    webhook_headers: Dict[str, str] = field(default_factory=lambda: {
        "Content-Type": "application/json"
    })
    file_output_enabled: bool = True  # 是否启用文件输出
    output_dir: str = "data/output/alerts"  # 输出目录

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "AlertConfig":
        """从字典创建配置对象"""
        return cls(
            enabled=config.get("enabled", True),
            doctor_daily_threshold=config.get("doctor_daily_threshold", 3),
            department_daily_threshold=config.get("department_daily_threshold", 10),
            high_severity_threshold=config.get("high_severity_threshold", 1),
            alert_levels=config.get("alert_levels", {
                "info": 0,
                "warning": 1,
                "error": 3,
                "critical": 5,
            }),
            webhook_url=config.get("webhook_url", ""),
            webhook_enabled=config.get("webhook_enabled", False),
            webhook_headers=config.get("webhook_headers", {"Content-Type": "application/json"}),
            file_output_enabled=config.get("file_output_enabled", True),
            output_dir=config.get("output_dir", "data/output/alerts"),
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "AlertConfig":
        """从YAML文件加载配置"""
        if not os.path.exists(yaml_path):
            logger.warning(f"配置文件不存在: {yaml_path}，使用默认配置")
            return cls()

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            alerting_config = config_data.get("alerting", {})
            return cls(
                enabled=alerting_config.get("enabled", True),
                doctor_daily_threshold=alerting_config.get("threshold", 3),
                high_severity_threshold=alerting_config.get("severity_threshold", {}).get("high_severity", 1),
                webhook_url=alerting_config.get("webhook_url", ""),
                webhook_enabled=alerting_config.get("webhook_enabled", False),
                output_dir=alerting_config.get("output_dir", "data/output/alerts"),
            )
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return cls()


class AlertEngine:
    """告警规则引擎

    核心功能：
    1. 基于矛盾检测结果生成告警汇总
    2. 按医生/科室维度统计矛盾数
    3. 判断告警级别
    4. 支持Webhook推送和文件输出
    """

    # 告警级别常量
    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_ERROR = "error"
    LEVEL_CRITICAL = "critical"

    def __init__(self, config: Optional[AlertConfig] = None):
        """初始化告警引擎

        Args:
            config: 告警配置对象，若为None则使用默认配置
        """
        self.config = config or AlertConfig()
        self._webhook_client = None

    def generate_alerts(
        self,
        contradictions: List[Contradiction],
        detection_date: Optional[str] = None,
    ) -> List[AlertSummary]:
        """生成告警汇总列表

        Args:
            contradictions: 矛盾检测结果列表
            detection_date: 检测日期（YYYY-MM-DD格式），若为None则使用当前日期

        Returns:
            AlertSummary列表
        """
        if not contradictions:
            logger.info("无矛盾记录，不生成告警")
            return []

        if detection_date is None:
            detection_date = datetime.now().strftime("%Y-%m-%d")

        # 按医生维度生成告警
        doctor_alerts = self._generate_doctor_alerts(contradictions, detection_date)

        # 按科室维度生成告警
        department_alerts = self._generate_department_alerts(contradictions, detection_date)

        # 合并告警列表
        all_alerts = doctor_alerts + department_alerts

        logger.info(f"共生成 {len(all_alerts)} 条告警汇总")
        return all_alerts

    def _generate_doctor_alerts(
        self,
        contradictions: List[Contradiction],
        detection_date: str,
    ) -> List[AlertSummary]:
        """按医生维度生成告警

        Args:
            contradictions: 矛盾检测结果列表
            detection_date: 检测日期

        Returns:
            AlertSummary列表
        """
        # 按医生分组
        by_doctor: Dict[str, List[Contradiction]] = {}
        for c in contradictions:
            if c.doctor_id not in by_doctor:
                by_doctor[c.doctor_id] = []
            by_doctor[c.doctor_id].append(c)

        alerts: List[AlertSummary] = []

        for doctor_id, doctor_contradictions in by_doctor.items():
            # 统计各级别矛盾数
            high_count = sum(1 for c in doctor_contradictions if c.severity == "high")
            medium_count = sum(1 for c in doctor_contradictions if c.severity == "medium")
            low_count = sum(1 for c in doctor_contradictions if c.severity == "low")

            # 触发规则列表
            triggered_rules = list(set(c.rule_type for c in doctor_contradictions))

            # 判断告警级别
            alert_level = self._determine_alert_level(
                total_count=len(doctor_contradictions),
                high_count=high_count,
            )

            # 如果告警级别为info且无高危矛盾，且矛盾数未超过阈值，则跳过
            if alert_level == self.LEVEL_INFO and high_count == 0:
                if len(doctor_contradictions) < self.config.doctor_daily_threshold:
                    continue

            # 获取科室（取第一条矛盾的科室）
            department = doctor_contradictions[0].department if doctor_contradictions else ""

            # 构建详情列表
            details = [self._contradiction_to_detail(c) for c in doctor_contradictions]

            alert = AlertSummary(
                doctor_id=doctor_id,
                doctor_name="",  # 医生姓名需从外部系统获取
                department=department,
                contradiction_count=len(doctor_contradictions),
                high_severity_count=high_count,
                medium_severity_count=medium_count,
                low_severity_count=low_count,
                alert_level=alert_level,
                triggered_rules=triggered_rules,
                details=details,
                detection_date=detection_date,
            )
            alerts.append(alert)

        return alerts

    def _generate_department_alerts(
        self,
        contradictions: List[Contradiction],
        detection_date: str,
    ) -> List[AlertSummary]:
        """按科室维度生成告警

        Args:
            contradictions: 矛盾检测结果列表
            detection_date: 检测日期

        Returns:
            AlertSummary列表
        """
        # 按科室分组
        by_department: Dict[str, List[Contradiction]] = {}
        for c in contradictions:
            if c.department not in by_department:
                by_department[c.department] = []
            by_department[c.department].append(c)

        alerts: List[AlertSummary] = []

        for department, dept_contradictions in by_department.items():
            # 统计各级别矛盾数
            high_count = sum(1 for c in dept_contradictions if c.severity == "high")
            medium_count = sum(1 for c in dept_contradictions if c.severity == "medium")
            low_count = sum(1 for c in dept_contradictions if c.severity == "low")

            # 触发规则列表
            triggered_rules = list(set(c.rule_type for c in dept_contradictions))

            # 判断告警级别
            alert_level = self._determine_alert_level(
                total_count=len(dept_contradictions),
                high_count=high_count,
            )

            # 如果告警级别为info，跳过（科室维度仅关注warning及以上）
            if alert_level == self.LEVEL_INFO:
                continue

            # 构建详情列表（按医生分组）
            details = []
            by_doctor: Dict[str, List[Contradiction]] = {}
            for c in dept_contradictions:
                if c.doctor_id not in by_doctor:
                    by_doctor[c.doctor_id] = []
                by_doctor[c.doctor_id].append(c)

            for doc_id, doc_contras in by_doctor.items():
                details.append({
                    "doctor_id": doc_id,
                    "doctor_name": "",
                    "contradiction_count": len(doc_contras),
                    "high_severity_count": sum(1 for c in doc_contras if c.severity == "high"),
                    "medium_severity_count": sum(1 for c in doc_contras if c.severity == "medium"),
                    "low_severity_count": sum(1 for c in doc_contras if c.severity == "low"),
                })

            alert = AlertSummary(
                doctor_id="DEPT_ALL",  # 科室汇总的标识
                doctor_name="",
                department=department,
                contradiction_count=len(dept_contradictions),
                high_severity_count=high_count,
                medium_severity_count=medium_count,
                low_severity_count=low_count,
                alert_level=alert_level,
                triggered_rules=triggered_rules,
                details=details,
                detection_date=detection_date,
            )
            alerts.append(alert)

        return alerts

    def _determine_alert_level(
        self,
        total_count: int,
        high_count: int,
    ) -> str:
        """判断告警级别

        告警级别判断逻辑：
        1. 高危矛盾数 >= high_severity_threshold 时，直接触发critical
        2. 否则根据总矛盾数判断

        Args:
            total_count: 矛盾总数
            high_count: 高危矛盾数

        Returns:
            告警级别：info/warning/error/critical
        """
        # 高危矛盾数达到或超过阈值，直接critical
        if high_count >= self.config.high_severity_threshold:
            return self.LEVEL_CRITICAL

        # 根据总矛盾数判断级别
        thresholds = self.config.alert_levels

        if total_count >= thresholds.get(self.LEVEL_CRITICAL, 5):
            return self.LEVEL_CRITICAL
        elif total_count >= thresholds.get(self.LEVEL_ERROR, 3):
            return self.LEVEL_ERROR
        elif total_count >= thresholds.get(self.LEVEL_WARNING, 1):
            return self.LEVEL_WARNING
        else:
            return self.LEVEL_INFO

    def _contradiction_to_detail(self, c: Contradiction) -> Dict[str, Any]:
        """将矛盾对象转换为详情字典"""
        return {
            "patient_id": c.patient_id,
            "rule_type": c.rule_type,
            "order_id": c.order_id,
            "record_id": c.record_id,
            "order_item_name": c.order_item_name,
            "record_keywords": c.record_keywords,
            "severity": c.severity,
            "create_time": c.create_time.isoformat() if c.create_time else None,
            "description": c.description,
        }

    def process_alerts(
        self,
        alerts: List[AlertSummary],
        push_webhook: bool = True,
        write_file: bool = True,
    ) -> Dict[str, Any]:
        """处理告警：推送Webhook和/或写入文件

        Args:
            alerts: 告警汇总列表
            push_webhook: 是否推送Webhook
            write_file: 是否写入文件

        Returns:
            处理结果字典
        """
        results = {
            "total_alerts": len(alerts),
            "webhook_push_success": False,
            "file_write_success": False,
            "webhook_count": 0,
            "file_count": 0,
        }

        if not self.config.enabled:
            logger.info("告警功能已禁用，跳过处理")
            return results

        # 过滤出需要处理的告警（warning及以上）
        actionable_alerts = [a for a in alerts if a.alert_level != self.LEVEL_INFO]

        if not actionable_alerts:
            logger.info("无需要处理的告警（均为info级别）")
            return results

        # 推送Webhook
        if push_webhook and self.config.webhook_enabled and self.config.webhook_url:
            success = self._push_webhook(actionable_alerts)
            results["webhook_push_success"] = success
            results["webhook_count"] = len(actionable_alerts) if success else 0

        # 写入文件
        if write_file and self.config.file_output_enabled:
            success, count = self._write_alerts_to_file(actionable_alerts)
            results["file_write_success"] = success
            results["file_count"] = count

        return results

    def _push_webhook(self, alerts: List[AlertSummary]) -> bool:
        """推送Webhook告警

        Args:
            alerts: 告警汇总列表

        Returns:
            是否推送成功
        """
        if not self.config.webhook_url:
            logger.warning("Webhook URL未配置，跳过推送")
            return False

        try:
            import urllib.request
            import urllib.error

            payload = {
                "alert_count": len(alerts),
                "alerts": [a.to_dict() for a in alerts],
                "generated_at": datetime.now().isoformat(),
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.config.webhook_url,
                data=data,
                headers=self.config.webhook_headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Webhook推送成功，推送 {len(alerts)} 条告警")
                    return True
                else:
                    logger.warning(f"Webhook推送失败，状态码: {response.status}")
                    return False

        except urllib.error.URLError as e:
            logger.error(f"Webhook推送失败（URL错误）: {e}")
            return False
        except Exception as e:
            logger.error(f"Webhook推送失败: {e}")
            return False

    def _write_alerts_to_file(
        self,
        alerts: List[AlertSummary],
    ) -> tuple:
        """将告警写入文件

        Args:
            alerts: 告警汇总列表

        Returns:
            (是否成功, 写入文件数)
        """
        if not alerts:
            return True, 0

        try:
            # 确保输出目录存在
            os.makedirs(self.config.output_dir, exist_ok=True)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"alerts_{timestamp}.json"
            filepath = os.path.join(self.config.output_dir, filename)

            # 写入JSON文件
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "generated_at": datetime.now().isoformat(),
                        "alert_count": len(alerts),
                        "alerts": [a.to_dict() for a in alerts],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            logger.info(f"告警已写入文件: {filepath}")
            return True, len(alerts)

        except Exception as e:
            logger.error(f"告警文件写入失败: {e}")
            return False, 0

    def get_config(self) -> AlertConfig:
        """获取当前告警配置"""
        return self.config

    def update_config(self, config: AlertConfig) -> None:
        """更新告警配置

        Args:
            config: 新的告警配置
        """
        self.config = config
        logger.info("告警配置已更新")


def generate_alerts(
    contradictions: List[Contradiction],
    config: Optional[AlertConfig] = None,
    push_webhook: bool = True,
    write_file: bool = True,
    config_path: Optional[str] = None,
) -> List[AlertSummary]:
    """生成并处理告警的便捷函数

    Args:
        contradictions: 矛盾检测结果列表
        config: 告警配置对象（若为None且提供了config_path，则从文件加载）
        push_webhook: 是否推送Webhook
        write_file: 是否写入文件
        config_path: 配置文件路径

    Returns:
        AlertSummary列表
    """
    # 加载配置
    if config is None and config_path:
        config = AlertConfig.from_yaml(config_path)

    # 创建告警引擎
    engine = AlertEngine(config=config)

    # 生成告警
    alerts = engine.generate_alerts(contradictions)

    # 处理告警
    if alerts:
        engine.process_alerts(alerts, push_webhook=push_webhook, write_file=write_file)

    return alerts