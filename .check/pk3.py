# -*- coding: utf-8 -*-
"""merged pkl 全景：体系/系列分布 + R8-xx 样本来源定位"""
import pickle, collections

D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
all_samples = D['all_samples']
print('样本总数:', len(all_samples))
sys_cnt = collections.Counter(s['体系'] for s in all_samples)
print('体系分布:', dict(sys_cnt))
lab = collections.Counter((s['体系'], s.get('标签状态')) for s in all_samples)
print('体系x标签:', dict(lab))

# R8-xx 样本详情
print('\n=== 体系=环氧酚醛 且 ID 含 R8 的样本 ===')
for s in all_samples:
    if s['体系'] == '环氧酚醛' and s['样本ID'].startswith('R8'):
        print(s['样本ID'], '| 系列=', s.get('系列'), '| T弯=', s.get('T弯'), '| MEK=', s.get('MEK'),
              '| 水煮=', s.get('水煮'), '| 标签状态=', s.get('标签状态'), '| 烘烤=', s.get('烘烤温度'))
        print('    组分:', {k: round(v, 4) for k, v in s['组分'].items()})

# 各体系 系列统计
print('\n=== 系列(样本ID前缀)分布 ===')
pref = collections.Counter()
for s in all_samples:
    sid = s['样本ID']
    parts = sid.split('-')
    grp = sid.split(s['体系'] + '-')[1] if (s['体系'] + '-') in sid else sid
    pref[(s['体系'], grp.split('-')[0])] += 1
for k, v in sorted(pref.items()):
    print(k, v)

# 环氧酚醛系列前缀
print('\n=== 环氧酚醛 ID 前缀 ===')
p2 = collections.Counter(s['样本ID'].split('-')[0] for s in all_samples if s['体系'] == '环氧酚醛')
print(dict(p2))

# dump 一个样本完整字段
print('\n=== 样本字段 ===')
s0 = all_samples[0]
for k, v in s0.items():
    print(k, ':', str(v)[:200])