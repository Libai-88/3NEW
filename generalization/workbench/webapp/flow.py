# -*- coding: utf-8 -*-
"""
前置流程控制模块 (flow.py) v2.0
===============================
「写死 vs 可配置」原则的落地实现：

【写死（固定逻辑，自动化减少人工误差）】
  1. 流程步骤与顺序：声明 → 预校验 → 整理 → 特征 → 导出
  2. 模板结构（工作表名、列名）
  3. 特征计算逻辑（组分用量 + 增强描述符 + 显式比例 + SMILES 聚合）
  4. 原料代码清洗规则（别名映射 + 大小写统一）
  5. 去重协议（按样本ID，重复测量取均值）
  6. 校验规则（必填列、数值范围、代码登记状态）

【可配置（领域内容，由用户在模板配置表中维护）】
  1. 体系配置（体系/目标属性/单位/方向/数据类型）
  2. 原料描述符（用户提供真实测量值，替代类别典型值估算）
  3. 工艺条件（烘烤温度/时间）
  4. 数据源格式（新增格式需新增解析器，但类型由用户显式声明）

本模块提供：文件类型声明、预校验、整理确认、流水线清单导出。
"""
import os
import json
import datetime
import numpy as np
import pandas as pd


# ---------- 文件类型声明 ----------
FILE_TYPES = {
    'template': '终极版模板 Excel（含原料主数据/配方明细/性能结果）',
    'labeled': '配料测试汇总（有标签，含配方与结果）',
    'formulation': '配方方案（无标签，如配比方案/聚酯金黄）',
    'materials': '原料数据（原料主数据/送检）',
}


def suggest_type(path):
    """自动建议文件类型（仅建议，由用户最终确认）"""
    try:
        xl = pd.ExcelFile(path)
        names = [str(s) for s in xl.sheet_names]
        if any('原料主数据' in s and '配方明细' in s for s in names):
            return 'template'
        if any('配方与结果' in s or '配料' in s for s in names):
            return 'labeled'
        if any('原料' in s and '送检' in s for s in names) or any('原材料' in s for s in names):
            return 'materials'
        base = os.path.basename(path)
        if '配比' in base or '聚酯' in base or '配方' in base:
            return 'formulation'
        return 'formulation'
    except Exception:
        return 'formulation'


# ---------- 预校验规则（写死） ----------
def _is_num(v):
    return isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v))


