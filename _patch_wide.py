import io

p = '/workspace/generalization/scripts/reingest_template.py'
s = io.open(p, encoding='utf-8').read()
n = 0


def rep(old, new):
    global s, n
    assert old in s, old[:80]
    s = s.replace(old, new, 1)
    n += 1


# ---------------------------------------------------------------- 1) 建模输入改宽表
rep("""    # 建模输入
    ws = wb.create_sheet('建模输入')
    mi_headers = ['样本ID', '系列', '体系', '标签状态', '目标属性', '目标值', '预测值', '不确定性'] + fd_headers[3:]
    ws.append(mi_headers)
    n_mi = 0
    for s in samples.values():
        d = desc.get(s['样本ID'])
        if d is None:
            continue
        have = {}
        for p in s['性能']:                        # 同目标多条记录（不同线棒/批次）取首条（14#线棒）
            if not isinstance(p['测试值'], str):
                have.setdefault(p['目标'], p['测试值'])
        for t in TARGETS:
            v = have.get(t)
            ws.append([s['样本ID'], s['系列'], s['体系'], '实测' if v is not None else '无标签', t,
                       round(float(v), 4) if v is not None else '', '', ''] +
                      [round(x, 6) if isinstance(x, float) else x for x in d.values()])
            n_mi += 1
    style_table(ws, len(mi_headers), n_mi, kpi_cols=[6], status_col=4)
    for i, w in enumerate([16, 12, 12, 10, 12, 10, 10, 10] + [11] * (len(mi_headers) - 8), 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'""",
"""    # 建模输入（宽表：一行 = 一个样本，三个目标的实测/预测/不确定性并列）
    ws = wb.create_sheet('建模输入')
    short = {'T弯': 'T弯', 'MEK擦拭': 'MEK', '水煮等级': '水煮'}
    mi_headers = (['样本ID', '系列', '体系', '标签状态']
                  + [f'{short[t]}实测' for t in TARGETS] + [f'{short[t]}预测' for t in TARGETS]
                  + [f'{short[t]}不确定性' for t in TARGETS] + fd_headers[3:])
    ws.append(mi_headers)
    n_mi = 0
    for s in samples.values():
        d = desc.get(s['样本ID'])
        if d is None:
            continue
        have = {}
        for pr in s['性能']:                       # 同目标多条记录（不同线棒/批次）取首条（14#线棒）
            if not isinstance(pr['测试值'], str):
                have.setdefault(pr['目标'], pr['测试值'])
        ws.append([s['样本ID'], s['系列'], s['体系'], '实测' if have else '无标签']
                  + [round(float(have[t]), 4) if t in have else None for t in TARGETS]
                  + [None] * (len(TARGETS) * 2)  # 预测值/不确定性由工作台回写
                  + [round(x, 6) if isinstance(x, float) else x for x in d.values()])
        n_mi += 1
    style_table(ws, len(mi_headers), n_mi, kpi_cols=[5, 6, 7], status_col=4)
    for i, w in enumerate([16, 12, 12, 10] + [11] * 9 + [11] * (len(mi_headers) - 13), 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'E2'""")

# ---------------------------------------------------------------- 2) 统一数字/文本格式
rep("""    wb.save(out_path)""",
"""    # 统一显示格式：文本列左对齐按文本、计数列整数、数值列最多 6 位小数（不截断有效位）
    FMT = {
        '原料主数据': {1: '@', 2: '@', 3: '@', 4: '@', 5: '@', 6: '@', 7: '@', 40: '@', 41: '@'},
        '配方明细': {1: '@', 2: '@', 3: '@', 4: '@', 6: '@', 7: '@'},
        '性能结果': {1: '@', 2: '@', 3: '@', 5: '@', 6: '@', 7: '@', 9: '@', 10: 'yyyy-mm-dd', 11: '@'},
        '工艺条件': {1: '@', 2: '@', 6: '@', 7: '@', 8: '@', 9: '@'},
        '配方级描述符': {1: '@', 2: '@', 3: '@'},
        '建模输入': {1: '@', 2: '@', 3: '@', 4: '@'},
        '数据字典': {1: '@', 2: '@', 3: '@', 4: '@', 5: '@', 6: '@'},
        '体系配置': {1: '@', 2: '@', 3: '@', 4: '@', 5: '@', 6: '@', 7: '@', 8: '@'},
    }
    INT_COLS = {'配方级描述符': [5], '建模输入': [15]}
    DATE_COLS = {'性能结果': [10]}
    for name, cols in FMT.items():
        sh = wb[name]
        for r in range(2, sh.max_row + 1):
            for c in range(1, sh.max_column + 1):
                cell = sh.cell(r, c)
                if cell.value is None:
                    continue
                if c in cols:
                    cell.number_format = cols[c]
                elif c in INT_COLS.get(name, []):
                    cell.number_format = '0'
                elif c in DATE_COLS.get(name, []):
                    continue
                else:
                    cell.number_format = '0.######'
    wb.save(out_path)""")

