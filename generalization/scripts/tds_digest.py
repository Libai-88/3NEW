# -*- coding: utf-8 -*-
"""把 TDS/SDS 档案压缩成「每产品一段」的数值摘要，供人工核定描述符时引用。

用法: python3 tds_digest.py <TDS-SDS目录> [输出文件]
"""
import os, re, sys, glob

KEY = r'(环氧当量|EEW|皂化当量|软化点|滴落|密度|比重|粘度|黏度|固含|不挥发|挥发分|酸值|羟值|羟当量|胺值|碘值|环氧值|氯|水分|闪点|沸点|熔程|熔点|玻璃化|Tg|T_?g|分子式|分子量|式量|CAS|PH值|pH|细度|粒径|比表面|吸油|白度|色相|着色力|有效分|活性物|VOC|挥发速率|蒸汽压|蒸气压|溶解度|灰分|含水|纯度|含量|密度|细度|平均粒径|D50|pH)'

ROW = re.compile(r'^\s*\|(.+)\|\s*$')


def cells(line):
    return [c.strip().strip('*').replace('**', '').replace(',', '').replace('，', '')
            for c in ROW.match(line).group(1).split('|')]


def digest(path):
    txt = open(path, encoding='utf-8', errors='ignore').read().splitlines()
    title = next((l[2:].strip() for l in txt[:6] if l.startswith('#')), os.path.basename(path))
    out = [f'### {os.path.relpath(path, ROOT)}  ||  {title}']
    for l in txt:
        if not ROW.match(l):
            if re.search(r'(化学名|成分|组分|CAS ?No|产品名称|化学品名称)', l) and len(l) < 200:
                out.append('  · ' + l.strip().strip('|').strip())
            continue
        cs = cells(l)
        if not cs or all(not c for c in cs):
            continue
        joined = ' | '.join(c for c in cs if c)
        if re.search(KEY, joined):
            out.append('  ' + joined[:200])
    seen, keep = set(), []
    for l in out:
        if l not in seen or l.startswith('###'):
            seen.add(l)
            keep.append(l)
    return keep


ROOT = sys.argv[1] if len(sys.argv) > 1 else '/workspace/.uploads/tds_sds/TDS-SDS'
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '_tds_digest.txt')
files = sorted(glob.glob(os.path.join(ROOT, '**', '*.md'), recursive=True))
with open(dst, 'w', encoding='utf-8') as f:
    for p in files:
        f.write('\n'.join(digest(p)) + '\n')
print(len(files), 'files ->', dst, os.path.getsize(dst), 'bytes')
