/**
 * Detect 命令 - 执行矛盾检测
 * 调用 Python CLI 执行实际检测逻辑
 */
import { Command } from 'commander';
import { execSync } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import chalk from 'chalk';

interface DetectOptions {
  his: string;
  emr: string;
  output?: string;
  rules?: string;
  timeWindow?: string;
  verbose?: boolean;
}

function findPythonCommand(): string {
  // 尝试多种 Python 命令
  const pythonCommands = ['python', 'python3', 'py'];
  for (const cmd of pythonCommands) {
    try {
      execSync(`${cmd} --version`, { stdio: 'ignore' });
      return cmd;
    } catch {
      continue;
    }
  }
  return 'python';
}

export const DetectCommand = new Command('detect')
  .description('执行医嘱-病程矛盾检测')
  .requiredOption('--his <path>', 'HIS医嘱数据文件路径 (CSV或JSON)')
  .requiredOption('--emr <path>', 'EMR病程记录数据文件路径 (CSV或JSON)')
  .option('--output <path>', '输出目录', 'data/output')
  .option('--rules <path>', '规则配置文件路径 (YAML)')
  .option('--time-window <minutes>', '时间窗口（分钟）', '30')
  .option('--verbose', '显示详细输出', false)
  .action(async (options: DetectOptions) => {
    const startTime = Date.now();

    console.log(chalk.bold('\n========== 门诊医嘱-病程矛盾检测 ==========\n'));

    // 验证输入文件
    console.log(chalk.blue('[1/5] 验证输入文件...'));

    if (!fs.existsSync(options.his)) {
      console.error(chalk.red(`[错误] HIS数据文件不存在: ${options.his}`));
      process.exit(1);
    }

    if (!fs.existsSync(options.emr)) {
      console.error(chalk.red(`[错误] EMR数据文件不存在: ${options.emr}`));
      process.exit(1);
    }

    if (options.rules && !fs.existsSync(options.rules)) {
      console.error(chalk.red(`[错误] 规则文件不存在: ${options.rules}`));
      process.exit(1);
    }

    console.log(chalk.green(`  ✓ HIS文件: ${options.his}`));
    console.log(chalk.green(`  ✓ EMR文件: ${options.emr}`));

    // 确保输出目录存在
    const outputDir = options.output || 'data/output';
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    // 构建 Python 命令
    console.log(chalk.blue('\n[2/5] 构建检测命令...'));

    const pythonCmd = findPythonCommand();
    const projectRoot = path.resolve(__dirname, '../../..');
    const cliPath = path.join(projectRoot, 'src', 'py', 'cli.py');

    // 构建参数
    const pythonArgs = [
      '-m', 'src.py.cli',
      'detect',
      '--his', options.his,
      '--emr', options.emr,
      '--output', outputDir,
    ];

    if (options.rules) {
      pythonArgs.push('--rules', options.rules);
    }

    if (options.timeWindow) {
      pythonArgs.push('--time-window', options.timeWindow);
    }

    console.log(chalk.gray(`  Python: ${pythonCmd}`));
    console.log(chalk.gray(`  命令: ${pythonArgs.join(' ')}`));

    // 执行 Python CLI
    console.log(chalk.blue('\n[3/5] 执行矛盾检测...\n'));

    try {
      // 切换到项目根目录执行
      const result = execSync(`${pythonCmd} ${pythonArgs.join(' ')}`, {
        cwd: projectRoot,
        encoding: 'utf-8',
        stdio: options.verbose ? 'inherit' : 'pipe',
        maxBuffer: 50 * 1024 * 1024, // 50MB buffer
      });

      if (options.verbose) {
        console.log(result);
      }
    } catch (error: any) {
      console.error(chalk.red('\n[错误] 检测执行失败!'));
      if (error.message) {
        console.error(chalk.red(error.message));
      }
      process.exit(1);
    }

    // 查找生成的结果文件
    console.log(chalk.blue('\n[4/5] 分析检测结果...'));

    try {
      const outputFiles = fs.readdirSync(outputDir)
        .filter(f => f.startsWith('contradictions_') && f.endsWith('.json'))
        .map(f => ({
          name: f,
          path: path.join(outputDir, f),
          time: fs.statSync(path.join(outputDir, f)).mtime.getTime()
        }))
        .sort((a, b) => b.time - a.time);

      if (outputFiles.length === 0) {
        console.error(chalk.red('[错误] 未找到检测结果文件'));
        process.exit(1);
      }

      const latestResult = outputFiles[0].path;
      const statsFile = latestResult.replace('contradictions_', 'stats_');

      // 读取并显示结果
      const resultData = JSON.parse(fs.readFileSync(latestResult, 'utf-8'));
      const statsData = fs.existsSync(statsFile)
        ? JSON.parse(fs.readFileSync(statsFile, 'utf-8'))
        : null;

      console.log(chalk.green('\n  ✓ 检测完成!\n'));

      // 显示摘要
      console.log(chalk.bold.green('========== 检测结果摘要 =========='));
      console.log(chalk.white(`  总矛盾数: ${chalk.bold(resultData.total_count)}`));

      if (statsData) {
        const severity = statsData.by_severity || {};
        console.log(chalk.red(`    - 高危: ${severity.high || 0}`));
        console.log(chalk.yellow(`    - 中危: ${severity.medium || 0}`));
        console.log(chalk.blue(`    - 低危: ${severity.low || 0}`));
        console.log(chalk.white(`  涉及患者数: ${statsData.unique_patients}`));
        console.log(chalk.white(`  涉及医生数: ${statsData.unique_doctors}`));
        console.log(chalk.white(`  涉及科室数: ${Object.keys(statsData.by_department || {}).length}`));
      }

      console.log(chalk.gray(`\n  结果文件: ${latestResult}`));
      if (statsData) {
        console.log(chalk.gray(`  统计文件: ${statsFile}`));
      }
      console.log(chalk.bold.green('==================================\n'));

      // 按科室显示前5名
      if (statsData && statsData.by_department) {
        const topDepts = Object.entries(statsData.by_department)
          .sort(([, a], [, b]) => (b as number) - (a as number))
          .slice(0, 5);

        if (topDepts.length > 0) {
          console.log(chalk.bold('  科室矛盾排名 (Top 5):'));
          topDepts.forEach(([dept, count], i) => {
            const bar = '█'.repeat(Math.min(Number(count), 20));
            console.log(chalk.cyan(`    ${i + 1}. ${dept}: ${count} ${bar}`));
          });
          console.log();
        }
      }

      // 按规则类型显示
      if (statsData && statsData.by_rule_type) {
        const ruleTypes = statsData.by_rule_type;
        console.log(chalk.bold('  按规则类型:'));
        for (const [rule, count] of Object.entries(ruleTypes)) {
          const label = rule === 'ordered_but_not_recorded'
            ? '开了没写'
            : rule === 'recorded_but_not_ordered'
              ? '写了没开'
              : rule;
          console.log(chalk.magenta(`    - ${label}: ${count}`));
        }
        console.log();
      }

    } catch (error: any) {
      console.error(chalk.red('\n[错误] 结果分析失败!'));
      if (error.message) {
        console.error(chalk.red(error.message));
      }
      process.exit(1);
    }

    // 完成
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(chalk.green(chalk.bold(`\n检测完成! 耗时: ${elapsed}s\n`)));
  });

export default DetectCommand;
