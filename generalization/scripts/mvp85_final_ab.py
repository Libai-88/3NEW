# -*- coding: utf-8 -*-
"""
实验 P-4：MEK 与水煮的 20 种子终验（含按体系拆分与分层维度）
==========================================================
与实验 P（mvp81）同协议，只保留「基线」与「基线 + 机理特征（羟值换算口径）」两臂，
把种子数提到 20 与历史基线对齐，并按体系拆分报告。

水煮额外比较阈值分层维度：按系列（现行）vs 按化学计量比 r 分箱（实验 Q 中较优）。
MEK 的评估集为未截尾样本，与截尾处理无关，因此不受噪声掩码口径影响。
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, accuracy_score, roc_auc_score
from xgboost import XGBRegressor, XGBClassifier
from lightgbm import LGBMRegressor, LGBMClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'workbench'))
sys.path.insert(0, HERE)
from CoatingModelWorkbench import (load_dataset, ENH_FEATURES, explicit_ratios,
                                   smi_aggregate, SMI_AGG_KEYS, canon,
                                   enhanced_descriptors, _bake_feat)
from mech_desc import mech_features, MECH_FEATURES

SEEDS = int(sys.argv[sys.argv.index('--seeds') + 1]) if '--seeds' in sys.argv else 20
MEK_CAP = 300
path = os.path.join(HERE, '..', '合并版数据集.xlsx')
mat_lib, samples, perf, proc = load_dataset(path)
present_codes = sorted(set(canon(str(c).strip()) for s in samples.values() for c in s['组分']))
IDS = sorted(samples.keys())


def build_base(sid):
    comp = samples[sid]['组分']
    p = proc.get(sid, {})
    bt, btm = p.get('烘烤温度'), p.get('烘烤时间')
    c2 = {canon(k): v for k, v in comp.items()}
    row = [float(c2.get(c, 0)) for c in present_codes]
    row += [_bake_feat(bt), _bake_feat(btm)]
    d = enhanced_descriptors(comp, mat_lib, bake_temp=bt, bake_time=btm)
    if d is None:
        return None
    row += [d.get(f, 0.0) for f in ENH_FEATURES]
    row += explicit_ratios(comp)
    smi = smi_aggregate(comp)
    row += [smi.get(k, 0.0) for k in SMI_AGG_KEYS]
    return row


def build_mech(sid):
    p = proc.get(sid, {})
    d, _ = mech_features(samples[sid]['组分'], mat_lib, p.get('烘烤温度'),
                         p.get('烘烤时间'), oh_source='ohv')
    return [0.0] * len(MECH_FEATURES) if d is None else [float(d.get(f, 0.0)) for f in MECH_FEATURES]


Xb, Xm, series, fams = [], [], [], []
for sid in IDS:
    b = build_base(sid)
    if b is None:
        continue
    Xb.append(b)
    Xm.append(build_mech(sid))
    series.append(samples[sid].get('系列', ''))
    fams.append(samples[sid].get('体系', ''))
Xb, Xm = np.array(Xb), np.array(Xm)
series = np.array(series, dtype=object)
fams = np.array(fams, dtype=object)
ROW_OF = {sid: i for i, sid in enumerate(IDS)}
NB = Xb.shape[1]
ARMS = {'base': Xb, 'base+mech': np.hstack([Xb, Xm])}
print(f'base {Xb.shape} | mech {Xm.shape} | 种子 {SEEDS}', flush=True)


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
    ct, ce = [], []
    for d, dv in ((enc, gm), (cnt, 0), (std, 0)):
        ct.append(np.array([d.get(s, dv) for s in ser_tr]).reshape(-1, 1))
        ce.append(np.array([d.get(s, dv) for s in ser_te]).reshape(-1, 1))
    return np.hstack([Xtr] + ct), np.hstack([Xte] + ce)


def imp_of(X, yy, clf=False):
    m = (XGBClassifier if clf else XGBRegressor)(
        n_estimators=300, learning_rate=0.05, max_depth=3 if clf else 4, subsample=0.8,
        colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, yy)
    return m.feature_importances_


def cv_reg(Xs, y, ser, k, keep, est, trans=None, inv=None, extra=None, w=0.85):
    yt = trans(y) if trans else y
    sel = np.argsort(imp_of(Xs, yt))[-keep:]
    Xs = Xs[:, sel]
    oof = np.zeros(len(y))
    r2s = []
    for tr, te in KFold(5, shuffle=True, random_state=42).split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yt[tr], ser[tr], ser[te], k)
        if extra is not None:
            Xtr = np.hstack([Xtr, extra[tr].reshape(-1, 1)])
            Xte = np.hstack([Xte, extra[te].reshape(-1, 1)])
        px, pl = [], []
        for sd in range(SEEDS):
            mx = XGBRegressor(n_estimators=est, learning_rate=0.015, max_depth=3, subsample=0.7,
                              colsample_bytree=0.8, min_child_weight=1, random_state=42 + sd, n_jobs=-1)
            mx.fit(Xtr, yt[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(n_estimators=est, learning_rate=0.015, num_leaves=15, max_depth=3,
                               subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                               random_state=42 + sd, n_jobs=-1, verbose=-1)
            ml.fit(Xtr, yt[tr]); pl.append(ml.predict(Xte))
        pred = w * np.mean(px, axis=0) + (1 - w) * np.mean(pl, axis=0)
        oof[te] = inv(pred) if inv else pred
        r2s.append(r2_score(y[te], oof[te]))
    return float(np.mean(r2s)), oof, int(np.sum(sel >= NB))


def cv_clf(Xs, yb, ser, k, keep, est=400):
    sel = np.argsort(imp_of(Xs, yb, clf=True))[-keep:]
    Xs = Xs[:, sel]
    oof = np.zeros(len(yb))
    for tr, te in KFold(5, shuffle=True, random_state=42).split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yb[tr], ser[tr], ser[te], k)
        ps = []
        for sd in range(SEEDS):
            mx = XGBClassifier(n_estimators=est, learning_rate=0.05, max_depth=3, subsample=0.8,
                               colsample_bytree=0.8, random_state=42 + sd, n_jobs=-1)
            mx.fit(Xtr, yb[tr]); ps.append(mx.predict_proba(Xte)[:, 1])
            ml = LGBMClassifier(n_estimators=est, learning_rate=0.05, num_leaves=15, max_depth=3,
                                subsample=0.8, colsample_bytree=0.8, random_state=42 + sd,
                                n_jobs=-1, verbose=-1)
            ml.fit(Xtr, yb[tr]); ps.append(ml.predict_proba(Xte)[:, 1])
        oof[te] = np.mean(ps, axis=0)
    return oof, int(np.sum(sel >= NB))


def best_th(a, b):
    best = (0.0, 0.5)
    for t in np.arange(0.35, 0.66, 0.005):
        v = accuracy_score(a, (b >= t).astype(int))
        if v > best[0]:
            best = (float(v), float(t))
    return best


def stratified(p, y2, strata, g_th, min_n=8):
    pred = np.zeros(len(y2))
    for u in set(strata):
        m = strata == u
        t = best_th(y2[m], p[m])[1] if m.sum() >= min_n else g_th
        pred[m] = (p[m] >= t).astype(int)
    return pred


OUT = {'seeds': SEEDS, 'arms': {}}

# ================= MEK =================
print('\n========== MEK (边界 p_hi + 未截尾回归, keep=45 k=1) ==========', flush=True)
idx, y = labeled('MEK擦拭')
fam_m, ser_m = fams[idx], series[idx]
ybin = (y >= MEK_CAP).astype(int)
unc = np.where(y != MEK_CAP)[0]
for arm, X in ARMS.items():
    Xd = X[idx]
    p_hi, nm_c = cv_clf(Xd, ybin, ser_m, 3, 75)
    r2, oof, nm_r = cv_reg(Xd[unc], y[unc], ser_m[unc], 1, 45, 1500,
                           trans=np.sqrt, inv=lambda p: p ** 2, extra=p_hi[unc])
    per = {}
    for f in sorted(set(fam_m[unc])):
        m = fam_m[unc] == f
        if m.sum() >= 5:
            per[f] = dict(n=int(m.sum()), r2=round(float(r2_score(y[unc][m], oof[m])), 4),
                          mae=round(float(np.mean(np.abs(y[unc][m] - oof[m]))), 3))
    OUT['arms'].setdefault(arm, {})['MEK'] = dict(
        r2=r2, n_uncensored=int(len(unc)), bnd_acc=float(accuracy_score(ybin, (p_hi >= 0.5).astype(int))),
        bnd_auc=float(roc_auc_score(ybin, p_hi)), by_fam=per,
        n_mech_sel_clf=nm_c, n_mech_sel_reg=nm_r)
    print(f'  {arm:11s} 未截尾R²={r2:.4f} (n={len(unc)}) 边界acc={OUT["arms"][arm]["MEK"]["bnd_acc"]:.4f} '
          f'AUC={OUT["arms"][arm]["MEK"]["bnd_auc"]:.4f} 入选机理列(回归)={nm_r}', flush=True)
    print(f'          分体系={per}', flush=True)

# ================= 水煮 =================
print('\n========== 水煮 (二值≥4, keep=80) ==========', flush=True)
idx, y = labeled('水煮等级')
y2 = (y.astype(int) >= 4).astype(int)
fam_w, ser_w = fams[idx], series[idx]
r_epoxy = Xm[idx][:, MECH_FEATURES.index('r_phenol_epoxy')]
edges = np.unique(np.quantile(r_epoxy, [0.2, 0.4, 0.6, 0.8]))
r_bins = np.array([f'r{b}' for b in np.digitize(r_epoxy, edges)], dtype=object)
for arm, Xd in (('base', ARMS['base'][idx]), ('base+mech', np.hstack([ARMS['base'][idx], Xm[idx]]))):
    p, nm = cv_clf(Xd, y2, ser_w, 3, 80)
    g_acc, g_th = best_th(y2, p)
    ps = stratified(p, y2, ser_w, g_th)
    res = dict(acc_global=g_acc, acc_per_series=float(accuracy_score(y2, ps)),
               auc=float(roc_auc_score(y2, p)), n_mech_sel=nm,
               by_fam={f: dict(n=int((fam_w == f).sum()),
                               acc=round(float((ps == y2)[fam_w == f].mean()), 4))
                       for f in sorted(set(fam_w))})
    if arm == 'base+mech':
        pr = stratified(p, y2, r_bins, g_th)
        res['acc_per_r_bin'] = float(accuracy_score(y2, pr))
        res['r_bin_acc_by_fam'] = {f: round(float((pr == y2)[fam_w == f].mean()), 4)
                                   for f in sorted(set(fam_w))}
    OUT['arms'].setdefault(arm, {})['水煮'] = res
    print(f'  {arm:11s} 全局acc={g_acc:.4f} 每系列acc={res["acc_per_series"]:.4f} '
          f'AUC={res["auc"]:.4f} 入选机理列={nm}', flush=True)
    print(f'          分体系={res["by_fam"]}'
          + (f' 每r分箱acc={res["acc_per_r_bin"]:.4f}' if 'acc_per_r_bin' in res else ''), flush=True)

out = os.environ.get('FINAL_OUT', os.path.join(HERE, 'mvp85_result.json'))
json.dump(OUT, open(out, 'w'), ensure_ascii=False, indent=1)
print(f'\n完成，写入 {out}', flush=True)
