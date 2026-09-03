import pickle, os, json, collections
import numpy as np, pandas as pd

P = '/workspace/generalization/data/merged_data.pkl'
D = pickle.load(open(P, 'rb'))
print('keys:', list(D.keys()))
ss = D['all_samples']
print('n_samples:', len(ss))
print('sample keys:', sorted(ss[0].keys()))
print('体系 counts:', collections.Counter(s['体系'] for s in ss))
print('标签状态 counts:', collections.Counter(s['标签状态'] for s in ss))
print('系列 counts (top40):', collections.Counter(s['系列'] for s in ss).most_common(60))
print('n 系列:', len(set(s['系列'] for s in ss)))
for tgt in ['T弯', 'MEK', '水煮']:
    print(tgt, 'non-null:', sum(1 for s in ss if s.get(tgt) is not None and not (isinstance(s.get(tgt), float) and np.isnan(s.get(tgt)))))
print('--- first 3 samples ---')
for s in ss[:3]:
    print(json.dumps(s, ensure_ascii=False, default=str))
print('--- full_mat ---')
print('n materials:', len(D['full_mat']))
print('new_mats:', len(D['new_mats']))
print('other keys types:', {k: type(v).__name__ for k, v in D.items()})
