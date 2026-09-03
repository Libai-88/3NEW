# -*- coding: utf-8 -*-
"""输出指定样本ID的merged组分明细"""
import pickle, sys
D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
ids = sys.argv[1:]
for s in D['all_samples']:
    if s['样本ID'] in ids:
        print('### %s  体系=%s' % (s['样本ID'], s['体系']))
        for k, v in sorted(s['组分'].items()):
            print('   %-22s %12.6f' % (k, v))
        print('   组分数=%d Σ=%.4f' % (len(s['组分']), sum(s['组分'].values())))