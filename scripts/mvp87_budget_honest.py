# -*- coding: utf-8 -*-
"""
实验 T-2：诚实协议下的选择预算复核（折叠内选择 + 公共掩码）
==========================================================
mvp86-P1 显示 base 臂 72 预算优于 60，但 mech 臂未测更大预算。
本实验只裁决一个问题：机理列进入候选空间后，多大 top-N 预算在
「折叠内选择」口径下最稳。预算取值先于结果确定（45/60/72/84/96），
评估主指标=公共掩码内 R²（20 种子配对），参考指标=留一系列外推加权 R²。
若 mech@更大预算相对 base@同预算仍无正收益，则诚实结论为：
T弯 机理列默认不参与（保留在数据集中供跨体系外推使用）。
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from scipy.stats import wilcoxon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'workbench'))
sys.path.insert(0, HERE)
from CoatingModelWorkbench import (load_dataset, ENH_FEATURES, explicit_ratios,
                                   smi_aggregate, SMI_AGG_KEYS, canon,
                                   enhanced_descriptors, _bake_feat)
from mech_desc import mech_features, MECH_FEATURES

SEEDS = int(sys.argv[sys.argv.index('--seeds') + 1]) if '--seeds' in sys.argv else 20
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


def build_mech(sid):
    p = proc.get(sid, {})
    d, _ = mech_features(samples[sid]['组分'], mat_lib, p.get('烘烤温度'),
                         p.get('烘烤时间'), oh_source='ohv', nan_no_bake=True)
    if d is None:
        return [0.0] * len(MECH_FEATURES)
    return [float(d[f]) if d.get(f) is not None else float('nan') for f in MECH_FEATURES]


Xb, Xm, series = [], [], []
for sid in IDS:
    b = build_base(sid)
    if b is None:
        continue
    Xb.append(b)
    Xm.append(build_mech(sid))
    series.append(samples[sid].get('系列', ''))
Xb, Xm = np.array(Xb), np.array(Xm, dtype=float)
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


def add_series(Xtr, Xte, y_tr, ser_tr, ser_te, k=8):
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


def imp_of(X, yy):
    m = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8,
                     colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, yy)
    return m.feature_importances_


idxT, yT = labeled('T弯')
serT = series[idxT]
XbT, XmT = Xb[idxT], Xm[idxT]

# 公共掩码：与 mvp84/mvp86 相同——A 臂（base 全局选择@60）20 种子 OOF
selA = np.argsort(imp_of(XbT, np.sqrt(yT)))[-60:]
foldsA = list(KFold(5, shuffle=True, random_state=42).split(XbT))
oofA = np.zeros(len(yT))
for sd in range(SEEDS):
    o = np.zeros(len(yT))
    for tr, te in foldsA:
        Xtr, Xte = add_series(XbT[tr][:, selA], XbT[te][:, selA], np.sqrt(yT[tr]), serT[tr], serT[te])
        mx = XGBRegressor(n_estimators=1000, learning_rate=0.015, max_depth=3, subsample=0.7,
                          colsample_bytree=0.8, min_child_weight=1, random_state=42 + sd, n_jobs=-1)
        mx.fit(Xtr, np.sqrt(yT[tr]))
        ml = LGBMRegressor(n_estimators=1000, learning_rate=0.015, num_leaves=15, max_depth=3,
                           subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                           random_state=42 + sd, n_jobs=-1, verbose=-1)
        ml.fit(Xtr, np.sqrt(yT[tr]))
        o[te] = 0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte)
    oofA += o / SEEDS
MASK = np.abs(yT - np.clip(oofA, 0, None) ** 2) <= 2.0 * NOISE_STD
print(f'公共掩码 {int(MASK.sum())}/{len(yT)}（A臂 base全局@60，{SEEDS}种子）', flush=True)

MONO_SIGN = {'ne_potential': 1, 'ne_effective': 1, 'xlink_per_binder': 1,
             'tg_fox_solids': 1, 'pvc': 1, 'stoich_dev_epoxy': -1, 'cure_margin_neg': -1}


def run(Xd, keep, mono):
    yt = np.sqrt(yT)
    folds = list(KFold(5, shuffle=True, random_state=42).split(Xd))
    sels = []
    for tr, te in folds:
        tru = tr[MASK[tr]]
        sels.append(np.argsort(imp_of(Xd[tru], yt[tru]))[-keep:])
    mono_map = {}
    if mono:
        for j, f in enumerate(MECH_FEATURES):
            if f in MONO_SIGN:
                mono_map[NB + j] = MONO_SIGN[f]
    oofs = []
    for sd in range(SEEDS):
        oof = np.zeros(len(yT))
        for (tr, te), sel in zip(folds, sels):
            tru = tr[MASK[tr]]
            Xtr, Xte = add_series(Xd[tru][:, sel], Xd[te][:, sel], yt[tru], serT[tru], serT[te])
            mc = [mono_map.get(int(s), 0) for s in sel] + [0] * (Xtr.shape[1] - len(sel)) if mono else None
            kw = {'monotone_constraints': tuple(mc)} if mono else {}
            mx = XGBRegressor(n_estimators=1000, learning_rate=0.015, max_depth=3, subsample=0.7,
                              colsample_bytree=0.8, min_child_weight=1, random_state=42 + sd,
                              n_jobs=-1, **kw)
            mx.fit(Xtr, yt[tru])
            ml = LGBMRegressor(n_estimators=1000, learning_rate=0.015, num_leaves=15, max_depth=3,
                               subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                               random_state=42 + sd, n_jobs=-1, verbose=-1)
            ml.fit(Xtr, yt[tru])
            oof[te] = np.clip(0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte), 0, None) ** 2
        oofs.append(oof)
    return ([float(r2_score(yT[MASK], o[MASK])) for o in oofs],
            [float(r2_score(yT, o)) for o in oofs])


OUT = {'mask_n': int(MASK.sum()), 'seeds': SEEDS, 'arms': {}}
res = {}
for arm, Xd in (('base', XbT), ('base+mech', np.hstack([XbT, XmT]))):
    for keep in (60, 72, 84, 96):
        mono = (arm == 'base+mech' and keep == 72)
        name = f'{arm}@{keep}' + ('_mono' if mono else '')
        rm, ra = run(Xd, keep, mono)
        res[name] = (rm, ra)
        print(f'  {name:22s} R²(掩码)={np.mean(rm):.4f}±{np.std(rm):.4f}  R²(全)={np.mean(ra):.4f}±{np.std(ra):.4f}', flush=True)
        OUT['arms'][name] = dict(r2_masked=float(np.mean(rm)), std_masked=float(np.std(rm)),
                                 r2_all=float(np.mean(ra)), std_all=float(np.std(ra)))
# 关键配对检验
for a, b in (('base+mech@72_mono', 'base@72'), ('base+mech@72', 'base@72'),
             ('base+mech@84', 'base@84'), ('base@96', 'base@60'),
             ('base+mech@72_mono', 'base+mech@72')):
    if a in res and b in res:
        d = np.subtract(res[a][0], res[b][0])
        try:
            p = float(wilcoxon(res[a][0], res[b][0]).pvalue)
        except Exception:
            p = 1.0
        OUT.setdefault('paired', {})[f'{a}-minus-{b}'] = dict(mean=float(d.mean()), p=p)
        print(f'  配对 {a} − {b}: {d.mean():+.4f}  p={p:.4f}', flush=True)

out = os.environ.get('BUD_OUT', os.path.join(HERE, 'mvp87_result.json'))
json.dump(OUT, open(out, 'w'), ensure_ascii=False, indent=1)
print(f'\n完成，写入 {out}', flush=True)
