# -*- coding: utf-8 -*-
"""
半监督/伪标签实验 (Semi-Supervised on Merged Dataset)
=====================================================
验证：当前数据集中 164 个无标签配方（环氧-配比方案112/聚酯金黄29/环氧酚醛23）
能否通过伪标签回放提升 T弯 模型性能。
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
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
from CoatingModelWorkbench import (load_dataset, ENH_FEATURES, explicit_ratios,
                                   smi_aggregate, SMI_AGG_KEYS, canon,
                                   enhanced_descriptors)

BASE = _GEN_DIR
mat_lib, samples, perf, proc = load_dataset(os.path.join(BASE, '合并版数据集.xlsx'))
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

X, ids, series, sysnames = [], [], [], []
for sid, s in samples.items():
    p = proc.get(sid, {})
    row = build_compact(s['组分'], mat_lib, bt=p.get('烘烤温度'), btm=p.get('烘烤时间'))
    if row is None:
        continue
    X.append(row); ids.append(sid); series.append(s.get('系列', '')); sysnames.append(s.get('体系', ''))
X = np.array(X)

# 有标签/无标签划分（T弯）
lab_idx, unlab_idx = [], []
for i, sid in enumerate(ids):
    v = perf.get(sid, {}).get('T弯')
    if v is not None and not (isinstance(v, float) and np.isnan(v)):
        lab_idx.append(i)
    else:
        unlab_idx.append(i)
print(f'T弯: 有标签={len(lab_idx)}, 无标签={len(unlab_idx)}', flush=True)

# 无标签样本的体系分布
from collections import Counter
unlab_sys = Counter(sysnames[i] for i in unlab_idx)
print('无标签体系分布:', dict(unlab_sys), flush=True)

# 特征空间距离：无标签样本是否在分布内
Xl = X[lab_idx]
rn = np.ptp(Xl, 0); rn[rn == 0] = 1
Xl_n = Xl / rn
Xu_n = X[unlab_idx] / rn
D = cdist(Xu_n, Xl_n)
nn_dist = D.min(axis=1)
D_in = cdist(Xl_n, Xl_n); np.fill_diagonal(D_in, np.inf)
in_nn = D_in.min(axis=1)
print(f'有标签样本内部最近邻: 中位数={np.median(in_nn):.3f}', flush=True)
for sysname in set(sysnames[i] for i in unlab_idx):
    mask = np.array([sysnames[i] for i in unlab_idx]) == sysname
    if mask.sum() >= 3:
        print(f'  无标签[{sysname}] n={mask.sum()} 最近邻距离中位数={np.median(nn_dist[mask]):.3f} '
              f'(OOD倍数={np.median(nn_dist[mask])/np.median(in_nn):.1f}x)', flush=True)

# 伪标签回放实验（仅用分布内无标签样本）
def cv_reg(Xs, y_orig, ser, k=8, nseed=5, w=0.85, trans=np.sqrt, inv=lambda p: p**2, est=400):
    yt = trans(y_orig)
    r2s = []
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        gm = yt[tr].mean()
        enc = {}
        for s in set(np.array(ser)[tr]):
            vals = yt[tr][np.array(ser)[tr] == s]
            enc[s] = (len(vals) * vals.mean() + k * gm) / (len(vals) + k)
        Xtr = np.hstack([Xs[tr], np.array([enc.get(s, gm) for s in np.array(ser)[tr]]).reshape(-1, 1)])
        Xte = np.hstack([Xs[te], np.array([enc.get(s, gm) for s in np.array(ser)[te]]).reshape(-1, 1)])
        px, pl = [], []
        for sd in range(nseed):
            mx = XGBRegressor(n_estimators=est, random_state=42 + sd, n_jobs=-1,
                              learning_rate=0.015, max_depth=3, subsample=0.7,
                              colsample_bytree=0.8, min_child_weight=1)
            mx.fit(Xtr, yt[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(n_estimators=est, random_state=42 + sd, n_jobs=-1, verbose=-1,
                               learning_rate=0.015, num_leaves=15, max_depth=3,
                               subsample=0.7, colsample_bytree=0.8, min_child_samples=10)
            ml.fit(Xtr, yt[tr]); pl.append(ml.predict(Xte))
        pred = w * np.mean(px, axis=0) + (1 - w) * np.mean(pl, axis=0)
        if inv is not None:
            pred = inv(pred)
        r2s.append(r2_score(y_orig[te], pred))
    return np.mean(r2s)

# 特征选择
imp_m = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8,
                     colsample_bytree=0.8, random_state=42, n_jobs=-1)
imp_m.fit(Xl, np.sqrt(np.array([perf[ids[i]]['T弯'] for i in lab_idx])))
keep = np.argsort(imp_m.feature_importances_)[-60:]
Xs_lab = Xl[:, keep]

ylab = np.array([perf[ids[i]]['T弯'] for i in lab_idx])
serlab = [series[i] for i in lab_idx]
r2_base = cv_reg(Xs_lab, ylab, serlab)
print(f'\n基线(仅标签数据): R²={r2_base:.4f} (n={len(ylab)})', flush=True)

# 用分布内无标签样本（环氧-配比方案 + 环氧酚醛无标签）生成伪标签
in_mask = np.array([sysnames[i] in ('环氧-配比方案', '环氧酚醛') for i in unlab_idx])
Xu_in = X[np.array(unlab_idx)[in_mask]][:, keep]
print(f'分布内无标签样本: {Xu_in.shape[0]} 个', flush=True)

if len(Xu_in) >= 10:
    # 训练伪标签生成器（5折OOF预测，避免自训练泄漏）
    yt_all = np.sqrt(ylab)
    pseudo_pred = np.zeros(len(Xu_in))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs_lab):
        Xtr, Xte = Xs_lab[tr], Xs_lab[te]
        px = []
        for sd in range(5):
            m = XGBRegressor(n_estimators=1000, random_state=42 + sd, n_jobs=-1,
                             learning_rate=0.015, max_depth=3, subsample=0.7,
                             colsample_bytree=0.8, min_child_weight=1)
            m.fit(Xtr, yt_all[tr]); px.append(m.predict(Xte))
        # 对无标签样本预测
        pp = []
        for sd in range(5):
            m = XGBRegressor(n_estimators=1000, random_state=42 + sd, n_jobs=-1,
                             learning_rate=0.015, max_depth=3, subsample=0.7,
                             colsample_bytree=0.8, min_child_weight=1)
            m.fit(Xtr, yt_all[tr]); pp.append(m.predict(Xu_in))
        pseudo_pred += np.mean(pp, axis=0) / 5
    pseudo_y = pseudo_pred ** 2

    # 高置信伪标签（预测值在合理范围内）
    conf_mask = (pseudo_y > ylab.min()) & (pseudo_y < ylab.max())
    print(f'高置信伪标签: {conf_mask.sum()}/{len(pseudo_y)} 个', flush=True)

    # 伪标签回放
    for wgt in [0.3, 0.5, 1.0]:
        X_comb = np.vstack([Xs_lab, Xu_in[conf_mask]])
        y_comb = np.concatenate([ylab, pseudo_y[conf_mask]])
        ser_comb = list(serlab) + [f'PL_{i}' for i in range(conf_mask.sum())]
        # 加权：伪标签权重 wgt（通过复制实现近似）
        if wgt < 1.0:
            n_rep = max(1, int(round(wgt * 10)))
            X_comb = np.vstack([Xs_lab] + [Xu_in[conf_mask]] * n_rep)
            y_comb = np.concatenate([ylab] + [pseudo_y[conf_mask]] * n_rep)
            ser_comb = list(serlab) + [f'PL_{i}' for i in range(conf_mask.sum())] * n_rep
        r2_pl = cv_reg(X_comb, y_comb, ser_comb)
        print(f'伪标签回放(w={wgt}): R²={r2_pl:.4f} (Δ={r2_pl - r2_base:+.4f})', flush=True)

print('\n完成', flush=True)
