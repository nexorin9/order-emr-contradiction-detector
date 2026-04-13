"""
数据适配层模块

提供HIS医嘱数据和EMR病程记录数据的读取功能，
以及统一数据模型和合并加载器。
"""

from .his_adapter import HisOrder, HisOrderReader
from .emr_adapter import EmrRecord, EmrRecordReader
from .merged_loader import PatientVisit, MergedDataLoader, VisitStatistics

__all__ = [
    "HisOrder",
    "HisOrderReader",
    "EmrRecord",
    "EmrRecordReader",
    "PatientVisit",
    "MergedDataLoader",
    "VisitStatistics",
]
