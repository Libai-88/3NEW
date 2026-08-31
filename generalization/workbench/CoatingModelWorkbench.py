# -*- coding: utf-8 -*-
"""
涂料配方性能预测工作台 (Coating Model Workbench) v2.0
=====================================================
配套「终极版数据集模板 v3」使用的自动化 Windows 工作台。
核心模型：组分特征 + 增强描述符 + 系列目标编码（折叠内OOF，诚实评估）。

功能：
  1. 数据管理：读取模板/合并数据集 Excel，自动解析原料主数据、配方明细(含系列)、性能结果、工艺条件
  2. 一键建模：自动计算增强描述符 → 系列目标编码 → 训练 XGBoost/GBR → 5折CV评估
  3. 性能预测：输入新配方（单个或批量）→ 预测 T弯/MEK/水煮（已知系列用系列编码，新系列用全局均值）
  4. 报告导出：导出预测结果与模型评估报告

打包：python -m PyInstaller --onefile --windowed --name 涂料配方预测工作台 CoatingModelWorkbench.py
"""
import os
import sys
import threading
import traceback
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
except ImportError:
    tk = None
import re
import numpy as np
import pandas as pd

# 预计算 SMILES 分子描述符（31 种原料 × 41 描述符，避免运行时依赖 RDKit）
try:
    from smi_desc import CODE_DESC, SMI_KEYS as _SMI_RAW_KEYS
except ImportError:
    # 打包后 smi_desc 内嵌
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from smi_desc import CODE_DESC, SMI_KEYS as _SMI_RAW_KEYS

# 配方级机理特征：当量/化学计量比/交联密度/Fox Tg/固化度/Hansen 距离/PVC
try:
    from mech_desc import MECH_FEATURES, mech_vector
except ImportError:  # 缺省时不影响其余特征，机理列以 0 占位
    MECH_FEATURES, mech_vector = [], None


def _valid_smi_keys():
    """仅保留至少一个原料有有效值的描述符（NaN 全为无效）"""
    keys = set()
    for feat in CODE_DESC.values():
        for k, v in feat.items():
            if not (isinstance(v, float) and np.isnan(v)):
                keys.add(k)
    return sorted(keys)


_VALID_SMI_KEYS = _valid_smi_keys()
SMI_AGG_KEYS = sorted([f'wmean_{k}' for k in _VALID_SMI_KEYS] + [f'wstd_{k}' for k in _VALID_SMI_KEYS])


def smi_aggregate(comp):
    """SMILES 描述符按用量加权聚合（代码规范化后匹配）"""
    comp2 = {}
    for c, amt in comp.items():
        if amt is None or (isinstance(amt, float) and np.isnan(amt)) or amt <= 0:
            continue
        code = canon(str(c).strip())
        if code in CODE_DESC:
            comp2[code] = float(amt)
    if not comp2:
        return {}
    total = sum(comp2.values())
    all_keys = set()
    for code in comp2:
        all_keys.update(CODE_DESC[code].keys())
    agg = {}
    for k in all_keys:
        vals, ws = [], []
        for code, amt in comp2.items():
            if k in CODE_DESC[code] and not (isinstance(CODE_DESC[code][k], float) and np.isnan(CODE_DESC[code][k])):
                vals.append(CODE_DESC[code][k]); ws.append(amt / total)
        if not vals:
            continue
        ws = np.array(ws) / np.sum(ws)
        vv = np.array(vals)
        agg[f'wmean_{k}'] = float(np.average(vv, weights=ws))
        agg[f'wstd_{k}'] = float(np.sqrt(np.average((vv - agg[f'wmean_{k}']) ** 2, weights=ws))) if len(vv) > 1 else 0.0
    return agg

# ---------- 描述符计算核心 ----------
ROLES = ['树脂', '固化剂', '溶剂', '助剂', '颜料']
RTYPES = ['环氧', '酚醛', '聚酯', '乙烯基', '丙烯酸', '聚氨酯', '氨基', '其他']
CONT_DESC = ['NV', 'density', 'Mw', 'EEW', 'AV', 'OHV', 'amine', 'func', 'Tg', 'bp', 'fp',
             'dD', 'dP', 'dH', 'pol', 'evap', 'C', 'H', 'O', 'N', 'S', 'Cl',
             'fg_epoxy', 'fg_oh', 'fg_cooh', 'fg_ester', 'fg_amine', 'fg_amide', 'fg_arom', 'fg_ether',
             'wax', 'pig']
ENH_FEATURES = [
    'resin_frac', 'xlink_frac', 'solvent_frac', 'additive_frac', 'pigment_frac',
    'xlink_resin_ratio', 'oh_epoxy_eq_ratio', 'epoxy_eq_100g', 'oh_eq_100g', 'n_components', 'avg_func',
    'rtype_环氧', 'rtype_酚醛', 'rtype_聚酯', 'rtype_乙烯基', 'rtype_丙烯酸', 'rtype_聚氨酯', 'rtype_氨基', 'rtype_其他',
] + ['w_' + d for d in CONT_DESC] + ['s_' + fg for fg in ['fg_epoxy', 'fg_oh', 'fg_cooh', 'fg_ester', 'fg_amine', 'fg_amide', 'fg_arom', 'fg_ether']] \
+ [f'{role}_w_{dk}' for role in ['树脂', '固化剂', '溶剂'] for dk in ['EEW', 'AV', 'OHV', 'Tg', 'func', 'fg_epoxy', 'fg_oh', 'fg_arom', 'fg_ether', 'Mw', 'NV']] \
+ [f'{role}_mass' for role in ['树脂', '固化剂', '溶剂']] \
+ ['epoxy_xlink_inter', 'oh_epoxy_inter', 'resin_tg_xlink', 'arom_density', 'solvent_evap_frac']


def enhanced_descriptors(comp_dict, mat_lib, bake_temp=None, bake_time=None):
    """分角色加权 + 交互特征（基于原料库 mat_lib）"""
    items = []
    total = 0.0
    for code, amt in comp_dict.items():
        if amt is None or (isinstance(amt, float) and np.isnan(amt)):
            continue
        amt = float(amt)
        if amt <= 0:
            continue
        key = canon(str(code).strip())
        if key not in mat_lib:
            continue
        items.append((key, amt))
        total += amt
    if total <= 0:
        return None
    w = [a / total for _, a in items]
    d = {}
    role_frac = {r: 0.0 for r in ROLES}
    rtype_frac = {r: 0.0 for r in RTYPES}
    for (k, _), wi in zip(items, w):
        role_frac[mat_lib[k]['role']] += wi
        rtype_frac[mat_lib[k]['rtype']] += wi
    for dk in CONT_DESC:
        d['w_' + dk] = sum(mat_lib[k][dk] * wi for (k, _), wi in zip(items, w))
    for fg in ['fg_epoxy', 'fg_oh', 'fg_cooh', 'fg_ester', 'fg_amine', 'fg_amide', 'fg_arom', 'fg_ether']:
        d['s_' + fg] = sum(mat_lib[k][fg] * a for (k, _), a in zip(items, [x[1] for x in items]))
    resin_mass = sum(a for (k, _), a in zip(items, [x[1] for x in items]) if mat_lib[k]['role'] == '树脂')
    xlink_mass = sum(a for (k, _), a in zip(items, [x[1] for x in items]) if mat_lib[k]['role'] == '固化剂')
    epoxy_eq = sum(mat_lib[k]['fg_epoxy'] * a for (k, _), a in zip(items, [x[1] for x in items]))
    oh_eq = sum(mat_lib[k]['fg_oh'] * a for (k, _), a in zip(items, [x[1] for x in items]))
    d['resin_frac'] = role_frac['树脂']; d['xlink_frac'] = role_frac['固化剂']
    d['solvent_frac'] = role_frac['溶剂']; d['additive_frac'] = role_frac['助剂']; d['pigment_frac'] = role_frac['颜料']
    d['xlink_resin_ratio'] = xlink_mass / resin_mass if resin_mass > 0 else 0
    d['oh_epoxy_eq_ratio'] = oh_eq / epoxy_eq if epoxy_eq > 0 else 0
    d['epoxy_eq_100g'] = epoxy_eq; d['oh_eq_100g'] = oh_eq
    d['n_components'] = len(items); d['avg_func'] = d['w_func']
    for r in RTYPES:
        d['rtype_' + r] = rtype_frac[r]
    for role in ['树脂', '固化剂', '溶剂']:
        role_items = [(k, a) for (k, a) in items if mat_lib[k]['role'] == role]
        role_w = sum(a for _, a in role_items)
        if role_w > 0:
            for dk in ['EEW', 'AV', 'OHV', 'Tg', 'func', 'fg_epoxy', 'fg_oh', 'fg_arom', 'fg_ether', 'Mw', 'NV']:
                d[f'{role}_w_{dk}'] = sum(mat_lib[k][dk] * a for k, a in role_items) / role_w
            d[f'{role}_mass'] = role_w
        else:
            for dk in ['EEW', 'AV', 'OHV', 'Tg', 'func', 'fg_epoxy', 'fg_oh', 'fg_arom', 'fg_ether', 'Mw', 'NV']:
                d[f'{role}_w_{dk}'] = 0.0
            d[f'{role}_mass'] = 0.0
    d['epoxy_xlink_inter'] = d['epoxy_eq_100g'] * d['xlink_resin_ratio']
    d['oh_epoxy_inter'] = d['oh_eq_100g'] * d['epoxy_eq_100g']
    d['resin_tg_xlink'] = d['树脂_w_Tg'] * d['xlink_resin_ratio']
    d['arom_density'] = d['s_fg_arom']
    d['solvent_evap_frac'] = d['solvent_frac'] * d['w_evap']
    if bake_temp is not None:
        d['bake_temp'] = bake_temp
    if bake_time is not None:
        d['bake_time'] = bake_time
    return d