# 日期写成真正的日期
rep("""            ws.append([s['样本ID'], s['体系'], p['目标'], round(float(v), 4), UNIT[p['目标']],
                       p['标签状态'], p['标签来源'], '', p['测试条件'], p['测试日期'], p.get('备注', '')])""",
    """            ws.append([s['样本ID'], s['体系'], p['目标'], round(float(v), 4), UNIT[p['目标']],
                       p['标签状态'], p['标签来源'], None, p['测试条件'], as_date(p['测试日期']),
                       p.get('备注') or None])""")
rep("""PERF_HEADERS = ['样本ID'""",
    """def as_date(s):
    \"\"\"YYYY-MM-DD → 日期单元格（避免日期以文本形式存储）。\"\"\"
    m = re.match(r'^(\\d{4})-(\\d{2})-(\\d{2})$', txt(s))
    if not m:
        return s or None
    import datetime
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


PERF_HEADERS = ['样本ID'""")

# 空单元格统一写 None（不再产生空串/空样式单元）
rep("""            row = [code, mat_name(code), systems_of(used.get(code, {'通用'})), d['role'], d['rtype'],
               smi, status]""",
    """            row = [code, mat_name(code), systems_of(used.get(code, {'通用'})), d['role'], d['rtype'],
               smi or None, status]""")
rep("""        row = [code, mat_name(code), systems_of(used.get(code, {'通用'})), d['role'], d['rtype'],
               smi, status]""",
    """        row = [code, mat_name(code), systems_of(used.get(code, {'通用'})), d['role'], d['rtype'],
               smi or None, status]""")
rep("""        for k in CONT_DESC:
            v = num(d.get(k))
            row.append(round(v, 6) if v is not None else '')""",
    """        for k in CONT_DESC:
            v = num(d.get(k))
            row.append(round(v, 6) if v is not None else None)""")
rep("""        note = ''
        if d.get('TDS档案'):""",
    """        note = None
        if d.get('TDS档案'):""")
rep("""        row += [d.get('数据来源', '类别典型值'), note]""",
    """        row += [d.get('数据来源', '类别典型值'), note]""")
rep("""        ws.append([s['样本ID'], s['体系'], p['烘烤温度'], p['烘烤时间'], p.get('膜厚') or '',
                   p.get('基材') or '', p['批次'], p.get('线棒号') or '', p.get('备注') or ''])""",
    """        ws.append([s['样本ID'], s['体系'], p['烘烤温度'], p['烘烤时间'], p.get('膜厚') or None,
                   p.get('基材') or None, p['批次'], p.get('线棒号') or None, p.get('备注') or None])""")

# ---------------------------------------------------------------- 3) 使用说明：取消手工空格换行
rep("""        '3. 8.14配料测试汇总（含测试原始数据）：D1–D7/C4–C6 系列 175 个配方，与 8.6 同一批配方，',
        '   以更晚的 8.14 为准（补齐了 8.6 尚未出结果的水煮等级），T弯取两份记录中更细的写法。',""",
    """        '3. 8.14配料测试汇总（含测试原始数据）：D1–D7/C4–C6 系列 175 个配方，与 8.6 同一批配方，以更晚的 8.14 为准（补齐 8.6 尚未出结果的水煮等级），T弯取两份记录中更细的写法。',""")
