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


# ---------- 补标签排程（实验 M 结论落地） ----------
def build_acquisition_plan(samples, budget=10, strategy='strat_random', seed=42):
    """推荐下一批应补测标签的样本（实验 M：系列分层随机采样优于不确定性采样）。

    实验 M（scripts/mvp78_experiments.py，T弯 n=277/18 系列，系列感知留出 20%）结论：
      - 系列分层随机 / 随机：最终测试 R²=0.688，达 R²≥0.6 仅需 70~90 标签
      - 纯不确定性采样：最终 R²=0.647，达 R²≥0.6 需 130 标签（最差）
    原因：数据有强系列结构，系列目标编码是关键特征；不确定性采样把标签集中在
    少数难系列，饿死其他系列，损害系列编码与泛化。

    因此补标签排程默认采用「系列分层随机」：按系列均匀分配预算，系列内随机，
    保证每个系列都有标签覆盖，最大化系列编码信号。

    参数：
      samples: dict {样本ID: {系列, 标签状态, ...}}
      budget: 本批补测样本数
      strategy: 'strat_random'（默认，系列分层随机）/ 'random'（纯随机）
      seed: 随机种子（固定种子保证可复现）
    返回：
      {ok, budget, strategy, total_unlabeled, series_summary, plan[]}
      plan 每项: {样本ID, 系列, 体系, 标签状态, 来源}
    """
    import random as _rnd
    rng = _rnd.Random(seed)
    # 未实测样本池（标签状态 != 实测）
    pool = []
    for sid, s in samples.items():
        if s.get('标签状态') != '实测':
            pool.append({'样本ID': sid, '系列': s.get('系列', ''), '体系': s.get('体系', ''),
                         '标签状态': s.get('标签状态', '无标签'), '来源': s.get('来源', '')})
    if not pool:
        return {'ok': True, 'budget': budget, 'strategy': strategy, 'total_unlabeled': 0,
                'series_summary': [], 'plan': [], 'note': '当前无未实测样本，无需补标签'}
    # 按系列分组
    by_ser = {}
    for p in pool:
        by_ser.setdefault(p['系列'], []).append(p)
    chosen = []
    if strategy == 'strat_random':
        # 系列分层随机：轮转分配，每轮每个系列最多取 1 个，系列内随机
        ser_keys = list(by_ser.keys())
        rng.shuffle(ser_keys)
        while len(chosen) < budget and any(by_ser.values()):
            for s in ser_keys:
                if len(chosen) >= budget:
                    break
                if by_ser[s]:
                    chosen.append(by_ser[s].pop(rng.randrange(len(by_ser[s]))))
    else:
        # 纯随机
        all_pool = [p for lst in by_ser.values() for p in lst]
        rng.shuffle(all_pool)
        chosen = all_pool[:budget]
    # 系列汇总
    series_summary = []
    for s in sorted(by_ser.keys()):
        total = len(by_ser[s]) + sum(1 for p in pool if p['系列'] == s and p in chosen)
        series_summary.append({'系列': s, '未实测': total, '本批推荐': sum(1 for p in chosen if p['系列'] == s)})
    return {'ok': True, 'budget': budget, 'strategy': strategy, 'total_unlabeled': len(pool),
            'series_summary': series_summary, 'plan': chosen,
            'note': '策略依据实验 M：系列分层随机采样在系列结构化数据上优于不确定性采样（R² 0.688 vs 0.647）。'}


# ---------- 建模就绪检查（写死阈值，来自实验 J/M/N 结论） ----------
# 阈值依据（均有实验支撑）：
#   标签覆盖：实验 M（scripts/mvp78_experiments.py）T弯 n=277/18 系列实测，
#             达 R²≥0.6 需 70~90 标签，130+ 标签后增益趋缓；
#             实验 N（scripts/mvp79_experiments.py）表明 R²>0.9 需降噪而非单纯加标签。
#   系列覆盖：系列目标编码需每系列 ≥2 样本（折叠内 OOF 才可计算），推荐 ≥5 才稳定。
#   体系多样性：跨体系泛化主张需 ≥3 体系（当前合并版数据集 3 体系）。
#   原料登记：未登记原料会走自动估算描述符（不确定性），应尽量为 0。
#   标签平衡：分类目标每类 ≥10 样本才可训练稳定分类器。
#   噪声水平：实验 J/N 实测 T弯 系列内噪声 std=1.244、总 std=2.72 → R² 上限 0.789；
#             R²>0.9 需噪声 ≤0.62（减半）或重复测量 4 次取均值。
READY_LABEL_MIN = 50          # 每目标最少标签数（可用）
READY_LABEL_GOOD = 100        # 每目标标签数（良好）
READY_SERIES_MIN = 2          # 每系列最少样本（OOF 编码可计算）
READY_SERIES_GOOD = 5         # 每系列推荐样本数（编码稳定）
READY_SYSTEMS_MIN = 3         # 跨体系泛化最少体系数
READY_CLASS_MIN = 10          # 分类目标每类最少样本
READY_NOISE_TW_STD = 1.244    # T弯 实测系列内噪声 std（实验 J）
READY_NOISE_TW_TOTAL = 2.708   # T弯 实测总 std（实验 J：噪声地板 R²=0.789）
READY_NOISE_TARGET = 0.62     # R²>0.9 所需噪声 std（实验 N：噪声减半）


