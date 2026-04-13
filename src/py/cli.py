"""
门诊医嘱-病程矛盾检测系统 Python CLI

支持命令：
- python -m src.py.cli detect --his <file> --emr <file> --output <dir>
- python -m src.py.cli stats --input <dir>
- python -m src.py.cli alert-config --show
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径，以便导入 src.py 模块
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.py.data.merged_loader import MergedDataLoader
from src.py.engine.contradiction_engine import ContradictionDetector
from src.py.engine.alert_engine import AlertEngine, AlertConfig
from src.py.rules.rule_definitions import RuleDefinitionsLoader
from src.py.exceptions import (
    OrderEmrDetectorError,
    DataFileNotFoundError,
    DataFormatError,
    EmptyDataError,
    MissingRequiredFieldError,
)
from src.py.cli_output import CLIOutput, cli_error, cli_warning, cli_success, cli_info


def cmd_detect(args):
    """执行矛盾检测命令"""
    cli_info("开始矛盾检测")
    cli_info(f"HIS数据: {args.his}")
    cli_info(f"EMR数据: {args.emr}")
    cli_info(f"输出目录: {args.output}")

    # 验证输入文件存在
    if not os.path.exists(args.his):
        cli_error(
            f"HIS数据文件不存在: {args.his}",
            suggestion="请确认文件路径正确，文件是否存在。可尝试使用绝对路径。"
        )
        return 1

    if not os.path.exists(args.emr):
        cli_error(
            f"EMR数据文件不存在: {args.emr}",
            suggestion="请确认文件路径正确，文件是否存在。可尝试使用绝对路径。"
        )
        return 1

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    # 加载规则文件（如果提供）
    rules_loader = None
    if args.rules:
        if os.path.exists(args.rules):
            cli_info(f"加载规则文件: {args.rules}")
            rules_loader = RuleDefinitionsLoader(args.rules)
            rules_loader.load()
        else:
            cli_warning(
                f"规则文件不存在: {args.rules}",
                details="将使用默认规则继续执行"
            )

    # 加载数据
    cli_info("正在加载数据...")
    loader = MergedDataLoader(time_window_minutes=args.time_window or 30)
    try:
        patient_visits = loader.load(his_data=args.his, emr_data=args.emr)
        cli_success(f"成功加载 {len(patient_visits)} 条患者就诊记录")
    except DataFileNotFoundError as e:
        cli_error(
            f"找不到HIS或EMR数据文件",
            suggestion=e.get_suggestion()
        )
        return 1
    except MissingRequiredFieldError as e:
        cli_error(
            e.get_user_message(),
            suggestion=e.get_suggestion()
        )
        return 1
    except DataFormatError as e:
        cli_error(
            e.get_user_message(),
            suggestion=e.get_suggestion()
        )
        return 1
    except EmptyDataError as e:
        cli_error(
            e.get_user_message(),
            suggestion=e.get_suggestion()
        )
        return 1
    except OrderEmrDetectorError as e:
        cli_error(
            f"数据加载失败: {e.message}",
            suggestion=e.get_suggestion()
        )
        return 1
    except Exception as e:
        cli_error(
            f"数据加载失败（未知错误）",
            suggestion=f"错误信息: {str(e)}。请检查数据文件格式是否正确。"
        )
        return 1

    if not patient_visits:
        cli_warning("未找到任何患者就诊记录", details="请检查HIS和EMR数据文件是否包含有效数据")
        return 0

    # 执行矛盾检测
    cli_info("正在执行矛盾检测...")
    detector = ContradictionDetector(
        rules_loader=rules_loader,
        time_window_minutes=args.time_window or 30,
    )

    try:
        contradictions = detector.detect(
            patient_visits=patient_visits,
            rules_file_path=args.rules,
        )
        cli_success(f"检测完成，发现 {len(contradictions)} 条矛盾记录")
    except Exception as e:
        cli_error(
            f"矛盾检测执行失败",
            suggestion=f"错误信息: {str(e)}。请检查输入数据是否正确。"
        )
        return 1

    # 生成检测结果文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(args.output, f"contradictions_{timestamp}.json")
    stats_file = os.path.join(args.output, f"stats_{timestamp}.json")

    # 保存矛盾详情
    contradictions_data = [c.to_dict() for c in contradictions]
    result_data = {
        "generated_at": datetime.now().isoformat(),
        "total_count": len(contradictions),
        "his_file": args.his,
        "emr_file": args.emr,
        "time_window_minutes": args.time_window or 30,
        "contradictions": contradictions_data,
    }

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    cli_success(f"矛盾详情已保存", details=result_file)

    # 生成统计摘要
    stats = detector.get_summary_stats(contradictions)
    stats_data = {
        "generated_at": datetime.now().isoformat(),
        "total": stats["total"],
        "by_severity": stats["by_severity"],
        "by_rule_type": stats["by_rule_type"],
        "by_department": stats["by_department"],
        "by_doctor": stats["by_doctor"],
        "unique_patients": stats["unique_patients"],
        "unique_doctors": stats["unique_doctors"],
    }

    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, ensure_ascii=False, indent=2)

    cli_success(f"统计摘要已保存", details=stats_file)

    # 打印摘要到控制台
    CLIOutput.header("检测结果摘要")
    CLIOutput.table(
        ["指标", "数值"],
        [
            ["总矛盾数", str(stats['total'])],
            ["高危矛盾", str(stats['by_severity']['high'])],
            ["中危矛盾", str(stats['by_severity']['medium'])],
            ["低危矛盾", str(stats['by_severity']['low'])],
            ["涉及患者数", str(stats['unique_patients'])],
            ["涉及医生数", str(stats['unique_doctors'])],
            ["涉及科室数", str(len(stats['by_department']))],
        ]
    )

    # 如果有告警配置且启用，也生成告警
    alert_config_path = os.path.join(project_root, ".config", "config.yaml")
    if os.path.exists(alert_config_path):
        try:
            alert_config = AlertConfig.from_yaml(alert_config_path)
            if alert_config.enabled:
                cli_info("正在生成告警...")
                alert_engine = AlertEngine(config=alert_config)
                alerts = alert_engine.generate_alerts(contradictions)
                if alerts:
                    alert_engine.process_alerts(alerts)
                    cli_success(f"已生成 {len(alerts)} 条告警")
                else:
                    cli_info("无需生成告警")
        except Exception as e:
            cli_warning(f"告警生成失败: {str(e)}")

    return 0


def cmd_stats(args):
    """输出统计报表命令"""
    cli_info("开始生成统计报表")
    cli_info(f"输入目录: {args.input}")
    cli_info(f"输出格式: {args.format}")

    # 查找最新的矛盾结果文件
    input_path = Path(args.input)
    if not input_path.exists():
        cli_error(
            f"输入目录不存在: {args.input}",
            suggestion="请确认目录路径正确，目录是否存在。"
        )
        return 1

    # 查找所有 JSON 文件
    json_files = list(input_path.glob("contradictions_*.json"))
    if not json_files:
        cli_error(
            f"在 {args.input} 中未找到矛盾结果文件",
            suggestion="请先运行 detect 命令生成检测结果。"
        )
        return 1

    # 获取最新的文件
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    cli_info(f"读取文件: {latest_file}")

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        cli_error(
            f"文件读取失败: {str(e)}",
            suggestion="请检查文件是否可读，格式是否为有效的JSON。"
        )
        return 1

    contradictions = data.get("contradictions", [])
    if not contradictions:
        cli_info("无矛盾记录")
        return 0

    # 计算统计
    total = len(contradictions)
    by_severity = {"high": 0, "medium": 0, "low": 0}
    by_rule_type = {}
    by_department = {}
    by_doctor = {}

    for c in contradictions:
        # 按严重程度
        severity = c.get("severity", "medium")
        if severity in by_severity:
            by_severity[severity] += 1

        # 按规则类型
        rule_type = c.get("rule_type", "unknown")
        by_rule_type[rule_type] = by_rule_type.get(rule_type, 0) + 1

        # 按科室
        dept = c.get("department", "未知")
        by_department[dept] = by_department.get(dept, 0) + 1

        # 按医生
        doctor = c.get("doctor_id", "未知")
        by_doctor[doctor] = by_doctor.get(doctor, 0) + 1

    # 输出统计
    if args.format == "json":
        stats_output = {
            "generated_at": datetime.now().isoformat(),
            "source_file": str(latest_file),
            "total": total,
            "by_severity": by_severity,
            "by_rule_type": by_rule_type,
            "by_department": by_department,
            "by_doctor": by_doctor,
            "unique_patients": len(set(c.get("patient_id") for c in contradictions)),
            "unique_doctors": len(by_doctor),
        }
        print(json.dumps(stats_output, ensure_ascii=False, indent=2))
    else:
        # CSV 格式 - 使用彩色输出
        CLIOutput.header("矛盾统计报表")
        print(f"数据来源: {latest_file}")
        print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        CLIOutput.table(
            ["严重程度", "数量"],
            [
                ["高危", str(by_severity['high'])],
                ["中危", str(by_severity['medium'])],
                ["低危", str(by_severity['low'])],
            ]
        )

        print()

        # 按规则类型
        rule_rows = [[rt, str(count)] for rt, count in sorted(by_rule_type.items(), key=lambda x: -x[1])]
        if rule_rows:
            CLIOutput.table(["规则类型", "数量"], rule_rows)

        print()

        # 按科室
        dept_rows = [[dept, str(count)] for dept, count in sorted(by_department.items(), key=lambda x: -x[1])]
        if dept_rows:
            CLIOutput.table(["科室", "矛盾数"], dept_rows)

        print()

        # 按医生（前10）
        doctor_rows = [[doctor, str(count)] for doctor, count in sorted(by_doctor.items(), key=lambda x: -x[1])[:10]]
        if doctor_rows:
            CLIOutput.table(["医生ID", "矛盾数"], doctor_rows)

        # 也输出 CSV 格式到控制台
        print("\n--- CSV 格式 ---")
        print("type,name,count")
        for rt, count in by_rule_type.items():
            print(f"rule_type,{rt},{count}")
        for dept, count in by_department.items():
            print(f"department,{dept},{count}")
        for doctor, count in sorted(by_doctor.items(), key=lambda x: -x[1])[:20]:
            print(f"doctor,{doctor},{count}")

    return 0


def cmd_alert_config(args):
    """显示/修改告警配置命令"""
    alert_config_path = os.path.join(project_root, ".config", "config.yaml")

    if args.show:
        # 显示当前告警配置
        cli_info("加载告警配置...")

        if os.path.exists(alert_config_path):
            try:
                config = AlertConfig.from_yaml(alert_config_path)
                CLIOutput.header("告警配置")
                CLIOutput.table(
                    ["配置项", "值"],
                    [
                        ["启用状态", "启用" if config.enabled else "禁用"],
                        ["医生日阈值", str(config.doctor_daily_threshold)],
                        ["科室日阈值", str(config.department_daily_threshold)],
                        ["高危阈值", str(config.high_severity_threshold)],
                        ["Webhook", "启用" if config.webhook_enabled else "禁用"],
                        ["Webhook URL", config.webhook_url if config.webhook_enabled else "未配置"],
                        ["文件输出", "启用" if config.file_output_enabled else "禁用"],
                        ["输出目录", config.output_dir if config.file_output_enabled else "未配置"],
                    ]
                )
                print("\n告警级别配置:")
                for level, threshold in config.alert_levels.items():
                    cli_info(f"  {level}: >= {threshold} 条矛盾")
                print()
            except Exception as e:
                cli_error(
                    f"配置加载失败: {str(e)}",
                    suggestion="请检查配置文件格式是否正确。"
                )
                return 1
        else:
            cli_warning(
                f"配置文件不存在: {alert_config_path}",
                details="将使用默认配置"
            )
            default_config = AlertConfig()
            CLIOutput.header("默认告警配置")
            CLIOutput.table(
                ["配置项", "值"],
                [
                    ["启用状态", "启用" if default_config.enabled else "禁用"],
                    ["医生日阈值", str(default_config.doctor_daily_threshold)],
                    ["科室日阈值", str(default_config.department_daily_threshold)],
                    ["高危阈值", str(default_config.high_severity_threshold)],
                ]
            )
            print()
            return 0

    if args.set_threshold:
        # 设置医生日阈值
        try:
            threshold = int(args.set_threshold)
            cli_info(f"告警阈值暂不支持运行时修改")
            cli_info(f"请编辑 .config/config.yaml 文件来修改配置")
            cli_info(f"建议阈值: {threshold}")
        except ValueError:
            cli_error(
                f"无效的阈值: {args.set_threshold}",
                suggestion="阈值必须为整数"
            )
            return 1

    return 0


def main():
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        description="门诊医嘱-病程矛盾实时检测系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 执行矛盾检测
  python -m src.py.cli detect --his data/his_orders.csv --emr data/emr_records.csv --output data/output

  # 查看统计报表
  python -m src.py.cli stats --input data/output

  # 查看告警配置
  python -m src.py.cli alert-config --show
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # detect 命令
    parser_detect = subparsers.add_parser(
        "detect",
        help="执行矛盾检测",
        description="对齐HIS医嘱数据和EMR病程记录时间戳，检测存在性矛盾"
    )
    parser_detect.add_argument(
        "--his",
        required=True,
        help="HIS医嘱数据文件路径 (CSV或JSON)"
    )
    parser_detect.add_argument(
        "--emr",
        required=True,
        help="EMR病程记录数据文件路径 (CSV或JSON)"
    )
    parser_detect.add_argument(
        "--output",
        required=True,
        help="输出目录路径"
    )
    parser_detect.add_argument(
        "--rules",
        help="规则文件路径 (YAML)，可选"
    )
    parser_detect.add_argument(
        "--time-window",
        type=int,
        help="时间窗口（分钟），默认30"
    )
    parser_detect.set_defaults(func=cmd_detect)

    # stats 命令
    parser_stats = subparsers.add_parser(
        "stats",
        help="输出统计报表",
        description="从检测结果生成统计报表"
    )
    parser_stats.add_argument(
        "--input",
        required=True,
        help="包含矛盾结果文件的目录路径"
    )
    parser_stats.add_argument(
        "--format",
        choices=["json", "csv"],
        default="csv",
        help="输出格式，默认csv"
    )
    parser_stats.set_defaults(func=cmd_stats)

    # alert-config 命令
    parser_alert = subparsers.add_parser(
        "alert-config",
        help="告警配置管理",
        description="查看或修改告警配置"
    )
    parser_alert.add_argument(
        "--show",
        action="store_true",
        help="显示当前告警配置"
    )
    parser_alert.add_argument(
        "--set-threshold",
        help="设置医生日告警阈值（暂不支持）"
    )
    parser_alert.set_defaults(func=cmd_alert_config)

    # 解析参数
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # 执行对应命令
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)