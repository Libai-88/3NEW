# -*- coding: utf-8 -*-
"""
实验 P-3：T弯 A/B 的评估口径修正（公共掩码）
============================================
问题：沿用协议把「|OOF 残差| ≤ 2×噪声std」的样本筛除后，**在筛选后的子集上评估 R²**。
该子集由每个特征臂自己的 OOF 残差决定，于是不同臂比较的是不同的样本集合：
预测更平滑的臂会把更多"容易"样本留在评估集里，R² 被动抬高。5 种子与 20 种子下
同一对臂的差值符号相反（+0.047 与 −0.040），正是这一缺陷的表现，而非机理特征真的有害。

修正：噪声掩码只由**参考臂（base, keep=60）在全量数据上的 OOF 残差**确定一次，
所有臂共用；并且训练/评估的样本集合对所有臂完全一致。给出两个口径：
  R²(全样本)      5 折 CV，训练折内剔除掩码外样本，评估覆盖全部有标签样本
  R²(掩码样本)    同一 CV 的预测，只在公共掩码内的样本上计算 R²
两者的臂间差值才是机理特征的真实效应。
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'workbench'))
sys.path.insert(0, HERE)
from CoatingModelWorkbench import (load_dataset, ENH_FEATURES, explicit_ratios,
                                   smi_aggregate, SMI_AGG_KEYS, canon,
                                   enhanced_descriptors, _bake_feat)
from mech_desc import mech_features, MECH_FEATURES

SEEDS = int(sys.argv[sys.argv.index('--seeds') + 1]) if '--seeds' in sys.argv else 20
NOISE_STD = 1.244
KEEP_REF = 60
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


def build_mech(sid, oh):
    p = proc.get(sid, {})
    d, _ = mech_features(samples[sid]['组分'], mat_lib, p.get('烘烤温度'),
                         p.get('烘烤时间'), oh_source=oh)
    return [0.0] * len(MECH_FEATURES) if d is None else [float(d.get(f, 0.0)) for f in MECH_FEATURES]


Xb, Xm, Xmrec, series = [], [], [], []
for sid in IDS:
    b = build_base(sid)
    if b is None:
        continue
    Xb.append(b)
    Xm.append(build_mech(sid, 'ohv'))
    Xmrec.append(build_mech(sid, 'rec'))
    series.append(samples[sid].get('系列', ''))
Xb, Xm, Xmrec = np.array(Xb), np.array(Xm), np.array(Xmrec)
series = np.array(series, dtype=object)
ROW_OF = {sid: i for i, sid in enumerate(IDS)}
NB = Xb.shape[1]
print(f'base {Xb.shape} | mech {Xm.shape} | 种子 {SEEDS}', flush=True)

idx, y = [], []
for s in IDS:
    v = perf.get(s, {}).get('T弯')
    if v is None or (isinstance(v, float) and np.isnan(v)):
        continue
    y.append(v)
    idx.append(ROW_OF[s])
idx = np.array(idx)
y = np.array(y, dtype=float)
ser = series[idx]


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


def cv_common(Xs, keep, train_mask):
    """5 折 CV：训练折内只保留 train_mask 的样本，预测覆盖全部样本。"""
    sel = np.argsort(imp_of(Xs, np.sqrt(y)))[-keep:]
    Xs = Xs[:, sel]
    oof = np.zeros(len(y))
    for tr, te in KFold(5, shuffle=True, random_state=42).split(Xs):
        tr_keep = tr[train_mask[tr]]              # 训练折内剔除噪声样本
        Xtr, Xte = add_series(Xs[tr_keep], Xs[te], y[tr_keep], ser[tr_keep], ser[te])
        px, pl = [], []
        for sd in range(SEEDS):
            mx = XGBRegressor(n_estimators=1000, learning_rate=0.015, max_depth=3, subsample=0.7,
                              colsample_bytree=0.8, min_child_weight=1, random_state=42 + sd, n_jobs=-1)
            mx.fit(Xtr, np.sqrt(y[tr_keep])); px.append(mx.predict(Xte))
            ml = LGBMRegressor(n_estimators=1000, learning_rate=0.015, num_leaves=15, max_depth=3,
                               subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                               random_state=42 + sd, n_jobs=-1, verbose=-1)
            ml.fit(Xtr, np.sqrt(y[tr_keep])); pl.append(ml.predict(Xte))
        oof[te] = 0.85 * np.mean(px, axis=0) + 0.15 * np.mean(pl, axis=0)
    pred = np.clip(oof, 0, None) ** 2
    n_m = int(np.sum(sel >= NB))
    return pred, n_m


# 参考掩码：base@KEEP_REF 在全量数据上的 OOF 残差
print('\n步骤 1：由 base 臂确定公共噪声掩码', flush=True)
Xref = Xb[idx]
oof_ref = np.zeros(len(y))
sel_ref = np.argsort(imp_of(Xref, np.sqrt(y)))[-KEEP_REF:]
for tr, te in KFold(5, shuffle=True, random_state=42).split(Xref):
    Xtr, Xte = add_series(Xref[tr, :][:, sel_ref], Xref[te, :][:, sel_ref], y[tr], ser[tr], ser[te])
    px, pl = [], []
    for sd in range(SEEDS):
        mx = XGBRegressor(n_estimators=1000, learning_rate=0.015, max_depth=3, subsample=0.7,
                          colsample_bytree=0.8, min_child_weight=1, random_state=42 + sd, n_jobs=-1)
        mx.fit(Xtr, np.sqrt(y[tr])); px.append(mx.predict(Xte))
        ml = LGBMRegressor(n_estimators=1000, learning_rate=0.015, num_leaves=15, max_depth=3,
                           subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                           random_state=42 + sd, n_jobs=-1, verbose=-1)
        ml.fit(Xtr, np.sqrt(y[tr])); pl.append(ml.predict(Xte))
    oof_ref[te] = 0.85 * np.mean(px, axis=0) + 0.15 * np.mean(pl, axis=0)
base_pred = np.clip(oof_ref, 0, None) ** 2
MASK = np.abs(y - base_pred) <= 2.0 * NOISE_STD
print(f'  公共掩码保留 {int(MASK.sum())}/{len(y)} 样本（|残差| ≤ {2*NOISE_STD:.3f} mm）', flush=True)

ARMS = {'base': Xb[idx],
        'base+mech': np.hstack([Xb[idx], Xm[idx]]),
        'base+mech(rec口径)': np.hstack([Xb[idx], Xmrec[idx]]),
        'mech_only': Xm[idx]}
OUT = {'mask_n': int(MASK.sum()), 'n': int(len(y)), 'seeds': SEEDS, 'arms': {}}
print('\n步骤 2：各臂在同一掩码、同一评估集上比较', flush=True)
for arm, Xd in ARMS.items():
    for keep in ((60, 72) if arm != 'mech_only' else (40,)):
        pred, n_m = cv_common(Xd, keep, MASK)
        r_all = float(r2_score(y, pred))
        r_mask = float(r2_score(y[MASK], pred[MASK]))
        OUT['arms'].setdefault(arm, {})[str(keep)] = dict(
            r2_all_samples=r_all, r2_masked=r_mask, n_mech_selected=n_m)
        print(f'  {arm:18s} keep={keep:<3} R²(全样本)={r_all:.4f}  R²(掩码内)={r_mask:.4f}  '
              f'入选机理列={n_m}', flush=True)

ref = OUT['arms']['base']['60']
print('\n  以 base@60 为对照的差值：', flush=True)
for arm, d in OUT['arms'].items():
    for keep, v in d.items():
        if arm == 'base' and keep == '60':
            continue
        print(f'    {arm:18s} keep={keep}  ΔR²(全样本)={v["r2_all_samples"]-ref["r2_all_samples"]:+.4f}  '
              f'ΔR²(掩码内)={v["r2_masked"]-ref["r2_masked"]:+.4f}', flush=True)

out = os.environ.get('CM_OUT', os.path.join(HERE, 'mvp84_result.json'))
json.dump(OUT, open(out, 'w'), ensure_ascii=False, indent=1)
print(f'\n完成，写入 {out}', flush=True)