def build_readiness_report(mat_lib, samples, perf, proc):
    """建模就绪检查：自动评估数据是否达到可训练/逼近 R²>0.9 的标准。

    将实验 J/M/N 的结论固化为硬编码阈值（写死），数据由用户提供（可配置），
    替代人工经验判断，减少人工熟练度差异引入的误差。

    返回：
      {ok, summary{...}, checks[{id,name,status,detail,evidence}],
       per_target[{target,labeled,status,note}], recommendations[]}
    """
    from collections import Counter
    checks = []
    recs = []

    # 1. 标签覆盖（每目标）
    tgt_cnt = Counter()
    for d in perf.values():
        for t in d:
            tgt_cnt[t] += 1
    per_target = []
    for t in sorted(tgt_cnt):
        n = tgt_cnt[t]
        if n >= READY_LABEL_GOOD:
            st = 'ok'
        elif n >= READY_LABEL_MIN:
            st = 'warn'
        else:
            st = 'fail'
        note = ''
        if t == 'T弯':
            note = f'实验 M：{n} 标签' + ('（≥100，接近 R² 上限区）' if n >= READY_LABEL_GOOD else '（需 ≥70 才达 R²≥0.6）')
        elif t == 'MEK擦拭':
            note = f'含截尾样本，按两阶段评估（边界 acc + 未截尾 R²）'
        elif t == '水煮等级':
            note = f'分类目标，按准确率评估'
        per_target.append({'target': t, 'labeled': n, 'status': st, 'note': note})
    n_lab_total = sum(1 for s in samples.values() if s.get('标签状态') == '实测')
    if n_lab_total == 0:
        checks.append({'id': 'labels', 'name': '标签覆盖', 'status': 'fail',
                       'detail': '当前无任何实测标签，无法训练',
                       'evidence': '需至少 50 标签/目标（实验 M）'})
        recs.append('先补测标签：使用「补标签排程」按系列分层随机推荐下一批应测样本')
    elif any(p['status'] == 'fail' for p in per_target):
        weak = [p['target'] for p in per_target if p['status'] == 'fail']
        checks.append({'id': 'labels', 'name': '标签覆盖', 'status': 'warn',
                       'detail': f'目标 {weak} 标签不足（<{READY_LABEL_MIN}）',
                       'evidence': f'实验 M：达 R²≥0.6 需 70~90 标签/目标'})
        recs.append(f'目标 {weak} 标签不足，用「补标签排程」优先补测')
    else:
        checks.append({'id': 'labels', 'name': '标签覆盖', 'status': 'ok',
                       'detail': f'实测标签 {n_lab_total} 个，各目标均 ≥{READY_LABEL_MIN}',
                       'evidence': '实验 M：70~90 标签达 R²≥0.6，130+ 后增益趋缓'})

    # 2. 系列覆盖
    ser_cnt = Counter(s['系列'] for s in samples.values())
    small_ser = {k: v for k, v in ser_cnt.items() if v < READY_SERIES_GOOD}
    if small_ser:
        checks.append({'id': 'series', 'name': '系列覆盖', 'status': 'warn',
                       'detail': f'{len(small_ser)} 个系列样本 <{READY_SERIES_GOOD}：{dict(list(small_ser.items())[:5])}',
                       'evidence': f'系列目标编码需每系列 ≥{READY_SERIES_MIN} 样本（OOF 可计算），推荐 ≥{READY_SERIES_GOOD}'})
        recs.append('样本过少的系列其系列编码不可靠，预测时按全局均值回退')
    else:
        checks.append({'id': 'series', 'name': '系列覆盖', 'status': 'ok',
                       'detail': f'{len(ser_cnt)} 个系列，每系列均 ≥{READY_SERIES_GOOD} 样本',
                       'evidence': '系列目标编码稳定'})

    # 3. 体系多样性
    sys_cnt = Counter(s['体系'] for s in samples.values())
    n_sys = len(sys_cnt)
    if n_sys < READY_SYSTEMS_MIN:
        checks.append({'id': 'systems', 'name': '体系多样性', 'status': 'warn',
                       'detail': f'仅 {n_sys} 个体系（{dict(sys_cnt)}），跨体系泛化证据不足',
                       'evidence': f'跨体系泛化主张需 ≥{READY_SYSTEMS_MIN} 体系'})
        recs.append('补充其他体系（有机/聚酯/聚氨酯/丙烯酸等）配方以支撑跨体系泛化')
    else:
        checks.append({'id': 'systems', 'name': '体系多样性', 'status': 'ok',
                       'detail': f'{n_sys} 个体系：{dict(sys_cnt)}',
                       'evidence': '≥3 体系可支撑跨体系泛化主张'})

    # 4. 原料登记完整性
    all_codes = set(c for s in samples.values() for c in s['组分'])
    unreg = sorted(c for c in all_codes if c not in mat_lib)
    if unreg:
        checks.append({'id': 'materials', 'name': '原料登记', 'status': 'warn',
                       'detail': f'{len(unreg)} 种原料未登记（将自动估算描述符）：{unreg[:10]}',
                       'evidence': '未登记原料走自动估算，描述符不确定性高，建议补测真实值'})
        recs.append(f'为 {unreg[:10]} 补测原料描述符（SDS/TDS 实测值优先）以降低特征不确定性')
    else:
        checks.append({'id': 'materials', 'name': '原料登记', 'status': 'ok',
                       'detail': f'全部 {len(all_codes)} 种原料均已登记描述符',
                       'evidence': '无自动估算原料'})

    # 5. 标签平衡（分类目标）
    wb = [v for d in perf.values() for t, v in d.items() if t == '水煮等级']
    if wb:
        cls_cnt = Counter(wb)
        sparse = {k: v for k, v in cls_cnt.items() if v < READY_CLASS_MIN}
        if sparse:
            checks.append({'id': 'balance', 'name': '标签平衡', 'status': 'warn',
                           'detail': f'水煮等级少数类样本 <{READY_CLASS_MIN}：{dict(sparse)}',
                           'evidence': f'分类目标每类需 ≥{READY_CLASS_MIN} 样本才可训练稳定分类器'})
            recs.append('水煮等级少数类样本不足，分类器对少数类召回有限，可考虑合并相邻等级')
        else:
            checks.append({'id': 'balance', 'name': '标签平衡', 'status': 'ok',
                           'detail': f'水煮等级各类均 ≥{READY_CLASS_MIN} 样本',
                           'evidence': '分类目标各类样本充足'})

    # 6. 噪声水平（R²>0.9 可达性）
    noise_floor = 1 - READY_NOISE_TW_STD ** 2 / READY_NOISE_TW_TOTAL ** 2
    noise_target_floor = 1 - READY_NOISE_TARGET ** 2 / READY_NOISE_TW_TOTAL ** 2
    checks.append({'id': 'noise', 'name': '噪声水平（R² 上限）', 'status': 'warn',
                   'detail': f'T弯 当前噪声 std={READY_NOISE_TW_STD} → R² 上限 {noise_floor:.3f}；'
                             f'R²>0.9 需噪声 ≤{READY_NOISE_TARGET}（上限 {noise_target_floor:.3f}）',
                   'evidence': '实验 J/N：T弯 噪声地板 R²=0.789，模型 0.791 已达上限；'
                               '降噪减半或重复测量 4 次取均值可达 R²>0.9'})
    recs.append('R²>0.9 路径：按 ISO 17132/ASTM D5402 规范降噪（减半）或重复测量 4 次取均值，'
                '而非更换模型/加特征（实验 J-3~J-5 验证无真实提升）')

    # 汇总
    n_fail = sum(1 for c in checks if c['status'] == 'fail')
    n_warn = sum(1 for c in checks if c['status'] == 'warn')
    if n_fail > 0:
        overall = 'insufficient'
    elif n_warn > 0:
        overall = 'attention'
    else:
        overall = 'ready'
    summary = {
        'samples': len(samples), 'series': len(ser_cnt), 'systems': n_sys,
        'labeled': n_lab_total, 'unlabeled': len(samples) - n_lab_total,
        'unregistered': len(unreg), 'overall': overall,
        'n_fail': n_fail, 'n_warn': n_warn,
    }
    return {'ok': True, 'summary': summary, 'checks': checks,
            'per_target': per_target, 'recommendations': recs}
