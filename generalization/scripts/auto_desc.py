# -*- coding: utf-8 -*-
"""
自动分子描述符计算模块 (Auto Molecular Descriptor Module)
==========================================================
将原料的 SMILES 结构式自动转换为分子描述符，替代人工录入描述符，
减少人工操作引入的误差变量，实现"统计人员友好、自动化、规范化"。

三级描述符体系：
  1) RDKit 2D 描述符   (~210 维，理化性质)
  2) Mordred 2D 描述符 (~1613 维，结构拓扑)
  3) Morgan 指纹       (2048 bit，子结构环境)

用法：
  from auto_desc import compute_mol_descriptors, FORMULA_AGG
  d = compute_mol_descriptors('CCO')            # 单分子
  agg = FORMULA_AGG.aggregate([(smiles, frac), ...])  # 配方级聚合
"""
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors, rdFingerprintGenerator
from mordred import Calculator, descriptors as mordred_descriptors

# ---------- 常量 ----------
MORGAN_RADIUS = 2
MORGAN_BITS = 2048

# 预编译：Mordred 2D 计算器（1613 维）
_MORD_CALC = Calculator(mordred_descriptors, ignore_3D=True)

# 预编译：Morgan 指纹生成器
_MFP_GEN = rdFingerprintGenerator.GetMorganGenerator(
    radius=MORGAN_RADIUS, fpSize=MORGAN_BITS)

# 精选 RDKit 描述符（稳定、可解释、跨体系通用）
RDKIT_SELECT = [
    'MolWt', 'HeavyAtomMolWt', 'ExactMolWt', 'NumHeavyAtoms', 'NumHeteroatoms',
    'NumRotatableBonds', 'NumHDonors', 'NumHAcceptors', 'NumAromaticRings',
    'NumAliphaticRings', 'NumSaturatedRings', 'RingCount', 'FractionCSP3',
    'TPSA', 'MolLogP', 'MolMR', 'BalabanJ', 'BertzCT', 'Chi0', 'Chi0n',
    'Chi1', 'Chi1n', 'Kappa1', 'Kappa2', 'Kappa3', 'HallKierAlpha',
    'LabuteASA', 'PEOE_VSA1', 'PEOE_VSA2', 'PEOE_VSA3', 'SMR_VSA1',
    'SMR_VSA2', 'SlogP_VSA1', 'SlogP_VSA2', 'EState_VSA1', 'EState_VSA2',
    'NOCount', 'NHOHCount', 'Np', 'Nring', 'HeavyAtomCount',
]


def _safe_desc(mol, name):
    """安全计算单个 RDKit 描述符，失败返回 NaN"""
    try:
        fn = getattr(Descriptors, name)
        v = fn(mol)
        return float(v) if v is not None else np.nan
    except Exception:
        return np.nan


def compute_mol_descriptors(smiles):
    """
    计算单个分子的完整描述符向量。
    返回 dict: {'rdkit': {...}, 'mordred': {...}, 'morgan': [bits]}
    解析失败返回 None。
    """
    if smiles is None or str(smiles).strip() == '':
        return None
    mol = Chem.MolFromSmiles(str(smiles).strip())
    if mol is None:
        return None

    # 1) RDKit 精选描述符
    rdkit = {name: _safe_desc(mol, name) for name in RDKIT_SELECT}

    # 2) Mordred 2D 描述符（1613 维）
    try:
        mordred_row = _MORD_CALC(mol)
        mordred = {}
        for name, val in zip(_MORD_CALC.descriptors, mordred_row):
            key = str(name)
            try:
                v = float(val)
                mordred[key] = v
            except (TypeError, ValueError):
                mordred[key] = np.nan
    except Exception:
        mordred = {}

    # 3) Morgan 指纹 (2048 bit)
    fp = _MFP_GEN.GetFingerprint(mol)
    morgan = fp.ToList()

    return {'rdkit': rdkit, 'mordred': mordred, 'morgan': morgan}


def smiles_to_feature_row(smiles, prefix=''):
    """
    将 SMILES 转为一行特征（RDKit + Mordred 合并，Morgan 单独返回）。
    返回 (feature_dict, morgan_bits)
    """
    d = compute_mol_descriptors(smiles)
    if d is None:
        return None, None
    row = {}
    for k, v in d['rdkit'].items():
        row[f'{prefix}rdkit_{k}'] = v
    for k, v in d['mordred'].items():
        row[f'{prefix}mordred_{k}'] = v
    return row, d['morgan']


