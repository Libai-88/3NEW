# -*- coding: utf-8 -*-
"""
配方级机理特征（Mechanistic Formulation Descriptors）
====================================================
现有 `enhanced_descriptors` 把原料描述符做**质量分数线性加权**（w_*），丢失了三类
化学上最关键的信息：

  1. 反应当量与化学计量比：涂膜性能取决于固化后网络结构，而不是组分的算术平均。
  2. 共混玻璃化转变：Tg 按 Fox 方程（1/T 加权）混合，线性平均是系统性偏差。
  3. 工艺-化学耦合：烘烤温度/时间通过反应速率与玻璃化受限影响最终转化度。

本模块在不引入实测 TDS 的前提下，仅用「已登记的描述符 + 公开化学常数」计算这些
机理量。所有外部常数集中在 LIT 表中，逐项标注依据与口径，便于后续用 TDS 替换。

口径约定
  · 当量单位统一为 mol/100g（与 materials.py 的 fg_* 一致），按**到货状态**计
    （即已把固含折进当量，与 EEW 的既有口径一致）。
  · 交联密度 ne 为 Flory-Stockmayer 量级估算，非实测膨胀计数据。
  · Ea 为环氧-酚醛固化表观活化能文献中值，作参数暴露并做敏感性检验。
"""
from __future__ import annotations
import numpy as np

R_GAS = 8.314          # J/(mol·K)
T_REF_K = 473.15       # 200 °C，等效固化时间的参考温度
EA_DEFAULT = 90.0e3    # J/mol，环氧-酚醛固化表观活化能文献中值（80~110 kJ/mol）
KOH_M = 56.1           # g/mol，酸值/羟值换算
LAMBDA_TG = 2000.0     # °C·(100g/mol)，固化后 Tg 抬升与潜在交联密度的经验比例常数

# ------------------------------------------------- 公开化学常数（无 TDS 依据项）
# code -> dict
#   nco_eq   : 异氰酸酯当量 g/eq（到货状态，已含固含折算）
#   amine_eq : 氨基/甲醚化三聚氰胺活性氢当量 g/eq（到货状态）
#   dbp      : 颜料 DBP 吸油值 cm3/100g
#   cat_eq   : 催化活性组分当量 g/eq（钛/铝螯合物、质子酸）
LIT = {
    # 封端异氰酸酯交联剂：母体多异氰酸酯 NCO 含量按 IPDI/HDI 型三聚体公开典型值 22 wt%，
    # 再乘送检组成给出的活性占比（compo_rules.COMPO）折算到到货状态当量。
    'RY460':  dict(nco_eq=100.0 / (0.57 * 0.22), 依据='IPDI 多异氰酸酯 NCO≈22wt%，活性 57% → 797 g/eq'),
    'RY075N': dict(nco_eq=100.0 / (0.75 * 0.22), 依据='HDI 多异氰酸酯 NCO≈22wt%，活性 75% → 606 g/eq'),
    # 醚化氨基树脂：纯树脂活性氢当量取公开典型值，再按固含折算到到货状态。
    'RA009':  dict(amine_eq=250.0 / 0.60, 依据='丁醇化三聚氰胺甲醛 纯≈250 g/eq，60% 固含 → 417 g/eq'),
    'RA083':  dict(amine_eq=300.0 / 0.995, 依据='苯代三聚氰胺甲醛 纯≈300 g/eq，99.5% → 301 g/eq'),
    'RA824':  dict(amine_eq=200.0 / 0.95, 依据='甲醚化三聚氰胺 纯≈200 g/eq（家族推断），95% → 211 g/eq'),
    # 催化剂：按活性组分计
    'AC040':  dict(cat_eq=1200.0, 依据='乙酰丙酮钛螯合物，催化位当量估算'),
    'AZ135':  dict(cat_eq=1500.0, 依据='铝酸酯偶联剂，催化位当量估算'),
    '10%磷酸': dict(cat_eq=3270.0, 依据='10% 磷酸水溶液，按三元酸当量折算'),
    # 颜料 DBP 吸油值（结构性公开典型值）
    '6#炭黑-阿克苏': dict(dbp=95.0, 依据='高色素炭黑 DBP 公开典型值'),
    '14.28%炭黑浆料': dict(dbp=95.0, 依据='炭黑浆料，按干色浆 DBP'),
    '35.7%白浆': dict(dbp=18.0, 依据='金红石 TiO2 经处理 DBP 公开典型值'),
    '35.7%白浆-新（无306）': dict(dbp=18.0, 依据='同 35.7%白浆'),
    '209-白浆': dict(dbp=18.0, 依据='TiO2 白浆'),
    '日本151-PVC': dict(dbp=25.0, 依据='有机颜料浆'),
    '气硅': dict(dbp=220.0, 依据='气相二氧化硅比表面积高，DBP 公开典型值'),
    '3%气硅混合料': dict(dbp=220.0, 依据='同气硅'),
    'FL815C': dict(dbp=30.0, 依据='铝银浆'),
}

