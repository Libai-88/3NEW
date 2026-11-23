# -*- coding: utf-8 -*-
"""
扩充 SMILES 分子描述符覆盖
==========================
`workbench/smi_desc.py` 预存了 31 种原料的 RDKit 描述符；库内还有若干**结构明确的
小分子**（溶剂、载体、单体、无机酸）没有登记，导致这些原料的分子描述符通道恒为 0。

本脚本只为「结构唯一确定的纯化合物」补充 SMILES 并计算描述符，与既有 41 维键完全一致：
  · 不处理石油馏分（100号/150号溶剂、石脑油）—— 组分不确定，无法用单一 SMILES 表示
  · 不处理聚合物/低聚物（环氧、聚酯、丙烯酸、CAB、蜡）—— 需 TDS 或结构表征，属后续工作
  · 混合物（DBE、补加混合液）取其代表性组分或已有登记项，不重复登记

用法（幂等，可重复运行）：
  PYTHONPATH=/data/user/work python3 scripts/extend_smiles.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WB = os.path.abspath(os.path.join(HERE, '..', 'workbench'))
sys.path.insert(0, WB)

from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors
RDLogger.DisableLog('rdApp.*')
from smi_desc import CODE_DESC, SMI_KEYS

# code -> (中文名, SMILES) ；SMILES 为唯一确定的结构式
NEW_SMILES = {
    '二甲苯':   ('二甲苯（间位异构体代表）', 'Cc1cccc(C)c1'),
    'TZ161':    ('丙二醇甲醚醋酸酯 PMA', 'CC(=O)OCC(C)OC'),
    'TZ240':    ('醋酸丁酯', 'CCCCOC(C)=O'),
    'TT066':    ('环己酮', 'O=C1CCCCC1'),
    'TM982':    ('丙二醇甲醚 PM', 'COCC(C)O'),
    'TM024':    ('二乙二醇单丁醚', 'CCCCOCCCO'),
    'TM221':    ('乙二醇单丁醚', 'CCCCOCCO'),
    'TZ221':    ('乙二醇单丁醚（重复登记）', 'CCCCOCCO'),
    'MIBK':     ('甲基异丁基甲酮', 'CC(C)CC(C)=O'),
    'DPM':      ('二丙二醇甲醚', 'COC(C)COCC(C)O'),
    '10%磷酸':  ('磷酸（水溶液，按溶质计）', 'OP(=O)(O)O'),
    'AZ135':    ('（乙酰乙酸乙酯基）二异丙氧基铝酸酯', 'CC(C)O[Al](OC(C)C)(OC(=O)CC(C)=O)C'),
    '正丁醇':   ('正丁醇', 'CCCCO'),
}

# 与既有表一致：整数描述符转 float；无法计算的键记 NaN（写回时用 float("nan") 字面量）
def _lit(v):
    return 'float("nan")' if v != v else repr(v)


def compute(smi):
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        raise ValueError(f'SMILES 解析失败: {smi}')
    out = {}
    for key in SMI_KEYS:
        name = key[len('rdkit_'):]
        fn = getattr(Descriptors, name, None)
        if fn is None:
            out[key] = float('nan')
            continue
        try:
            v = fn(mol)
        except Exception:
            v = float('nan')
        out[key] = float(v) if isinstance(v, (int, float)) else float('nan')
    return out


def main():
    added = []
    for code, (label, smi) in NEW_SMILES.items():
        if code in CODE_DESC:
            continue
        CODE_DESC[code] = compute(smi)
        added.append(code)
    print(f'新增 {len(added)} 种原料的分子描述符: {added}')
    print(f'覆盖总数: {len(CODE_DESC)}（原 31）')

    # 写回：在文件末尾以 update 形式追加，保持既有行不变、diff 最小
    targets = [os.path.join(WB, 'smi_desc.py'), os.path.join(HERE, 'smi_desc.py')]
    block = ['', '# ---- 由 scripts/extend_smiles.py 追加：结构明确的小分子（RDKit 计算）----',
             'CODE_DESC.update({']
    for code in added:
        rows = ', '.join(f'{k!r}: {_lit(CODE_DESC[code][k])}' for k in SMI_KEYS)
        block.append(f'    {code!r}: {{{rows}}},')
    block.append('})')
    tail = '\n'.join(block) + '\n'
    for p in targets:
        if not os.path.exists(p):
            continue
        src = open(p, encoding='utf-8').read()
        if 'extend_smiles.py 追加' in src:
            print(f'跳过（已追加过）: {p}')
            continue
        open(p, 'w', encoding='utf-8').write(src + tail)
        print(f'已写入 {p}')


if __name__ == '__main__':
    main()
