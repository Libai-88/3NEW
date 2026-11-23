# -*- coding: utf-8 -*-
"""
占位描述符修正（不依赖 TDS 的部分）
==================================
「原料主数据」中标注为「专有估算」的 15 行是建库时按代码模式生成的占位记录：
同一模板值被复制到化学完全不同的原料上（例如 MIBK/DBE/DPM 与 MEK 共用
「密度 1.0、分子量 110、沸点 160、Hansen 17.5/6/8」），且部分行的固含与其
自身名称矛盾（如「40%818」记为 NV=55、「3%气硅混合料」记为 NV=50）。

本模块只处理**无需供应商 TDS**即可判定的三类问题，逐条给出依据；
无法确证的行统一进入 PENDING，保留原值并改标状态，不做猜测性填充。

  F1 同物合并：与库内已有原料是同一物质/同一商品 → 走 ALIAS 归并，不重复建描述符
  F2 名称自证：固含直接写在代码名里 → 按名称修正 NV
  F3 公开常数：纯溶剂/纯氧化物的密度、沸点、闪点、Hansen 参数等为手册定值
  F4 族内一致：同族原料已有登记的化学量 → 沿用以消除自相矛盾

用量占比参考（合并版数据集 486 样本）：这 15 行合计占配方总用量质量 13.7%，
影响 81 个样本；其中 14 行仅出现在「环氧-配比方案」（112 条无实测标签），
只有 MEK 出现在有标签的聚酯金黄样本中。因此本次修正不改变当前三项目标指标，
作用是让这 112 条配方可用于跨体系外推验证与补标签排程。
"""

# ------------------------------------------------ F3/F4：字段级修正
# code -> {描述符字段: 值}，附 依据 与 口径标签
FIXES = {
    'MIBK': dict(
        role='溶剂', rtype='其他', NV=0.0, density=0.80, Mw=100.2, EEW=0, AV=0, OHV=0,
        amine=0, func=0, Tg=-105.0, bp=116.5, fp=15.0,
        dD=14.7, dP=5.3, dH=7.7, pol=3.0, evap=2.7,
        C=72.9, H=11.2, O=15.9, N=0, S=0, Cl=0,
        fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0,
        fg_arom=0, fg_ether=0, wax=0, pig=0,
        依据='甲基异丁基甲酮 CAS108-10-1 手册定值；挥发速率以乙酸丁酯=1', 口径='F3-公开手册'),
    'DPM': dict(
        role='溶剂', rtype='其他', NV=0.0, density=0.91, Mw=146.2, EEW=0, AV=0, OHV=0,
        amine=0, func=0, Tg=-85.0, bp=190.0, fp=82.0,
        dD=15.8, dP=3.8, dH=8.4, pol=2.8, evap=0.14,
        C=58.9, H=10.3, O=30.8, N=0, S=0, Cl=0,
        # 端羟基 + 两个醚氧，按 1/MW 折算（与库内 PM/丁醚类的 fg 口径一致）
        fg_oh=0.68, fg_ether=1.37, fg_epoxy=0, fg_cooh=0, fg_ester=0,
        fg_amine=0, fg_amide=0, fg_arom=0, wax=0, pig=0,
        依据='二丙二醇甲醚 CAS34590-94-8 手册定值；fg 按官能团数/MW 折算', 口径='F3-公开手册'),
    'DBE': dict(
        role='溶剂', rtype='其他', NV=0.0, density=1.06, Mw=180.0, EEW=0, AV=0, OHV=0,
        amine=0, func=0, Tg=-70.0, bp=223.0, fp=102.0,
        dD=16.5, dP=3.5, dH=3.8, pol=2.5, evap=0.03,
        C=58.0, H=9.0, O=33.0, N=0, S=0, Cl=0,
        # 混合二元酸二甲酯：每分子 2 个酯基
        fg_ester=1.15, fg_epoxy=0, fg_oh=0, fg_cooh=0,
        fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0, wax=0, pig=0,
        依据='混合二元酸酯（己二酸/戊二酸/丁二酸二甲酯）公开物性', 口径='F3-公开手册'),
    '气硅': dict(
        role='助剂', rtype='其他', NV=100.0, density=2.20, Mw=60.1, EEW=0, AV=0, OHV=0,
        amine=0, func=0, Tg=0.0, bp=500.0, fp=0.0,
        dD=18.0, dP=8.0, dH=10.0, pol=3.0, evap=0.0,
        C=0, H=0.8, O=53.3, N=0, S=0, Cl=0,
        fg_oh=0.05, fg_epoxy=0, fg_cooh=0, fg_ester=0,
        fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0, wax=0, pig=0,
        依据='气相二氧化硅 SiO2：真密度 2.2、表面硅醇约 0.05 mol/100g；'
             '与库内「3%气硅」同一化学，仅固含不同', 口径='F4-族内一致'),
    '6#炭黑-阿克苏': dict(
        role='颜料', rtype='其他', NV=100.0, density=1.85,
        C=80.0, H=2.0, O=10.0, pig=100.0,
        依据='色素炭黑真密度约 1.85 g/cm3；元素组成沿用库内既有炭黑记录'
             '「14.28%炭黑浆料」的干色浆口径，避免同族自相矛盾',
        口径='F4-族内一致'),
    '40%818': dict(
        NV=40.0,
        依据='代码名「40%818」自证固含 40%，原占位值 55 与名称矛盾', 口径='F2-名称自证'),
    '10%135': dict(
        NV=10.0,
        依据='代码名「10%135」= AZ135 的 10% 稀释品（AZ135 为 98% 有效分）；'
             '载体类型未记录，仅修正固含', 口径='F2-名称自证'),
    '50170M': dict(
        role='树脂', rtype='聚酯', NV=40.0, density=1.10, Mw=3000, Tg=40.0,
        AV=8.0, OHV=60.0, func=2, C=66, H=8, O=26,
        fg_ester=0.35, fg_oh=0.035,
        依据='与「50173M」（= 已登记 RJ173M，商品名 聚酯树脂 50173-M-40）同族命名，'
             '按同族 40% 固含聚酯取值，属推断待校核', 口径='F4-族内一致(推断)'),
}

