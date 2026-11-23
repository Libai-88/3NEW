# -*- coding: utf-8 -*-
"""
实验 M：主动学习模拟（Active Learning Simulation）
================================================================
文献依据（research-guide 调研）：
  - CIAL（Chemical Science 2026）：化学信息主动学习，20 个实验样本达 R²>0.8
  - BayBE（Digital Discovery 2025）：贝叶斯实验规划，平均实验次数降低 ≥50%
  - 自监督 GNN（MSDE 2024）：小样本下 RMSE 降低 28.39%

目的：在真实数据（T弯，n=277/18 系列）上诚实模拟「标签获取策略」，
验证不确定性采样 vs 随机采样能否用更少标签达到更高 R²。
评估协议：系列感知留出测试集（20%），测试标签全程不进入训练池；
特征选择与系列编码均在「当前标签池」内完成（折叠内诚实）。
"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.metrics import r2_score
from xgboost import XGBRegressor
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'workbench'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CoatingModelWorkbench import load_dataset, build_sample_features, select_features, fit_series_enc

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '合并版数据集.xlsx')
mat_lib, samples, perf, proc = load_dataset(path)
present_codes = sorted(set(str(c).strip() for s in samples.values() for c in s['组分']))

# ---------- 构建特征矩阵（含烘烤条件） ----------
X, ids, series = [], [], []
for sid, s in samples.items():
    p = proc.get(sid, {})
    row = build_sample_features(s['组分'], mat_lib, present_codes,
                                bake_temp=p.get('烘烤温度'), bake_time=p.get('烘烤时间'))
    if row is None:
        continue
    X.append(row); ids.append(sid); series.append(s.get('系列', ''))
X = np.array(X)

# ---------- 取 T弯 标签 ----------
y_list, idx = [], []
for i, sid in enumerate(ids):
    v = perf.get(sid, {}).get('T弯')
    if v is not None and not (isinstance(v, float) and np.isnan(v)):
        y_list.append(v); idx.append(i)
X = X[idx]; y = np.array(y_list); ser = np.array([series[i] for i in idx])
print(f'T弯: n={len(y)}, 系列数={len(set(ser))}')

# ---------- 系列感知留出测试集（20%） ----------
rng = np.random.RandomState(42)
test_idx = []
for s in set(ser):
    m = np.where(ser == s)[0]
    n_te = max(1, int(round(len(m) * 0.2)))
    test_idx.extend(rng.choice(m, n_te, replace=False))
test_idx = np.array(test_idx)
pool_idx = np.array([i for i in range(len(y)) if i not in set(test_idx)])
print(f'测试集={len(test_idx)}（{len(set(ser[test_idx]))} 系列）, 训练池={len(pool_idx)}')

# ---------- 模型：XGB + 系列编码（折叠内诚实） ----------
K = 3          # 系列编码收缩
N_KEEP = 45    # 特征数
N_SEED = 5     # 集成种子（不确定性估计）
EST = 400
LR = 0.03


def add_series_feats(Xtr_f, Xte_f, y_tr, ser_tr, ser_te, k=K):
    """在标签池上拟合系列编码，应用到训练/测试特征"""
    enc, gm, cnt, std = fit_series_enc(y_tr, ser_tr, k)
    Xtr = np.hstack([Xtr_f, np.array([enc.get(s, gm) for s in ser_tr]).reshape(-1, 1)])
    Xte = np.hstack([Xte_f, np.array([enc.get(s, gm) for s in ser_te]).reshape(-1, 1)])
    Xtr = np.hstack([Xtr, np.array([cnt.get(s, 0) for s in ser_tr]).reshape(-1, 1)])
    Xte = np.hstack([Xte, np.array([cnt.get(s, 0) for s in ser_te]).reshape(-1, 1)])
    Xtr = np.hstack([Xtr, np.array([std.get(s, 0.0) for s in ser_tr]).reshape(-1, 1)])
    Xte = np.hstack([Xte, np.array([std.get(s, 0.0) for s in ser_te]).reshape(-1, 1)])
    return Xtr, Xte


def train_eval_on_pool(lab_idx):
    """在标签池上训练，返回测试集 R² 与池内 OOF 预测（用于不确定性）"""
    Xl = X[lab_idx]; yl = np.sqrt(y[lab_idx]); sl = ser[lab_idx]
    keep = select_features(Xl, yl, N_KEEP)
    Xl_s = Xl[:, keep]
    Xt_s = X[test_idx][:, keep]
    # 系列编码（标签池内拟合）
    Xtr, Xte = add_series_feats(Xl_s, Xt_s, yl, sl, ser[test_idx])
    # 集成训练
    preds = []
    for sd in range(N_SEED):
        m = XGBRegressor(n_estimators=EST, learning_rate=LR, max_depth=3,
                         subsample=0.8, colsample_bytree=0.8, min_child_weight=1,
                         random_state=42 + sd, n_jobs=-1)
        m.fit(Xtr, yl)
        preds.append(m.predict(Xte))
    preds = np.array(preds)  # (n_seed, n_test)
    p_mean = preds.mean(axis=0) ** 2
    r2 = r2_score(y[test_idx], p_mean)
    # 池内 OOF 不确定性（用集成在标签池上的预测 std）
    oof_preds = []
    for sd in range(N_SEED):
        m = XGBRegressor(n_estimators=EST, learning_rate=LR, max_depth=3,
                         subsample=0.8, colsample_bytree=0.8, min_child_weight=1,
                         random_state=42 + sd, n_jobs=-1)
        m.fit(Xtr, yl)
        oof_preds.append(m.predict(Xtr))
    oof_preds = np.array(oof_preds)
    unc = oof_preds.std(axis=0)  # 标签池内不确定性
    return r2, unc, lab_idx


# ---------- 三种采样策略 ----------
def strategy_random(pool, lab_set, budget):
    return rng.choice(list(pool), budget, replace=False)


def strategy_uncertainty(pool, lab_set, budget, unc_map):
    cand = [i for i in pool if i not in lab_set]
    cand = sorted(cand, key=lambda i: unc_map.get(i, 0), reverse=True)
    return np.array(cand[:budget])


def strategy_unc_diversity(pool, lab_set, budget, unc_map):
    cand = [i for i in pool if i not in lab_set]
    # 高不确定 top 50% 内做多样性（与已选样本特征距离最远）
    cand = sorted(cand, key=lambda i: unc_map.get(i, 0), reverse=True)
    hi = cand[:max(budget, len(cand) // 2)]
    if not lab_set:
        return np.array(hi[:budget])
    lab_arr = np.array(list(lab_set))
    Xl = X[lab_arr]
    chosen = []
    for _ in range(budget):
        if not hi:
            break
        # 到已选集合的最小距离最大者
        dists = []
        for c in hi:
            d = np.min(np.linalg.norm(X[c] - Xl, axis=1))
            dists.append(d)
        pick = hi[int(np.argmax(dists))]
        chosen.append(pick)
        hi.remove(pick)
        Xl = np.vstack([Xl, X[pick]])
    return np.array(chosen)


def strategy_strat_random(pool, lab_set, budget):
    """系列分层随机：按系列均匀分配预算，系列内随机"""
    cand = [i for i in pool if i not in lab_set]
    by_ser = {}
    for i in cand:
        by_ser.setdefault(ser[i], []).append(i)
    chosen = []
    # 轮转分配：每轮每个系列最多取 1 个
    while len(chosen) < budget and any(by_ser.values()):
        for s in list(by_ser.keys()):
            if len(chosen) >= budget:
                break
            if by_ser[s]:
                chosen.append(by_ser[s].pop(rng.randint(len(by_ser[s]))))
    return np.array(chosen)


def strategy_strat_unc(pool, lab_set, budget, unc_map):
    """系列分层不确定性：每系列取不确定性最高者，跨系列轮转"""
    cand = [i for i in pool if i not in lab_set]
    by_ser = {}
    for i in cand:
        by_ser.setdefault(ser[i], []).append(i)
    for s in by_ser:
        by_ser[s].sort(key=lambda i: unc_map.get(i, 0), reverse=True)
    chosen = []
    while len(chosen) < budget and any(by_ser.values()):
        for s in list(by_ser.keys()):
            if len(chosen) >= budget:
                break
            if by_ser[s]:
                chosen.append(by_ser[s].pop(0))
    return np.array(chosen)


# ---------- 主循环 ----------
INIT = 20
BATCH = 10
ROUNDS = 15
N_INIT_SEED = 3   # 多初始化种子平均，降低随机性
print(f'\n初始标签={INIT}, 每轮+{BATCH}, 共{ROUNDS}轮（最终 {INIT + BATCH * ROUNDS} 标签）')
print(f'多初始化种子={N_INIT_SEED} 平均')
print(f'{"标签数":>6} | {"随机":>7} | {"不确定性":>8} | {"不确定+多样":>10} | {"分层随机":>8} | {"分层不确定":>9}')
STRATS = ['random', 'unc', 'unc_div', 'strat_random', 'strat_unc']
all_results = {s: np.zeros((N_INIT_SEED, ROUNDS)) for s in STRATS}
for iseed in range(N_INIT_SEED):
    rng = np.random.RandomState(100 + iseed)
    for s in STRATS:
        lab_set = set(rng.choice(pool_idx, INIT, replace=False).tolist())
        for rnd in range(ROUNDS):
            r2, unc, lab_idx = train_eval_on_pool(np.array(sorted(lab_set)))
            all_results[s][iseed, rnd] = r2
            unc_map = {lab_idx[i]: unc[i] for i in range(len(lab_idx))}
            if s == 'random':
                new = strategy_random(pool_idx, lab_set, BATCH)
            elif s == 'unc':
                new = strategy_uncertainty(pool_idx, lab_set, BATCH, unc_map)
            elif s == 'unc_div':
                new = strategy_unc_diversity(pool_idx, lab_set, BATCH, unc_map)
            elif s == 'strat_random':
                new = strategy_strat_random(pool_idx, lab_set, BATCH)
            else:
                new = strategy_strat_unc(pool_idx, lab_set, BATCH, unc_map)
            lab_set.update(new.tolist())

# 汇总打印（均值±标准差）
for rnd in range(ROUNDS):
    n = INIT + BATCH * rnd
    vals = [all_results[s][:, rnd].mean() for s in STRATS]
    print(f'{n:>6} | ' + ' | '.join(f'{v:>7.4f}' for v in vals))

# 关键对比：达到 R²=0.6/0.7 所需标签数（均值口径）
print('\n达到目标 R² 所需标签数（均值口径）:')
for target in [0.5, 0.6]:
    line = f'  R²>={target}: '
    for s in STRATS:
        need = None
        for rnd in range(ROUNDS):
            if all_results[s][:, rnd].mean() >= target:
                need = INIT + BATCH * rnd
                break
        line += f'{s}={"未达" if need is None else need} '
    print(line)

# 最终标签数对比（均值±std）
print('\n最终（170 标签）测试集 R²（均值±std）:')
for s in STRATS:
    m = all_results[s][:, -1].mean()
    sd = all_results[s][:, -1].std()
    print(f'  {s}: {m:.4f} ± {sd:.4f}')
