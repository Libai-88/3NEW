# -*- coding: utf-8 -*-
"""
主动学习模拟 (Active Learning Simulation)
=========================================
核心问题：实验室产能有限，209 个无标签配方中，先标注哪些能最大化 R² 提升？
对比策略：
  - 随机标注 (random)
  - 不确定性优先 (uncertainty: 模型树间方差最大)
  - 多样性/探索优先 (diversity: 距已标注集最远 = OOD 探索)
  - 混合策略 (hybrid: 不确定性 + 多样性加权)
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
from collections import Counter
from scipy.spatial.distance import cdist
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor

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

lab_idx, unlab_idx = [], []
for i, sid in enumerate(ids):
    v = perf.get(sid, {}).get('T弯')
    if v is not None and not (isinstance(v, float) and np.isnan(v)):
        lab_idx.append(i)
    else:
        unlab_idx.append(i)
print(f'T弯: 有标签={len(lab_idx)}, 无标签={len(unlab_idx)}', flush=True)

# 特征选择（与半监督实验一致）
Xl = X[lab_idx]
ylab = np.array([perf[ids[i]]['T弯'] for i in lab_idx])
imp_m = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8,
                     colsample_bytree=0.8, random_state=42, n_jobs=-1)
imp_m.fit(Xl, np.sqrt(ylab))
keep = np.argsort(imp_m.feature_importances_)[-60:]
Xs_lab = Xl[:, keep]
Xu = X[unlab_idx][:, keep]
serlab = [series[i] for i in lab_idx]

# 归一化（用于距离计算）
rn = np.ptp(np.vstack([Xs_lab, Xu]), 0); rn[rn == 0] = 1
Xl_n = Xs_lab / rn
Xu_n = Xu / rn

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

# 基线
r2_base = cv_reg(Xs_lab, ylab, serlab)
print(f'\n基线(仅当前标签): R²={r2_base:.4f} (n={len(ylab)})', flush=True)

# 模拟：从无标签池中挑选 B 个样本"真实标注"（用伪标签近似真实值，仅用于排序评估）
# 注意：这里用伪标签近似"真实标注后的值"，评估的是"选哪些样本标注"的收益排序
B = 30  # 标注预算
rng = np.random.RandomState(42)

# 预计算不确定性（模型树间方差）与多样性（到已标注集距离）
def uncertainty_scores(Xtr, ytr, Xq):
    """用 RF 树间方差估计不确定性"""
    yt = np.sqrt(ytr)
    m = RandomForestRegressor(n_estimators=200, max_depth=8, min_samples_leaf=3,
                              random_state=42, n_jobs=-1)
    m.fit(Xtr, yt)
    preds = np.array([t.predict(Xq) for t in m.estimators_])
    return preds.std(axis=0)

def diversity_scores(Xl_n, Xu_n):
    """到已标注集的最小距离（越大越 OOD）"""
    D = cdist(Xu_n, Xl_n)
    return D.min(axis=1)

# 各策略选出的样本
strategies = {}
unc = uncertainty_scores(Xs_lab, ylab, Xu)
div = diversity_scores(Xl_n, Xu_n)

# 随机
strategies['随机'] = rng.choice(len(Xu), B, replace=False)
# 不确定性
strategies['不确定性优先'] = np.argsort(unc)[-B:]
# 多样性
strategies['多样性优先'] = np.argsort(div)[-B:]
# 混合（不确定性+多样性 归一化加权）
unc_n = (unc - unc.min()) / (unc.max() - unc.min() + 1e-9)
div_n = (div - div.min()) / (div.max() - div.min() + 1e-9)
hyb = 0.5 * unc_n + 0.5 * div_n
strategies['混合(不确定+多样)'] = np.argsort(hyb)[-B:]

print(f'\n标注预算 B={B}，各策略选中的无标签样本体系分布：', flush=True)
for name, sel in strategies.items():
    cnt = Counter(sysnames[unlab_idx[i]] for i in sel)
    print(f'  {name}: {dict(cnt)}', flush=True)

# 用伪标签近似"标注后的真实值"（OOF 预测，避免泄漏），评估各策略的 R² 提升
print(f'\n各策略标注后 R² 提升（伪标签近似真实标注）：', flush=True)
for name, sel in strategies.items():
    # 伪标签：用全量标签数据 OOF 预测无标签样本
    yt_all = np.sqrt(ylab)
    pp = np.zeros(len(Xu))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs_lab):
        for sd in range(5):
            m = XGBRegressor(n_estimators=1000, random_state=42 + sd, n_jobs=-1,
                             learning_rate=0.015, max_depth=3, subsample=0.7,
                             colsample_bytree=0.8, min_child_weight=1)
            m.fit(Xs_lab[tr], yt_all[tr]); pp += m.predict(Xu) / 25
    pseudo_y = pp ** 2
    # 选中的样本加入训练集（伪标签当真实值）
    X_comb = np.vstack([Xs_lab, Xu[sel]])
    y_comb = np.concatenate([ylab, pseudo_y[sel]])
    ser_comb = list(serlab) + [f'AL_{i}' for i in range(B)]
    r2_new = cv_reg(X_comb, y_comb, ser_comb)
    print(f'  {name}: R²={r2_new:.4f} (Δ={r2_new - r2_base:+.4f})', flush=True)

# 主动学习迭代：每轮标注 B/3 个，重训模型，更新不确定性
print(f'\n迭代式主动学习（3 轮 × {B//3} 个）：', flush=True)
for name in ['随机', '不确定性优先', '混合(不确定+多样)']:
    cur_lab = list(range(len(ylab)))
    cur_unlab = list(range(len(Xu)))
    Xcur = Xs_lab.copy()
    ycur = ylab.copy()
    sercur = list(serlab)
    Xl_n_cur = Xl_n.copy()
    for rnd in range(3):
        if len(cur_unlab) == 0:
            break
        Xu_cur = Xu[cur_unlab]
        Xu_n_cur = Xu_n[cur_unlab]
        unc_cur = uncertainty_scores(Xcur, ycur, Xu_cur)
        div_cur = diversity_scores(Xl_n_cur, Xu_n_cur)
        if name == '随机':
            sel = rng.choice(len(cur_unlab), min(B // 3, len(cur_unlab)), replace=False)
        elif name == '不确定性优先':
            sel = np.argsort(unc_cur)[-min(B // 3, len(cur_unlab)):]
        else:
            unc_n = (unc_cur - unc_cur.min()) / (unc_cur.max() - unc_cur.min() + 1e-9)
            div_n = (div_cur - div_cur.min()) / (div_cur.max() - div_cur.min() + 1e-9)
            hyb = 0.5 * unc_n + 0.5 * div_n
            sel = np.argsort(hyb)[-min(B // 3, len(cur_unlab)):]
        # 伪标签近似真实标注
        yt_all = np.sqrt(ycur)
        pp = np.zeros(len(Xu_cur))
        kf = KFold(5, shuffle=True, random_state=42)
        for tr, te in kf.split(Xcur):
            for sd in range(5):
                m = XGBRegressor(n_estimators=1000, random_state=42 + sd, n_jobs=-1,
                                 learning_rate=0.015, max_depth=3, subsample=0.7,
                                 colsample_bytree=0.8, min_child_weight=1)
                m.fit(Xcur[tr], yt_all[tr]); pp += m.predict(Xu_cur) / 25
        pseudo_y = pp ** 2
        Xcur = np.vstack([Xcur, Xu_cur[sel]])
        ycur = np.concatenate([ycur, pseudo_y[sel]])
        sercur += [f'AL_{rnd}_{i}' for i in range(len(sel))]
        Xl_n_cur = np.vstack([Xl_n_cur, Xu_n_cur[sel]])
        cur_unlab = [i for j, i in enumerate(cur_unlab) if j not in set(sel)]
        r2_it = cv_reg(Xcur, ycur, sercur)
        print(f'  {name} 第{rnd+1}轮(+{len(sel)}): R²={r2_it:.4f} (Δ={r2_it - r2_base:+.4f})', flush=True)

print('\n完成', flush=True)
