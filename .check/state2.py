# -*- coding: utf-8 -*-
"""打印指定sheet的merged组分与来源"""
import pickle, collections, sys
D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
samples = [s for s in D['all_samples'] if s['体系'] == '环氧-配比方案']
sheet = sys.argv[1]
for s in samples:
    sid = s['样本ID'].split('环氧-配比方案-', 1)[1]
    if sid.startswith(sheet + '-'):
        print(sid, '| 来源:', s.get('来源'), '| 系列:', s.get('系列'))
        for c, a in sorted(s['组分'].items()):
            print('    %-22s %s' % (c, a))
        print()