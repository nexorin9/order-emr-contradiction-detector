"""
时间对齐引擎模块

将HIS医嘱和EMR病程记录按patient_id和时间窗口对齐，
支持关键词模糊匹配和同义词扩展。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..data.his_adapter import HisOrder
from ..data.emr_adapter import EmrRecord
from ..rules.rule_definitions import RuleDefinitionsLoader, RuleDefinition

logger = logging.getLogger(__name__)


@dataclass
class AlignmentResult:
    """单条对齐结果"""

    matched: bool  # 是否匹配成功
    order: HisOrder  # 对应的HIS医嘱
    record: Optional[EmrRecord]  # 对应的EMR记录（若matched=True）
    match_type: str  # 匹配类型：exact/fuzzy/synonym/none
    match_basis: str  # 匹配依据说明
    matched_keywords: List[str] = field(default_factory=list)  # 匹配到的关键词


@dataclass
class AlignedOrderRecord:
    """医嘱-病程记录对齐对"""

    order: HisOrder
    record: Optional[EmrRecord]
    matched: bool
    match_type: str  # exact/fuzzy/synonym/none
    match_basis: str  # 说明为何匹配或未匹配
    time_diff_minutes: Optional[float] = None  # 时间差（分钟）
    matched_keywords: List[str] = field(default_factory=list)  # 匹配到的关键词列表


class TimeAligner:
    """HIS医嘱与EMR病程记录时间对齐器

    核心功能：
    1. 按patient_id分组
    2. 对每条HIS医嘱，在配置的time_window内查找EMR记录中是否包含对应关键词
    3. 对每条EMR记录，检查是否有对应HIS医嘱
    4. 输出AlignedOrderRecord对列表（含matched标志和匹配依据）
    """

    def __init__(
        self,
        time_window_minutes: int = 120,
        rules_loader: Optional[RuleDefinitionsLoader] = None,
    ):
        """初始化时间对齐器

        Args:
            time_window_minutes: 默认时间窗口（分钟），默认120分钟
            rules_loader: 规则定义加载器，若提供则使用规则中的配置
        """
        self.time_window_minutes = time_window_minutes
        self.rules_loader = rules_loader

    def align(
        self,
        orders: List[HisOrder],
        records: List[EmrRecord],
        rule_type: Optional[str] = None,
    ) -> List[AlignedOrderRecord]:
        """对齐HIS医嘱和EMR病程记录

        对每条HIS医嘱，在time_window时间窗口内查找匹配的EMR记录。
        同时检查是否有EMR记录提及了未开医嘱的项目。

        Args:
            orders: HIS医嘱列表
            records: EMR病程记录列表
            rule_type: 规则类型（用于获取特定规则配置），若为None则使用默认配置

        Returns:
            AlignedOrderRecord列表
        """
        # 按patient_id分组
        orders_by_patient: Dict[str, List[HisOrder]] = {}
        for order in orders:
            if order.patient_id not in orders_by_patient:
                orders_by_patient[order.patient_id] = []
            orders_by_patient[order.patient_id].append(order)

        records_by_patient: Dict[str, List[EmrRecord]] = {}
        for record in records:
            if record.patient_id not in records_by_patient:
                records_by_patient[record.patient_id] = []
            records_by_patient[record.patient_id].append(record)

        # 确定时间窗口
        time_window = self._get_time_window(rule_type)

        # 对齐结果
        aligned_results: List[AlignedOrderRecord] = []

        # 对每条医嘱，查找匹配的病程记录
        for patient_id, patient_orders in orders_by_patient.items():
            patient_records = records_by_patient.get(patient_id, [])

            for order in patient_orders:
                result = self._align_order_to_records(
                    order, patient_records, time_window, rule_type
                )
                aligned_results.append(result)

        return aligned_results

    def _get_time_window(self, rule_type: Optional[str]) -> int:
        """获取时间窗口分钟数"""
        if self.rules_loader and rule_type:
            return self.rules_loader.get_time_window_minutes(rule_type)
        return self.time_window_minutes

    def _align_order_to_records(
        self,
        order: HisOrder,
        records: List[EmrRecord],
        time_window_minutes: int,
        rule_type: Optional[str],
    ) -> AlignedOrderRecord:
        """将单条医嘱与患者的病程记录进行对齐

        Args:
            order: HIS医嘱
            records: 同一患者的所有病程记录
            time_window_minutes: 时间窗口（分钟）
            rule_type: 规则类型

        Returns:
            AlignedOrderRecord对齐结果
        """
        time_window = timedelta(minutes=time_window_minutes)
        order_time = order.create_time

        if order_time is None:
            return AlignedOrderRecord(
                order=order,
                record=None,
                matched=False,
                match_type="none",
                match_basis="医嘱创建时间无效",
            )

        # 查找时间窗口内的病程记录
        candidate_records: List[Tuple[EmrRecord, float]] = []
        for record in records:
            if record.create_time is None:
                continue

            time_diff = (record.create_time - order_time).total_seconds() / 60

            # 医嘱创建后time_window分钟内，或病程记录在医嘱创建前time_window分钟内
            if -time_window_minutes <= time_diff <= time_window_minutes:
                candidate_records.append((record, time_diff))

        # 如果没有候选记录
        if not candidate_records:
            return AlignedOrderRecord(
                order=order,
                record=None,
                matched=False,
                match_type="none",
                match_basis=f"在{time_window_minutes}分钟时间窗口内未找到病程记录",
                time_diff_minutes=None,
            )

        # 在候选记录中查找关键词匹配
        matched_record, matched_keywords, match_type = self._find_matching_record(
            order, candidate_records, rule_type
        )

        if matched_record:
            time_diff = (
                (matched_record.create_time - order_time).total_seconds() / 60
            )
            return AlignedOrderRecord(
                order=order,
                record=matched_record,
                matched=True,
                match_type=match_type,
                match_basis=self._build_match_basis(order, matched_record, matched_keywords, match_type),
                time_diff_minutes=time_diff,
                matched_keywords=matched_keywords,
            )
        else:
            # 医嘱创建后最早的那条记录作为参考
            earliest_record, earliest_diff = min(candidate_records, key=lambda x: x[1])
            return AlignedOrderRecord(
                order=order,
                record=None,
                matched=False,
                match_type="none",
                match_basis=f"时间窗口内有{len(candidate_records)}条病程记录，但关键词不匹配。医嘱项目「{order.item_name}」未在任何病程记录中找到对应描述",
                time_diff_minutes=earliest_diff,
            )

    def _find_matching_record(
        self,
        order: HisOrder,
        candidate_records: List[Tuple[EmrRecord, float]],
        rule_type: Optional[str],
    ) -> Tuple[Optional[EmrRecord], List[str], str]:
        """在候选记录中查找关键词匹配

        Args:
            order: HIS医嘱
            candidate_records: 候选病程记录列表（含时间差）
            rule_type: 规则类型

        Returns:
            (匹配的病程记录, 匹配到的关键词列表, 匹配类型) 元组
        """
        # 获取同义词列表
        synonyms = self._get_item_synonyms(order.item_name, rule_type)

        # 按优先级检查匹配：精确匹配 > 同义词匹配 > 模糊匹配
        for record, time_diff in candidate_records:
            # 检查是否有关键词匹配
            matched_keywords = self._check_keyword_match(
                record.content_keywords, synonyms
            )

            if matched_keywords:
                # 确定匹配类型
                if order.item_name in record.content_keywords:
                    match_type = "exact"
                elif any(syn in record.content_keywords for syn in synonyms if syn != order.item_name):
                    match_type = "synonym"
                else:
                    match_type = "fuzzy"

                return record, matched_keywords, match_type

        return None, [], "none"

    def _check_keyword_match(
        self, record_keywords: List[str], synonyms: List[str]
    ) -> List[str]:
        """检查病程记录关键词是否与医嘱项目匹配

        Args:
            record_keywords: 病程记录中的关键词列表
            synonyms: 医嘱项目的同义词列表

        Returns:
            匹配到的关键词列表
        """
        if not record_keywords or not synonyms:
            return []

        matched = []
        for record_kw in record_keywords:
            for syn_kw in synonyms:
                if syn_kw in record_kw or record_kw in syn_kw:
                    matched.append(record_kw)
                    break

        return matched

    def _get_item_synonyms(self, item_name: str, rule_type: Optional[str]) -> List[str]:
        """获取医嘱项目的同义词列表

        Args:
            item_name: 医嘱项目名称
            rule_type: 规则类型

        Returns:
            同义词列表（包含原名称）
        """
        synonyms = [item_name]

        if self.rules_loader:
            rule_synonyms = self.rules_loader.get_synonyms_for_item(item_name)
            synonyms.extend(rule_synonyms)
        else:
            # 无规则加载器时，使用简单的模糊匹配
            synonyms.append(item_name)

        # 去重
        return list(dict.fromkeys(synonyms))

    def _build_match_basis(
        self,
        order: HisOrder,
        record: EmrRecord,
        matched_keywords: List[str],
        match_type: str,
    ) -> str:
        """构建匹配依据说明

        Args:
            order: HIS医嘱
            record: 匹配的EMR记录
            matched_keywords: 匹配到的关键词
            match_type: 匹配类型

        Returns:
            匹配依据说明字符串
        """
        match_type_desc = {
            "exact": "精确匹配",
            "synonym": "同义词匹配",
            "fuzzy": "模糊匹配",
        }.get(match_type, match_type)

        basis = f"{match_type_desc}：医嘱项目「{order.item_name}」在病程记录中找到对应描述"

        if matched_keywords:
            basis += f"，匹配关键词：{'、'.join(matched_keywords)}"

        if order.create_time and record.create_time:
            time_diff = (record.create_time - order.create_time).total_seconds() / 60
            if time_diff >= 0:
                basis += f"，病程记录晚于医嘱{int(time_diff)}分钟"
            else:
                basis += f"，病程记录早于医嘱{int(-time_diff)}分钟"

        return basis

    def align_by_record(
        self,
        orders: List[HisOrder],
        records: List[EmrRecord],
        rule_type: Optional[str] = None,
    ) -> List[AlignedOrderRecord]:
        """按EMR记录维度对齐（用于检测"写了没开"类矛盾）

        对每条EMR记录，查找是否有对应的HIS医嘱。

        Args:
            orders: HIS医嘱列表
            records: EMR病程记录列表
            rule_type: 规则类型

        Returns:
            AlignedOrderRecord列表
        """
        # 按patient_id分组
        orders_by_patient: Dict[str, List[HisOrder]] = {}
        for order in orders:
            if order.patient_id not in orders_by_patient:
                orders_by_patient[order.patient_id] = []
            orders_by_patient[order.patient_id].append(order)

        records_by_patient: Dict[str, List[EmrRecord]] = {}
        for record in records:
            if record.patient_id not in records_by_patient:
                records_by_patient[record.patient_id] = []
            records_by_patient[record.patient_id].append(record)

        time_window = self._get_time_window(rule_type)
        aligned_results: List[AlignedOrderRecord] = []

        for patient_id, patient_records in records_by_patient.items():
            patient_orders = orders_by_patient.get(patient_id, [])

            for record in patient_records:
                result = self._align_record_to_orders(
                    record, patient_orders, time_window, rule_type
                )
                aligned_results.append(result)

        return aligned_results

    def _align_record_to_orders(
        self,
        record: EmrRecord,
        orders: List[HisOrder],
        time_window_minutes: int,
        rule_type: Optional[str],
    ) -> AlignedOrderRecord:
        """将单条病程记录与患者医嘱进行对齐

        Args:
            record: EMR病程记录
            orders: 同一患者的所有医嘱
            time_window_minutes: 时间窗口（分钟）
            rule_type: 规则类型

        Returns:
            AlignedOrderRecord对齐结果
        """
        if not record.create_time:
            return AlignedOrderRecord(
                order=HisOrder(
                    order_id="",
                    patient_id=record.patient_id,
                    doctor_id=record.doctor_id,
                    department=record.department,
                    order_type="",
                    item_name="",
                    create_time=None,
                ),
                record=record,
                matched=False,
                match_type="none",
                match_basis="病程记录创建时间无效",
            )

        matched_order = None
        matched_keywords = []
        match_type = "none"

        for order in orders:
            if not order.create_time:
                continue

            time_diff = (record.create_time - order.create_time).total_seconds() / 60

            # 只考虑病程记录时间之前time_window分钟内的医嘱
            if -time_window_minutes <= time_diff <= 0:
                synonyms = self._get_item_synonyms(order.item_name, rule_type)
                keywords_matched = self._check_keyword_match(
                    record.content_keywords, synonyms
                )

                if keywords_matched:
                    matched_order = order
                    matched_keywords = keywords_matched
                    if order.item_name in record.content_keywords:
                        match_type = "exact"
                    elif any(syn in record.content_keywords for syn in synonyms if syn != order.item_name):
                        match_type = "synonym"
                    else:
                        match_type = "fuzzy"
                    break

        if matched_order:
            return AlignedOrderRecord(
                order=matched_order,
                record=record,
                matched=True,
                match_type=match_type,
                match_basis=self._build_record_match_basis(
                    record, matched_order, matched_keywords, match_type
                ),
                time_diff_minutes=(record.create_time - matched_order.create_time).total_seconds() / 60,
                matched_keywords=matched_keywords,
            )
        else:
            return AlignedOrderRecord(
                order=HisOrder(
                    order_id="",
                    patient_id=record.patient_id,
                    doctor_id=record.doctor_id,
                    department=record.department,
                    order_type="",
                    item_name="",
                    create_time=None,
                ),
                record=record,
                matched=False,
                match_type="none",
                match_basis=f"病程记录提及了「{'、'.join(record.content_keywords)}」，但在记录时间之前的{time_window_minutes}分钟内未找到对应医嘱",
            )

    def _build_record_match_basis(
        self,
        record: EmrRecord,
        order: HisOrder,
        matched_keywords: List[str],
        match_type: str,
    ) -> str:
        """构建病程记录匹配依据说明"""
        match_type_desc = {
            "exact": "精确匹配",
            "synonym": "同义词匹配",
            "fuzzy": "模糊匹配",
        }.get(match_type, match_type)

        basis = f"{match_type_desc}：病程记录中的关键词在医嘱中找到对应项目"

        if matched_keywords:
            basis += f"，匹配关键词：{'、'.join(matched_keywords)}"

        if record.create_time and order.create_time:
            time_diff = (record.create_time - order.create_time).total_seconds() / 60
            basis += f"，病程记录晚于医嘱{int(time_diff)}分钟"

        return basis


def align_orders_and_records(
    orders: List[HisOrder],
    records: List[EmrRecord],
    time_window_minutes: int = 120,
    rules_loader: Optional[RuleDefinitionsLoader] = None,
    rule_type: Optional[str] = None,
) -> List[AlignedOrderRecord]:
    """对齐HIS医嘱和EMR病程记录的便捷函数

    Args:
        orders: HIS医嘱列表
        records: EMR病程记录列表
        time_window_minutes: 时间窗口（分钟）
        rules_loader: 规则定义加载器
        rule_type: 规则类型

    Returns:
        AlignedOrderRecord列表
    """
    aligner = TimeAligner(
        time_window_minutes=time_window_minutes,
        rules_loader=rules_loader,
    )
    return aligner.align(orders, records, rule_type)