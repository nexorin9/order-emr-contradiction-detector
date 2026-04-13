"""
HIS医嘱数据适配器模块

提供HisOrder数据类和HisOrderReader类，
支持从CSV和JSON文件读取HIS医嘱数据并输出标准化格式。
"""

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from ..exceptions import (
    DataFileNotFoundError,
    DataFormatError,
    MissingRequiredFieldError,
    EmptyDataError,
)

logger = logging.getLogger(__name__)


@dataclass
class HisOrder:
    """HIS医嘱标准化数据模型"""

    order_id: str
    patient_id: str
    doctor_id: str
    department: str
    order_type: str  # 检查/检验/药品/治疗
    item_name: str  # 医嘱项目名称（如B超、血常规、阿莫西林）
    create_time: datetime  # 医嘱创建时间
    execute_time: Optional[datetime] = None  # 医嘱执行时间
    status: str = "pending"  # pending/completed/cancelled

    def __post_init__(self):
        """数据类型校验和转换"""
        # 确保时间字段是datetime对象
        if isinstance(self.create_time, str):
            self.create_time = self._parse_datetime(self.create_time)
        if isinstance(self.execute_time, str):
            self.execute_time = self._parse_datetime(self.execute_time)

    @staticmethod
    def _parse_datetime(time_str: Union[str, datetime]) -> Optional[datetime]:
        """解析时间字符串为datetime对象"""
        if time_str is None or time_str == "":
            return None
        if isinstance(time_str, datetime):
            return time_str

        # 尝试多种日期格式
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue

        logger.warning(f"无法解析时间字符串: {time_str}")
        return None

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "order_id": self.order_id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "department": self.department,
            "order_type": self.order_type,
            "item_name": self.item_name,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "execute_time": self.execute_time.isoformat() if self.execute_time else None,
            "status": self.status,
        }


