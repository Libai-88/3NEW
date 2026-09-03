# -*- coding: utf-8 -*-
"""列出配比方案 workbook 全部 sheet，以及merged中每个sheet的样本ID"""
import pickle, collections, openpyxl
F = "/workspace/.uploads/b36f4809-d40f-491a-b9d7-2a9c4e359b1b_fbfc94091fa4955969e5d0fff7df0fd6_789507228604997242_m_3NX240913-6C--AI研发26.7.22配比方案.xlsx"
wb = openpyxl.load_workbook(F, data_only=True)
D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
samples = [s for s in D['all_samples'] if s['体系'] == '环氧-配比方案']
merged_keys = collections.defaultdict(list)
for s in samples:
    tail = s['样本ID'].split('环氧-配比方案-', 1)[1]
    merged_keys[tail].append(s['样本ID'])
print('sheet 数:', len(wb.sheetnames))
print('merged 样本数:', len(samples))
flat = sorted(merged_keys.items())
print('--- merged 按尾号分组:')
for k, v in flat:
    print('  %-28s %s' % (k[:28], len(v)))
# 检查 merged 中是否有不在 workbook sheet 前缀中的
sheetnames = wb.sheetnames
print()
print('--- workbook sheets:')
for i, n in enumerate(sheetnames):
    print('  %2d %r' % (i, n))