/**
 * 告警配置和Webhook端点
 * Task 15: TypeScript/Node.js Web API：告警配置和Webhook推送端点
 */

import { Router, Request, Response } from 'express';
import axios from 'axios';
import { ApiResponse, AlertSummary } from '../../types';
import { PythonBackendClient } from '../client';

const router = Router();

// 告警配置接口
export interface AlertConfig {
  time_window_minutes: number;
  alert_threshold: number;
  severity_thresholds: {
    high: number;
    medium: number;
    low: number;
  };
  webhook_url: string;
  webhook_enabled: boolean;
  auto_resolve_days: number;
}

// 默认告警配置
let alertConfig: AlertConfig = {
  time_window_minutes: 30,
  alert_threshold: 5,
  severity_thresholds: {
    high: 3,
    medium: 5,
    low: 10
  },
  webhook_url: '',
  webhook_enabled: false,
  auto_resolve_days: 7
};

/**
 * GET /api/alerts/config - 获取告警配置
 */
router.get('/config', (_req: Request, res: Response) => {
  res.json({
    success: true,
    data: alertConfig
  } as ApiResponse<AlertConfig>);
});

/**
 * PUT /api/alerts/config - 更新告警阈值
 */
router.put('/config', (req: Request, res: Response) => {
  try {
    const updates = req.body;

    // 验证并更新配置
    if (typeof updates.time_window_minutes === 'number') {
      alertConfig.time_window_minutes = updates.time_window_minutes;
    }
    if (typeof updates.alert_threshold === 'number') {
      alertConfig.alert_threshold = updates.alert_threshold;
    }
    if (typeof updates.webhook_url === 'string') {
      alertConfig.webhook_url = updates.webhook_url;
    }
    if (typeof updates.webhook_enabled === 'boolean') {
      alertConfig.webhook_enabled = updates.webhook_enabled;
    }
    if (typeof updates.auto_resolve_days === 'number') {
      alertConfig.auto_resolve_days = updates.auto_resolve_days;
    }
    if (updates.severity_thresholds) {
      if (typeof updates.severity_thresholds.high === 'number') {
        alertConfig.severity_thresholds.high = updates.severity_thresholds.high;
      }
      if (typeof updates.severity_thresholds.medium === 'number') {
        alertConfig.severity_thresholds.medium = updates.severity_thresholds.medium;
      }
      if (typeof updates.severity_thresholds.low === 'number') {
        alertConfig.severity_thresholds.low = updates.severity_thresholds.low;
      }
    }

    res.json({
      success: true,
      data: alertConfig,
      message: '告警配置已更新'
    } as ApiResponse<AlertConfig>);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : '未知错误',
      error_code: 'UPDATE_CONFIG_FAILED',
      suggestion: '更新配置时遇到错误，请检查请求参数格式是否正确'
    } as ApiResponse<null>);
  }
});

/**
 * POST /api/alerts/test - 发送测试Webhook
 */
router.post('/test', async (req: Request, res: Response) => {
  try {
    const { webhook_url } = req.body;

    // 如果请求中没有提供webhook_url，使用当前配置
    const targetUrl = webhook_url || alertConfig.webhook_url;

    if (!targetUrl) {
      res.status(400).json({
        success: false,
        error: '未配置Webhook URL',
        error_code: 'WEBHOOK_URL_MISSING',
        suggestion: '请在请求body中提供webhook_url参数，或先通过 PUT /api/alerts/config 配置Webhook URL'
      } as ApiResponse<null>);
      return;
    }

    // 构建测试payload
    const testPayload = {
      event_type: 'test',
      timestamp: new Date().toISOString(),
      service: 'order-emr-detect',
      test: true,
      alert_summaries: [{
        doctor_id: 'TEST_DOCTOR_001',
        department: '测试科室',
        contradiction_count: 3,
        high_severity_count: 1,
        alert_level: 'warning'
      } as AlertSummary
      ] as AlertSummary[]
    };

    // 发送测试Webhook
    const client = new PythonBackendClient();
    const result = await client.sendWebhook(targetUrl, testPayload);

    if (result.success) {
      res.json({
        success: true,
        data: {
          webhook_url: targetUrl,
          status_code: result.statusCode,
          response_body: result.data
        },
        message: '测试Webhook发送成功'
      } as ApiResponse<any>);
    } else {
      res.status(502).json({
        success: false,
        error: `Webhook请求失败: ${result.error}`,
        error_code: 'WEBHOOK_REQUEST_FAILED',
        suggestion: '请检查Webhook URL是否可访问，以及目标服务器是否正常运行'
      } as ApiResponse<null>);
    }
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : '未知错误',
      error_code: 'WEBHOOK_TEST_FAILED',
      suggestion: 'Webhook测试时遇到意外错误，请检查网络连接或稍后重试'
    } as ApiResponse<null>);
  }
});

/**
 * 获取当前告警配置（供其他模块使用）
 */
export function getAlertConfig(): AlertConfig {
  return alertConfig;
}

/**
 * 设置告警配置（供其他模块使用）
 */
export function setAlertConfig(config: Partial<AlertConfig>): void {
  alertConfig = { ...alertConfig, ...config };
}

export default router;