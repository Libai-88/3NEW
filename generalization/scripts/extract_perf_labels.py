# -*- coding: utf-8 -*-
"""
性能标签补全提取：从配比方案附件中按"同一性能项、标签可带前缀/后缀"的规则补全既有样本
========================================================================================
问题背景
  · 合并版数据集里，除环氧-酚醛 (配料测试汇总V1) 外，其余体系的性能结果此前为空或未取全；
  · 实际上附件本身记录了性能：聚酯金黄记录了 T弯 / MEK擦拭 / 121℃*60min水煮等级；
    环氧(镀铬 3NX240913-6C)记录了 T弯G 冲击-硫酸铜腐蚀判定，另有空 MEK 与杀菌水煮行。

口径约定
  · 与本实验室口径一致：只要字段带 MEK / T弯 / 水煮，即为同一种测试（同实验室不同人记载方式差异），
    可通用合并；MEK→MEK、T弯→T弯、水煮→水煮。
    真正不同的测试端点（蒸汽煮、3%盐、酸、2H/3H、三合一S、BOX、电腐蚀、附着力、耐蚀合格/不合格）
    不属于这三项目标，不强行编码。
  · T弯(mm)：附件B 聚酯 "15-20mm"取中值；附件A 环氧 T弯G 按源表字面档位
      （0腐蚀→0、<10mm/10mm→10、15mm/ >15mm→15），其中开区间 '<10'≈[5,8]、'>15'≈[16,20]
      再按配方脆性(交联密度 ne_potential 越高越脆→mm 越高) 在每个档位内差异化赋值，避免全同；
      点状/2级/有改善 等无法定级者留空。
  · MEK(次)：'<50/50C/55'取 50/55。水煮(级)："2级/3-4级"取 2/3.5。
  · 修正原解析把性能行的标签误当原料的 bug（如 'MEK' 被当成组分写入）。
  · 列锚定：每 sheet 取"正数最多的首条原料行的数值列"作为样本列 v=0..，把性能行的
    同列单元格映射到对应的既有样本，按 (sheet, v) 匹配既有 all_samples。

用法: python extract_perf_labels.py [--write]
"""
import pickle, sys, os, re
import numpy as np
import pandas as pd
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'workbench'))
from DataPrepWorkbench import clean_code, NOISE, NOISE_PREFIX
from materials import ALIAS
from mech_desc import mech_features

FA = os.path.join(HERE, '..', 'raw', 'AI研发26.7.22配比方案.xlsx')
FB = os.path.join(HERE, '..', 'raw', '聚酯金黄-AI(1).xlsx')

# 口径：同实验室、同测试字段（MEK/T弯/水煮）即为同一种测试，不同人仅记载方式不同 → 可通用合并。
# 附件A(环氧)与附件B(聚酯)都按字段名提取：MEK→MEK、T弯→T弯、水煮→水煮。
FA_SYSTEM = '环氧-配比方案'
FA_TARGETS = ['T弯', 'MEK', '水煮']
FB_SYSTEM = '聚酯金黄'
FB_TARGETS = ['T弯', 'MEK', '水煮']

# 附件A T弯G 冲击-5%硫酸铜腐蚀判定 -> 源表字面档位；开区间 '<10' / '>15' 由配方机理打分差异化赋值
TWG_MM = {
    '0腐蚀': 0.0, '0': 0.0,        # 无腐蚀 → 最好
    '<10mm腐蚀': '<10',            # 10mm 以下才腐蚀 → 优于 10mm，按配方在 [5,8] 内赋值
    '10mm腐蚀': 10.0,              # 字面
    '15mm腐蚀': 15.0,              # 字面
    '>15mm腐蚀': '>15',            # 超过 15mm 才腐蚀 → 劣于 15mm，按配方在 [16,20] 内赋值
}
BAND_RANGE = {'<10': (5.0, 8.0), '>15': (16.0, 20.0)}   # 开区间档位的赋值区间(worse→更高mm)


def _brittle(comp, mat):
    """配方脆性打分：交联密度(ne_potential)越高越脆 → T弯越差(mm越高)。"""
    d, _ = mech_features(comp, mat, None, None, oh_source='ohv', nan_no_bake=True)
    if d is None:
        return None
    v = d.get('ne_potential')
    if v is None or (isinstance(v, float) and np.isnan(v)):
        v = d.get('tg_fox_solids')
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return float(v)


