/**
 * Stats 命令 - 输出科室矛盾统计报表
 */
import { Command } from 'commander';
import * as fs from 'fs';
import * as path from 'path';
import chalk from 'chalk';

interface StatsOptions {
  input: string;
  format?: string;
  department?: string;
}

interface ContradictionDetail {
  patient_id: string;
  doctor_id: string;
  department: string;
  rule_type: string;
  severity: string;
  create_time: string;
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

interface DepartmentStats {
  department: string;
  total: number;
  high: number;
  medium: number;
  low: number;
  doctors: Set<string>;
  patients: Set<string>;
}

function findResultFiles(inputPath: string): string[] {
  if (fs.statSync(inputPath).isFile()) {
    if (inputPath.endsWith('.json')) {
      return [inputPath];
    }
    return [];
  }

  const outputDir = path.join(inputPath, 'alerts');
  if (!fs.existsSync(outputDir)) {
    return [];
  }

  return fs.readdirSync(outputDir)
    .filter(f => (f.startsWith('alerts_') || f.startsWith('contradictions_')) && f.endsWith('.json'))
    .map(f => path.join(outputDir, f));
}

function calculateStats(options: StatsOptions): DepartmentStats[] {
  const inputPath = options.input;
  const targetDept = options.department;

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

  const deptStats = new Map<string, DepartmentStats>();

  for (const file of resultFiles) {
    try {
      const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
      const alerts: AlertRecord[] = data.alerts || [];

      for (const alert of alerts) {
        // 按科室过滤
        if (targetDept && alert.department !== targetDept) {
          continue;
        }

        if (!deptStats.has(alert.department)) {
          deptStats.set(alert.department, {
            department: alert.department,
            total: 0,
            high: 0,
            medium: 0,
            low: 0,
            doctors: new Set(),
            patients: new Set(),
          });
        }

        const stats = deptStats.get(alert.department)!;
        stats.total += alert.contradiction_count;
        stats.high += alert.high_severity_count;
        stats.medium += alert.medium_severity_count;
        stats.low += alert.low_severity_count;

        // 收集医生和患者
        for (const detail of alert.details || []) {
          stats.doctors.add(detail.doctor_id);
          stats.patients.add(detail.patient_id);
        }
      }
    } catch (error) {
      continue;
    }
  }

  return Array.from(deptStats.values());
}

function outputStats(options: StatsOptions): void {
  const stats = calculateStats(options);

  if (options.format === 'csv') {
    // CSV format output
    console.log('科室,总矛盾数,高危,中危,低危,涉及医生数,涉及患者数');
    for (const s of stats) {
      console.log(`${s.department},${s.total},${s.high},${s.medium},${s.low},${s.doctors.size},${s.patients.size}`);
    }
    return;
  }

  // JSON format (default)
  const output = stats.map(s => ({
    department: s.department,
    total: s.total,
    high: s.high,
    medium: s.medium,
    low: s.low,
    doctor_count: s.doctors.size,
    patient_count: s.patients.size,
  }));

  console.log(JSON.stringify({
    summary: {
      total_contradictions: stats.reduce((sum, s) => sum + s.total, 0),
      total_departments: stats.length,
      total_high: stats.reduce((sum, s) => sum + s.high, 0),
      total_medium: stats.reduce((sum, s) => sum + s.medium, 0),
      total_low: stats.reduce((sum, s) => sum + s.low, 0),
    },
    by_department: output,
  }, null, 2));
}

function displayStatsSummary(options: StatsOptions): void {
  const stats = calculateStats(options);

  console.log(chalk.bold('\n========== 科室矛盾统计报表 ==========\n'));

  if (stats.length === 0) {
    console.log(chalk.yellow('  暂无统计数据'));
    console.log(chalk.bold('\n====================================\n'));
    return;
  }

  // 总体统计
  const totalContradictions = stats.reduce((sum, s) => sum + s.total, 0);
  const totalHigh = stats.reduce((sum, s) => sum + s.high, 0);
  const totalMedium = stats.reduce((sum, s) => sum + s.medium, 0);
  const totalLow = stats.reduce((sum, s) => sum + s.low, 0);

  console.log(chalk.bold('  总体统计:'));
  console.log(chalk.white(`    涉及科室数: ${chalk.cyan(stats.length.toString())}`));
  console.log(chalk.white(`    矛盾总数: ${chalk.bold(totalContradictions.toString())}`));
  console.log(chalk.red(`      高危: ${totalHigh}`));
  console.log(chalk.yellow(`      中危: ${totalMedium}`));
  console.log(chalk.blue(`      低危: ${totalLow}`));
  console.log();

  // 科室列表
  console.log(chalk.bold('  科室明细:\n'));
  console.log(chalk.bold(
    chalk.cyan('  科室              矛盾数   高危   中危   低危   医生数   患者数')
  ));
  console.log(chalk.gray('  ' + '-'.repeat(70)));

  // 按总数排序
  stats.sort((a, b) => b.total - a.total);

  for (const s of stats) {
    const deptName = s.department.substring(0, 10).padEnd(14);
    const total = s.total.toString().padStart(6);
    const high = s.high.toString().padStart(6);
    const medium = s.medium.toString().padStart(6);
    const low = s.low.toString().padStart(6);
    const doctorCount = s.doctors.size.toString().padStart(7);
    const patientCount = s.patients.size.toString().padStart(8);

    // 颜色标记高危科室
    const rowColor = s.high > 0 ? chalk.red : chalk.white;

    console.log(
      rowColor(`  ${deptName}`) +
      chalk.white(`${total}   `) +
      chalk.red(`${high}   `) +
      chalk.yellow(`${medium}   `) +
      chalk.blue(`${low}   `) +
      chalk.cyan(`${doctorCount}   `) +
      chalk.cyan(patientCount)
    );
  }

  console.log(chalk.gray('  ' + '-'.repeat(70)));

  // Top 3 高危科室
  const highRiskDepts = stats.filter(s => s.high > 0).sort((a, b) => b.high - a.high).slice(0, 3);

  if (highRiskDepts.length > 0) {
    console.log(chalk.bold('\n  高危科室提醒:'));
    highRiskDepts.forEach((dept, i) => {
      console.log(chalk.red(`    ${i + 1}. ${dept.department}: ${dept.high} 例高危矛盾`));
    });
  }

  console.log(chalk.bold('\n====================================\n'));

  // 如果是 table format (default), also output machine-readable format hint
  if (options.format !== 'csv' && options.format !== 'json') {
    console.log(chalk.gray(`  提示: 使用 --format json 或 --format csv 获取机器可读格式\n`));
  }
}

export const StatsCommand = new Command('stats')
  .description('输出科室矛盾统计报表')
  .requiredOption('--input <path>', '输入数据目录或文件路径')
  .option('--format <format>', '输出格式 (json|csv|table)', 'table')
  .option('--department <dept>', '按科室过滤')
  .action(async (options: StatsOptions) => {
    try {
      if (options.format === 'json' || options.format === 'csv') {
        outputStats(options);
      } else {
        displayStatsSummary(options);
      }
    } catch (error: any) {
      console.error(chalk.red('\n[错误] 统计生成失败!'));
      if (error.message) {
        console.error(chalk.red(error.message));
      }
      process.exit(1);
    }
  });

export default StatsCommand;