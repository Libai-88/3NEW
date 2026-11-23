# -*- coding: utf-8 -*-
"""
通用型配方性能预测流水线 CLI (Generalization Pipeline)
======================================================
把"泛化方案"封装为统计人员可直接运行的命令行工具：
  模板Excel → SMILES自动描述符(RDKit/Mordred/Morgan) → 配方级聚合 → 建模CSV
  → 半监督伪标签/主动学习/迁移 标签补充 → 补充后标签CSV

设计原则（对应方案要求）：
  - 便捷性高：一条命令完成，无需手工整理特征
  - 统计人员友好：输入/输出均为标准 Excel/CSV，参数有默认值
  - 自动化程度高：SMILES→描述符→聚合全自动，零人工计算
  - 规范化：严格按"通用型数据集模板"工作表结构读取
  - 模板化：输入即模板本身，输出即建模就绪宽表

用法示例：
  # 1) 模板 → 配方级描述符 → 建模CSV
  python run_pipeline.py desc --input 通用型数据集模板.xlsx --output 特征.csv

  # 2) 建模CSV + 性能结果 → 标签补充（半监督+主动学习+迁移）
  python run_pipeline.py label --features 特征.csv --input 通用型数据集模板.xlsx \
      --target T弯 --output 标签补充.csv

  # 3) 全流程
  python run_pipeline.py all --input 通用型数据集模板.xlsx --output_dir ./out
"""
import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# ---------- 依赖模块 ----------
try:
    from auto_desc import compute_mol_descriptors, FORMULA_AGG, resolve_smiles
    HAS_AUTODESC = True
except Exception as e:  # pragma: no cover
    HAS_AUTODESC = False
    _AUTODESC_ERR = e

try:
    from materials import MAT, ALIAS, CONT_DESC, ROLES, RTYPES
    from descriptors import formulation_descriptors, DESC_FEATURES
    HAS_MATLIB = True
except Exception as e:  # pragma: no cover
    HAS_MATLIB = False
    _MATLIB_ERR = e

try:
    from semi_supervised import SemiSupervisedLabeler
    HAS_SEMI = True
except Exception as e:  # pragma: no cover
    HAS_SEMI = False
    _SEMI_ERR = e


# =====================================================================
# 第1步：从模板读取数据
# =====================================================================
def read_template(input_path):
    """读取通用型数据集模板，返回 (原料主数据df, 配方明细df, 性能结果df)"""
    xl = pd.ExcelFile(input_path)
    sheets = xl.sheet_names
    need = ['原料主数据', '配方明细', '性能结果']
    for s in need:
        if s not in sheets:
            raise ValueError(f'模板缺少工作表: {s}（当前: {sheets}）')

    mat = xl.parse('原料主数据')
    rec = xl.parse('配方明细')
    perf = xl.parse('性能结果')
    # 清理列名空白
    mat.columns = [str(c).strip() for c in mat.columns]
    rec.columns = [str(c).strip() for c in rec.columns]
    perf.columns = [str(c).strip() for c in perf.columns]
    return mat, rec, perf


# =====================================================================
# 第2步：SMILES → 分子描述符（有SMILES的原料自动计算）
# =====================================================================
def build_material_desc(mat_df):
    """
    为每个原料构建描述符：
      - 有SMILES → RDKit/Mordred/Morgan 自动计算
      - 无SMILES(专有树脂) → 回退 materials.py 手工库（角色/类型典型值）
    返回 {原料代码: 特征dict}
    """
    if not HAS_AUTODESC:
        print('[警告] auto_desc 不可用，全部回退 materials.py 库')
        return None

    smi_col = None
    for c in mat_df.columns:
        if 'SMILES' in c.upper():
            smi_col = c
            break
    if smi_col is None:
        print('[警告] 原料主数据无 SMILES 列，回退 materials.py 库')
        return None

    mat_desc = {}
    n_smiles = 0
    for _, row in mat_df.iterrows():
        code = str(row.get('原料代码', '')).strip()
        if not code:
            continue
        smi = row.get(smi_col)
        smi = None if (smi is None or str(smi).strip() in ('', '专有(无SMILES)')) else str(smi).strip()
        if smi:
            d = compute_mol_descriptors(smi)
            if d is not None:
                # 合并 RDKit + Mordred 为一行
                feat = {}
                for k, v in d['rdkit'].items():
                    feat[f'rdkit_{k}'] = v
                for k, v in d['mordred'].items():
                    feat[f'mordred_{k}'] = v
                mat_desc[code] = feat
                n_smiles += 1
    print(f'[OK] 自动计算分子描述符: {n_smiles} 种原料（SMILES）')
    return mat_desc


