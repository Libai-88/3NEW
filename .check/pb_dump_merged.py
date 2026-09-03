# -*- coding: utf-8 -*-
"""转储配比方案全部merged样本 组分+标签（含组分键的归一化形态）"""
import pickle, collections, unicodedata, re
D = pickle.load(open('/workspace/generalization/data/merged_data.pkl', 'rb'))
samples = [s for s in D['all_samples'] if s['体系'] == '环氧-配比方案']
samples.sort(key=lambda s: s['样本ID'])


def norm(s):
    return unicodedata.normalize('NFKC', str(s)).replace('\n', '').replace(' ', '')


out = []
for sd in samples:
    out.append('### %s  状态=%s 烘=%s/%s' % (sd['样本ID'], sd.get('标签状态'), sd.get('烘烤温度'), sd.get('烘烤时间')))
    for t in ('T弯', 'MEK', '水煮'):
        v = sd.get(t)
        if v is not None and not (isinstance(v, float) and v != v):
            out.append('   %s=%s' % (t, v))
    comps = collections.defaultdict(float)
    for a, b in sd['组分'].items():
        comps[norm(a)] += b
    for a in sorted(comps):
        out.append('   %-24s %12.6f' % (a, comps[a]))
    out.append('   Σ=%.6f  n=%d' % (sum(comps.values()), len(comps)))
open('/tmp/pb_merged_dump.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('written /tmp/pb_merged_dump.txt, lines:', len(out))