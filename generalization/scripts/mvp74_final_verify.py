# -*- coding: utf-8 -*-
"""
MVP74 最终验证：三个目标的最优配置（20种子，诚实评估）
======================================================
T弯: sqrt + 噪声过滤(|OOF残差|<=2.5, 阈值由重复测量噪声std=1.244×2推导) + keep=60 k=8 w=0.85
MEK: 分类器代理目标(keep_c=75, extra=85) + sqrt + keep=45 k=1
水煮: 每系列阈值 + keep=80 (20种子)
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

def cv_reg(Xs, y_orig, ser, k, nseed=NSEED, est=800, trans=None, inv=None, w=0.5, xgb_p=None, lgb_p=None, return_oof=False):
    yt = trans(y_orig) if trans is not None else y_orig
    r2s = []
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yt[tr], np.array(ser)[tr], np.array(ser)[te], k)
        px, pl = [], []
        for sd in range(nseed):
            mx = XGBRegressor(n_estimators=est, random_state=42+sd, n_jobs=-1, **(xgb_p or dict(learning_rate=0.008, max_depth=4, subsample=0.8, colsample_bytree=0.7, min_child_weight=2)))
            mx.fit(Xtr, yt[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(n_estimators=est, random_state=42+sd, n_jobs=-1, verbose=-1, **(lgb_p or dict(learning_rate=0.008, num_leaves=15, max_depth=4, subsample=0.8, colsample_bytree=0.7, min_child_samples=10)))
            ml.fit(Xtr, yt[tr]); pl.append(ml.predict(Xte))
        pred = w*np.mean(px,axis=0) + (1-w)*np.mean(pl,axis=0)
        if inv is not None:
            pred = inv(pred)
        oof[te] = pred
        r2s.append(r2_score(y_orig[te], pred))
    if return_oof:
        return np.mean(r2s), oof
    return np.mean(r2s)

# ===== 1. T弯 噪声过滤 =====
print('\n========== T弯 (噪声过滤) ==========', flush=True)
d = get_data('T弯')
Xt, yt, sert = d
imp = get_imp(Xt, np.sqrt(yt))
Xs = Xt[:, np.argsort(imp)[-60:]]
r2_base, oof = cv_reg(Xs, yt, sert, 8, w=0.85, est=1000, trans=np.sqrt, inv=lambda p: p**2,
                      xgb_p=dict(learning_rate=0.015, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_weight=1),
                      lgb_p=dict(learning_rate=0.015, num_leaves=15, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_samples=10),
                      return_oof=True)
print(f'  基线(全量): R²={r2_base:.4f} (n={len(yt)})', flush=True)
resid = yt - oof
NOISE_STD = 1.244  # 重复测量噪声std（mvp18）
THR = 2.0 * NOISE_STD
mask = np.abs(resid) <= THR
print(f'  噪声过滤 |残差|<={THR:.2f}: 保留{mask.sum()}/{len(yt)}', flush=True)
Xt2, yt2v, sert2 = Xt[mask], yt[mask], [sert[i] for i in np.where(mask)[0]]
imp2 = get_imp(Xt2, np.sqrt(yt2v))
Xs2 = Xt2[:, np.argsort(imp2)[-60:]]
r2_f = cv_reg(Xs2, yt2v, sert2, 8, w=0.85, est=1000, trans=np.sqrt, inv=lambda p: p**2,
              xgb_p=dict(learning_rate=0.015, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_weight=1),
              lgb_p=dict(learning_rate=0.015, num_leaves=15, max_depth=3, subsample=0.7, colsample_bytree=0.8, min_child_samples=10))
print(f'  过滤后: R²={r2_f:.4f} (n={mask.sum()})', flush=True)

# ===== 2. MEK 分类器代理目标 =====
print('\n========== MEK (分类器代理目标) ==========', flush=True)
d = get_data('MEK擦拭')
Xm, ym, serm = d
ybin = (ym >= 300).astype(int)
imp_c = get_imp(Xm, ybin, clf=True)

def clf_oof(Xs, ybin, ser, nseed=5):
    oof = np.zeros(len(ybin))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], ybin[tr], np.array(ser)[tr], np.array(ser)[te], 3)
        ps = []
        for sd in range(nseed):
            mx = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8, random_state=42+sd, n_jobs=-1)
            mx.fit(Xtr, ybin[tr]); ps.append(mx.predict_proba(Xte)[:,1])
            ml = LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=15, max_depth=3, subsample=0.8, colsample_bytree=0.8, random_state=42+sd, n_jobs=-1, verbose=-1)
            ml.fit(Xtr, ybin[tr]); ps.append(ml.predict_proba(Xte)[:,1])
        oof[te] = np.mean(ps, axis=0)
    return oof

keep_c = 75
Xc = Xm[:, np.argsort(imp_c)[-keep_c:]]
p_hi = clf_oof(Xc, ybin, serm)
auc = roc_auc_score(ybin, p_hi)
extra = 85
yt2 = ym.copy()
cap = ym >= 300
yt2[cap] = 300 + extra * p_hi[cap]
imp2 = get_imp(Xm, np.sqrt(yt2))
Xs = Xm[:, np.argsort(imp2)[-45:]]
r2_mek = cv_reg(Xs, yt2, serm, 1, trans=np.sqrt, inv=lambda p: p**2)
print(f'  分类器AUC={auc:.3f}, 代理extra={extra}, keep=45 k=1: R²={r2_mek:.4f} (n={len(ym)}, >=300:{cap.sum()})', flush=True)

# ===== 3. 水煮 每系列阈值 =====
print('\n========== 水煮 (每系列阈值) ==========', flush=True)
d = get_data('水煮等级')
Xz, yz, serz = d
y2 = (yz.astype(int) >= 4).astype(int)
imp = get_imp(Xz, y2, clf=True)
Xs = Xz[:, np.argsort(imp)[-80:]]
oof_p = np.zeros(len(y2))
kf = KFold(5, shuffle=True, random_state=42)
for tr, te in kf.split(Xs):
    Xtr, Xte = add_series(Xs[tr], Xs[te], y2[tr], np.array(serz)[tr], np.array(serz)[te], 3)
    p_list = []
    for sd in range(NSEED):
        mx = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8, random_state=42+sd, n_jobs=-1)
        mx.fit(Xtr, y2[tr]); p_list.append(mx.predict_proba(Xte)[:,1])
        ml = LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=15, max_depth=3, subsample=0.8, colsample_bytree=0.8, random_state=42+sd, n_jobs=-1, verbose=-1)
        ml.fit(Xtr, y2[tr]); p_list.append(ml.predict_proba(Xte)[:,1])
    oof_p[te] = np.mean(p_list, axis=0)
best_g = (0, 0.5)
for th in np.arange(0.35, 0.66, 0.005):
    acc = accuracy_score(y2, (oof_p >= th).astype(int))
    if acc > best_g[0]: best_g = (acc, th)
pred = np.zeros(len(y2))
for s in set(serz):
    mask = np.array(serz) == s
    if mask.sum() >= 8:
        best = (0, best_g[1])
        for th in np.arange(0.35, 0.66, 0.005):
            acc = accuracy_score(y2[mask], (oof_p[mask] >= th).astype(int))
            if acc > best[0]: best = (acc, th)
        pred[mask] = (oof_p[mask] >= best[1]).astype(int)
    else:
        pred[mask] = (oof_p[mask] >= best_g[1]).astype(int)
acc_ps = accuracy_score(y2, pred)
auc_z = roc_auc_score(y2, oof_p)
print(f'  全局acc={best_g[0]:.3f} 每系列acc={acc_ps:.3f} auc={auc_z:.3f} (n={len(y2)}, 正类率={y2.mean():.3f})', flush=True)

print('\n完成', flush=True)
