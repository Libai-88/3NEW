"""In-place text edits for the 3NEW repository restructure.

Run after `generalization/*` has been moved to the repository root and the
Phase 1 / web workbench directories have been removed.
"""
from pathlib import Path
import re

FALLBACK = '''def _carryover_from_merged_xlsx():
    """从当前 合并版数据集.xlsx 读取 R8/R9/R10（旧 pkl 不可读时的兜底）。

    R8/R9/R10 是 200℃/10min 批次，原始 5 份文件未含；旧逻辑从 merged_data.pkl
    继承。pkl 由更早版本的 pandas 生成，当前环境无法 unpickle 时，直接读主数据集
    的「配方明细 / 性能结果 / 工艺条件」三张表重建同样结构。
    """
    path = os.path.join(HERE, '..', '合并版数据集.xlsx')
    if not os.path.exists(path):
        return OrderedDict()
    det = pd.read_excel(path, sheet_name='配方明细')
    perf_df = pd.read_excel(path, sheet_name='性能结果')
    proc_df = pd.read_excel(path, sheet_name='工艺条件')
    det['样本ID'] = det['样本ID'].astype(str).str.strip()
    perf_df['样本ID'] = perf_df['样本ID'].astype(str).str.strip()
    proc_df['样本ID'] = proc_df['样本ID'].astype(str).str.strip()
    ids = sorted({sid for sid in det['样本ID'] if re.match(r'^R(8|9|10)-', sid)})
    out = OrderedDict()
    for sid in ids:
        rows = det[det['样本ID'] == sid]
        comp = OrderedDict()
        for _, row in rows.iterrows():
            code = canon(CODE_FIX.get(txt(row.get('原料代码')), txt(row.get('原料代码'))))
            q = num(row.get('用量(g)'))
            if code and q and q > 0:
                comp[code] = round(comp.get(code, 0.0) + float(q), 4)
        if not comp:
            continue
        prow = proc_df[proc_df['样本ID'] == sid]
        bt = num(prow.iloc[0].get('烘烤温度(℃)')) if len(prow) else None
        btm = num(prow.iloc[0].get('烘烤时间(min)')) if len(prow) else None
        s = {'样本ID': sid, '系列': txt(rows.iloc[0].get('系列')), '体系': SYS_EPOXY,
             '组分': comp,
             '工艺': {'烘烤温度': bt or 200, '烘烤时间': btm or 10,
                      '基材': '镀铬铁', '批次': '7.26', '线棒号': '14#', '备注': ''},
             '性能': []}
        cond = f"{s['工艺']['烘烤温度']}℃/{s['工艺']['烘烤时间']}min"
        for _, row in perf_df[perf_df['样本ID'] == sid].iterrows():
            tgt = txt(row.get('目标属性'))
            val = num(row.get('测试值'))
            if not tgt or val is None:
                continue
            s['性能'].append({'目标': tgt, '测试值': float(val),
                              '测试条件': txt(row.get('测试条件')) or cond,
                              '测试日期': '2025-07-26', '备注': '',
                              '标签状态': '实测',
                              '标签来源': txt(row.get('标签来源')) or '实验室'})
        out[sid] = s
    print(f'[回退] 从 合并版数据集.xlsx 读取 R8/R9/R10：{len(out)} 条')
    return out


'''


def read(p):
    return Path(p).read_text(encoding='utf-8')


def write(p, s):
    Path(p).write_text(s, encoding='utf-8')


# 1. report links / code paths
p = 'composition-completion.html'
write(p, read(p).replace('generalization/', ''))

