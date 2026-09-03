# -*- coding: utf-8 -*-
import pickle, collections
D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
N = 0
cur = None
for s in D['all_samples']:
    if s['体系'] != '环氧-配比方案':
        continue
    tail = s['样本ID'].split('环氧-配比方案-', 1)[1]
    sheet = tail[:tail.rfind('-')]
    if sheet != cur:
        print()
        print('### sheet', sheet)
        cur = sheet
    comp = {repr(k): round(v, 2) for k, v in s['组分'].items() if v > 0}
    print('%-40s %s T=%s W=%s n=%d %s' % (s['样本ID'], s['标签状态'][:4], s['T弯'], s['水煮'], len(comp), ' '.join('%s=%s' % (k, v) for k, v in list(comp.items())[:6])))
    N += 1
print()
print('total', N)