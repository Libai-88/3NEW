# -*- coding: utf-8 -*-
"""
实验 P-2：机理特征的选择预算检验
================================
实验 P 的 20 种子复验显示：在 T弯 上 base+mech 反而低于 base。一个可检验的解释是
「top-N 固定预算下的零和挤压」——新增 40 列机理特征会占掉若干原有基线列的名额，
当基线本身已足够强时，被挤掉列的贡献大于机理列的贡献。

本脚本把 keep 预算作为显式变量，对每个目标做 keep 扫描：
  keep ∈ {基线值, 基线值+12, 基线值+24}   ×   arm ∈ {base, base+mech}
若机理列的收益随预算放宽而转正，则结论是「预算受限」而非「特征无用」；
若放宽后仍不转正，则机理特征对该目标判负。

同时报告每个臂的 top-40 机理列入选数与被挤掉的基线列数，作为机制证据。
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

SEEDS = int(sys.argv[sys.argv.index('--seeds') + 1]) if '--seeds' in sys.argv else 10
MEK_CAP = 300
NOISE_STD = 1.244
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


def build_mech(sid, oh='ohv'):
    p = proc.get(sid, {})
    d, _ = mech_features(samples[sid]['组分'], mat_lib, p.get('烘烤温度'),
                         p.get('烘烤时间'), oh_source=oh)
    return [0.0] * len(MECH_FEATURES) if d is None else [float(d.get(f, 0.0)) for f in MECH_FEATURES]


Xb, Xm, series = [], [], []
for sid in IDS:
    b = build_base(sid)
    if b is None:
        continue
    Xb.append(b)
    Xm.append(build_mech(sid))
    series.append(samples[sid].get('系列', ''))
Xb, Xm = np.array(Xb), np.array(Xm)
series = np.array(series, dtype=object)
ROW_OF = {sid: i for i, sid in enumerate(IDS)}
NB = Xb.shape[1]


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
    Xtr, Xte = np.hstack([Xtr] + ct), np.hstack([Xte] + ce)
    for s in sorted(set(ser_tr)):
        Xtr = np.hstack([Xtr, (ser_tr == s).astype(float).reshape(-1, 1)])
        Xte = np.hstack([Xte, (ser_te == s).astype(float).reshape(-1, 1)])
    return Xtr, Xte


def imp_of(X, y, clf=False):
    m = (XGBClassifier if clf else XGBRegressor)(
        n_estimators=300, learning_rate=0.05, max_depth=3 if clf else 4, subsample=0.8,
        colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, y)
    return m.feature_importances_


def cv_reg(Xs, y, ser, k, keep, est, trans=None, inv=None, w=0.85, extra=None, ret_oof=False):
    yt = trans(y) if trans else y
    sel = np.argsort(imp_of(Xs, yt, False))[-keep:]
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
        if inv:
            pred = inv(pred)
        oof[te] = pred
        r2s.append(r2_score(y[te], pred))
    return (float(np.mean(r2s)), oof, sel) if ret_oof else (float(np.mean(r2s)), None, sel)


def cv_clf(Xs, yb, ser, k, keep, est=400):
    sel = np.argsort(imp_of(Xs, yb, True))[-keep:]
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
    return oof, sel


def n_mech_in(sel):
    return int(np.sum(sel >= NB))


OUT = {}

# ---------- T弯：keep 扫描 ----------
print('\n========== T弯 keep 预算扫描（噪声过滤两步） ==========', flush=True)
idx, y = labeled('T弯')
T = {}
for base_keep in (60, 72, 84):
    T[base_keep] = {}
    for arm, X in (('base', Xb), ('base+mech', np.hstack([Xb, Xm]))):
        Xd, s = X[idx], series[idx]
        r2f, oof, _ = cv_reg(Xd, y, s, 8, base_keep, 1000, trans=np.sqrt,
                             inv=lambda p: p ** 2, ret_oof=True)
        mask = np.abs(y - oof) <= 2.0 * NOISE_STD
        r2, _o, sel = cv_reg(Xd[mask], y[mask], s[mask], 8, base_keep, 1000,
                             trans=np.sqrt, inv=lambda p: p ** 2)
        T[base_keep][arm] = dict(r2_full=r2f, r2_filtered=r2, n_mech_selected=n_mech_in(sel))
        print(f'  keep={base_keep:<3} {arm:11s} R²(过滤)={r2:.4f}  入选机理列={T[base_keep][arm]["n_mech_selected"]}', flush=True)
    d = T[base_keep]['base+mech']['r2_filtered'] - T[base_keep]['base']['r2_filtered']
    print(f'  → Δ(机理−基线) @keep={base_keep}: {d:+.4f}', flush=True)
OUT['T弯'] = {str(k): v for k, v in T.items()}

# ---------- MEK：keep 扫描 ----------
print('\n========== MEK 未截尾回归 keep 预算扫描 ==========', flush=True)
idx, y = labeled('MEK擦拭')
ybin = (y >= MEK_CAP).astype(int)
unc = np.where(y != MEK_CAP)[0]
Mk = {}
for arm, X in (('base', Xb), ('base+mech', np.hstack([Xb, Xm]))):
    Xd, s = X[idx], series[idx]
    p_hi, _sel_c = cv_clf(Xd, ybin, s, 3, 75)
    Mk[arm] = {}
    for keep in (45, 57, 69):
        r2, _o, sel = cv_reg(Xd[unc], y[unc], s[unc], 1, keep, 1500, trans=np.sqrt,
                             inv=lambda p: p ** 2, extra=p_hi[unc])
        Mk[arm][keep] = dict(r2=r2, n_mech_selected=n_mech_in(sel))
        print(f'  {arm:11s} keep={keep:<3} 未截尾R²={r2:.4f}  入选机理列={Mk[arm][keep]["n_mech_selected"]}', flush=True)
    for keep in (45, 57, 69):
        print(f'  → Δ @keep={keep}: {Mk["base+mech"][keep]["r2"] - Mk["base"][keep]["r2"]:+.4f}', flush=True)
OUT['MEK'] = {a: {str(k): v for k, v in d.items()} for a, d in Mk.items()}

# ---------- 水煮：keep 扫描 ----------
print('\n========== 水煮 keep 预算扫描（每系列阈值） ==========', flush=True)
idx, y = labeled('水煮等级')
y2 = (y.astype(int) >= 4).astype(int)
Wk = {}


def th_metrics(p, s):
    def bt(a, b):
        best = (0.0, 0.5)
        for t in np.arange(0.35, 0.66, 0.005):
            v = accuracy_score(a, (b >= t).astype(int))
            if v > best[0]:
                best = (float(v), float(t))
        return best
    g_acc, g_th = bt(y2, p)
    pred = np.zeros(len(y2))
    for u in set(s):
        m = s == u
        t = bt(y2[m], p[m])[1] if m.sum() >= 8 else g_th
        pred[m] = (p[m] >= t).astype(int)
    return g_acc, float(accuracy_score(y2, pred)), float(roc_auc_score(y2, p))


for arm, X in (('base', Xb), ('base+mech', np.hstack([Xb, Xm]))):
    Xd, s = X[idx], series[idx]
    Wk[arm] = {}
    for keep in (80, 92, 104):
        p, sel = cv_clf(Xd, y2, s, 3, keep)
        g, ps, auc = th_metrics(p, s)
        Wk[arm][keep] = dict(acc_global=g, acc_per_series=ps, auc=auc, n_mech_selected=n_mech_in(sel))
        print(f'  {arm:11s} keep={keep:<3} 每系列acc={ps:.4f} 全局acc={g:.4f} AUC={auc:.4f} '
              f'入选机理列={Wk[arm][keep]["n_mech_selected"]}', flush=True)
    for keep in (80, 92, 104):
        print(f'  → Δ @keep={keep}: {Wk["base+mech"][keep]["acc_per_series"] - Wk["base"][keep]["acc_per_series"]:+.4f}', flush=True)
OUT['水煮'] = {a: {str(k): v for k, v in d.items()} for a, d in Wk.items()}

out = os.environ.get('SWEEP_OUT', os.path.join(HERE, 'mvp83_result.json'))
json.dump(dict(seeds=SEEDS, n_base=NB, n_mech=int(Xm.shape[1]), results=OUT),
          open(out, 'w'), ensure_ascii=False, indent=1)
print(f'\n完成，写入 {out}', flush=True)