# =====================================================================
# 第3步：配方级聚合
# =====================================================================
def aggregate_formulations(rec_df, mat_desc=None, mat_df=None):
    """
    按样本ID聚合配方级描述符：
      - SMILES描述符：质量加权平均/标准差（配方内异质性）
      - 角色/树脂类型占比 + 化学计量（materials.py）
    返回 (样本ID列表, 特征DataFrame)
    """
    # 先算角色/类型/化学计量（materials.py 库，覆盖全部原料）
    rows = []
    sample_ids = []
    for sid, grp in rec_df.groupby('样本ID'):
        comp = {}
        for _, r in grp.iterrows():
            code = str(r.get('原料代码', '')).strip()
            amt = r.get('用量(g)')
            if code and amt is not None and not (isinstance(amt, float) and np.isnan(amt)):
                comp[code] = float(amt)
        if not comp:
            continue
        d = formulation_descriptors(comp)
        if d is None:
            continue
        sample_ids.append(sid)
        rows.append(d)

    if not rows:
        raise ValueError('配方明细无可聚合样本')
    base_df = pd.DataFrame(rows, index=sample_ids)

    # 叠加 SMILES 分子描述符聚合（仅对有 SMILES 的原料）
    if mat_desc:
        smi_agg_rows = []
        for sid, grp in rec_df.groupby('样本ID'):
            comps = []
            for _, r in grp.iterrows():
                code = str(r.get('原料代码', '')).strip()
                amt = r.get('用量(g)')
                if code in mat_desc and amt is not None:
                    comps.append((code, float(amt)))
            if not comps:
                smi_agg_rows.append({})
                continue
            # 用 FormulaAggregator 聚合
            smi_feats = []
            total = sum(a for _, a in comps)
            for code, amt in comps:
                smi_feats.append((mat_desc[code], amt / total))
            agg = {}
            # 加权平均 + 加权标准差
            all_keys = set()
            for feat, _ in smi_feats:
                all_keys.update(feat.keys())
            for k in all_keys:
                vals = []
                ws = []
                for feat, w in smi_feats:
                    if k in feat and not (isinstance(feat[k], float) and np.isnan(feat[k])):
                        vals.append(feat[k])
                        ws.append(w)
                if not vals:
                    continue
                ws = np.array(ws) / np.sum(ws)
                vv = np.array(vals)
                agg[f'wmean_{k}'] = float(np.average(vv, weights=ws))
                if len(vv) > 1:
                    agg[f'wstd_{k}'] = float(np.sqrt(np.average((vv - agg[f'wmean_{k}'])**2, weights=ws)))
                else:
                    agg[f'wstd_{k}'] = 0.0
            smi_agg_rows.append(agg)
        smi_df = pd.DataFrame(smi_agg_rows, index=sample_ids)
        # 合并（SMILES列加前缀避免与库列冲突）
        smi_df.columns = ['smi_' + c for c in smi_df.columns]
        base_df = base_df.join(smi_df, how='left')

    return sample_ids, base_df


