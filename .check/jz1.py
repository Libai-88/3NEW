# -*- coding: utf-8 -*-
import pickle, collections
D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
for s in D['all_samples']:
    if s['体系'] != '聚酯金黄':
        continue
    comp = ', '.join('%s=%g' % (k, v) for k, v in s['组分'].items())
    print('%-24s %-6s T=%-6s M=%-6s W=%-5s | %s' % (
        s['样本ID'], s['标签状态'], s['T弯'], s['MEK'], s['水煮'], comp))