# 参与网络反应的角色与化学类别
PHENOLIC_RTYPES = {'酚醛'}
OH_ALI_RTYPES = {'聚酯', '丙烯酸', '氨基', '环氧'}   # 含脂肪族/脂环族 OH（环氧自身含仲羟基）
PIGMENT_ROLES = {'颜料'}
BINDER_ROLES = {'树脂', '固化剂'}

MECH_FEATURES = [
    # 固含量与体积
    'm_solids', 'solids_frac', 'binder_solids_frac', 'volatile_frac',
    # 当量浓度（mol/100g 全配方）
    'eq_epoxy', 'eq_oh_phenol', 'eq_oh_ali', 'eq_oh_all', 'eq_cooh', 'eq_nco', 'eq_amine', 'eq_cat',
    # 化学计量比与偏离
    'r_phenol_epoxy', 'r_oh_epoxy', 'r_nco_oh', 'r_amino_oh', 'stoich_dev_epoxy', 'stoich_dev_nco',
    # 网络结构
    'f_bar', 'ne_potential', 'ne_effective', 'xlink_per_binder',
    # 玻璃化与工艺
    'tg_fox_solids', 'tg_linear_solids', 'tg_rise_est',
    'cure_margin', 'cure_margin_eff', 'cure_margin_neg', 't_eff_min', 'cure_drive',
    # 相容性与挥发
    'h_d_resin_solvent', 'h_d_min_pair', 'solvent_power', 'evap_solvent_w',
    # 颜料体积浓度
    'pvc', 'pvc_over_binder_vol', 'dbp_w_pigment',
    # 催化与副反应
    'cat_per_epoxy_eq', 'acid_phosphate_frac', 'wax_frac',
]


def _fg(mat, key):
    v = mat.get(key, 0.0)
    return 0.0 if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def eq_per_g(mat, code, oh_source='rec'):
    """单克（到货状态）各类当量 mol/g。

    oh_source='rec' 用登记的 fg_oh；'ohv' 用标准换算 OHV/56.1/10（mol/100g→mol/g）。
    两者在部分原料上相差约 3 倍，作为可切换选项交由诚实评估裁决。
    """
    e = {}
    e['epoxy'] = _fg(mat, 'fg_epoxy') / 100.0
    oh = _fg(mat, 'fg_oh') / 100.0
    if oh_source == 'ohv':
        ohv = _fg(mat, 'OHV')
        if ohv > 0:
            oh = ohv / KOH_M / 10.0
    e['oh'] = oh
    cooh = _fg(mat, 'fg_cooh') / 100.0
    if oh_source == 'ohv' and _fg(mat, 'AV') > 0:
        cooh = max(cooh, _fg(mat, 'AV') / KOH_M / 10.0)
    e['cooh'] = cooh
    lit = LIT.get(code, {})
    e['nco'] = (1.0 / lit['nco_eq']) if lit.get('nco_eq') else 0.0
    e['amine'] = (1.0 / lit['amine_eq']) if lit.get('amine_eq') else 0.0
    e['cat'] = (1.0 / lit['cat_eq']) if lit.get('cat_eq') else 0.0
    return e