# ------------------------------------------------ F1：同物合并（走 ALIAS）
# 被合并行的描述符不再使用，统一由目标原料的真实记录提供
MERGE_ALIAS = {
    'MEK': 'TT444',                       # 甲乙酮 = 丁酮，库内 TT444 即丁酮
    '50173M': 'RJ173M',                   # 送检名称「聚酯树脂 50173-M-40」= RJ173M
    '209-白浆': '35.7%白浆',              # ALIAS 已有「35.7%白浆-209」→ 同一浆料
    '35.7%白浆-新（无306）': '35.7%白浆',  # 同一白浆，仅配方中不含 BYK306
    '3%气硅混合料': '3%气硅',             # 同为 3% 气相二氧化硅分散体
}

# ------------------------------------------------ 无法确证，保留原值并标记
PENDING = {
    'DMP': '代码缩写歧义（丙二醇二甲醚 / 邻苯二甲酸二甲酯 / 二甲氨基丙醇皆用 DMP），'
           '需物料编码或 SDS 确认；该原料用于 21 个配方、合计 238.7 g',
    '209-基料': '与「209-白浆」配对出现的基料，组成未记录',
}


def apply(mat):
    """就地修正 full_mat(code -> dict) 的占位行。

    返回 (changed, merged, pending)：
      changed  被修正的 code 列表
      merged   归并到既有原料的 {code: target}
      pending  标记为待确认的 {code: 原因}
    """
    changed, merged, pending = [], dict(MERGE_ALIAS), dict(PENDING)
    for code, ov in FIXES.items():
        if code not in mat:
            continue
        m = mat[code]
        dirty = False
        for k, v in ov.items():
            if k in ('依据', '口径'):
                continue
            if m.get(k) != v:
                m[k] = v
                dirty = True
        if dirty:
            m['数据来源'] = 'handbook:' + ov.get('口径', 'F3-公开手册')
            m['备注'] = ov.get('依据', '')
            changed.append(code)
    for code, why in PENDING.items():
        if code in mat:
            mat[code]['数据来源'] = 'pending_TDS'
            mat[code]['备注'] = why
    return changed, merged, pending