class FormulaAggregator:
    """
    配方级聚合器：将 [(SMILES, 质量分数), ...] 聚合为配方级描述符。
    聚合策略（对每种分子描述符）：
      - 质量加权平均 (weighted mean)
      - 质量加权标准差 (weighted std) —— 刻画配方内异质性
      - 质量加权和 (weighted sum) —— 用于官能团密度类
      - 极值 (max/min) —— 用于沸点/闪点等极端约束
    """

    def __init__(self, use_morgan=True):
        self.use_morgan = use_morgan
        self._cache = {}  # smiles -> feature_row

    def _get(self, smiles):
        if smiles not in self._cache:
            row, morgan = smiles_to_feature_row(smiles)
            self._cache[smiles] = (row, morgan)
        return self._cache[smiles]

    def aggregate(self, comps, morgan_agg='weighted_sum'):
        """
        comps: list of (smiles, mass_fraction)
        返回配方级特征 dict（不含 Morgan）与 Morgan 聚合向量。
        """
        rows, morgan_list, fracs = [], [], []
        for smi, frac in comps:
            row, morgan = self._get(smi)
            if row is None:
                continue
            rows.append(row)
            morgan_list.append(morgan)
            fracs.append(frac)
        if not rows:
            return None, None

        df = pd.DataFrame(rows)
        w = np.array(fracs)
        w = w / w.sum()  # 归一化

        agg = {}
        for col in df.columns:
            v = df[col].to_numpy(dtype=float)
            valid = ~np.isnan(v)
            if valid.sum() == 0:
                continue
            vv = v[valid]
            ww = w[valid]
            ww = ww / ww.sum()
            agg[f'wmean_{col}'] = float(np.average(vv, weights=ww))
            if len(vv) > 1:
                agg[f'wstd_{col}'] = float(np.sqrt(np.average((vv - agg[f'wmean_{col}'])**2, weights=ww)))
            else:
                agg[f'wstd_{col}'] = 0.0

        # Morgan 聚合：质量加权和（可解释为"配方子结构丰度"）
        morgan_agg_vec = None
        if self.use_morgan and morgan_list:
            m = np.array(morgan_list, dtype=float)
            morgan_agg_vec = (m * w[:, None]).sum(axis=0)

        return agg, morgan_agg_vec


# 全局聚合器实例
FORMULA_AGG = FormulaAggregator(use_morgan=True)


# ---------- 常用溶剂/单体的 SMILES 映射（可扩展） ----------
SMILES_LIB = {
    # 溶剂
    '正丁醇': 'CCCCO',
    '二甲苯': 'Cc1ccccc1C',
    '乙二醇单丁醚': 'CCCCOCCO',
    '丁酮': 'CCC(=O)C',
    '环己酮': 'O=C1CCCCC1',
    '醋酸丁酯': 'CCCCOC(=O)C',
    'PMA(丙二醇甲醚醋酸酯)': 'CC(C)OC(=O)C',
    'DBE(二元酸酯)': 'COC(=O)CCCC(=O)OC',
    'PM(丙二醇甲醚)': 'CC(C)OC',
    '二乙二醇单丁醚': 'CCCCOCCOCCO',
    # 单体/小分子
    '双酚A': 'CC(C)(c1ccc(O)cc1)c1ccc(O)cc1',
    '双酚A二缩水甘油醚(DGEBA)': 'CC(C)(c1ccc(OCC2CO2)cc1)c1ccc(OCC2CO2)cc1',
    '苯酚': 'Oc1ccccc1',
    '甲酚': 'Cc1ccccc1O',
    '对苯二甲酸': 'O=C(O)c1ccc(C(=O)O)cc1',
    '间苯二甲酸': 'O=C(O)c1cccc(C(=O)O)c1',
    '新戊二醇': 'OCC(C)(C)CO',
    '乙二醇': 'OCCO',
    '丙三醇': 'OCC(O)CO',
    '季戊四醇': 'OCC(CO)(CO)CO',
    '三羟甲基丙烷': 'CCC(CO)(CO)CO',
    '苯乙烯': 'C=Cc1ccccc1',
    '甲基丙烯酸甲酯(MMA)': 'CC(=C)C(=O)OC',
    '丙烯酸丁酯(BA)': 'CCCCOC(=O)C=C',
    '丙烯酸羟乙酯(HEA)': 'OCCCOC(=O)C=C',
    '甲基丙烯酸羟乙酯(HEMA)': 'OCCCOC(=O)C(=C)C',
    '丙烯酸(AA)': 'OC(=O)C=C',
    '甲基丙烯酸(MAA)': 'CC(=C)C(=O)O',
    '乙酸乙烯酯(VAc)': 'CC(=O)OC=C',
    '氯乙烯(VCM)': 'C=CCl',
    '环氧氯丙烷': 'ClCC1CO1',
    '己二酸': 'OC(=O)CCCCC(=O)O',
    '1,6-己二醇': 'OCCCCCCO',
    '二乙烯三胺(DETA)': 'NCCNCCN',
    '三乙烯四胺(TETA)': 'NCCNCCNCCN',
    '间苯二胺(mPDA)': 'Nc1cccc(N)c1',
    '二氨基二苯砜(DDS)': 'Nc1ccc(S(=O)(=O)c2ccc(N)cc2)cc1',
    '二氨基二苯甲烷(DDM)': 'Nc1ccc(Cc2ccc(N)cc2)cc1',
    '异氰酸酯(MDI)': 'O=C=NC1=CC=C(C2=CC=C(N=C=O)C=C2)C=C1',
    '甲苯二异氰酸酯(TDI)': 'CC1=C(C=C(C=C1)N=C=O)N=C=O',
    '六亚甲基二异氰酸酯(HDI)': 'O=C=NC1CCCCC1N=C=O',
}


def resolve_smiles(code_or_name):
    """从原料代码/名称解析 SMILES（命中库则返回，否则 None）"""
    if code_or_name is None:
        return None
    s = str(code_or_name).strip()
    if s in SMILES_LIB:
        return SMILES_LIB[s]
    # 模糊匹配（包含关系）
    for k, v in SMILES_LIB.items():
        if k in s or s in k:
            return v
    return None


if __name__ == '__main__':
    # 自检
    for smi in ['CCO', 'c1ccccc1', 'CCCCO']:
        d = compute_mol_descriptors(smi)
        print(smi, '-> rdkit:', len(d['rdkit']), 'mordred:', len(d['mordred']), 'morgan:', len(d['morgan']))
    agg, morgan = FORMULA_AGG.aggregate([('CCO', 0.6), ('c1ccccc1', 0.4)])
    print('配方聚合特征数:', len(agg), 'Morgan聚合:', len(morgan))
