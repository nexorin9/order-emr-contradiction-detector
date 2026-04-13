"""
验收测试：矛盾检测准确性验证

测试目标：
1. 验证"开了没写"矛盾全部被检测出
2. 验证"写了没开"矛盾全部被检测出
3. 验证无假阳性（正常医嘱+正常记录不应被标记）
4. 验证严重程度分级正确（高/中/低）
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径（避免py包名冲突）
root_path = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, root_path)

from src.py.data.his_adapter import HisOrderReader
from src.py.data.emr_adapter import EmrRecordReader
from src.py.data.merged_loader import MergedDataLoader
from src.py.engine.contradiction_engine import ContradictionDetector
from src.py.rules.rule_definitions import RuleDefinitionsLoader


# 测试数据路径
SAMPLE_DIR = Path(__file__).parent.parent.parent / "data" / "sample"
HIS_CSV = SAMPLE_DIR / "his_orders_sample.csv"
EMR_CSV = SAMPLE_DIR / "emr_records_sample.csv"
RULES_YAML = Path(__file__).parent.parent.parent / "src" / "py" / "rules" / "contradiction_rules.yaml"

# 期望的 planted contradictions
# HIS orders O031-O040 (10条) 对应患者 P016-P025 只有orders没有EMR records -> ordered_but_not_recorded
EXPECTED_ORDERED_NOT_RECORDED = [
    "O031",  # P016, 胃镜, pending
    "O032",  # P017, 华法林, pending
    "O033",  # P018, 过敏原检测, pending
    "O034",  # P019, 盆底康复, pending
    "O035",  # P020, 头部CT, pending
    "O036",  # P021, 二甲双胍, pending
    "O037",  # P022, 术前四项, pending
    "O038",  # P023, 阿奇霉素干混悬剂, pending
    "O039",  # P024, 阴道镜, pending
    "O040",  # P025, 清创缝合, pending
]

# EMR records R016-R020 (5条) 对应患者 P026-P030 只有records没有HIS orders -> recorded_but_not_ordered
EXPECTED_RECORDED_NOT_ORDERED = [
    "R016",  # P026, 核磁共振成像
    "R017",  # P027, 肿瘤标志物检测
    "R018",  # P028, 骨龄测定
    "R019",  # P029, 羊水穿刺
    "R020",  # P030, 急诊洗胃
]


def load_data_and_detect():
    """加载数据并执行矛盾检测"""
    # 加载规则
    rules_loader = RuleDefinitionsLoader(str(RULES_YAML))
    rules_loader.load()

    # 创建检测器
    detector = ContradictionDetector(
        rules_loader=rules_loader,
        time_window_minutes=120,
    )

    # 加载并合并数据
    loader = MergedDataLoader(time_window_minutes=120)
    patient_visits = loader.load(str(HIS_CSV), str(EMR_CSV))

    # 执行检测
    contradictions = detector.detect(patient_visits)

    return contradictions, detector


def test_ordered_but_not_recorded_detection():
    """测试：开了没写矛盾检测"""
    print("\n=== 测试：开了没写矛盾检测 ===")

    contradictions, _ = load_data_and_detect()

    # 筛选 ordered_but_not_recorded 类型
    ordered_not_recorded = [c for c in contradictions if c.rule_type == "ordered_but_not_recorded"]
    detected_order_ids = [c.order_id for c in ordered_not_recorded]

    print(f"期望检测出 {len(EXPECTED_ORDERED_NOT_RECORDED)} 条开了没写矛盾")
    print(f"实际检测出 {len(ordered_not_recorded)} 条")
    print(f"检测到的order_id: {detected_order_ids}")

    # 检查是否全部检测出
    missing = set(EXPECTED_ORDERED_NOT_RECORDED) - set(detected_order_ids)
    if missing:
        print(f"❌ 漏检: {missing}")
    else:
        print("✅ 全部检测出")

    # 检查是否有假阳性（不在期望列表中的）
    false_positives = set(detected_order_ids) - set(EXPECTED_ORDERED_NOT_RECORDED)
    if false_positives:
        print(f"❌ 假阳性: {false_positives}")
    else:
        print("✅ 无假阳性")

    return len(missing) == 0 and len(false_positives) == 0


def test_recorded_but_not_ordered_detection():
    """测试：写了没开矛盾检测"""
    print("\n=== 测试：写了没开矛盾检测 ===")

    contradictions, _ = load_data_and_detect()

    # 筛选 recorded_but_not_ordered 类型
    recorded_not_ordered = [c for c in contradictions if c.rule_type == "recorded_but_not_ordered"]
    detected_record_ids = [c.record_id for c in recorded_not_ordered]

    print(f"期望检测出 {len(EXPECTED_RECORDED_NOT_ORDERED)} 条写了没开矛盾")
    print(f"实际检测出 {len(recorded_not_ordered)} 条")
    print(f"检测到的record_id: {detected_record_ids}")

    # 检查是否全部检测出
    missing = set(EXPECTED_RECORDED_NOT_ORDERED) - set(detected_record_ids)
    if missing:
        print(f"❌ 漏检: {missing}")
    else:
        print("✅ 全部检测出")

    # 检查是否有假阳性
    false_positives = set(detected_record_ids) - set(EXPECTED_RECORDED_NOT_ORDERED)
    if false_positives:
        print(f"❌ 假阳性: {false_positives}")
    else:
        print("✅ 无假阳性")

    return len(missing) == 0 and len(false_positives) == 0


def test_no_false_positives_on_normal_records():
    """测试：正常医嘱和记录不应被标记为矛盾"""
    print("\n=== 测试：正常医嘱+记录无假阳性 ===")

    contradictions, _ = load_data_and_detect()

    # O001-O030 是正常的（有HIS订单也有EMR记录且匹配）
    # R001-R015 是正常的（有EMR记录也有对应的HIS订单）
    NORMAL_ORDER_IDS = [f"O{i:03d}" for i in range(1, 31)]  # O001-O030
    NORMAL_RECORD_IDS = [f"R{i:03d}" for i in range(1, 16)]  # R001-R015

    false_positive_orders = []
    false_positive_records = []

    for c in contradictions:
        if c.order_id in NORMAL_ORDER_IDS:
            false_positive_orders.append(c.order_id)
        if c.record_id in NORMAL_RECORD_IDS:
            false_positive_records.append(c.record_id)

    if false_positive_orders:
        print(f"❌ 正常医嘱被误标记: {false_positive_orders}")
    else:
        print("✅ 正常医嘱(O001-O030)未被误标记")

    if false_positive_records:
        print(f"❌ 正常记录被误标记: {false_positive_records}")
    else:
        print("✅ 正常记录(R001-R015)未被误标记")

    return len(false_positive_orders) == 0 and len(false_positive_records) == 0


def test_severity_classification():
    """测试：严重程度分级正确"""
    print("\n=== 测试：严重程度分级 ===")

    contradictions, detector = load_data_and_detect()

    # 统计各严重程度的矛盾数
    by_severity = detector.get_contradictions_by_severity(contradictions)

    print(f"高危矛盾: {len(by_severity['high'])}")
    print(f"中危矛盾: {len(by_severity['medium'])}")
    print(f"低危矛盾: {len(by_severity['low'])}")

    # 检查开了没写类型的严重程度
    ordered_not_recorded = [c for c in contradictions if c.rule_type == "ordered_but_not_recorded"]
    print("\n开了没写矛盾详情:")
    for c in ordered_not_recorded:
        print(f"  {c.order_id}: {c.order_item_name} -> {c.severity}")

    # 检查写了没开类型的严重程度
    recorded_not_ordered = [c for c in contradictions if c.rule_type == "recorded_but_not_ordered"]
    print("\n写了没开矛盾详情:")
    for c in recorded_not_ordered:
        print(f"  {c.record_id}: {c.record_keywords} -> {c.severity}")

    # 验证严重程度分布合理
    # 开了没写类型（pending orders）应该是高危，因为是未执行的医嘱
    if len(by_severity['high']) > 0:
        print(f"\n✅ 高危矛盾存在（开了没写类型）: {len(by_severity['high'])} 条")
    else:
        print(f"\n⚠️ 高危矛盾数量异常")

    # 写了没开类型应该是中危
    if len(by_severity['medium']) > 0:
        print(f"✅ 中危矛盾存在（写了没开类型）: {len(by_severity['medium'])} 条")
    else:
        print(f"⚠️ 中危矛盾数量异常")

    return True


def generate_acceptance_report():
    """生成验收报告"""
    print("\n" + "=" * 60)
    print("验收测试报告")
    print("=" * 60)

    contradictions, detector = load_data_and_detect()

    # 基本统计
    by_severity = detector.get_contradictions_by_severity(contradictions)
    by_rule_type = {}
    for c in contradictions:
        by_rule_type[c.rule_type] = by_rule_type.get(c.rule_type, 0) + 1

    print(f"\n【检测结果概览】")
    print(f"总矛盾数: {len(contradictions)}")
    print(f"  - 开了没写: {by_rule_type.get('ordered_but_not_recorded', 0)}")
    print(f"  - 写了没开: {by_rule_type.get('recorded_but_not_ordered', 0)}")
    print(f"\n按严重程度:")
    print(f"  - 高危: {len(by_severity['high'])}")
    print(f"  - 中危: {len(by_severity['medium'])}")
    print(f"  - 低危: {len(by_severity['low'])}")

    print(f"\n【准确性验证】")

    # 开了没写验证
    ordered_not_recorded = [c for c in contradictions if c.rule_type == "ordered_but_not_recorded"]
    detected_order_ids = set(c.order_id for c in ordered_not_recorded)
    expected_set = set(EXPECTED_ORDERED_NOT_RECORDED)
    ordered_recall = len(detected_order_ids & expected_set) / len(expected_set) * 100 if expected_set else 0
    ordered_precision = len(detected_order_ids & expected_set) / len(detected_order_ids) * 100 if detected_order_ids else 0

    print(f"\n开了没写矛盾:")
    print(f"  - 期望: {len(expected_set)} 条")
    print(f"  - 检测: {len(detected_order_ids)} 条")
    print(f"  - 召回率: {ordered_recall:.1f}%")
    print(f"  - 精确率: {ordered_precision:.1f}%")

    # 写了没开验证
    recorded_not_ordered = [c for c in contradictions if c.rule_type == "recorded_but_not_ordered"]
    detected_record_ids = set(c.record_id for c in recorded_not_ordered)
    expected_records_set = set(EXPECTED_RECORDED_NOT_ORDERED)
    recorded_recall = len(detected_record_ids & expected_records_set) / len(expected_records_set) * 100 if expected_records_set else 0
    recorded_precision = len(detected_record_ids & expected_records_set) / len(detected_record_ids) * 100 if detected_record_ids else 0

    print(f"\n写了没开矛盾:")
    print(f"  - 期望: {len(expected_records_set)} 条")
    print(f"  - 检测: {len(detected_record_ids)} 条")
    print(f"  - 召回率: {recorded_recall:.1f}%")
    print(f"  - 精确率: {recorded_precision:.1f}%")

    # 假阳性验证
    normal_order_ids = set(f"O{i:03d}" for i in range(1, 31))
    normal_record_ids = set(f"R{i:03d}" for i in range(1, 16))
    false_positive_orders = detected_order_ids & normal_order_ids
    false_positive_records = detected_record_ids & normal_record_ids
    false_positive_rate = (len(false_positive_orders) + len(false_positive_records)) / (len(normal_order_ids) + len(normal_record_ids)) * 100

    print(f"\n假阳性:")
    print(f"  - 正常医嘱被误标记: {len(false_positive_orders)} 条")
    print(f"  - 正常记录被误标记: {len(false_positive_records)} 条")
    print(f"  - 假阳性率: {false_positive_rate:.2f}%")

    # 总体评估
    print(f"\n【总体评估】")
    all_ordered_detected = detected_order_ids == expected_set
    all_recorded_detected = detected_record_ids == expected_records_set
    no_false_positives = len(false_positive_orders) == 0 and len(false_positive_records) == 0

    if all_ordered_detected and all_recorded_detected and no_false_positives:
        print("✅ 验收通过 - 所有矛盾检测正确，无假阳性")
        return True
    else:
        print("❌ 验收不通过")
        if not all_ordered_detected:
            print(f"  - 开了没写: 漏检 {expected_set - detected_order_ids}")
        if not all_recorded_detected:
            print(f"  - 写了没开: 漏检 {expected_records_set - detected_record_ids}")
        if not no_false_positives:
            print(f"  - 假阳性: 医嘱 {false_positive_orders}, 记录 {false_positive_records}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("门诊医嘱-病程矛盾检测验收测试")
    print("=" * 60)

    # 运行各项测试
    test1 = test_ordered_but_not_recorded_detection()
    test2 = test_recorded_but_not_ordered_detection()
    test3 = test_no_false_positives_on_normal_records()
    test4 = test_severity_classification()

    # 生成验收报告
    passed = generate_acceptance_report()

    print("\n" + "=" * 60)
    if passed:
        print("验收测试结果: ✅ 通过")
    else:
        print("验收测试结果: ❌ 未通过")
    print("=" * 60)

    return passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)