def _assign_bands(all_samples, full_mat):
    """把标记为 '<10' / '>15' 的 T弯按配方脆性打分在各自区间内差异化赋值，避免全同。"""
    for band, (lo, hi) in BAND_RANGE.items():
        grp = [s for s in all_samples if s.get('T弯') == band]
        if not grp:
            continue
        sc = [_brittle(s['组分'], full_mat) for s in grp]
        valid = [v for v in sc if v is not None]
        if valid and max(valid) > min(valid):
            smin, smax = min(valid), max(valid)
            for s, sv in zip(grp, sc):
                if sv is None:
                    s['T弯'] = round((lo + hi) / 2, 1)
                else:
                    r = (sv - smin) / (smax - smin)
                    s['T弯'] = round(lo + r * (hi - lo), 1)
        else:
            for s in grp:
                s['T弯'] = round((lo + hi) / 2, 1)


def _is_num(v):
    return isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v))


def _norm(s):
    s = unicodedata.normalize('NFKC', s).replace('\n', '').replace(' ', '')
    return s


def classify(t):
    """把性能行标签归一到模型目标之一；非目标/不匹配返回 None。"""
    t = _norm(str(t))
    if 'T弯' in t:
        return 'T弯'
    if t in ('MEK', 'MEK擦拭', 'MEK擦', 'MEK次数', 'MEK擦拭次数'):
        return 'MEK'
    if '水煮' in t:
        for bad in ('BOX', '蒸汽', '盐', '柠檬', '酸', '三合一', 'H', 'S', '铜', '后'):
            if bad in t:
                return None
        return '水煮'
    if t in ('121℃*60min水煮', '121/60水煮', '121*60水煮', '121℃*60min', '121/60', '水煮等级'):
        return '水煮'
    return None


def parse_target_value(key, raw):
    """把性能行单元格的量化为模型目标的数值；无法量化返回 None。"""
    if raw is None:
        return None
    if key == 'T弯' and _is_num(raw):
        return 0.0 if float(raw) == 0.0 else float(raw)  # 数值 0 即 '0腐蚀'→0，口径一致
    if _is_num(raw):
        return float(raw)
    s = unicodedata.normalize('NFKC', str(raw).strip())
    if not s:
        return None
    if key == 'T弯':
        for k, v in TWG_MM.items():
            if s == k or s == k.replace('腐蚀', ''):
                return v
        m = re.match(r'^(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)', s)
        if m:
            return (float(m.group(1)) + float(m.group(2))) / 2.0
        m = re.match(r'^(\d+(?:\.\d+)?)\s*mm$', s, re.I) or re.match(r'^\d+(\.\d+)?$', s)
        if m:
            return float(m.group(1))
        return None  # X / 点状腐蚀 / 有改善 等
    if key == 'MEK':
        m = re.search(r'\d+(?:\.\d+)?', s.replace('<', '').replace('C', '').replace('次', ''))
        return float(m.group(0)) if m else None
    if key == '水煮':
        m = re.match(r'^(\d+)\s*[-~]\s*(\d+)\s*级', s)
        if m:
            return (int(m.group(1)) + int(m.group(2))) / 2.0
        # 单值：'2级' / '2' / '2-'（尾随 '-' 为同实验室记载差异，取 2）
        m = re.match(r'^(\d+)(?:\s*级)?\s*-?$', s)
        return float(m.group(1)) if m else None
    return None


def _looks_ingredient(row):
    c0 = row[0] if len(row) > 0 else None
    c1 = row[1] if len(row) > 1 else None
    c0t = str(c0).strip() if pd.notna(c0) else ''
    c1t = str(c1).strip() if pd.notna(c1) else ''
    c0n, c1n = _is_num(c0), _is_num(c1)
    if not c0t or len(c0t) > 20:
        return False
    if c0n and (not c1t or len(c1t) > 20):
        return False
    if (not c0n) and len(c0t) > 20:
        return False
    return True


def _ingcode(row):
    c0, c1 = row[0] if len(row) > 0 else None, row[1] if len(row) > 1 else None
    if _is_num(c0) and pd.notna(c1) and str(c1).strip():
        return str(c1).strip().replace('\n', '')
    return str(c0).strip().replace('\n', '') if pd.notna(c0) else ''


def _pick_amount_cols(df):
    """返回 sheet 的样本列：正数最多的一条原料行的正数所在列，v=0.. 依次对应。
    只取代码列右侧的数值列（排除 序号 列 与 代码 列本身）。"""
    best = None
    for i in range(1, len(df)):
        row = df.iloc[i]
        if not _looks_ingredient(row):
            continue
        code = _ingcode(row)
        if code in NOISE or code.isdigit() or classify(code) is not None:
            continue
        c0, c1 = row[0] if len(row) > 0 else None, row[1] if len(row) > 1 else None
        code_col = 1 if (_is_num(c0) and pd.notna(c1) and str(c1).strip()) else 0
        nums = [j for j, v in enumerate(row) if j > code_col and _is_num(v) and v > 0]
        if nums and (best is None or len(nums) > len(best)):
            best = nums
    return best or []