# =====================================================================
# 第4步：性能标签宽表
# =====================================================================
def build_label_wide(perf_df, sample_ids, target):
    """从性能结果构建 样本ID→目标值 映射（含标签状态）"""
    tgt_col = None
    for c in perf_df.columns:
        if c.strip() in ('目标属性', '目标属性名称'):
            tgt_col = c
            break
    if tgt_col is None:
        raise ValueError('性能结果缺少"目标属性"列')

    val_col = None
    for c in perf_df.columns:
        if '测试值' in c or '数值' in c:
            val_col = c
            break
    if val_col is None:
        raise ValueError('性能结果缺少"测试值"列')

    status_col = None
    for c in perf_df.columns:
        if '标签状态' in c:
            status_col = c
            break

    sub = perf_df[perf_df[tgt_col].astype(str).str.strip() == target]
    y = {}
    status = {}
    for _, r in sub.iterrows():
        sid = str(r.get('样本ID', '')).strip()
        v = r.get(val_col)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            y[sid] = float(v)
            if status_col:
                status[sid] = str(r.get(status_col, '')).strip()
    return y, status


# =====================================================================
# 子命令：desc
# =====================================================================
def cmd_desc(args):
    print(f'[1/3] 读取模板: {args.input}')
    mat, rec, perf = read_template(args.input)
    print(f'      原料 {len(mat)} 种 / 配方明细 {len(rec)} 行 / 性能 {len(perf)} 行')

    print('[2/3] SMILES → 分子描述符（RDKit/Mordred/Morgan）')
    mat_desc = build_material_desc(mat)

    print('[3/3] 配方级聚合')
    sample_ids, feat_df = aggregate_formulations(rec, mat_desc, mat)
    feat_df.insert(0, '样本ID', sample_ids)
    feat_df.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f'[OK] 建模特征已保存: {args.output}  ({feat_df.shape[0]} 样本 × {feat_df.shape[1]-1} 特征)')
    return feat_df


# =====================================================================
# 子命令：label（半监督伪标签 + 主动学习 + 迁移）
# =====================================================================
def cmd_label(args):
    print(f'[1/3] 读取特征: {args.features}')
    feat = pd.read_csv(args.features)
    sid_col = '样本ID' if '样本ID' in feat.columns else feat.columns[0]
    sample_ids = feat[sid_col].astype(str).tolist()
    X = feat.drop(columns=[sid_col]).select_dtypes(include=[np.number]).values

    print(f'[2/3] 读取性能标签: {args.input} (目标={args.target})')
    mat, rec, perf = read_template(args.input)
    y_map, status_map = build_label_wide(perf, sample_ids, args.target)
    y = np.array([y_map.get(s, np.nan) for s in sample_ids])
    lab_mask = ~np.isnan(y)
    print(f'      有标签 {lab_mask.sum()} / 无标签 {(~lab_mask).sum()}')
    if lab_mask.sum() < 5:
        print(f'[提示] 目标"{args.target}"有标签样本仅 {lab_mask.sum()} 条，不足以训练可靠模型。')
        print('       建议先用主动学习安排少量实测（推荐测试），或换用标签更充足的目标属性。')
        print('       输出将仅标记"推荐测试/待复核"，不生成伪标签。')

    print('[3/3] 半监督伪标签 + 主动学习标签补充')
    if not HAS_SEMI:
        print('[错误] semi_supervised 不可用，无法执行标签补充')
        sys.exit(1)

    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import r2_score
    SEED = 42

    # 有标签样本训练基线
    X_lab, y_lab = X[lab_mask], y[lab_mask]
    X_unlab = X[~lab_mask]
    labeler = SemiSupervisedLabeler()
    labeler.fit(X_lab, y_lab)

    # 预测无标签样本 + 不确定性（树间标准差）
    unlab_info = labeler.label_unlabeled(X_unlab, conf_quantile=0.5, act_quantile=0.8)
    mean_p = unlab_info['pred'].values
    rel_std = unlab_info['rel_std'].values
    status = unlab_info['label_status'].values
    pseudo_mask = status == 'pseudo'
    active_mask = status == 'active'

    # 伪标签回放（权重0.5）
    X_aug = np.vstack([X_lab, X_unlab[pseudo_mask]])
    y_aug = np.concatenate([y_lab, mean_p[pseudo_mask]])
    w_aug = np.concatenate([np.ones(len(y_lab)), np.full(pseudo_mask.sum(), 0.5)])
    m1 = RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=-1)
    m1.fit(X_aug, y_aug, sample_weight=w_aug)

    # 输出补充标签表
    out = pd.DataFrame({'样本ID': sample_ids})
    out['目标属性'] = args.target
    out['原始标签'] = np.where(lab_mask, y, np.nan)
    out['预测值'] = np.nan
    out['不确定性'] = np.nan
    out['标签状态'] = ''
    out.loc[lab_mask, '标签状态'] = '实测'
    # 无标签样本回填预测
    unlab_idx = np.where(~lab_mask)[0]
    for i, idx in enumerate(unlab_idx):
        out.loc[idx, '预测值'] = mean_p[i]
        out.loc[idx, '不确定性'] = rel_std[i]
        if pseudo_mask[i]:
            out.loc[idx, '标签状态'] = '伪标签(自动)'
        elif active_mask[i]:
            out.loc[idx, '标签状态'] = '推荐测试(主动学习)'
        else:
            out.loc[idx, '标签状态'] = '待定(人工复核)'
    out.to_csv(args.output, index=False, encoding='utf-8-sig')

    n_pseudo = pseudo_mask.sum()
    n_active = active_mask.sum()
    print(f'[OK] 标签补充完成: 伪标签 {n_pseudo} 条 / 推荐测试 {n_active} 条 / 待复核 {(~lab_mask).sum()-n_pseudo-n_active} 条')
    print(f'[OK] 已保存: {args.output}')
    return out


