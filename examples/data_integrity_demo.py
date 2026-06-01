#!/usr/bin/env python3
"""
数据完整性检测演示
==================

演示如何使用 data_integrity_checker 检测论文数据中的可疑模式。

用法：
    python data_integrity_demo.py                    # 使用内置示例数据
    python data_integrity_demo.py --file your.xlsx   # 检测你的数据文件

三种检测方法：
    1. 尾数分布分析 — 真实数据尾数(0-9)应均匀分布
    2. 小数点一致性 — 固定小数位模式暗示人工构造
    3. 数据重复检测 — 独立实验中完全重复的数值极为罕见
"""

import sys
from pathlib import Path

# 确保能导入 scripts 模块
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from deep_evidence.data_forensics import check_data_integrity, IntegrityConfig


def demo_with_sample_data():
    """用内置的模拟数据演示检测流程。"""
    import pandas as pd
    import tempfile, os

    # 模拟一组"可疑"数据：尾数偏好 + 小数位重复 + 数值重复
    data = {
        "Control": [1.23, 2.53, 3.13, 4.83, 5.03, 6.33, 7.93, 8.43, 9.13, 10.63,
                    11.23, 12.53, 13.13, 14.83, 15.03, 16.33, 17.93, 18.43, 19.13, 20.63,
                    21.23, 22.53, 23.13, 24.83, 25.03, 26.33, 27.93, 28.43, 29.13, 30.63,
                    31.23, 32.53, 33.13, 34.83, 35.03],
        "Treatment": [1.45, 2.45, 3.45, 4.45, 5.45, 6.78, 7.78, 8.78, 9.78, 10.78,
                      11.45, 12.45, 13.45, 14.45, 15.45, 16.78, 17.78, 18.78, 19.78, 20.78,
                      21.45, 22.45, 23.45, 24.45, 25.45, 26.78, 27.78, 28.78, 29.78, 30.78,
                      31.45, 32.45, 33.45, 34.45, 35.45],
    }

    # 写入临时 Excel
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp_path = tmp.name
    tmp.close()
    pd.DataFrame(data).to_excel(tmp_path, index=False)

    print("=" * 60)
    print("数据完整性检测 — 内置示例数据演示")
    print("=" * 60)
    print(f"临时文件: {tmp_path}")
    print(f"数据特点: 尾数偏好(3/5/8)、小数位高度重复(.23/.45/.78)、数值多次重复")
    print()

    result = check_data_integrity(tmp_path)

    _print_result(result)

    # 清理
    os.unlink(tmp_path)


def demo_borderline_case():
    """用灰色地带数据演示：70% 均匀 + 30% 尾数偏好。

    这种数据更接近真实造假场景——不是 100% 明显，而是部分数据被人工修改。
    """
    import pandas as pd
    import tempfile, os
    import numpy as np

    rng = np.random.default_rng(42)

    # 70% 真实随机数据（尾数均匀）
    real_data = rng.uniform(1.0, 50.0, size=70).round(2)
    # 30% 人工构造数据（尾数偏好 3 和 7）
    fake_base = rng.uniform(1.0, 50.0, size=30)
    fake_data = []
    for v in fake_base:
        # 强制尾数为 3 或 7
        s = f"{v:.2f}"
        prefix = s[:-1]
        tail = rng.choice([3, 7])
        fake_data.append(float(prefix + str(tail)))

    combined = np.concatenate([real_data, np.array(fake_data)])
    rng.shuffle(combined)

    # 第二列：正常数据（对照组）
    normal_data = rng.uniform(10.0, 100.0, size=100).round(3)

    data = {"Measurement_A": combined, "Measurement_B": normal_data}

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp_path = tmp.name
    tmp.close()
    pd.DataFrame(data).to_excel(tmp_path, index=False)

    print("=" * 60)
    print("数据完整性检测 — 边界案例（70%正常 + 30%偏好）")
    print("=" * 60)
    print(f"临时文件: {tmp_path}")
    print(f"数据特点: Measurement_A 有30%尾数被人工改为3/7")
    print(f"          Measurement_B 完全随机（对照组）")
    print(f"预期结果: A列应被检出轻度-中度异常，B列应正常")
    print()

    result = check_data_integrity(tmp_path)
    _print_result(result)

    os.unlink(tmp_path)


def demo_with_file(file_path: str):
    """检测用户指定的数据文件。"""
    print("=" * 60)
    print(f"数据完整性检测 — {Path(file_path).name}")
    print("=" * 60)

    result = check_data_integrity(file_path)
    _print_result(result)


def _print_result(result: dict):
    """格式化输出检测结果。"""
    print(f"\n{'=' * 60}")
    print(f"检测结果")
    print(f"{'=' * 60}")
    print(f"风险评分:   {result['risk_score']}/100")
    print(f"风险等级:   {result['risk_level']}")
    print(f"异常总数:   {result['summary']['total_findings']}")
    print(f"  HIGH:     {result['summary']['high_severity']}")
    print(f"  MEDIUM:   {result['summary']['medium_severity']}")
    print(f"  LOW:      {result['summary']['low_severity']}")
    print(f"涉及方法:   {', '.join(result['summary']['methods_involved']) or '无'}")
    print(f"涉及数据列: {len(result['summary']['columns_involved'])}")

    if result["findings"]:
        print(f"\n{'=' * 60}")
        print(f"详细发现")
        print(f"{'=' * 60}")
        for i, f in enumerate(result["findings"], 1):
            print(f"\n[{i}] {f['severity']} — {f['method']}")
            print(f"    位置: {f['sheet']} / {f['column']}")
            print(f"    描述: {f['description']}")
            if f["statistics"]:
                for k, v in f["statistics"].items():
                    if k == "tail_distribution":
                        print(f"    {k}: {v}")
                    elif k == "top5":
                        print(f"    {k}: {v}")
                    else:
                        print(f"    {k}: {v}")

    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="数据完整性检测演示")
    parser.add_argument("--file", help="Excel 或 CSV 文件路径（不指定则使用内置示例数据）")
    parser.add_argument("--borderline", action="store_true",
                        help="运行边界案例演示（70%%正常 + 30%%偏好）")
    args = parser.parse_args()

    if args.file:
        demo_with_file(args.file)
    elif args.borderline:
        demo_borderline_case()
    else:
        demo_with_sample_data()
        print("\n" + "=" * 60)
        print("提示: 使用 --borderline 运行灰色地带案例演示")
        print("=" * 60)


if __name__ == "__main__":
    main()