rep("""        '2. 用量统一为质量份(g)，按原始记录口径；矩阵表的百分比/1000KG/500克等折算列不另立样本，',
        '   其上的性能记录归入对应配方。',""",
    """        '2. 用量统一为质量份(g)，按原始记录口径；矩阵表的百分比/1000KG/500克等折算列不另立样本，其上的性能记录归入对应配方。',""")
rep("""        '7. 建模输入：宽表，一行 = 一个样本×目标，特征 + 目标值 + 标签状态。',""",
    """        '7. 建模输入：宽表，一行 = 一个样本，三个目标的实测值与特征并列。',""")

# ---------------------------------------------------------------- 4) 数据字典口径同步
rep("""    ('测试值', '性能结果/建模输入', '数值', '-', '性能测试结果数值（原始写法见备注）', '17.415'),""",
    """    ('测试值', '性能结果', '数值', '-', '性能测试结果数值（原始写法见备注）', '17.415'),
    ('T弯/MEK/水煮实测', '建模输入', '数值', '-', '一行=一个样本的三个目标实测值；无实测记为空', '17.415'),
    ('T弯/MEK/水煮预测', '建模输入', '数值', '-', '工作台回写的预测值（录入时为空）', '18.6'),""")
rep("""    ('不确定性', '性能结果/建模输入', '数值', '-', '模型预测的树间标准差（实测记录留空）', '0.42'),""",
    """    ('不确定性', '性能结果/建模输入', '数值', '-', '模型预测的树间标准差（实测记录留空）', '0.42'),
    ('测试日期', '性能结果', '日期', 'yyyy-mm-dd', '该条性能记录的测试日期，按日期格式存储', '2025-08-14'),""")
s = s.replace("""    ('测试日期', '性能结果', '文本', 'YYYY-MM-DD', '该条性能记录的测试日期', '2025-08-14'),\n""", "")

io.open(p, 'w', encoding='utf-8').write(s)
print('patched', n, 'blocks')

# ---------------------------------------------------------------- 5) 同步产出 merged_data.pkl
rep("""def write_workbook(samples, mat, used, out_path, stats):""",
    """PKL = os.path.join(HERE, '..', 'data', 'merged_data.pkl')


def write_payload(samples, mat, used, path):
    \"\"\"输出 data/merged_data.pkl（合并版数据集与实验脚本的中间产物，口径同既有 schema）。\"\"\"
    import pandas as pd
    all_samples, lab, unlab = [], [], []
    for s in samples.values():
        prim = {}
        for pr in s['性能']:
            if not isinstance(pr['测试值'], str):
                prim.setdefault(pr['目标'], pr['测试值'])
        row = {'样本ID': s['样本ID'], '体系': s['体系'], '系列': s['系列'], '组分': dict(s['组分']),
               '烘烤温度': s['工艺']['烘烤温度'], '烘烤时间': s['工艺']['烘烤时间'],
               'T弯': prim.get('T弯'), 'MEK': prim.get('MEK擦拭'), '水煮': prim.get('水煮等级'),
               '标签状态': '实测' if prim else '无标签',
               '来源': f"{s['体系']}·{s['工艺']['批次']}"}
        all_samples.append(row)
        (lab if prim else unlab).append(row)
    desc_rows = [{'样本ID': r['样本ID'], '体系': r['体系']} for r in all_samples]
    D = {'full_mat': mat,
         'new_mats': [c for c in mat if c not in MAT],
         'lab_samples': lab, 'unlab_samples': unlab, 'all_samples': all_samples,
         'desc_df': pd.DataFrame(desc_rows)}
    pickle.dump(D, open(path, 'wb'))
    return len(all_samples), len(lab), len(unlab)


def write_workbook(samples, mat, used, out_path, stats):""")

rep("""    written = write_workbook(samples, mat, used, OUT, stats)
    print('已写出', OUT)
    print('  各表行数:', written)""",
    """    written = write_workbook(samples, mat, used, OUT, stats)
    print('已写出', OUT)
    print('  各表行数:', written)
    ns, nl, nu = write_payload(samples, mat, used, PKL)
    print(f'已写出 {os.path.relpath(PKL, ROOT)}（样本 {ns}，实测 {nl}，无标签 {nu}）')""")

io.open(p, 'w', encoding='utf-8').write(s)
print('patch2 blocks', n)