# 2. data_dilemma README
p = 'data_dilemma/README.md'
s = read(p)
s = s.replace(
    '本目录是「3NEW 三新项目研发」第二阶段（`../generalization/`）的**数据困境专项实验**',
    '本目录是「3NEW 三新项目研发」主仓库中的**数据困境专项实验**',
)
s = s.replace('generalization/data_dilemma/', 'data_dilemma/')
s = s.replace('`../workbench/', '`../../workbench/')
s = s.replace('`../合并版数据集.xlsx`', '`../../合并版数据集.xlsx`')
note = ('\n\n> 口径说明：本目录实验基于重录前的 486 样本快照；当前主数据集为 456 样本 / '
        '421 条实测标签，最新主表指标见根 `README.md`。实验结论（瓶颈在测量噪声）不受影响，'
        '但引用绝对 R² 时需区分快照。')
if '口径说明：本目录实验' not in s:
    target = ('本目录是「3NEW 三新项目研发」主仓库中的**数据困境专项实验**：'
              '针对「R²>0.9 目标受数据质量制约」的问题，通过公开数据检索、噪声地板分析'
              '与多路径对照实验，给出突破性能上限的最优方案。')
    s = s.replace(target, target + note)
write(p, s)

# 3. data_dilemma scripts comments
for p in Path('data_dilemma/scripts').glob('*.py'):
    s = read(p)
    s = s.replace('generalization/data_dilemma/scripts/', 'data_dilemma/scripts/')
    write(p, s)

# 4. mvp80 webapp sys.path line
p = 'scripts/mvp80_experiments.py'
s = read(p)
s = '\n'.join(line for line in s.splitlines()
              if 'workbench", \'webapp\'' not in line
              and 'workbench\', \'webapp\'' not in line) + '\n'
write(p, s)

# 5. reingest path, docstring, pandas import, legacy-pkl fallback
p = 'scripts/reingest_template.py'
s = read(p)
s = s.replace("ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))",
              "ROOT = os.path.abspath(os.path.join(HERE, '..'))")
s = s.replace('写入 generalization/终极版数据集模板.xlsx：', '写入 终极版数据集模板.xlsx：')
s = s.replace('import openpyxl\n', 'import openpyxl\nimport pandas as pd\n', 1)
if 'def _carryover_from_merged_xlsx()' not in s:
    s = s.replace('\ndef carryover_series():', '\n' + FALLBACK + 'def carryover_series():', 1)
old = '    D = pickle.load(open(LEGACY_PKL, \'rb\'))\n    out = OrderedDict()'
new = ('    try:\n'
       '        D = pickle.load(open(LEGACY_PKL, \'rb\'))\n'
       '    except Exception as e:\n'
       '        print(f\'[警告] 旧 pkl 不可读（{type(e).__name__}: {e}），'
       '改用合并版数据集读取 R8/R9/R10\')\n'
       '        return _carryover_from_merged_xlsx()\n'
       '    out = OrderedDict()')
if old in s:
    s = s.replace(old, new, 1)
write(p, s)

# 6. TDS-SDS docstring path
p = 'workbench/tds_sds.py'
write(p, read(p).replace('generalization/TDS-SDS/', 'TDS-SDS/'))

# 7. experiment V deliverable paths
p = '达标分类验证实验V.md'
write(p, read(p).replace('generalization/scripts/', 'scripts/'))

# 8. template principle data snapshot
p = '模板工作原理与泛化原理.md'
s = read(p)
s = s.replace('- 486 个配方样品；', '- 456 个配方样品；')
s = s.replace('- 实测有标签 440 / 无标签 46；', '- 实测有标签 421 / 无标签 35；')
s = s.replace('- 三项目标实测数：T弯 354、MEK 335、水煮 218；',
              '- 三项目标实测数：T弯 373、MEK 352、水煮 277；')
s = s.replace('- 80 种原料，77 种描述符已由 TDS/SDS 实测或同族推断锚定（类别典型值的用量加权占比已降到 0）。',
              '- 73 种原料，其中 69 种描述符已由 TDS/SDS 实测或同族推断锚定（仅剩 4 种仍为类别典型值）。')
write(p, s)

# 9. gitignore final form
write('.gitignore', '__pycache__/\n*.pyc\n.uploads/\n.trae-html-share-packages/\n\n_tmp/\n')
print('restructure edits applied')
