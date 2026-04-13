"""
自定义异常类模块

定义门诊医嘱-病程矛盾检测系统中使用的自定义异常类型。
所有异常均包含中文错误消息和建议操作，便于用户理解和处理。
"""

from typing import Optional, List


class OrderEmrDetectorError(Exception):
    """基础异常类"""

    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        if self.details:
            return f"{self.message}，详情: {self.details}"
        return self.message

    def get_user_message(self) -> str:
        """获取面向用户的友好错误消息"""
        return self.message

    def get_suggestion(self) -> Optional[str]:
        """获取问题处理建议"""
        return self.details.get("suggestion")


class DataFileNotFoundError(OrderEmrDetectorError):
    """数据文件不存在异常"""

    def __init__(self, file_path: str, file_type: str = "数据"):
        self.file_path = file_path
        self.file_type = file_type
        message = f"{file_type}文件不存在: {file_path}"
        suggestion = f"请确认文件路径是否正确，文件是否存在。可尝试使用绝对路径。"
        super().__init__(message, {
            "suggestion": suggestion,
            "file_path": file_path,
            "file_type": file_type,
            "error_code": "FILE_NOT_FOUND"
        })
        self.message = message

    def get_user_message(self) -> str:
        return f"找不到指定的{self.file_type}文件"


class DataFormatError(OrderEmrDetectorError):
    """数据格式错误异常"""

    def __init__(
        self,
        file_path: str,
        error_details: str,
        row_number: Optional[int] = None,
        expected_format: Optional[str] = None
    ):
        self.file_path = file_path
        self.row_number = row_number
        self.expected_format = expected_format

        if row_number:
            message = f"文件格式错误 [{file_path}] 第{row_number}行: {error_details}"
        else:
            message = f"文件格式错误 [{file_path}]: {error_details}"

        # 根据文件类型提供更具体的建议
        if file_path.lower().endswith('.csv'):
            suggestion = "CSV格式要求：表头行包含必需字段，数据行不含空行。请检查第" + \
                        (f"{row_number}行" if row_number else "各行") + "的数据是否完整。"
        elif file_path.lower().endswith('.json'):
            suggestion = "JSON格式要求：顶层为数组，或包含orders/records/data等键的对象。"
        else:
            suggestion = "请确认文件为CSV或JSON格式，且编码为UTF-8。"

        if expected_format:
            suggestion += f"\n期望格式: {expected_format}"

        super().__init__(message, {
            "suggestion": suggestion,
            "file_path": file_path,
            "row_number": row_number,
            "error_details": error_details,
            "expected_format": expected_format,
            "error_code": "DATA_FORMAT_ERROR"
        })
        self.message = message

    def get_user_message(self) -> str:
        if self.row_number:
            return f"CSV/JSON文件第{self.row_number}行格式不正确"
        return f"文件格式不正确，请检查{self.file_path}的格式是否正确"


class DataValidationError(OrderEmrDetectorError):
    """数据校验失败异常"""

    def __init__(self, field: str, value: str, reason: str, valid_values: Optional[List[str]] = None):
        self.field = field
        self.value = value
        self.reason = reason
        self.valid_values = valid_values

        message = f"数据校验失败: 字段「{field}」的值「{value}」不符合要求 - {reason}"

        if valid_values:
            suggestion = f"字段「{field}」的有效值为: {', '.join(valid_values)}"
        else:
            suggestion = f"请检查字段「{field}」的值是否符合要求"

        super().__init__(message, {
            "suggestion": suggestion,
            "field": field,
            "value": value,
            "reason": reason,
            "valid_values": valid_values,
            "error_code": "DATA_VALIDATION_ERROR"
        })
        self.message = message


class MissingRequiredFieldError(DataFormatError):
    """缺少必需字段异常"""

    # CSV必需字段映射
    HIS_REQUIRED_FIELDS = ["order_id", "patient_id", "doctor_id", "department", "order_type", "item_name", "create_time"]
    EMR_REQUIRED_FIELDS = ["record_id", "patient_id", "doctor_id", "department", "record_type", "create_time"]

    def __init__(self, file_path: str, missing_fields: List[str], row_number: Optional[int] = None):
        self.missing_fields = missing_fields
        fields_str = "、".join(f"「{f}」" for f in missing_fields)

        if row_number:
            message = f"文件 [{file_path}] 第{row_number}行缺少必需字段: {fields_str}"
        else:
            message = f"文件 [{file_path}] 缺少必需字段: {fields_str}"

        # 根据文件类型提供具体指导
        if file_path.lower().endswith('.csv'):
            if all(f in self.HIS_REQUIRED_FIELDS for f in missing_fields):
                suggestion = f"HIS医嘱CSV必需字段: {', '.join(self.HIS_REQUIRED_FIELDS)}。请在CSV表头行添加以上缺失字段。"
            elif all(f in self.EMR_REQUIRED_FIELDS for f in missing_fields):
                suggestion = f"EMR病程记录CSV必需字段: {', '.join(self.EMR_REQUIRED_FIELDS)}。请在CSV表头行添加以上缺失字段。"
            else:
                suggestion = f"请在CSV表头行添加以下必需字段: {', '.join(missing_fields)}"
        else:
            suggestion = f"请在JSON数据中添加以下必需字段: {', '.join(missing_fields)}"

        super().__init__(file_path, message, row_number)
        self.message = message
        # 重新设置details中的suggestion
        self.details["suggestion"] = suggestion
        self.details["error_code"] = "MISSING_REQUIRED_FIELD"

    def get_user_message(self) -> str:
        if self.row_number:
            return f"CSV表头缺少必需字段: {'、'.join(self.missing_fields)}"
        return f"文件缺少必需字段: {'、'.join(self.missing_fields)}"