# =====================================================================
# 子命令：all（全流程）
# =====================================================================
def cmd_all(args):
    os.makedirs(args.output_dir, exist_ok=True)
    feat_csv = os.path.join(args.output_dir, '建模特征.csv')
    cmd_desc(type('A', (), {'input': args.input, 'output': feat_csv})())
    for tgt in args.targets:
        label_csv = os.path.join(args.output_dir, f'标签补充_{tgt}.csv')
        cmd_label(type('A', (), {
            'features': feat_csv, 'input': args.input,
            'target': tgt, 'output': label_csv})())
    print(f'\n[OK] 全流程完成，输出目录: {args.output_dir}')


# =====================================================================
# 主入口
# =====================================================================
def main():
    p = argparse.ArgumentParser(
        prog='run_pipeline.py',
        description='通用型配方性能预测流水线：模板→描述符→建模CSV→标签补充')
    sub = p.add_subparsers(dest='cmd', required=True)

    p_desc = sub.add_parser('desc', help='模板→配方级描述符→建模CSV')
    p_desc.add_argument('--input', required=True, help='通用型数据集模板.xlsx 路径')
    p_desc.add_argument('--output', default='建模特征.csv', help='输出CSV路径')
    p_desc.set_defaults(fn=cmd_desc)

    p_label = sub.add_parser('label', help='半监督伪标签+主动学习标签补充')
    p_label.add_argument('--features', required=True, help='desc输出的建模CSV')
    p_label.add_argument('--input', required=True, help='通用型数据集模板.xlsx 路径')
    p_label.add_argument('--target', default='T弯', help='目标属性（T弯/MEK擦拭/水煮等级）')
    p_label.add_argument('--output', default='标签补充.csv', help='输出CSV路径')
    p_label.set_defaults(fn=cmd_label)

    p_all = sub.add_parser('all', help='全流程（desc + label）')
    p_all.add_argument('--input', required=True, help='通用型数据集模板.xlsx 路径')
    p_all.add_argument('--output_dir', default='./out', help='输出目录')
    p_all.add_argument('--targets', nargs='+', default=['T弯', 'MEK擦拭', '水煮等级'],
                       help='目标属性列表')
    p_all.set_defaults(fn=cmd_all)

    args = p.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
