# -*- coding: utf-8 -*-
"""
实验 U：供应商 TDS/SDS 实测层对数据集准确度与模型性能的诚实增益
================================================================
把「档案实测替换类别典型值」与「当量口径自洽」两件事拆成可对照的四个原料库，
在实验 T 的同一诚实评估协议（折叠内 top-N 选择 + 公共噪声掩码 + 固定分类阈值）下重跑三目标：

  A0 旧库          类别典型值 / 送检组成（实验 T 的交付口径，两列当量互不绑定）
  A1 旧库+口径统一  不引入任何档案数值，仅把 EEW/OHV/AV 与 fg_* 绑定为标准换算
  A2 档案库（主）   TDS/SDS 实测值 + 口径统一（有档案支撑的一侧为准）＝ 交付数据集口径
  A3 档案库+当量优先 同 A2，但冲突时一律以当量列（OHV/EEW/AV）为准

除性能指标外，同时报告：
  · 化学计量诊断：环氧酚醛体系 r_phenol_epoxy 的分布与 r=1 的配方占比（档案层的机理论据）
  · 覆盖度诊断：配方级特征向量相对 A0 的漂移幅度、样本级实测锚定权重
  · 泛化诊断：T弯 GroupKFold-by-系列 与 留一系列外推（LSO），检验档案层是否只抬域内数字

用法：python3 mvp88_tds_uplift.py [--s1 20] [--s2 8] [--arms A0,A1,A2,A3]
"""
import sys, os, json, copy, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold, GroupKFold
from sklearn.metrics import r2_score, accuracy_score, roc_auc_score, mean_absolute_error
from xgboost import XGBRegressor, XGBClassifier
from lightgbm import LGBMRegressor, LGBMClassifier
from scipy.stats import wilcoxon, spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'workbench'))
sys.path.insert(0, HERE)
os.environ['MATERIALS_TDS'] = '0'          # 由本脚本按臂切换，不让 materials 自动叠加
import materials as _M                     # noqa: E402
import tds_sds                             # noqa: E402
import handbook_fixes as HF                # noqa: E402
import compo_rules                         # noqa: E402
import mech_desc                           # noqa: E402
from mech_desc import mech_features, MECH_FEATURES        # noqa: E402
from CoatingModelWorkbench import (load_dataset, ENH_FEATURES, explicit_ratios,   # noqa: E402
                                   smi_aggregate, SMI_AGG_KEYS, canon, enhanced_descriptors,
                                   _bake_feat)
from DataPrepWorkbench import est_material

S_IN = int(sys.argv[sys.argv.index('--s1') + 1]) if '--s1' in sys.argv else 20
S_EX = int(sys.argv[sys.argv.index('--s2') + 1]) if '--s2' in sys.argv else 8
ARMS = (sys.argv[sys.argv.index('--arms') + 1].split(',') if '--arms' in sys.argv
        else ['A0', 'A1', 'A2', 'A3'])
MEK_CAP = 300
NOISE_STD = 1.244
KEEP = {'T弯': 60, 'MEK': 45, 'MEK_clf': 75, '水煮': 80}
PATH = os.path.join(HERE, '..', '合并版数据集.xlsx')

_LIT0 = copy.deepcopy(mech_desc.LIT)      # 档案合并前的机理当量表
samples_all = {}
_perf = {}


ARM_CFG = {'A0': dict(tds=False, unify=False, prefer='documented'),
           'A1': dict(tds=False, unify=True, prefer='documented'),
           'A2': dict(tds=True, unify=True, prefer='documented'),
           'A3': dict(tds=True, unify=True, prefer='equiv')}


