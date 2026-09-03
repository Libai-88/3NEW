# -*- coding: utf-8 -*-
"""聚焦查看指定sheet的原始网格（浓缩格式），用于设计权威解析器"""
import sys, openpyxl

FA = '/workspace/.uploads/b36f4809-d40f-491a-b9d7-2a9c4e359b1b_fbfc94091fa4955969e5d0fff7df0fd6_789507228604997242_m_3NX240913-6C--AI研发26.7.22配比方案.xlsx'
wb = openpyxl.load_workbook(FA, data_only=True)


def fmt(v, w=8):
    if v is None:
        return ''
    if isinstance(v, float):
        if v != v:
            return ''
        if abs(v - round(v)) < 1e-9:
            return '%d' % round(v)
        return '%.2f' % v
    s = str(v).strip().replace('\n', '\\n')
    if len(s) > w:
        s = s[:w - 1] + '~'
    return s


for name in sys.argv[1:]:
    if name not in wb.sheetnames:
        print('MISSING:', name)
        continue
    ws = wb[name]
    print('=' * 110)
    print('SHEET %s  max_row=%d max_col=%d' % (ws.title, ws.max_row, ws.max_column))
    # 逐行打印所有非空单元格（不超过列18）
    for r in range(1, ws.max_row + 1):
        cells = []
        for c in range(1, min(ws.max_column, 18) + 1):
            v = ws.cell(r, c).value
            if v is None or (isinstance(v, float) and v != v):
                continue
            cells.append('c%d=%s' % (c, fmt(v)))
        if cells:
            print('r%02d: %s' % (r, ' | '.join(cells)))