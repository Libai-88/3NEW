# -*- coding: utf-8 -*-
"""
实验 L：XGBoost survival:aft 处理 MEK 右截尾（文献调研驱动的突破路径）
================================================================
文献调研（XGBoost 官方 AFT 教程）指出：右截尾目标可用官方 survival:aft 目标，
通过 label_lower_bound / label_upper_bound 表达（截尾样本 [300, +∞)），
比自定义 Tobit 更正规、梯度稳定。

本实验验证 AFT 相对当前两阶段基线（未截尾回归+p_hi：未截尾 R²=0.495、边界 acc=0.915）
是否有真实提升：
  L-1: AFT 全样本（未截尾 [y,y] + 截尾 [300,inf)），系列编码
  L-2: AFT + 分类器 p_hi 特征
  L-3: AFT 不同分布/尺度（normal/logistic/extreme）
  L-4: AFT 与两阶段基线诚实对比（未截尾 R² + 边界 acc）
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, accuracy_score, roc_auc_score
from xgboost import XGBRegressor, XGBClassifier
import xgboost as xgb
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

def cv_aft(Xs, y_orig, ser, k, n_keep, nseed=5, dist='normal', scale=1.0,
           extra_feat=None, n_est=1500, lr=0.008, max_depth=4):
    """AFT 5折CV：未截尾 [y,y]，截尾 [300,inf)"""
    cap = 300
    cen_mask = (y_orig == cap).astype(bool)
    yl = y_orig.copy(); yu = y_orig.copy()
    yu[cen_mask] = np.inf
    # 特征选择：用截断目标（min(y,cap)）的重要性
    imp = get_imp(Xs, np.sqrt(np.minimum(y_orig, cap)))
    keep = np.argsort(imp)[-n_keep:]
    Xs = Xs[:, keep]
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yl[tr], np.array(ser)[tr], np.array(ser)[te], k)
        if extra_feat is not None:
            Xtr = np.hstack([Xtr, extra_feat[tr].reshape(-1,1)])
            Xte = np.hstack([Xte, extra_feat[te].reshape(-1,1)])
        ps = []
        for sd in range(nseed):
            dtr = xgb.DMatrix(Xtr)
            dtr.set_float_info('label_lower_bound', yl[tr])
            dtr.set_float_info('label_upper_bound', yu[tr])
            params = dict(
                objective='survival:aft', eval_metric='aft-nloglik',
                aft_loss_distribution=dist, aft_loss_distribution_scale=scale,
                tree_method='hist', learning_rate=lr, max_depth=max_depth,
                subsample=0.8, colsample_bytree=0.7, min_child_weight=2,
                random_state=42+sd, nthread=-1)
            bst = xgb.train(params, dtr, num_boost_round=n_est)
            ps.append(bst.predict(xgb.DMatrix(Xte)))
        oof[te] = np.mean(ps, axis=0)
    return oof, keep

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
print('实验 L: XGBoost survival:aft 处理 MEK 右截尾')
print('='*70)
d = get_data('MEK擦拭')
Xt, yt, sert = d
cap = 300
ybin = (yt >= cap).astype(int)
cen_mask = (yt == cap).astype(bool)
unc_idx = np.where(~cen_mask)[0]
print(f'  样本={len(yt)}, 未截尾={int((~cen_mask).sum())}, 截尾={int(cen_mask.sum())}')

# 分类器 OOF（用于 p_hi 特征）
p_hi, keep_c = clf_oof(Xt, ybin, sert, MEK_CFG['keep_c'])
print(f'  边界分类器 AUC={roc_auc_score(ybin, p_hi):.4f}')

# 基线：未截尾回归 + p_hi（K-5a，两阶段当前方案）
imp_unc = get_imp(Xt[unc_idx], np.sqrt(yt[unc_idx]))
keep_unc = np.argsort(imp_unc)[-MEK_CFG['n_keep']:]
Xs_unc = Xt[:, keep_unc]

def cv_reg(Xs, y_orig, ser, k, trans=None, inv=None, w=0.5, nseed=5, extra_feat=None):
    yt_ = trans(y_orig) if trans is not None else y_orig
    xgb_cfg = dict(MEK_CFG['xgb']); lgb_cfg = dict(MEK_CFG['lgb'])
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yt_[tr], np.array(ser)[tr], np.array(ser)[te], k)
        if extra_feat is not None:
            Xtr = np.hstack([Xtr, extra_feat[tr].reshape(-1,1)])
            Xte = np.hstack([Xte, extra_feat[te].reshape(-1,1)])
        px, pl = [], []
        for sd in range(nseed):
            mx = XGBRegressor(random_state=42+sd, n_jobs=-1, **xgb_cfg); mx.fit(Xtr, yt_[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(random_state=42+sd, n_jobs=-1, verbose=-1, **lgb_cfg); ml.fit(Xtr, yt_[tr]); pl.append(ml.predict(Xte))
        pred = w*np.mean(px,axis=0) + (1-w)*np.mean(pl,axis=0)
        if inv is not None:
            pred = inv(pred)
        oof[te] = pred
    return oof

print()
print('--- L-0 基线: 未截尾回归 + p_hi（两阶段当前方案） ---')
oof_base = cv_reg(Xs_unc[unc_idx], yt[unc_idx], [sert[i] for i in unc_idx], MEK_CFG['k'],
                  trans=np.sqrt, inv=lambda p: p**2, extra_feat=p_hi[unc_idx])
r2_base = r2_score(yt[unc_idx], oof_base)
print(f'  未截尾 R²={r2_base:.4f}')

print()
print('--- L-1: AFT 全样本（未截尾[y,y] + 截尾[300,inf)），normal/scale=1.0 ---')
oof_aft, keep_aft = cv_aft(Xt, yt, sert, MEK_CFG['k'], MEK_CFG['n_keep'], nseed=5)
r2_aft, acc_aft, accu_aft, recc_aft = honest_eval(yt[unc_idx], oof_aft[unc_idx], yt, oof_aft, cap)
print(f'  未截尾 R²={r2_aft:.4f}, 边界 acc={acc_aft:.4f} (未截尾 acc={accu_aft:.4f}, 截尾召回={recc_aft:.4f})')

print()
print('--- L-2: AFT + p_hi 特征 ---')
oof_aft2, _ = cv_aft(Xt, yt, sert, MEK_CFG['k'], MEK_CFG['n_keep'], nseed=5, extra_feat=p_hi)
r2_aft2, acc_aft2, accu_aft2, recc_aft2 = honest_eval(yt[unc_idx], oof_aft2[unc_idx], yt, oof_aft2, cap)
print(f'  未截尾 R²={r2_aft2:.4f}, 边界 acc={acc_aft2:.4f} (未截尾 acc={accu_aft2:.4f}, 截尾召回={recc_aft2:.4f})')

print()
print('--- L-3: AFT 分布/尺度敏感性 ---')
for dist, scale in [('normal', 0.5), ('normal', 2.0), ('logistic', 1.0), ('extreme', 1.0)]:
    try:
        oof_d, _ = cv_aft(Xt, yt, sert, MEK_CFG['k'], MEK_CFG['n_keep'], nseed=3, dist=dist, scale=scale)
        r2_d, acc_d, _, _ = honest_eval(yt[unc_idx], oof_d[unc_idx], yt, oof_d, cap)
        print(f'  {dist}/scale={scale}: 未截尾 R²={r2_d:.4f}, 边界 acc={acc_d:.4f}')
    except Exception as e:
        print(f'  {dist}/scale={scale}: 失败 {type(e).__name__}: {str(e)[:80]}')

print()
print('--- L-4: 对比汇总 ---')
print(f'  基线(未截尾回归+p_hi): 未截尾 R²={r2_base:.4f}')
print(f'  AFT(全样本):          未截尾 R²={r2_aft:.4f}, 边界 acc={acc_aft:.4f}')
print(f'  AFT+p_hi:             未截尾 R²={r2_aft2:.4f}, 边界 acc={acc_aft2:.4f}')
print()
print('实验 L 完成')
