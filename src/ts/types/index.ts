/**
 * 共享类型定义
 */

/**
 * HIS医嘱数据
 */
export interface HisOrder {
  order_id: string;
  patient_id: string;
  doctor_id: string;
  department: string;
  order_type: string;
  item_name: string;
  create_time: string;
  execute_time: string;
  status: string;
}

/**
 * EMR病程记录
 */
export interface EmrRecord {
  record_id: string;
  patient_id: string;
  doctor_id: string;
  department: string;
  record_type: string;
  content_keywords: string[];
  create_time: string;
}

/**
 * 矛盾检测结果
 */
export interface Contradiction {
  id: string;
  patient_id: string;
  doctor_id: string;
  department: string;
  rule_type: 'ordered_but_not_recorded' | 'recorded_but_not_ordered';
  order_id?: string;
  record_id?: string;
  record_type?: string;
  item_name?: string;
  keywords?: string;
  execute_time?: string;
  create_time: string;
  severity: 'high' | 'medium' | 'low';
  resolved: boolean;
  resolved_time?: string;
  resolution_note?: string;
}

/**
 * 告警汇总
 */
export interface AlertSummary {
  doctor_id: string;
  department: string;
  contradiction_count: number;
  high_severity_count: number;
  alert_level: 'critical' | 'warning' | 'info';
}

/**
 * API响应基础结构
 */
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  error_code?: string;
}