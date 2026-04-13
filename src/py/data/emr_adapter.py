"""
EMR病程记录数据适配器模块

提供EmrRecord数据类和EmrRecordReader类，
支持从CSV和JSON文件读取EMR病程记录数据并输出标准化格式。
"""

import csv
import json
import logging
from dataclasses import dataclass
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
class EmrRecord:
    """EMR病程记录标准化数据模型"""

    record_id: str
    patient_id: str
    doctor_id: str
    department: str
    record_type: str  # 首次病程/日常病程/手术记录/出院记录等
    content_keywords: List[str]  # 关键词列表（如检查项目名、药品名、操作名称）
    create_time: datetime  # 记录创建时间

    def __post_init__(self):
        """数据类型校验和转换"""
        # 确保时间字段是datetime对象
        if isinstance(self.create_time, str):
            self.create_time = self._parse_datetime(self.create_time)

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
            "record_id": self.record_id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "department": self.department,
            "record_type": self.record_type,
            "content_keywords": self.content_keywords,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


class EmrRecordReader:
    """EMR病程记录数据读取器

    支持从CSV和JSON文件读取病程记录数据，
    输出标准化的EmrRecord对象列表。
    """

    # CSV文件必需字段
    REQUIRED_CSV_FIELDS = [
        "record_id",
        "patient_id",
        "doctor_id",
        "department",
        "record_type",
        "create_time",
    ]

    # 关键词字段（CSV中用分号分隔）
    KEYWORDS_FIELD = "content_keywords"
    KEYWORDS_SEPARATOR = ";"

    # 可选字段
    OPTIONAL_CSV_FIELDS = ["content_keywords"]

    def __init__(self, time_window_minutes: int = 30):
        """初始化读取器

        Args:
            time_window_minutes: 时间窗口分钟数（用于矛盾检测）
        """
        self.time_window_minutes = time_window_minutes

    def read(
        self, file_path: Union[str, Path], file_format: Optional[str] = None
    ) -> List[EmrRecord]:
        """读取病程记录数据文件

        Args:
            file_path: 文件路径
            file_format: 文件格式（csv/json），若为None则根据扩展名推断

        Returns:
            EmrRecord对象列表

        Raises:
            DataFileNotFoundError: 文件不存在
            DataFormatError: 文件格式不支持或数据格式错误
            EmptyDataError: 数据为空
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise DataFileNotFoundError(str(file_path), "EMR病程记录")

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

    def _read_csv(self, file_path: Path) -> List[EmrRecord]:
        """从CSV文件读取病程记录数据

        Raises:
            DataFormatError: CSV格式错误
            MissingRequiredFieldError: 缺少必需字段
            EmptyDataError: 数据为空
        """
        records = []
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
                    record = self._parse_csv_row(row, row_num)
                    if record is not None:
                        records.append(record)
                    else:
                        skipped_rows.append(row_num)
                except Exception as e:
                    logger.warning(f"跳过第{row_num}行数据，解析错误: {e}")
                    skipped_rows.append(row_num)
                    continue

        if skipped_rows:
            logger.warning(f"从CSV文件 [{file_path}] 共跳过了{len(skipped_rows)}行数据: 行号{skipped_rows[:10]}...")

        if not records:
            raise EmptyDataError("EMR病程记录", str(file_path))

        logger.info(f"从CSV文件读取了{len(records)}条病程记录: {file_path}")
        return records

    def _parse_csv_row(self, row: dict, row_num: int) -> Optional[EmrRecord]:
        """解析CSV单行数据"""
        # 检查必需字段是否有值
        for field in self.REQUIRED_CSV_FIELDS:
            if not row.get(field):
                logger.warning(f"第{row_num}行缺少必需字段{field}，跳过")
                return None

        # 解析关键词列表
        keywords_str = row.get(self.KEYWORDS_FIELD, "").strip()
        if keywords_str:
            keywords = [k.strip() for k in keywords_str.split(self.KEYWORDS_SEPARATOR) if k.strip()]
        else:
            keywords = []

        try:
            return EmrRecord(
                record_id=row["record_id"].strip(),
                patient_id=row["patient_id"].strip(),
                doctor_id=row["doctor_id"].strip(),
                department=row["department"].strip(),
                record_type=row["record_type"].strip(),
                content_keywords=keywords,
                create_time=row["create_time"].strip(),
            )
        except Exception as e:
            logger.warning(f"第{row_num}行数据解析失败: {e}")
            return None

    def _read_json(self, file_path: Path) -> List[EmrRecord]:
        """从JSON文件读取病程记录数据

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
        elif isinstance(data, dict) and "records" in data:
            records = data["records"]
        elif isinstance(data, dict) and "emr_records" in data:
            records = data["emr_records"]
        elif isinstance(data, dict) and "data" in data:
            records = data["data"]
        else:
            raise DataFormatError(
                str(file_path),
                "JSON文件格式不正确，应为数组或包含records/emr_records/data键的对象"
            )

        if not records:
            raise EmptyDataError("EMR病程记录", str(file_path))

        records_list = []
        skipped_idx = []  # 记录跳过的索引
        for idx, record in enumerate(records):
            try:
                emr_record = self._parse_json_record(record, idx)
                if emr_record is not None:
                    records_list.append(emr_record)
                else:
                    skipped_idx.append(idx)
            except Exception as e:
                logger.warning(f"第{idx}条记录解析错误: {e}")
                skipped_idx.append(idx)
                continue

        if skipped_idx:
            logger.warning(f"从JSON文件 [{file_path}] 共跳过了{len(skipped_idx)}条记录")

        if not records_list:
            raise EmptyDataError("EMR病程记录", str(file_path))

        logger.info(f"从JSON文件读取了{len(records_list)}条病程记录: {file_path}")
        return records_list

    def _parse_json_record(self, record: dict, idx: int) -> Optional[EmrRecord]:
        """解析JSON单条记录"""
        # 检查必需字段
        for field in self.REQUIRED_CSV_FIELDS:
            if field not in record or not record[field]:
                logger.warning(f"第{idx}条记录缺少必需字段{field}，跳过")
                return None

        # 解析关键词列表
        keywords = record.get(self.KEYWORDS_FIELD, [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(self.KEYWORDS_SEPARATOR) if k.strip()]
        elif not isinstance(keywords, list):
            keywords = []

        try:
            return EmrRecord(
                record_id=str(record["record_id"]).strip(),
                patient_id=str(record["patient_id"]).strip(),
                doctor_id=str(record["doctor_id"]).strip(),
                department=str(record["department"]).strip(),
                record_type=str(record["record_type"]).strip(),
                content_keywords=keywords,
                create_time=record["create_time"],
            )
        except Exception as e:
            logger.warning(f"第{idx}条记录解析失败: {e}")
            return None

    def read_directory(self, dir_path: Union[str, Path]) -> List[EmrRecord]:
        """从目录读取所有CSV和JSON文件

        Args:
            dir_path: 目录路径

        Returns:
            所有文件的EmrRecord对象列表

        Raises:
            DataFileNotFoundError: 目录不存在
            DataFormatError: 目录路径无效（非目录）
        """
        dir_path = Path(dir_path)
        if not dir_path.exists():
            raise DataFileNotFoundError(str(dir_path), "EMR数据目录")
        if not dir_path.is_dir():
            raise DataFormatError(str(dir_path), "路径不是有效的目录")

        all_records = []
        failed_files = []  # 记录读取失败的文件
        for file_path in dir_path.glob("*"):
            if file_path.suffix.lower() in [".csv", ".json"]:
                try:
                    records = self.read(file_path)
                    all_records.extend(records)
                except Exception as e:
                    logger.warning(f"读取文件失败 {file_path}: {e}")
                    failed_files.append(str(file_path))
                    continue

        if failed_files:
            logger.warning(f"部分文件读取失败: {failed_files}")

        if not all_records:
            logger.warning(f"目录 [{dir_path}] 中未找到有效的EMR病程记录数据")

        return all_records