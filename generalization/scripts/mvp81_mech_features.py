# -*- coding: utf-8 -*-
"""
实验 P：机理量特征层 A/B 对照
=============================
在同一诚实评估协议下，比较「基线特征」与「基线 + 配方级机理特征」在三个目标上的表现，
并检验机理特征单独使用的可迁移性、以及 OH 当量口径（登记值 vs 羟值标准换算）。

协议与 mvp74_final_verify.py 一致：
  · 特征选择：XGBoost 重要性 top-N，N 固定为基线取值（不随特征池扩大而放宽）
  · 系列目标编码：折叠内 OOF（T弯 k=8 / MEK k=1 / 水煮 k=3）
  · T弯：sqrt 变换 + 噪声过滤(|OOF 残差| ≤ 2×1.244) + XGB/LGB 加权集成 w=0.85
  · MEK：两阶段（边界判别给出 p_hi 特征 + 未截尾样本回归）
  · 水煮：二值化(等级≥4) + 全局阈值 → 每系列阈值

特征臂
  base            组分用量 + 烘烤 + 增强描述符 + 显式比例 + SMILES 聚合（= 现有生产配置）
  base+mech       上述 + 40 维配方级机理特征
  mech_only       仅机理特征（不含用量列，检验纯机理表达的可迁移性）
  base+mech(ohv)  同 base+mech，但羟基/羧基当量按羟值/酸值标准换算（口径裁决）

用法：
  python3 scripts/mvp81_mech_features.py              # 5 种子 A/B 筛选
  python3 scripts/mvp81_mech_features.py --seeds 20   # 20 种子复验
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

SEEDS = int(sys.argv[sys.argv.index('--seeds') + 1]) if '--seeds' in sys.argv else 5
MEK_CAP = 300
NOISE_STD = 1.244          # T弯重复测量噪声 std（mvp18 估计）
KEEP = dict(t=60, mek=45, mek_clf=75, water=80)

path = os.path.join(HERE, '..', '合并版数据集.xlsx')
mat_lib, samples, perf, proc = load_dataset(path)
present_codes = sorted(set(canon(str(c).strip()) for s in samples.values() for c in s['组分']))
IDS = sorted(samples.keys())


def build_base(sid):
    """现有生产配置的特征行（与 mvp74 的 build_compact 完全一致）。"""
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
    return row


def build_mech(sid, oh_source='rec'):
    p = proc.get(sid, {})
    d, _ = mech_features(samples[sid]['组分'], mat_lib, p.get('烘烤温度'),
                         p.get('烘烤时间'), oh_source=oh_source)
    if d is None:
        return [0.0] * len(MECH_FEATURES)
    return [float(d.get(f, 0.0)) for f in MECH_FEATURES]


# ---------- 特征矩阵 ----------
Xb, Xm, Xmo, series, fams = [], [], [], [], []
for sid in IDS:
    b = build_base(sid)
    if b is None:
        continue
    Xb.append(b)
    Xm.append(build_mech(sid, 'rec'))
    Xmo.append(build_mech(sid, 'ohv'))
    series.append(samples[sid].get('系列', ''))
    fams.append(samples[sid].get('体系', ''))
Xb, Xm, Xmo = np.array(Xb), np.array(Xm), np.array(Xmo)
series = np.array(series, dtype=object)
fams = np.array(fams, dtype=object)
ROW_OF = {sid: i for i, sid in enumerate(IDS)}
print(f'特征矩阵: base {Xb.shape} | mech {Xm.shape} | 种子数 {SEEDS}', flush=True)

ARMS = {
    'base': Xb,
    'base+mech': np.hstack([Xb, Xm]),
    'mech_only': Xm,
    'base+mech(ohv)': np.hstack([Xb, Xmo]),
}


def labeled(tgt):
    """返回该目标的 (行索引数组, y)。跳过缺失/NaN 标签。"""
    idx, y = [], []
    for sid, v in ((s, perf.get(s, {}).get(tgt)) for s in IDS):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        y.append(v)
        idx.append(ROW_OF[sid])
    return np.array(idx), np.array(y, dtype=float)


def add_series(Xtr, Xte, y_tr, ser_tr, ser_te, k=3):
    """折叠内 OOF 系列编码：目标编码 + 计数 + 组内 std + 系列 one-hot。"""
    gm = y_tr.mean()
    enc, cnt, std = {}, {}, {}
    for s in set(ser_tr):
        vals = y_tr[ser_tr == s]
        n = len(vals)
        cnt[s] = n
        std[s] = float(vals.std()) if n > 1 else 0.0
        enc[s] = (n * vals.mean() + k * gm) / (n + k)
    extra = []
    for d, dv in ((enc, gm), (cnt, 0), (std, 0)):
        extra.append(np.array([d.get(s, dv) for s in ser_tr]).reshape(-1, 1))
        extra.append(np.array([d.get(s, dv) for s in ser_te]).reshape(-1, 1))
    Xtr = np.hstack([Xtr] + extra[0::2])
    Xte = np.hstack([Xte] + extra[1::2])
    for s in sorted(set(ser_tr)):
        Xtr = np.hstack([Xtr, (ser_tr == s).astype(float).reshape(-1, 1)])
        Xte = np.hstack([Xte, (ser_te == s).astype(float).reshape(-1, 1)])
    return Xtr, Xte


def get_imp(X, y, clf=False):
    if clf:
        m = XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8,
                          colsample_bytree=0.8, random_state=42, n_jobs=-1)
    else:
        m = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.8,
                         colsample_bytree=0.8, random_state=42, n_jobs=-1)
    m.fit(X, y)
    return m.feature_importances_


def select(X, y, n, clf=False):
    return X[:, np.argsort(get_imp(X, y, clf))[-n:]]


def cv_reg(Xs, y_orig, ser, k, est=1000, trans=None, inv=None, w=0.85,
           return_oof=False, extra_feat=None):
    yt = trans(y_orig) if trans is not None else y_orig
    r2s = []
    oof = np.zeros(len(y_orig))
    for tr, te in KFold(5, shuffle=True, random_state=42).split(Xs):
        Xtr, Xte = add_series(Xs[tr], Xs[te], yt[tr], ser[tr], ser[te], k)
        if extra_feat is not None:
            Xtr = np.hstack([Xtr, extra_feat[tr].reshape(-1, 1)])
            Xte = np.hstack([Xte, extra_feat[te].reshape(-1, 1)])
        px, pl = [], []
        for sd in range(SEEDS):
            mx = XGBRegressor(n_estimators=est, learning_rate=0.015, max_depth=3, subsample=0.7,
                              colsample_bytree=0.8, min_child_weight=1,
                              random_state=42 + sd, n_jobs=-1)
            mx.fit(Xtr, yt[tr]); px.append(mx.predict(Xte))
            ml = LGBMRegressor(n_estimators=est, learning_rate=0.015, num_leaves=15, max_depth=3,
                               subsample=0.7, colsample_bytree=0.8, min_child_samples=10,
                               random_state=42 + sd, n_jobs=-1, verbose=-1)
            ml.fit(Xtr, yt[tr]); pl.append(ml.predict(Xte))
        pred = w * np.mean(px, axis=0) + (1 - w) * np.mean(pl, axis=0)
        if inv is not None:
            pred = inv(pred)
        oof[te] = pred
        r2s.append(r2_score(y_orig[te], pred))
    return (float(np.mean(r2s)), oof) if return_oof else float(np.mean(r2s))


def clf_oof(Xs, yb, ser, k=3, est=400):
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
    return oof


def best_threshold(y2, p, lo=0.35, hi=0.66):
    best = (0.0, 0.5)
    for th in np.arange(lo, hi, 0.005):
        a = accuracy_score(y2, (p >= th).astype(int))
        if a > best[0]:
            best = (float(a), float(th))
    return best


def by_fam(fam_mask_arr, correct):
    """按体系拆分给出命中率；聚酯金黄的水煮标签全部为同一等级，其命中不具判别意义。"""
    out = {}
    for f in sorted(set(fam_mask_arr)):
        m = fam_mask_arr == f
        if m.sum():
            out[f] = dict(n=int(m.sum()), acc=round(float(correct[m].mean()), 4))
    return out


def by_fam_reg(fam_arr, y_true, y_pred):
    """按体系拆分的 R²/MAE；小样本体系的 R² 仅作提示，不作达标依据。"""
    out = {}
    for f in sorted(set(fam_arr)):
        m = fam_arr == f
        if m.sum() < 5:
            continue
        out[f] = dict(n=int(m.sum()),
                      r2=round(float(r2_score(y_true[m], y_pred[m])), 4) if m.sum() > 1 else None,
                      mae=round(float(np.mean(np.abs(y_true[m] - y_pred[m]))), 4))
    return out


R = {}

# ================= T弯 =================
print('\n========== T弯 (sqrt + 噪声过滤, keep=60 k=8 w=0.85) ==========', flush=True)
idx, y = labeled('T弯')
fam_t = fams[idx]
T = {}
for arm, X in ARMS.items():
    Xd, s = X[idx], series[idx]
    r2_full, oof = cv_reg(select(Xd, np.sqrt(y), KEEP['t']), y, s, 8, return_oof=True)
    mask = np.abs(y - oof) <= 2.0 * NOISE_STD
    r2_f, oof_f = cv_reg(select(Xd[mask], np.sqrt(y[mask]), KEEP['t']), y[mask], s[mask], 8,
                         return_oof=True)
    T[arm] = dict(n=int(len(y)), n_kept=int(mask.sum()), r2_full=r2_full, r2_filtered=r2_f,
                  by_fam=by_fam_reg(fam_t[mask], y[mask], oof_f))
    print(f'  {arm:16s} R²(全量)={r2_full:.4f}  R²(过滤后)={r2_f:.4f}  n={len(y)}→{mask.sum()}  '
          f'分体系={T[arm]["by_fam"]}', flush=True)
R['T弯'] = T

# ================= MEK =================
print('\n========== MEK (p_hi 边界特征 + 未截尾回归, keep=45 k=1) ==========', flush=True)
idx, y = labeled('MEK擦拭')
fam_m = fams[idx]
M = {}
for arm, X in ARMS.items():
    Xd, s = X[idx], series[idx]
    ybin = (y >= MEK_CAP).astype(int)
    unc = np.where(y != MEK_CAP)[0]
    p_hi = clf_oof(select(Xd, ybin, KEEP['mek_clf'], clf=True), ybin, s, k=3)
    r2, oof_u = cv_reg(select(Xd[unc], np.sqrt(y[unc]), KEEP['mek']), y[unc], s[unc], 1,
                       est=1500, trans=np.sqrt, inv=lambda p: p ** 2, extra_feat=p_hi[unc],
                       return_oof=True)
    M[arm] = dict(n=int(len(y)), n_uncensored=int(len(unc)), r2=r2,
                  bnd_acc=float(accuracy_score(ybin, (p_hi >= 0.5).astype(int))),
                  bnd_auc=float(roc_auc_score(ybin, p_hi)),
                  by_fam=by_fam_reg(fam_m[unc], y[unc], oof_u))
    print(f'  {arm:16s} 未截尾R²={r2:.4f} (n={len(unc)})  边界acc={M[arm]["bnd_acc"]:.4f} '
          f'AUC={M[arm]["bnd_auc"]:.4f}  分体系={M[arm]["by_fam"]}', flush=True)
R['MEK'] = M

# ================= 水煮 =================
print('\n========== 水煮 (二值≥4 + 每系列阈值, keep=80) ==========', flush=True)
idx, y = labeled('水煮等级')
fam_w = fams[idx]
W = {}
for arm, X in ARMS.items():
    Xd, s = X[idx], series[idx]
    y2 = (y.astype(int) >= 4).astype(int)
    oof = clf_oof(select(Xd, y2, KEEP['water'], clf=True), y2, s, k=3)
    g_acc, g_th = best_threshold(y2, oof)
    pred = np.zeros(len(y2))
    for u in set(s):
        m = s == u
        th = best_threshold(y2[m], oof[m])[1] if m.sum() >= 8 else g_th
        pred[m] = (oof[m] >= th).astype(int)
    ok = (pred == y2).astype(float)
    W[arm] = dict(n=int(len(y2)), pos_rate=float(y2.mean()), acc_global=g_acc,
                  acc_per_series=float(accuracy_score(y2, pred)),
                  auc=float(roc_auc_score(y2, oof)), by_fam=by_fam(fam_w, ok))
    ep = W[arm]['by_fam'].get('环氧酚醛', {}).get('acc', float('nan'))
    print(f'  {arm:16s} 全局acc={g_acc:.4f} 每系列acc={W[arm]["acc_per_series"]:.4f} '
          f'AUC={W[arm]["auc"]:.4f} | 仅环氧酚醛 acc={ep:.4f} '
          f'(n={W[arm]["by_fam"]["环氧酚醛"]["n"]})', flush=True)
R['水煮'] = W

# ================= 机理特征入选情况 =================
print('\n========== 机理特征在 base+mech 中的入选情况 ==========', flush=True)
sel = {}
Xbm = np.hstack([Xb, Xm])
NB = Xb.shape[1]
for tgt, key, n, use_clf in [('T弯', 't', KEEP['t'], False), ('MEK擦拭', 'mek', KEEP['mek'], False),
                             ('水煮等级', 'water', KEEP['water'], True)]:
    i2, y2 = labeled(tgt)
    if key == 'mek':
        u = np.where(y2 != MEK_CAP)[0]
        i2, y2 = i2[u], y2[u]
    if use_clf:
        yy = (y2.astype(int) >= 4).astype(int)
    else:
        yy = np.sqrt(y2)
    imp = get_imp(Xbm[i2], yy, clf=use_clf)
    keep = np.argsort(imp)[-n:]
    hits = [(float(imp[j]), MECH_FEATURES[j - NB]) for j in keep if j >= NB]
    hits.sort(reverse=True)
    sel[key] = dict(n_selected=len(hits), hits=[nm for _v, nm in hits],
                    top_by_importance=[nm for _v, nm in hits][:10])
    print(f'  {tgt}: 机理列入选 {len(hits)}/{n} | 重要性靠前: {sel[key]["top_by_importance"]}', flush=True)
R['mech_selected'] = sel

# 机理特征单变量相关性（对三目标 Spearman）
from scipy.stats import spearmanr
corr = {}
for tgt, key in [('T弯', 't'), ('MEK擦拭', 'mek'), ('水煮等级', 'water')]:
    i2, y2 = labeled(tgt)
    if key == 'mek':
        u = np.where(y2 != MEK_CAP)[0]
        i2, y2 = i2[u], y2[u]
    if key == 'water':
        y2 = (y2.astype(int) >= 4).astype(int)
    cs = []
    for j, f in enumerate(MECH_FEATURES):
        v = Xm[i2, j]
        if v.std() < 1e-12:
            continue
        rho = spearmanr(v, y2).statistic
        cs.append((abs(rho), f, float(rho)))
    cs.sort(reverse=True)
    corr[key] = [(f, round(r, 3)) for _a, f, r in cs[:8]]
    print(f'  |Spearman| top {tgt}: {corr[key][:6]}', flush=True)
R['mech_spearman'] = corr

out = os.environ.get('MECH_OUT', os.path.join(HERE, 'mvp81_result.json'))
json.dump(dict(seeds=SEEDS, n_base=int(Xb.shape[1]), n_mech=int(Xm.shape[1]), results=R),
          open(out, 'w'), ensure_ascii=False, indent=1)
print(f'\n完成，结果写入 {out}', flush=True)