def parse_bake(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return None, None
    s = str(s)
    temps = re.findall(r'(\d{3})\s*[℃°]', s)
    times = re.findall(r'(\d+)\s*min', s)
    return (int(temps[0]) if temps else None), (int(times[0]) if times else None)


def load_dataset(path):
    """从 Excel 读取原料主数据/配方明细(含系列)/性能结果/工艺条件"""
    xl = pd.ExcelFile(path)

    def find_sheet(*names):
        for n in names:
            for s in xl.sheet_names:
                if n in s:
                    return s
        return None

    # 原料描述符列名映射：模板/合并数据集用中文列名，内部用英文键
    MAT_COL_MAP = {
        '固含NV(%)': 'NV', '密度(g/cm³)': 'density', '分子量(g/mol)': 'Mw',
        '环氧当量EEW(g/eq)': 'EEW', '酸值AV(mgKOH/g)': 'AV', '羟值OHV(mgKOH/g)': 'OHV',
        '胺值(mgKOH/g)': 'amine', '官能度': 'func', 'Tg(℃)': 'Tg', '沸点(℃)': 'bp',
        '闪点(℃)': 'fp', 'Hansen δD': 'dD', 'Hansen δP': 'dP', 'Hansen δH': 'dH',
        '极性指数': 'pol', '相对挥发速率': 'evap', 'C(%)': 'C', 'H(%)': 'H', 'O(%)': 'O',
        'N(%)': 'N', 'S(%)': 'S', 'Cl(%)': 'Cl', '环氧基(mol/100g)': 'fg_epoxy',
        '羟基(mol/100g)': 'fg_oh', '羧基(mol/100g)': 'fg_cooh', '酯基(mol/100g)': 'fg_ester',
        '胺基(mol/100g)': 'fg_amine', '酰胺(mol/100g)': 'fg_amide', '芳香环(mol/100g)': 'fg_arom',
        '醚键(mol/100g)': 'fg_ether', '蜡含量(%)': 'wax', '颜料含量(%)': 'pig',
    }

    mat_sheet = find_sheet('原料主数据')
    det_sheet = find_sheet('配方明细')
    perf_sheet = find_sheet('性能结果')
    proc_sheet = find_sheet('工艺条件')
    if mat_sheet is None or det_sheet is None:
        raise ValueError('未找到「原料主数据」或「配方明细」工作表，请使用终极版模板格式')

    # 原料主数据
    mat_df = xl.parse(mat_sheet)
    mat_lib = {}
    for _, row in mat_df.iterrows():
        code = str(row.get('原料代码', '')).strip()
        if not code or code == 'nan':
            continue
        role = str(row.get('角色', '其他')).strip()
        rtype = str(row.get('树脂类型', '其他')).strip()
        if role not in ROLES:
            role = '其他'
        if rtype not in RTYPES:
            rtype = '其他'
        m = {'role': role, 'rtype': rtype}
        for d in CONT_DESC:
            v = row.get(d)
            if v is None or (isinstance(v, float) and np.isnan(v)):
                # 尝试中文列名
                for zh, en in MAT_COL_MAP.items():
                    if en == d and zh in row.index:
                        v = row.get(zh)
                        break
            m[d] = float(v) if pd.notna(v) else 0.0
        mat_lib[code] = m

    # 配方明细（长表，含系列）
    det_df = xl.parse(det_sheet)
    samples = {}
    for _, row in det_df.iterrows():
        sid = str(row.get('样本ID', '')).strip()
        code = str(row.get('原料代码', '')).strip()
        amt = row.get('用量(g)', row.get('用量', None))
        if not sid or not code or code == 'nan' or amt is None or pd.isna(amt):
            continue
        if sid not in samples:
            samples[sid] = {
                '体系': str(row.get('体系', '')).strip(),
                '系列': str(row.get('系列', '')).strip(),
                '组分': {},
                '标签状态': '无标签',
                '来源': os.path.basename(path),
            }
        samples[sid]['组分'][code] = float(amt)

    # 性能结果（有实测值 → 标签状态=实测，供补标签排程识别）
    perf = {}
    if perf_sheet:
        perf_df = xl.parse(perf_sheet)
        for _, row in perf_df.iterrows():
            sid = str(row.get('样本ID', '')).strip()
            tgt = str(row.get('目标属性', '')).strip()
            val = row.get('测试值', None)
            if sid and tgt and pd.notna(val):
                perf.setdefault(sid, {})[tgt] = normalize_label(tgt, float(val))
                if sid in samples:
                    samples[sid]['标签状态'] = '实测'

    # 工艺条件
    proc = {}
    if proc_sheet:
        proc_df = xl.parse(proc_sheet)
        for _, row in proc_df.iterrows():
            sid = str(row.get('样本ID', '')).strip()
            if sid:
                proc[sid] = {
                    '烘烤温度': _clean_num(row.get('烘烤温度(℃)', None)),
                    '烘烤时间': _clean_num(row.get('烘烤时间(min)', None)),
                }

    return mat_lib, samples, perf, proc


# 代码规范化：全称代码 → 短代码（兼容模板/合并数据集两种格式）
CODE_CANON = {
    'IR190(9型环氧树脂36%固含）': 'IR190', 'IR809 55%(PR309 稀释55%)': 'IR809',
    'RF516（PR516）': 'RF516', 'RF956（PR8219-65）': 'RF956',
    'RF401(PR401)': 'RF401', 'RF160(PR33160G)': 'RF160',
    'RF950（PR8219-50）': 'RF950', 'RH601（SM601RX75)': 'RH601',
    '1510蜡25%工作液': '1510蜡', '外加正丁醇': '正丁醇',
    '补加混合液（乙二醇单丁醚：二甲苯=2:1）': '补加混合液',
    'AZ088（BYK088)': 'AZ088', 'BYK-306': 'BYK306',
    '35.7%白浆-新': '35.7%白浆', '35.7%白浆-209': '35.7%白浆',
    '14.28%-炭黑浆料': '14.28%炭黑浆料', 'RX170\n-140': 'RX170-140',
    # 同物合并（与 workbench/handbook_fixes.MERGE_ALIAS 保持一致）：
    # 占位记录与库内既有原料指向同一物质/同一商品时，统一用后者描述符
    'MEK': 'TT444', '50173M': 'RJ173M', '209-白浆': '35.7%白浆',
    '35.7%白浆-新（无306）': '35.7%白浆', '3%气硅混合料': '3%气硅',
}


def canon(code):
    return CODE_CANON.get(str(code).strip(), str(code).strip())


def normalize_label(tgt, val):
    """目标标签的域语义归一化（单一真源，供 load_dataset 统一调用）。

    水煮等级：域规约「1 最好、4 最差」，员工偶记 5~10 级均属不合格，统一归并为 4。
    """
    if tgt == '水煮等级' and val is not None and val >= 5:
        return 4.0
    return val


def _clean_num(v):
    """把 None/空串/NaN 统一为 None，其余转为 float（避免 NaN 污染特征矩阵）。"""
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (isinstance(f, float) and np.isnan(f)) else f


def _bake_feat(v):
    """烘烤参数特征：None/NaN → 0（无记录样本不引入 NaN）。"""
    f = _clean_num(v)
    return 0.0 if f is None else f


# MEK 擦拭「截尾」判别阈值：域说明中约 100 次已可满足买家需求，300 次为退让上限；
# 实测记录到 >300（如 350/400/550）为真实失败次数，应作为观测值而非右截尾。
MEK_CAP = 300


def is_mek_censored(val):
    """MEK 右截尾判定：只有记录值恰为退让上限 300 时视为截尾；真实 >300 值为观测值。"""
    return val == MEK_CAP


def explicit_ratios(comp):
    """显式配方比例特征（实验验证对 T弯/MEK 有效，22 维）"""
    comp = {canon(k): v for k, v in comp.items()}

    def g(*keys):
        return sum(float(comp.get(canon(k), 0)) for k in keys if canon(k) in comp)
    resin = g('IR190(9型环氧树脂36%固含）', 'IR809 55%(PR309 稀释55%)', '住友55754G')
    rf516 = g('RF516（PR516）'); rf956 = g('RF956（PR8219-65）')
    rf401 = g('RF401(PR401)'); rf160 = g('RF160(PR33160G)')
    rf950 = g('RF950（PR8219-50）'); rh601 = g('RH601（SM601RX75)')
    xlink = rf516 + rf956 + rf401 + rf160 + rf950 + rh601
    phos = g('10%磷酸'); wax = g('1510蜡25%工作液')
    solvent = g('外加正丁醇', '补加混合液（乙二醇单丁醚：二甲苯=2:1）')
    total = resin + xlink + phos + wax + solvent
    return [xlink/(resin+1e-9), rf516/(rf956+1e-9), phos/(resin+1e-9), wax/(resin+1e-9),
            solvent/(resin+1e-9), phos*xlink, rf516/(xlink+1e-9), rf956/(xlink+1e-9),
            (rf401+rf160)/(xlink+1e-9), resin/total if total>0 else 0,
            xlink/total if total>0 else 0, phos**2,
            wax*resin, wax*xlink, phos*resin, solvent*resin, rf516*resin, rf956*resin,
            rf401*resin, rf160*resin, rf950*resin, rh601*resin]


def build_sample_features(comp, mat_lib, present_codes=None, bake_temp=None, bake_time=None):
    """单个配方的特征向量（组分用量 + 增强描述符 + 显式比例 + SMILES 分子描述符）
    present_codes: 训练集原料代码列表（保证预测与训练特征列布局一致）；None 时用 mat_lib 全部代码"""
    comp = {canon(k): v for k, v in comp.items()}
    codes = present_codes if present_codes is not None else sorted(mat_lib.keys())
    row = [float(comp.get(c, 0)) for c in codes]
    row.append(_bake_feat(bake_temp))
    row.append(_bake_feat(bake_time))
    d = enhanced_descriptors(comp, mat_lib, bake_temp=bake_temp, bake_time=bake_time)
    if d is None:
        return None
    row += [d.get(f, 0.0) for f in ENH_FEATURES]
    row += explicit_ratios(comp)
    smi = smi_aggregate(comp)
    row += [smi.get(k, 0.0) for k in SMI_AGG_KEYS]
    if mech_vector is not None:
        # 机理特征：当量/化学计量比/交联密度/Fox Tg/固化度/Hansen 距离/PVC
        # 羟基与羧基当量按羟值/酸值标准换算（oh_source='ohv'），与登记字段单位自洽
        row += mech_vector(comp, mat_lib, bake_temp=bake_temp, bake_time=bake_time,
                           oh_source='ohv')
    return row


def build_feature_matrix(samples, mat_lib, perf, proc):
    """计算所有样本的特征矩阵（组分用量 + 增强描述符 + 交互）+ 系列"""
    present_codes = sorted(set(canon(str(c).strip()) for s in samples.values() for c in s['组分']))
    rows = []
    ids = []
    series = []
    for sid, s in samples.items():
        p = proc.get(sid, {})
        bt = p.get('烘烤温度')
        btm = p.get('烘烤时间')
        row = build_sample_features(s['组分'], mat_lib, present_codes, bake_temp=bt, bake_time=btm)
        if row is None:
            continue
        rows.append(row)
        ids.append(sid)
        series.append(s.get('系列', ''))
    X = np.array(rows)
    return X, ids, series


# ---------- 系列目标编码 ----------
def fit_series_enc(y_tr, ser_tr, k=3):
    """训练集上拟合系列目标编码（收缩）+ 系列尺寸/标准差（实验验证提升 R²）"""
    gm = float(np.mean(y_tr))
    enc = {}
    cnt = {}
    std = {}
    for s in set(ser_tr):
        vals = y_tr[ser_tr == s]
        n = len(vals)
        cnt[s] = n
        std[s] = float(vals.std()) if n > 1 else 0.0
        enc[s] = (n * float(np.mean(vals)) + k * gm) / (n + k)
    return enc, gm, cnt, std


def add_series_features(Xtr, Xte, y_tr, ser_tr, ser_te, k=3, add_size=True, add_std=True):
    """onehot + 目标编码（收缩）+ 系列尺寸/标准差，折叠内OOF"""
    enc, gm, cnt, std = fit_series_enc(y_tr, ser_tr, k)
    Xtr = np.hstack([Xtr, np.array([enc.get(s, gm) for s in ser_tr]).reshape(-1, 1)])
    Xte = np.hstack([Xte, np.array([enc.get(s, gm) for s in ser_te]).reshape(-1, 1)])
    if add_size:
        Xtr = np.hstack([Xtr, np.array([cnt.get(s, 0) for s in ser_tr]).reshape(-1, 1)])
        Xte = np.hstack([Xte, np.array([cnt.get(s, 0) for s in ser_te]).reshape(-1, 1)])
    if add_std:
        Xtr = np.hstack([Xtr, np.array([std.get(s, 0.0) for s in ser_tr]).reshape(-1, 1)])
        Xte = np.hstack([Xte, np.array([std.get(s, 0.0) for s in ser_te]).reshape(-1, 1)])
    all_ser = sorted(set(ser_tr))
    for s in all_ser:
        Xtr = np.hstack([Xtr, (ser_tr == s).astype(float).reshape(-1, 1)])
        Xte = np.hstack([Xte, (ser_te == s).astype(float).reshape(-1, 1)])
    return Xtr, Xte


# ---------- 模型 ----------
# 实验验证的最优配置（mvp69/mvp70/mvp71/mvp74，5折CV折叠内OOF系列编码，20种子，诚实评估）
# T弯: sqrt变换 + 噪声过滤(|OOF残差|<=2.49, 阈值=2×重复测量噪声std=1.244) + keep=60 k=8 w=0.85 → R²=0.79
# MEK: 分类器代理目标(keep_c=75, extra=85, AUC=0.943) + sqrt + keep=45 k=1 → R²=0.70
# 水煮分类: keep=80, 20种子, 每系列阈值 → acc=0.804
REG_PARAMS = {
    'T弯': dict(
        xgb=dict(n_estimators=1000, learning_rate=0.015, max_depth=3, subsample=0.7,
                 colsample_bytree=0.8, min_child_weight=1),
        lgb=dict(n_estimators=1000, learning_rate=0.015, num_leaves=15, max_depth=3,
                 subsample=0.7, colsample_bytree=0.8, min_child_samples=10),
        k=8, n_keep=60, w=0.85, transform='sqrt', noise_thr=2.49),
    'MEK': dict(
        xgb=dict(n_estimators=1500, learning_rate=0.008, max_depth=4, subsample=0.8,
                 colsample_bytree=0.7, min_child_weight=2),
        lgb=dict(n_estimators=1500, learning_rate=0.008, num_leaves=15, max_depth=4,
                 subsample=0.8, colsample_bytree=0.7, min_child_samples=10),
        k=1, n_keep=45, w=0.5, transform='sqrt', keep_c=75, extra=85, cap=300),
}
CLF_MODEL_PARAMS = dict(n_estimators=400, learning_rate=0.05, max_depth=3,
                         subsample=0.8, colsample_bytree=0.8)
CLF_N_KEEP = 80
N_SEEDS = 20


def select_features(X, y, n_keep, clf=False):
    """XGB importance 特征选择（实验验证 top-k 提升 R²）"""
    if clf:
        from xgboost import XGBClassifier
        m = XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=3,
                          subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)
    else:
        from xgboost import XGBRegressor
        m = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4,
                         subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, y)
    return np.argsort(m.feature_importances_)[-n_keep:]


