# -*- coding: utf-8 -*-
"""
实验 Q：建模方式改造与水煮评估口径修正
=====================================
在实验 P 确认机理特征有效的基础上，检验四项建模侧改动，并修正水煮的评估口径。

触发修正的事实（由「性能结果」表统计）：
  · 水煮等级取值 1/2/2.33/2.5/2.67/3/3.33/4/5，其中 **聚酯金黄 26 条全部为 2 级**
    —— 该体系对水煮不提供任何判别信息，只改变基率；
  · 因此「按体系分层」在该目标上的增益主要来自常量层的平凡命中，而非化学判别；
  · 现行「二值化(≥4) + 每系列阈值」把有序等级当二元标签，浪费了等级间次序信息。

四项改动
  A 序回归（Breckling 累积分解）替代二值化，报告 MAE / ±0.5 容差准确率 / ≥4 判别
  B 分层维度对比：按体系 / 按化学计量比 r 分箱 / 按系列（现有）
  C 小样本体系样本加权：聚酯金黄（n=26/29）相对环氧酚醛（n=189/345）的权重
  D 工艺记录缺失指示：bake_recorded（避免「无记录」被当作 0 ℃ 固化）

评估一律按体系拆分报告，避免常量层稀释结论。
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, accuracy_score, roc_auc_score, mean_absolute_error
from xgboost import XGBRegressor, XGBClassifier
from lightgbm import LGBMRegressor, LGBMClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'workbench'))
sys.path.insert(0, HERE)
from CoatingModelWorkbench import (load_dataset, ENH_FEATURES, explicit_ratios,
                                   smi_aggregate, SMI_AGG_KEYS, canon,
                                   enhanced_descriptors, _bake_feat)
from mech_desc import mech_features, MECH_FEATURES

SEEDS = int(sys.argv[sys.argv.index('--seeds') + 1]) if '--seeds' in sys.argv else 5
MEK_CAP = 300
GRADES = np.array([1.0, 2.0, 3.0, 4.0, 5.0])       # ASTM D1654 允许半级，评估用 ±0.5 容差
W_POLY = float(os.environ.get('W_POLY', 3.0))       # 改动 C：小样本体系权重

path = os.path.join(HERE, '..', '合并版数据集.xlsx')
mat_lib, samples, perf, proc = load_dataset(path)
present_codes = sorted(set(canon(str(c).strip()) for s in samples.values() for c in s['组分']))
IDS = sorted(samples.keys())


def build_rows(sid):
    comp = samples[sid]['组分']
    p = proc.get(sid, {})
    bt, btm = p.get('烘烤温度'), p.get('烘烤时间')
    c2 = {canon(k): v for k, v in comp.items()}
    row = [float(c2.get(c, 0)) for c in present_codes]
    row.append(_bake_feat(bt))
    row.append(_bake_feat(btm))
    d = enhanced_descriptors(comp, mat_lib, bake_temp=bt, bake_time=btm)
    if d is None:
        return None
    row += [d.get(f, 0.0) for f in ENH_FEATURES]
    row += explicit_ratios(comp)
    smi = smi_aggregate(comp)
    row += [smi.get(k, 0.0) for k in SMI_AGG_KEYS]
    md, _ = mech_features(comp, mat_lib, bt, btm, oh_source='ohv')
    mv = [0.0] * len(MECH_FEATURES) if md is None else [float(md.get(f, 0.0)) for f in MECH_FEATURES]
    return row, mv


Xb, Xm, series, fams, bake_rec = [], [], [], [], []
for sid in IDS:
    r = build_rows(sid)
    if r is None:
        continue
    b, mv = r
    Xb.append(b)
    Xm.append(mv)
    series.append(samples[sid].get('系列', ''))
    fams.append(samples[sid].get('体系', ''))
    bake_rec.append(1.0 if proc.get(sid, {}).get('烘烤温度') else 0.0)
Xb, Xm = np.array(Xb), np.array(Xm)
series = np.array(series, dtype=object)
fams = np.array(fams, dtype=object)
bake_rec = np.array(bake_rec)
ROW_OF = {sid: i for i, sid in enumerate(IDS)}
XBM = np.hstack([Xb, Xm])
NB = Xb.shape[1]
print(f'base {Xb.shape} + mech {Xm.shape} = {XBM.shape} | 种子 {SEEDS} | 有工艺记录 {int(bake_rec.sum())}/{len(bake_rec)}', flush=True)


def labeled(tgt):
    idx, y = [], []
    for s in IDS:
        v = perf.get(s, {}).get(tgt)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        y.append(v)
        idx.append(ROW_OF[s])
    return np.array(idx), np.array(y, dtype=float)


def add_series(Xtr, Xte, y_tr, ser_tr, ser_te, k=3):
    gm = y_tr.mean()
    enc, cnt, std = {}, {}, {}
    for s in set(ser_tr):
        vals = y_tr[ser_tr == s]
        n = len(vals)
        cnt[s] = n
        std[s] = float(vals.std()) if n > 1 else 0.0
        enc[s] = (n * vals.mean() + k * gm) / (n + k)
    cols_tr, cols_te = [], []
    for d, dv in ((enc, gm), (cnt, 0), (std, 0)):
        cols_tr.append(np.array([d.get(s, dv) for s in ser_tr]).reshape(-1, 1))
        cols_te.append(np.array([d.get(s, dv) for s in ser_te]).reshape(-1, 1))
    Xtr = np.hstack([Xtr] + cols_tr)
    Xte = np.hstack([Xte] + cols_te)
    for s in sorted(set(ser_tr)):
        Xtr = np.hstack([Xtr, (ser_tr == s).astype(float).reshape(-1, 1)])
        Xte = np.hstack([Xte, (ser_te == s).astype(float).reshape(-1, 1)])
    return Xtr, Xte


def get_imp(X, y, clf=False, sw=None):
    if clf:
        m = XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8,
                          colsample_bytree=0.8, random_state=42, n_jobs=-1)
    else:
        m = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8,
                         colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, y, sample_weight=sw)
    return m.feature_importances_


def select(X, y, n, clf=False, sw=None):
    return X[:, np.argsort(get_imp(X, y, clf, sw))[-n:]]


def cv_class(Xs, yb, ser, k, n, sw=None, est=400, clf_feat=True):
    """二值 OOF 概率（含特征选择与折叠内系列编码），可带样本权重。"""
    sel_kwargs = dict(clf=clf_feat, sw=sw)
    Xf = select(Xs, yb, n, **sel_kwargs)
    oof = np.zeros(len(yb))
    for tr, te in KFold(5, shuffle=True, random_state=42).split(Xf):
        Xtr, Xte = add_series(Xf[tr], Xf[te], yb[tr], ser[tr], ser[te], k)
        ps = []
        for sd in range(SEEDS):
            mx = XGBClassifier(n_estimators=est, learning_rate=0.05, max_depth=3, subsample=0.8,
                               colsample_bytree=0.8, random_state=42 + sd, n_jobs=-1)
            mx.fit(Xtr, yb[tr], sample_weight=None if sw is None else sw[tr])
            ps.append(mx.predict_proba(Xte)[:, 1])
            ml = LGBMClassifier(n_estimators=est, learning_rate=0.05, num_leaves=15, max_depth=3,
                                subsample=0.8, colsample_bytree=0.8, random_state=42 + sd,
                                n_jobs=-1, verbose=-1)
            ml.fit(Xtr, yb[tr], sample_weight=None if sw is None else sw[tr])
            ps.append(ml.predict_proba(Xte)[:, 1])
        oof[te] = np.mean(ps, axis=0)
    return oof


def cv_reg(Xs, y, ser, k, n, sw=None, est=1000, trans=None, inv=None, w=0.85, extra=None):
    Xf = select(Xs, trans(y) if trans is not None else y, n, sw=sw)
    yt = trans(y) if trans is not None else y
    r2s = []
    oof = np.zeros(len(y))
    for tr, te in KFold(5, shuffle=True, random_state=42).split(Xf):
        Xtr, Xte = add_series(Xf[tr], Xf[te], yt[tr], ser[tr], ser[te], k)
        if extra is not None:
            Xtr = np.hstack([Xtr, extra[tr].reshape(-1, 1)])
            Xte = np.hstack([Xte, extra[te].reshape(-1, 1)])
        px, pl = [], []
        for sd in range(SEEDS):
            mx = XGBRegressor(n_estimators=est, learning_rate=0.015, max_depth=3, subsample=0.7,
                              colsample_bytree=0.8, min_child_weight=1,
                              random_state=42 + sd, n_jobs=-1)
            mx.fit(Xtr, yt[tr], sample_weight=None if sw is None else sw[tr])
            px.append(mx.predict(Xte))
            ml = LGBMRegressor(n_estimators=est, learning_rate=0.015, num_leaves=15, max_depth=3,
                               subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                               random_state=42 + sd, n_jobs=-1, verbose=-1)
            ml.fit(Xtr, yt[tr], sample_weight=None if sw is None else sw[tr])
            pl.append(ml.predict(Xte))
        pred = w * np.mean(px, axis=0) + (1 - w) * np.mean(pl, axis=0)
        if inv is not None:
            pred = inv(pred)
        oof[te] = pred
        r2s.append(r2_score(y[te], pred))
    return float(np.mean(r2s)), oof


def best_threshold(y2, p, lo=0.30, hi=0.70):
    best = (0.0, 0.5)
    for th in np.arange(lo, hi, 0.005):
        a = accuracy_score(y2, (p >= th).astype(int))
        if a > best[0]:
            best = (float(a), float(th))
    return best


def per_series_pred(y2, p, ser, g_th, min_n=8):
    pred = np.zeros(len(y2))
    for u in set(ser):
        m = ser == u
        th = best_threshold(y2[m], p[m])[1] if m.sum() >= min_n else g_th
        pred[m] = (p[m] >= th).astype(int)
    return pred


def by_fam_report(fam, acc_arr):
    return {f: round(float(acc_arr[fam == f].mean()), 4) for f in sorted(set(fam))}


R = {}

# ============ A. 水煮：二值 vs 序回归（按体系拆分） ============
print('\n========== A. 水煮 二值 vs 序回归 ==========', flush=True)
idx, yw = labeled('水煮等级')
famw, serw = fams[idx], series[idx]
y2 = (yw >= 4).astype(int)
uniq = sorted({float(round(v, 2)) for v in yw})
print(f'  n={len(yw)} 等级取值={uniq} 正类率={y2.mean():.3f}', flush=True)
print('  体系分布:', {f: int((famw == f).sum()) for f in sorted(set(famw))}, flush=True)

# A1 现行：二值 + 全局阈值 + 每系列阈值
p_bin = cv_class(XBM[idx], y2, serw, 3, 80)
g_acc, g_th = best_threshold(y2, p_bin)
pred_bin = per_series_pred(y2, p_bin, serw, g_th)
A1 = dict(acc_global=g_acc, acc_per_series=float(accuracy_score(y2, pred_bin)),
          auc=float(roc_auc_score(y2, p_bin)),
          acc_by_fam=by_fam_report(famw, (pred_bin == y2).astype(float)))
print(f'  A1 二值(≥4)+每系列阈值: 全局={A1["acc_global"]:.4f} 每系列={A1["acc_per_series"]:.4f} '
      f'AUC={A1["auc"]:.4f}', flush=True)
print(f'     分体系: {A1["acc_by_fam"]}', flush=True)

# A2 序回归：K-1 个累积分类器 P(Y>=t)，期望等级 = 1 + Σ_t P(Y>=t)
cum = {}
for t in [2, 3, 4, 5]:
    yb = (yw >= t).astype(int)
    if yb.sum() < 15 or (1 - yb).sum() < 15:
        cum[t] = None
        continue
    cum[t] = cv_class(XBM[idx], yb, serw, 3, 60)
pg = np.ones(len(yw))
for t, p in cum.items():
    if p is not None:
        pg = pg + p
pg = np.clip(pg, 1.0, 5.0)
A2 = dict(mae=float(mean_absolute_error(yw, pg)),
          acc_tol05=float(np.mean(np.abs(yw - np.round(pg * 2) / 2) <= 0.5)),
          acc_exact=float(np.mean(np.abs(yw - pg) < 0.25)),
          r2=float(r2_score(yw, pg)),
          bin_acc_35=float(accuracy_score(y2, (pg >= 3.5).astype(int))),
          bin_auc=float(roc_auc_score(y2, pg)))
for t_name, val in [('环氧酚醛', famw == '环氧酚醛'), ('聚酯金黄', famw == '聚酯金黄')]:
    A2[f'mae_{t_name}'] = float(mean_absolute_error(yw[val], pg[val]))
print(f'  A2 序回归: MAE={A2["mae"]:.3f} 等级±0.5命中={A2["acc_tol05"]:.4f} R²={A2["r2"]:.4f} '
      f'≥3.5判≥4 acc={A2["bin_acc_35"]:.4f} AUC={A2["bin_auc"]:.4f}', flush=True)
print(f'     分体系 MAE: 环氧酚醛={A2["mae_环氧酚醛"]:.3f} 聚酯金黄={A2["mae_聚酯金黄"]:.3f}', flush=True)

R['水煮'] = dict(A1_binary=A1, A2_ordinal=A2, notes=dict(
    poly_constant=bool(np.all(yw[famw == '聚酯金黄'] == 2.0)),
    n_poly=int((famw == '聚酯金黄').sum())))
print('  聚酯金黄水煮标签是否全为 2 级:', R['水煮']['notes']['poly_constant'], flush=True)

# ============ B. 分层维度对比 ============
print('\n========== B. 分层维度: 体系 / r 分箱 / 系列 ==========', flush=True)
r_epoxy = XBM[idx, NB + MECH_FEATURES.index('r_phenol_epoxy')]
# 分箱边界取数据分位数，避免手工设界退化成单一层
edges = np.unique(np.quantile(r_epoxy, [0.2, 0.4, 0.6, 0.8]))
bins = np.digitize(r_epoxy, edges)
strata = {'按系列': serw, '按r分箱': np.array([f'r{b}' for b in bins], dtype=object),
          '按体系': famw}
B = {}
for nm, s in strata.items():
    sizes = np.array([int((s == u).sum()) for u in set(s)])
    p = cv_class(XBM[idx], y2, s, 3, 80)
    acc = best_threshold(y2, p)[0]
    ps = per_series_pred(y2, p, s, best_threshold(y2, p)[1])
    B[nm] = dict(n_strata=int(len(sizes)), min_stratum=int(sizes.min()) if len(sizes) else 0,
                 acc_global=float(acc), acc_stratified=float(accuracy_score(y2, ps)))
    print(f'  {nm:8s} 层数={B[nm]["n_strata"]:3d} 最小层={B[nm]["min_stratum"]:3d} '
          f'全局acc={B[nm]["acc_global"]:.4f} 分层阈值acc={B[nm]["acc_stratified"]:.4f}', flush=True)
R['分层'] = B

# ============ C. 小样本体系加权 ============
print('\n========== C. 小样本体系加权（MEK 未截尾回归） ==========', flush=True)
idxm, ym = labeled('MEK擦拭')
fam_m, ser_m = fams[idxm], series[idxm]
unc = np.where(ym != MEK_CAP)[0]
im, yu, sm, fm = idxm[unc], ym[unc], ser_m[unc], fam_m[unc]
# 阶段一（边界判别）用全部样本，阶段二（未截尾回归）只用未截尾样本：两级权重长度不同
sw_clf_all = np.where(fam_m == '聚酯金黄', W_POLY, 1.0)
sw_reg_unc = np.where(fm == '聚酯金黄', W_POLY, 1.0)
C = {}
for nm, use_w in [('等权', False), (f'聚酯金黄×{W_POLY:g}', True)]:
    swc = sw_clf_all if use_w else None
    swr = sw_reg_unc if use_w else None
    ybin_all = (ym >= MEK_CAP).astype(int)
    p_hi = cv_class(XBM[idxm], ybin_all, ser_m, 3, 75, sw=swc)
    r2, oof = cv_reg(XBM[im], yu, sm, 1, 45, sw=swr, est=1500,
                     trans=np.sqrt, inv=lambda p: p ** 2, extra=p_hi[unc])
    per = {f: float(r2_score(yu[fm == f], oof[fm == f])) for f in sorted(set(fm)) if (fm == f).sum() > 5}
    C[nm] = dict(r2=r2, r2_by_fam={k: round(v, 4) for k, v in per.items()}, n=int(len(yu)))
    print(f'  {nm:16s} 未截尾R²={r2:.4f} (n={len(yu)}) 分体系={C[nm]["r2_by_fam"]}', flush=True)
R['MEK加权'] = C

# ============ D. 工艺缺失指示 ============
print('\n========== D. bake_recorded 缺失指示（T弯） ==========', flush=True)
idxd, ydt = labeled('T弯')
D = {}
for nm, Xd in [('无指示', XBM[idxd]),
               ('+bake_recorded', np.hstack([XBM[idxd], bake_rec[idxd].reshape(-1, 1)]))]:
    s = series[idxd]
    r2f, oof = cv_reg(Xd, ydt, s, 8, 60, est=1000, trans=np.sqrt, inv=lambda p: p ** 2)
    mask = np.abs(ydt - oof) <= 2.0 * 1.244
    r2, _oof2 = cv_reg(Xd[mask], ydt[mask], s[mask], 8, 60, est=1000,
                       trans=np.sqrt, inv=lambda p: p ** 2)
    D[nm] = dict(r2_full=r2f, r2_filtered=r2, n_kept=int(mask.sum()),
                 bake_known=float(bake_rec[idxd].mean()))
    print(f'  {nm:16s} R²(全量)={r2f:.4f} R²(过滤)={r2:.4f} n={len(ydt)}→{mask.sum()} '
          f'(有工艺比例 {D[nm]["bake_known"]:.2f})', flush=True)
R['T弯工艺指示'] = D

out = os.environ.get('VAR_OUT', os.path.join(HERE, 'mvp82_result.json'))
json.dump(dict(seeds=SEEDS, w_poly=W_POLY, results=R), open(out, 'w'), ensure_ascii=False, indent=1)
print(f'\n完成，结果写入 {out}', flush=True)
