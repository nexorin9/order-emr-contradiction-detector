/**
 * Python后端HTTP客户端
 * Task 15: TypeScript/Node.js Web API：告警配置和Webhook推送端点
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import { AlertSummary } from '../types';

// Python后端URL配置
const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:5000';

/**
 * Webhook发送结果
 */
export interface WebhookResult {
  success: boolean;
  statusCode?: number;
  data?: any;
  error?: string;
}

/**
 * Python后端客户端
 */
export class PythonBackendClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor(baseURL?: string) {
    this.baseURL = baseURL || PYTHON_BACKEND_URL;
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }

  /**
   * 获取后端URL
   */
  getBaseURL(): string {
    return this.baseURL;
  }

  /**
   * 发送Webhook请求
   */
  async sendWebhook(url: string, payload: any): Promise<WebhookResult> {
    try {
      const response = await axios.post(url, payload, {
        timeout: 10000,
        headers: {
          'Content-Type': 'application/json'
        }
      });

      return {
        success: true,
        statusCode: response.status,
        data: response.data
      };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError;
        return {
          success: false,
          statusCode: axiosError.response?.status,
          error: axiosError.message
        };
      }
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      };
    }
  }

  /**
   * 推送告警到配置的Webhook
   */
  async pushAlert(webhookUrl: string, alertData: {
    event_type: string;
    timestamp: string;
    alert_summaries: AlertSummary[];
  }): Promise<WebhookResult> {
    return this.sendWebhook(webhookUrl, {
      ...alertData,
      service: 'order-emr-detect',
      source: 'web_api'
    });
  }

  /**
   * 调用Python检测CLI
   */
  async runDetection(hisPath: string, emrPath: string, outputDir?: string): Promise<{
    success: boolean;
    outputPath?: string;
    error?: string;
  }> {
    try {
      const { spawn } = require('child_process');
      const args = [
        '-m', 'src.py.cli',
        'detect',
        '--his', hisPath,
        '--emr', emrPath
      ];
      if (outputDir) {
        args.push('--output', outputDir);
      }

      return new Promise((resolve) => {
        const pythonProcess = spawn('python', args);

        let stdout = '';
        let stderr = '';

        pythonProcess.stdout.on('data', (data: Buffer) => {
          stdout += data.toString();
        });

        pythonProcess.stderr.on('data', (data: Buffer) => {
          stderr += data.toString();
        });

        pythonProcess.on('close', (code: number) => {
          if (code === 0) {
            resolve({
              success: true,
              outputPath: outputDir || 'data/output'
            });
          } else {
            resolve({
              success: false,
              error: stderr || stdout
            });
          }
        });
      });
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      };
    }
  }

  /**
   * 获取告警配置（从Python后端）
   */
  async getAlertConfig(): Promise<{
    success: boolean;
    data?: any;
    error?: string;
  }> {
    try {
      const response = await this.client.get('/api/alerts/config');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return {
          success: false,
          error: error.message
        };
      }
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      };
    }
  }

  /**
   * 更新告警配置（到Python后端）
   */
  async updateAlertConfig(config: any): Promise<{
    success: boolean;
    data?: any;
    error?: string;
  }> {
    try {
      const response = await this.client.put('/api/alerts/config', config);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        return {
          success: false,
          error: error.message
        };
      }
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      };
    }
  }
}

export default PythonBackendClient;