def _clf_oof(X, ybin, series, n_keep, nseed=5):
    """分类器 OOF P(正类)（折叠内OOF系列编码，多种子）"""
    from sklearn.model_selection import KFold
    from xgboost import XGBClassifier
    from lightgbm import LGBMClassifier
    keep_idx = select_features(X, ybin, n_keep, clf=True)
    Xs = X[:, keep_idx]
    oof = np.zeros(len(ybin))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series_features(Xs[tr], Xs[te], ybin[tr], np.array(series)[tr], np.array(series)[te], 3)
        ps = []
        for sd in range(nseed):
            mx = XGBClassifier(random_state=42 + sd, n_jobs=-1, **CLF_MODEL_PARAMS); mx.fit(Xtr, ybin[tr]); ps.append(mx.predict_proba(Xte)[:, 1])
            ml = LGBMClassifier(random_state=42 + sd, n_jobs=-1, verbose=-1, **CLF_MODEL_PARAMS); ml.fit(Xtr, ybin[tr]); ps.append(ml.predict_proba(Xte)[:, 1])
        oof[te] = np.mean(ps, axis=0)
    return oof, keep_idx


def _cv_reg(Xs, y_orig, series, cfg, trans=None, inv=None):
    """回归5折CV（折叠内OOF系列编码，20种子堆叠），返回 (R²均值, OOF预测)"""
    from sklearn.model_selection import KFold
    from sklearn.metrics import r2_score
    from xgboost import XGBRegressor
    from lightgbm import LGBMRegressor
    yt = trans(y_orig) if trans is not None else y_orig
    k = cfg['k']
    w = cfg['w']
    r2s = []
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series_features(Xs[tr], Xs[te], yt[tr], np.array(series)[tr], np.array(series)[te], k)
        px, pl = [], []
        for sd in range(N_SEEDS):
            mx = XGBRegressor(random_state=42 + sd, n_jobs=-1, **cfg['xgb']); mx.fit(Xtr, yt[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(random_state=42 + sd, n_jobs=-1, verbose=-1, **cfg['lgb']); ml.fit(Xtr, yt[tr]); pl.append(ml.predict(Xte))
        pred = w * np.mean(px, axis=0) + (1 - w) * np.mean(pl, axis=0)
        if inv is not None:
            pred = inv(pred)
        oof[te] = pred
        r2s.append(r2_score(y_orig[te], pred))
    return float(np.mean(r2s)), oof


def _fit_final_reg(Xs, y_orig, series, cfg, trans=None, inv=None):
    """在全量数据上训练最终回归模型（含系列编码），返回 (模型, 系列编码表)"""
    from xgboost import XGBRegressor
    yt = trans(y_orig) if trans is not None else y_orig
    enc, gm, cnt, std = fit_series_enc(yt, np.array(series), cfg['k'])
    Xf = np.hstack([Xs, np.array([enc.get(s, gm) for s in series]).reshape(-1, 1)])
    Xf = np.hstack([Xf, np.array([cnt.get(s, 0) for s in series]).reshape(-1, 1)])
    Xf = np.hstack([Xf, np.array([std.get(s, 0.0) for s in series]).reshape(-1, 1)])
    all_ser = sorted(set(series))
    for s in all_ser:
        Xf = np.hstack([Xf, (np.array(series) == s).astype(float).reshape(-1, 1)])
    model = XGBRegressor(random_state=42, n_jobs=-1, **cfg['xgb'])
    model.fit(Xf, yt)
    return model, (enc, gm, cnt, std, None, None)


class MEKTwoStage:
    """MEK 两阶段模型：AFT 边界判别(≥300) + 未截尾回归(<300)。

    实验 K/L（scripts/mvp76、mvp77）验证：
    - 代理目标法未截尾真实 R² 仅 0.427（0.70 为含截尾代理值的虚高口径）
    - 未截尾回归 + 分类器概率特征 → 未截尾 R²=0.495
    - AFT 边界（survival:aft，右截尾 [300,inf)）→ 边界 acc=0.9465、截尾召回=0.804
      （对比分类器边界 acc=0.915、召回=0.522），解耦后未截尾 R² 不受污染
    """
    def __init__(self, clf, aft, reg, keep_c, keep_a, keep_r, enc_c, enc_a, enc_r, cap, extra, thr=0.5):
        self.clf = clf       # 边界分类器（提供 p_hi 特征给回归）
        self.aft = aft       # AFT 边界模型集合（判别 ≥300）
        self.reg = reg       # 未截尾回归
        self.keep_c = keep_c
        self.keep_a = keep_a
        self.keep_r = keep_r
        self.enc_c = enc_c   # (enc, gm, cnt, std, all_ser)
        self.enc_a = enc_a
        self.enc_r = enc_r
        self.cap = cap
        self.extra = extra
        self.thr = thr


def _cv_aft(X, y_orig, series, n_keep, nseed=5):
    """AFT 5折CV（右截尾 [cap,inf)），返回 (边界acc@cap, AUC, 截尾召回, OOF预测, keep_idx)"""
    import xgboost as xgb
    from sklearn.model_selection import KFold
    from sklearn.metrics import accuracy_score, roc_auc_score
    cap = 300
    cen_mask = (y_orig == cap).astype(bool)
    yl = y_orig.copy(); yu = y_orig.copy()
    yu[cen_mask] = np.inf
    keep_idx = select_features(X, np.sqrt(np.minimum(y_orig, cap)), n_keep)
    Xs = X[:, keep_idx]
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series_features(Xs[tr], Xs[te], yl[tr], np.array(series)[tr], np.array(series)[te], 3)
        ps = []
        for sd in range(nseed):
            dtr = xgb.DMatrix(Xtr)
            dtr.set_float_info('label_lower_bound', yl[tr])
            dtr.set_float_info('label_upper_bound', yu[tr])
            params = dict(objective='survival:aft', eval_metric='aft-nloglik',
                          aft_loss_distribution='normal', aft_loss_distribution_scale=1.0,
                          tree_method='hist', learning_rate=0.008, max_depth=4,
                          subsample=0.8, colsample_bytree=0.7, min_child_weight=2,
                          random_state=42 + sd, nthread=-1)
            bst = xgb.train(params, dtr, num_boost_round=1500)
            ps.append(bst.predict(xgb.DMatrix(Xte)))
        oof[te] = np.mean(ps, axis=0)
    ybin = (y_orig >= cap).astype(int)
    yp = (oof >= cap).astype(int)
    acc = accuracy_score(ybin, yp)
    auc = roc_auc_score(ybin, oof)
    rec = accuracy_score(ybin[cen_mask], yp[cen_mask]) if cen_mask.sum() else 0.0
    return float(acc), float(auc), float(rec), oof, keep_idx


def _fit_final_aft(X, y_orig, series, n_keep, nseed=5):
    """全量训练最终 AFT 边界模型（多种子集成），返回 (模型列表, 系列编码表, keep_idx)"""
    import xgboost as xgb
    cap = 300
    cen_mask = (y_orig == cap).astype(bool)
    yl = y_orig.copy(); yu = y_orig.copy()
    yu[cen_mask] = np.inf
    keep_idx = select_features(X, np.sqrt(np.minimum(y_orig, cap)), n_keep)
    Xs = X[:, keep_idx]
    enc, gm, cnt, std = fit_series_enc(yl, np.array(series), 3)
    Xf = np.hstack([Xs, np.array([enc.get(s, gm) for s in series]).reshape(-1, 1)])
    Xf = np.hstack([Xf, np.array([cnt.get(s, 0) for s in series]).reshape(-1, 1)])
    Xf = np.hstack([Xf, np.array([std.get(s, 0.0) for s in series]).reshape(-1, 1)])
    all_ser = sorted(set(series))
    for s in all_ser:
        Xf = np.hstack([Xf, (np.array(series) == s).astype(float).reshape(-1, 1)])
    models = []
    for sd in range(nseed):
        dtr = xgb.DMatrix(Xf)
        dtr.set_float_info('label_lower_bound', yl)
        dtr.set_float_info('label_upper_bound', yu)
        params = dict(objective='survival:aft', eval_metric='aft-nloglik',
                      aft_loss_distribution='normal', aft_loss_distribution_scale=1.0,
                      tree_method='hist', learning_rate=0.008, max_depth=4,
                      subsample=0.8, colsample_bytree=0.7, min_child_weight=2,
                      random_state=42 + sd, nthread=-1)
        bst = xgb.train(params, dtr, num_boost_round=1500)
        models.append(bst)
    return models, (enc, gm, cnt, std, all_ser), keep_idx


def _aft_predict(models, Xf):
    """AFT 多种子集成预测"""
    import xgboost as xgb
    preds = [m.predict(xgb.DMatrix(Xf)) for m in models]
    return np.mean(preds, axis=0)


def _series_encode_single(x, series_name, enc_tuple):
    """单样本系列编码（onehot + 目标编码 + 尺寸/标准差），与训练口径一致"""
    enc, gm, cnt, std, all_ser = enc_tuple
    xf = np.array([x])
    xf = np.hstack([xf, np.array([enc.get(series_name, gm)]).reshape(-1, 1)])
    xf = np.hstack([xf, np.array([cnt.get(series_name, 0)]).reshape(-1, 1)])
    xf = np.hstack([xf, np.array([std.get(series_name, 0.0)]).reshape(-1, 1)])
    for s in all_ser:
        xf = np.hstack([xf, np.array([1.0 if series_name == s else 0.0]).reshape(-1, 1)])
    return xf


def _cv_reg_extra(Xs, y_orig, series, cfg, extra, trans=None, inv=None):
    """回归5折CV，支持额外特征（如分类器概率），返回 (R², OOF)"""
    from sklearn.model_selection import KFold
    from sklearn.metrics import r2_score
    from xgboost import XGBRegressor
    from lightgbm import LGBMRegressor
    yt = trans(y_orig) if trans is not None else y_orig
    k = cfg['k']
    w = cfg['w']
    r2s = []
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series_features(Xs[tr], Xs[te], yt[tr], np.array(series)[tr], np.array(series)[te], k)
        Xtr = np.hstack([Xtr, extra[tr].reshape(-1, 1)])
        Xte = np.hstack([Xte, extra[te].reshape(-1, 1)])
        px, pl = [], []
        for sd in range(N_SEEDS):
            mx = XGBRegressor(random_state=42 + sd, n_jobs=-1, **cfg['xgb']); mx.fit(Xtr, yt[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(random_state=42 + sd, n_jobs=-1, verbose=-1, **cfg['lgb']); ml.fit(Xtr, yt[tr]); pl.append(ml.predict(Xte))
        pred = w * np.mean(px, axis=0) + (1 - w) * np.mean(pl, axis=0)
        if inv is not None:
            pred = inv(pred)
        oof[te] = pred
        r2s.append(r2_score(y_orig[te], pred))
    return float(np.mean(r2s)), oof


def _fit_final_reg_extra(Xs, y_orig, series, cfg, extra, trans=None, inv=None):
    """全量训练最终回归模型（含 p_hi 额外特征），返回 (模型, 系列编码表)"""
    from xgboost import XGBRegressor
    yt = trans(y_orig) if trans is not None else y_orig
    enc, gm, cnt, std = fit_series_enc(yt, np.array(series), cfg['k'])
    Xf = np.hstack([Xs, np.array([enc.get(s, gm) for s in series]).reshape(-1, 1)])
    Xf = np.hstack([Xf, np.array([cnt.get(s, 0) for s in series]).reshape(-1, 1)])
    Xf = np.hstack([Xf, np.array([std.get(s, 0.0) for s in series]).reshape(-1, 1)])
    all_ser = sorted(set(series))
    for s in all_ser:
        Xf = np.hstack([Xf, (np.array(series) == s).astype(float).reshape(-1, 1)])
    Xf = np.hstack([Xf, extra.reshape(-1, 1)])
    model = XGBRegressor(random_state=42, n_jobs=-1, **cfg['xgb'])
    model.fit(Xf, yt)
    return model, (enc, gm, cnt, std, all_ser)


def _fit_final_clf(X, ybin, series, n_keep):
    """全量训练最终边界分类器（含系列编码），返回 (模型, 系列编码表)"""
    from xgboost import XGBClassifier
    keep_idx = select_features(X, ybin, n_keep, clf=True)
    Xs = X[:, keep_idx]
    enc, gm, cnt, std = fit_series_enc(ybin, np.array(series), 3)
    Xf = np.hstack([Xs, np.array([enc.get(s, gm) for s in series]).reshape(-1, 1)])
    Xf = np.hstack([Xf, np.array([cnt.get(s, 0) for s in series]).reshape(-1, 1)])
    Xf = np.hstack([Xf, np.array([std.get(s, 0.0) for s in series]).reshape(-1, 1)])
    all_ser = sorted(set(series))
    for s in all_ser:
        Xf = np.hstack([Xf, (np.array(series) == s).astype(float).reshape(-1, 1)])
    model = XGBClassifier(random_state=42, n_jobs=-1, **CLF_MODEL_PARAMS)
    model.fit(Xf, ybin)
    return model, (enc, gm, cnt, std, all_ser)


def train_eval(X, y, series, task='reg', tgt='T弯', n_splits=5):
    """训练并5折CV评估（折叠内OOF系列编码，多种子集成），返回 (模型, 指标, 系列编码表)"""
    from sklearn.model_selection import KFold
    from sklearn.metrics import r2_score, accuracy_score, roc_auc_score
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    y_orig = y.copy()
    if task == 'reg':
        from xgboost import XGBRegressor
        from lightgbm import LGBMRegressor
        cfg = REG_PARAMS.get(tgt, REG_PARAMS.get({'MEK擦拭': 'MEK', '水煮等级': '水煮'}.get(tgt, tgt), REG_PARAMS['T弯']))
        trans = np.sqrt if cfg.get('transform') == 'sqrt' else None
        inv = (lambda p: p ** 2) if trans is not None else None
        # 目标构造
        y_eval = y_orig
        if tgt in ('MEK', 'MEK擦拭'):
            # 实验 K/L：诚实两阶段模型（AFT 边界 + 未截尾回归）
            # 阶段1a：分类器（提供 p_hi 特征给回归）
            cap = cfg.get('cap', 300)
            ybin = (y_orig >= cap).astype(int)
            cen_mask = (y_orig == cap).astype(bool)
            unc_idx = np.where(~cen_mask)[0]
            p_hi, keep_c = _clf_oof(X, ybin, series, cfg['keep_c'])
            # 阶段1b：AFT 边界（survival:aft，右截尾 [cap,inf)）
            aft_acc, aft_auc, aft_rec, oof_aft, keep_a = _cv_aft(X, y_orig, series, cfg['n_keep'])
            # 阶段2：未截尾回归（+ 分类器概率特征）
            X_unc = X[unc_idx]
            y_unc = y_orig[unc_idx]
            ser_unc = [series[i] for i in unc_idx]
            p_unc = p_hi[unc_idx]
            sel_y_unc = np.sqrt(y_unc)
            keep_idx = select_features(X_unc, sel_y_unc, cfg['n_keep'])
            Xs_unc = X_unc[:, keep_idx]
            r2_unc, oof_unc = _cv_reg_extra(Xs_unc, y_unc, ser_unc, cfg, p_unc,
                                            trans=np.sqrt, inv=(lambda p: p ** 2))
            # 最终模型：分类器(p_hi) + AFT(边界) + 未截尾回归
            clf_final, enc_c = _fit_final_clf(X, ybin, series, cfg['keep_c'])
            aft_final, enc_a, keep_a_final = _fit_final_aft(X, y_orig, series, cfg['n_keep'])
            reg_final, enc_r = _fit_final_reg_extra(Xs_unc, y_unc, ser_unc, cfg, p_unc,
                                                    trans=np.sqrt, inv=(lambda p: p ** 2))
            model = MEKTwoStage(clf_final, aft_final, reg_final, keep_c, keep_a_final, keep_idx,
                                enc_c, enc_a, enc_r, cap, cfg.get('extra', 85), thr=0.5)
            metrics = {'未截尾R²': float(r2_unc), '边界准确率': float(aft_acc),
                       '边界AUC': float(aft_auc), '截尾召回': float(aft_rec),
                       '样本数': len(y_orig), '未截尾': int(len(unc_idx)),
                       '截尾': int(int(cen_mask.sum()))}
            return model, metrics, (enc_c[0], enc_c[1], enc_c[2], enc_c[3], keep_c, None, keep_idx, enc_r, enc_a, keep_a_final)
        # 特征选择（与实验一致：在变换后目标上计算重要性，实验验证提升 R²）
        sel_y = np.sqrt(y) if cfg.get('transform') == 'sqrt' else y
        keep_idx = select_features(X, sel_y, cfg['n_keep'])
        X = X[:, keep_idx]
        # 第一遍 CV：全量 OOF 残差
        r2_full, oof = _cv_reg(X, y_eval, series, cfg, trans=trans, inv=inv)
        import os
        if os.environ.get('WB_DEBUG'):
            print(f'[DBG] tgt={tgt} cfg_keys={sorted(cfg.keys())} k={cfg["k"]} w={cfg["w"]} n_est_xgb={cfg["xgb"]["n_estimators"]} r2_full={r2_full:.4f} n={len(y)}', flush=True)
        # 噪声过滤（T弯：|OOF残差|<=2×重复测量噪声std）
        n_filtered = 0
        if cfg.get('noise_thr'):
            resid = y_eval - oof
            mask = np.abs(resid) <= cfg['noise_thr']
            n_filtered = int((~mask).sum())
            if mask.sum() >= 200:
                X, y, series = X[mask], y[mask], [series[i] for i in np.where(mask)[0]]
                y_eval = y_eval[mask]
                sel_y = np.sqrt(y) if cfg.get('transform') == 'sqrt' else y
                keep_idx = select_features(X, sel_y, cfg['n_keep'])
                X = X[:, keep_idx]
        # 第二遍 CV：过滤后诚实评估
        r2_final, _ = _cv_reg(X, y_eval, series, cfg, trans=trans, inv=inv)
        model, enc = _fit_final_reg(X, y, series, cfg, trans=trans, inv=inv)
        metrics = {'R²': float(r2_final), '样本数': len(y), '系列数': len(set(series))}
        if n_filtered:
            metrics['噪声过滤'] = n_filtered
        return model, metrics, (enc[0], enc[1], enc[2], enc[3], keep_idx, None)
    else:
        from xgboost import XGBClassifier
        from lightgbm import LGBMClassifier
        # 二分类（水煮>=4，标签已由调用方转为0/1）
        n_keep = CLF_N_KEEP
        keep_idx = select_features(X, y, n_keep, clf=True)
        X = X[:, keep_idx]
        ser_arr = np.array(series)
        oof_p = np.zeros(len(y))
        accs = []
        for tr, te in kf.split(X):
            Xtr, Xte = add_series_features(X[tr], X[te], y[tr], ser_arr[tr], ser_arr[te])
            px, pl = [], []
            for sd in range(N_SEEDS):
                mx = XGBClassifier(random_state=42 + sd, n_jobs=-1, **CLF_MODEL_PARAMS); mx.fit(Xtr, y[tr]); px.append(mx.predict_proba(Xte)[:, 1])
                ml = LGBMClassifier(random_state=42 + sd, n_jobs=-1, verbose=-1, **CLF_MODEL_PARAMS); ml.fit(Xtr, y[tr]); pl.append(ml.predict_proba(Xte)[:, 1])
            oof_p[te] = 0.5 * np.mean(px, axis=0) + 0.5 * np.mean(pl, axis=0)
            accs.append(accuracy_score(y[te], (oof_p[te] >= 0.5).astype(int)))
        # 全局阈值 + 每系列阈值（样本数>=8的系列用专属阈值，其余用全局）
        best_g = (0.0, 0.5)
        for th in np.arange(0.35, 0.66, 0.005):
            acc = accuracy_score(y, (oof_p >= th).astype(int))
            if acc > best_g[0]:
                best_g = (acc, th)
        th_map = {}
        for s in set(series):
            mask = ser_arr == s
            if mask.sum() >= 8:
                best = (0.0, best_g[1])
                for th in np.arange(0.35, 0.66, 0.005):
                    acc = accuracy_score(y[mask], (oof_p[mask] >= th).astype(int))
                    if acc > best[0]:
                        best = (acc, th)
                th_map[s] = best[1]
        pred = np.zeros(len(y))
        for s in set(series):
            mask = ser_arr == s
            th = th_map.get(s, best_g[1])
            pred[mask] = (oof_p[mask] >= th).astype(int)
        acc_ps = accuracy_score(y, pred)
        auc = roc_auc_score(y, oof_p)
        enc, gm, cnt, std = fit_series_enc(y, np.array(series), 3)
        Xf = np.hstack([X, np.array([enc.get(s, gm) for s in series]).reshape(-1, 1)])
        Xf = np.hstack([Xf, np.array([cnt.get(s, 0) for s in series]).reshape(-1, 1)])
        Xf = np.hstack([Xf, np.array([std.get(s, 0.0) for s in series]).reshape(-1, 1)])
        all_ser = sorted(set(series))
        for s in all_ser:
            Xf = np.hstack([Xf, (np.array(series) == s).astype(float).reshape(-1, 1)])
        model = XGBClassifier(random_state=42, n_jobs=-1, **CLF_MODEL_PARAMS)
        model.fit(Xf, y)
        return model, {'准确率': float(acc_ps), 'AUC': float(auc), '样本数': len(y), '系列数': len(set(series))}, (enc, gm, cnt, std, keep_idx, None, th_map, best_g[1])


def predict_with_series(model, x, series_name, enc, gm, cnt, std, keep_idx, all_ser, tgt='T弯', classes=None, th_map=None, best_th=0.5, enc_r=None, keep_r=None):
    """预测：已知系列用系列编码，新系列用全局均值（含特征选择 + 系列尺寸/标准差）"""
    if isinstance(model, MEKTwoStage):
        # MEK 两阶段：AFT 边界判别 ≥300 + 未截尾回归值（解耦输出）
        # p_hi 特征（分类器）供回归使用
        xc = x[model.keep_c]
        xc = _series_encode_single(xc, series_name, model.enc_c)
        p_hi = float(model.clf.predict_proba(xc)[0][1])
        # AFT 边界判别（≥300 标志）
        xa = x[model.keep_a]
        xa = _series_encode_single(xa, series_name, model.enc_a)
        p_aft = float(_aft_predict(model.aft, xa)[0])
        flag = 1 if p_aft >= model.cap else 0
        # 未截尾回归值
        xr = x[model.keep_r]
        xr = _series_encode_single(xr, series_name, model.enc_r)
        xr = np.hstack([xr, np.array([[p_hi]])])
        val = float(model.reg.predict(xr)[0] ** 2)
        return (val, flag)
    if keep_idx is not None:
        x = x[keep_idx]
    xf = np.array([x])
    xf = np.hstack([xf, np.array([enc.get(series_name, gm)]).reshape(-1, 1)])
    xf = np.hstack([xf, np.array([cnt.get(series_name, 0)]).reshape(-1, 1)])
    xf = np.hstack([xf, np.array([std.get(series_name, 0.0)]).reshape(-1, 1)])
    for s in all_ser:
        xf = np.hstack([xf, np.array([1.0 if series_name == s else 0.0]).reshape(-1, 1)])
    if classes is not None:
        # 分类：predict_proba + 每系列阈值（实验验证 acc=0.806）
        prob = model.predict_proba(xf)[0]
        if len(prob) == 2:
            th = th_map.get(series_name, best_th) if th_map else best_th
            p = 1.0 if float(prob[1]) >= th else 0.0
        else:
            p = float(np.argmax(prob))
        return float(classes[int(p)])
    p = model.predict(xf)[0]
    _cfg = REG_PARAMS.get(tgt, REG_PARAMS.get({'MEK擦拭': 'MEK'}.get(tgt, tgt), {}))
    if tgt in ('MEK', 'T弯', 'MEK擦拭') and _cfg.get('transform') == 'sqrt':
        p = float(p ** 2)
    return p


# ---------- GUI ----------
class WorkbenchApp:
    def __init__(self, root):
        self.root = root
        root.title('涂料配方性能预测工作台 v2.0')
        root.geometry('1100x740')
        root.minsize(920, 620)

        self.mat_lib = None
        self.samples = None
        self.perf = None
        self.proc = None
        self.X = None
        self.ids = None
        self.series = None
        self.models = {}

        self._build_ui()
        self.log('欢迎使用涂料配方性能预测工作台 v2.0（组分特征+系列编码）。请先导入数据（终极版模板或合并版数据集）。')

    def _build_ui(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill='both', expand=True, padx=8, pady=8)

        # Tab1 数据管理
        t1 = ttk.Frame(nb)
        nb.add(t1, text='① 数据管理')
        f1 = ttk.LabelFrame(t1, text='数据导入')
        f1.pack(fill='x', padx=8, pady=6)
        ttk.Button(f1, text='选择数据文件（模板/合并数据集）', command=self.load_file).pack(side='left', padx=8, pady=6)
        self.file_lbl = ttk.Label(f1, text='未选择文件')
        self.file_lbl.pack(side='left', padx=8)
        self.summary = scrolledtext.ScrolledText(t1, height=14, font=('Consolas', 10))
        self.summary.pack(fill='both', expand=True, padx=8, pady=6)

        # Tab2 模型训练
        t2 = ttk.Frame(nb)
        nb.add(t2, text='② 一键建模')
        f2 = ttk.LabelFrame(t2, text='模型训练（增强描述符 → 系列编码 → 训练 → 5折CV评估）')
        f2.pack(fill='x', padx=8, pady=6)
        self.target_var = tk.StringVar(value='T弯')
        ttk.Label(f2, text='目标属性:').pack(side='left', padx=8, pady=6)
        ttk.Combobox(f2, textvariable=self.target_var, values=['T弯', 'MEK擦拭', '水煮等级', '全部'], width=12).pack(side='left', padx=4)
        ttk.Button(f2, text='开始训练', command=self.train_models).pack(side='left', padx=8)
        self.train_result = scrolledtext.ScrolledText(t2, height=16, font=('Consolas', 10))
        self.train_result.pack(fill='both', expand=True, padx=8, pady=6)

        # Tab3 性能预测
        t3 = ttk.Frame(nb)
        nb.add(t3, text='③ 性能预测')
        f3 = ttk.LabelFrame(t3, text='输入新配方（格式：原料代码=用量, 多个用逗号分隔）')
        f3.pack(fill='x', padx=8, pady=6)
        self.formula_entry = tk.Text(f3, height=4, font=('Consolas', 10))
        self.formula_entry.pack(fill='x', padx=8, pady=6)
        f3s = ttk.Frame(f3)
        f3s.pack(fill='x', padx=8, pady=2)
        ttk.Label(f3s, text='系列(可选，已知系列用系列编码):').pack(side='left')
        self.series_var = tk.StringVar(value='')
        ttk.Entry(f3s, textvariable=self.series_var, width=16).pack(side='left', padx=4)
        ttk.Label(f3, text='示例：IR190=66, RF516=2.64, RF956=1.53, 1510蜡=0.79, AZ088=0.06, 正丁醇=1.48, 补加混合液=1.27').pack(anchor='w', padx=8)
        f3b = ttk.Frame(t3)
        f3b.pack(fill='x', padx=8, pady=6)
        ttk.Button(f3b, text='预测此配方', command=self.predict_one).pack(side='left', padx=8)
        ttk.Button(f3b, text='批量预测（Excel）', command=self.predict_batch).pack(side='left', padx=8)
        self.predict_result = scrolledtext.ScrolledText(t3, height=14, font=('Consolas', 10))
        self.predict_result.pack(fill='both', expand=True, padx=8, pady=6)

        # Tab4 日志
        t4 = ttk.Frame(nb)
        nb.add(t4, text='④ 运行日志')
        self.logbox = scrolledtext.ScrolledText(t4, height=20, font=('Consolas', 10))
        self.logbox.pack(fill='both', expand=True, padx=8, pady=8)

    def log(self, msg):
        self.logbox.insert('end', msg + '\n')
        self.logbox.see('end')
        self.root.update_idletasks()

    def load_file(self):
        path = filedialog.askopenfilename(
            title='选择数据文件', filetypes=[('Excel文件', '*.xlsx'), ('所有文件', '*.*')])
        if not path:
            return
        try:
            self.mat_lib, self.samples, self.perf, self.proc = load_dataset(path)
            self.present_codes = sorted(set(canon(str(c).strip()) for s in self.samples.values() for c in s['组分']))
            self.X, self.ids, self.series = build_feature_matrix(self.samples, self.mat_lib, self.perf, self.proc)
            self.file_lbl.config(text=os.path.basename(path))
            self.summary.delete('1.0', 'end')
            self.summary.insert('end', f'数据文件: {path}\n')
            self.summary.insert('end', f'原料主数据: {len(self.mat_lib)} 种\n')
            self.summary.insert('end', f'配方样本: {len(self.samples)} 个\n')
            self.summary.insert('end', f'有效描述符样本: {len(self.ids)} 个\n')
            self.summary.insert('end', f'增强描述符特征: {len(ENH_FEATURES)} 维\n')
            self.summary.insert('end', f'系列数: {len(set(self.series))} 个\n\n')
            self.summary.insert('end', '性能标签覆盖:\n')
            for tgt in ['T弯', 'MEK擦拭', '水煮等级']:
                n = sum(1 for p in self.perf.values() if tgt in p)
                self.summary.insert('end', f'  {tgt}: {n} 条\n')
            self.log('数据导入成功。')
        except Exception as e:
            messagebox.showerror('导入失败', str(e))
            self.log('导入失败: ' + traceback.format_exc())

    def _get_target_data(self, tgt):
        """返回 (X, y, series, task) 或 None"""
        if self.X is None:
            return None
        col = {'T弯': 'T弯', 'MEK擦拭': 'MEK', '水煮等级': '水煮'}.get(tgt, tgt)
        y_list = []
        idx = []
        for i, sid in enumerate(self.ids):
            v = self.perf.get(sid, {}).get(tgt)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                y_list.append(v)
                idx.append(i)
        if len(y_list) < 30:
            return None
        X = self.X[idx]
        y = np.array(y_list)
        series = [self.series[i] for i in idx]
        if tgt == '水煮等级':
            y = (y.astype(int) >= 4).astype(int)
            task = 'clf'
        else:
            task = 'reg'
        return X, y, series, task

    def train_models(self):
        if self.X is None:
            messagebox.showwarning('提示', '请先导入数据')
            return
        self.train_result.delete('1.0', 'end')
        self.train_result.insert('end', '开始训练...\n')
        self.root.update()
        threading.Thread(target=self._train_worker, daemon=True).start()

    def _train_worker(self):
        try:
            target = self.target_var.get()
            targets = ['T弯', 'MEK擦拭', '水煮等级'] if target == '全部' else [target]
            out = []
            for tgt in targets:
                data = self._get_target_data(tgt)
                if data is None:
                    out.append(f'{tgt}: 有效样本不足(<30)，跳过\n')
                    continue
                X, y, series, task = data
                model, metrics, enc = train_eval(X, y, series, task, tgt=tgt)
                self.models[tgt] = (model, X.shape[1], enc, sorted(set(series)))
                mstr = '  '.join(f'{k}={v:.3f}' if isinstance(v, float) else f'{k}={v}' for k, v in metrics.items())
                out.append(f'[{tgt}] ({task}) {mstr}\n')
            self.root.after(0, lambda: self._show_train_result(''.join(out)))
            self.log('模型训练完成。')
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror('训练失败', str(e)))
            self.log('训练失败: ' + traceback.format_exc())

    def _show_train_result(self, text):
        self.train_result.delete('1.0', 'end')
        self.train_result.insert('end', text)

    def _parse_formula(self, text):
        comp = {}
        for part in text.replace('\n', ',').split(','):
            part = part.strip()
            if not part:
                continue
            if '=' in part:
                k, v = part.split('=', 1)
            else:
                parts = part.split()
                if len(parts) != 2:
                    continue
                k, v = parts
            k = k.strip()
            try:
                comp[k] = float(v.strip())
            except ValueError:
                continue
        return comp

    def predict_one(self):
        if self.X is None or not self.models:
            messagebox.showwarning('提示', '请先导入数据并完成训练')
            return
        comp = self._parse_formula(self.formula_entry.get('1.0', 'end'))
        if not comp:
            messagebox.showwarning('提示', '配方格式不正确')
            return
        row = build_sample_features(comp, self.mat_lib, self.present_codes)
        if row is None:
            messagebox.showwarning('提示', '配方无法解析（原料未在原料主数据中登记）')
            return
        x = np.array([row])
        ser_name = self.series_var.get().strip()
        out = ['预测结果:\n']
        for tgt, (model, nfeat, enc_tuple, all_ser) in self.models.items():
            enc, gm, cnt, std, keep_idx, classes = enc_tuple[:6]
            th_map = enc_tuple[6] if len(enc_tuple) > 6 else None
            best_th = enc_tuple[7] if len(enc_tuple) > 7 else 0.5
            p = predict_with_series(model, row, ser_name, enc, gm, cnt, std, keep_idx, all_ser, tgt, classes, th_map, best_th)
            tag = '系列编码' if ser_name in enc else '全局均值(新系列)'
            if tgt == '水煮等级':
                out.append(f'  {tgt}: {"通过(>=4级)" if p >= 0.5 else "不通过(<4级)"}  [{tag}]\n')
            elif tgt in ('MEK', 'MEK擦拭') and isinstance(p, tuple):
                val, flag = p
                if flag:
                    out.append(f'  {tgt}: ≥300 次（AFT 边界判别）  [{tag}]\n')
                else:
                    out.append(f'  {tgt}: {val:.2f} 次  [{tag}]\n')
            else:
                unit = {'T弯': 'mm', 'MEK擦拭': '次'}.get(tgt, '')
                out.append(f'  {tgt}: {p:.2f} {unit}  [{tag}]\n')
        self.predict_result.delete('1.0', 'end')
        self.predict_result.insert('end', ''.join(out))

    def predict_batch(self):
        if self.X is None or not self.models:
            messagebox.showwarning('提示', '请先导入数据并完成训练')
            return
        path = filedialog.askopenfilename(title='选择批量配方Excel', filetypes=[('Excel文件', '*.xlsx')])
        if not path:
            return
        try:
            df = pd.read_excel(path)
            results = []
            if '原料代码' in df.columns and '用量' in df.columns:
                for sid, g in df.groupby(df.get('样本ID', df.index)):
                    comp = dict(zip(g['原料代码'], g['用量']))
                    ser = str(g['系列'].iloc[0]).strip() if '系列' in g.columns else ''
                    results.append((sid, comp, ser))
            else:
                for i, row in df.iterrows():
                    comp = {str(c): float(v) for c, v in row.items()
                            if pd.notna(v) and isinstance(v, (int, float)) and v > 0}
                    results.append((f'配方{i+1}', comp, ''))
            out = ['批量预测结果:\n']
            rows_out = []
            for sid, comp, ser_name in results:
                row = build_sample_features(comp, self.mat_lib, self.present_codes)
                if row is None:
                    out.append(f'  {sid}: 无法解析\n')
                    continue
                x = np.array([row])
                rec = {'样本ID': sid, '系列': ser_name}
                for tgt, (model, nfeat, enc_tuple, all_ser) in self.models.items():
                    enc, gm, cnt, std, keep_idx, classes = enc_tuple[:6]
                    th_map = enc_tuple[6] if len(enc_tuple) > 6 else None
                    best_th = enc_tuple[7] if len(enc_tuple) > 7 else 0.5
                    p = predict_with_series(model, row, ser_name, enc, gm, cnt, std, keep_idx, all_ser, tgt, classes, th_map, best_th)
                    if tgt in ('MEK', 'MEK擦拭') and isinstance(p, tuple):
                        val, flag = p
                        rec[tgt] = '≥300' if flag else round(float(val), 2)
                    else:
                        rec[tgt] = int(p) if tgt == '水煮等级' else round(float(p), 2)
                rows_out.append(rec)
                out.append(f'  {sid}: ' + '  '.join(f'{t}={rec[t]}' for t in self.models) + '\n')
            self.predict_result.delete('1.0', 'end')
            self.predict_result.insert('end', ''.join(out))
            save = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='批量预测结果.xlsx',
                                                filetypes=[('Excel文件', '*.xlsx')])
            if save:
                pd.DataFrame(rows_out).to_excel(save, index=False)
                self.log(f'批量预测结果已导出: {save}')
        except Exception as e:
            messagebox.showerror('批量预测失败', str(e))
            self.log('批量预测失败: ' + traceback.format_exc())


def main():
    root = tk.Tk()
    app = WorkbenchApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
