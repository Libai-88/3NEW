# -*- coding: utf-8 -*-
"""
配方级描述符计算：将任意体系的配方(组分->用量)转换为统一描述符向量
"""
import numpy as np
from materials import MAT, ALIAS, CONT_DESC, ROLES, RTYPES

def resolve(code):
    """解析原料代码，返回规范名"""
    code = str(code).strip()
    if code in MAT:
        return code
    if code in ALIAS:
        return ALIAS[code]
    # 尝试直接匹配
    for k in MAT:
        if code == k:
            return k
    return None

def formulation_descriptors(comp_dict, bake_temp=None, bake_time=None):
    """
    输入: comp_dict = {原料代码: 用量(质量份)}
    输出: 配方级描述符 dict
    """
    # 解析并过滤
    items = []
    total = 0.0
    for code, amt in comp_dict.items():
        if amt is None or (isinstance(amt, float) and np.isnan(amt)):
            continue
        amt = float(amt)
        if amt <= 0:
            continue
        key = resolve(code)
        if key is None:
            continue
        items.append((key, amt))
        total += amt
    if total <= 0:
        return None

    n = len(items)
    w = [a / total for _, a in items]  # 质量分数

    # 角色/树脂类型质量分数
    role_frac = {r: 0.0 for r in ROLES}
    rtype_frac = {r: 0.0 for r in RTYPES}
    for (key, _), wi in zip(items, w):
        role_frac[MAT[key]['role']] += wi
        rtype_frac[MAT[key]['rtype']] += wi

    # 连续描述符加权平均
    desc = {}
    for d in CONT_DESC:
        vals = [MAT[k][d] for k, _ in items]
        desc['w_' + d] = sum(v * wi for v, wi in zip(vals, w))

    # 官能团密度 (每100g配方的摩尔数)
    for fg in ['fg_epoxy','fg_oh','fg_cooh','fg_ester','fg_amine','fg_amide','fg_arom','fg_ether']:
        desc['s_' + fg] = sum(MAT[k][fg] * a for (k, _), a in zip(items, [x[1] for x in items]))

    # 化学计量描述符
    resin_mass = sum(a for (k, _), a in zip(items, [x[1] for x in items]) if MAT[k]['role'] == '树脂')
    xlink_mass = sum(a for (k, _), a in zip(items, [x[1] for x in items]) if MAT[k]['role'] == '固化剂')
    # 树脂环氧当量 (mol/100g配方)
    epoxy_eq = sum(MAT[k]['fg_epoxy'] * a for (k, _), a in zip(items, [x[1] for x in items]))
    # 固化剂羟值当量 (mol/100g配方)
    oh_eq = sum(MAT[k]['fg_oh'] * a for (k, _), a in zip(items, [x[1] for x in items]))
    desc['resin_frac'] = role_frac['树脂']
    desc['xlink_frac'] = role_frac['固化剂']
    desc['solvent_frac'] = role_frac['溶剂']
    desc['additive_frac'] = role_frac['助剂']
    desc['pigment_frac'] = role_frac['颜料']
    desc['xlink_resin_ratio'] = xlink_mass / resin_mass if resin_mass > 0 else 0
    desc['oh_epoxy_eq_ratio'] = oh_eq / epoxy_eq if epoxy_eq > 0 else 0
    desc['epoxy_eq_100g'] = epoxy_eq
    desc['oh_eq_100g'] = oh_eq
    desc['n_components'] = n
    desc['avg_func'] = desc['w_func']
    # 树脂类型占比
    for r in RTYPES:
        desc['rtype_' + r] = rtype_frac[r]
    # 工艺条件
    if bake_temp is not None:
        desc['bake_temp'] = bake_temp
    if bake_time is not None:
        desc['bake_time'] = bake_time
    return desc

DESC_FEATURES = [
    'resin_frac','xlink_frac','solvent_frac','additive_frac','pigment_frac',
    'xlink_resin_ratio','oh_epoxy_eq_ratio','epoxy_eq_100g','oh_eq_100g','n_components','avg_func',
    'rtype_环氧','rtype_酚醛','rtype_聚酯','rtype_乙烯基','rtype_丙烯酸','rtype_聚氨酯','rtype_其他',
] + ['w_' + d for d in CONT_DESC] + ['s_' + fg for fg in ['fg_epoxy','fg_oh','fg_cooh','fg_ester','fg_amine','fg_amide','fg_arom','fg_ether']]
