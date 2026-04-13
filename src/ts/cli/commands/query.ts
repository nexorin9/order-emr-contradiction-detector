/**
 * Query 命令 - 查询矛盾记录
 * 查询指定医生指定日期的矛盾记录
 */
import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import chalk from 'chalk';

interface QueryOptions {
  doctor: string;
  date: string;
  format?: string;
  input?: string;
}

interface ContradictionDetail {
  patient_id: string;
  doctor_id: string;
  department: string;
  rule_type: string;
  order_id?: string;
  record_id?: string;
  order_item_name?: string;
  record_keywords?: string[];
  severity: string;
  create_time: string;
  description?: string;
}

interface AlertRecord {
  doctor_id: string;
  department: string;
  contradiction_count: number;
  high_severity_count: number;
  medium_severity_count: number;
  low_severity_count: number;
  alert_level: string;
  details: ContradictionDetail[];
  detection_date: string;
}

function findResultFiles(inputPath: string): string[] {
  if (fs.statSync(inputPath).isFile()) {
    return [inputPath];
  }

  const outputDir = path.join(inputPath, 'alerts');
  if (!fs.existsSync(outputDir)) {
    return [];
  }

  return fs.readdirSync(outputDir)
    .filter(f => f.startsWith('alerts_') && f.endsWith('.json'))
    .map(f => path.join(outputDir, f));
}

function queryContradictions(options: QueryOptions): void {
  const inputPath = options.input || 'data/output';
  const targetDoctor = options.doctor;
  const targetDate = options.date;

  if (!fs.existsSync(inputPath)) {
    console.error(chalk.red(`[错误] 输入路径不存在: ${inputPath}`));
    process.exit(1);
  }

  const resultFiles = findResultFiles(inputPath);

  if (resultFiles.length === 0) {
    console.error(chalk.yellow('[警告] 未找到任何检测结果文件'));
    console.log(chalk.gray('提示: 请先运行 detect 命令生成检测结果'));
    process.exit(0);
  }

  // 收集所有匹配的记录
  const matchedRecords: ContradictionDetail[] = [];

  for (const file of resultFiles) {
    try {
      const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
      const alerts: AlertRecord[] = data.alerts || [];

      for (const alert of alerts) {
        // 按日期过滤
        if (alert.detection_date !== targetDate && !file.includes(targetDate.replace(/-/g, ''))) {
          continue;
        }

        // 遍历详细记录，按医生过滤 - detail可能没有doctor_id，需要用alert的doctor_id
        // 跳过汇总类记录（没有patient_id）
        for (const detail of alert.details || []) {
          if (!detail.patient_id) {
            continue; // 跳过汇总记录
          }

          const detailDoctorId = detail.doctor_id || alert.doctor_id;
          if (detailDoctorId !== targetDoctor && targetDoctor !== 'ALL') {
            continue;
          }

          // 收集详细记录
          matchedRecords.push({
            ...detail,
            doctor_id: detailDoctorId,
            department: detail.department || alert.department,
          });
        }
      }
    } catch (error) {
      // 跳过无法解析的文件
      continue;
    }
  }

  // 输出结果
  if (options.format === 'json') {
    console.log(JSON.stringify({
      doctor_id: targetDoctor,
      date: targetDate,
      total_count: matchedRecords.length,
      records: matchedRecords,
    }, null, 2));
    return;
  }

  // Table format (default)
  console.log(chalk.bold(`\n========== 矛盾记录查询结果 ==========\n`));
  console.log(chalk.white(`  医生ID: ${chalk.cyan(targetDoctor)}`));
  console.log(chalk.white(`  日期: ${chalk.cyan(targetDate)}`));
  console.log(chalk.white(`  匹配记录数: ${chalk.bold(matchedRecords.length.toString())}\n`));

  if (matchedRecords.length === 0) {
    console.log(chalk.green('  ✓ 未发现矛盾记录'));
    console.log(chalk.bold('\n====================================\n'));
    return;
  }

  // 按严重程度排序
  const severityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
  matchedRecords.sort((a, b) => (severityOrder[a.severity] || 0) - (severityOrder[b.severity] || 0));

  // 打印表头
  console.log(chalk.bold(
    chalk.cyan('  ID   科室          患者ID    类型              严重程度  时间')
  ));
  console.log(chalk.gray('  ' + '-'.repeat(80)));

  matchedRecords.forEach((record, index) => {
    const ruleTypeLabel = record.rule_type === 'ordered_but_not_recorded'
      ? '开了没写'
      : record.rule_type === 'recorded_but_not_ordered'
        ? '写了没开'
        : record.rule_type;

    const severityColor = record.severity === 'high'
      ? chalk.red
      : record.severity === 'medium'
        ? chalk.yellow
        : chalk.blue;

    const typeIndicator = record.rule_type === 'ordered_but_not_recorded' ? '↓×' : '↑×';

    console.log(
      chalk.white(`  ${(index + 1).toString().padStart(2)}   `) +
      chalk.white(`${(record.department || 'N/A').substring(0, 8).padEnd(10)}`) +
      chalk.white(`${record.patient_id.substring(0, 8).padEnd(10)}`) +
      chalk.white(`${typeIndicator} ${ruleTypeLabel.substring(0, 8).padEnd(8)}`) +
      severityColor(` ${record.severity.toUpperCase().padEnd(7)}`) +
      chalk.gray(` ${record.create_time.substring(0, 16)}`)
    );
  });

  console.log(chalk.gray('  ' + '-'.repeat(80)));

  // 统计摘要
  const highCount = matchedRecords.filter(r => r.severity === 'high').length;
  const mediumCount = matchedRecords.filter(r => r.severity === 'medium').length;
  const lowCount = matchedRecords.filter(r => r.severity === 'low').length;

  console.log(chalk.bold('\n  严重程度分布:'));
  console.log(chalk.red(`    高危: ${highCount}`));
  console.log(chalk.yellow(`    中危: ${mediumCount}`));
  console.log(chalk.blue(`    低危: ${lowCount}`));
  console.log(chalk.bold('\n====================================\n'));
}

export const QueryCommand = new Command('query')
  .description('查询指定医生指定日期的矛盾记录')
  .requiredOption('--doctor <id>', '医生ID (使用 ALL 查询所有医生)')
  .requiredOption('--date <date>', '日期 (YYYY-MM-DD)')
  .option('--format <format>', '输出格式 (table|json)', 'table')
  .option('--input <path>', '输入数据目录或文件路径', 'data/output')
  .action(async (options: QueryOptions) => {
    try {
      queryContradictions(options);
    } catch (error: any) {
      console.error(chalk.red('\n[错误] 查询失败!'));
      if (error.message) {
        console.error(chalk.red(error.message));
      }
      process.exit(1);
    }
  });

export default QueryCommand;