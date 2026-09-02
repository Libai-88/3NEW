# -*- coding: utf-8 -*-
"""按原料代码查看对应 TDS/SDS 档案中的高信号数值行（人工核定描述符时用）。

用法: python3 tds_view.py <档案关键字1> [关键字2 ...]
关键字匹配档案相对路径（不区分大小写）。
"""
import sys, re, os

SIG = re.compile(r'(固含|固成份|固体含量|不挥发|挥发分|非挥发|有效成分|活性含量|环氧当量|EEW|环氧值|皂化|羟值|OH价|OH含量|羟基|酸值|酸价|胺值|NCO|异氰酸酯|比重|密度|粘度|黏度|闪点|沸点|熔程|熔点|软化点|玻璃化|Tg|分子量|式量|Mn|CAS|含量|组分|成分|细度|粒径|D50|吸油|DBP|比表面|白度|色|pH|水分|VOC|纯度|元素|分子式|甲醛|中和度|当量)')
NOISE = re.compile(r'(LD50|LC50|TWA|STEL|MAC|防护|急救|灭火|泄漏|储存|废弃|运输|分类|标签|说明|措施|禁配|稳|生态|降解|目录|列入|接触|吸入|经皮|经口|皮肤|眼睛|操作|处置)')


def show(path, root):
    lines = open(path, encoding='utf-8', errors='ignore').read().splitlines()
    title = next((l[2:].strip() for l in lines[:6] if l.startswith('#')), os.path.basename(path))
    print('=== ' + os.path.relpath(path, root) + '  ||  ' + title)
    seen = 0
    for l in lines:
        t = l.strip()
        if not t or t.startswith('---'):
            continue
        if len(t) > 170:
            continue
        if SIG.search(t) and not NOISE.search(t):
            print('   ' + t[:170])
            seen += 1
            if seen > 34:
                print('   ...')
                break


root = '/workspace/.uploads/tds_sds/TDS-SDS'
import glob
files = sorted(glob.glob(os.path.join(root, '**', '*.md'), recursive=True))
for pat in sys.argv[1:]:
    hit = [f for f in files if pat.lower() in os.path.relpath(f, root).lower()]
    for f in hit:
        show(f, root)
    if not hit:
        print(f'!!! 无匹配档案: {pat}')
