"""
矛盾检测执行引擎模块

核心功能：
1. 检测 ordered_but_not_recorded（开了没写）：HIS有医嘱但EMR无对应记录
2. 检测 recorded_but_not_ordered（写了没开）：EMR有记录但HIS无对应医嘱
3. 严重程度分级：高/中/低
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..data.his_adapter import HisOrder
from ..data.emr_adapter import EmrRecord
from ..data.merged_loader import PatientVisit
from ..rules.rule_definitions import RuleDefinitionsLoader, RuleDefinition
from .time_aligner import TimeAligner, AlignedOrderRecord

logger = logging.getLogger(__name__)


@dataclass
class Contradiction:
    """矛盾检测结果数据模型"""

    patient_id: str  # 患者ID
    doctor_id: str  # 医生ID
    department: str  # 科室
    rule_type: str  # 矛盾类型：ordered_but_not_recorded / recorded_but_not_ordered
    order_id: str  # 关联的HIS医嘱ID（若为写了没开类型则为空）
    record_id: str  # 关联的EMR记录ID（若为开了没写类型则为空）
    order_item_name: str  # 医嘱项目名称
    record_keywords: List[str] = field(default_factory=list)  # EMR记录关键词
    create_time: datetime = None  # 矛盾产生时间（取医嘱或记录的创建时间）
    severity: str = "medium"  # 严重程度：高(high)/中(medium)/低(low)
    description: str = ""  # 矛盾描述
    matched_keywords: List[str] = field(default_factory=list)  # 匹配到的关键词（用于诊断）
    time_window_minutes: int = 0  # 检测时使用的时间窗口

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "department": self.department,
            "rule_type": self.rule_type,
            "order_id": self.order_id,
            "record_id": self.record_id,
            "order_item_name": self.order_item_name,
            "record_keywords": self.record_keywords,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "severity": self.severity,
            "description": self.description,
            "matched_keywords": self.matched_keywords,
            "time_window_minutes": self.time_window_minutes,
        }


class ContradictionDetector:
    """矛盾检测执行器

    核心功能：
    1. 加载规则定义
    2. 使用时间对齐引擎对齐HIS医嘱和EMR记录
    3. 执行矛盾检测（开了没写、写了没开）
    4. 严重程度分级
    """

    # 严重程度常量
    SEVERITY_HIGH = "high"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_LOW = "low"

    def __init__(
        self,
        rules_loader: Optional[RuleDefinitionsLoader] = None,
        time_window_minutes: int = 120,
    ):
        """初始化矛盾检测器

        Args:
            rules_loader: 规则定义加载器，若为None则使用默认配置
            time_window_minutes: 默认时间窗口（分钟）
        """
        self.rules_loader = rules_loader
        self.time_window_minutes = time_window_minutes
        self.time_aligner = TimeAligner(
            time_window_minutes=time_window_minutes,
            rules_loader=rules_loader,
        )

    def detect(
        self,
        patient_visits: List[PatientVisit],
        rules_file_path: Optional[str] = None,
    ) -> List[Contradiction]:
        """执行矛盾检测

        对每个患者就诊记录执行矛盾检测：
        1. ordered_but_not_recorded：开了没写（HIS有医嘱，EMR无对应记录）
        2. recorded_but_not_ordered：写了没开（EMR有记录，HIS无对应医嘱）

        Args:
            patient_visits: 患者就诊记录列表
            rules_file_path: 规则文件路径（仅当rules_loader为None时使用）

        Returns:
            Contradiction列表
        """
        # 加载规则（如果提供了规则文件路径）
        if rules_file_path and not self.rules_loader:
            self.rules_loader = RuleDefinitionsLoader(rules_file_path)
            self.rules_loader.load()
            # 重建时间对齐器（使用加载的规则）
            self.time_aligner = TimeAligner(
                time_window_minutes=self.time_window_minutes,
                rules_loader=self.rules_loader,
            )

        contradictions: List[Contradiction] = []

        for visit in patient_visits:
            # 检测 ordered_but_not_recorded（开了没写）
            ordered_not_recorded = self._detect_ordered_but_not_recorded(visit)
            contradictions.extend(ordered_not_recorded)

            # 检测 recorded_but_not_ordered（写了没开）
            recorded_not_ordered = self._detect_recorded_but_not_ordered(visit)
            contradictions.extend(recorded_not_ordered)

        logger.info(f"检测完成，共发现 {len(contradictions)} 条矛盾记录")
        return contradictions

    def _detect_ordered_but_not_recorded(
        self, visit: PatientVisit
    ) -> List[Contradiction]:
        """检测开了没写类矛盾

        对每条HIS医嘱，检查在时间窗口内是否有对应的EMR记录。

        Args:
            visit: 患者就诊记录

        Returns:
            Contradiction列表
        """
        contradictions: List[Contradiction] = []

        if not visit.orders:
            return contradictions

        # 使用时间对齐引擎对齐医嘱和记录
        aligned_results = self.time_aligner.align(
            orders=visit.orders,
            records=visit.records,
            rule_type="ordered_but_not_recorded",
        )

        # 获取规则定义（用于获取严重程度配置）
        rule_def = self._get_rule_definition("ordered_but_not_recorded")

        for result in aligned_results:
            if not result.matched:
                # 医嘱未匹配到病程记录，产生矛盾
                severity = self._determine_severity(
                    rule_type="ordered_but_not_recorded",
                    order=result.order,
                    rule_def=rule_def,
                )

                # 获取时间窗口配置
                time_window = self.time_window_minutes
                if self.rules_loader and rule_def:
                    time_window = rule_def.time_window.minutes

                contradiction = Contradiction(
                    patient_id=visit.patient_id,
                    doctor_id=result.order.doctor_id,
                    department=result.order.department,
                    rule_type="ordered_but_not_recorded",
                    order_id=result.order.order_id,
                    record_id="",
                    order_item_name=result.order.item_name,
                    record_keywords=[],
                    create_time=result.order.create_time,
                    severity=severity,
                    description=f"医嘱项目「{result.order.item_name}」在{time_window}分钟时间窗口内未找到对应病程记录",
                    matched_keywords=result.matched_keywords,
                    time_window_minutes=time_window,
                )
                contradictions.append(contradiction)

        return contradictions

    def _detect_recorded_but_not_ordered(
        self, visit: PatientVisit
    ) -> List[Contradiction]:
        """检测写了没开类矛盾

        对每条EMR记录，检查是否有对应的HIS医嘱。
        关键：记录中提到的关键词在医嘱中找不到对应项目。

        Args:
            visit: 患者就诊记录

        Returns:
            Contradiction列表
        """
        contradictions: List[Contradiction] = []

        if not visit.records:
            return contradictions

        # 获取规则定义
        rule_def = self._get_rule_definition("recorded_but_not_ordered")

        # 获取时间窗口配置
        time_window = self.time_window_minutes
        if self.rules_loader and rule_def:
            time_window = rule_def.time_window.minutes

        for record in visit.records:
            # 检查这条记录中的每个关键词，是否在任何医嘱中找到匹配
            record_has_order = False

            for order in visit.orders:
                # 检查关键词是否匹配（模糊匹配）
                matched_keywords = self._check_keywords_match(
                    record.content_keywords, order.item_name
                )
                if matched_keywords:
                    record_has_order = True
                    break

            # 如果记录中的关键词在所有医嘱中都找不到匹配，则为"写了没开"
            if not record_has_order and record.content_keywords:
                # 获取记录的关键词（用于描述）
                record_keywords = record.content_keywords

                # 查找匹配的关键词
                all_matched = []
                for order in visit.orders:
                    matched = self._check_keywords_match(
                        record_keywords, order.item_name
                    )
                    all_matched.extend(matched)

                severity = self._determine_severity_for_record(
                    rule_type="recorded_but_not_ordered",
                    record_keywords=record_keywords,
                    rule_def=rule_def,
                )

                contradiction = Contradiction(
                    patient_id=record.patient_id,
                    doctor_id=record.doctor_id,
                    department=record.department,
                    rule_type="recorded_but_not_ordered",
                    order_id="",
                    record_id=record.record_id,
                    order_item_name="",
                    record_keywords=record_keywords,
                    create_time=record.create_time,
                    severity=severity,
                    description=f"病程记录提及了「{'、'.join(record_keywords)}」，但在{time_window}分钟时间窗口内未找到对应医嘱",
                    matched_keywords=list(set(all_matched)),
                    time_window_minutes=time_window,
                )
                contradictions.append(contradiction)

        return contradictions

    def _check_keywords_match(
        self, record_keywords: List[str], order_item_name: str
    ) -> List[str]:
        """检查记录关键词是否与医嘱项目名称匹配

        Args:
            record_keywords: 病程记录中的关键词列表
            order_item_name: 医嘱项目名称

        Returns:
            匹配到的关键词列表
        """
        matched = []
        for kw in record_keywords:
            # 精确匹配
            if kw == order_item_name:
                matched.append(kw)
            # 部分匹配（关键词在项目名中，或项目名在关键词中）
            elif kw in order_item_name or order_item_name in kw:
                matched.append(kw)
            # 模糊匹配（同义词支持）
            elif self.rules_loader:
                synonyms = self.rules_loader.get_synonyms_for_item(order_item_name)
                if any(syn in kw or kw in syn for syn in synonyms):
                    matched.append(kw)

        return matched

    def _get_rule_definition(
        self, rule_type: str
    ) -> Optional[RuleDefinition]:
        """获取规则定义"""
        if self.rules_loader:
            return self.rules_loader.get_rule(rule_type)
        return None

    def _determine_severity(
        self,
        rule_type: str,
        order: HisOrder,
        rule_def: Optional[RuleDefinition],
    ) -> str:
        """确定矛盾严重程度（针对开了没写类型）

        严重程度判断逻辑：
        1. 高危(High)：检查/检验类医嘱未记录（可能影响诊断）
        2. 中危(Medium)：药品类医嘱未记录
        3. 低危(Low)：治疗/其他类医嘱未记录

        Args:
            rule_type: 矛盾类型
            order: 关联的HIS医嘱
            rule_def: 规则定义

        Returns:
            严重程度：high/medium/low
        """
        # 从规则定义获取严重程度（如果配置了）
        if rule_def:
            severity_config = rule_def.severity
            if severity_config:
                # 如果规则有明确的科室/类型适用配置，按配置判断
                if rule_def.is_applicable_order_type(order.order_type):
                    return rule_def.severity

        # 默认严重程度判断逻辑
        order_type_to_severity = {
            "检查": self.SEVERITY_HIGH,
            "检验": self.SEVERITY_HIGH,
            "药品": self.SEVERITY_MEDIUM,
            "治疗": self.SEVERITY_LOW,
            "手术": self.SEVERITY_HIGH,
            "护理": self.SEVERITY_LOW,
            "其他": self.SEVERITY_LOW,
        }

        # 获取基础严重程度
        base_severity = order_type_to_severity.get(order.order_type, self.SEVERITY_MEDIUM)

        # 如果规则有科室配置，特定科室提升严重程度
        if rule_def and rule_def.applicable_departments:
            if order.department in rule_def.applicable_departments:
                # 关键科室提升严重程度
                if base_severity == self.SEVERITY_LOW:
                    return self.SEVERITY_MEDIUM
                elif base_severity == self.SEVERITY_MEDIUM:
                    return self.SEVERITY_HIGH

        return base_severity

    def _determine_severity_for_record(
        self,
        rule_type: str,
        record_keywords: List[str],
        rule_def: Optional[RuleDefinition],
    ) -> str:
        """确定矛盾严重程度（针对写了没开类型）

        严重程度判断逻辑：
        1. 高危(High)：检查/检验类关键词未开医嘱
        2. 中危(Medium)：药品类关键词未开医嘱
        3. 低危(Low)：其他类关键词未开医嘱

        Args:
            rule_type: 矛盾类型
            record_keywords: 病程记录中的关键词列表
            rule_def: 规则定义

        Returns:
            严重程度：high/medium/low
        """
        # 基于关键词推断类型
        high_keywords = ["B超", "CT", "MRI", "X光", "超声", "心电图", "检查", "检验", "化验", "血常规", "尿常规", "生化", "凝血", "输血", "手术", "麻醉"]
        medium_keywords = ["阿莫西林", "布洛芬", "对乙酰氨基酚", "头孢", "青霉素", "药品", "药物", "服药", "口服", "输液", "注射"]
        low_keywords = ["雾化", "理疗", "换药", "拆线", "护理", "治疗"]

        severity = self.SEVERITY_MEDIUM  # 默认中危

        for kw in record_keywords:
            if kw in high_keywords:
                return self.SEVERITY_HIGH
            elif kw in low_keywords:
                severity = self.SEVERITY_LOW

        return severity

    def get_contradictions_by_severity(
        self, contradictions: List[Contradiction]
    ) -> Dict[str, List[Contradiction]]:
        """按严重程度分组矛盾

        Args:
            contradictions: 矛盾列表

        Returns:
            按严重程度分组的字典
        """
        result: Dict[str, List[Contradiction]] = {
            self.SEVERITY_HIGH: [],
            self.SEVERITY_MEDIUM: [],
            self.SEVERITY_LOW: [],
        }

        for c in contradictions:
            if c.severity == self.SEVERITY_HIGH:
                result[self.SEVERITY_HIGH].append(c)
            elif c.severity == self.SEVERITY_MEDIUM:
                result[self.SEVERITY_MEDIUM].append(c)
            else:
                result[self.SEVERITY_LOW].append(c)

        return result

    def get_contradictions_by_department(
        self, contradictions: List[Contradiction]
    ) -> Dict[str, List[Contradiction]]:
        """按科室分组矛盾

        Args:
            contradictions: 矛盾列表

        Returns:
            按科室分组的字典
        """
        result: Dict[str, List[Contradiction]] = {}

        for c in contradictions:
            if c.department not in result:
                result[c.department] = []
            result[c.department].append(c)

        return result

    def get_contradictions_by_doctor(
        self, contradictions: List[Contradiction]
    ) -> Dict[str, List[Contradiction]]:
        """按医生分组矛盾

        Args:
            contradictions: 矛盾列表

        Returns:
            按医生分组的字典
        """
        result: Dict[str, List[Contradiction]] = {}

        for c in contradictions:
            if c.doctor_id not in result:
                result[c.doctor_id] = []
            result[c.doctor_id].append(c)

        return result

    def get_summary_stats(
        self, contradictions: List[Contradiction]
    ) -> Dict[str, any]:
        """获取矛盾统计摘要

        Args:
            contradictions: 矛盾列表

        Returns:
            统计摘要字典
        """
        by_severity = self.get_contradictions_by_severity(contradictions)
        by_department = self.get_contradictions_by_department(contradictions)
        by_doctor = self.get_contradictions_by_doctor(contradictions)

        # 按矛盾类型统计
        by_rule_type: Dict[str, int] = {}
        for c in contradictions:
            by_rule_type[c.rule_type] = by_rule_type.get(c.rule_type, 0) + 1

        return {
            "total": len(contradictions),
            "by_severity": {
                "high": len(by_severity[self.SEVERITY_HIGH]),
                "medium": len(by_severity[self.SEVERITY_MEDIUM]),
                "low": len(by_severity[self.SEVERITY_LOW]),
            },
            "by_rule_type": by_rule_type,
            "by_department": {dept: len(items) for dept, items in by_department.items()},
            "by_doctor": {doctor: len(items) for doctor, items in by_doctor.items()},
            "unique_patients": len(set(c.patient_id for c in contradictions)),
            "unique_doctors": len(set(c.doctor_id for c in contradictions)),
        }


def detect_contradictions(
    patient_visits: List[PatientVisit],
    rules_file_path: Optional[str] = None,
    time_window_minutes: int = 120,
) -> List[Contradiction]:
    """执行矛盾检测的便捷函数

    Args:
        patient_visits: 患者就诊记录列表
        rules_file_path: 规则文件路径
        time_window_minutes: 时间窗口（分钟）

    Returns:
        Contradiction列表
    """
    detector = ContradictionDetector(
        rules_loader=None,
        time_window_minutes=time_window_minutes,
    )

    if rules_file_path:
        rules_loader = RuleDefinitionsLoader(rules_file_path)
        rules_loader.load()
        detector = ContradictionDetector(
            rules_loader=rules_loader,
            time_window_minutes=time_window_minutes,
        )

    return detector.detect(patient_visits, rules_file_path)