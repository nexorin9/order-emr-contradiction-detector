/**
 * Express API 服务器
 * Task 14: TypeScript/Node.js Web API服务：Express服务器
 */

import express, { Express, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import path from 'path';
import { Contradiction, ApiResponse, AlertSummary } from '../types';
import alertsRouter from './routes/alerts';

// 内存存储（实际项目中应连接数据库）
let contradictions: Contradiction[] = [];
let alertSummaries: AlertSummary[] = [];

// 标准化错误代码枚举
enum ErrorCode {
  // 通用错误
  INTERNAL_ERROR = 'INTERNAL_ERROR',
  INVALID_REQUEST = 'INVALID_REQUEST',
  NOT_FOUND = 'NOT_FOUND',
  SERVER_ERROR = 'SERVER_ERROR',

  // 检测相关错误
  MISSING_PARAMS = 'MISSING_PARAMS',
  FILE_NOT_FOUND = 'FILE_NOT_FOUND',
  DETECTION_FAILED = 'DETECTION_FAILED',
  INVALID_FILE_PATH = 'INVALID_FILE_PATH',

  // 矛盾记录相关错误
  CONTRADICTION_NOT_FOUND = 'CONTRADICTION_NOT_FOUND',
  UPDATE_FAILED = 'UPDATE_FAILED',

  // 统计相关错误
  NO_DATA_FOUND = 'NO_DATA_FOUND',
  STATS_CALCULATION_FAILED = 'STATS_CALCULATION_FAILED',
}

// 错误响应接口（包含建议）
interface ErrorResponseData {
  success: false;
  error: string;
  error_code: string;
  suggestion?: string;
}

// 错误响应辅助函数（带建议）
function errorResponse(res: Response, statusCode: number, error: string, errorCode: ErrorCode, suggestion?: string): void {
  const response: ErrorResponseData = {
    success: false,
    error,
    error_code: errorCode
  };
  if (suggestion) {
    response.suggestion = suggestion;
  }
  res.status(statusCode).json(response);
}

// 分页参数接口
interface PaginationParams {
  page: number;
  limit: number;
}

// 过滤参数接口
interface FilterParams {
  department?: string;
  doctor_id?: string;
  severity?: string;
  start_date?: string;
  end_date?: string;
  resolved?: string;
}

/**
 * 创建Express应用
 */
export function createApp(): Express {
  const app = express();

  // 中间件
  app.use(cors());
  app.use(express.json());

  // 静态文件服务
  app.use(express.static(path.join(__dirname, '../../public')));

  // 请求日志中间件
  app.use((req: Request, _res: Response, next: NextFunction) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
    next();
  });

  // 健康检查端点
  app.get('/health', (_req: Request, res: Response) => {
    res.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      service: 'order-emr-detect-api'
    });
  });

  // POST /api/detect - 接收HIS和EMR数据文件路径，执行检测，返回矛盾列表JSON
  app.post('/api/detect', (req: Request, res: Response) => {
    try {
      const { his_path, emr_path, output_dir } = req.body;

      if (!his_path || !emr_path) {
        errorResponse(res, 400, '缺少必需参数：his_path 和 emr_path', ErrorCode.MISSING_PARAMS, '请在请求body中提供 his_path（HIS医嘱数据文件路径）和 emr_path（EMR病程记录文件路径）参数');
        return;
      }

      // 调用Python检测逻辑（这里用子进程调用，实际项目中可以导入Python模块）
      const { spawn } = require('child_process');
      const pythonProcess = spawn('python', [
        '-m', 'src.py.cli',
        'detect',
        '--his', his_path,
        '--emr', emr_path,
        '--output', output_dir || 'data/output'
      ]);

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
          // 假设检测结果写入到output目录，从那里读取
          const fs = require('fs');
          const path = require('path');
          const outputPath = path.join(output_dir || 'data/output', 'contradictions.json');

          if (fs.existsSync(outputPath)) {
            const results = JSON.parse(fs.readFileSync(outputPath, 'utf-8'));
            contradictions = results.contradictions || [];
            res.json({
              success: true,
              data: {
                count: contradictions.length,
                contradictions: contradictions
              }
            } as ApiResponse<{ count: number; contradictions: Contradiction[] }>);
          } else {
            res.json({
              success: true,
              data: {
                count: 0,
                contradictions: []
              }
            } as ApiResponse<{ count: number; contradictions: Contradiction[] }>);
          }
        } else {
          errorResponse(res, 500, `检测执行失败: ${stderr || stdout}`, ErrorCode.DETECTION_FAILED, '请检查HIS和EMR数据文件路径是否正确，数据格式是否为CSV或JSON编码是否为UTF-8');
        }
      });
    } catch (error) {
      errorResponse(res, 500, error instanceof Error ? error.message : '未知错误', ErrorCode.INTERNAL_ERROR, '检测执行遇到意外错误，请检查输入数据是否正确或联系技术支持');
    }
  });

  // GET /api/contradictions - 支持分页和过滤参数
  app.get('/api/contradictions', (req: Request, res: Response) => {
    try {
      const { page = '1', limit = '20', department, doctor_id, severity, start_date, end_date, resolved } = req.query;

      const pageNum = parseInt(page as string, 10);
      const limitNum = parseInt(limit as string, 10);

      // 应用过滤
      let filtered = contradictions.filter(c => {
        if (department && c.department !== department) return false;
        if (doctor_id && c.doctor_id !== doctor_id) return false;
        if (severity && c.severity !== severity) return false;
        if (resolved !== undefined && String(c.resolved) !== resolved) return false;
        if (start_date && c.create_time < start_date) return false;
        if (end_date && c.create_time > end_date) return false;
        return true;
      });

      // 计算分页
      const total = filtered.length;
      const totalPages = Math.ceil(total / limitNum);
      const startIndex = (pageNum - 1) * limitNum;
      const endIndex = startIndex + limitNum;

      const paginatedResults = filtered.slice(startIndex, endIndex);

      res.json({
        success: true,
        data: {
          contradictions: paginatedResults,
          pagination: {
            page: pageNum,
            limit: limitNum,
            total: total,
            total_pages: totalPages
          }
        }
      } as ApiResponse<{ contradictions: Contradiction[]; pagination: any }>);
    } catch (error) {
      errorResponse(res, 500, error instanceof Error ? error.message : '未知错误', ErrorCode.INTERNAL_ERROR, '查询矛盾列表时遇到错误，请稍后重试或联系技术支持');
    }
  });

  // PUT /api/contradictions/:id/resolve - 标记矛盾为已整改
  app.put('/api/contradictions/:id/resolve', (req: Request, res: Response) => {
    try {
      const { id } = req.params;
      const { resolved, resolution_note } = req.body;

      // 查找矛盾记录
      const index = contradictions.findIndex(c => c.id === id);

      if (index === -1) {
        errorResponse(res, 404, `未找到指定的矛盾记录 (ID: ${id})`, ErrorCode.CONTRADICTION_NOT_FOUND, '请确认矛盾记录ID是否正确，可通过 GET /api/contradictions 查询现有矛盾记录');
        return;
      }

      // 更新矛盾记录
      contradictions[index] = {
        ...contradictions[index],
        resolved: resolved !== undefined ? resolved : true,
        resolved_time: resolved ? new Date().toISOString() : undefined,
        resolution_note: resolution_note || contradictions[index].resolution_note
      } as Contradiction & { resolved_time?: string; resolution_note?: string };

      res.json({
        success: true,
        data: contradictions[index],
        message: resolved ? '矛盾已标记为已整改' : '矛盾已标记为未整改'
      } as ApiResponse<Contradiction>);
    } catch (error) {
      errorResponse(res, 500, error instanceof Error ? error.message : '更新失败', ErrorCode.UPDATE_FAILED, '更新矛盾记录状态时出错，请稍后重试或联系技术支持');
    }
  });

  // 挂载告警路由
  app.use('/api/alerts', alertsRouter);

  // GET /api/stats/summary - 返回科室级统计汇总
  app.get('/api/stats/summary', (req: Request, res: Response) => {
    try {
      // 按科室汇总
      const deptStats = new Map<string, {
        department: string;
        total: number;
        high: number;
        medium: number;
        low: number;
        resolved: number;
        unresolved: number;
      }>();

      contradictions.forEach(c => {
        const existing = deptStats.get(c.department) || {
          department: c.department,
          total: 0,
          high: 0,
          medium: 0,
          low: 0,
          resolved: 0,
          unresolved: 0
        };

        existing.total++;
        if (c.severity === 'high') existing.high++;
        else if (c.severity === 'medium') existing.medium++;
        else existing.low++;

        if (c.resolved) existing.resolved++;
        else existing.unresolved++;

        deptStats.set(c.department, existing);
      });

      // 按矛盾数降序排列
      const summary = Array.from(deptStats.values()).sort((a, b) => b.total - a.total);

      // 告警级别计算
      const alertSummariesResult: AlertSummary[] = summary.map(s => ({
        doctor_id: '',
        department: s.department,
        contradiction_count: s.total,
        high_severity_count: s.high,
        alert_level: s.high >= 5 ? 'critical' : s.total >= 10 ? 'warning' : 'info'
      }));

      alertSummaries = alertSummariesResult;

      res.json({
        success: true,
        data: {
          summary: summary,
          alert_summaries: alertSummariesResult,
          overall: {
            total_contradictions: contradictions.length,
            total_departments: summary.length,
            critical_departments: alertSummariesResult.filter(a => a.alert_level === 'critical').length,
            warning_departments: alertSummariesResult.filter(a => a.alert_level === 'warning').length
          }
        }
      } as ApiResponse<any>);
    } catch (error) {
      errorResponse(res, 500, error instanceof Error ? error.message : '统计计算失败', ErrorCode.STATS_CALCULATION_FAILED, '统计汇总计算时出错，请确保已有检测数据或联系技术支持');
    }
  });

  // 错误处理中间件
  app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
    console.error('[Error]', err.message);
    errorResponse(res, 500, err.message, ErrorCode.SERVER_ERROR, '服务器内部错误，请查看服务器日志或联系技术支持');
  });

  // 404处理
  app.use((_req: Request, res: Response) => {
    errorResponse(res, 404, '请求的API端点不存在', ErrorCode.NOT_FOUND, '请检查API端点URL是否正确，可用的端点包括：/health, /api/detect, /api/contradictions, /api/stats/summary, /api/alerts/config');
  });

  return app;
}

/**
 * 启动服务器
 */
export function startServer(port: number = 3000): void {
  const app = createApp();
  app.listen(port, () => {
    console.log(`[${new Date().toISOString()}] 服务器启动，监听端口 ${port}`);
    console.log(`健康检查: http://localhost:${port}/health`);
    console.log(`矛盾检测: POST http://localhost:${port}/api/detect`);
    console.log(`矛盾列表: GET http://localhost:${port}/api/contradictions`);
    console.log(`统计汇总: GET http://localhost:${port}/api/stats/summary`);
    console.log(`告警配置: GET/PUT http://localhost:${port}/api/alerts/config`);
    console.log(`测试Webhook: POST http://localhost:${port}/api/alerts/test`);
  });
}

// 如果直接运行此文件，则启动服务器
if (require.main === module) {
  const port = parseInt(process.env.PORT || '3000', 10);
  startServer(port);
}