import io

path = 'generalization/scripts/reingest_template.py'
src = io.open(path, encoding='utf-8').read()

HELPER = '''def as_date(v):
    """'YYYY-MM-DD' → 日期单元格（避免日期以文本形式存储）。"""
    m = re.match(r'^(\\d{4})-(\\d{2})-(\\d{2})$', txt(v))
    if not m:
        return v or None
    import datetime
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


# 上方占位：as_date 供性能结果「测试日期」写入真日期
'''

LOST_ROW = "    ('用量', '配方明细', '数值', 'g', '该组分在样本中的质量份（原始记录口径）', '66.0'),"

assert HELPER in src, 'helper block not found verbatim'
src = src.replace('\n' + HELPER + '\n', '\n' + LOST_ROW, 1)

anchor = "PERF_HEADERS = ['样本ID', '体系', '目标属性'"
assert anchor in src
src = src.replace(anchor, HELPER.rstrip('\n') + '\n\n\n' + anchor, 1)

io.open(path, 'w', encoding='utf-8').write(src)
print('repaired')
