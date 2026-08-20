# -*- coding: utf-8 -*-
"""可复用的涂料性能预测接口（v3：MEK stacking / T弯门控混合 / 水煮RF）。
对齐体系：champion_models_v3.pkl，33 维交互特征（build3.py Xo_b/Xn_b 格式）。

用法:
    import predict as pp
    res = pp.predict_performance(
        IR190=66, RF401=0, RF160=0, IR809=0, RF516=0, RF950=0, RF956=0,
        RH601=0, S55754=0, W1510=2.1, AZ088=0, PR411=0, TF022=0,
        nBtOH=5.5, Mix=0, PA=1.2, bake_temp=200, bake_min=10)
    # PA 为 85% 磷酸用量
"""
import os, pickle
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = ['IR190','RF401','RF160','IR809','RF516','RF950','RF956',
          'RH601','S55754','W1510','AZ088','PR411','TF022','nBtOH','Mix']

def _load():
    with open(os.path.join(_HERE, '..', 'models', 'champion_models_v3.pkl'), 'rb') as fh:
        return pickle.load(fh)

def _feat(comp, temp, minute):
    """构建 33 维特征（15原始 + 4化学先验 + 10交互 + 4烘烤）。
    与 build3.py 中 feats(..., use_inter=True) 保持一致。"""
    A = np.array([float(comp.get(c, 0.0)) for c in COMMON])
    paeff = float(comp.get('PA', 0.0)) * 0.85
    ep = A[COMMON.index('IR190')]; epeff = ep * 0.36
    tot = A.sum() + paeff
    radd = tot - ep
    acid_ep = paeff / max(epeff, 1e-9)
    chem = np.array([paeff / max(tot, 1e-9), epeff, radd / max(tot, 1e-9), acid_ep])
    # 交互特征：RF160, RF516, RF950, RF956, RH601 两两乘积 / tot
    inter_names = ['RF160','RF516','RF950','RF956','RH601']
    inter_vals = []
    for i in range(len(inter_names)):
        for j in range(i+1, len(inter_names)):
            inter_vals.append(A[COMMON.index(inter_names[i])] * A[COMMON.index(inter_names[j])] / max(tot, 1e-9))
    bake = np.array([float(temp), float(minute), float(temp) * float(minute), np.sqrt(float(minute))])
    return np.concatenate([A, chem, np.array(inter_vals), bake])

def predict_performance(bake_temp=200, bake_min=10, **comps):
    m = _load()
    x = _feat(comps, bake_temp, bake_min)[m['feat_keep']].reshape(1, -1)
    # T弯: gating weighted ensemble
    bases=m['T_bases']; w=m['T_weights']
    preds=np.array([bases[k].predict(x)[0] for k in m['meta']['T_bases']])
    t = float((preds*w).sum())
    # MEK: stacking (5 base -> Ridge meta)
    bases=m['MEK_bases']; meta=m['MEK_meta']
    P=np.column_stack([bases[k].predict(x) for k in m['meta']['MEK_bases']])
    mek_log = float(meta.predict(P)[0])
    mek = int(round(float(np.expm1(mek_log))))
    # 水煮: RF classifier + regressor
    wb = int(m['WB_RF'].predict(x)[0])
    classes = np.asarray(m['WB_RF'].classes_)
    prob = m['WB_RF'].predict_proba(x)[0]
    off1 = float(np.sum(prob[np.abs(classes.astype(int) - wb) <= 1]))
    probs = {int(c): round(float(p), 4) for c, p in zip(classes, prob)}
    wbreg = int(round(float(np.clip(m['WB_reg'].predict(x)[0], 1, 5))))
    return {'T弯': round(t, 2), 'MEK': max(mek, 0),
            '水煮等级': wb, '水煮±1级概率': round(off1, 3),
            '水煮等级(回归取整)': wbreg, '水煮各等级概率': probs}

if __name__ == '__main__':
    # 复现新批第 1 条（200℃/10min）
    print(predict_performance(IR190=62.0, RF401=0, RF160=0, IR809=0, RF516=0,
                              RF950=0, RF956=0, RH601=0, S55754=0, W1510=0,
                              AZ088=0, PR411=0, TF022=0, nBtOH=0, Mix=0, PA=0,
                              bake_temp=200, bake_min=10))