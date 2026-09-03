# -*- coding: utf-8 -*-
import pickle, collections
import numpy as np

D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
ms = {s['样本ID']: s for s in D['all_samples']}
for sid in ['D2-3', 'D2-4', 'D4-1', 'D5-1', 'D6-1', 'C4-1', 'D7-4', 'D7-21', 'D7-26', 'D7-32', 'D7-1', 'D1-5', 'D3-10', 'R01-01']:
    s = ms[sid]
    print(sid, 'T=', s['T弯'], 'M=', s['MEK'], 'W=', s['水煮'], '| 来源', s['来源'], '| 标签', s['标签状态'])
print()
lab = collections.Counter()
for s in D['all_samples']:
    if s['体系'] != '环氧酚醛':
        continue
    for t in ('T弯', 'MEK', '水煮'):
        v = s[t]
        if v is None:
            lab[(t, 'None')] += 1
        elif isinstance(v, float) and np.isnan(v):
            lab[(t, 'NaN')] += 1
        else:
            lab[(t, 'val')] += 1
print('环氧酚醛 345 条目标覆盖:', dict(lab))
# 非整数值检查（应无 4.333 之类？）
for t in ('T弯', 'MEK', '水煮'):
    vals = [s[t] for s in D['all_samples'] if s['体系'] == '环氧酚醛' and isinstance(s[t], float)]
    frac = [v for v in vals if abs(v - round(v)) > 1e-9]
    print(t, '值带小数(非整数)条数:', len(frac), sorted(set(round(v, 4) for v in frac))[:12])
