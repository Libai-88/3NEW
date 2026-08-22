# -*- coding: utf-8 -*-
"""
实验 L-3：解耦两阶段（边界判别 + 数值回归互不污染）+ AFT 边界稳定性验证
================================================================
L-2 发现：AFT 回归差（R²=0.24）但边界判别好（acc=0.9434, 截尾召回=0.804）。
本实验验证解耦结构下 AFT 边界的稳定性，并与当前分类器公平对比（多种子）：
  L-3a: 当前分类器边界（nseed=10）acc/召回
  L-3b: AFT 边界（nseed=10）acc/召回
  L-3c: 解耦两阶段诚实指标（边界 acc + 未截尾 R² 互不污染）
  L-3d: AFT 预测作为分类器额外特征
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

def clf_oof(Xs, ybin, ser, n_keep, nseed=10, extra_feat=None):
    keep_idx = np.argsort(get_imp(Xs, ybin, clf=True))[-n_keep:]
    Xs = Xs[:, keep_idx]
    oof = np.zeros(len(ybin))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], ybin[tr], np.array(ser)[tr], np.array(ser)[te], 3)
        if extra_feat is not None:
            Xtr = np.hstack([Xtr, extra_feat[tr].reshape(-1,1)])
            Xte = np.hstack([Xte, extra_feat[te].reshape(-1,1)])
        ps = []
        for sd in range(nseed):
            mx = XGBClassifier(random_state=42+sd, n_jobs=-1, **dict(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8))
            mx.fit(Xtr, ybin[tr]); ps.append(mx.predict_proba(Xte)[:,1])
            ml = LGBMClassifier(random_state=42+sd, n_jobs=-1, verbose=-1, **dict(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8))
            ml.fit(Xtr, ybin[tr]); ps.append(ml.predict_proba(Xte)[:,1])
        oof[te] = np.mean(ps, axis=0)
    return oof, keep_idx

def cv_aft(Xs, y_orig, ser, k, n_keep, nseed=10, dist='normal', scale=1.0):
    cap = 300
    cen_mask = y_orig >= cap
    yl = y_orig.copy(); yu = y_orig.copy()
    yu[cen_mask] = np.inf
    imp = get_imp(Xs, np.sqrt(np.minimum(y_orig, cap)))
    keep = np.argsort(imp)[-n_keep:]
    Xs = Xs[:, keep]
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yl[tr], np.array(ser)[tr], np.array(ser)[te], k)
        ps = []
        for sd in range(nseed):
            dtr = xgb.DMatrix(Xtr)
            dtr.set_float_info('label_lower_bound', yl[tr])
            dtr.set_float_info('label_upper_bound', yu[tr])
            params = dict(
                objective='survival:aft', eval_metric='aft-nloglik',
                aft_loss_distribution=dist, aft_loss_distribution_scale=scale,
                tree_method='hist', learning_rate=0.008, max_depth=4,
                subsample=0.8, colsample_bytree=0.7, min_child_weight=2,
                random_state=42+sd, nthread=-1)
            bst = xgb.train(params, dtr, num_boost_round=1500)
            ps.append(bst.predict(xgb.DMatrix(Xte)))
        oof[te] = np.mean(ps, axis=0)
    return oof, keep

def cv_reg(Xs, y_orig, ser, k, trans=None, inv=None, w=0.5, nseed=10, extra_feat=None):
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

def boundary_stats(score, ybin, cap=300):
    """给定连续分数，扫描阈值，返回 (最优acc, 对应截尾召回, 未截尾acc, AUC)"""
    auc = roc_auc_score(ybin, score)
    cen = ybin == 1
    unc = ybin == 0
    best = None
    for thr in np.percentile(score, np.arange(0, 101, 2)):
        yp = (score >= thr).astype(int)
        acc = accuracy_score(ybin, yp)
        rec = accuracy_score(ybin[cen], yp[cen]) if cen.sum() else 0
        accu = accuracy_score(ybin[unc], yp[unc]) if unc.sum() else 0
        if best is None or acc > best[0]:
            best = (acc, rec, accu, thr)
    return best, auc

print('='*70)
print('实验 L-3: 解耦两阶段 + AFT 边界稳定性')
print('='*70)
d = get_data('MEK擦拭')
Xt, yt, sert = d
cap = 300
ybin = (yt >= cap).astype(int)
cen_mask = yt >= cap
unc_idx = np.where(~cen_mask)[0]
print(f'  样本={len(yt)}, 未截尾={int((~cen_mask).sum())}, 截尾={int(cen_mask.sum())}')

# 回归（未截尾 + p_hi，nseed=10）
imp_unc = get_imp(Xt[unc_idx], np.sqrt(yt[unc_idx]))
keep_unc = np.argsort(imp_unc)[-MEK_CFG['n_keep']:]
Xs_unc = Xt[:, keep_unc]
p_hi_clf, keep_c = clf_oof(Xt, ybin, sert, MEK_CFG['keep_c'], nseed=10)
oof_reg = cv_reg(Xs_unc[unc_idx], yt[unc_idx], [sert[i] for i in unc_idx], MEK_CFG['k'],
                 trans=np.sqrt, inv=lambda p: p**2, nseed=10, extra_feat=p_hi_clf[unc_idx])
r2_reg = r2_score(yt[unc_idx], oof_reg)
print(f'  未截尾回归+p_hi: 未截尾 R²={r2_reg:.4f}')

# L-3a: 当前分类器边界
print()
print('--- L-3a: 当前分类器边界（nseed=10） ---')
best_c, auc_c = boundary_stats(p_hi_clf, ybin)
print(f'  最优 acc={best_c[0]:.4f} (截尾召回={best_c[1]:.4f}, 未截尾acc={best_c[2]:.4f}, thr={best_c[3]:.2f}), AUC={auc_c:.4f}')
# thr=0.5 口径（与报告一致）
yp05 = (p_hi_clf >= 0.5).astype(int)
acc05 = accuracy_score(ybin, yp05)
rec05 = accuracy_score(ybin[cen_mask], yp05[cen_mask])
print(f'  thr=0.5: acc={acc05:.4f}, 截尾召回={rec05:.4f}')

# L-3b: AFT 边界
print()
print('--- L-3b: AFT 边界（nseed=10） ---')
oof_aft, keep_aft = cv_aft(Xt, yt, sert, MEK_CFG['k'], MEK_CFG['n_keep'], nseed=10)
best_a, auc_a = boundary_stats(oof_aft, ybin)
print(f'  最优 acc={best_a[0]:.4f} (截尾召回={best_a[1]:.4f}, 未截尾acc={best_a[2]:.4f}, thr={best_a[3]:.2f}), AUC={auc_a:.4f}')
ypa = (oof_aft >= 300).astype(int)
acca = accuracy_score(ybin, ypa)
reca = accuracy_score(ybin[cen_mask], ypa[cen_mask])
print(f'  thr=300: acc={acca:.4f}, 截尾召回={reca:.4f}')

# L-3c: 解耦两阶段（边界 acc + 未截尾 R² 互不污染）
print()
print('--- L-3c: 解耦两阶段诚实指标 ---')
print(f'  方案A(当前分类器): 边界 acc={acc05:.4f} (thr=0.5), 未截尾 R²={r2_reg:.4f}')
print(f'  方案B(AFT边界):    边界 acc={acca:.4f} (thr=300), 未截尾 R²={r2_reg:.4f}')

# L-3d: AFT 预测作为分类器额外特征
print()
print('--- L-3d: AFT 预测作为分类器额外特征 ---')
p_hi_clf2, _ = clf_oof(Xt, ybin, sert, MEK_CFG['keep_c'], nseed=10, extra_feat=oof_aft)
best_c2, auc_c2 = boundary_stats(p_hi_clf2, ybin)
print(f'  最优 acc={best_c2[0]:.4f} (截尾召回={best_c2[1]:.4f}, 未截尾acc={best_c2[2]:.4f}), AUC={auc_c2:.4f}')
yp2 = (p_hi_clf2 >= 0.5).astype(int)
acc2 = accuracy_score(ybin, yp2)
rec2 = accuracy_score(ybin[cen_mask], yp2[cen_mask])
print(f'  thr=0.5: acc={acc2:.4f}, 截尾召回={rec2:.4f}')

print()
print('实验 L-3 完成')