def validate_file(path, ftype, mat_lib=None):
    """按声明类型校验文件，返回 {ok, errors[], warnings[], info}"""
    errors, warnings = [], []
    info = {}
    try:
        xl = pd.ExcelFile(path)
        info['sheets'] = [str(s) for s in xl.sheet_names]
    except Exception as e:
        return {'ok': False, 'errors': [f'文件无法读取: {e}'], 'warnings': [], 'info': {}}

    if ftype == 'template':
        need = ['原料主数据', '配方明细', '性能结果', '工艺条件']
        missing = [s for s in need if not any(s in n for n in info['sheets'])]
        if missing:
            errors.append(f'模板缺少工作表: {missing}')
        # 校验配方明细必填列
        try:
            det = xl.parse([s for s in info['sheets'] if '配方明细' in s][0])
            for col in ['样本ID', '原料代码', '用量(g)']:
                if col not in det.columns:
                    errors.append(f'配方明细缺少列: {col}')
        except Exception as e:
            errors.append(f'配方明细解析失败: {e}')

    elif ftype == 'labeled':
        try:
            sheet = None
            for s in info['sheets']:
                if '配方与结果' in s or '配料' in s:
                    sheet = s
                    break
            df = xl.parse(sheet if sheet else info['sheets'][0])
            info['columns'] = list(df.columns)
            for col in ['配方ID', '烘烤条件']:
                if col not in df.columns:
                    warnings.append(f'有标签文件缺少列「{col}」（可能影响样本ID/工艺解析）')
            # 校验性能列
            for col in ['T弯(mm)_原始', 'MEK擦拭(次)_原始', '水煮（等级）_原始']:
                if col not in df.columns:
                    warnings.append(f'有标签文件缺少性能列「{col}」')
            # 数值范围校验
            if 'T弯(mm)_原始' in df.columns:
                v = df['T弯(mm)_原始'].dropna()
                v = v[pd.to_numeric(v, errors='coerce').notna()]
                if len(v) > 0:
                    v = pd.to_numeric(v, errors='coerce')
                    if (v < 0).any():
                        errors.append('T弯存在负值（数据异常）')
                    if (v > 100).any():
                        warnings.append('T弯存在 >100 的异常大值')
            info['rows'] = len(df)
        except Exception as e:
            errors.append(f'有标签文件解析失败: {e}')

    elif ftype == 'formulation':
        try:
            df = xl.parse(info['sheets'][0], header=None)
            info['rows'] = len(df)
            # 校验是否有可识别的组分行
            code_count = 0
            for i in range(1, min(20, len(df))):
                row = df.iloc[i]
                c0 = row[0]
                c1 = row[1] if len(row) > 1 else None
                c0_txt = str(c0).strip() if pd.notna(c0) else ''
                c1_txt = str(c1).strip() if pd.notna(c1) else ''
                if (not _is_num(c0) and 0 < len(c0_txt) <= 20) or \
                   (_is_num(c0) and c1_txt and not _is_num(c1) and 0 < len(c1_txt) <= 20):
                    code_count += 1
            if code_count == 0:
                errors.append('配方方案未识别到组分行（代码|用量 结构）')
            else:
                info['code_rows'] = code_count
        except Exception as e:
            errors.append(f'配方方案解析失败: {e}')

    elif ftype == 'materials':
        try:
            sheet = None
            for s in info['sheets']:
                if '原料主数据' in s:
                    sheet = s
                    break
            df = xl.parse(sheet if sheet else info['sheets'][0])
            info['columns'] = list(df.columns)
            code_col = None
            for cand in ['原料代码', '存货编码', '存货代码', '代码']:
                if cand in df.columns:
                    code_col = cand
                    break
            if code_col is None:
                errors.append('原料数据缺少代码列（原料代码/存货编码/存货代码/代码）')
            else:
                info['rows'] = len(df)
                codes = df[code_col].dropna().astype(str).str.strip()
                info['n_codes'] = len(codes)
                if mat_lib is not None:
                    new_codes = [c for c in codes if c and c != 'nan' and c not in mat_lib]
                    info['new_codes'] = len(new_codes)
                    if new_codes:
                        warnings.append(f'新增原料 {len(new_codes)} 种（此前未登记）')
        except Exception as e:
            errors.append(f'原料数据解析失败: {e}')

    return {'ok': len(errors) == 0, 'errors': errors, 'warnings': warnings, 'info': info}


# ---------- 整理后确认（写死） ----------
def organize_report(mat_lib, samples, perf, proc, report):
    """整理后生成确认报告：去重、估算原料、未登记代码"""
    out = {'report': list(report), 'estimated': [], 'unregistered': [], 'dedup': 0}
    # 估算原料（描述符状态=估算）
    for code, d in mat_lib.items():
        if d.get('_estimated'):
            out['estimated'].append(code)
    # 未登记代码（不在原料库）
    all_codes = set(c for s in samples.values() for c in s['组分'])
    out['unregistered'] = sorted(c for c in all_codes if c not in mat_lib)
    # 去重信息
    for line in report:
        if '去重' in line:
            out['dedup'] = line
    return out


# ---------- 流水线清单导出（可复现） ----------
def build_manifest(files, ftypes, params=None):
    """生成流水线清单 JSON（记录输入文件、类型、参数、时间，保证可复现）"""
    manifest = {
        'version': '2.0',
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'files': [
            {'name': os.path.basename(f), 'type': ftypes.get(os.path.basename(f), 'unknown'),
             'type_desc': FILE_TYPES.get(ftypes.get(os.path.basename(f), ''), '')}
            for f in files
        ],
        'params': params or {},
        'note': '本清单记录数据整理流水线的输入与参数，用于复现与审计。',
    }
    return manifest
