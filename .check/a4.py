# -*- coding: utf-8 -*-
import pickle
D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
for sid in ['环氧-配比方案-25.1.13-1', '环氧-配比方案-25.1.13-2', '环氧-配比方案-25.1.16-6',
            '环氧-配比方案-25.1.17-19', '环氧-配比方案-25.3.12-180KG配方确认-29',
            '环氧-配比方案-25.11.18-62', '环氧-配比方案-25.12.31-103']:
    for s in D['all_samples']:
        if s['样本ID'] == sid:
            print(sid, 'n=', len(s['组分']))
            for k, v in s['组分'].items():
                print('   ', repr(k), round(v, 4))
            break