"""
统一数据模型和合并加载器模块

提供PatientVisit数据类和MergedDataLoader类，
支持从HIS和EMR数据源批量加载并按患者就诊日期合并。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

from .his_adapter import HisOrder, HisOrderReader
from .emr_adapter import EmrRecord, EmrRecordReader
from ..exceptions import (
    MergeConflictError,
    EmptyDataError,
)

logger = logging.getLogger(__name__)


@dataclass
class PatientVisit:
    """患者就诊统一视图数据模型

    包含同一患者同一次就诊的所有HIS医嘱和EMR病程记录。
    """

    patient_id: str
    visit_date: datetime  # 就诊日期（不含时间）
    orders: List[HisOrder] = field(default_factory=list)  # HIS医嘱列表
    records: List[EmrRecord] = field(default_factory=list)  # EMR病程记录列表

    def __post_init__(self):
        """数据类型校验和转换"""
        # 确保visit_date是日期对象（不含时间）
        if isinstance(self.visit_date, datetime):
            # 保留日期部分，去除时间部分
            self.visit_date = self.visit_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif isinstance(self.visit_date, str):
            self.visit_date = self._parse_date(self.visit_date)

    @staticmethod
    def _parse_date(date_str: Union[str, datetime]) -> datetime:
        """解析日期字符串为datetime对象（日期部分）"""
        if isinstance(date_str, datetime):
            return date_str.replace(hour=0, minute=0, second=0, microsecond=0)
        if isinstance(date_str, str):
            # 尝试多种日期格式
            formats = [
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.replace(hour=0, minute=0, second=0, microsecond=0)
                except ValueError:
                    continue
        raise ValueError(f"无法解析日期: {date_str}")

    def get_orders_by_type(self, order_type: str) -> List[HisOrder]:
        """获取指定类型的医嘱

        Args:
            order_type: 医嘱类型（检查/检验/药品/治疗）

        Returns:
            该类型的医嘱列表
        """
        return [o for o in self.orders if o.order_type == order_type]

    def get_records_by_type(self, record_type: str) -> List[EmrRecord]:
        """获取指定类型的病程记录

        Args:
            record_type: 病程记录类型

        Returns:
            该类型的病程记录列表
        """
        return [r for r in self.records if r.record_type == record_type]

    def get_all_keywords(self) -> List[str]:
        """获取本次就诊所有病程记录中的关键词

        Returns:
            去重后的关键词列表
        """
        keywords = set()
        for record in self.records:
            keywords.update(record.content_keywords)
        return list(keywords)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "patient_id": self.patient_id,
            "visit_date": self.visit_date.isoformat() if self.visit_date else None,
            "orders": [o.to_dict() for o in self.orders],
            "records": [r.to_dict() for r in self.records],
            "order_count": len(self.orders),
            "record_count": len(self.records),
        }


class MergedDataLoader:
    """HIS和EMR数据合并加载器

    从CSV/JSON文件或目录批量加载HIS医嘱和EMR病程记录，
    按patient_id+visit_date合并，输出PatientVisit列表。
    """

    def __init__(self, time_window_minutes: int = 30):
        """初始化合并加载器

        Args:
            time_window_minutes: 时间窗口分钟数（用于矛盾检测）
        """
        self.time_window_minutes = time_window_minutes
        self.his_reader = HisOrderReader(time_window_minutes=time_window_minutes)
        self.emr_reader = EmrRecordReader(time_window_minutes=time_window_minutes)

    def load(
        self,
        his_data: Union[str, Path, List[Union[str, Path]]],
        emr_data: Union[str, Path, List[Union[str, Path]]],
    ) -> List[PatientVisit]:
        """加载并合并HIS和EMR数据

        Args:
            his_data: HIS数据文件路径、目录路径或文件路径列表
            emr_data: EMR数据文件路径、目录路径或文件路径列表

        Returns:
            PatientVisit列表（按patient_id+visit_date合并）

        Raises:
            EmptyDataError: HIS或EMR数据为空
            MergeConflictError: 数据合并时发现冲突
        """
        # 加载HIS数据
        his_orders = self._load_his_data(his_data)
        if not his_orders:
            logger.warning("HIS医嘱数据为空")
        else:
            logger.info(f"加载了 {len(his_orders)} 条HIS医嘱")

        # 加载EMR数据
        emr_records = self._load_emr_data(emr_data)
        if not emr_records:
            logger.warning("EMR病程记录数据为空")
        else:
            logger.info(f"加载了 {len(emr_records)} 条EMR病程记录")

        if not his_orders and not emr_records:
            raise EmptyDataError("HIS医嘱和EMR病程记录", "两个数据源均为空")

        # 按patient_id+visit_date合并
        patient_visits = self._merge_by_patient_visit(his_orders, emr_records)
        logger.info(f"合并后得到 {len(patient_visits)} 条患者就诊记录")

        return patient_visits

    def _load_his_data(
        self, his_data: Union[str, Path, List[Union[str, Path]]]
    ) -> List[HisOrder]:
        """加载HIS数据

        Raises:
            DataFileNotFoundError: 文件或目录不存在
            DataFormatError: 文件格式错误
            EmptyDataError: 数据为空
        """
        if isinstance(his_data, (str, Path)):
            path = Path(his_data)
            if path.is_dir():
                return self.his_reader.read_directory(path)
            else:
                return self.his_reader.read(path)
        elif isinstance(his_data, list):
            all_orders = []
            for p in his_data:
                orders = self.his_reader.read(Path(p))
                all_orders.extend(orders)
            return all_orders
        else:
            raise ValueError(f"HIS数据路径类型不支持: {type(his_data)}")

    def _load_emr_data(
        self, emr_data: Union[str, Path, List[Union[str, Path]]]
    ) -> List[EmrRecord]:
        """加载EMR数据

        Raises:
            DataFileNotFoundError: 文件或目录不存在
            DataFormatError: 文件格式错误
            EmptyDataError: 数据为空
        """
        if isinstance(emr_data, (str, Path)):
            path = Path(emr_data)
            if path.is_dir():
                return self.emr_reader.read_directory(path)
            else:
                return self.emr_reader.read(path)
        elif isinstance(emr_data, list):
            all_records = []
            for p in emr_data:
                records = self.emr_reader.read(Path(p))
                all_records.extend(records)
            return all_records
        else:
            raise ValueError(f"EMR数据路径类型不支持: {type(emr_data)}")

    def _merge_by_patient_visit(
        self, orders: List[HisOrder], records: List[EmrRecord]
    ) -> List[PatientVisit]:
        """按patient_id+visit_date合并医嘱和病程记录

        规则：
        1. 使用create_time的日期部分作为visit_date
        2. 同一患者同一天的就诊记录合并为一个PatientVisit
        3. 若某患者某天只有医嘱或只有病程记录，仍然创建一个PatientVisit

        Args:
            orders: HIS医嘱列表
            records: EMR病程记录列表

        Returns:
            PatientVisit列表
        """
        # 按 (patient_id, visit_date) 分组
        visit_map: Dict[tuple, PatientVisit] = {}

        # 处理HIS医嘱
        for order in orders:
            visit_date = order.create_time.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            key = (order.patient_id, visit_date)

            if key not in visit_map:
                visit_map[key] = PatientVisit(
                    patient_id=order.patient_id,
                    visit_date=visit_date,
                    orders=[],
                    records=[],
                )
            visit_map[key].orders.append(order)

        # 处理EMR病程记录
        for record in records:
            visit_date = record.create_time.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            key = (record.patient_id, visit_date)

            if key not in visit_map:
                visit_map[key] = PatientVisit(
                    patient_id=record.patient_id,
                    visit_date=visit_date,
                    orders=[],
                    records=[],
                )
            visit_map[key].records.append(record)

        # 转换为列表并按日期排序
        visits = list(visit_map.values())
        visits.sort(key=lambda v: (v.patient_id, v.visit_date))

        return visits

    def get_patient_visit(
        self, patient_id: str, visit_date: Union[str, datetime]
    ) -> Optional[PatientVisit]:
        """获取指定患者指定日期的就诊记录

        Args:
            patient_id: 患者ID
            visit_date: 就诊日期

        Returns:
            PatientVisit对象，若不存在则返回None
        """
        if isinstance(visit_date, str):
            visit_date = PatientVisit._parse_date(visit_date)

        visits = self._merge_by_patient_visit([], [])
        for visit in visits:
            if visit.patient_id == patient_id and visit.visit_date == visit_date:
                return visit

        return None


class VisitStatistics:
    """就诊统计数据类"""

    def __init__(self, patient_visits: List[PatientVisit]):
        """初始化统计数据

        Args:
            patient_visits: PatientVisit列表
        """
        self.patient_visits = patient_visits

    @property
    def total_visits(self) -> int:
        """总就诊次数"""
        return len(self.patient_visits)

    @property
    def total_orders(self) -> int:
        """总医嘱数"""
        return sum(len(v.orders) for v in self.patient_visits)

    @property
    def total_records(self) -> int:
        """总病程记录数"""
        return sum(len(v.records) for v in self.patient_visits)

    @property
    def unique_patients(self) -> int:
        """独立患者数"""
        return len(set(v.patient_id for v in self.patient_visits))

    @property
    def visits_by_department(self) -> Dict[str, int]:
        """按科室统计就诊次数"""
        dept_counts: Dict[str, int] = {}
        for visit in self.patient_visits:
            if visit.orders:
                dept = visit.orders[0].department
            elif visit.records:
                dept = visit.records[0].department
            else:
                dept = "未知"
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
        return dept_counts

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "total_visits": self.total_visits,
            "total_orders": self.total_orders,
            "total_records": self.total_records,
            "unique_patients": self.unique_patients,
            "visits_by_department": self.visits_by_department,
        }