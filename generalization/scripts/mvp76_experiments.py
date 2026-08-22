# -*- coding: utf-8 -*-
"""
实验 K：MEK 截尾处理改进（诚实评估 + 两阶段模型 + Tobit 式目标）
================================================================
背景：实验 J 显示 MEK 噪声地板 R²=0.966，当前 0.701 的差距主要来自截尾
（43 个样本 MEK 恰为 300，真实值 ≥300 未知）。当前工作台用「分类器代理目标」
（截尾样本赋 300+extra×P(≥300)）并在代理目标上评估 R²，可能虚高。

本实验目标：
  K-1 诚实评估拆分：未截尾样本(<300) 的真实 R² + 边界分类准确率(≥300 vs <300)
  K-2 两阶段模型：分类器(≥300) + 未截尾回归，与当前代理目标对比
  K-3 训练变体对比：代理目标 / 丢弃截尾 / Tobit 式目标（截尾样本只罚预测<300）
  K-4 边界特征重要性：什么特征驱动 ≥300，能否提升边界准确率
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
MEK_CFG = dict(
    xgb=dict(n_estimators=1500, learning_rate=0.008, max_depth=4, subsample=0.8, colsample_bytree=0.7, min_child_weight=2),
    lgb=dict(n_estimators=1500, learning_rate=0.008, num_leaves=15, max_depth=4, subsample=0.8, colsample_bytree=0.7, min_child_samples=10),
    k=1, n_keep=45, w=0.5, cap=300, extra=85, keep_c=75)

def clf_oof(Xs, ybin, ser, n_keep, nseed=5):
    keep_idx = get_imp(Xs, ybin, clf=True)
    keep_idx = np.argsort(keep_idx)[-n_keep:]
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

def cv_reg(Xs, y_orig, ser, k, est=1500, trans=None, inv=None, w=0.5, xgb_p=None, lgb_p=None, return_oof=False):
    yt = trans(y_orig) if trans is not None else y_orig
    xgb_cfg = dict(xgb_p or MEK_CFG['xgb'])
    lgb_cfg = dict(lgb_p or MEK_CFG['lgb'])
    xgb_cfg.setdefault('n_estimators', est)
    lgb_cfg.setdefault('n_estimators', est)
    r2s = []
    oof = np.zeros(len(y_orig))
    kf = KFold(5, shuffle=True, random_state=42)
    for tr, te in kf.split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yt[tr], np.array(ser)[tr], np.array(ser)[te], k)
        px, pl = [], []
        for sd in range(NSEED):
            mx = XGBRegressor(random_state=42+sd, n_jobs=-1, **xgb_cfg)
            mx.fit(Xtr, yt[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(random_state=42+sd, n_jobs=-1, verbose=-1, **lgb_cfg)
            ml.fit(Xtr, yt[tr]); pl.append(ml.predict(Xte))
        pred = w*np.mean(px,axis=0) + (1-w)*np.mean(pl,axis=0)
        if inv is not None:
            pred = inv(pred)
        oof[te] = pred
        r2s.append(r2_score(y_orig[te], pred))
    if return_oof:
        return np.mean(r2s), oof
    return np.mean(r2s)

def honest_eval(y_true_unc, y_pred_unc, y_true_all, y_pred_all, cap=300):
    """诚实评估：未截尾 R² + 边界分类准确率/召回"""
    # 未截尾 R²
    r2_unc = r2_score(y_true_unc, y_pred_unc) if len(y_true_unc) >= 5 else float('nan')
    # 边界：预测 ≥300 视为"通过"
    ybin_true = (y_true_all >= cap).astype(int)
    ybin_pred = (y_pred_all >= cap).astype(int)
    acc = accuracy_score(ybin_true, ybin_pred)
    # 未截尾样本的边界准确率（真实 <300 的样本是否被正确判为 <300）
    unc_mask = y_true_all < cap
    acc_unc = accuracy_score(ybin_true[unc_mask], ybin_pred[unc_mask]) if unc_mask.sum() > 0 else float('nan')
    # 截尾样本召回（真实 ≥300 是否被判为 ≥300）
    cen_mask = y_true_all >= cap
    rec_cen = accuracy_score(ybin_true[cen_mask], ybin_pred[cen_mask]) if cen_mask.sum() > 0 else float('nan')
    return r2_unc, acc, acc_unc, rec_cen

print('='*70)
print('实验 K-1: 诚实评估拆分（当前代理目标方法）')
print('='*70)
d = get_data('MEK擦拭')
Xt, yt, sert = d
cap = 300
ybin = (yt >= cap).astype(int)
print(f'  样本数={len(yt)}, 未截尾(<{cap})={int((yt<cap).sum())}, 截尾(>={cap})={int((yt>=cap).sum())}')
# 当前方法：代理目标
p_hi, keep_c = clf_oof(Xt, ybin, sert, MEK_CFG['keep_c'])
auc_clf = roc_auc_score(ybin, p_hi)
print(f'  边界分类器 AUC={auc_clf:.4f}')
y_proxy = yt.copy()
cen_mask = yt >= cap
y_proxy[cen_mask] = cap + MEK_CFG['extra'] * p_hi[cen_mask]
# 特征选择 + 回归
sel_y = np.sqrt(y_proxy)
imp = get_imp(Xt, sel_y)
keep_idx = np.argsort(imp)[-MEK_CFG['n_keep']:]
Xs = Xt[:, keep_idx]
r2_proxy, oof_proxy = cv_reg(Xs, y_proxy, sert, MEK_CFG['k'], w=MEK_CFG['w'],
                             trans=np.sqrt, inv=lambda p: p**2, return_oof=True)
print(f'  代理目标 R²(全样本, 含截尾代理值)={r2_proxy:.4f}')
# 诚实评估：未截尾 R² + 边界准确率
r2_unc, acc, acc_unc, rec_cen = honest_eval(yt[~cen_mask], oof_proxy[~cen_mask], yt, oof_proxy, cap)
print(f'  诚实评估 → 未截尾 R²={r2_unc:.4f} (n={int((~cen_mask).sum())})')
print(f'  边界准确率 acc={acc:.4f} (未截尾 acc={acc_unc:.4f}, 截尾召回={rec_cen:.4f})')

print()
print('='*70)
print('实验 K-2: 两阶段模型（分类器 + 未截尾回归，诚实评估）')
print('='*70)
# 阶段1：分类器（已有 p_hi）——先报告分类器本身的边界指标
for thr in [0.3, 0.5, 0.7]:
    ybin_pred = (p_hi >= thr).astype(int)
    acc_c = accuracy_score(ybin, ybin_pred)
    rec_c = accuracy_score(ybin[cen_mask], ybin_pred[cen_mask]) if cen_mask.sum() else float('nan')
    prec_c = (ybin_pred[cen_mask].sum() / ybin_pred.sum()) if ybin_pred.sum() > 0 else float('nan')
    print(f'  分类器阈值={thr}: acc={acc_c:.4f}, 截尾召回={rec_c:.4f}, 精度={prec_c:.4f}')
# 阶段2：仅在未截尾样本上回归
unc_idx = np.where(~cen_mask)[0]
Xt_unc, yt_unc, sert_unc = Xt[unc_idx], yt[unc_idx], [sert[i] for i in unc_idx]
imp_unc = get_imp(Xt_unc, np.sqrt(yt_unc))
keep_unc = np.argsort(imp_unc)[-MEK_CFG['n_keep']:]
Xs_unc = Xt_unc[:, keep_unc]
r2_unc_reg, oof_unc = cv_reg(Xs_unc, yt_unc, sert_unc, MEK_CFG['k'], w=MEK_CFG['w'],
                              trans=np.sqrt, inv=lambda p: p**2, return_oof=True)
print(f'  未截尾回归 R²(仅未截尾训练+评估)={r2_unc_reg:.4f} (n={len(yt_unc)})')
# 诚实两阶段：对全样本，分类器判定是否 ≥300；未截尾样本用回归值，截尾判定样本用校准高值
# 未截尾样本的回归 OOF 已知；截尾样本的回归值用"未截尾回归模型"在截尾样本上的预测（需重新CV）
# 简化：全样本回归 OOF（代理目标法已给 oof_proxy），两阶段 = 分类器阈值 + 回归值
# 对全样本：p_hi >= thr → 预测 = cap + extra*(p_hi-thr)/(1-thr)；否则 → 回归值
for thr in [0.3, 0.5, 0.7]:
    pred_2s = oof_proxy.copy()
    hi = p_hi >= thr
    pred_2s[hi] = cap + MEK_CFG['extra'] * np.clip((p_hi[hi] - thr) / (1 - thr), 0, 1)
    r2u, acc2, accu2, rec2 = honest_eval(yt[~cen_mask], pred_2s[~cen_mask], yt, pred_2s, cap)
    print(f'  两阶段 thr={thr} → 未截尾 R²={r2u:.4f}, 边界 acc={acc2:.4f} (未截尾 acc={accu2:.4f}, 截尾召回={rec2:.4f})')
print(f'  对比：代理目标 未截尾R²={r2_unc:.4f} 边界acc={acc:.4f}；未截尾回归 R²={r2_unc_reg:.4f}')

print()
print('='*70)
print('实验 K-3: 训练变体对比（代理目标 vs 丢弃截尾 vs Tobit 式）')
print('='*70)
# 变体A：代理目标（K-1 已算）→ r2_proxy
# 变体B：丢弃截尾训练（K-2 已算）→ r2_unc_reg
# 变体C：Tobit 式目标——截尾样本用"≥cap 的软标签"，回归在全部样本上
#   用 p_hi 作为截尾样本的连续目标（cap + extra*p_hi），但评估只看未截尾
#   这其实与代理目标相同。真正的 Tobit 需要自定义损失。
#   近似：对截尾样本，目标设为 cap + extra*p_hi（同代理），但回归损失对截尾样本
#   只罚"预测<cap"（即预测低于 cap 才惩罚）。用样本权重近似：截尾样本权重=1，
#   但预测<cap 时损失更大。简化实现：对截尾样本，若预测<cap，用 (cap-pred)^2 惩罚。
#   用 XGBoost 自定义目标实现 Tobit 式损失。
def tobit_obj(preds, labels):
    """Tobit 式目标（sqrt 空间）：未截尾用平方误差，截尾只罚预测<cap_sqrt"""
    y = np.asarray(labels)
    cap_sqrt = np.sqrt(300.0)
    grad = np.zeros_like(preds)
    hess = np.ones_like(preds) * 2.0
    unc = y < cap_sqrt  # 未截尾样本标签 < sqrt(300)
    grad[unc] = 2 * (preds[unc] - y[unc])
    cen = ~unc
    below = preds[cen] < cap_sqrt
    grad[cen] = 2 * (preds[cen] - cap_sqrt) * below
    hess[cen] = 2.0 * below + 0.1
    return grad, hess
# 在 sqrt 变换空间做 Tobit 回归（cap 也变换）
cap_sqrt = np.sqrt(cap)
X_all = Xt[:, keep_idx]  # 用代理目标的特征选择
r2s_tobit = []
oof_tobit = np.zeros(len(yt))
kf = KFold(5, shuffle=True, random_state=42)
for tr, te in kf.split(X_all):
    Xtr, Xte = add_series(X_all[tr], X_all[te], np.sqrt(y_proxy[tr]), np.array(sert)[tr], np.array(sert)[te], MEK_CFG['k'])
    ytr = np.sqrt(y_proxy[tr])
    ps = []
    for sd in range(NSEED):
        mx = XGBRegressor(n_estimators=1500, learning_rate=0.008, max_depth=4, subsample=0.8,
                          colsample_bytree=0.7, min_child_weight=2, random_state=42+sd, n_jobs=-1,
                          objective=tobit_obj)
        mx.fit(Xtr, ytr); ps.append(mx.predict(Xte))
        ml = LGBMRegressor(n_estimators=1500, learning_rate=0.008, num_leaves=15, max_depth=4,
                           subsample=0.8, colsample_bytree=0.7, min_child_samples=10, random_state=42+sd, n_jobs=-1, verbose=-1)
        ml.fit(Xtr, ytr); ps.append(ml.predict(Xte))
    pred = 0.5*np.mean(ps, axis=0)**2
    oof_tobit[te] = pred
    r2s_tobit.append(r2_score(y_proxy[te], pred))
r2_tobit = np.mean(r2s_tobit)
r2_unc_tobit, acc_tobit, acc_unc_tobit, rec_cen_tobit = honest_eval(yt[~cen_mask], oof_tobit[~cen_mask], yt, oof_tobit, cap)
print(f'  Tobit式 → 全样本R²(代理口径)={r2_tobit:.4f}, 未截尾R²={r2_unc_tobit:.4f}, 边界acc={acc_tobit:.4f} (截尾召回={rec_cen_tobit:.4f})')
print(f'  对比：代理目标 未截尾R²={r2_unc:.4f} 边界acc={acc:.4f}；丢弃截尾 未截尾R²={r2_unc_reg:.4f}')

print()
print('='*70)
print('实验 K-4: 边界分类特征重要性（什么驱动 ≥300）')
print('='*70)
imp_clf = get_imp(Xt, ybin, clf=True)
n_comp = len(present_codes)
n_enh = len(ENH_FEATURES)
n_ratio = len(explicit_ratios({}))
n_smi = len(SMI_AGG_KEYS)
feat_names = present_codes + ['烘烤温度', '烘烤时间'] + ENH_FEATURES + [f'ratio{i}' for i in range(n_ratio)] + [f'smi{i}' for i in range(n_smi)]
print(f'  特征维度: 组分{n_comp}+工艺2+增强{n_enh}+比例{n_ratio}+SMILES{n_smi} = {len(feat_names)}')
top = np.argsort(imp_clf)[-20:][::-1]
print('  边界分类 top-20 特征:')
for i in top:
    print(f'    {feat_names[i]}: {imp_clf[i]:.4f}')

print()
print('='*70)
print('实验 K 完成')
print('='*70)