class HisOrderReader:
    """HIS医嘱数据读取器

    支持从CSV和JSON文件读取医嘱数据，
    输出标准化的HisOrder对象列表。
    """

    # CSV文件必需字段
    REQUIRED_CSV_FIELDS = [
        "order_id",
        "patient_id",
        "doctor_id",
        "department",
        "order_type",
        "item_name",
        "create_time",
    ]

    # 可选字段
    OPTIONAL_CSV_FIELDS = ["execute_time", "status"]

    def __init__(self, time_window_minutes: int = 30):
        """初始化读取器

        Args:
            time_window_minutes: 时间窗口分钟数（用于矛盾检测）
        """
        self.time_window_minutes = time_window_minutes

    def read(
        self, file_path: Union[str, Path], file_format: Optional[str] = None
    ) -> List[HisOrder]:
        """读取医嘱数据文件

        Args:
            file_path: 文件路径
            file_format: 文件格式（csv/json），若为None则根据扩展名推断

        Returns:
            HisOrder对象列表

        Raises:
            DataFileNotFoundError: 文件不存在
            DataFormatError: 文件格式不支持或数据格式错误
            EmptyDataError: 数据为空
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise DataFileNotFoundError(str(file_path), "HIS医嘱")

        if file_format is None:
            file_format = file_path.suffix.lower().lstrip(".")

        if file_format == "csv":
            return self._read_csv(file_path)
        elif file_format == "json":
            return self._read_json(file_path)
        else:
            raise DataFormatError(
                str(file_path),
                f"不支持的文件格式: {file_format}，仅支持csv和json"
            )

    def _read_csv(self, file_path: Path) -> List[HisOrder]:
        """从CSV文件读取医嘱数据

        Raises:
            DataFormatError: CSV格式错误
            MissingRequiredFieldError: 缺少必需字段
            EmptyDataError: 数据为空
        """
        orders = []
        skipped_rows = []  # 记录跳过的行号

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # 检查必需字段
            if reader.fieldnames is None:
                raise DataFormatError(str(file_path), "CSV文件字段为空或格式不正确")

            missing_fields = set(self.REQUIRED_CSV_FIELDS) - set(reader.fieldnames)
            if missing_fields:
                raise MissingRequiredFieldError(str(file_path), list(missing_fields))

            for row_num, row in enumerate(reader, start=2):  # start=2因为首行是表头
                try:
                    order = self._parse_csv_row(row, row_num)
                    if order is not None:
                        orders.append(order)
                    else:
                        skipped_rows.append(row_num)
                except Exception as e:
                    logger.warning(f"跳过第{row_num}行数据，解析错误: {e}")
                    skipped_rows.append(row_num)
                    continue

        if skipped_rows:
            logger.warning(f"从CSV文件 [{file_path}] 共跳过了{len(skipped_rows)}行数据: 行号{skipped_rows[:10]}...")

        if not orders:
            raise EmptyDataError("HIS医嘱", str(file_path))

        logger.info(f"从CSV文件读取了{len(orders)}条医嘱记录: {file_path}")
        return orders

    def _parse_csv_row(self, row: dict, row_num: int) -> Optional[HisOrder]:
        """解析CSV单行数据"""
        # 检查必需字段是否有值
        for field in self.REQUIRED_CSV_FIELDS:
            if not row.get(field):
                logger.warning(f"第{row_num}行缺少必需字段{field}，跳过")
                return None

        try:
            return HisOrder(
                order_id=row["order_id"].strip(),
                patient_id=row["patient_id"].strip(),
                doctor_id=row["doctor_id"].strip(),
                department=row["department"].strip(),
                order_type=row["order_type"].strip(),
                item_name=row["item_name"].strip(),
                create_time=row["create_time"].strip(),
                execute_time=row.get("execute_time", "").strip() or None,
                status=row.get("status", "pending").strip() or "pending",
            )
        except Exception as e:
            logger.warning(f"第{row_num}行数据解析失败: {e}")
            return None

    def _read_json(self, file_path: Path) -> List[HisOrder]:
        """从JSON文件读取医嘱数据

        Raises:
            DataFormatError: JSON格式错误
            EmptyDataError: 数据为空
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise DataFormatError(str(file_path), f"JSON解析失败: {e}")
        except IOError as e:
            raise DataFormatError(str(file_path), f"文件读取失败: {e}")

        # 支持多种JSON格式：数组或包含数组的对象
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and "orders" in data:
            records = data["orders"]
        elif isinstance(data, dict) and "data" in data:
            records = data["data"]
        else:
            raise DataFormatError(
                str(file_path),
                "JSON文件格式不正确，应为数组或包含orders/data键的对象"
            )

        if not records:
            raise EmptyDataError("HIS医嘱", str(file_path))

        orders = []
        skipped_idx = []  # 记录跳过的索引
        for idx, record in enumerate(records):
            try:
                order = self._parse_json_record(record, idx)
                if order is not None:
                    orders.append(order)
                else:
                    skipped_idx.append(idx)
            except Exception as e:
                logger.warning(f"第{idx}条记录解析错误: {e}")
                skipped_idx.append(idx)
                continue

        if skipped_idx:
            logger.warning(f"从JSON文件 [{file_path}] 共跳过了{len(skipped_idx)}条记录")

        if not orders:
            raise EmptyDataError("HIS医嘱", str(file_path))

        logger.info(f"从JSON文件读取了{len(orders)}条医嘱记录: {file_path}")
        return orders

    def _parse_json_record(self, record: dict, idx: int) -> Optional[HisOrder]:
        """解析JSON单条记录"""
        # 检查必需字段
        for field in self.REQUIRED_CSV_FIELDS:
            if field not in record or not record[field]:
                logger.warning(f"第{idx}条记录缺少必需字段{field}，跳过")
                return None

        try:
            return HisOrder(
                order_id=str(record["order_id"]).strip(),
                patient_id=str(record["patient_id"]).strip(),
                doctor_id=str(record["doctor_id"]).strip(),
                department=str(record["department"]).strip(),
                order_type=str(record["order_type"]).strip(),
                item_name=str(record["item_name"]).strip(),
                create_time=record["create_time"],
                execute_time=record.get("execute_time"),
                status=str(record.get("status", "pending")).strip() or "pending",
            )
        except Exception as e:
            logger.warning(f"第{idx}条记录解析失败: {e}")
            return None

    def read_directory(self, dir_path: Union[str, Path]) -> List[HisOrder]:
        """从目录读取所有CSV和JSON文件

        Args:
            dir_path: 目录路径

        Returns:
            所有文件的HisOrder对象列表

        Raises:
            DataFileNotFoundError: 目录不存在
            DataFormatError: 目录路径无效（非目录）
        """
        dir_path = Path(dir_path)
        if not dir_path.exists():
            raise DataFileNotFoundError(str(dir_path), "HIS数据目录")
        if not dir_path.is_dir():
            raise DataFormatError(str(dir_path), "路径不是有效的目录")

        all_orders = []
        failed_files = []  # 记录读取失败的文件
        for file_path in dir_path.glob("*"):
            if file_path.suffix.lower() in [".csv", ".json"]:
                try:
                    orders = self.read(file_path)
                    all_orders.extend(orders)
                except Exception as e:
                    logger.warning(f"读取文件失败 {file_path}: {e}")
                    failed_files.append(str(file_path))
                    continue

        if failed_files:
            logger.warning(f"部分文件读取失败: {failed_files}")

        if not all_orders:
            logger.warning(f"目录 [{dir_path}] 中未找到有效的HIS医嘱数据")

        return all_orders