def build_library(arm):
    """按实验 T 的加工链重建原料库：类别典型值(+送检组成) → 占位修正 → [TDS/SDS] → 当量统一。"""
    import pickle
    cfg = ARM_CFG[arm]
    D = pickle.load(open(os.path.join(HERE, '..', 'data', 'merged_data.pkl'), 'rb'))
    used = sorted({c for s in D['all_samples'] for c in s['组分']})
    mat = {c: copy.deepcopy(_M.MAT[c]) if c in _M.MAT else est_material(c)
           for c in used}
    for c, m in mat.items():
        m.setdefault('数据来源', '类别典型值(工作台估算登记)')
    _ch, merge, _pd = HF.apply(mat)
    for c in merge:
        mat.pop(c, None)
    mech_desc.LIT = copy.deepcopy(_LIT0)
    if cfg['tds']:
        tds_sds.apply(mat, unify=False, use_tds=True)
        tds_sds._merge_lit()
    if cfg['unify']:
        tds_sds.unify_equivalents(mat, {}, prefer=cfg['prefer'])
    for m in mat.values():
        for k in tds_sds.CONT_DESC_KEYS:
            v = m.get(k, 0.0)
            m[k] = 0.0 if v is None or (isinstance(v, float) and np.isnan(v)) else v
    return mat


def build_rows(mat):
    """返回 (base 特征矩阵, mech 特征矩阵, 系列, 体系, 样本ID)。"""
    present = sorted(set(canon(str(c).strip()) for s in SAMPLES.values() for c in s['组分']))
    ids = sorted(SAMPLES.keys())
    Xb, Xm, ser, fam = [], [], [], []
    for sid in ids:
        comp = SAMPLES[sid]['组分']
        p = PROC.get(sid, {})
        bt, btm = p.get('烘烤温度'), p.get('烘烤时间')
        c2 = {canon(k): v for k, v in comp.items()}
        row = [float(c2.get(c, 0)) for c in present] + [_bake_feat(bt), _bake_feat(btm)]
        d = enhanced_descriptors(comp, mat, bake_temp=bt, bake_time=btm)
        if d is None:
            continue
        row += [d.get(f, 0.0) for f in ENH_FEATURES]
        row += explicit_ratios(comp)
        smi = smi_aggregate(comp)
        row += [smi.get(k, 0.0) for k in SMI_AGG_KEYS]
        Xb.append(row)
        md, _ = mech_features(comp, mat, bt, btm, oh_source='ohv', nan_no_bake=True)
        Xm.append([float('nan') if md.get(f) is None or (isinstance(md.get(f), float) and np.isnan(md.get(f)))
                   else float(md.get(f)) for f in MECH_FEATURES])
        ser.append(SAMPLES[sid].get('系列', ''))
        fam.append(SAMPLES[sid].get('体系', ''))
    return np.array(Xb), np.array(Xm, dtype=float), np.array(ser, dtype=object), np.array(fam, dtype=object), ids


SAMPLES, PERF, PROC = None, None, None


# ---------------------------------------------------------------- 协议原语（与实验 T 一致）
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


def imp_of(X, yy, clf=False):
    m = XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8,
                      colsample_bytree=0.8, random_state=42, n_jobs=-1) if clf else \
        XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8,
                     colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, yy)
    return m.feature_importances_


def reg_fit(Xtr, ytr, sd, n_est=1000):
    mx = XGBRegressor(n_estimators=n_est, learning_rate=0.015, max_depth=3, subsample=0.7,
                      colsample_bytree=0.8, min_child_weight=1, random_state=42 + sd, n_jobs=-1)
    mx.fit(Xtr, ytr)
    ml = LGBMRegressor(n_estimators=n_est, learning_rate=0.015, num_leaves=15, max_depth=3,
                       subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                       random_state=42 + sd, n_jobs=-1, verbose=-1)
    ml.fit(Xtr, ytr)
    return mx, ml