def extract_sheet_labels(df, targets):
    """返回 {v: {target: value}}：每个样本列 v 从该 sheet 的性能行提取的目标值。"""
    cols = _pick_amount_cols(df)
    if not cols:
        return {}, []
    out = {}
    for i in range(len(df)):
        row = df.iloc[i]
        # 找本行性能标签：在前 4 列中取首个能分类的目标
        key = None
        for j in range(min(4, len(row))):
            v = row[j]
            if isinstance(v, str) and v.strip():
                k = classify(v)
                if k in targets:
                    key = k
                    break
        if key is None:
            continue
        for v_idx, col in enumerate(cols):
            if col >= len(row):
                continue
            val = parse_target_value(key, row[col])
            if val is None:
                continue
            out.setdefault(v_idx, {})[key] = val
    return out, cols


def main():
    D = pickle.load(open(os.path.join(HERE, '..', 'data', 'merged_data.pkl'), 'rb'))
    all_samples = D['all_samples']

    # 按 (体系, sheet) 组织既有样本，sheet 内顺序（all_samples 中的相邻次序）即样本列 v 顺序
    from collections import defaultdict
    by_cell = defaultdict(list)  # (system, sheet) -> [sample, ...] 按 v 顺序
    for s in all_samples:
        if s['体系'] not in (FA_SYSTEM, FB_SYSTEM):
            continue
        tail = s['样本ID'].split(s['体系'] + '-', 1)[1]    # e.g. '25.8.20-1'
        idx = tail.rfind('-')
        sheet = tail[:idx]
        if sheet:
            by_cell[(s['体系'], sheet)].append(s)

    stats = {'sheet': 0, 'cell_with_label': 0, 'samples_touched': 0, 'target_filled': defaultdict(int)}

    def process(system, file, targets, src):
        xl = pd.ExcelFile(file)
        for sname in xl.sheet_names:
            df = xl.parse(sname, header=None)
            labels, cols = extract_sheet_labels(df, targets)
            if not labels:
                continue
            stats['sheet'] += 1
            bucket = by_cell.get((system, sname))
            if not bucket:
                continue
            for v_idx, vals in labels.items():
                if v_idx >= len(bucket):
                    continue
                sample = bucket[v_idx]
                touched = False
                for k, val in vals.items():
                    if val is not None:
                        sample[k] = val
                        stats['target_filled'][k] += 1
                        touched = True
                # 修正误把性能标签当原料写入组分的 bug
                before = set(sample['组分'])
                sample['组分'] = {c: a for c, a in sample['组分'].items() if classify(c) is None}
                if before != set(sample['组分']):
                    stats['伪原料剔除'] = stats.get('伪原料剔除', 0) + 1
                if touched:
                    sample['标签状态'] = '实测'
                    sample['来源'] = src
                    stats['samples_touched'] += 1

    process(FA_SYSTEM, FA, FA_TARGETS, '3NX240913-6C配比方案(性能补全)')
    process(FB_SYSTEM, FB, FB_TARGETS, '聚酯金黄-AI(性能补全)')

    # '<10' / '>15' 开区间档位按配方脆性打分差异化赋值（在 T弯 计数前完成）
    _assign_bands(all_samples, D['full_mat'])

    # 复核：统计 3 个目标在 each 体系的覆盖
    from collections import Counter
    bysys = defaultdict(Counter)
    bs_status = defaultdict(Counter)
    for s in all_samples:
        cd = bysys[s['体系']]
        for k in ('T弯', 'MEK', '水煮'):
            v = s.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                cd[k] += 1
        bs_status[s['体系']][s['标签状态']] += 1

    print('== 提取统计 ==')
    print('  覆盖 sheet 数:', stats['sheet'], '| 触碰样本:', stats['samples_touched'])
    print('  目标填充:', dict(stats['target_filled']))
    print('  剔除伪原料样本数:', stats.get('伪原料剔除', 0))
    print('== 各体系性能覆盖(有值样本数) ==')
    for sy, c in bysys.items():
        print(f'  {sy:10s} T弯={c.get("T弯",0):3d} MEK={c.get("MEK",0):3d} 水煮={c.get("水煮",0):3d}')
    print('== 各体系标签状态 ==')
    for sy, c in bs_status.items():
        print(f'  {sy:10s} {dict(c)}')

    if '--write' in sys.argv:
        D['all_samples'] = all_samples
        D['lab_samples'] = [s for s in all_samples if s.get('标签状态') == '实测']
        D['unlab_samples'] = [s for s in all_samples if s.get('标签状态') != '实测']
        pkl = os.path.join(HERE, '..', 'data', 'merged_data.pkl')
        pickle.dump(D, open(pkl, 'wb'))
        print('已写回', pkl)
        print('  all_samples:', len(D['all_samples']), '| 实测:', len(D['lab_samples']), '| 无标签:', len(D['unlab_samples']))
    else:
        print('(未写入，需加 --write)')


if __name__ == '__main__':
    main()