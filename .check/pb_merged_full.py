# -*- coding: utf-8 -*-
"""dump merged 环氧-配比方案 样本全组分子典"""
import pickle, re
d = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
out = open('/tmp/pb_merged_dump.txt', 'w')
for s in sorted(d['all_samples'], key=lambda x: x['样本ID']):
    if s.get('体系') != '环氧-配比方案':
        continue
    out.write('### %s\n' % s['样本ID'])
    comp = s.get('组分', {})
    for k in sorted(comp.keys()):
        v = comp[k]
        if isinstance(v, float):
            vs = ('%.6f' % v).rstrip('0').rstrip('.')
        else:
            vs = str(v)
        out.write('   %s = %s\n' % (k, vs))
    out.write('\n')
out.close()
print('done')