def cv_seeds(Xd, y, ser, keep, seeds, trans=None, inv=None, w=0.85, splitter='kfold',
             groups=None, use_series=True, k=8, train_mask=None, folds_cache=None):
    yt = trans(y) if trans else y
    folds = folds_cache or (list(KFold(5, shuffle=True, random_state=42).split(Xd)) if splitter == 'kfold'
                            else list(GroupKFold(n_splits=5).split(Xd, groups=groups)))
    sels = [np.argsort(imp_of(Xd[tr if train_mask is None else tr[train_mask[tr]]],
                              yt[tr if train_mask is None else tr[train_mask[tr]]]))[-keep:]
            for tr, _ in folds]
    oofs = []
    for sd in range(seeds):
        oof = np.zeros(len(y))
        for (tr, te), sel in zip(folds, sels):
            tr_use = tr if train_mask is None else tr[train_mask[tr]]
            Xtr, Xte = Xd[tr_use][:, sel], Xd[te][:, sel]
            if use_series:
                Xtr, Xte = add_series(Xtr, Xte, yt[tr_use], ser[tr_use], ser[te], k)
            mx, ml = reg_fit(Xtr, yt[tr_use], sd)
            pred = w * mx.predict(Xte) + (1 - w) * ml.predict(Xte)
            oof[te] = inv(pred) if inv else pred
        oofs.append(oof)
    return oofs


SQR_INV = lambda p: np.clip(p, 0, None) ** 2      # noqa: E731


def labeled(ids, tgt, X_rows):
    idx, y = [], []
    for i, s in enumerate(ids):
        v = PERF.get(s, {}).get(tgt)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        y.append(v)
        idx.append(i)
    return np.array(idx), np.array(y, dtype=float)


# ---------------------------------------------------------------- 主流程
RESULT = {'protocol': dict(seeds_infold=S_IN, seeds_extra=S_EX, keep=KEEP,
                           noise_std=NOISE_STD, mek_cap=MEK_CAP)}
_, SAMPLES, PERF, PROC = load_dataset(PATH)
print(f'数据集 {os.path.basename(PATH)}：样本 {len(SAMPLES)} | 域内种子 {S_IN} | 外推种子 {S_EX} | 臂 {ARMS}',
      flush=True)
REF = None

