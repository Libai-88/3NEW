# -*- coding: utf-8 -*-
"""
水煮指标分层建模方案：按化学体系(环氧酚醛/聚酯金黄)分而治之
============================================================
- 复用 mvp74_final_verify 完全一致的水煮建模块（每系列阈值 + keep=80 + 20 种子）
- 每个体系单独做特征选择/模型/每系列阈值，再按样本量加权汇总
- 对照：池化(现状) vs 分层逐体系 vs 分层综合
用法：python scripts/stratified_water.py   （读取 ../合并版数据集.xlsx，相对路径）
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import accuracy_score, roc_auc_score
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'workbench'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CoatingModelWorkbench import load_dataset, ENH_FEATURES, explicit_ratios, smi_aggregate, SMI_AGG_KEYS, canon, enhanced_descriptors, _bake_feat

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '合并版数据集.xlsx')
mat_lib, samples, perf, proc = load_dataset(path)
present_codes = sorted(set(canon(str(c).strip()) for s in samples.values() for c in s['组分']))
NSEED = 20

def build_compact(comp, mat_lib, bt=None, btm=None):
    comp = {canon(k): v for k, v in comp.items()}
    row = [float(comp.get(c, 0)) for c in present_codes]
    row.append(_bake_feat(bt)); row.append(_bake_feat(btm))
    d = enhanced_descriptors(comp, mat_lib, bake_temp=bt, bake_time=btm)
    if d is None: return None
    row += [d.get(f, 0.0) for f in ENH_FEATURES] + explicit_ratios(comp)
    smi = smi_aggregate(comp); row += [smi.get(k, 0.0) for k in SMI_AGG_KEYS]
    return row

X, ids, series, fams = [], [], [], []
for sid, s in samples.items():
    p = proc.get(sid, {})
    row = build_compact(s['组分'], mat_lib, bt=p.get('烘烤温度'), btm=p.get('烘烤时间'))
    if row is None: continue
    X.append(row); ids.append(sid); series.append(s.get('系列', '')); fams.append(s.get('体系', '?'))
X = np.array(X); fams = np.array(fams)

def get_data(fam_mask, tgt='水煮等级'):
    idx = []
    for i, sid in enumerate(ids):
        if not fam_mask[i]: continue
        v = perf.get(sid, {}).get(tgt)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            idx.append(i)
    if len(idx) < 5: return None
    return X[idx], np.array([float(perf[ids[i]]['水煮等级']) for i in idx]), [series[i] for i in idx]

def add_series(Xtr, Xte, y_tr, ser_tr, ser_te, k=3):
    gm = y_tr.mean(); enc = {}; cnt = {}; std = {}
    for s in set(ser_tr):
        vals = y_tr[ser_tr == s]; n = len(vals)
        cnt[s] = n; std[s] = vals.std() if n > 1 else 0.0
        enc[s] = (n*vals.mean() + k*gm)/(n+k)
    Xtr = np.hstack([Xtr, np.array([enc.get(s, gm) for s in ser_tr]).reshape(-1, 1)])
    Xte = np.hstack([Xte, np.array([enc.get(s, gm) for s in ser_te]).reshape(-1, 1)])
    Xtr = np.hstack([Xtr, np.array([cnt.get(s, 0) for s in ser_tr]).reshape(-1, 1)])
    Xte = np.hstack([Xte, np.array([cnt.get(s, 0) for s in ser_te]).reshape(-1, 1)])
    Xtr = np.hstack([Xtr, np.array([std.get(s, 0) for s in ser_tr]).reshape(-1, 1)])
    Xte = np.hstack([Xte, np.array([std.get(s, 0) for s in ser_te]).reshape(-1, 1)])
    for s in sorted(set(ser_tr)):
        Xtr = np.hstack([Xtr, (ser_tr == s).astype(float).reshape(-1, 1)])
        Xte = np.hstack([Xte, (ser_te == s).astype(float).reshape(-1, 1)])
    return Xtr, Xte

def get_imp(X, y):
    m = XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, y); return m.feature_importances_

def water_block(Xz, yz, serz, tag):
    y2 = (yz.astype(int) >= 4).astype(int)
    imp = get_imp(Xz, y2)
    Xs = Xz[:, np.argsort(imp)[-80:]]
    oof_p = np.zeros(len(y2))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], y2[tr], np.array(serz)[tr], np.array(serz)[te], 3)
        p_list = []
        for sd in range(NSEED):
            mx = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8, random_state=42+sd, n_jobs=-1)
            mx.fit(Xtr, y2[tr]); p_list.append(mx.predict_proba(Xte)[:, 1])
            ml = LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=15, max_depth=3, subsample=0.8, colsample_bytree=0.8, random_state=42+sd, n_jobs=-1, verbose=-1)
            ml.fit(Xtr, y2[tr]); p_list.append(ml.predict_proba(Xte)[:, 1])
        oof_p[te] = np.mean(p_list, axis=0)
    best_g = (0, 0.5)
    for th in np.arange(0.35, 0.66, 0.005):
        a = accuracy_score(y2, (oof_p >= th).astype(int))
        if a > best_g[0]: best_g = (a, th)
    pred = np.zeros(len(y2))
    for s in set(serz):
        mask = np.array(serz) == s
        if mask.sum() >= 8:
            best = (0, best_g[1])
            for th in np.arange(0.35, 0.66, 0.005):
                a = accuracy_score(y2[mask], (oof_p[mask] >= th).astype(int))
                if a > best[0]: best = (a, th)
            pred[mask] = (oof_p[mask] >= best[1]).astype(int)
        else:
            pred[mask] = (oof_p[mask] >= best_g[1]).astype(int)
    acc = accuracy_score(y2, pred)
    auc = roc_auc_score(y2, oof_p) if len(set(y2)) > 1 else float('nan')
    print(f'  [{tag}] 分层水煮: acc={acc:.3f} (n={len(y2)}, 正类率={y2.mean():.3f}, 系列数={len(set(serz))}, auc={auc:.3f})')
    return y2, pred

print('====== 水煮 · 分层建模对比 ======')
print('基线(纯环氧,历史) acc=0.804 (n=189)')
res = {}
for fam in ['环氧酚醛', '聚酯金黄']:
    d = get_data(fams == fam)
    if d is None:
        print(f'  [{fam}] 样本过少，跳过'); continue
    y2, pred = water_block(*d, fam)
    res[fam] = (len(y2), float((y2 == pred).mean()))
tot_w = sum(n for n, _ in res.values())
blend = sum(n*a for n, a in res.values()) / tot_w
print(f'\n  分层综合(按样本量加权): acc={blend:.3f} (n={tot_w})')
print('  各体系:', {k: round(a, 3) for k, (n, a) in res.items()})
print('  对照-池化(现状): acc=0.777 (n=215)')
print('  对照-基线(纯环氧): acc=0.804 (n=189)')