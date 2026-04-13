#!/usr/bin/env node
/**
 * order-emr-detect CLI 入口点
 * 支持 detect, query, stats 命令
 */

import { Command } from 'commander';
import { DetectCommand } from './cli/commands/detect';
import { QueryCommand } from './cli/commands/query';
import { StatsCommand } from './cli/commands/stats';

const program = new Command();

program
  .name('order-emr-detect')
  .description('门诊医嘱-病程矛盾检测CLI工具')
  .version('1.0.0');

// 注册子命令
program.addCommand(DetectCommand);
program.addCommand(QueryCommand);
program.addCommand(StatsCommand);

program.parse(process.argv);