# -*- coding: utf-8 -*-
"""
实验 L-2：AFT 预测分布分析与组合方案
================================================================
L-1 发现：AFT 边界判别优秀（acc=0.9434, 截尾召回=0.804）但未截尾回归 R² 为负。
本实验分析：1) AFT 预测分布（未截尾 vs 截尾）；2) 相关性（是否仅标定偏移）；
3) 校准后的 AFT 未截尾 R²；4) AFT边界 + 回归数值 的组合两阶段。
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, accuracy_score, roc_auc_score
from scipy.stats import pearsonr
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

def cv_aft(Xs, y_orig, ser, k, n_keep, nseed=5, dist='normal', scale=1.0,
           extra_feat=None, n_est=1500, lr=0.008, max_depth=4, ser_stat='lower'):
    """AFT 5折CV。ser_stat: 'lower'用下界做系列编码, 'obs'用观测值(截尾=300)"""
    cap = 300
    cen_mask = y_orig >= cap
    yl = y_orig.copy(); yu = y_orig.copy()
    yu[cen_mask] = np.inf
    ser_base = yl if ser_stat == 'lower' else y_orig
    imp = get_imp(Xs, np.sqrt(np.minimum(y_orig, cap)))
    keep = np.argsort(imp)[-n_keep:]
    Xs = Xs[:, keep]
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], ser_base[tr], np.array(ser)[tr], np.array(ser)[te], k)
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

def honest_eval(y_true_unc, y_pred_unc, y_true_all, y_pred_all, cap=300):
    r2_unc = r2_score(y_true_unc, y_pred_unc) if len(y_true_unc) >= 5 else float('nan')
    ybin_true = (y_true_all >= cap).astype(int)
    ybin_pred = (y_pred_all >= cap).astype(int)
    acc = accuracy_score(ybin_true, ybin_pred)
    unc_mask = y_true_all < cap
    acc_unc = accuracy_score(ybin_true[unc_mask], ybin_pred[unc_mask]) if unc_mask.sum() > 0 else float('nan')
    cen_mask = y_true_all >= cap
    rec_cen = accuracy_score(ybin_true[cen_mask], ybin_pred[cen_mask]) if cen_mask.sum() > 0 else float('nan')
    return r2_unc, acc, acc_unc, rec_cen

print('='*70)
print('实验 L-2: AFT 预测分布分析与组合方案')
print('='*70)
d = get_data('MEK擦拭')
Xt, yt, sert = d
cap = 300
ybin = (yt >= cap).astype(int)
cen_mask = yt >= cap
unc_idx = np.where(~cen_mask)[0]
print(f'  样本={len(yt)}, 未截尾={int((~cen_mask).sum())}, 截尾={int(cen_mask.sum())}')

# AFT OOF（normal/scale=1.0）
oof_aft, keep_aft = cv_aft(Xt, yt, sert, MEK_CFG['k'], MEK_CFG['n_keep'], nseed=5)
print()
print('--- AFT 预测分布 ---')
print(f'  未截尾样本: 真实 mean={yt[unc_idx].mean():.1f}, AFT预测 mean={oof_aft[unc_idx].mean():.1f}, std={oof_aft[unc_idx].std():.1f}')
print(f'  截尾样本:   真实(下界) mean={yt[cen_mask].mean():.1f}, AFT预测 mean={oof_aft[cen_mask].mean():.1f}')
r_corr, _ = pearsonr(yt[unc_idx], oof_aft[unc_idx])
print(f'  未截尾 真实-预测 相关系数 r={r_corr:.4f} (R²若仅标定偏移则 r²≈R²)')

# 校准：对未截尾样本做线性标定 y_pred_cal = a*pred + b
a, b = np.polyfit(oof_aft[unc_idx], yt[unc_idx], 1)
print(f'  线性标定: y = {a:.4f}*pred + {b:.2f}')
pred_cal = a * oof_aft + b
r2_cal, acc_cal, accu_cal, recc_cal = honest_eval(yt[unc_idx], pred_cal[unc_idx], yt, pred_cal, cap)
print(f'  标定后: 未截尾 R²={r2_cal:.4f}, 边界 acc={acc_cal:.4f} (未截尾 acc={accu_cal:.4f}, 截尾召回={recc_cal:.4f})')

# 组合方案：AFT 边界 + 未截尾回归数值
print()
print('--- 组合方案: AFT边界 + 未截尾回归数值 ---')
imp_unc = get_imp(Xt[unc_idx], np.sqrt(yt[unc_idx]))
keep_unc = np.argsort(imp_unc)[-MEK_CFG['n_keep']:]
Xs_unc = Xt[:, keep_unc]
oof_reg = cv_reg(Xs_unc[unc_idx], yt[unc_idx], [sert[i] for i in unc_idx], MEK_CFG['k'],
                 trans=np.sqrt, inv=lambda p: p**2, nseed=5)
r2_reg = r2_score(yt[unc_idx], oof_reg)
print(f'  未截尾回归基线: 未截尾 R²={r2_reg:.4f}')

# 组合1: AFT预测>=300 → 判为截尾(输出300+校准高值)，否则用回归值
# 对全样本：AFT OOF 有全样本，回归 OOF 只有未截尾。用 AFT 边界决策。
# 对未截尾样本：若 AFT 判为 <300，用回归值；若判为 >=300，用 AFT 值（或300）
pred_comb = oof_aft.copy()
pred_comb[unc_idx] = np.where(oof_aft[unc_idx] < cap, oof_reg, oof_aft[unc_idx])
r2_comb, acc_comb, accu_comb, recc_comb = honest_eval(yt[unc_idx], pred_comb[unc_idx], yt, pred_comb, cap)
print(f'  组合(AFT边界+回归值): 未截尾 R²={r2_comb:.4f}, 边界 acc={acc_comb:.4f} (未截尾 acc={accu_comb:.4f}, 截尾召回={recc_comb:.4f})')

# 组合2: 阈值可调，找最优边界阈值
print()
print('--- 组合阈值扫描（AFT 边界阈值） ---')
best = None
for thr in np.arange(200, 351, 10):
    pred_t = oof_aft.copy()
    pred_t[unc_idx] = np.where(oof_aft[unc_idx] < thr, oof_reg, oof_aft[unc_idx])
    r2_t, acc_t, accu_t, recc_t = honest_eval(yt[unc_idx], pred_t[unc_idx], yt, pred_t, cap)
    if best is None or r2_t > best[0]:
        best = (r2_t, thr, acc_t, accu_t, recc_t)
    print(f'  thr={thr}: 未截尾 R²={r2_t:.4f}, 边界 acc={acc_t:.4f}, 截尾召回={recc_t:.4f}')
print(f'  最优 thr={best[1]}: 未截尾 R²={best[0]:.4f}, 边界 acc={best[2]:.4f}, 截尾召回={best[4]:.4f}')

print()
print('实验 L-2 完成')
