import pickle, collections, json
import numpy as np

D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
ss = D['all_samples']
print('来源 counts:', collections.Counter(s['来源'] for s in ss))
print()
for src in sorted(set(s['来源'] for s in ss)):
    sub = [s for s in ss if s['来源'] == src]
    print('==', src, len(sub))
    print('  体系:', collections.Counter(s['体系'] for s in sub))
    print('  系列:', collections.Counter(s['系列'] for s in sub))
    print('  标签:', collections.Counter(s['标签状态'] for s in sub))
    print('  first ids:', [s['样本ID'] for s in sub[:6]], '...', [s['样本ID'] for s in sub[-4:]])
    print('  烘烤:', collections.Counter((s['烘烤温度'], s['烘烤时间']) for s in sub))
print()
# check R01-23 dedup behaviour
for sid in ['R01-23', 'R02-16', 'R03-16', 'R4-16', 'R5-06', 'R7-16', 'D1-24', 'D2-24', 'D3-24', 'C4-8', 'C5-16', 'D7-35']:
    m = [s for s in ss if s['样本ID'] == sid]
    for s in m:
        print(sid, s['来源'], 'T=', s['T弯'], 'M=', s['MEK'], 'W=', s['水煮'], 'bake=', s['烘烤温度'], s['烘烤时间'])
