# -*- coding: utf-8 -*-
"""
实验 J：噪声地板严格估计 + 多任务/机理特征/加权回归 真实提升验证
================================================================
目标：诚实评估 R²>0.9 的可达性，验证多任务学习、机理特征、加权回归是否真实提升。
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
from collections import defaultdict
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, accuracy_score, roc_auc_score
from xgboost import XGBRegressor, XGBClassifier
from lightgbm import LGBMRegressor, LGBMClassifier
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'workbench'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CoatingModelWorkbench import load_dataset, ENH_FEATURES, explicit_ratios, smi_aggregate, SMI_AGG_KEYS, canon, enhanced_descriptors

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '合并版数据集.xlsx')
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

X, ids, series = [], [], []
for sid, s in samples.items():
    p = proc.get(sid, {})
    row = build_compact(s['组分'], mat_lib, bt=p.get('烘烤温度'), btm=p.get('烘烤时间'))
    if row is None:
        continue
    X.append(row); ids.append(sid); series.append(s.get('系列', ''))
X = np.array(X)

def get_data(tgt):
    y_list, idx = [], []
    for i, sid in enumerate(ids):
        v = perf.get(sid, {}).get(tgt)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            y_list.append(v); idx.append(i)
    if len(y_list) < 30:
        return None
    return X[idx], np.array(y_list), [series[i] for i in idx]

def add_series(Xtr, Xte, y_tr, ser_tr, ser_te, k=3):
    gm = y_tr.mean()
    enc = {}; cnt = {}; std = {}
    for s in set(ser_tr):
        vals = y_tr[ser_tr==s]
        n = len(vals)
        cnt[s] = n; std[s] = vals.std() if n > 1 else 0.0
        enc[s] = (n*vals.mean() + k*gm)/(n+k)
    Xtr = np.hstack([Xtr, np.array([enc.get(s,gm) for s in ser_tr]).reshape(-1,1)])
    Xte = np.hstack([Xte, np.array([enc.get(s,gm) for s in ser_te]).reshape(-1,1)])
    Xtr = np.hstack([Xtr, np.array([cnt.get(s,0) for s in ser_tr]).reshape(-1,1)])
    Xte = np.hstack([Xte, np.array([cnt.get(s,0) for s in ser_te]).reshape(-1,1)])
    Xtr = np.hstack([Xtr, np.array([std.get(s,0) for s in ser_tr]).reshape(-1,1)])
    Xte = np.hstack([Xte, np.array([std.get(s,0) for s in ser_te]).reshape(-1,1)])
    all_ser = sorted(set(ser_tr))
    for s in all_ser:
        Xtr = np.hstack([Xtr, (ser_tr==s).astype(float).reshape(-1,1)])
        Xte = np.hstack([Xte, (ser_te==s).astype(float).reshape(-1,1)])
    return Xtr, Xte

def get_imp(X, y, clf=False):
    if clf:
        m = XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)
    else:
        m = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, y)
    return m.feature_importances_

NSEED = 20

def cv_reg(Xs, y_orig, ser, k, nseed=NSEED, est=800, trans=None, inv=None, w=0.5, xgb_p=None, lgb_p=None, sample_w=None, return_oof=False):
    yt = trans(y_orig) if trans is not None else y_orig
    r2s = []
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yt[tr], np.array(ser)[tr], np.array(ser)[te], k)
        sw = sample_w[tr] if sample_w is not None else None
        px, pl = [], []
        for sd in range(nseed):
            mx = XGBRegressor(n_estimators=est, random_state=42+sd, n_jobs=-1, **(xgb_p or dict(learning_rate=0.008, max_depth=4, subsample=0.8, colsample_bytree=0.7, min_child_weight=2)))
            mx.fit(Xtr, yt[tr], sample_weight=sw); px.append(mx.predict(Xte))
            ml = LGBMRegressor(n_estimators=est, random_state=42+sd, n_jobs=-1, verbose=-1, **(lgb_p or dict(learning_rate=0.008, num_leaves=15, max_depth=4, subsample=0.8, colsample_bytree=0.7, min_child_samples=10)))
            ml.fit(Xtr, yt[tr], sample_weight=sw); pl.append(ml.predict(Xte))
        pred = w*np.mean(px,axis=0) + (1-w)*np.mean(pl,axis=0)
        if inv is not None:
            pred = inv(pred)
        oof[te] = pred
        r2s.append(r2_score(y_orig[te], pred))
    if return_oof:
        return np.mean(r2s), oof
    return np.mean(r2s)

print('='*70)
print('实验 J-1: 噪声地板严格估计')
print('='*70)
# 用同系列内方差估计噪声（系列内样本共享大部分配方结构）
for tgt in ['T弯', 'MEK擦拭']:
    d = get_data(tgt)
    Xt, yt, sert = d
    # 系列内残差方差（用系列均值作为预测）
    ser_arr = np.array(sert)
    within_ss = 0; within_n = 0
    for s in set(sert):
        vals = yt[ser_arr==s]
        if len(vals) >= 2:
            within_ss += ((vals - vals.mean())**2).sum()
            within_n += len(vals) - 1
    if within_n > 0:
        noise2 = within_ss / within_n
        floor = 1 - noise2 / yt.var()
        print(f'  {tgt}: 系列内噪声 std={np.sqrt(noise2):.3f}, 总std={yt.std():.3f}, 噪声地板R²={floor:.3f}')

print()
print('='*70)
print('实验 J-2: 基线复现（当前最优配置）')
print('='*70)
# T弯
d = get_data('T弯')
Xt, yt, sert = d
imp = get_imp(Xt, np.sqrt(yt))
Xs = Xt[:, np.argsort(imp)[-60:]]
r2_base, oof = cv_reg(Xs, yt, sert, 8, w=0.85, est=1000, trans=np.sqrt, inv=lambda p: p**2,
                      xgb_p=dict(learning_rate=0.015, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_weight=1),
                      lgb_p=dict(learning_rate=0.015, num_leaves=15, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_samples=10),
                      return_oof=True)
print(f'  T弯 基线: R²={r2_base:.4f} (n={len(yt)})')
resid = yt - oof
NOISE_STD = 1.244
THR = 2.0 * NOISE_STD
mask = np.abs(resid) <= THR
Xt2, yt2v, sert2 = Xt[mask], yt[mask], [sert[i] for i in np.where(mask)[0]]
imp2 = get_imp(Xt2, np.sqrt(yt2v))
Xs2 = Xt2[:, np.argsort(imp2)[-60:]]
r2_f = cv_reg(Xs2, yt2v, sert2, 8, w=0.85, est=1000, trans=np.sqrt, inv=lambda p: p**2,
              xgb_p=dict(learning_rate=0.015, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_weight=1),
              lgb_p=dict(learning_rate=0.015, num_leaves=15, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_samples=10))
print(f'  T弯 噪声过滤后: R²={r2_f:.4f} (n={mask.sum()})')

print()
print('='*70)
print('实验 J-3: 加权回归（软噪声处理，不硬删样本）')
print('='*70)
# 用 OOF 残差构造权重：残差大 → 权重低
wts = np.clip(1 - np.abs(resid)/ (3*NOISE_STD), 0.1, 1.0)
r2_w = cv_reg(Xs, yt, sert, 8, w=0.85, est=1000, trans=np.sqrt, inv=lambda p: p**2,
              xgb_p=dict(learning_rate=0.015, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_weight=1),
              lgb_p=dict(learning_rate=0.015, num_leaves=15, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_samples=10),
              sample_w=wts)
print(f'  T弯 加权回归: R²={r2_w:.4f} (对比硬过滤 {r2_f:.4f})')

print()
print('='*70)
print('实验 J-4: 多任务学习（共享表征，联合预测 T弯/MEK）')
print('='*70)
# 多任务：用 T弯+MEK 联合样本，特征拼接目标编码，共享模型
d1 = get_data('T弯'); d2 = get_data('MEK擦拭')
X1, y1, s1 = d1; X2, y2, s2 = d2
# 交集样本（同时有 T弯 和 MEK 标签）
id_set1 = set(); id_set2 = set()
for i, sid in enumerate(ids):
    if perf.get(sid, {}).get('T弯') is not None: id_set1.add(sid)
    if perf.get(sid, {}).get('MEK擦拭') is not None: id_set2.add(sid)
common = id_set1 & id_set2
print(f'  同时有T弯+MEK标签的样本: {len(common)}')
# 多任务特征：为 T弯 模型加入 MEK 的系列编码作为辅助特征（利用任务相关性）
# 简单实现：MEK 系列均值编码作为 T弯 的额外特征
ser_mek_mean = {}
for s in set(s2):
    vals = y2[np.array(s2)==s]
    ser_mek_mean[s] = vals.mean()
X1_mt = np.hstack([X1, np.array([ser_mek_mean.get(ss, y2.mean()) for ss in s1]).reshape(-1,1)])
imp_mt = get_imp(X1_mt, np.sqrt(y1))
Xs_mt = X1_mt[:, np.argsort(imp_mt)[-61:]]
r2_mt = cv_reg(Xs_mt, y1, s1, 8, w=0.85, est=1000, trans=np.sqrt, inv=lambda p: p**2,
               xgb_p=dict(learning_rate=0.015, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_weight=1),
               lgb_p=dict(learning_rate=0.015, num_leaves=15, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_samples=10))
print(f'  T弯+MEK辅助特征: R²={r2_mt:.4f} (对比基线 {r2_base:.4f})')

print()
print('='*70)
print('实验 J-5: 机理特征增强（交联密度/固化度）')
print('='*70)
# 检查现有增强描述符中是否已有交联相关特征，尝试构造更物理的交联密度特征
# epoxy_eq_100g, oh_eq_100g 已存在。补充：交联密度 = min(epoxy_eq, oh_eq) / 100g
def xlink_density(comp, mat_lib):
    comp = {canon(k): v for k, v in comp.items()}
    total = sum(comp.values())
    if total <= 0: return 0, 0, 0
    epoxy_eq = 0; oh_eq = 0
    for c, amt in comp.items():
        d = mat_lib.get(c)
        if d is None: continue
        w = amt / total
        eew = d.get('EEW', 0)
        ohv = d.get('OHV', 0)
        if eew and eew > 0: epoxy_eq += w * 100 / eew
        if ohv and ohv > 0: oh_eq += w * ohv / 56.1
    xd = min(epoxy_eq, oh_eq)
    return epoxy_eq, oh_eq, xd

xfeat = []
for sid in ids:
    e, o, x = xlink_density(samples[sid]['组分'], mat_lib)
    xfeat.append([e, o, x, e-o, o-e])
xfeat = np.array(xfeat)
# 只取 T弯 样本对应的行
idx1 = [i for i, sid in enumerate(ids) if perf.get(sid, {}).get('T弯') is not None]
xfeat1 = xfeat[idx1]
X1_xl = np.hstack([X1, xfeat1])
imp_xl = get_imp(X1_xl, np.sqrt(y1))
Xs_xl = X1_xl[:, np.argsort(imp_xl)[-65:]]
r2_xl = cv_reg(Xs_xl, y1, s1, 8, w=0.85, est=1000, trans=np.sqrt, inv=lambda p: p**2,
               xgb_p=dict(learning_rate=0.015, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_weight=1),
               lgb_p=dict(learning_rate=0.015, num_leaves=15, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_samples=10))
print(f'  T弯+交联密度特征: R²={r2_xl:.4f} (对比基线 {r2_base:.4f})')

print()
print('='*70)
print('实验 J-6: 重复测量噪声严格估计（同配方重复样本）')
print('='*70)
from collections import defaultdict
comp_map = defaultdict(list)
for sid, s in samples.items():
    key = tuple(sorted((canon(c), round(float(a), 2)) for c, a in s['组分'].items()))
    comp_map[key].append(sid)
rep = {k: v for k, v in comp_map.items() if len(v) >= 2}
print(f'  完全相同配方的重复样本组: {len(rep)}')
for tgt in ['T弯', 'MEK擦拭', '水煮等级']:
    noises = []
    for k, sids in rep.items():
        vals = [perf.get(sid, {}).get(tgt) for sid in sids]
        vals = [v for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
        if len(vals) >= 2:
            noises.append(np.var(vals))
    if noises:
        noise_std = np.sqrt(np.mean(noises))
        d = get_data(tgt)
        Xt, yt, sert = d
        floor = 1 - noise_std**2 / yt.var()
        print(f'  {tgt}: 重复测量噪声 std={noise_std:.3f}, 总std={yt.std():.3f}, 噪声地板R²={floor:.3f} (n组={len(noises)})')
    else:
        print(f'  {tgt}: 无重复测量样本')

print()
print('完成')
