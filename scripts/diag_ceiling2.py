# -*- coding: utf-8 -*-
"""噪声地板与理论上限诊断：评估 R²>0.9 的可达性"""
import sys, os, warnings
warnings.filterwarnings('ignore')
import numpy as np
from sklearn.metrics import r2_score
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'workbench'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CoatingModelWorkbench import load_dataset, ENH_FEATURES, explicit_ratios, smi_aggregate, SMI_AGG_KEYS, canon, enhanced_descriptors

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '合并版数据集.xlsx')
mat_lib, samples, perf, proc = load_dataset(path)
present_codes = sorted(set(canon(str(c).strip()) for s in samples.values() for c in s['组分']))

def build_compact(comp, mat_lib, bt=None, btm=None):
    comp = {canon(k): v for k, v in comp.items()}
    row = [float(comp.get(c, 0)) for c in present_codes]
    row.append(float(bt) if bt is not None else 0)
    row.append(float(btm) if btm is not None else 0)
    d = enhanced_descriptors(comp, mat_lib, bake_temp=bt, bake_time=btm)
    if d is None:
        return None
    row += [d.get(f, 0.0) for f in ENH_FEATURES]
    row += explicit_ratios(comp)
    smi = smi_aggregate(comp)
    row += [smi.get(k, 0.0) for k in SMI_AGG_KEYS]
    return row

X, ids, series = [], [], []
for sid, s in samples.items():
    p = proc.get(sid, {})
    row = build_compact(s['组分'], mat_lib, bt=p.get('烘烤温度'), btm=p.get('烘烤时间'))
    if row is None:
        continue
    X.append(row); ids.append(sid); series.append(s.get('系列', ''))
X = np.array(X)

def get_data(tgt):
    y_list, idx = [], []
    for i, sid in enumerate(ids):
        v = perf.get(sid, {}).get(tgt)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            y_list.append(v); idx.append(i)
    if len(y_list) < 30:
        return None
    return X[idx], np.array(y_list), [series[i] for i in idx]

for tgt in ['T弯', 'MEK擦拭', '水煮等级']:
    d = get_data(tgt)
    if d is None:
        print(f'{tgt}: 无数据'); continue
    Xt, yt, sert = d
    print(f'=== {tgt}: n={len(yt)} ===')
    print(f'  mean={yt.mean():.3f} std={yt.std():.3f} min={yt.min():.3f} max={yt.max():.3f}')
    gm = yt.mean()
    ss_total = ((yt-gm)**2).sum()
    ss_series = 0
    for s in set(sert):
        vals = yt[np.array(sert)==s]
        ss_series += len(vals)*((vals.mean()-gm)**2)
    print(f'  系列间方差占比(系列效应): {ss_series/ss_total:.3f}')
    print(f'  系列数: {len(set(sert))}')
    # 同系列内重复样本的噪声估计（若存在）
    # 同组分不同样本的重复测量噪声
    from collections import defaultdict
    comp_map = defaultdict(list)
    for i, sid in enumerate(ids):
        if perf.get(sid, {}).get(tgt) is not None:
            comp_map[tuple(sorted(samples[sid]['组分'].items()))].append(perf[sid][tgt])
    rep = {k: v for k, v in comp_map.items() if len(v) >= 2}
    if rep:
        noise = np.sqrt(np.mean([np.var(v) for v in rep.values()]))
        print(f'  重复组分测量噪声 std: {noise:.3f} (n组={len(rep)})')
        # 噪声地板 R²
        floor = 1 - noise**2 / yt.var()
        print(f'  噪声地板 R² 上限: {floor:.3f}')
