# -*- coding: utf-8 -*-
"""R8/R9/R10 与各系列来源字段分布"""
import pickle, collections

D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
src = collections.Counter()
for s in D['all_samples']:
    src[(s['体系'], s.get('来源', ''), s['样本ID'][:2])] += 1
for k, v in sorted(src.items()):
    print(k, v)

print()
print('R8/R9/R10 + 各系列首样本 来源:')
for s in D['all_samples']:
    if s['体系'] == '环氧酚醛' and (s['样本ID'].startswith(('R8', 'R9', 'R10')) or s['样本ID'] in ('D1-1', 'C4-1', 'R7-1')) and not s['样本ID'].startswith(('R8','R9','R10')) or (s['体系']=='环氧酚醛' and s['样本ID'] in ('R8-1','R9-1','R10-1','R7-1','R6-1','R5-1','R4-1','R01-1')):
        pass
for s in D['all_samples']:
    sid = s['样本ID']
    if s['体系'] == '环氧酚醛' and sid.split('-')[0] in ('R8','R9','R10','R7','R6','R5','R4','R01','R02','R03') and sid.endswith(('-1','-01','-2','-02')):
        print(sid, '| 来源=', s.get('来源'), '| T弯=', s.get('T弯'), '| MEK=', s.get('MEK'), '| 水煮=', s.get('水煮'))
        if sid.split('-')[0] in ('R8','R9','R10'):
            print('  组分keys:', list(s['组分'].keys())[:3])
            break_loop = True