class MergeConflictError(OrderEmrDetectorError):
    """数据合并冲突异常"""

    def __init__(self, patient_id: str, conflict_type: str, details: str):
        self.patient_id = patient_id
        self.conflict_type = conflict_type

        message = f"患者[{patient_id}]的就诊数据存在冲突 ({conflict_type}): {details}"
        suggestion = "请检查该患者的数据是否存在重复录入或时间逻辑错误（如医嘱时间晚于病程记录）"
        super().__init__(message, {
            "suggestion": suggestion,
            "patient_id": patient_id,
            "conflict_type": conflict_type,
            "details": details,
            "error_code": "MERGE_CONFLICT"
        })
        self.message = message


class EmptyDataError(OrderEmrDetectorError):
    """数据为空异常"""

    def __init__(self, data_type: str, source: str):
        self.data_type = data_type
        self.source = source

        message = f"{data_type}数据为空或未找到有效记录: {source}"

        if "HIS" in data_type:
            suggestion = "请检查HIS数据文件是否存在且包含有效医嘱数据。"
        elif "EMR" in data_type or "病程" in data_type:
            suggestion = "请检查EMR数据文件是否存在且包含有效病程记录。"
        else:
            suggestion = "请检查数据文件是否包含有效数据。"

        super().__init__(message, {
            "suggestion": suggestion,
            "data_type": data_type,
            "source": source,
            "error_code": "EMPTY_DATA"
        })
        self.message = message

    def get_user_message(self) -> str:
        return f"未找到有效的{self.data_type}数据，请检查数据文件是否正确"


class RuleLoadError(OrderEmrDetectorError):
    """规则加载异常"""

    def __init__(self, rule_file: str, error_details: str):
        self.rule_file = rule_file

        message = f"规则文件加载失败 [{rule_file}]: {error_details}"
        suggestion = "请检查规则YAML文件格式是否正确，语法是否符合YAML规范。可使用在线YAML验证工具检查。"
        super().__init__(message, {
            "suggestion": suggestion,
            "rule_file": rule_file,
            "error_details": error_details,
            "error_code": "RULE_LOAD_ERROR"
        })
        self.message = message


class DetectionError(OrderEmrDetectorError):
    """检测执行异常"""

    def __init__(self, stage: str, error_details: str, recoverable: bool = False):
        self.stage = stage
        self.recoverable = recoverable

        stage_descriptions = {
            "data_loading": "数据加载",
            "time_alignment": "时间对齐",
            "rule_matching": "规则匹配",
            "contradiction_detection": "矛盾检测",
            "report_generation": "报告生成",
        }

        stage_name = stage_descriptions.get(stage, stage)
        message = f"{stage_name}阶段执行失败: {error_details}"

        if recoverable:
            suggestion = f"系统可在跳过错误数据后继续执行。请检查输入数据是否正确，或联系技术支持。"
        else:
            suggestion = "请检查输入数据是否正确，或联系技术支持。"

        super().__init__(message, {
            "suggestion": suggestion,
            "stage": stage,
            "stage_name": stage_name,
            "error_details": error_details,
            "recoverable": recoverable,
            "error_code": "DETECTION_ERROR"
        })
        self.message = message


class ConfigurationError(OrderEmrDetectorError):
    """配置错误异常"""

    def __init__(self, config_item: str, error_details: str, config_file: Optional[str] = None):
        self.config_item = config_item
        self.config_file = config_file

        message = f"配置项「{config_item}」错误: {error_details}"
        if config_file:
            suggestion = f"请检查配置文件{config_file}中「{config_item}」的值是否正确。"
        else:
            suggestion = f"请检查配置项「{config_item}」的值是否正确。"

        super().__init__(message, {
            "suggestion": suggestion,
            "config_item": config_item,
            "config_file": config_file,
            "error_details": error_details,
            "error_code": "CONFIGURATION_ERROR"
        })
        self.message = message


class APIError(OrderEmrDetectorError):
    """API调用异常"""

    def __init__(self, endpoint: str, status_code: int, response_body: str):
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_body = response_body

        message = f"API调用失败 [{endpoint}]: HTTP {status_code}"
        suggestion = f"请检查网络连接和API服务是否正常运行。状态码{status_code}表示: "

        if status_code == 400:
            suggestion += "请求参数错误"
        elif status_code == 401:
            suggestion += "认证失败，请检查API密钥"
        elif status_code == 403:
            suggestion += "权限不足"
        elif status_code == 404:
            suggestion += "API端点不存在"
        elif status_code == 500:
            suggestion += "服务器内部错误"
        elif status_code >= 500:
            suggestion += "服务端错误，请稍后重试"
        else:
            suggestion += "请检查API文档确认正确的请求方式"

        super().__init__(message, {
            "suggestion": suggestion,
            "endpoint": endpoint,
            "status_code": status_code,
            "response_body": response_body,
            "error_code": "API_ERROR"
        })
        self.message = message
