# -*- coding: utf-8 -*-
"""
外部公开数据整合实验 (External Data Integration Experiment)
===========================================================
目标：实验验证「公开数据集扩充能否提升当前涂料配方性能预测模型」。
覆盖：
  E-1 特征空间兼容性：外部样本到当前训练分布的 OOD 距离
  E-2 目标尺度兼容性：T弯(mm) vs 外部 T-bend(T值) 尺度对照
  E-3 强制合并实验：把外部样本（尽力映射）加入训练集，测 R² 变化
  E-4 噪声地板复核：T弯 R² 理论上限（重复测量噪声）
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd
from collections import defaultdict
from scipy.spatial.distance import cdist
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

# 相对路径：脚本位于 generalization/data_dilemma/scripts/
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_GEN_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..'))
sys.path.insert(0, os.path.join(_GEN_DIR, 'workbench'))
sys.path.insert(0, os.path.join(_GEN_DIR, 'scripts'))
from CoatingModelWorkbench import (load_dataset, ENH_FEATURES, explicit_ratios,
                                   smi_aggregate, SMI_AGG_KEYS, canon,
                                   enhanced_descriptors, ROLES, RTYPES, CONT_DESC)

BASE = _GEN_DIR
path = os.path.join(BASE, '合并版数据集.xlsx')
mat_lib, samples, perf, proc = load_dataset(path)
present_codes = sorted(set(canon(str(c).strip()) for s in samples.values() for c in s['组分']))

def build_compact(comp, mat_lib, bt=None, btm=None):
    comp = {canon(k): v for k, v in comp.items()}
    row = [float(comp.get(c, 0)) for c in present_codes]
    row.append(float(bt) if bt is not None else 0)
    row.append(float(btm) if btm is not None else 0)
    d = enhanced_descriptors(comp, mat_lib, bake_temp=bt, bake_time=btm)
    if d is None:
        return None
    row += [d.get(f, 0.0) for f in ENH_FEATURES]
    row += explicit_ratios(comp)
    smi = smi_aggregate(comp)
    row += [smi.get(k, 0.0) for k in SMI_AGG_KEYS]
    return row

# ---------- 构建当前特征矩阵 ----------
X, ids, series = [], [], []
for sid, s in samples.items():
    p = proc.get(sid, {})
    row = build_compact(s['组分'], mat_lib, bt=p.get('烘烤温度'), btm=p.get('烘烤时间'))
    if row is None:
        continue
    X.append(row); ids.append(sid); series.append(s.get('系列', ''))
X = np.array(X)
FEAT_NAMES = (present_codes + ['bake_temp', 'bake_time'] + ENH_FEATURES
              + [f'ratio_{i}' for i in range(22)] + SMI_AGG_KEYS)
print(f'当前特征矩阵: {X.shape}, 特征数={len(FEAT_NAMES)}', flush=True)

def get_data(tgt):
    y_list, idx = [], []
    for i, sid in enumerate(ids):
        v = perf.get(sid, {}).get(tgt)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            y_list.append(v); idx.append(i)
    if len(y_list) < 30:
        return None
    return X[idx], np.array(y_list), [series[i] for i in idx]

# ============================================================
# E-1 特征空间兼容性：外部样本 OOD 距离
# ============================================================
print('\n' + '=' * 72)
print('E-1 特征空间兼容性：外部样本到当前训练分布的 OOD 距离')
print('=' * 72)

# 外部树脂描述符（来自 Coatings 2025, 15(3), 350 表2/3）
# 用树脂实测属性构造原料库条目（角色=树脂, 类型=聚酯）
def resin_mat(nv, av, ohv, tg, mn, mw, func=2.0):
    return dict(role='树脂', rtype='聚酯', NV=nv, density=1.1, Mw=mw, EEW=0.0,
                AV=av, OHV=ohv, amine=0, func=func, Tg=tg, bp=300, fp=150,
                dD=18.0, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=8, O=27,
                N=0, S=0, Cl=0, fg_epoxy=0.0, fg_oh=ohv/56100.0*100, fg_cooh=av/56100.0*100,
                fg_ester=0.5, fg_amine=0, fg_amide=0, fg_arom=0.3, fg_ether=0.1,
                wax=0, pig=0)

EXT_RESINS = {
    'RES-STD':   resin_mat(59.5, 2.5, 24.7, 42.4, 6022, 11704),
    'RES-FDCA1': resin_mat(60.1, 3.5, 24.6, 39.4, 5266, 11478),
    'RES-FDCA2': resin_mat(59.8, 2.5, 23.8, 36.1, 5733, 11875),
    'RES-FDCA4': resin_mat(59.6, 3.1, 23.7, 38.8, 5740, 11644),
    'RES-FDCA8': resin_mat(59.7, 4.0, 24.9, 35.8, 5946, 11621),
    'RES-FDCA22': resin_mat(59.5, 4.6, 24.9, 38.9, 4974, 10046),
    'RES-FDCA31': resin_mat(60.1, 3.4, 22.7, 32.2, 4691, 9582),
    'RES-FDCA41': resin_mat(59.0, 3.6, 22.0, 37.8, 4362, 8620),
}

# 外部涂层配方（尽力映射：树脂 + 三聚氰胺固化剂 + 溶剂 + 颜料 + 助剂）
# 采用文献中白色底漆的典型配比（树脂:固化剂:溶剂:颜料 ≈ 100:10:30:45）
def ext_comp(resin_code):
    return {
        resin_code: 100.0,
        'EXT_MELAMINE': 10.0,   # 六甲氧基甲基三聚氰胺
        'EXT_SOLVENT': 30.0,    # 混合溶剂(DBE/甲氧基丙醇/溶剂油)
        'EXT_PIGMENT': 45.0,    # 钛白+滑石+缓蚀颜料
        'EXT_ADDITIVE': 1.5,    # 润湿分散+流变助剂
        'EXT_CATALYST': 0.8,    # 氨基封闭酸催化剂
    }

# 扩展原料库
ext_lib = dict(mat_lib)
ext_lib.update(EXT_RESINS)
ext_lib.update({
    'EXT_MELAMINE': dict(role='固化剂', rtype='其他', NV=98, density=1.2, Mw=390, EEW=0,
        AV=0, OHV=0, amine=0, func=6, Tg=0, bp=200, fp=100, dD=18, dP=8, dH=10, pol=4,
        evap=0, C=55, H=8, O=25, N=12, S=0, Cl=0, fg_epoxy=0, fg_oh=0.2, fg_cooh=0,
        fg_ester=0.3, fg_amine=0.3, fg_amide=0.3, fg_arom=0, fg_ether=0.4, wax=0, pig=0),
    'EXT_SOLVENT': dict(role='溶剂', rtype='其他', NV=0, density=0.95, Mw=150, EEW=0,
        AV=0, OHV=0, amine=0, func=0, Tg=-50, bp=180, fp=50, dD=17, dP=5, dH=6, pol=2,
        evap=0.3, C=65, H=11, O=24, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.1, fg_cooh=0,
        fg_ester=0.2, fg_amine=0, fg_amide=0, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'EXT_PIGMENT': dict(role='颜料', rtype='其他', NV=100, density=4.0, Mw=80, EEW=0,
        AV=0, OHV=0, amine=0, func=0, Tg=0, bp=2000, fp=1000, dD=20, dP=10, dH=8, pol=5,
        evap=0, C=0, H=0, O=40, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.1, fg_cooh=0.1,
        fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0, wax=0, pig=100),
    'EXT_ADDITIVE': dict(role='助剂', rtype='其他', NV=50, density=1.0, Mw=1000, EEW=0,
        AV=0, OHV=0, amine=0, func=0, Tg=0, bp=300, fp=150, dD=18, dP=7, dH=8, pol=3,
        evap=0, C=60, H=9, O=25, N=5, S=0, Cl=0, fg_epoxy=0, fg_oh=0.2, fg_cooh=0.1,
        fg_ester=0.2, fg_amine=0.1, fg_amide=0.1, fg_arom=0.1, fg_ether=0.2, wax=0, pig=0),
    'EXT_CATALYST': dict(role='助剂', rtype='其他', NV=25, density=1.0, Mw=200, EEW=0,
        AV=0, OHV=0, amine=0, func=0, Tg=0, bp=200, fp=100, dD=18, dP=8, dH=8, pol=4,
        evap=0, C=40, H=8, O=30, N=10, S=5, Cl=0, fg_epoxy=0, fg_oh=0.1, fg_cooh=0.2,
        fg_ester=0.1, fg_amine=0.1, fg_amide=0, fg_arom=0.1, fg_ether=0.1, wax=0, pig=0),
})

# 外部样本特征（树脂级尽力映射）
ext_rows, ext_names = [], []
for rc in ['RES-STD', 'RES-FDCA1', 'RES-FDCA2', 'RES-FDCA4', 'RES-FDCA8', 'RES-FDCA22', 'RES-FDCA31']:
    comp = ext_comp(rc)
    # 用扩展库构建特征：组分列用扩展库代码，但特征布局与当前一致
    comp2 = {canon(k): v for k, v in comp.items()}
    row = [float(comp2.get(c, 0)) for c in present_codes]
    row.append(232.0)  # bake_temp (PMT 232°C)
    row.append(37.0)   # bake_time (37s)
    d = enhanced_descriptors(comp2, ext_lib, bake_temp=232, bake_time=37)
    if d is None:
        continue
    row += [d.get(f, 0.0) for f in ENH_FEATURES]
    row += explicit_ratios(comp2)
    smi = smi_aggregate(comp2)
    row += [smi.get(k, 0.0) for k in SMI_AGG_KEYS]
    ext_rows.append(row); ext_names.append(rc)
X_ext = np.array(ext_rows)
print(f'外部样本: {X_ext.shape} ({len(ext_names)} 个涂层)', flush=True)

# OOD 距离：外部样本到当前 T弯 训练样本的最近邻距离（标准化后）
dT = get_data('T弯')
Xt, yt, sert = dT
rn = np.ptp(Xt, 0); rn[rn == 0] = 1
Xt_n = Xt / rn
Xext_n = X_ext / rn
D = cdist(Xext_n, Xt_n)
nn_dist = D.min(axis=1)
# 当前样本内部的最近邻距离（对照）
D_in = cdist(Xt_n, Xt_n); np.fill_diagonal(D_in, np.inf)
in_nn = D_in.min(axis=1)
print(f'当前样本内部最近邻距离: 中位数={np.median(in_nn):.3f}, P90={np.percentile(in_nn,90):.3f}')
print(f'外部样本到当前样本最近邻距离: 中位数={np.median(nn_dist):.3f}, 范围=[{nn_dist.min():.3f}, {nn_dist.max():.3f}]')
print(f'外部样本 OOD 倍数: 中位数={np.median(nn_dist)/np.median(in_nn):.2f}x 当前样本间距')

# ============================================================
# E-2 目标尺度兼容性
# ============================================================
print('\n' + '=' * 72)
print('E-2 目标尺度兼容性：T弯(mm) vs 外部 T-bend(T值)')
print('=' * 72)
print(f'当前 T弯: n={len(yt)}, 范围=[{yt.min():.2f}, {yt.max():.2f}] mm, 均值={yt.mean():.2f}')
ext_tbend = {'RES-STD': '2T', 'RES-FDCA1': '0.5T', 'RES-FDCA2': '1T', 'RES-FDCA4': '0.5T',
             'RES-FDCA8': '1.5T', 'RES-FDCA22': '1T', 'RES-FDCA31': '1.5T'}
print('外部 T-bend (T值):', ext_tbend)
print('→ 尺度不同：当前为连续 mm 值(10.8~26.7)，外部为离散 T 值(0.5T~2T)')
print('→ 无可靠换算关系（T值依赖板厚/弯曲半径协议），无法直接合并')
print('→ 外部 MEK 全部为截尾值(>100 DR)，与当前 MEK(2~550, 截尾@300) 口径不同')

# ============================================================
# E-3 强制合并实验：外部样本加入训练集对 T弯 R² 的影响
# ============================================================
print('\n' + '=' * 72)
print('E-3 强制合并实验：外部样本加入训练集 → 当前 T弯 R² 变化')
print('=' * 72)
# 由于尺度不同，外部 T 值无法直接作为 mm 标签。
# 采用「代理标签」方式：把外部 T 值映射为当前 T弯 分位数（0.5T→P10, 1T→P40, 1.5T→P60, 2T→P80）
# 这只是一种尽力而为的尺度对齐，用于量化「即便强行合并」的影响。
qmap = {'0.5T': 0.10, '1T': 0.40, '1.5T': 0.60, '2T': 0.80}
ext_y = np.array([np.quantile(yt, qmap[v]) for v in ext_tbend.values()])
print('外部代理标签 (分位数映射):', {k: round(float(v), 1) for k, v in zip(ext_names, ext_y)})

def cv_reg(Xs, y_orig, ser, k=8, nseed=10, w=0.85, trans=np.sqrt, inv=lambda p: p**2,
           xgb_p=None, lgb_p=None):
    yt = trans(y_orig)
    r2s = []
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        # 系列编码（折叠内OOF）
        gm = yt[tr].mean()
        enc = {}
        for s in set(np.array(ser)[tr]):
            vals = yt[tr][np.array(ser)[tr] == s]
            enc[s] = (len(vals) * vals.mean() + k * gm) / (len(vals) + k)
        Xtr = np.hstack([Xs[tr], np.array([enc.get(s, gm) for s in np.array(ser)[tr]]).reshape(-1, 1)])
        Xte = np.hstack([Xs[te], np.array([enc.get(s, gm) for s in np.array(ser)[te]]).reshape(-1, 1)])
        px, pl = [], []
        for sd in range(nseed):
            mx = XGBRegressor(n_estimators=1000, random_state=42 + sd, n_jobs=-1,
                              **(xgb_p or dict(learning_rate=0.015, max_depth=3, subsample=0.7,
                                               colsample_bytree=0.8, min_child_weight=1)))
            mx.fit(Xtr, yt[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(n_estimators=1000, random_state=42 + sd, n_jobs=-1, verbose=-1,
                               **(lgb_p or dict(learning_rate=0.015, num_leaves=15, max_depth=3,
                                                subsample=0.7, colsample_bytree=0.8, min_child_samples=10)))
            ml.fit(Xtr, yt[tr]); pl.append(ml.predict(Xte))
        pred = w * np.mean(px, axis=0) + (1 - w) * np.mean(pl, axis=0)
        if inv is not None:
            pred = inv(pred)
        r2s.append(r2_score(y_orig[te], pred))
    return np.mean(r2s)

# 特征选择（用当前 T弯 数据）
from xgboost import XGBRegressor as _X
imp_m = _X(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8,
           colsample_bytree=0.8, random_state=42, n_jobs=-1)
imp_m.fit(Xt, np.sqrt(yt))
keep = np.argsort(imp_m.feature_importances_)[-60:]
Xs = Xt[:, keep]

# 基线（当前数据，10种子）
r2_base = cv_reg(Xs, yt, sert)
print(f'基线(仅当前数据): R²={r2_base:.4f} (n={len(yt)})')

# 合并外部样本（作为独立新系列）
X_comb = np.vstack([Xs, X_ext[:, keep]])
y_comb = np.concatenate([yt, ext_y])
ser_comb = list(sert) + [f'EXT_{i}' for i in range(len(ext_y))]
r2_merge = cv_reg(X_comb, y_comb, ser_comb)
print(f'合并外部样本(尽力映射): R²={r2_merge:.4f} (n={len(y_comb)}, 外部={len(ext_y)})')
print(f'ΔR² = {r2_merge - r2_base:+.4f}')

# 对照：加入等量「当前分布内」的合成样本（验证数据量本身是否有用）
rs = np.random.RandomState(0)
syn_idx = rs.choice(len(Xt), len(ext_y), replace=False)
X_syn = Xs[syn_idx]
y_syn = yt[syn_idx] + rs.normal(0, 1.244, len(syn_idx))  # 加测量噪声的重复样本
X_comb2 = np.vstack([Xs, X_syn])
y_comb2 = np.concatenate([yt, y_syn])
ser_comb2 = list(sert) + [f'SYN_{i}' for i in range(len(y_syn))]
r2_syn = cv_reg(X_comb2, y_comb2, ser_comb2)
print(f'对照-加入等量分布内重复样本: R²={r2_syn:.4f} (n={len(y_comb2)})')
print(f'ΔR² = {r2_syn - r2_base:+.4f}')

# ============================================================
# E-4 噪声地板复核
# ============================================================
print('\n' + '=' * 72)
print('E-4 噪声地板复核：T弯 R² 理论上限')
print('=' * 72)
noise_std = 1.244
total_std = yt.std()
floor = 1 - noise_std ** 2 / total_std ** 2
print(f'T弯: 重复测量噪声 std={noise_std}, 总 std={total_std:.3f}')
print(f'噪声地板 R² 上限 = {floor:.3f}')
print(f'当前模型 R²=0.791 ≈ 上限 → 换模型/加特征/加同质数据均无法突破')
print(f'R²>0.9 需噪声 ≤ {np.sqrt((1-0.9)*total_std**2):.3f} (减半) 或重复测量 4 次取均值')
print(f'外部数据无法降低当前数据的测量噪声 → 对 R²>0.9 无直接帮助')

print('\n完成', flush=True)
