# -*- coding: utf-8 -*-
"""merged_data.pkl 中 环氧-配比方案 样本清单与组分"""
import pickle, collections
D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
samples = [s for s in D['all_samples'] if s['体系'] == '环氧-配比方案']
print('配比方案样本数:', len(samples))
bysheet = collections.defaultdict(list)
for s in samples:
    sid = s['样本ID'].split('环氧-配比方案-', 1)[1]
    sheet = sid.rsplit('-', 1)[0]
    bysheet[sheet].append(sid)
for k in sorted(bysheet):
    print(k, len(bysheet[k]), bysheet[k])
print()
print('keys of sample:', sorted(samples[0].keys()))