def hansen_dist(d_src, d_tgt):
    """Hansen 距离 Ra（MPa^0.5），常系数 4/1/0.25。"""
    return float(np.sqrt(4 * (d_src[0] - d_tgt[0]) ** 2 + (d_src[1] - d_tgt[1]) ** 2
                         + 0.25 * (d_src[2] - d_tgt[2]) ** 2))


def mech_features(comp, mat_lib, bake_temp=None, bake_time=None,
                  ea=EA_DEFAULT, oh_source='rec'):
    """计算配方级机理特征。comp: {原料代码: 用量g}（原始代码，内部 canon 化）。

    返回 (dict 特征, None)；配方无可登记组分时返回 (None, 原因)。
    """
    from CoatingModelWorkbench import canon
    items = []
    for code, amt in comp.items():
        try:
            a = float(amt)
        except (TypeError, ValueError):
            continue
        if a <= 0:
            continue
        k = canon(str(code).strip())
        if k not in mat_lib:
            continue
        items.append((k, a))
    if not items:
        return None, 'no_registered_components'
    total = sum(a for _, a in items)

    solids = 0.0
    binder_solids = 0.0
    pig_vol = 0.0
    binder_vol = 0.0
    dbp_num = 0.0
    evap_num = 0.0
    solvent_mass = 0.0
    wax_mass = 0.0
    acid_mass = 0.0
    eq = {kk: 0.0 for kk in ('epoxy', 'oh_phenol', 'oh_ali', 'oh', 'cooh', 'nco', 'amine', 'cat')}
    f_eq_num = 0.0
    f_eq_den = 0.0
    fox_num = 0.0            # Σ w_i / T_K,i  （固含基）
    fox_den = 0.0            # Σ w_i
    tg_lin_num = 0.0
    resin_d = [0.0, 0.0, 0.0]
    resin_w = 0.0
    sol_d = [0.0, 0.0, 0.0]
    sol_w = 0.0
    pair_max = 0.0
    pair_evaluated = False

    per_solvent = []
    per_resin = []
    for k, a in items:
        m = mat_lib[k]
        role = m.get('role', '其他')
        rtype = m.get('rtype', '其他')
        nv = _fg(m, 'NV') / 100.0
        dens = _fg(m, 'density')
        s = a * nv
        solids += s
        is_pigment = (role in PIGMENT_ROLES)
        if not is_pigment and role in BINDER_ROLES:
            binder_solids += s
        if is_pigment and dens > 0:
            pig_vol += a / dens
            dbp_num += LIT.get(k, {}).get('dbp', 0.0) * a
        if role in BINDER_ROLES and dens > 0:
            binder_vol += a / dens
        if role == '溶剂':
            solvent_mass += a
            evap_num += _fg(m, 'evap') * a
        if _fg(m, 'wax') > 0:
            wax_mass += a * _fg(m, 'wax') / 100.0
        if '磷酸' in k:
            acid_mass += a

        e = eq_per_g(m, k, oh_source)
        eq['epoxy'] += e['epoxy'] * a
        eq['oh'] += e['oh'] * a
        eq['cooh'] += e['cooh'] * a
        eq['nco'] += e['nco'] * a
        eq['amine'] += e['amine'] * a
        eq['cat'] += e['cat'] * a
        if rtype in PHENOLIC_RTYPES:
            eq['oh_phenol'] += e['oh'] * a
        elif rtype in OH_ALI_RTYPES:
            eq['oh_ali'] += e['oh'] * a
        # 平均官能度（按当量加权，仅交联相关组分）
        f = _fg(m, 'func')
        e_tot = e['epoxy'] + e['oh'] + e['cooh'] + e['nco'] + e['amine']
        if f > 0 and e_tot > 0:
            f_eq_num += f * e_tot * a
            f_eq_den += e_tot * a

        # Fox 共混 Tg：仅树脂/固化剂的固体部分，溶剂与颜料不参与
        tg = _fg(m, 'Tg')
        if not is_pigment and role in BINDER_ROLES and nv > 0 and tg > -200:
            t_k = tg + 273.15
            if t_k > 50:
                fox_num += (s / t_k)
                fox_den += s
                tg_lin_num += tg * s
        # Hansen：溶剂 vs 树脂/固化剂（固体部分加权）
        d = (_fg(m, 'dD'), _fg(m, 'dP'), _fg(m, 'dH'))
        if role == '溶剂':
            sol_d = [sol_d[i] + d[i] * a for i in range(3)]
            sol_w += a
            per_solvent.append((d, a))
        elif role in BINDER_ROLES:
            resin_d = [resin_d[i] + d[i] * s for i in range(3)]
            resin_w += s
            per_resin.append((d, s))

    eps = 1e-9
    d = {}
    d['m_solids'] = solids
    d['solids_frac'] = solids / total
    d['binder_solids_frac'] = binder_solids / total
    d['volatile_frac'] = 1.0 - solids / total

    scale = 100.0 / total            # mol/100g 全配方
    d['eq_epoxy'] = eq['epoxy'] * scale
    d['eq_oh_phenol'] = eq['oh_phenol'] * scale
    d['eq_oh_ali'] = eq['oh_ali'] * scale
    d['eq_oh_all'] = eq['oh'] * scale
    d['eq_cooh'] = eq['cooh'] * scale
    d['eq_nco'] = eq['nco'] * scale
    d['eq_amine'] = eq['amine'] * scale
    d['eq_cat'] = eq['cat'] * scale

    act_h_epoxy = eq['oh_phenol'] + eq['oh_ali'] + eq['amine'] + eq['cooh']
    act_h_nco = eq['oh'] + eq['amine'] + eq['cooh']
    d['r_phenol_epoxy'] = eq['epoxy'] / act_h_epoxy if act_h_epoxy > eps else 0.0
    d['r_oh_epoxy'] = eq['epoxy'] / eq['oh'] if eq['oh'] > eps else 0.0
    d['r_nco_oh'] = eq['nco'] / max(eq['oh'], eps) if eq['nco'] > eps else 0.0
    d['r_amino_oh'] = eq['amine'] / max(eq['oh'] + eq['cooh'], eps) if eq['amine'] > eps else 0.0
    d['stoich_dev_epoxy'] = abs(1.0 - d['r_phenol_epoxy']) if act_h_epoxy > eps else 0.0
    d['stoich_dev_nco'] = abs(1.0 - d['r_nco_oh']) if (eq['nco'] > eps and eq['oh'] > eps) else 0.0

    f_bar = (f_eq_num / f_eq_den) if f_eq_den > eps else 0.0
    d['f_bar'] = f_bar
    # Flory-Stockmayer 量级：有效交联密度 ∝ 限制性当量 × (f̄-2)/f̄，按结合料固体归一
    lim_epoxy = min(eq['epoxy'], act_h_epoxy)
    lim_nco = min(eq['nco'], act_h_nco)
    gel_factor = max(0.0, (f_bar - 2.0) / f_bar) if f_bar > 0 else 0.0
    binder_g = max(binder_solids, eps)
    d['ne_potential'] = (lim_epoxy + lim_nco) * gel_factor * 100.0 / binder_g
    d['xlink_per_binder'] = (eq['epoxy'] + eq['nco'] + eq['amine']) * 100.0 / binder_g

    # 固化度估算：等效时间 × 官能团稀释度 → 简单饱和动力学（仅用于给 ne_effective 一个形状）
    bt = 0.0 if bake_temp is None or (isinstance(bake_temp, float) and np.isnan(bake_temp)) else float(bake_temp)
    btm = 0.0 if bake_time is None or (isinstance(bake_time, float) and np.isnan(bake_time)) else float(bake_time)
    if bt > 0:
        t_eff = btm * np.exp(-ea / R_GAS * (1.0 / (bt + 273.15) - 1.0 / T_REF_K))
    else:
        t_eff = 0.0
    d['t_eff_min'] = float(t_eff)
    alpha = 1.0 - np.exp(-t_eff / 30.0) if t_eff > 0 else 0.0
    d['ne_effective'] = d['ne_potential'] * float(alpha)
    d['cure_drive'] = float(t_eff * d['ne_potential'])

    if fox_den > eps:
        tg_fox = 1.0 / (fox_num / fox_den) - 273.15
        d['tg_fox_solids'] = float(tg_fox)
    else:
        d['tg_fox_solids'] = 0.0
    d['tg_linear_solids'] = float(tg_lin_num / fox_den) if fox_den > eps else 0.0
    # 固化后 Tg 抬升的经验比例项：λ_TG 取使 ΔTg 落在环氧-酚醛网络文献区间
    # （后固化抬升约 15~35 °C，对应 ne_potential 0.008~0.015 mol/100g）的常数。
    d['tg_rise_est'] = float(LAMBDA_TG * d['ne_potential'])
    d['cure_margin'] = float(bt - d['tg_fox_solids']) if bt > 0 else 0.0
    # 玻璃化受限判据：烘烤温度与「固化后 Tg」之差，为负则反应受扩散控制、转化停滞
    d['cure_margin_eff'] = float(bt - d['tg_fox_solids'] - d['tg_rise_est']) if bt > 0 else 0.0
    d['cure_margin_neg'] = float(max(0.0, -d['cure_margin_eff']))

    if resin_w > eps and sol_w > eps:
        rd = [x / resin_w for x in resin_d]
        sd = [x / sol_w for x in sol_d]
        d['h_d_resin_solvent'] = hansen_dist(sd, rd)
        for (ds, _w) in per_solvent:
            for (dr, _) in per_resin:
                pair_evaluated = True
                pair_max = max(pair_max, hansen_dist(ds, dr))
        d['h_d_min_pair'] = pair_max if pair_evaluated else 0.0
    else:
        d['h_d_resin_solvent'] = 0.0
        d['h_d_min_pair'] = 0.0
    d['solvent_power'] = float(d['h_d_resin_solvent'] * (solvent_mass / total)) if solvent_mass > 0 else 0.0
    d['evap_solvent_w'] = float(evap_num / solvent_mass) if solvent_mass > eps else 0.0

    tot_vol = pig_vol + binder_vol
    d['pvc'] = float(pig_vol / tot_vol) if tot_vol > eps else 0.0
    d['pvc_over_binder_vol'] = float(pig_vol / binder_vol) if binder_vol > eps else 0.0
    d['dbp_w_pigment'] = float(dbp_num / max(sum(a for k, a in items if mat_lib[k].get('role') in PIGMENT_ROLES), eps)) \
        if (tot_vol > eps) else 0.0

    d['cat_per_epoxy_eq'] = float(eq['cat'] / max(eq['epoxy'], eps)) if eq['epoxy'] > eps else 0.0
    d['acid_phosphate_frac'] = acid_mass / total
    d['wax_frac'] = wax_mass / total
    return d, None


def mech_vector(comp, mat_lib, bake_temp=None, bake_time=None,
                ea=EA_DEFAULT, oh_source='rec'):
    d, err = mech_features(comp, mat_lib, bake_temp, bake_time, ea=ea, oh_source=oh_source)
    if d is None:
        return [0.0] * len(MECH_FEATURES)
    return [float(d.get(f, 0.0)) for f in MECH_FEATURES]
