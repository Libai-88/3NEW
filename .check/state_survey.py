# -*- coding: utf-8 -*-
"""merged_data.pkl 现状速览：体系/系列/标签状态/标签字段/组分样例"""
import pickle, collections
import numpy as np

D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
print('pkl keys:', list(D.keys()))
all_samples = D['all_samples']
print('样本总数:', len(all_samples))

by_sys = collections.defaultdict(list)
for s in all_samples:
    by_sys[s['体系']].append(s)
print('体系分布:', {k: len(v) for k, v in by_sys.items()})

for sys_name, lst in by_sys.items():
    lab = sum(1 for s in lst if s['标签状态'] == '实测')
    print(f'-- {sys_name}: {len(lst)} 样本, 实测 {lab}')
    # 系列
    ser = collections.Counter(s.get('系列', '') or '' for s in lst)
    print('   系列:', dict(ser.items()))
    # 标签值统计
    for t in ('T弯', 'MEK', '水煮'):
        vals = [s.get(t) for s in lst if s.get(t) is not None and not (isinstance(s.get(t), float) and np.isnan(s.get(t)))]
        print(f'   {t}: 非空 {len(vals)} 个, 示例 {vals[:6]}')

# 检查标签字段是否还有nan
print()
print('### 样本字段检查（nan统计）')
need_fields = ['样本ID', '系列', '体系', '组分', 'T弯', 'MEK', '水煮', '烘烤温度', '烘烤时间', '标签状态']
for f in need_fields:
    bad = 0
    for s in all_samples:
        v = s.get(f)
        if isinstance(v, float) and np.isnan(v):
            bad += 1
    print(f'  {f}: {len(all_samples)-bad}/{len(all_samples)}')

# 组分键个数分布
print()
print('### 组分键数分布')
ncomp = collections.Counter(len(s['组分']) for s in all_samples)
print(' ', dict(sorted(ncomp.items())))