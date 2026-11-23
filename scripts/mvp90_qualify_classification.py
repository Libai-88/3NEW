# -*- coding: utf-8 -*-
"""
实验 V：达标分类验证（预测"是多少" → 预测"能不能"）
====================================================
思路：T弯/MEK/水煮的产线决策本质是二值"能否达标"，而非连续值本身。
本实验把三个目标的回归问题转成业务二值分类问题，并回答三个问题：
  Q1 直接学分类（CLF）是否优于"先回归再阈值化"（REG→THR）？
  Q2 分类视角下 MEK 右截尾（43 条恰为 300）是否自动豁免？
  Q3 留一系列外推（LSO）上分类是否比回归更可用？

业务阈值（用户口径）：
  T弯：<15mm 达标（T15）、<20mm 达标（T20）——越小越好
  MEK：>70 次达标（M70）、>100 次达标（M100）——越大越好，100+ 无实际价值
  水煮：1-2 级达标（W3，3-5 级不合格）；另对照旧口径 W4（≥4 才不合格）

评估协议（沿用实验 T 诚实协议）：
  折叠内 top-N 特征选择（选择步骤不接触验证折标签）、KFold-5、
  20 种子报 mean±std、固定阈值 0.5、正类=不达标（不合格检出率=召回）。
  LSO：n≥12 系列逐一留出，训练集内选择 + 5 种子集成。
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import (accuracy_score, roc_auc_score, f1_score,
                             recall_score, r2_score, mean_absolute_error)
from xgboost import XGBRegressor, XGBClassifier
from lightgbm import LGBMRegressor, LGBMClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'workbench'))
from CoatingModelWorkbench import (load_dataset, ENH_FEATURES, explicit_ratios,
                                   smi_aggregate, SMI_AGG_KEYS, canon,
                                   enhanced_descriptors, _bake_feat)
from mech_desc import mech_features, MECH_FEATURES

# ---------------- 数据与特征构造（与 mvp86 完全一致） ----------------
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
print(f'特征矩阵 base {Xb.shape} | mech {Xm.shape}', flush=True)


def labeled(tgt):
    idx, y = [], []
    for s in IDS:
        v = perf.get(s, {}).get(tgt)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        y.append(v)
        idx.append(ROW_OF[s])
    return np.array(idx), np.array(y, dtype=float)


# ---------------- 工具函数（与 mvp86 一致） ----------------
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
    m = (XGBClassifier if clf else XGBRegressor)(
        n_estimators=300, learning_rate=0.05, max_depth=3 if clf else 4, subsample=0.8,
        colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, yy)
    return m.feature_importances_


def fold_sel(Xs, yt, tr, keep, clf=False):
    return np.argsort(imp_of(Xs[tr], yt[tr], clf=clf))[-keep:]


def reg_fit(Xtr, ytr, sd, n_est=1000):
    mx = XGBRegressor(n_estimators=n_est, learning_rate=0.015, max_depth=3, subsample=0.7,
                      colsample_bytree=0.8, min_child_weight=1, random_state=42 + sd, n_jobs=-1)
    mx.fit(Xtr, ytr)
    ml = LGBMRegressor(n_estimators=n_est, learning_rate=0.015, num_leaves=15, max_depth=3,
                       subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                       random_state=42 + sd, n_jobs=-1, verbose=-1)
    ml.fit(Xtr, ytr)
    return mx, ml


def clf_fit(Xtr, ytr, sd, n_est=400):
    mc = XGBClassifier(n_estimators=n_est, learning_rate=0.05, max_depth=3, subsample=0.8,
                       colsample_bytree=0.8, random_state=42 + sd, n_jobs=-1,
                       eval_metric='logloss')
    mc.fit(Xtr, ytr)
    mlc = LGBMClassifier(n_estimators=n_est, learning_rate=0.05, num_leaves=15, max_depth=3,
                         subsample=0.8, colsample_bytree=0.8, random_state=42 + sd,
                         n_jobs=-1, verbose=-1)
    mlc.fit(Xtr, ytr)
    return mc, mlc


def oof_clf(Xd, ybin, ser, keep, seeds, k=8):
    """直接分类：折叠内选择 + 系列编码，返回逐种子 OOF 概率（正类=1）。"""
    folds = list(KFold(5, shuffle=True, random_state=42).split(Xd))
    sels = [fold_sel(Xd, ybin, tr, keep, clf=True) for tr, te in folds]
    outs = []
    for sd in range(seeds):
        p = np.zeros(len(ybin))
        for (tr, te), sel in zip(folds, sels):
            Xtr, Xte = Xd[tr][:, sel], Xd[te][:, sel]
            Xtr, Xte = add_series(Xtr, Xte, ybin[tr], ser[tr], ser[te], k)
            mc, mlc = clf_fit(Xtr, ybin[tr], sd)
            p[te] = 0.5 * mc.predict_proba(Xte)[:, 1] + 0.5 * mlc.predict_proba(Xte)[:, 1]
        outs.append(p)
    return outs


def oof_reg(Xd, y, ser, keep, seeds, k=8):
    """回归管线：sqrt 变换 + 折叠内选择 + 系列编码，返回逐种子 OOF 预测（原尺度）。"""
    folds = list(KFold(5, shuffle=True, random_state=42).split(Xd))
    sels = [fold_sel(Xd, np.sqrt(y), tr, keep) for tr, te in folds]
    outs = []
    for sd in range(seeds):
        p = np.zeros(len(y))
        for (tr, te), sel in zip(folds, sels):
            Xtr, Xte = Xd[tr][:, sel], Xd[te][:, sel]
            Xtr, Xte = add_series(Xtr, Xte, np.sqrt(y[tr]), ser[tr], ser[te], k)
            mx, ml = reg_fit(Xtr, np.sqrt(y[tr]), sd)
            p[te] = np.clip(0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte), 0, None) ** 2
        outs.append(p)
    return outs


def metrics(y, p, thr=0.5):
    """正类=1（不达标）。返回 auc/acc/recall(不合格检出)/误杀率/f1。"""
    pred = (p >= thr).astype(int)
    auc = roc_auc_score(y, p) if len(set(y)) > 1 else float('nan')
    return dict(auc=float(auc), acc=float(accuracy_score(y, pred)),
                rec=float(recall_score(y, pred, zero_division=0)),
                mis=float(((y == 0) & (pred == 1)).mean()),       # 达标被误杀
                f1=float(f1_score(y, pred, zero_division=0)))


def agg(ms):
    def sm(k):
        vals = [m[k] for m in ms if not (isinstance(m[k], float) and np.isnan(m[k]))]
        return (float(np.mean(vals)), float(np.std(vals))) if vals else (float('nan'), float('nan'))
    return {k: sm(k) for k in ('auc', 'acc', 'rec', 'mis', 'f1')}


# ---------------- 任务定义 ----------------
# 达标判据（业务口径）；正类=不达标
TASKS = [
    ('T15', 'T弯',       lambda v: v < 15,  'T弯 < 15mm 达标'),
    ('T20', 'T弯',       lambda v: v < 20,  'T弯 < 20mm 达标'),
    ('M70', 'MEK擦拭',   lambda v: v > 70,  'MEK > 70 次达标'),
    ('M100', 'MEK擦拭',  lambda v: v > 100, 'MEK > 100 次达标'),
    ('W3', '水煮等级',   lambda v: np.asarray(v).astype(int) <= 2, '水煮 1-2 级达标（新口径）'),
]
# 水煮旧口径对照：≥4 不合格
W4 = ('W4', '水煮等级', lambda v: np.asarray(v).astype(int) >= 4, '水煮 ≥4 级不合格（旧口径）')

SEEDS_IN = int(sys.argv[sys.argv.index('--s1') + 1]) if '--s1' in sys.argv else 20
SEEDS_EX = int(sys.argv[sys.argv.index('--s2') + 1]) if '--s2' in sys.argv else 5
KEEP = int(sys.argv[sys.argv.index('--keep') + 1]) if '--keep' in sys.argv else 60
print(f'域内种子 {SEEDS_IN} | 外推种子 {SEEDS_EX} | keep={KEEP}', flush=True)

OUT = {'tasks': {}, 'lso': {}, 'note': '实验V 达标分类：正类=不达标；固定阈值0.5；折叠内选择；KFold5'}


# ---------------- P1 域内：直接分类 vs 回归转阈值 ----------------
print('\n================ P1 域内：直接分类(CLF) vs 回归转阈值(REG→THR) ================', flush=True)
for name, tgt, ok_f, desc in TASKS:
    idx, y = labeled(tgt)
    Xd, ser = Xb[idx], series[idx]
    ybin = (~ok_f(y)).astype(int)          # 1=不达标
    pos = ybin.mean()
    is_reg = tgt in ('T弯', 'MEK擦拭')
    res = {'n': int(len(y)), '不达标率': round(float(pos), 4), 'desc': desc}
    # 直接分类
    pclf = oof_clf(Xd, ybin, ser, KEEP, SEEDS_IN)
    ms = [metrics(ybin, p) for p in pclf]
    res['CLF'] = agg(ms)
    line = (f'  [{name}] n={len(y)} 不达标率={pos:.1%}  CLF: AUC={res["CLF"]["auc"][0]:.4f} '
            f'acc={res["CLF"]["acc"][0]:.4f} 不合格检出={res["CLF"]["rec"][0]:.3f} 误杀={res["CLF"]["mis"][0]:.3f}')
    # 回归转阈值（T弯/MEK）：同一回归管线预测连续值，按业务阈值判定
    if is_reg:
        regs = oof_reg(Xd, y, ser, KEEP, SEEDS_IN)
        thr = 15 if name == 'T15' else 20 if name == 'T20' else 70 if name == 'M70' else 100
        ms = []
        for p in regs:
            pred = (p >= thr).astype(int) if tgt == 'T弯' else (p <= thr).astype(int)
            score = p if tgt == 'T弯' else -p          # 分数越大越可能不达标
            auc = roc_auc_score(ybin, score) if len(set(ybin)) > 1 else float('nan')
            ms.append(dict(auc=float(auc), acc=float(accuracy_score(ybin, pred)),
                           rec=float(recall_score(ybin, pred, zero_division=0)),
                           mis=float(((ybin == 0) & (pred == 1)).mean()),
                           f1=float(f1_score(ybin, pred, zero_division=0))))
        res['REG_THR'] = agg(ms)
        line += (f'  REG→THR: AUC={res["REG_THR"]["auc"][0]:.4f} '
                 f'acc={res["REG_THR"]["acc"][0]:.4f} 不合格检出={res["REG_THR"]["rec"][0]:.3f} 误杀={res["REG_THR"]["mis"][0]:.3f}')
    print(line, flush=True)
    OUT['tasks'][name] = res

# 水煮旧口径对照（同特征管线，仅标签口径不同）
print('\n================ 水煮口径对照：W3(1-2级达标) vs W4(≥4不合格) ================', flush=True)
for name, tgt, bad_f, desc in (W4,):
    idx, y = labeled(tgt)
    Xd, ser = Xb[idx], series[idx]
    ybin = bad_f(y).astype(int)
    pclf = oof_clf(Xd, ybin, ser, KEEP, SEEDS_IN)
    ms = [metrics(ybin, p) for p in pclf]
    a = agg(ms)
    print(f'  [{name}] n={len(y)} 不合格率={ybin.mean():.1%}  CLF AUC={a["auc"][0]:.4f}±{a["auc"][1]:.4f} '
          f'acc={a["acc"][0]:.4f} 不合格检出={a["rec"][0]:.3f} 误杀={a["mis"][0]:.3f}', flush=True)
    OUT['tasks'][name] = {'n': int(len(y)), '不合格率': round(float(ybin.mean()), 4),
                          'desc': desc, 'CLF': a}


# ---------------- P2 LSO 留一系列外推：分类 vs 回归 ----------------
print('\n================ P2 LSO 留一系列外推（n≥12 系列） ================', flush=True)
print(f'  留出系列按任务标签计数（n≥12）', flush=True)
LSO_TASKS = [t for t in TASKS]   # 含 W3
for name, tgt, ok_f, desc in LSO_TASKS:
    idx, y = labeled(tgt)
    Xd, ser = Xb[idx], series[idx]
    ybin = (~ok_f(y)).astype(int)
    is_reg = tgt in ('T弯', 'MEK擦拭')
    ser_cnt = {}
    for s in ser:
        ser_cnt[s] = ser_cnt.get(s, 0) + 1
    big = [s for s, c in sorted(ser_cnt.items()) if c >= 12]
    print(f'  [{name}] 留出系列 {len(big)} 个: {big}', flush=True)
    per = {}
    for hd in big:
        hold = ser == hd
        tr_idx = np.where(~hold)[0]
        te_idx = np.where(hold)[0]
        ytr, yte = ybin[tr_idx], ybin[te_idx]
        if len(set(yte)) < 2:
            auc_te = float('nan')
        # 全训练集选择
        if len(set(ytr)) < 2:
            # 训练集单类：按优势类退化预测（无判别信息）
            pc = np.full(len(te_idx), float(ytr[0]))
            for sd in range(SEEDS_EX):
                pass
        else:
            sel_c = fold_sel(Xd, ybin, tr_idx, KEEP, clf=True)
            pc = np.zeros(len(te_idx))
            for sd in range(SEEDS_EX):
                Xtr, Xte = Xd[tr_idx][:, sel_c], Xd[te_idx][:, sel_c]
                Xtr, Xte = add_series(Xtr, Xte, ytr, ser[tr_idx], ser[te_idx])
                mc, mlc = clf_fit(Xtr, ytr, sd)
                pc += (0.5 * mc.predict_proba(Xte)[:, 1] + 0.5 * mlc.predict_proba(Xte)[:, 1]) / SEEDS_EX
        pred_c = (pc >= 0.5).astype(int)
        rec = dict(n=int(len(te_idx)), acc=round(float(accuracy_score(yte, pred_c)), 4))
        if len(set(yte)) > 1:
            rec['auc'] = round(float(roc_auc_score(yte, pc)), 4)
        if is_reg:
            sel_r = fold_sel(Xd, np.sqrt(y), tr_idx, KEEP)
            pr = np.zeros(len(te_idx))
            for sd in range(SEEDS_EX):
                Xtr, Xte = Xd[tr_idx][:, sel_r], Xd[te_idx][:, sel_r]
                Xtr, Xte = add_series(Xtr, Xte, np.sqrt(y[tr_idx]), ser[tr_idx], ser[te_idx])
                mx, ml = reg_fit(Xtr, np.sqrt(y[tr_idx]), sd)
                pr += np.clip(0.85 * mx.predict(Xte) + 0.15 * ml.predict(Xte), 0, None) ** 2 / SEEDS_EX
            thr = 15 if name == 'T15' else 20 if name == 'T20' else 70 if name == 'M70' else 100
            pred_r = (pr >= thr).astype(int) if tgt == 'T弯' else (pr <= thr).astype(int)
            rec['acc_reg'] = round(float(accuracy_score(yte, pred_r)), 4)
            if len(set(yte)) > 1:
                rec['auc_reg'] = round(float(roc_auc_score(yte, pr if tgt == 'T弯' else -pr)), 4)
        per[hd] = rec
    # 汇总：按样本量加权
    def wavg(key):
        keepv = [(v['n'], v[key]) for v in per.values() if v.get(key) is not None]
        return round(float(np.average([x[1] for x in keepv], weights=[x[0] for x in keepv])), 4) if keepv else None
    agg_l = dict(
        acc_c=wavg('acc'), auc_c=wavg('auc'),
        acc_r=wavg('acc_reg') if is_reg else None, auc_r=wavg('auc_reg') if is_reg else None)
    line = f'  [{name}] 加权 acc(分类)={agg_l["acc_c"]}  AUC(分类)={agg_l["auc_c"]}'
    if is_reg:
        line += f'  | acc(回归)={agg_l["acc_r"]}  AUC(回归)={agg_l["auc_r"]}'
    print(line, flush=True)
    OUT['lso'][name] = dict(per_series=per, weighted=agg_l, held_series=big)

out = os.environ.get('V_OUT', os.path.join(HERE, 'mvp90_result.json'))
json.dump(OUT, open(out, 'w'), ensure_ascii=False, indent=1)
print(f'\n完成，写入 {out}', flush=True)
