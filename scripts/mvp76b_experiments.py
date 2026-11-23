# -*- coding: utf-8 -*-
"""
实验 K-5：诚实两阶段 MEK 模型优化（软混合 + p_hi 特征）
================================================================
K-1~K-3 结论：当前代理目标法未截尾 R²=0.427（虚高 0.70 来自代理评估）；
未截尾回归 R²=0.474；硬阈值两阶段伤害未截尾 R²（假阳性被抬到≥300）。

本实验测试更优的诚实组合：
  K-5a: 未截尾回归 + p_hi 作为额外特征（分类器信息注入回归）
  K-5b: 软混合两阶段（final = reg*(1-p_hi) + high*p_hi，无硬阈值）
  K-5c: 未截尾回归 + 边界分类器（两个独立输出，诚实双指标）
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
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
MEK_CFG = dict(
    xgb=dict(n_estimators=1500, learning_rate=0.008, max_depth=4, subsample=0.8, colsample_bytree=0.7, min_child_weight=2),
    lgb=dict(n_estimators=1500, learning_rate=0.008, num_leaves=15, max_depth=4, subsample=0.8, colsample_bytree=0.7, min_child_samples=10),
    k=1, n_keep=45, w=0.5, cap=300, extra=85, keep_c=75)

def clf_oof(Xs, ybin, ser, n_keep, nseed=5):
    keep_idx = np.argsort(get_imp(Xs, ybin, clf=True))[-n_keep:]
    Xs = Xs[:, keep_idx]
    oof = np.zeros(len(ybin))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], ybin[tr], np.array(ser)[tr], np.array(ser)[te], 3)
        ps = []
        for sd in range(nseed):
            mx = XGBClassifier(random_state=42+sd, n_jobs=-1, **dict(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8))
            mx.fit(Xtr, ybin[tr]); ps.append(mx.predict_proba(Xte)[:,1])
            ml = LGBMClassifier(random_state=42+sd, n_jobs=-1, verbose=-1, **dict(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8))
            ml.fit(Xtr, ybin[tr]); ps.append(ml.predict_proba(Xte)[:,1])
        oof[te] = np.mean(ps, axis=0)
    return oof, keep_idx

def cv_reg(Xs, y_orig, ser, k, trans=None, inv=None, w=0.5, nseed=NSEED, extra_feat=None):
    yt = trans(y_orig) if trans is not None else y_orig
    xgb_cfg = dict(MEK_CFG['xgb']); lgb_cfg = dict(MEK_CFG['lgb'])
    r2s = []
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yt[tr], np.array(ser)[tr], np.array(ser)[te], k)
        if extra_feat is not None:
            Xtr = np.hstack([Xtr, extra_feat[tr].reshape(-1,1)])
            Xte = np.hstack([Xte, extra_feat[te].reshape(-1,1)])
        px, pl = [], []
        for sd in range(nseed):
            mx = XGBRegressor(random_state=42+sd, n_jobs=-1, **xgb_cfg); mx.fit(Xtr, yt[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(random_state=42+sd, n_jobs=-1, verbose=-1, **lgb_cfg); ml.fit(Xtr, yt[tr]); pl.append(ml.predict(Xte))
        pred = w*np.mean(px,axis=0) + (1-w)*np.mean(pl,axis=0)
        if inv is not None:
            pred = inv(pred)
        oof[te] = pred
        r2s.append(r2_score(y_orig[te], pred))
    return np.mean(r2s), oof

def honest_eval(y_true_unc, y_pred_unc, y_true_all, y_pred_all, cap=300):
    r2_unc = r2_score(y_true_unc, y_pred_unc) if len(y_true_unc) >= 5 else float('nan')
    ybin_true = (y_true_all >= cap).astype(int)
    ybin_pred = (y_pred_all >= cap).astype(int)
    acc = accuracy_score(ybin_true, ybin_pred)
    unc_mask = y_true_all < cap
    acc_unc = accuracy_score(ybin_true[unc_mask], ybin_pred[unc_mask]) if unc_mask.sum() > 0 else float('nan')
    cen_mask = (y_true_all == cap).astype(bool)
    rec_cen = accuracy_score(ybin_true[cen_mask], ybin_pred[cen_mask]) if cen_mask.sum() > 0 else float('nan')
    return r2_unc, acc, acc_unc, rec_cen

print('='*70)
print('实验 K-5: 诚实两阶段 MEK 模型优化')
print('='*70)
d = get_data('MEK擦拭')
Xt, yt, sert = d
cap = 300
ybin = (yt >= cap).astype(int)
cen_mask = (yt == cap).astype(bool)
unc_idx = np.where(~cen_mask)[0]
print(f'  样本={len(yt)}, 未截尾={int((~cen_mask).sum())}, 截尾={int(cen_mask.sum())}')

# 分类器 OOF
p_hi, keep_c = clf_oof(Xt, ybin, sert, MEK_CFG['keep_c'])
print(f'  边界分类器 AUC={roc_auc_score(ybin, p_hi):.4f}')

# 特征选择（未截尾样本）
imp_unc = get_imp(Xt[unc_idx], np.sqrt(yt[unc_idx]))
keep_unc = np.argsort(imp_unc)[-MEK_CFG['n_keep']:]
Xs_unc = Xt[:, keep_unc]  # 全样本用同一特征选择

print()
print('--- K-5a: 未截尾回归 + p_hi 特征 ---')
r2a, oofa = cv_reg(Xs_unc[unc_idx], yt[unc_idx], [sert[i] for i in unc_idx], MEK_CFG['k'],
                   trans=np.sqrt, inv=lambda p: p**2, extra_feat=p_hi[unc_idx])
r2a_unc = r2_score(yt[unc_idx], oofa)
print(f'  未截尾 R²={r2a:.4f} (对比无p_hi特征 0.474)')

print()
print('--- K-5b: 软混合两阶段（无硬阈值） ---')
# 回归 OOF（未截尾训练，全样本预测需重新CV：用未截尾训练，预测全样本）
# 简化：用未截尾回归在未截尾上的 OOF；全样本预测 = 未截尾回归值
# 软混合：final = reg*(1-p_hi) + (cap+extra*p_hi)*p_hi
# 但 reg 只对未截尾样本有 OOF。对全样本，用代理目标法回归 OOF 作为 reg。
y_proxy = yt.copy()
y_proxy[cen_mask] = cap + MEK_CFG['extra'] * p_hi[cen_mask]
imp_all = get_imp(Xt, np.sqrt(y_proxy))
keep_all = np.argsort(imp_all)[-MEK_CFG['n_keep']:]
Xs_all = Xt[:, keep_all]
r2_proxy, oof_proxy = cv_reg(Xs_all, y_proxy, sert, MEK_CFG['k'], trans=np.sqrt, inv=lambda p: p**2)
# 软混合
high_val = cap + MEK_CFG['extra'] * p_hi
pred_blend = oof_proxy * (1 - p_hi) + high_val * p_hi
r2b, accb, accub, recb = honest_eval(yt[unc_idx], pred_blend[unc_idx], yt, pred_blend, cap)
print(f'  软混合 → 未截尾 R²={r2b:.4f}, 边界 acc={accb:.4f} (未截尾 acc={accub:.4f}, 截尾召回={recb:.4f})')

print()
print('--- K-5c: 未截尾回归 + 边界分类器（双输出，诚实指标） ---')
# 回归：未截尾回归 R²（已算 r2a 或 0.474）
# 分类：边界分类器 acc（thr=0.5）
for thr in [0.4, 0.5, 0.6]:
    ybp = (p_hi >= thr).astype(int)
    acc_c = accuracy_score(ybin, ybp)
    rec_c = accuracy_score(ybin[cen_mask], ybp[cen_mask])
    prec_c = ybp[cen_mask].sum() / ybp.sum() if ybp.sum() > 0 else float('nan')
    print(f'  分类器 thr={thr}: acc={acc_c:.4f}, 截尾召回={rec_c:.4f}, 精度={prec_c:.4f}')

print()
print('--- K-5d: 未截尾回归稳定性（多种子） ---')
r2s = []
for sd_seed in range(5):
    np.random.seed(sd_seed)
    r2d, _ = cv_reg(Xs_unc[unc_idx], yt[unc_idx], [sert[i] for i in unc_idx], MEK_CFG['k'],
                    trans=np.sqrt, inv=lambda p: p**2, nseed=5)
    r2s.append(r2d)
print(f'  未截尾回归 R² 5次抽样: {[f"{r:.4f}" for r in r2s]}, 均值={np.mean(r2s):.4f}')

print()
print('实验 K-5 完成')
