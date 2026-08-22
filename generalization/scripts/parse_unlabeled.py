# -*- coding: utf-8 -*-
"""
重写无标签配方解析器：兼容两种表结构
====================================
结构A（配比方案/环氧）：序号 | 原料代码 | 用量1 | 用量2 | ...
结构B（聚酯金黄）：      原料代码 | 用量1 | 用量2 | ...
自动识别代码列；同一样本内重复原料合并用量。
"""
import pickle, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

def is_num(v):
    return isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v))

def parse_sheet(df):
    """解析单个sheet，返回配方列表 [{组分:{code:amt}}]"""
    # 找原料数据区：从第2行起，逐行判断是否为原料行
    # 原料行特征：至少2个数值列，且代码列(第0或第1列)为短文本
    ing_rows = []
    for i in range(1, len(df)):
        row = df.iloc[i]
        c0 = row[0]
        c1 = row[1] if len(row) > 1 else None
        # 判断代码列：c0非数值且短文本 → c0是代码；c0是数值(序号)且c1是短文本 → c1是代码
        c0_txt = str(c0).strip() if pd.notna(c0) else ''
        c1_txt = str(c1).strip() if pd.notna(c1) else ''
        c0_is_num = is_num(c0)
        c1_is_num = is_num(c1)
        # 跳过明显非原料行
        if not c0_txt or len(c0_txt) > 20:
            continue
        # 跳过元数据行（含中文长文本）
        if c0_is_num and (not c1_txt or len(c1_txt) > 20):
            continue
        if not c0_is_num and len(c0_txt) > 20:
            continue
        # 取代码与数值列
        if c0_is_num and c1_txt and not c1_is_num:
            code = c1_txt
            nums = [v for v in row[2:] if is_num(v) and v > 0]
        elif not c0_is_num and c0_txt:
            code = c0_txt
            nums = [v for v in row[1:] if is_num(v) and v > 0]
        else:
            continue
        if not nums:
            continue
        ing_rows.append((code, nums))
    if not ing_rows:
        return []
    n_var = max(len(n) for _, n in ing_rows)
    formulas = []
    for v in range(n_var):
        comp = {}
        for code, nums in ing_rows:
            if v < len(nums):
                comp[code] = comp.get(code, 0.0) + float(nums[v])
        if comp:
            formulas.append(comp)
    return formulas

def parse_formulation_sheets(path, system):
    xl = pd.ExcelFile(path)
    all_formulas = []
    for s in xl.sheet_names:
        df = xl.parse(s, header=None)
        for comp in parse_sheet(df):
            all_formulas.append({'配方ID': f'{system}-{s}-{len(all_formulas)+1}', '体系': system, '组分': comp})
    return all_formulas

import sys, os
if __name__ == '__main__':
    # 用法: python parse_unlabeled.py <配比方案.xlsx> [聚酯金黄.xlsx ...] [-o 输出.pkl]
    # 每个输入文件按体系名解析；体系名取文件名前缀（去掉扩展名）
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    out = 'unlabeled_formulas.pkl'
    if '-o' in sys.argv:
        out = sys.argv[sys.argv.index('-o') + 1]
    if not args:
        print('用法: python parse_unlabeled.py <配方文件1.xlsx> [配方文件2.xlsx ...] [-o 输出.pkl]')
        sys.exit(1)
    all_formulas = []
    for f in args:
        system = os.path.splitext(os.path.basename(f))[0]
        fs = parse_formulation_sheets(f, system)
        print(f"{system}: 配方数 {len(fs)}")
        all_formulas += fs
    print("无标签配方总数:", len(all_formulas))

# 统计原料代码
all_codes = set()
for f in all_formulas:
    all_codes.update(f['组分'].keys())
print(f"原料代码 {len(all_codes)} 种:", sorted(all_codes))

# 检查示例
print("\n示例1:", all_formulas[0]['配方ID'], dict(list(all_formulas[0]['组分'].items())[:8]))
print("示例2:", all_formulas[-1]['配方ID'], dict(list(all_formulas[-1]['组分'].items())[:8]))

with open(out, 'wb') as fh:
    pickle.dump({'formulas': all_formulas}, fh)
print(f"\n已保存 {out}")
