# -*- coding: utf-8 -*-
"""
实验 T：泛化压力测试与评估泄漏修复（不依赖 TDS）
================================================
动机：现行协议有三处系统性乐观来源，全部与"评估方式"有关而非特征本身——
  (1) 特征选择在全量数据（含验证折标签）上做 top-N 重要性排序，选择步骤见过测试标签；
  (2) 水煮每系列阈值在用于报告同一份 OOF 概率上直接寻优，报的是"挑完阈值"的成绩；
  (3) 随机 KFold 下同一系列样本同时出现在训练/验证折，系列级批效应可被记忆，
      域内 R² 无法回答"新系列/新批次能否外推"。
另有一处特征卫生问题：无烘烤记录样本的固化类机理量记 0，与"真实低固化"混成同一伪域，
堵死向"有烘烤记录的其它体系/工艺"外推的路线；本实验改为 NaN（树模型学默认分裂方向）。

本脚本五个部分：
  P1 T弯域内：全局选择(现行对照) vs 折叠内选择（公共掩码不变），按种子报 mean±std；
  P2 T弯 GroupKFold-by-系列：折叠内选择，有/无系列编码块，衡量"新样本新系列混合外推"；
  P3 T弯 留一系列外推(LSO)：base / base+mech(NaN) / +物理单调约束 三臂，逐系列 R²/MAE；
  P4 水煮：折叠内选择 + 阈值诚实化（折内调阈值→折外应用 vs 现行折外直接寻优 vs 固定0.5）；
  P5 MEK 审计：折叠内选择重跑 mvp85 两阶段臂，量化 (1) 的影响。

判定口径：域内数字预期略降——降了才对。采纳标准是 LSO/GroupKFold 外推指标不劣化或改善，
单调约束只有在外推臂上稳定为正收益时才并入工作台默认配置。
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold, GroupKFold
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

S_IN = int(sys.argv[sys.argv.index('--s1') + 1]) if '--s1' in sys.argv else 10   # 域内种子
S_EX = int(sys.argv[sys.argv.index('--s2') + 1]) if '--s2' in sys.argv else 5    # 外推种子
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


def build_mech(sid, nan_bake=True):
    p = proc.get(sid, {})
    d, _ = mech_features(samples[sid]['组分'], mat_lib, p.get('烘烤温度'),
                         p.get('烘烤时间'), oh_source='ohv', nan_no_bake=nan_bake)
    if d is None:
        return [0.0] * len(MECH_FEATURES)
    return [float('nan') if d.get(f) is None or (isinstance(d.get(f), float) and np.isnan(d.get(f)))
            else float(d.get(f)) for f in MECH_FEATURES]


Xb, Xm, series, fams = [], [], [], []
for sid in IDS:
    b = build_base(sid)
    if b is None:
        continue
    Xb.append(b)
    Xm.append(build_mech(sid))
    series.append(samples[sid].get('系列', ''))
    fams.append(samples[sid].get('体系', ''))
Xb, Xm = np.array(Xb), np.array(Xm, dtype=float)
series = np.array(series, dtype=object)
fams = np.array(fams, dtype=object)
ROW_OF = {sid: i for i, sid in enumerate(IDS)}
NB = Xb.shape[1]
print(f'base {Xb.shape} | mech {Xm.shape}(NaN工艺口径) | 域内种子 {S_IN} | 外推种子 {S_EX}', flush=True)


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


def imp_of(X, yy, clf=False, mono=None):
    kw = {}
    if mono is not None:
        kw['monotone_constraints'] = tuple(mono)
    m = (XGBClassifier if clf else XGBRegressor)(
        n_estimators=300, learning_rate=0.05, max_depth=3 if clf else 4, subsample=0.8,
        colsample_bytree=0.8, random_state=42, n_jobs=-1, **kw)
    m.fit(X, yy)
    return m.feature_importances_


# 机理列物理单调先验（T弯 mm，越大越脆/越差）：
#   交联/刚性↑ → T弯变差(mm↑)：+1；当量偏离/玻璃化受限 → 欠固化更柔(mm↓)：-1
MONO_SIGN = {'ne_potential': 1, 'ne_effective': 1, 'xlink_per_binder': 1,
             'tg_fox_solids': 1, 'pvc': 1, 'stoich_dev_epoxy': -1, 'cure_margin_neg': -1}
MONO_FULL = [0] * NB + [MONO_SIGN.get(f, 0) for f in MECH_FEATURES]


def reg_fit(Xtr, ytr, sd, n_est=1000, mono=None):
    kw = {'monotone_constraints': tuple(mono)} if mono is not None else {}
    mx = XGBRegressor(n_estimators=n_est, learning_rate=0.015, max_depth=3, subsample=0.7,
                      colsample_bytree=0.8, min_child_weight=1, random_state=42 + sd,
                      n_jobs=-1, **kw)
    mx.fit(Xtr, ytr)
    ml = LGBMRegressor(n_estimators=n_est, learning_rate=0.015, num_leaves=15, max_depth=3,
                       subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                       random_state=42 + sd, n_jobs=-1, verbose=-1)
    ml.fit(Xtr, ytr)
    return mx, ml


def fold_sel(Xs, yt, tr, keep, clf=False):
    """折叠内特征选择：只用训练折标签。"""
    return np.argsort(imp_of(Xs[tr], yt[tr], clf=clf))[-keep:]


def cv_seeds(Xd, y, ser, keep, seeds, trans=None, inv=None, w=0.85, splitter='kfold',
             groups=None, use_series=True, k=8, mono_cols=None, n_est=1000,
             train_mask=None, extra=None):
    """逐种子诚实 CV：特征选择在折内做（只用训练折标签）。
    返回 (per-seed OOF 预测列表)。"""
    yt = trans(y) if trans else y
    folds = (list(KFold(5, shuffle=True, random_state=42).split(Xd)) if splitter == 'kfold'
             else list(GroupKFold(n_splits=5).split(Xd, groups=groups)))
    sels = []
    for tr, te in folds:
        tr_use = tr if train_mask is None else tr[train_mask[tr]]
        sels.append(fold_sel(Xd, yt, tr_use, keep))
    mono_map = {}
    if mono_cols is not None:
        for j in mono_cols:
            mono_map[j] = MONO_FULL[j] if j < len(MONO_FULL) else 0
    oofs = []
    for sd in range(seeds):
        oof = np.zeros(len(y))
        for (tr, te), sel in zip(folds, sels):
            tr_use = tr if train_mask is None else tr[train_mask[tr]]
            Xtr, Xte = Xd[tr_use][:, sel], Xd[te][:, sel]
            if use_series:
                Xtr, Xte = add_series(Xtr, Xte, yt[tr_use], ser[tr_use], ser[te], k)
            if extra is not None:
                Xtr = np.hstack([Xtr, extra[tr_use].reshape(-1, 1)])
                Xte = np.hstack([Xte, extra[te].reshape(-1, 1)])
            mono = None
            if mono_cols is not None:
                mono = [mono_map.get(int(s_), 0) for s_ in sel] + [0] * (Xtr.shape[1] - len(sel))
            mx, ml = reg_fit(Xtr, yt[tr_use], sd, n_est=n_est, mono=mono)
            pred = w * mx.predict(Xte) + (1 - w) * ml.predict(Xte)
            oof[te] = inv(pred) if inv else pred
        oofs.append(oof)
    return oofs


OUT = {}
SQR_INV = lambda p: np.clip(p, 0, None) ** 2   # 与 mvp84 一致：sqrt 逆变换先截负

# ================= P1 T弯 域内：全局选择 vs 折叠内选择 =================
print('\n========== P1 T弯 域内协议对照（公共掩码由 A 臂 OOF 定义） ==========', flush=True)
idxT, yT = labeled('T弯')
serT = series[idxT]
XbT, XmT = Xb[idxT], Xm[idxT]
A_base = XbT
B_base = XbT
B_mech = np.hstack([XbT, XmT])

# A 臂（现行：全局选择）多种子平均 OOF → 固定公共掩码（与 mvp84 口径一致）
selA = np.argsort(imp_of(A_base, np.sqrt(yT)))[-60:]
oofA = np.zeros(len(yT))
foldsA = list(KFold(5, shuffle=True, random_state=42).split(A_base))
for sd in range(S_IN):
    o = np.zeros(len(yT))
    for tr, te in foldsA:
        Xtr, Xte = add_series(A_base[tr][:, selA], A_base[te][:, selA], np.sqrt(yT[tr]), serT[tr], serT[te])
        mx, ml = reg_fit(Xtr, np.sqrt(yT[tr]), sd)
        o[te] = 0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte)
    oofA += o / S_IN
predA = np.clip(oofA, 0, None) ** 2
MASK = np.abs(yT - predA) <= 2.0 * NOISE_STD
r2A_all = float(r2_score(yT, predA))
r2A_mask = float(r2_score(yT[MASK], predA[MASK]))
print(f'  A 全局选择(现行) base@60   R²(全)={r2A_all:.4f}  R²(掩码)={r2A_mask:.4f}  掩码 {int(MASK.sum())}/{len(yT)}', flush=True)

P1 = {'A_global_base60': dict(r2_all=r2A_all, r2_masked=r2A_mask, mask_n=int(MASK.sum()))}
runs = [('B_infold_base45', B_base, 45, False), ('B_infold_base60', B_base, 60, False),
        ('B_infold_base72', B_base, 72, False), ('B_infold_mech60', B_mech, 60, False),
        ('B_infold_mech60_mono', B_mech, 60, True)]
mech_idx = list(range(NB, NB + XmT.shape[1]))
stats = {}
for name, Xd, keep, mono in runs:
    oofs = cv_seeds(Xd, yT, serT, keep, S_IN, trans=np.sqrt, inv=SQR_INV,
                    train_mask=MASK, mono_cols=mech_idx if mono else None)
    r_all = [float(r2_score(yT, o)) for o in oofs]
    r_msk = [float(r2_score(yT[MASK], o[MASK])) for o in oofs]
    stats[name] = dict(r_all=r_all, r_msk=r_msk)
    print(f'  {name:22s} R²(全)={np.mean(r_all):.4f}±{np.std(r_all):.4f}  '
          f'R²(掩码)={np.mean(r_msk):.4f}±{np.std(r_msk):.4f}', flush=True)
P1['B_infold'] = {k: dict(r2_all_mean=float(np.mean(v['r_all'])), r2_all_std=float(np.std(v['r_all'])),
                          r2_masked_mean=float(np.mean(v['r_msk'])), r2_masked_std=float(np.std(v['r_msk'])))
                  for k, v in stats.items()}
from scipy.stats import wilcoxon


def paired(a, b, key='r_msk'):
    d = np.subtract(stats[a][key], stats[b][key])
    try:
        p = float(wilcoxon(stats[a][key], stats[b][key]).pvalue)
    except Exception:
        p = 1.0
    return dict(mean=float(d.mean()), std=float(d.std()), wilcoxon_p=p)


P1['paired'] = {
    'mech_minus_base60_masked': paired('B_infold_mech60', 'B_infold_base60'),
    'mech_minus_base60_all': paired('B_infold_mech60', 'B_infold_base60', 'r_all'),
    'mono_minus_free_masked': paired('B_infold_mech60_mono', 'B_infold_mech60'),
    'infold_minus_global_base60': dict(
        mean=float(np.mean(stats['B_infold_base60']['r_msk']) - r2A_mask),
        note='折叠内(均值) − 全局选择(单次) 掩码内差值，量化选择泄漏幅度'),
}
for k, v in P1['paired'].items():
    print(f'  配对 {k}: {v["mean"]:+.4f} ± {v.get("std", float("nan")):.4f}'
          + (f'  p={v["wilcoxon_p"]:.4f}' if 'wilcoxon_p' in v else ''), flush=True)
OUT['P1'] = P1

# ================= P2 GroupKFold-by-系列 =================
print('\n========== P2 T弯 GroupKFold-5 by 系列（折叠内选择，无掩码） ==========', flush=True)
P2 = {}
for use_ser in (True, False):
    for name, Xd in (('base', XbT), ('base+mech', B_mech)):
        oofs = cv_seeds(Xd, yT, serT, 60, S_EX, trans=np.sqrt, inv=SQR_INV,
                        splitter='group', groups=serT, use_series=use_ser)
        ps = [float(r2_score(yT, o)) for o in oofs]
        key = f'{name}_serfeat' if use_ser else f'{name}_nosef'
        P2[key] = dict(mean=float(np.mean(ps)), std=float(np.std(ps)))
        print(f'  {name:11s} 系列特征={"有" if use_ser else "无"}  R² {np.mean(ps):.4f} ± {np.std(ps):.4f}', flush=True)
OUT['P2'] = P2

# ================= P3 LSO 留一系列外推 =================
print('\n========== P3 T弯 留一系列外推（n≥12 系列；训练集内选择+回退编码） ==========', flush=True)
ser_cnt = {}
for s in serT:
    ser_cnt[s] = ser_cnt.get(s, 0) + 1
big = [s for s, c in sorted(ser_cnt.items()) if c >= 12]
print(f'  留出系列 {len(big)} 个: {big}', flush=True)
ARM3 = {'base': XbT, 'base+mech': B_mech, 'base+mech+mono': B_mech}
lso = {}
for hd in big:
    hold = serT == hd
    tr_idx = np.where(~hold)[0]
    te_idx = np.where(hold)[0]
    for arm, Xd in ARM3.items():
        ytr = yT[tr_idx]
        mono = mech_idx if 'mono' in arm else None
        # 全训练集选择（只用训练标签）→ 单模型集成，逐种子
        Xtr_all = Xd[tr_idx]
        sel = fold_sel(Xtr_all, np.sqrt(ytr), np.arange(len(tr_idx)), 60)
        preds = np.zeros(len(te_idx))
        for sd in range(S_EX):
            Xtr, Xte = Xtr_all[:, sel], Xd[te_idx][:, sel]
            Xtr, Xte = add_series(Xtr, Xte, np.sqrt(ytr), serT[tr_idx], serT[te_idx])
            mcol = None
            if mono is not None:
                bm = {int(j): MONO_FULL[int(j)] for j in mono}
                mcol = [bm.get(int(s_), 0) for s_ in sel] + [0] * (Xtr.shape[1] - len(sel))
            mx, ml = reg_fit(Xtr, np.sqrt(ytr), sd, mono=mcol)
            preds += (0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte)) / S_EX
        p = np.clip(preds, 0, None) ** 2
        yy = yT[te_idx]
        rec = dict(n=int(len(te_idx)), r2=round(float(r2_score(yy, p)), 4),
                   mae=round(float(mean_absolute_error(yy, p)), 3))
        lso.setdefault(arm, {})[hd] = rec
    mrow = {a: round(float(np.mean([v['r2'] for v in lso[a].values()])), 4) for a in ARM3}
    print(f'  {hd:6s} n={ser_cnt[hd]:3d} ' + '  '.join(f'{a}={lso[a][hd]["r2"]:+.3f}' for a in ARM3), flush=True)
print('  留出系列 R² 均值：', mrow, flush=True)
wsum = {a: round(float(np.average([v['r2'] for v in lso[a].values()],
                                  weights=[v['n'] for v in lso[a].values()])), 4) for a in ARM3}
print('  样本量加权均值：', wsum, flush=True)
OUT['P3'] = dict(per_series=lso, mean=mrow, weighted=wsum, held_series=big)

# ================= P4 水煮：阈值诚实化 + 折叠内选择 =================
print('\n========== P4 水煮（二值≥4，折叠内选择 + 三种阈值口径） ==========', flush=True)
idxW, yW = labeled('水煮等级')
y2 = (yW.astype(int) >= 4).astype(int)
serW, famW = series[idxW], fams[idxW]


def best_th(a, b):
    best = (0.0, 0.5)
    for t in np.arange(0.35, 0.66, 0.005):
        v = accuracy_score(a, (b >= t).astype(int))
        if v > best[0]:
            best = (float(v), float(t))
    return best


def strat_apply(th_map, g_th, p, ser):
    pred = np.zeros(len(p))
    for i, s in enumerate(ser):
        t = th_map.get(s, g_th)
        pred[i] = int(p[i] >= t)
    return pred


clf_runs = {}
for arm, Xd in (('base', Xb[idxW]),
                ('base+mech', np.hstack([Xb[idxW], Xm[idxW]]))):
    sel_cache = [fold_sel(Xd, y2, tr, 80, clf=True)
                 for tr, te in KFold(5, shuffle=True, random_state=42).split(Xd)]
    acc_ft, acc_05, acc_opt, aucs = [], [], [], []
    for sd in range(S_IN):
        oof_p = np.zeros(len(y2))
        trn_p_all = np.zeros(len(y2))   # 折内训练集自身预测（供"折内调阈值"）
        for fi, ((tr, te), sel) in enumerate(zip(KFold(5, shuffle=True, random_state=42).split(Xd), sel_cache)):
            Xtr, Xte = add_series(Xd[tr][:, sel], Xd[te][:, sel], y2[tr], serW[tr], serW[te], 3)
            mc = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8,
                               colsample_bytree=0.8, random_state=42 + sd, n_jobs=-1)
            mc.fit(Xtr, y2[tr])
            mlc = LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=15, max_depth=3,
                                 subsample=0.8, colsample_bytree=0.8, random_state=42 + sd,
                                 n_jobs=-1, verbose=-1)
            mlc.fit(Xtr, y2[tr])
            pt = 0.5 * mc.predict_proba(Xte)[:, 1] + 0.5 * mlc.predict_proba(Xte)[:, 1]
            ptr = 0.5 * mc.predict_proba(Xtr)[:, 1] + 0.5 * mlc.predict_proba(Xtr)[:, 1]
            oof_p[te] = pt
            trn_p_all[tr] = ptr
        # (a) 固定 0.5
        acc_05.append(float(accuracy_score(y2, (oof_p >= 0.5).astype(int))))
        # (b) 折内调阈值→折外应用（诚实）：每折用训练折自身概率调每系列阈值，应用于验证折
        pred_h = np.zeros(len(y2))
        for tr, te in KFold(5, shuffle=True, random_state=42).split(Xd):
            g = best_th(y2[tr], trn_p_all[tr])[1]
            th_map = {}
            for s in set(serW[tr]):
                mtr = tr[serW[tr] == s]
                if len(mtr) >= 8:
                    th_map[s] = best_th(y2[mtr], trn_p_all[mtr])[1]
            for i in te:
                pred_h[i] = int(oof_p[i] >= th_map.get(serW[i], g))
        acc_ft.append(float(accuracy_score(y2, pred_h)))
        # (c) 现行口径（在同一 OOF 上全局挑每系列阈值，报喜偏置对照）
        g_acc, g_th = best_th(y2, oof_p)
        th_map = {s: best_th(y2[serW == s], oof_p[serW == s])[1]
                  for s in set(serW) if (serW == s).sum() >= 8}
        acc_opt.append(float(accuracy_score(y2, strat_apply(th_map, g_th, oof_p, serW))))
        aucs.append(float(roc_auc_score(y2, oof_p)))
    clf_runs[arm] = dict(acc_fixed05=float(np.mean(acc_05)), acc_foldthr=float(np.mean(acc_ft)),
                         acc_thr_optimistic=float(np.mean(acc_opt)), auc=float(np.mean(aucs)),
                         acc_foldthr_std=float(np.std(acc_ft)))
    print(f'  {arm:10s} 固定0.5={np.mean(acc_05):.4f}  折内调阈值={np.mean(acc_ft):.4f}±{np.std(acc_ft):.4f}  '
          f'折外寻优(对照)={np.mean(acc_opt):.4f}  AUC={np.mean(aucs):.4f}', flush=True)
    # 分体系（base+mech 折内调阈值口径）
    if arm == 'base+mech':
        byf = {}
        oof_last = oof_p
        g = best_th(y2, trn_p_all)[1]
        for f in sorted(set(famW)):
            m = famW == f
            byf[f] = dict(n=int(m.sum()), acc=round(float(accuracy_score(y2[m], (oof_last[m] >= 0.5).astype(int))), 4))
        clf_runs[arm]['by_fam_fixed05'] = byf
OUT['P4'] = clf_runs

# ================= P5 MEK 审计（折叠内选择） =================
print('\n========== P5 MEK 两阶段：全局选择(对照) vs 折叠内选择 ==========', flush=True)
idxM, yM = labeled('MEK擦拭')
serM = series[idxM]
ybin = (yM >= MEK_CAP).astype(int)
unc = np.where(yM != MEK_CAP)[0]
XbM, XmM = Xb[idxM], Xm[idxM]
P5 = {}
for arm, Xd in (('base', XbM), ('base+mech', np.hstack([XbM, XmM]))):
    # 分类器 p_hi：折叠内选择
    sel_c = [fold_sel(Xd, ybin, tr, 75, clf=True)
             for tr, te in KFold(5, shuffle=True, random_state=42).split(Xd)]
    p_hi = np.zeros(len(yM))
    for (tr, te), sel in zip(KFold(5, shuffle=True, random_state=42).split(Xd), sel_c):
        Xtr, Xte = add_series(Xd[tr][:, sel], Xd[te][:, sel], ybin[tr], serM[tr], serM[te], 3)
        mc = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8,
                           colsample_bytree=0.8, random_state=42, n_jobs=-1)
        mc.fit(Xtr, ybin[tr])
        mlc = LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=15, max_depth=3,
                             subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1, verbose=-1)
        mlc.fit(Xtr, ybin[tr])
        p_hi[te] = 0.5 * mc.predict_proba(Xte)[:, 1] + 0.5 * mlc.predict_proba(Xte)[:, 1]
    # 未截尾回归：折叠内选择 + p_hi 特征，逐种子
    Xu, yu, su, pu = Xd[unc], yM[unc], serM[unc], p_hi[unc]
    sely = [fold_sel(Xu, np.sqrt(yu), tr, 45) for tr, te in KFold(5, shuffle=True, random_state=42).split(Xu)]
    r2s = []
    for sd in range(S_EX):
        oof = np.zeros(len(yu))
        for (tr, te), sel in zip(KFold(5, shuffle=True, random_state=42).split(Xu), sely):
            Xtr, Xte = add_series(Xu[tr][:, sel], Xu[te][:, sel], np.sqrt(yu[tr]), su[tr], su[te], 1)
            Xtr = np.hstack([Xtr, pu[tr].reshape(-1, 1)])
            Xte = np.hstack([Xte, pu[te].reshape(-1, 1)])
            mx, ml = reg_fit(Xtr, np.sqrt(yu[tr]), sd, n_est=1500)
            oof[te] = (0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte)) ** 2
        r2s.append(float(r2_score(yu, oof)))
    P5[arm] = dict(r2_unc_infold=float(np.mean(r2s)), r2_unc_std=float(np.std(r2s)),
                   bnd_acc=float(accuracy_score(ybin, (p_hi >= 0.5).astype(int))),
                   bnd_auc=float(roc_auc_score(ybin, p_hi)))
    print(f'  {arm:10s} 未截尾R²(折叠内选择)={np.mean(r2s):.4f}±{np.std(r2s):.4f}  '
          f'边界acc={P5[arm]["bnd_acc"]:.4f} AUC={P5[arm]["bnd_auc"]:.4f}', flush=True)
P5['reference_global_selection'] = dict(base_r2=0.5087, base_mech_r2=0.4790,
                                        note='mvp85_s20 全局选择口径')
OUT['P5'] = P5

out = os.environ.get('HARD_OUT', os.path.join(HERE, 'mvp86_result.json'))
json.dump(OUT, open(out, 'w'), ensure_ascii=False, indent=1)
print(f'\n完成，写入 {out}', flush=True)