for arm in ARMS:
    mat = build_library(arm)
    Xb, Xm, series, fams, ids = build_rows(mat)
    n_TDS = sum(1 for m in mat.values() if (m.get('数据来源') or '').startswith('TDS'))
    print(f'\n========== {arm}  原料 {len(mat)} 种 / 档案覆盖 {n_TDS} 种 | base {Xb.shape} |', flush=True)
    R = {'n_tds_materials': n_TDS, 'base_dim': int(Xb.shape[1])}

    # ---------------- T弯：域内（折叠内选择 + 公共掩码） ----------------
    iT, yT = labeled(ids, 'T弯', Xb)
    serT = series[iT]
    XbT, B_mech = Xb[iT], np.hstack([Xb[iT], Xm[iT]])
    foldsT = list(KFold(5, shuffle=True, random_state=42).split(XbT))
    selA = np.argsort(imp_of(XbT, np.sqrt(yT)))[: -KEEP['T弯']]
    oofA = np.zeros(len(yT))
    for sd in range(5):
        o = np.zeros(len(yT))
        for tr, te in foldsT:
            Xtr, Xte = add_series(XbT[tr][:, selA], XbT[te][:, selA], np.sqrt(yT[tr]), serT[tr], serT[te])
            mx, ml = reg_fit(Xtr, np.sqrt(yT[tr]), sd)
            o[te] = 0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte)
        oofA += o / 5
    predA = np.clip(oofA, 0, None) ** 2
    MASK = np.abs(yT - predA) <= 2.0 * NOISE_STD
    R['T_mask_n'] = int(MASK.sum())
    stats = {}
    for name, Xd, keep in (('base', XbT, KEEP['T弯']), ('base+mech', B_mech, KEEP['T弯']),
                           ('base+mech@96', B_mech, 96)):
        oofs = cv_seeds(Xd, yT, serT, keep, S_IN, trans=np.sqrt, inv=SQR_INV, train_mask=MASK)
        stats[name] = (np.array([float(r2_score(yT, o)) for o in oofs]),
                       np.array([float(r2_score(yT[MASK], o[MASK])) for o in oofs]))
        print(f'  T弯 {name:14s} R²(全)={stats[name][0].mean():.4f}±{stats[name][0].std():.4f}  '
              f'R²(掩码)={stats[name][1].mean():.4f}±{stats[name][1].std():.4f}  '
              f'MAE(掩码)={mean_absolute_error(yT[MASK], np.clip(oofs[-1],0,None)[MASK]):.3f}', flush=True)
    R['T'] = {k: dict(r2_all=[float(v[0].mean()), float(v[0].std())],
                      r2_masked=[float(v[1].mean()), float(v[1].std())]) for k, v in stats.items()}
    R['T_paired_vs_base'] = {k: dict(
        d_all=float((stats[k][0] - stats['base'][0]).mean()),
        p_all=float(wilcoxon(stats[k][0], stats['base'][0]).pvalue),
        d_masked=float((stats[k][1] - stats['base'][1]).mean()),
        p_masked=float(wilcoxon(stats[k][1], stats['base'][1]).pvalue))
        for k in stats if k != 'base'}

    # ---------------- T弯：GroupKFold-by-系列 与 LSO（泛化诊断） ----------------
    g = {}
    for name, Xd in (('base', XbT), ('base+mech', B_mech)):
        oofs = cv_seeds(Xd, yT, serT, KEEP['T弯'], S_EX, trans=np.sqrt, inv=SQR_INV,
                        splitter='group', groups=serT)
        g[name] = [float(r2_score(yT, o)) for o in oofs]
    cnt = {}
    for s in serT:
        cnt[s] = cnt.get(s, 0) + 1
    big = [s for s, c in sorted(cnt.items()) if c >= 12]
    lso = {}
    for hd in big:
        hold = serT == hd
        tr_idx, te_idx = np.where(~hold)[0], np.where(hold)[0]
        for name, Xd in (('base', XbT), ('base+mech', B_mech)):
            sel = np.argsort(imp_of(Xd[tr_idx], np.sqrt(yT[tr_idx])))[: -KEEP['T弯']]
            preds = np.zeros(len(te_idx))
            for sd in range(S_EX):
                Xtr, Xte = add_series(Xd[tr_idx][:, sel], Xd[te_idx][:, sel],
                                      np.sqrt(yT[tr_idx]), serT[tr_idx], serT[te_idx])
                mx, ml = reg_fit(Xtr, np.sqrt(yT[tr_idx]), sd)
                preds += (0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte)) / S_EX
            p = np.clip(preds, 0, None) ** 2
            lso.setdefault(name, {})[hd] = dict(n=int(len(te_idx)),
                                                r2=round(float(r2_score(yT[te_idx], p)), 4))
    wsum = {k: round(float(np.average([v['r2'] for v in lso[k].values()],
                                      weights=[v['n'] for v in lso[k].values()])), 4) for k in lso}
    R['T_groupkfold'] = {k: [float(np.mean(v)), float(np.std(v))] for k, v in g.items()}
    R['T_lso_weighted'] = wsum
    R['T_lso_per_series'] = lso
    print('  T弯 GroupKFold ' + '  '.join(f'{k}={np.mean(v):.4f}' for k, v in g.items()) +
          '  LSO加权 ' + '  '.join(f'{k}={v:+.4f}' for k, v in wsum.items()), flush=True)

    # ---------------- 水煮：折叠内选择 + 固定 0.5 ----------------
    iW, yW = labeled(ids, '水煮等级', Xb)
    y2 = (yW.astype(int) >= 4).astype(int)
    serW, famW = series[iW], fams[iW]
    W = {}
    for name, Xd in (('base', Xb[iW]), ('base+mech', np.hstack([Xb[iW], Xm[iW]]))):
        folds = list(KFold(5, shuffle=True, random_state=42).split(Xd))
        sels = [np.argsort(imp_of(Xd[tr], y2[tr], clf=True))[: -KEEP['水煮']] for tr, _ in folds]
        accs, aucs = [], []
        for sd in range(S_IN):
            oof = np.zeros(len(y2))
            for (tr, te), sel in zip(folds, sels):
                Xtr, Xte = add_series(Xd[tr][:, sel], Xd[te][:, sel], y2[tr], serW[tr], serW[te], 3)
                mc = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8,
                                   colsample_bytree=0.8, random_state=42 + sd, n_jobs=-1)
                mc.fit(Xtr, y2[tr])
                mlc = LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=15, max_depth=3,
                                     subsample=0.8, colsample_bytree=0.8, random_state=42 + sd,
                                     n_jobs=-1, verbose=-1)
                mlc.fit(Xtr, y2[tr])
                oof[te] = 0.5 * mc.predict_proba(Xte)[:, 1] + 0.5 * mlc.predict_proba(Xte)[:, 1]
            accs.append(float(accuracy_score(y2, (oof >= 0.5).astype(int))))
            aucs.append(float(roc_auc_score(y2, oof)))
        byf = {}
        for f in sorted(set(famW)):
            mk = famW == f
            byf[f] = dict(n=int(mk.sum()), pos=int(y2[mk].sum()),
                          acc=round(float(accuracy_score(y2[mk], (oof[mk] >= 0.5).astype(int))), 4))
        W[name] = dict(acc=[float(np.mean(accs)), float(np.std(accs))],
                       auc=[float(np.mean(aucs)), float(np.std(aucs))], by_family=byf)
        print(f'  水煮 {name:10s} acc(固定0.5)={np.mean(accs):.4f}±{np.std(accs):.4f}  '
              f'AUC={np.mean(aucs):.4f}  分体系={byf}', flush=True)
    R['W'] = W

    # ---------------- MEK：两阶段（边界判别 + 未截尾回归） ----------------
    iM, yM = labeled(ids, 'MEK擦拭', Xb)
    serM = series[iM]
    ybin = (yM >= MEK_CAP).astype(int)
    unc = np.where(yM != MEK_CAP)[0]
    ME = {}
    for name, Xd in (('base', Xb[iM]), ('base+mech', np.hstack([Xb[iM], Xm[iM]]))):
        folds = list(KFold(5, shuffle=True, random_state=42).split(Xd))
        sels = [np.argsort(imp_of(Xd[tr], ybin[tr], clf=True))[: -KEEP['MEK_clf']] for tr, _ in folds]
        p_hi = np.zeros(len(yM))
        for (tr, te), sel in zip(folds, sels):
            Xtr, Xte = add_series(Xd[tr][:, sel], Xd[te][:, sel], ybin[tr], serM[tr], serM[te], 3)
            mc = XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=3, subsample=0.8,
                               colsample_bytree=0.8, random_state=42, n_jobs=-1)
            mc.fit(Xtr, ybin[tr])
            mlc = LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=15, max_depth=3,
                                 subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1,
                                 verbose=-1)
            mlc.fit(Xtr, ybin[tr])
            p_hi[te] = 0.5 * mc.predict_proba(Xte)[:, 1] + 0.5 * mlc.predict_proba(Xte)[:, 1]
        Xu, yu, su, pu = Xd[unc], yM[unc], serM[unc], p_hi[unc]
        folds_u = list(KFold(5, shuffle=True, random_state=42).split(Xu))
        sels_u = [np.argsort(imp_of(Xu[tr], np.sqrt(yu[tr])))[: -KEEP['MEK']] for tr, _ in folds_u]
        r2s = []
        for sd in range(S_EX):
            oof = np.zeros(len(yu))
            for (tr, te), sel in zip(folds_u, sels_u):
                Xtr, Xte = add_series(Xu[tr][:, sel], Xu[te][:, sel], np.sqrt(yu[tr]), su[tr], su[te], 1)
                Xtr = np.hstack([Xtr, pu[tr].reshape(-1, 1)])
                Xte = np.hstack([Xte, pu[te].reshape(-1, 1)])
                mx, ml = reg_fit(Xtr, np.sqrt(yu[tr]), sd, n_est=1500)
                oof[te] = (0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte)) ** 2
            r2s.append(float(r2_score(yu, oof)))
        ME[name] = dict(r2_unc=[float(np.mean(r2s)), float(np.std(r2s))],
                        bnd_acc=round(float(accuracy_score(ybin, (p_hi >= 0.5).astype(int))), 4),
                        bnd_auc=round(float(roc_auc_score(ybin, p_hi)), 4), n_unc=int(len(yu)))
        print(f'  MEK {name:10s} 未截尾R²={np.mean(r2s):.4f}±{np.std(r2s):.4f}(n={len(yu)})  '
              f'边界acc={ME[name]["bnd_acc"]:.4f} AUC={ME[name]["bnd_auc"]:.4f}', flush=True)
    R['MEK'] = ME

    # ---------------- 诊断：化学计量分布 + 特征漂移 ----------------
    if arm == 'A0':
        REF_BASE, REF_IDS = Xb, ids
    else:
        common = [i for i, s in enumerate(ids) if s in REF_IDS]
        jj = [REF_IDS.index(ids[i]) for i in common]
        arr = np.abs(Xb[common] - REF_BASE[jj]) / (np.abs(REF_BASE[jj]) + 1e-6)
        R['drift_base_mean_abs_rel'] = round(float(np.mean(arr)), 4)
    RESULT[arm] = R

    # 计量诊断（对所有臂统一计算，便于横向比较）
    ep, vals, ys = [], [], []
    for s in ids:
        if SAMPLES[s]['体系'] != '环氧酚醛':
            continue
        try:
            d, _ = mech_features(SAMPLES[s]['组分'], mat, PROC.get(s, {}).get('烘烤温度'),
                                 PROC.get(s, {}).get('烘烤时间'), oh_source='ohv', nan_no_bake=True)
        except Exception:
            continue
        if d is None:
            continue
        rv = d.get('r_phenol_epoxy', 0.0) or 0.0
        ep.append(rv)
        v = PERF.get(s, {}).get('T弯')
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            vals.append(rv)
            ys.append(v)
    ep = np.asarray(ep, dtype=float)
    epz = ep[ep > 0]
    rho = float(spearmanr(vals, ys).statistic) if len(vals) >= 5 else None
    RESULT.setdefault('stoich', {})[arm] = dict(
        n_r=len(ep), n_r_gt0=int((ep > 0).sum()),
        r_median=round(float(np.median(epz)), 4) if len(epz) else None,
        r_p10=round(float(np.percentile(epz, 10)), 4) if len(epz) else None,
        r_p90=round(float(np.percentile(epz, 90)), 4) if len(epz) else None,
        frac_near_1=round(float(np.mean(np.abs(epz - 1) <= 0.25)), 4) if len(epz) else None,
        frac_zero=round(float(np.mean(ep == 0)), 4) if len(ep) else None,
        spearman_r_vs_T弯=round(rho, 4) if rho is not None else None)

    # 增量落盘：任一臂完成后即保存，避免中途崩溃丢失已跑完的臂
    json.dump(RESULT, open(os.environ.get('U_OUT', os.path.join(HERE, 'mvp88_result.json')), 'w'),
              ensure_ascii=False, indent=1)

print('\n========== 化学计量诊断（环氧酚醛 r_phenol_epoxy）==========')
for k, v in RESULT.get('stoich', {}).items():
    print(f'  {k}: {v}', flush=True)
out = os.environ.get('U_OUT', os.path.join(HERE, 'mvp88_result.json'))
json.dump(RESULT, open(out, 'w'), ensure_ascii=False, indent=1)
print(f'\n完成，写入 {out}', flush=True)
