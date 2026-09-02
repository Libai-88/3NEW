# -*- coding: utf-8 -*-
"""
供应商 TDS/SDS 实测描述符层（Raw-Material Data-Sheet Layer）
==========================================================
描述符库 `materials.py` 的专有原料基线是「化学类别典型值」；`compo_rules.py` 用送检组成
覆盖了 21 条；`handbook_fixes.py` 修正了无需供应商文档即可判定的占位行。本模块是**优先级
最高**的第四层：逐字段引用供应商技术数据表（TDS）与安全说明书（SDS）的原文数值，把描述符
从「类别典型值」升级为「该到货牌号的实测值」。

档案：`generalization/TDS-SDS/`（291 份 markdown，TDS 与 SDS 原文转录）。
每条记录带 `依据`（原文摘录）与 `doc`（档案相对路径），可逐条回溯核对。

口径约定（与「数据字典」一致）
  · NV / density / bp / fp / evap：到货状态（原包装，含载体溶剂）。
  · EEW / OHV / AV / Mw / Tg：档案多按**固体树脂**给出，本层按标准换算折到到货状态：
        OHV_到货 = OHV_固体 × NV/100（AV 同理）    EEW_到货 = EEW_固体 ÷ (NV/100)
        fg_epoxy = 100/EEW_到货    fg_oh = OHV_到货/561    fg_cooh = AV_到货/561
        NCO%（到货）→ nco_eq = 4202/NCO%    环氧数 ESO%（氧含量）→ EEW = 1600/ESO%
        DGEBA 固体羟值 = 56100×(n+1)/(2×EEW_固体)，n=(EEW_固体−171.1)/284.4
  · 溶液密度/沸点/闪点：按「固体树脂 + 登记载体」体积混合规则与质量加权折算（公式见 derive）。
  · 档案未给出的字段一律不改（保留类别典型值），prov 记为 typical 并进补档清单。

prov 字段来源标签
  tds        TDS 实测/规格值           sds        SDS 理化特性或成分表
  formula    SDS 分子式精确折算        tds_carry  由 TDS/SDS 值按标准换算或混合规则推导
  name       代码名自证（固含/稀释比）  typical    类别典型值（未替换）
"""
from __future__ import annotations
import re

KOH_M = 56.1           # g/mol
NCO_M = 42.02          # g/mol —N=C=O
O_XIRANE = 16.0        # g/mol 环氧氧
EEW_BPA_MONO = 171.1   # g/eq  DGEBA 单体（n=0）环氧当量
EEW_BPA_STEP = 284.4   # g/eq  每增加一个重复单元
MW = dict(C=12.011, H=1.008, O=15.999, N=14.007, S=32.06, Cl=35.45,
          Al=26.982, Ti=47.867, Si=28.085, P=30.974, Zn=65.38, Fe=55.845)


def formula_mass(fml):
    """'C6H12O3' → (分子量, {元素: 质量分数%})"""
    cnt, out = {}, {}
    for el, n in re.findall(r'([A-Z][a-z]?)(\d*)', fml):
        if not el:
            continue
        cnt[el] = cnt.get(el, 0) + (int(n) if n else 1)
    mw = sum(MW[e] * c for e, c in cnt.items())
    for e, c in cnt.items():
        out[e] = round(100.0 * MW[e] * c / mw, 2)
    return round(mw, 3), out


def fg_from_groups(fml, groups):
    """分子式 + 每分子官能团数 → mol/100g。"""
    mw, _ = formula_mass(fml)
    return {f'fg_{k}': round(v * 100.0 / mw, 5) for k, v in groups.items()}


def dgeba_ohv_dry(eew_dry):
    """DGEBA 系列固体羟值（mgKOH/g），由环氧当量按同系物结构推导。"""
    n = max(0.0, (eew_dry - EEW_BPA_MONO) / EEW_BPA_STEP)
    return 56100.0 * (n + 1.0) / (2.0 * eew_dry)


def mix_density(parts):
    """[(质量分数, 密度)] → 体积混合密度 g/cm³（按组分体积可加性）。"""
    ps = [(w, d) for w, d in parts if d and d > 0 and w > 0]
    tw = sum(w for w, _ in ps)
    if not ps or tw <= 0:
        return None
    v = sum(w / d for w, d in ps) / tw        # 单位总质量下的体积加成
    return round(1.0 / v, 3) if v > 0 else None


def wavg(parts):
    t = sum(w for w, v in parts if v is not None)
    return round(sum(w * v for w, v in parts if v is not None) / t, 2) if t > 0 else None


# ================================================================== 纯物质（SDS 给分子式/理化定值）
# fields 一律为到货（=纯品或登记稀释度）口径
PURE = {
    '正丁醇': dict(
        fml='C4H10O', nv=0.0, groups=dict(oh=1),
        fields=dict(density=0.810, bp=117.7, fp=35.0, evap=0.55, func=0),
        doc=['溶剂/正丁醇/正丁醇-TDS.md', '溶剂/正丁醇/正丁醇-MSDS.md'],
        依据='万华 工业正丁醇 TDS：正丁醇含量 ≥99.5%、密度(ρ20) 0.809~0.811、水分 ≤0.1%；'
             'SDS：C4H10O、沸点 117.7℃、闪点 35℃'),
    '二甲苯': dict(
        fml='C8H10', nv=0.0, groups=dict(arom=1),
        fields=dict(density=0.867, bp=138.0, fp=29.0, evap=0.70, func=0),
        doc=['溶剂/二甲苯/二甲苯-TDS.md', '溶剂/二甲苯/二甲苯-MSDS.md', '二甲苯_TDS_巨川化学品.md'],
        依据='二甲苯 SDS：分子量 106.2、分子式 C8H10、沸点（常压）136.68℃、闪点 29℃、相对密度 0.867；'
             'TDS：比重(15.56℃) 0.8650-0.8750；长春 AR785M1 SDS：挥发速率 0.7（乙酸丁酯=1）'),
    'TM004': dict(
        fml='C6H14O2', nv=0.0, groups=dict(oh=1, ether=1),
        fields=dict(density=0.900, bp=171.0, fp=63.2, evap=0.07, func=0),
        doc=['溶剂/乙二醇丁醚/乙二醇丁醚-SDS.md'],
        依据='乙二醇（单）丁醚 SDS：CAS111-76-2、分子式 C6H14O2、组分含量 ≥99%、'
             '熔点 -75℃、沸点 171℃、闪点（闭杯）63.2℃、相对密度 0.9'),
    'TM221': dict(
        fml='C6H14O2', nv=0.0, groups=dict(oh=1, ether=1),
        fields=dict(density=0.900, bp=171.0, fp=63.2, evap=0.07, func=0),
        doc=['溶剂/乙二醇丁醚/乙二醇丁醚-SDS.md'], 依据='同 TM004（乙二醇单丁醚，同一 SDS）'),
    'TZ221': dict(
        fml='C6H14O2', nv=0.0, groups=dict(oh=1, ether=1),
        fields=dict(density=0.900, bp=171.0, fp=63.2, evap=0.07, func=0),
        doc=['溶剂/乙二醇丁醚/乙二醇丁醚-SDS.md'], 依据='同 TM004（乙二醇单丁醚，同一 SDS）'),
    'TZ161': dict(
        fml='C6H12O3', nv=0.0, groups=dict(ester=1, ether=1),
        fields=dict(density=0.967, bp=145.8, fp=43.0, evap=0.10, func=0),
        doc=['溶剂/PMA/PMA-华伦-SDS.md', '溶剂/PMA/PMA-TDS.md', '溶剂/PMA/PMA-德纳-SDS.md'],
        依据='PMA SDS：CAS108-65-6、分子式 C6H12O3、分子量 132.16、沸点 145.8℃、闪点 45.5/42℃、'
             '密度 0.967、含量 ≥99.5%；TDS：比重(20℃) 0.965-0.975、水分 ≤0.05%'),
    'TZ240': dict(
        fml='C6H12O2', nv=0.0, groups=dict(ester=1),
        fields=dict(density=0.880, bp=126.1, fp=22.0, evap=1.0, func=0),
        doc=['溶剂/乙酸丁酯/乙酸丁酯-MSDS.md'],
        依据='乙酸丁酯 SDS：CAS123-86-4、分子量 116.16、熔点 -73.5℃、沸点 126.1℃、闪点 22℃、'
             '相对密度 0.88、主要成分 纯品'),
    'TT444': dict(
        fml='C4H8O', nv=0.0, groups=dict(),
        fields=dict(density=0.810, bp=79.6, fp=-9.0, evap=3.8, func=0),
        doc=['溶剂/丁酮/丁酮-MSDS.md'],
        依据='丁酮（甲乙酮）MSDS：CAS78-93-3、C4H8O、熔点 -85.9℃、沸点 79.6℃、'
             '相对密度 0.81、闪点 -9℃、蒸气压 9.49 kPa(20℃)'),
    'TT066': dict(
        fml='C6H10O', nv=0.0, groups=dict(),
        fields=dict(density=0.947, bp=156.0, fp=44.0, evap=0.30, func=0),
        doc=['溶剂/环己酮/环己酮-MSDS.md', '溶剂/环己酮/环己酮检验报告.md'],
        依据='环己酮 SDS：CAS108-94-1、熔点 -32.1℃、沸点 156℃、密度 950 g/L、闪点 44℃；'
             '检验报告：密度 ρ₂₀ 0.946、纯度 ≥99.5%（实测 99.92%）'),
    'TM982': dict(
        fml='C4H10O2', nv=0.0, groups=dict(oh=1, ether=1),
        fields=dict(density=0.921, bp=121.0, fp=39.0, evap=0.65, func=0),
        doc=['溶剂/PM/PM-SDS.md'],
        依据='丙二醇甲醚（PM）SDS：CAS107-98-2、C4H10O2、熔点 -96.7℃、沸点 117-125℃、'
             '闪点（开口）39℃、密度 0.918-0.924 g/cm³(20℃)'),
    'DPM': dict(
        fml='C7H16O3', nv=0.0, groups=dict(oh=1, ether=2),
        fields=dict(density=0.950, bp=194.0, fp=74.0, evap=0.02, func=0),
        doc=['溶剂/二丙二醇甲醚/二丙二醇甲醚-MSDS.md'],
        依据='二丙二醇甲醚 MSDS：CAS34590-94-8、分子式 C7H16O3、分子量 149.00、'
             '沸点 193-195℃、闪点 74℃、相对密度 0.95、主要成分 纯品；'
             'SDS 自列分子量 149.00 与分子式 C7H16O3 折算值 148.20 不符，本层按分子式取 148.20'),
    'MIBK': dict(
        fml='C6H12O', nv=0.0, groups=dict(),
        fields=dict(density=0.800, bp=116.5, fp=15.0, evap=2.7, Tg=-105.0, func=0),
        doc=['填料/色浆3010/苏州汉卓新材料_Nanos-3010B氧化铁红浆_MSDS.md', '助剂/消泡剂-BYK-018_TDS SDS.md'],
        依据='甲基异丁基甲酮 CAS108-10-1（色浆 MSDS 成分表：MIBK 约 10%、LD50 4300 mg/kg）；'
             '物性按 SDS 同 CAS 定值：C6H12O、100.16、沸点 116.5℃、闪点 15℃、密度 0.80'),
    'TM024': dict(
        fml='C8H18O3', nv=0.0, groups=dict(oh=1, ether=2),
        fields=dict(density=0.955, bp=231.0, fp=100.0, evap=0.01, Tg=-68.0, func=0),
        doc=['—（纯物质由分子式/档案族定值）'],
        依据='二乙二醇单丁醚（丁基卡必醇/BDG）CAS112-34-5：分子式 C8H18O3、分子量 162.23、'
             '相对密度 0.955、沸点 230-231℃、闪点 ~100℃（丙二醇醚乙二醇醚族档案；'
             '国都 YD-019 起始配方亦以 Butyl Carbitol 为稀释剂）'),
    '10%磷酸': dict(
        fml='H3PO4', nv=10.0, groups=dict(cooh=3), water=True,
        els_wet=dict(H=11.19, O=88.81),
        fields=dict(density=1.050, bp=100.0, fp=0.0, evap=1.4, func=3,
                    assay=85.2, acid_density=1.87, acid_mp=42.4, acid_bp=260.0),
        doc=['催化剂/武汉联德_工业磷酸_TDS.md', '催化剂/武汉联德_磷酸_SDS.md'],
        依据='工业磷酸 TDS 检验结果：磷酸（H3PO4）含量 85.2%（指标 ≥85.0）、氯化物（以Cl计）<0.0004%；'
             'SDS：CAS7664-38-2、相对密度（纯品）1.87、熔点 42.4℃、沸点 260℃；代码名自证 10% 水溶液'),
}
# 库内以别名指向同一 SDS 物质的代码
PURE_ALIAS = {'MEK': 'TT444', '外加正丁醇': '正丁醇', 'TM982b': 'TM982'}

# ================================================================== 产品档案（TDS/SDS 原文口径）
# basis='dry' 档案值即到货口径；'solution' 档案化学量按固体给出，NV 为到货固含。
PRODUCTS = {
    # ---------------- 环氧树脂 ----------------
    'YD-019': dict(
        name='EPOKUKDO YD-019 未改性双酚A型固体环氧树脂', vendor='国都化工（昆山）', cas='25036-25-3',
        doc=['环氧树脂/国都化工_YD-019_TDS_SDS.md', 'YD-019_TDS_国都化工.md', 'YD-019_MSDS_国都化工.md'],
        dry=dict(NV=100.0, EEW=2800.0, Mw=5600.0, Tg=132.5, density=1.18, bp=260.0, fp=249.0, func=2),
        res_solid=True,
        q=dict(EEW='TDS 树脂性能：EEW（环氧当量，g/eq）2,500~3,100（KD-AS-001）→ 中值 2800',
               Mw='SDS 理化特性：式量 5,000~6,200 → 中值 5600（≈2×EEW，与 DGEBA 结构一致）',
               Tg='TDS：软化点（℃）125~140（KD-AS-020 环球法）→ 中值 132.5',
               density='TDS：比重（20℃）1.16~1.20（KD-AS-040）', bp='SDS：沸点 >260℃',
               fp='SDS：闪点 >249℃',
               chem='TDS：未改性的双酚A型固体环氧树脂，专为高性能单组分烘烤涂料设计；'
                    '用途含可折叠管涂料、罐头涂料、PCM 涂料、漆包线漆'),
        use='TDS 起始配方：YD-019 30 份 + 溶剂 69 份 + Melan11（尿素树脂 NV60）11 份；固化 200℃×10min'),
    'SM601R-75': dict(
        name='SM601R-75 双酚A型环氧树脂溶液（二甲苯兑稀）', vendor='江苏三木集团', cas='25036-25-3',
        doc=['环氧树脂/江苏三木_SM601R-75_TDS_SDS.md', 'SM601R-75_TDS_江苏三木.md', 'SM601R-75_MSDS_江苏三木.md'],
        dry=dict(NV=75.0, EEW=480.0, Mw=960.0, Tg=55.0, density=1.16, func=2),
        res_solid=True, carrier=[('二甲苯', 25.0)],
        q=dict(EEW='TDS 技术指标：环氧当量（以100%树脂计）g/eq 450 - 510 → 中值 480（固体基）',
               NV='TDS：固体份（%）75 ± 1', density='固体环氧比重 1.16（同族 YD-019/SM601R），'
                                                    '溶液密度按载体二甲苯折算',
               bp='载体二甲苯 SDS：沸点 136.68℃、闪点 29℃',
               chem='TDS 基本特性：此环氧树脂溶液是二甲苯兑稀 SM601R 制得，粘度低、流动性好；'
                    '粘度（mPa·s/25℃）8000~19000、色泽 ≤1.0G、水解氯 ≤1000ppm')),
    'ETERKYD-50173-M-40': dict(
        name='ETERKYD 50173-M-40 高分子量聚酯（溶剂型）', vendor='长兴材料工业', cas='164002-50-0',
        doc=['聚酯树脂/ETERKYD_50173-M-40_TDS_长兴材料.md', '聚酯树脂/ETERKYD_50173-M-40_SDS_长兴材料.md'],
        dry=dict(NV=40.0, AV=6.0, OHV=6.5, Tg=56.0, Mw=18000.0, density=0.98, func=2),
        sb=('AV', 'OHV'),
        carrier=[('100号溶剂油', 48.0), ('TZ161', 6.0), ('TT066', 6.0)],
        q=dict(AV='TDS 产品规格：酸价 (mg KOH/g, solid) 5.00~7.00 → 中值 6.0（固体基）',
               OHV='TDS：OH价 (mg KOH/g, solid) 4.50~8.50 → 中值 6.5（固体基）',
               Tg='TDS：玻璃转化点 (Tg, °C) 56', Mw='TDS：Mn (±2000) 18,000',
               NV='TDS：溶剂 S100 / PMA / ANO；牌号 -M-40 即 40% 固含（与送检组成 39~41% 一致）',
               density='SDS 理化：相对密度（水=1）0.98（到货液体）',
               chem='TDS：溶剂型高分子聚酯，可与酚醛树脂、氨基树脂、封闭型多异氰酸酯搭配；'
                    '杀菌型烘烤罐头涂料；建议配方 聚酯/酚醛 = 70/30（固含量），205℃×12min'),
        use='TDS 建议配方：50173-M-40 100 份 + ETERPHEN 8219-B-50 34.3 份 + 磷酸 0.47 份；'
            '性能：T-bend 0TC/4TT、MEK 擦拭 25 次、铅笔硬度 2H'),
    'ETERKYD-50561-R-60': dict(
        name='ETERKYD 50561-R-60 饱和聚酯树脂（烤漆用）', vendor='长兴材料（天津）', cas='926925-64-6',
        doc=['聚酯树脂/ETERKYD_50561-R-60_TDS_长兴材料.md', '聚酯树脂/ETERKYD_50561-R-60S_SDS_长兴材料.md'],
        dry=dict(NV=60.0, AV=9.0, density=0.98, func=2), sb=('AV',),
        carrier=[('100号溶剂油', 32.0), ('CAC', 8.0)],
        q=dict(AV='TDS 规格参数：酸价 (mg KOH/g, solid) 6-12 → 中值 9.0（固体基）',
               NV='TDS：固成份 (%) 60；溶剂 Solvesso 150 / Cellosolve acetate',
               density='SDS：相对密度（水=1）约0.98（到货液体）',
               chem='TDS：白可丁用饱和聚酯树脂；粘度（Gardner-Holdt @25℃）Z3-Z5、色数 2 max；'
                    '相容性：EPON828 完全相容、Melamine 有限'),
        note='TDS 未给 Tg/Mn/羟值 → 该三项仍为类别典型值'),
    'ETERKYD-50177': dict(
        name='ETERKYD 50177 高分子量聚酯树脂', vendor='长兴材料', cas='（SDS：高分子量聚酯）',
        doc=['聚酯树脂/ETERKYD_50177_TDS_长兴材料.md', '聚酯树脂/ETERKYD_50177_SDS_长兴材料.md',
             '聚酯树脂/ETERKYD_50176_TDS_长兴材料.md'],
        dry=dict(NV=100.0, Mw=15000.0, Tg=80.0, OHV=7.0, AV=6.0, density=1.265, func=2),
        res_solid=True, sb=('OHV', 'AV'),
        carrier=[('100号溶剂油', 60.0)],
        q=dict(Mw='TDS：分子量 (Mn) 15000 ± 2000', Tg='TDS：玻璃转化点 (Tg) 80°C',
               chem='SDS 别名：高分子量聚酯树脂 —— 旧库把代码「40%50177」登记为环氧树脂，按 SDS 化学类别改归聚酯',
               OHV='同族 ETERKYD 50176 TDS：羟值 (mg KOH/g solid) 5-9 → 中值 7；'
                   '同族 50173 TDS：羟值 5-9（固体基）',
               density='SDS：相对密度（水=1）1.25-1.28（固体树脂）、软化点 >120℃；溶液按载体折算'),
        note='50177 本体 TDS 未列羟值/酸价，取同族 50176/50173 档案值（口径 TDS同族）'),
    'ETERKYD-50170-M-52': dict(
        name='ETERKYD 50170-M-52 高分子量聚酯', vendor='长兴材料',
        doc=['聚酯树脂/ETERKYD_50170-M-52_TDS_长兴材料.md', '聚酯树脂/ETERKYD_50170-M-52_MSDS_长兴材料.md'],
        dry=dict(NV=52.0, Tg=52.0, density=1.00, Mw=18000.0, OHV=6.5, AV=6.0, func=2),
        sb=('OHV', 'AV'),
        carrier=[('100号溶剂油', 40.0), ('TZ161', 8.0)],
        q=dict(Tg='TDS：玻璃转化点 (Tg °C) 52；粘度 Z1-Z2',
               NV='TDS 牌号 -52 → 52% 固含（旧库按同族误记 40%）',
               density='SDS：相对密度（水=1）0.95-1.05 → 中值 1.00；闪点 38℃（闭杯）',
               chem='TDS 标题：ETERKYD 50170-M-52 高分子量聚酯',
               Mw='同族 ETERKYD 50173-M-40 TDS：Mn 18,000（±2000）',
               OHV='同族 50173-M-40 TDS：OH价 4.50~8.50（固体基）')),

    # ---------------- 酚醛固化剂 ----------------
    'PHENODUR-PR401-72B': dict(
        name='PHENODUR PR 401/72B 可固化未增塑酚醛树脂（72% 正丁醇溶液）', vendor='湛新树脂（allnex）',
        doc=['酚醛树脂/上海长运-湛新/PR401-72B/PHENODUR_PR401-72B_TDS与SDS整合.md',
             'PHENODUR_PR401_72B_TDS_湛新树脂.md', 'PHENODUR_PR401_72B_MSDS_湛新树脂.md'],
        dry=dict(NV=72.0, density=1.03, bp=117.7, fp=35.0, func=3),
        carrier=[('正丁醇', 25.0)],
        q=dict(NV='TDS 技术指标：非挥发分 70–74%（DIN EN ISO 3251，1h/125℃/1g）；交付形式 72% 丁醇溶液',
               density='TDS：密度（20℃）约1.03 g/cm³（DIN EN ISO 2811-2）',
               bp='载体正丁醇 SDS：沸点 117.7℃、闪点 35℃',
               chem='SDS 成分：丁醇 CAS71-36-3 25%；双酚A CAS80-05-7 <2%；甲醛 CAS50-00-0 <1.5%',
               visc='TDS：动态粘度（23℃）200–1000 mPa·s（DIN 53177）；碘色值 ≤2'),
        use='TDS：罐体涂层 20–40% PR401 + 80–60% BECKOPOX EP307/EP309（固体分计）；'
            '烘烤 180–210℃/30–10min，薄膜 190–200℃/10–15min；推荐酸性催化剂 Additol XK406'),
    'PHENODUR-PR516-60B': dict(
        name='PHENODUR PR 516/60B 酚醛树脂（交联剂，60% 正丁醇溶液）', vendor='湛新树脂（allnex）',
        doc=['酚醛树脂/上海长运-湛新/PR516/PHENODUR_PR516-60B_TDS与SDS整合.md',
             'PHENODUR_PR516_60B_TDS_湛新树脂.md'],
        dry=dict(NV=60.0, density=1.03, bp=117.7, fp=30.0, func=3),
        carrier=[('正丁醇', 39.0)],
        q=dict(NV='TDS：非挥发分 58–62%（DIN EN ISO 3251，1h/135℃/2g；B）',
               density='TDS：密度（20℃）约1.03 g/cm³；闪点 约30℃（DIN EN ISO 1523）',
               chem='SDS 成分：丁醇 CAS71-36-3 39%；甲基苯酚（甲酚）1319-77-3 2–3%；甲醛 <1%',
               visc='TDS：动态粘度（23℃）150–500 mPa·s；碘色值 ≤150'),
        use='TDS：与高分子量环氧树脂（固体树脂计）混合比 1:2 至 1:4；完全固化需 190–210℃ 烘烤 10–20 分钟'),
    'PHENODUR-PR309-63B': dict(
        name='PHENODUR PR 309/63B/MP 酚醛树脂', vendor='湛新树脂（allnex）',
        doc=['酚醛树脂/上海长运-湛新/PR309/PHENODUR_PR309-63B-MP_TDS与SDS整合.md'],
        dry=dict(NV=65.0, density=1.03, func=3),
        q=dict(NV='TDS：非挥发分 ~65%（DIN EN ISO 3251，1h/135℃/2g；B）',
               chem='TDS：动态粘度 200–2500 mPa·s（DIN EN ISO 3219，23℃）')),
    'SUMILITERESIN-PR33160G': dict(
        name='SUMILITERESIN PR-33160G 烷基改性酚醛树脂（正丁醇/二甲苯溶液）', vendor='南通住友电木',
        cas='28453-20-5',
        doc=['酚醛树脂/住友/PR-33160/TDS_PR-33160G_CN.md', '酚醛树脂/住友/PR-33160/SDS_PR-33160G_CN_2021.md'],
        dry=dict(NV=72.0, bp=117.0, fp=44.0, func=3.5),
        q=dict(NV='TDS 树脂特性：不挥发份 %/135℃ = 72；粘度 mPa·s/25℃ = 2300',
               bp='SDS：沸点 117°C', fp='SDS：闪点 44°C（Tag式闭环）',
               chem='SDS 成分：改性酚醛树脂 CAS28453-20-5 60-80%；二甲苯 10-30%；丁醇 5-10%；'
                    '杂质 丁基苯酚 1-5%、甲醛 <2%',
               density='固体树脂比重取 1.05（同族住友 PR-34419 TDS：比重 1.10，此处按树脂+载体折算）'),
        use='TDS：用于金属表面涂层，作为涂料主剂的固化剂使用，具有优异的柔韧性；使用正丁醇、二甲苯作为溶剂'),
    'ETERPHEN-8219-B-50': dict(
        name='ETERPHEN 8219-B-50 热固型酚醛树脂（正丁醇溶液）', vendor='长兴材料', cas='65733-81-5',
        doc=['酚醛树脂/长兴/8129-B-50/8219-B-50_TDS.md', '酚醛树脂/长兴/8129-B-50/8219-B-50_SDS_简中.md',
             '酚醛树脂/长兴/8129-B-50/8219-B-50_相关资料_SDS.md'],
        dry=dict(NV=50.0, density=1.005, bp=117.0, fp=31.0, func=3),
        carrier=[('正丁醇', 48.7)],
        q=dict(NV='TDS 规格：固成分（%，105°C×3hrs×1g）48.5-51.5% → 中值 50；黏度 C-F',
               density='SDS：相对密度（水=1）1.005',
               bp='SDS：初馏点和沸点范围（°C）116-118（正丁醇）；相关资料 SDS：138℃',
               fp='相关资料 SDS：闪点 31 ℃（闭杯）；简中 SDS：57℃（取闭杯低值口径）',
               chem='SDS：危险成分 正丁醇、甲醛 1.3%；VOC 487 g/L',
               visc='TDS：黏度 C-F（Gardner）'),
        use='TDS：金属内罐保护涂装，与环氧树脂及乙烯树脂相溶性佳；烘烤 400°F×10-20min；'
            '可与有机/无机磷酸盐类催化'),
    'ETERPHEN-8219-B-65': dict(
        name='ETERPHEN 8219-B-65 热固型酚醛树脂（正丁醇溶液）', vendor='长兴材料', cas='25053-96-7',
        doc=['酚醛树脂/长兴/8129-B-65/8219-B-65_TDS.md', '酚醛树脂/长兴/8129-B-65/8219-B-65_SDS.md'],
        dry=dict(NV=66.0, density=1.005, bp=138.0, fp=31.0, func=3),
        carrier=[('正丁醇', 33.7)],
        q=dict(NV='TDS：固含量（±1%）（105℃×3hrs×1g）66±1.5% → 中值 66；粘度（Gardner25℃）F~J',
               density='SDS：密度 1.005', bp='SDS：沸点/沸点范围 138°C',
               chem='SDS：危害成分 正丁醇、甲醛 1.3%', fp='同族 8219-B-50 SDS：闪点 31℃（闭杯）')),

    # ---------------- 氨基树脂交联剂 ----------------
    'A09-60LF': dict(
        name='A09-60LF 异丁基醚化三聚氰胺甲醛树脂', vendor='慧新化工', cas='68002-21-1',
        doc=['氨基树脂/慧新化工_A09-60LF_TDS.md', '氨基树脂/慧新化工_A09-60LF_SDS.md'],
        dry=dict(NV=60.0, density=0.985, bp=108.0, fp=37.0, func=5),
        q=dict(NV='TDS：固含量（%）60 ± 2；粘度（mPa·s25℃）1500 – 4500',
               density='SDS：相对比重（水=1）0.9848', fp='SDS：闪点（℃）37（闭杯）',
               bp='载体异丁醇：沸点 108℃',
               chem='送检组成：异丁基醚化三聚氰胺甲醛树脂 CAS68002-21-1 60%；异丁醇 38.7%；甲醛 1.3%')),
    'MELCROSS-83': dict(
        name='MELCROSS-83 混合醚型苯并胍胺甲醛树脂', vendor='—', cas='68002-26-6',
        doc=['氨基树脂/P.md', '氨基树脂/P (1).md'],
        dry=dict(NV=98.0, density=1.185, func=5),
        q=dict(NV='TDS：固体含量 ≥ 98%、不挥发份 > 98%、粘度（Gardner）Z1 – Z5、酸值 1 max',
               density='SDS：比重 1.17 ~ 1.20 g/cm³；挥发分（重量百分比）~ 1%',
               chem='TDS 产品特性：高烷基化度、低羟甲基含量、低亚氨基官能团（苯并胍胺系）')),
    'RESIMENE-CE8824': dict(
        name='Resimene CE8824 全烷基化苯代三聚氰胺甲醛树脂', vendor='INEOS Oligomers',
        doc=['氨基树脂/INEOS_CE8824_TDS.md', '氨基树脂/INEOS_CE8824_SDS.md'],
        dry=dict(NV=97.0, density=1.150, fp=46.0, func=5),
        q=dict(NV='TDS 供货形式：无溶剂，有效成分 > 97%',
               density='TDS：密度（25℃）1.138 – 1.162 g/ml（DIN 53217-4）',
               fp='TDS：闪点（Penskey-Martens）46℃',
               chem='TDS：动态粘度（23℃）3800–10200 mPa·s；甲醛含量（亚硫酸盐法）< 0.2%；'
                    '分子量分布 Mw/Mn（GPC）1.20')),

    # ---------------- 封闭型异氰酸酯 ----------------
    'WANNATE-ITBL-460S': dict(
        name='WANNATE ITBL-460S 封闭型聚异氰酸酯（己内酰胺封端 IPDI 型）', vendor='万华化学',
        doc=['异氰酸酯树脂/万华化学_WANNATE-ITBL-460S_TDS.md',
             '异氰酸酯树脂/万华化学_WANNATE-ITBL-460S_SDS.md'],
        dry=dict(NV=60.0, density=1.04, bp=170.5, fp=49.0, func=3, NCO=7.0),
        q=dict(NCO='TDS：封闭型NCO含量 ~7 %（到货口径）',
               NV='TDS：固含量 % 58.00 ~ 62.00 → 中值 60；粘度25°C 1000 ~ 3000 mPa·s',
               density='TDS：密度（20°C）~1.04 g/cm³',
               bp='SDS：沸点范围 170.5°C、闪点 49°C、蒸气压 2 kPa(20℃)、相对密度 1.04',
               chem='送检组成：己内酰胺封端IPDI聚异氰酸酯 CAS127184-53-6 57%；轻质芳香石脑油 40%；ε-己内酰胺 3%')),
    'BURNOCK-FH-075N': dict(
        name='BURNOCK FH-075N 封闭型 HDI 固化剂', vendor='爱敬化学（Aekyung）',
        doc=['异氰酸酯树脂/爱敬化学_FH-075N_TDS.md', '异氰酸酯树脂/爱敬化学_FH-075N_SDS.md'],
        dry=dict(NV=75.0, density=1.05, bp=125.6, func=3, NCO=11.0),
        q=dict(NCO='TDS：NCO含量（%）11 ± 0.5', NV='TDS：不挥发份（%）75 ± 1；比重 1.05',
               bp='SDS：沸点/沸点范围 125.6°C、蒸气密度 2.41、密度 1.15（水=1）',
               chem='送检组成：异氰酸酯预聚物（封端HDI）75%；醋酸丁酯 5%；丙二醇甲醚醋酸酯 20%')),

    # ---------------- 氯化烯类树脂 ----------------
    'VESTOLIT-G170-L140-UF': dict(
        name='Vestolit G 170-L140 UF 超高分子量 PVC 分散树脂', vendor='Mexichem/Vestolit',
        cas='9002-86-2', fml='C2H3Cl',
        doc=['烯类树脂/Mexichem_Vestolit_G170-L140-UF_TDS-SDS.md'],
        dry=dict(NV=100.0, density=1.40, Tg=82.0, func=0),
        q=dict(density='TDS：比重 1.4；堆积密度 28–37 lb/ft³',
               chem='TDS：特性粘度 (IV) 1.4（STP 1386）、含水量 0.09%、残留氯乙烯单体 ≤1 ppm、'
                    'North 细度 Hegman 6.25 —— 超高分子量PVC糊用分散树脂',
               formula='单体单元 C2H3Cl（CAS9002-86-2，SDS 分子式 (CH₂-CHCl)ₙ）→ C 38.4% / H 4.8% / Cl 56.8%'),
        note='TDS 未给数均分子量（仅特性粘度 IV=1.4）→ Mw 仍为类别典型值'),
    # ---------------- 助剂 ----------------
    'BYK-088': dict(
        name='BYK-088 消泡剂（聚烯烃/聚硅氧烷，烃类溶液）', vendor='毕克化学（BYK）',
        doc=['助剂/消泡剂-BYK-088_TDS SDS FoodContact.md', '助剂/BYK-088_SDS_安全技术说明书.md'],
        dry=dict(NV=3.3, bp=155.0, fp=38.0, func=0),
        q=dict(NV='TDS：不挥发份 3.3%',
               density='SDS：密度 0.7500 g/cm³(20℃)、初沸点 155.0℃、闪点 38℃、蒸气压 13.00 hPa、'
                       '运动黏度 <5.00 mm²/s、表面张力 21.70 mN/m',
               chem='SDS 成分：石脑油（石油）CAS64741-65-7 >50%；聚硅氧烷聚合物 3.3%；BHT <0.1%')),
    'BYK-306': dict(
        name='BYK-306 流平剂（聚醚改性聚二甲基硅氧烷溶液）', vendor='毕克化学（BYK）',
        doc=['助剂/流平剂-BYK-306_TDS SDS 食品接触声明.md', '助剂/BYK-306_SDS_安全技术说明书.md'],
        dry=dict(NV=12.5, density=0.928, bp=137.0, fp=25.0, func=0),
        carrier=[('二甲苯', 35.0)],
        q=dict(NV='TDS：不挥发份 12.5%（30 min/150℃）',
               density='SDS：密度 0.928 g/cm³、闪点 25℃、初沸点 137℃、蒸气压 8 hPa、运动黏度 2 mm²/s(40℃)',
               chem='SDS 成分：二甲苯 30–50%；2-苯氧基乙醇 20–25%；乙苯 12.5–20%；'
                    '链烯基-烷基-聚乙二醇醚 1–3%；八甲基环四硅氧烷 0.1–0.25%')),
    'BYK-P104S': dict(
        name='BYK-P 104 S 分散剂（低分子量不饱和多元羧酸聚合物+聚硅氧烷共聚物溶液）',
        vendor='毕克化学（BYK）',
        doc=['助剂/BYK-P104S_TDS_技术资料.md', '助剂/BYK-P104S_SDS_安全技术说明书.md'],
        dry=dict(NV=50.0, density=0.95, AV=150.0, fp=28.0, func=0),
        carrier=[('二甲苯', 40.0)],
        q=dict(AV='TDS：酸值 150 mgKOH/g', NV='TDS：不挥发份 50%；密度 0.95；闪点 28℃',
               chem='SDS 成分：顺丁烯二酸化硬脂酸 CAS85711-46-2 30–50%；二甲苯 30–50%；'
                    '乙基苯 12.5–20%；2,6-二甲基-4-庚酮 3–5%；顺丁烯二酸酐 0.25–0.5%')),
    'ACA-EAA1': dict(
        name='Capatue ACA-EAA1 偶联剂（（乙酰乙酸乙酯基）二异丙氧基铝酸酯）', vendor='南京能德',
        cas='14782-75-3', fml='C12H23O5Al', mw_from_formula=True, groups=dict(ester=1),
        doc=['助剂/偶联剂-南京能德Capatue_ACA-EAA1_TDS SDS.md'],
        dry=dict(NV=98.0, Mw=274.29, density=1.035, fp=75.0, func=1),
        q=dict(Mw='TDS：分子量 274.29、铝含量 9.5%、CAS14782-75-3、分子式 C12H23O5Al',
               density='SDS：密度 ρ25 1.035 g/cm³（比重 1.045）、闪点 75℃（闭杯）、黏度 10 泊(25℃)、遇水水解',
               NV='SDS 成分：（乙酰乙酸乙酯基）二异丙氧基铝酸酯 ≥98%',
               groups='分子式 C12H23O5Al：每分子 1 个酯基（乙酰乙酸乙酯基）→ fg_ester=100/274.29')),
    'ESO-O-130C': dict(
        name='环氧大豆油 O-130C（增塑剂/环氧改性剂）', vendor='常熟艾迪科', cas='8013-07-8',
        doc=['助剂/常熟艾迪科-环氧大豆油_O-130C_TDS SDS.md'],
        dry=dict(NV=99.0, Mw=1000.0, density=0.992, AV=0.5, fp=311.0, func=4, ESO=6.6),
        q=dict(ESO='TDS：环氧数 ≥6.6%（氧含量法）→ EEW=1600/6.6=242 g/eq，fg_epoxy=0.4125 mol/100g',
               Mw='TDS：分子量 ≈1000；酸价 ≤0.5；碘价 ≤3.0（WIJS）',
               density='TDS：比重 0.982–1.002（25/25）、密度 0.992(25℃)、黏度 350–450 cps、'
                       '折射率 1.470±0.002、凝固点 5℃、闪点 311℃（开杯）、加热减量 ≤0.2%、色数 ≤200 APHA',
               chem='SDS 成分：环氧豆油 CAS8013-07-8 ≥99%')),
    'TYZOR-GBA': dict(
        name='TYZOR GBA 有机钛酸盐催化剂（乙酰丙酮钛螯合物/异丙醇）', vendor='Dorf Ketal（上海邦硕）',
        cas='150702-37-7',
        doc=['催化剂/上海邦硕_Tyzor-GBA_TDS.md', '催化剂/上海邦硕_Tyzor-GBA_SDS.md'],
        dry=dict(NV=75.0, density=1.02, bp=70.0, fp=12.0, func=3, TiO2=16.4),
        q=dict(NV='TDS：活性含量 75%、TiO₂ 含量 16.4%、比重（25°C）1.02、粘度 60 mPa·s',
               bp='TDS/SDS：沸点（°C）70、闪点（°C）12（Pensky-Martens）、相对密度（25°C）1.02、与水混溶',
               chem='送检组成：钛螯合物（乙酰丙酮钛/丁醇/异丙醇/甲醇）CAS150702-37-7 60-80%；异丙醇 13-30%')),

    'TIOXIDE-Rutile': dict(
        name='金红石型钛白粉（R2 级）', vendor='Venator / 中信钛业 / 科慕', cas='13463-67-7',
        doc=['填料/钛白粉/Venator_TIOXIDE_TR92_TDS.md', '填料/钛白粉/中信钛业_CITIC_CR-510_TDS.md',
             '填料/钛白粉/科慕_Chemours_Ti-Pure_R-960_TDS.md'],
        dry=dict(NV=100.0, TiO2=94.0, density=4.10, dbp=18.0, D50=0.26),
        q=dict(TiO2='Venator TR92 TDS：TiO₂ 94%、比重 4.1 g/cm³、吸油量 18 cm³/100g（ISO 787/5）、'
                   '晶粒 0.24 μm、无机涂层 氧化铝+氧化锆；中信 CR-510 TDS：TiO₂ 94.5%、比重 4.1、'
                   '吸油量 17.5 g/100g、平均粒径 0.27 μm、pH 7.5；科慕 R-960 TDS：TiO₂ ≥89%、比重 3.9',
               chem='ISO 591 R2 / ASTM D-476 II；C.I. 77891；密度按 R2 级氯化法金红石档案值')),
    # ---------------- 蜡 / 二氧化硅 / 纤维素 ----------------
    'LANCO-1510-EF': dict(
        name='Lanco 1510 EF 微粉化聚烯烃蜡', vendor='路博润（Lubrizol）', cas='8002-74-2',
        doc=['蜡/路博润/LANCO-1510-EF_TDS.md', '蜡/路博润/LANCO-1510-EF_SDS.md'],
        dry=dict(NV=100.0, density=0.96, bp=350.0, fp=200.0, mp=106.0, func=0, D50=5.0),
        q=dict(density='TDS：密度 0.96（25℃）、相对密度 0.96（20℃）、熔点 106℃',
               chem='SDS 成分：烃蜡和石蜡 CAS8002-74-2 50–<100%；粒径 Dv50 ≤5.0 μm、Dv90 ≤9.5 μm')),
    'SYLOID-7000': dict(
        name='SYLOID 7000 有机处理无定形二氧化硅（消光/防沉剂）', vendor='W. R. Grace', cas='7631-86-9',
        doc=['助剂/格蕾丝_SYLOID-7000_TDS_技术资料.md', '填料/铝银浆/Grace_SYLOID7000_SDS.md'],
        dry=dict(NV=100.0, density=1.40, bp=350.0, fp=200.0, func=0, SiO2=99.4, dbp=300.0, D50=4.6),
        q=dict(dbp='TDS：吸油量 300 g/100g、平均粒径 4.2–5.0 μm（Malvern）、孔隙率 2.0 ml/g、'
                  'SiO₂ 典型 99.4%、碳含量 5.5–7.5%、总挥发物(950℃) ≤15.0%、pH 2.9–3.7(5%悬浮液)',
               density='SDS：密度（20℃）约 1.126~1.669 g/cm³ → 取中值 1.40；堆积密度 200–600 kg/m³；'
                       '固体含量 100.0%；闪点 >200℃、沸点 350℃')),
    'CAB-381-2': dict(
        name='Eastman CAB 381-2 醋酸丁酸纤维素', vendor='伊士曼（Eastman）', cas='9004-36-8',
        doc=['助剂/流平剂-伊士曼Eastman_CAB-381-2_TDS SDS.md'],
        dry=dict(NV=100.0, Mw=40000.0, density=1.20, Tg=133.0, func=0,
                 OH_pct=1.3, acetyl=13.5, butyryl=38.0, mp=177.5),
        sb=('OH_pct',),
        q=dict(Mw='TDS：Mn 40000、Tg 133℃、黏度 7.6 poise、折射率 1.475、Tukon 硬度 18 Knoop',
               chem='TDS：丁酰基 38%、乙酰基 13.5%、羟基 1.3%；酸度（乙酸计）<0.03%、灰分 0.05%、'
                    '颜色 125 ppm、浊度 35 ppm、松装 352 / 振实 465 kg/m³',
               density='TDS：比重 1.2；熔点 171–184℃')),
    'SUNRUNS-LY815-C': dict(
        name='Sunruns LY815-C 非浮型铝银浆', vendor='旭阳（Sunruns）', cas='7429-90-5',
        doc=['填料/铝银浆/Sunruns旭阳_LY815-C_TDS_SDS.md'],
        dry=dict(NV=57.0, density=1.55, func=0, bp=172.5, fp=49.4),
        q=dict(NV='TDS：固含量 57 ± 2 %（企业标准）；325 目筛余 ≤0.1%（ISO 1247）；'
                  'D50 7 ± 2 μm（ISO 13320）；水分 ≤0.15%（ISO 760）',
               density='TDS：比重 1.45–1.65 kg/l（ASTM D1475）→ 中值 1.55',
               chem='SDS 成分：铝 7429-90-5 50–80%；轻芳烃溶剂石脑油 64742-95-6 19.5–49%；'
                    '油酸 112-80-1 0.5–1%；闪点（闭杯，溶剂部分）<61℃；铝熔点 660℃'),
        note='TDS 不给吸油量 → dbp 保留原公开典型值口径'),
    # ---------------- 溶剂（混合物折算用，非直接登记代码） ----------------
    'SOLVENT-N100': dict(
        name='100号溶剂油（轻芳烃溶剂石脑油 S-100）', vendor='—', cas='64742-95-6',
        doc=['溶剂/100号溶剂油/S-100B溶剂油-TDS.md', '溶剂/100号溶剂油/S-100溶剂油-SDS.md'],
        dry=dict(NV=0.0, density=0.872, bp=160.0, fp=43.0, func=0, evap=0.40, aromatics=98.0),
        q=dict(density='TDS：Density@20℃ 0.865-0.880 kg/dm³（ASTM D4052）→ 中值 0.872',
               fp='TDS：Flash Point 45℃ min（ASTM D56）；SDS：闪点 ≥42℃',
               chem='SDS：CAS 64742-95-6、芳烃含量 98 vol% min、沸点范围 ≤260℃、熔点 <-60℃'),
        note='混合物（石脑油），分子量/元素组成按芳烃主体折算'),
    'SOLVENT-DBE': dict(
        name='DBE 混合二元酸二甲酯（丁二酸/戊二酸/己二酸二甲酯）', vendor='—',
        doc=['溶剂/DBE/DBE-MSDS.md'],
        dry=dict(NV=0.0, density=1.081, bp=210.0, fp=100.0, mp=-20.0, evap=0.10, func=0, Mw=160.0),
        groups=dict(ester=2),
        q=dict(density='SDS：相对密度（水=1）1.070-1.092 → 中值 1.081；比重 1.092(20℃)',
               bp='SDS：沸点（℃）190-230 → 中值 210；闪点（℃）100（TCC）；熔点 约-20',
               evap='SDS 其他理化性质：蒸发速率 <0.1（乙酸丁酯=1.0）、挥发性 100%（20℃）',
               chem='SDS 成分：丁二酸二甲酯/戊二酸二甲酯/己二酸二甲酯（每分子 2 个酯基）',
               groups='平均分子量 160、每分子 2 个酯基 → fg_ester=2×100/160=1.25 mol/100g')),
    'SOLVENT-CAC': dict(
        name='乙二醇乙醚醋酸酯（CAC）', vendor='—', cas='111-15-9', fml='C5H10O3',
        doc=['溶剂/乙二醇乙醚/乙二醇乙醚醋酸酯-MSDS.md'],
        dry=dict(NV=0.0, density=0.978, bp=156.0, fp=43.0, func=0, evap=0.08),
        q=dict(chem='SDS：CAS111-15-9、分子式 C5H10O3、分子量 118.13、密度 0.978、沸点 156℃、闪点 43℃')),
}
# 载体（用于溶液物性折算）
CARRIER = {
    '二甲苯': dict(density=0.867, bp=138.0, fp=29.0, evap=0.70),
    '正丁醇': dict(density=0.810, bp=117.7, fp=35.0, evap=0.55),
    '异丁醇': dict(density=0.802, bp=108.0, fp=28.0, evap=1.00),
    '异丙醇': dict(density=0.786, bp=82.4, fp=13.0, evap=1.90),
    '水': dict(density=1.000, bp=100.0, fp=0.0, evap=1.40),
    '100号溶剂油': dict(density=0.872, bp=160.0, fp=43.0, evap=0.40),
    'TZ161': dict(density=0.967, bp=145.8, fp=43.0, evap=0.10),
    'TT066': dict(density=0.947, bp=156.0, fp=44.0, evap=0.30),
    'CAC': dict(density=0.978, bp=156.0, fp=43.0, evap=0.08),
    'PHENODUR-PR309-63B': dict(density=1.030, bp=117.7, fp=35.0, evap=0.05),
}

# ================================================================== 族推断层（FAMILY）
# 对档案内「牌号未识别」的原料：不套用通用典型值，而是用**同化学族在档案中的实测值**
# 缩小范围近似（用户口径：间接推出组成后近似计算，向实际情况靠拢）。来源标 FAMILY 而非实测，
# 保留可追溯依据；一旦按物料编码确认牌号即可升级为直接实测。
# fields 一律为**到货状态**值（含稀释），EEW/OHV/AV 按到货基给出，fg_* 由 unify 派生。
FAMILY = {
    # ---- 丙烯酸多元醇（聚酯金黄/配比方案在用，牌号未识别）----
    # 档案族：SU-4660(NV60±2/羟值70供应·116固体/酸值<6/比重1.03)、HYC-R926(NV60/羟值26固体/酸值5-9/密度1.05)、
    #        SETALUX1187(NV60/OH 3.6%/酸值2.3-4.9/密度1.01)、RB819(NV55-59/酸值7-10)、NeoCrylB-725(Tg63)
    'IA151': dict(role='树脂', rtype='丙烯酸', nv=60.0,
                  fields=dict(OHV=70.0, AV=5.0, density=1.04, Mw=18000.0, Tg=38.0, func=2,
                              bp=150.0, fp=40.0, evap=0.1, C=66, H=9, O=25, N=0, S=0, Cl=0),
                  依据='丙烯酸多元醇 档案族 NV≈60：SU-4660 羟值70(供应)、酸值<6、比重1.03；'
                      'HYC-R926 酸值5-9、密度1.05；牌号未识别 → 族内取中值'),
    'IA800': dict(role='树脂', rtype='丙烯酸', nv=60.0, copy_from='IA151',
                  依据='同 IA151（丙烯酸多元醇 族档案值）'),
    'IA8000': dict(role='树脂', rtype='丙烯酸', nv=60.0, copy_from='IA151',
                   依据='同 IA151（丙烯酸多元醇 族档案值）'),
    'IA893': dict(role='树脂', rtype='丙烯酸', nv=60.0, copy_from='IA151',
                  依据='同 IA151（丙烯酸多元醇 族档案值）'),
    'AL800': dict(role='树脂', rtype='丙烯酸', nv=60.0, copy_from='IA151',
                  依据='同 IA151（丙烯酸多元醇 族档案值）'),
    # ---- 烯类/氯醋（聚酯金黄在用，牌号未识别）----
    # 档案族：MVAH 氯醋(Tg79/Mn27000/比重1.39)、VMA(Tg70/Mn15000)、Vinnolit P70/PVC(密度1.4)
    'TF100': dict(role='树脂', rtype='乙烯基', nv=25.0,
                  fields=dict(density=1.00, Mw=20000.0, Tg=72.0, func=0, bp=160.0, fp=60.0,
                              C=42, H=5, O=13, N=0, S=0, Cl=40),
                  依据='氯醋/PVC 档案族（MVAH Tg79/Mn27000/比重1.39 氯乙烯~90%、VMA Tg70/Mn15000）；'
                      'NV25 为溶液自证口径，固体密度1.39、Cl≈40%'),
    'TF022': dict(role='树脂', rtype='乙烯基', nv=25.0, copy_from='TF100',
                  依据='同 TF100（氯醋/PVC 族档案值）'),
    # ---- 聚酯（1873 / CN7-18-60，档案缺失 → ETERKYD 聚酯族）----
    'RJ183': dict(role='树脂', rtype='聚酯', nv=40.0,
                  fields=dict(OHV=2.6, AV=2.4, density=0.98, Mw=18000.0, Tg=52.0, func=2,
                              bp=158.0, fp=43.0, evap=0.35, C=66, H=8, O=26, N=0, S=0, Cl=0),
                  依据='ETERKYD 聚酯族（50173-M-40 TDS：OH价4.5-8.5固体→到货≈2.6、酸价5-7固体→2.4、'
                      'Tg56/Mn18000/密度0.98）；牌号 1873 无档案 → 族内取'),
    'RJ362': dict(role='树脂', rtype='聚酯', nv=60.0,
                  fields=dict(OHV=3.9, AV=5.4, density=0.98, Mw=18000.0, Tg=56.0, func=2,
                              bp=159.0, fp=43.0, evap=0.34, C=66, H=8, O=26, N=0, S=0, Cl=0),
                  依据='ETERKYD 聚酯族（50561-R-60 TDS：固含60/酸价6-12固体；50173-M-40 OH价/酸价同族）；'
                      '牌号 CN7-18-60 无档案 → 族内取'),
    # ---- 环氧（中分子量双酚A型，牌号未识别；旧库有同族多行同值退化）----
    # 档案族：YD-011(EEW450-500/74-76%)、SM601R(450-510/75%)、YD-019(2500-3100固体)、HY-2801(5500-7500/40%)
    'IR877': dict(role='树脂', rtype='环氧', nv=60.0,
                  fields=dict(EEW=3900.0, OHV=26.0, density=1.07, Mw=2400.0, Tg=82.0, func=2,
                              bp=138.0, fp=32.0, evap=0.62, C=73, H=7, O=19, N=0, S=0, Cl=0),
                  依据='双酚A型环氧 中高分子量族（HY-2801 EEW5500-7500@40%、HY-5100 6000-8000@40%、'
                      'YD-019 2500-3100固体）；NV60 溶液 → 到货 EEW≈3900、轻值26'),
    'IR909': dict(role='树脂', rtype='环氧', nv=60.0, copy_from='IR877',
                  依据='同 IR877（双酚A型环氧 族档案值；聚酯金黄主用环氧）'),
    'IR557': dict(role='树脂', rtype='环氧', nv=60.0, copy_from='IR877',
                  依据='同 IR877（双酚A型环氧 族档案值）'),
    'IR868': dict(role='树脂', rtype='环氧', nv=60.0, copy_from='IR877',
                  依据='同 IR877（双酚A型环氧 族档案值）'),
    'IR842': dict(role='树脂', rtype='环氧', nv=60.0, copy_from='IR877',
                  依据='同 IR877（双酚A型环氧 族档案值）'),
    'IR170': dict(role='树脂', rtype='环氧', nv=50.0, copy_from='IR877',
                  依据='同 IR877（双酚A型环氧 族档案值；NV50 代码自证）'),
    'R170M': dict(role='树脂', rtype='环氧', nv=60.0, copy_from='IR877',
                  依据='同 IR877（双酚A型环氧 族档案值）'),
    '杜邦-FT960': dict(role='树脂', rtype='环氧', nv=55.0, copy_from='IR877',
                       依据='同 IR877（双酚A型环氧 族档案值；杜邦牌号未匹配到档案，NV 取旧库）'),
    '住友55754G': dict(role='树脂', rtype='环氧', nv=100.0,
                       fields=dict(EEW=1050.0, OHV=30.0, density=1.16, Mw=1600.0, Tg=80.0, func=2,
                                   bp=300.0, fp=249.0, evap=0.0, C=73, H=7, O=19, N=0, S=0, Cl=0),
                       依据='库内登记为固体环氧（NV100）；若为住友 SUMILITERESIN 酚醛系列则角色应改固化剂，'
                           '待物料编码核定（现按固含环氧/中分子量处理）'),
    # ---- 蜡（送检类别已明，牌号无档案 → 蜡族）----
    'AL525': dict(role='助剂', rtype='其他', nv=100.0,
                  fields=dict(density=0.96, Mw=400.0, Tg=-10.0, func=0, bp=350.0, fp=200.0,
                              C=72, H=11, O=17, N=0, S=0, Cl=0),
                  依据='送检：单油酸甘油酯蜡 LHWAX2525A；蜡族档案 LANCO1510 微粉蜡 密度0.96/熔点106℃'),
    'AL710': dict(role='助剂', rtype='其他', nv=35.0,
                  fields=dict(density=0.90, Mw=500.0, Tg=-10.0, func=0, bp=160.0, fp=80.0,
                              C=82, H=14, O=4, N=0, S=0, Cl=0),
                  依据='送检：合成蜡分散体 TPG-710（固含35%）；蜡族档案（LANCO-WD420 固含19-21% 同属性）'),
    # ---- 助剂/流平剂 AZ551 = BYK-3550（毕克 TDS/SDS 直接匹配，硅改性丙烯酸酯共聚物/PM溶剂）
    'AZ551': dict(role='助剂', rtype='其他', nv=52.0,
                  fields=dict(density=1.006, Mw=15000.0, Tg=5.0, func=0, bp=146.0, fp=45.0,
                              evap=0.05, C=50, H=7, O=20, N=0, S=0, Cl=0),
                  依据='毕克 BYK-3550 TDS/SDS：硅改性聚丙烯酸酯溶液，不挥发份 52%（10min/150℃）、'
                      '密度 1.006 g/cm³（20℃）、溶剂为甲氧基丙酸甲酯(PMA)、初沸点 146℃、闪点 45℃'),
    'FL208': dict(role='助剂', rtype='其他', nv=60.0, copy_from='AZ551',
                  依据='通用流平剂（档案未收录 BYK/WEK 适配牌号），暂按硅改性丙烯酸酯流平剂族近似'),
    'FL208S': dict(role='助剂', rtype='其他', nv=52.0, copy_from='AZ551',
                   依据='通用流平剂（档案未收录对应牌号），暂按硅改性丙烯酸酯流平剂族近似'),
    # ---- 颜料（牌号未识别的黄/黑/PVC 浆）----
    'RY078': dict(role='颜料', rtype='其他', nv=100.0,
                  fields=dict(density=1.80, Mw=200.0, func=0, DBP=50.0, C=50, H=5, O=20),
                  依据='有机黄颜料族：华宝 PY110(密度1.7-1.9/吸油量40-80)、PY138(1.852/30-60)；取中值'),
    '6#炭黑-阿克苏': dict(role='颜料', rtype='其他', nv=100.0,
                           fields=dict(density=1.85, Mw=12.01, func=0, DBP=95.0, C=80, H=2, O=10),
                           依据='色素炭黑物理常数：真密度~1.85、DBP~95、比表面积高（档案内无炭黑条，手册定值）'),
    '14.28%炭黑浆料': dict(role='颜料', rtype='其他', nv=14.28,
                           fields=dict(density=1.10, Mw=12.01, func=0, DBP=95.0, C=80, H=2, O=10),
                           依据='炭黑浆料（干料同 6#炭黑；14.28% 固含为代码自证，浆料密度按分散体折算）'),
    '日本151-PVC': dict(role='颜料', rtype='其他', nv=100.0,
                        fields=dict(density=4.10, Mw=200.0, func=0, DBP=25.0, C=10, H=0, O=20),
                        依据='PVC 颜料浆（候选氧化铁黄 TSY-1/拜耳乐3920 真比重4.1、吸油量25-35）；'
                            '牌号不完全确定，按氧化铁黄族近似'),
}
# 颜料相对颜色密度（用于 mech_desc.LIT 的 DBP 实测替换）
LIT_FAMILY = {
    'RY078': dict(dbp=50.0, 依据='有机黄族 PY110/PY138 TDS 吸油量 30-80 → 50'),
    '6#炭黑-阿克苏': dict(dbp=95.0, 依据='色素炭黑手册定值'),
    '14.28%炭黑浆料': dict(dbp=95.0, 依据='同 6#炭黑'),
    '日本151-PVC': dict(dbp=25.0, 依据='有机颜料浆（保留原口径）'),
}
# 补档清单：族推断仍无法覆盖的歧义/未定义原料
FAMILY_PENDING = {
    'DMP': '缩写歧义（丙二醇二甲醚/邻苯二甲酸二甲酯/二甲氨基丙醇），需物料编码确认',
    '209-基料': '与「209-白浆」配对出现的基料，组成未记录',
}


def _family_fields(code):
    """族推断：用同化学族档案值近似（到货状态字段，来源=family）。"""
    f = FAMILY[code]
    if f.get('copy_from'):
        base = FAMILY[f['copy_from']]
        f = {**base, **{k: v for k, v in f.items() if k in ('role', 'rtype', 'nv',
                                                             '依据', 'fields', 'copy_from', 'wax', 'pig')}}
        if 'fields' in base and f.get('fields') is None:
            f['fields'] = base['fields']
    fld = dict(f['fields'])
    fld['NV'] = f['nv']
    fld['role'] = f.get('role', '其他')
    fld['rtype'] = f.get('rtype', '其他')
    prov = {'NV': 'name', 'role': 'family', 'rtype': 'family'}
    for k in fld:
        if k in ('role', 'rtype'):
            continue
        prov[k] = 'family'
    if f.get('wax'):
        fld['wax'] = f['wax']
    if f.get('pig'):
        fld['pig'] = f['pig']
    docs = []
    q = f['依据']
    return fld, prov, docs, q, {'chem': q, '来源': 'TDS族推（牌号未识别，按同化学族档案近似）'}


# ================================================================== 原料代码 → 档案
CODE_MAP = {
    # ---- 环氧 ----
    'IR190': dict(pid='YD-019', nv=36.0, carrier=[('二甲苯', 32.0), ('正丁醇', 32.0)],
                  依据='库内登记名「9型环氧树脂36%固含」→ 双酚A型 DGEBA 平均取代度 n≈9'
                       '（EEW=171.1+284.4n≈2730），与国都 YD-019 TDS（EEW 2500~3100、式量 5000~6200、'
                       '软化点 125~140）一致；同型 40% 溶液牌号（安徽新远 HY-2801 EEW 5500~7500/不挥发份 39~41、'
                       '安徽恒远 HY-5100 EEW 6000~8000/39~41）亦按到货状态给出该量级环氧当量',
                  carrier_依据='载体未登记，按库内同体系常用溶剂（二甲苯/正丁醇）等比折算密度·沸点·闪点'),
    'IR191': dict(pid='YD-019', nv=36.0, carrier=[('二甲苯', 32.0), ('正丁醇', 32.0)],
                  依据='库内登记名与 IR190 同类（9型环氧树脂 36% 固含）'),
    'RH601': dict(pid='SM601R-75', nv=75.0,
                  依据='库内代码 RH601（SM601RX75）→ 江苏三木 SM601R-75 双酚A型环氧树脂溶液'),
    'IR809': dict(pid='YD-019', nv=55.0, carrier=[('PHENODUR-PR309-63B', 45.0)],
                  依据='库内登记名「IR809 55%(PR309 稀释55%)」：固体环氧以 PHENODUR PR309/63B 酚醛溶液'
                       '配至 55% 总固含（PR309 档案：非挥发分 ~65%、密度 ~1.03）',
                  role_note='保持树脂角色；载体 PR309 为酚醛，其酚羟基当量由 RF* 档案单独提供'),
    '40%50177': dict(pid='ETERKYD-50177', nv=40.0, rtype='聚酯',
                     依据='牌号 50177 → 长兴 ETERKYD 50177；SDS 化学名称「高分子量聚酯树脂」。'
                          '旧库登记为「环氧树脂40%固含」与 SDS 类别矛盾，此处按 SDS 归正为聚酯'),
    '50170M': dict(pid='ETERKYD-50170-M-52', nv=52.0, rtype='聚酯', role='树脂',
                   依据='牌号 50170-M-52 → 长兴 ETERKYD 50170-M-52 高分子量聚酯（TDS：Tg 52、粘度 Z1-Z2）。'
                        '旧库按同族推断为 40% 固含，档案牌号自证为 52%'),
    # ---- 聚酯 ----
    'RJ173M': dict(pid='ETERKYD-50173-M-40', nv=40.0,
                   依据='送检组成名称「聚酯树脂 50173-M-40」= 长兴 ETERKYD 50173-M-40'),
    'RJ561': dict(pid='ETERKYD-50561-R-60', nv=60.0,
                  依据='送检组成名称「聚酯树脂 50561」= 长兴 ETERKYD 50561-R-60'),
    # ---- 酚醛 ----
    'RF401': dict(pid='PHENODUR-PR401-72B', nv=72.0,
                  依据='库内代码 RF401(PR401) → 湛新 PHENODUR PR 401/72B'),
    'RF516': dict(pid='PHENODUR-PR516-60B', nv=60.0,
                  依据='库内代码 RF516（PR516）→ 湛新 PHENODUR PR 516/60B'),
    'RF160': dict(pid='SUMILITERESIN-PR33160G', nv=72.0,
                  依据='库内代码 RF160(PR33160G) → 住友 SUMILITERESIN PR-33160G（TDS 不挥发份 72%，'
                       '旧库按送检组成区间中值记 65%）'),
    'RF950': dict(pid='ETERPHEN-8219-B-50', nv=50.0,
                  依据='库内代码 RF950（PR8219-50）→ 长兴 ETERPHEN 8219-B-50'),
    'RF956': dict(pid='ETERPHEN-8219-B-65', nv=66.0,
                  依据='库内代码 RF956（PR8219-65）→ 长兴 ETERPHEN 8219-B-65'),
    # ---- 交联剂 ----
    'RA009': dict(pid='A09-60LF', nv=60.0, role='固化剂',
                  依据='送检组成名称「氨基树脂 A09-60-LF」→ 慧新 A09-60LF'),
    'RA083': dict(pid='MELCROSS-83', nv=98.0, role='固化剂',
                  依据='送检组成名称「氨基树脂 M-83」→ MELCROSS-83 混合醚型苯并胍胺甲醛树脂'),
    'RA824': dict(pid='RESIMENE-CE8824', nv=97.0, role='固化剂',
                  依据='送检组成名称「氨基树脂 8824」→ INEOS Resimene CE8824'),
    'RY460': dict(pid='WANNATE-ITBL-460S', nv=60.0, role='树脂', rtype='聚氨酯',
                  依据='送检组成名称「异氰酸酯树脂 ITBL-460S」→ 万华 WANNATE ITBL-460S'),
    'RY075N': dict(pid='BURNOCK-FH-075N', nv=75.0, role='树脂', rtype='聚氨酯',
                   依据='送检组成名称「异氰酸酯树脂 FH075N」→ 爱敬 BURNOCK FH-075N'),
    # ---- 氯化烯类 / 助剂 / 颜料 ----
    'RX170-140': dict(pid='VESTOLIT-G170-L140-UF', nv=100.0, rtype='乙烯基',
                      依据='送检组成名称「烯类树脂 170-L140UF（聚氯乙烯）」→ Vestolit G 170-L140 UF'),
    'AS400': dict(pid='ESO-O-130C', nv=99.0, role='助剂', rtype='其他',
                  依据='送检组成名称「塑化剂（环氧豆油）CAS8013-07-8 ≥99%」→ 常熟艾迪科 O-130C'),
    'AZ088': dict(pid='BYK-088', nv=3.3,
                  依据='库内代码 AZ088（BYK088）→ 毕克 BYK-088 消泡剂'),
    'AZ306': dict(pid='BYK-306', nv=12.5, 依据='送检组成名称「助剂 BYK306」→ 毕克 BYK-306'),
    'BYK306': dict(pid='BYK-306', nv=12.5, 依据='原料代码即商品名 BYK306 → 毕克 BYK-306'),
    'BYK104': dict(pid='BYK-P104S', nv=50.0,
                   依据='库内登记名「分散剂BYK104」→ 毕克 BYK-P 104 S'),
    'AZ135': dict(pid='ACA-EAA1', nv=98.0,
                  依据='送检组成名称「助剂 ACA-EAA1」→ 南京能德 Capatue ACA-EAA1（CAS14782-75-3）'),
    '10%135': dict(pid='ACA-EAA1', nv=10.0,
                   依据='代码名自证：AZ135（ACA-EAA1，≥98%）的 10% 稀释品；载体类型未记录 → 仅折算固含与当量'),
    'AC040': dict(pid='TYZOR-GBA', nv=75.0,
                  依据='送检组成名称「催化剂 GBA（乙酰丙酮钛螯合物）」→ Dorf Ketal TYZOR GBA'),
    '10%AC040': dict(pid='TYZOR-GBA', nv=7.5, 依据='代码名自证：AC040 的 10% 稀释品'),
    '1510蜡': dict(pid='LANCO-1510-EF', nv=25.0, wax_pct=100.0,
                   依据='库内登记名「1510蜡25%工作液」→ 路博润 Lanco 1510 EF 微粉化聚烯烃蜡；'
                        '25% 为工作液自证固含，蜡粉本体的密度/熔点/粒径取 TDS'),
    '气硅': dict(pid='SYLOID-7000', nv=100.0,
                 依据='气相二氧化硅/二氧化硅消光剂，档案内两个候选：Grace SYLOID 7000（吸油量 300 g/100g、'
                      'D50 4.6 μm）与湖北汇富 HIFULL FA32（BET 200 m²/g、密度 2.2）；'
                      '按「有机处理二氧化硅」到货取 SYLOID 7000 口径'),
    '3%气硅': dict(pid='SYLOID-7000', nv=3.0,
                   依据='代码名自证 3% 气相二氧化硅分散体；固体部分取 SYLOID 7000 档案'),
    'FL815C': dict(pid='SUNRUNS-LY815-C', nv=57.0, role='颜料', pig_pct=57.0,
                   依据='送检组成名称「铝银浆 LY815C」→ 旭阳 Sunruns LY815-C（TDS：固含量 57±2%、'
                        'D50 7±2 μm、比重 1.45-1.65）；旧库按送检区间中值记 65%'),
    '35.7%白浆': dict(pid='TIO2-PASTE', nv=35.7, role='颜料', pig_pct=35.7,
                      依据='钛白粉档案（Venator TR92：TiO₂ 94%、比重 4.1、吸油量 18 cm³/100g；'
                           '中信 CR-510：TiO₂ 94.5%、比重 4.1、吸油量 17.5）；'
                           '35.7% 为浆料自证固含，浆料密度按颜料体积浓度混合规则折算'),
    '20%CAB': dict(pid='CAB-381-2', nv=20.0,
                   依据='代码名自证：CAB 20% 溶液；干树脂本体取伊士曼 CAB-381-2 档案'
                        '（Mn 40000、Tg 133℃、丁酰基38%/乙酰基13.5%/羟基1.3%）'),
    'DBE': dict(pid='SOLVENT-DBE', nv=0.0, 依据='SDS：DBE（MADE）混合二元酸二甲酯'),
    'TZ425': dict(pid='SOLVENT-DBE', nv=0.0,
                  依据='库内登记名「DBE溶剂」→ 混合二元酸二甲酯 SDS（旧库分子量 160 与 SDS 一致，'
                       '酯基密度按每分子 2 个酯基折算）'),
    # ---- 纯物质溶剂（分子式定值） ----
    '正丁醇': dict(pure='正丁醇'), '二甲苯': dict(pure='二甲苯'),
    'TM004': dict(pure='TM004'), 'TM221': dict(pure='TM221'), 'TZ221': dict(pure='TZ221'),
    'TZ161': dict(pure='TZ161'), 'TZ240': dict(pure='TZ240'), 'TT444': dict(pure='TT444'),
    'TT066': dict(pure='TT066'), 'TM982': dict(pure='TM982'), 'DPM': dict(pure='DPM'), 'MIBK': dict(pure='MIBK'), '10%磷酸': dict(pure='10%磷酸'),
    'TM024': dict(pure='TM024'),                       # 二乙二醇单丁醚（丁基卡必醇）
    '补加混合液': dict(mixture='补加混合液'),
}

# 混合物：按组分档案折算（键 = 原料代码）
MIXTURE = {
    '补加混合液': dict(parts=[('TM004', 2.0), ('二甲苯', 1.0)],
                       依据='代码名自证「乙二醇单丁醚：二甲苯=2:1」→ 两组分各自 SDS 值按质量加权/体积混合规则折算'),
}

# 机理当量实测替换（覆盖 mech_desc.LIT 的公开典型值项）
LIT_TDS = {
    'RY460': dict(nco_eq=4202.0 / 7.0, 依据='TDS 封闭型NCO含量 ~7%（到货）→ nco_eq=4202/7=600 g/eq'),
    'RY075N': dict(nco_eq=4202.0 / 11.0, 依据='TDS NCO含量 11±0.5% → nco_eq=4202/11=382 g/eq'),
    '气硅': dict(dbp=300.0, 依据='SYLOID 7000 TDS：吸油量 300 g/100g'),
    '3%气硅': dict(dbp=300.0, 依据='同气硅（固体部分取 SYLOID 7000）'),
    '35.7%白浆': dict(dbp=18.0, 依据='TIOXIDE TR92 TDS：吸油量 18 cm³/100g（ISO 787/5）'),
}

# 到货牌号未获档案 → 保留类别典型值，列入补档清单
PENDING = {
    'IR877': '环氧-配比方案在用环氧树脂（该体系质量占比 6.0%），牌号未登记；档案内候选 '
             'YD-011X75（EEW 450~500、不挥发份 74~76%、MIBK 载体）、NP1023-R-50（椰油改性环氧酯、固含 50±2%、'
             '酸值 ≤3）、4901-B-72（附着力促进环氧、固含 72±2%）——需按物料编码确认后替换',
    'IR909': '聚酯金黄主用环氧树脂之一（该体系质量占比 22.6%），牌号未登记 → 需 TDS',
    'IR557': '聚酯金黄在用环氧树脂（8.7%），牌号未登记 → 需 TDS',
    'IR868': '聚酯金黄在用环氧树脂（1.0%），牌号未登记 → 需 TDS',
    'IR842': '环氧-配比方案在用环氧树脂，牌号未登记 → 需 TDS',
    'IR170': '环氧树脂，牌号未登记 → 需 TDS',
    'R170M': '聚酯金黄在用环氧树脂（0.9%），牌号未登记 → 需 TDS',
    '杜邦-FT960': '环氧树脂（杜邦牌号），档案缺失 → 需 TDS',
    '住友55754G': '库内按环氧树脂登记（NV100/EEW950）；档案内住友 33xxx/34xxx/55xxx/56xxx 系列均为 '
                  'SUMILITERESIN 酚醛固化剂。若为同一系列，角色应改为固化剂/酚醛，需物料编码核定',
    'TF100': '聚酯金黄在用乙烯基树脂（16.5%），牌号未登记；档案内氯醋/PVC 类（MVAH：Tg 79、Mn 27000、比重 1.39；'
             'VMA：Tg 70、Mn 15000；Kanevinyl EH-150、Vinnolit P70、GEON178）需按到货单确认后替换',
    'TF022': '乙烯基树脂，牌号未登记 → 需 TDS',
    'RJ183': '送检名称「聚酯树脂 1873」，档案缺失 → 需 TDS',
    'RJ362': '送检名称「聚酯树脂 CN7-18-60」，档案缺失 → 需 TDS',
    'IA151': '丙烯酸树脂，牌号未登记；档案内丙烯酸多元醇 SU-4660（固含 60±2%、羟值 70 供应/116 固体、酸值 <6）'
             '为候选，需确认',
    'IA800': '丙烯酸树脂，牌号未登记 → 需 TDS',
    'IA8000': '丙烯酸树脂，牌号未登记 → 需 TDS',
    'IA893': '丙烯酸树脂，牌号未登记 → 需 TDS',
    'AL800': '丙烯酸树脂，牌号未登记 → 需 TDS',
    'AL525': '送检名称「蜡 LHWAX2525A（单油酸甘油酯）」，档案缺失 → 需 TDS',
    'AL710': '送检名称「蜡 TPG-710 合成蜡分散体」（固含 35%）；档案内蜡分散体 Unidisp WD420（19~21%）、'
             'Lanco Glidd 4818（11.5%）固含均不符，牌号需确认',
    'AZ551': '助剂，疑似 BYK-3550（不挥发份 52%、密度 1.01、载体 PMA），需确认',
    'FL208': '助剂/流平剂，档案缺失 → 需 TDS',
    'FL208S': '助剂/流平剂，档案缺失 → 需 TDS',
    '6#炭黑-阿克苏': '色素炭黑（配比方案体系质量占比 8.8%），档案缺失 → 需 TDS（吸油值/粒径/真密度）',
    '14.28%炭黑浆料': '炭黑浆料，档案缺失 → 需 TDS',
    'RY078': '黄色颜料，档案内有 PY110（密度 1.7~1.9、吸油量 40~80）、PY138（1.852、吸油量 30~60）、'
             '拜耳乐3920（密度 4.0、吸油量 35）等候选，需确认',
    'TM024': '库内登记名「二乙二醇单丁醚」，档案缺失 → 需 SDS/TDS',
    '209-基料': '与「209-白浆」配对出现的基料，组成未记录',
    'DMP': '代码缩写歧义（丙二醇二甲醚 / 邻苯二甲酸二甲酯 / 二甲氨基丙醇皆用 DMP），需物料编码确认',
}

# ================================================================== 折算实现
FIELD_SRC_DOC = {}   # code -> [档案相对路径]（apply 时填充，供报表引用）


def _carrier_props(carrier):
    parts = [(w, CARRIER[c]['density']) for c, w in carrier if c in CARRIER]
    bp = [(w, CARRIER[c]['bp']) for c, w in carrier if c in CARRIER]
    fp = [(w, CARRIER[c]['fp']) for c, w in carrier if c in CARRIER]
    ev = [(w, CARRIER[c].get('evap', 0.0)) for c, w in carrier if c in CARRIER]
    return parts, bp, fp, ev


def _from_pure(code, tag):
    """纯物质：SDS 分子式定值（分子量/元素组成/官能团密度）+ SDS/TDS 理化项。"""
    p = PURE[code]
    mw, els = formula_mass(p['fml'])
    f = {'NV': p['nv'], 'Mw': mw}
    f.update({k: v for k, v in p['fields'].items()
              if k not in ('assay', 'acid_density', 'acid_mp', 'acid_bp')})
    tag.update({k: 'sds' for k in f})
    tag['Mw'] = 'formula'
    if 'func' in f:
        tag['func'] = 'formula'
    dilu = p['nv'] / 100.0 if (p['nv'] and p.get('water')) else 1.0   # 水溶液：按有效物稀释
    if dilu < 1.0 and p.get('els_wet'):        # 水溶液按「有效物+水」重算元素质量分数
        for e in ('C', 'H', 'O', 'N', 'S', 'Cl'):
            f[e] = round(els.get(e, 0.0) * dilu + p['els_wet'].get(e, 0.0) * (1.0 - dilu), 2)
            tag[e] = 'formula'
    else:
        for e, v in els.items():
            if e in ('C', 'H', 'O', 'N', 'S', 'Cl'):
                f[e] = v
                tag[e] = 'formula'
    for k, n in p.get('groups', {}).items():
        f[f'fg_{k}'] = round(n * 100.0 / mw * dilu, 5)
        tag[f'fg_{k}'] = 'formula'
    if f.get('fg_oh'):
        f['OHV'] = round(f['fg_oh'] * 561.0, 1)
        tag['OHV'] = 'formula'
    if f.get('fg_cooh'):
        f['AV'] = round(f['fg_cooh'] * 561.0, 1)
        tag['AV'] = 'formula'
    for k in ('fg_epoxy', 'fg_oh', 'fg_cooh', 'fg_ester', 'fg_amine', 'fg_amide',
              'fg_arom', 'fg_ether', 'wax', 'pig'):
        if f.get('groups') and k.startswith('fg_') and k[3:] not in f['groups']:
            f[k] = 0.0
        elif k not in ('fg_epoxy',):
            f.setdefault(k, 0.0)
    f.pop('groups', None)
    return f


def tds_fields(code):
    """返回 (fields, prov, docs, 依据, 摘录dict)。fields 只含 TDS/SDS 支撑的项。"""
    fld, prov, docs = {}, {}, []
    mp = CODE_MAP.get(code)
    if not mp:
        if code in PURE_ALIAS:
            return tds_fields(PURE_ALIAS[code])
        if code in FAMILY:
            return _family_fields(code)
        return {}, {}, [], '', {}
    q = {}
    if 'mixture' in mp or 'pure' in mp:
        key = mp.get('mixture') or mp.get('pure')
        if key in MIXTURE:
            mx = MIXTURE[key]
            parts, bps, fps, evs, elems, fgs, mws, tg = [], [], [], [], {}, {}, [], []
            tw = sum(w for _, w in mx['parts'])
            for sc, w in mx['parts']:
                sf = PURE[sc]['fields']
                mw, els = formula_mass(PURE[sc]['fml'])
                parts.append((w, sf['density']))
                bps.append((w, sf['bp']))
                fps.append((w, sf['fp']))
                evs.append((w, sf.get('evap', 0.0)))
                mws.append((w, mw))
                tg.append((w, sf.get('Tg')))
                for e, v in els.items():
                    if e in ('C', 'H', 'O', 'N', 'S', 'Cl'):
                        elems[e] = elems.get(e, 0.0) + w * v
                for k, n in PURE[sc].get('groups', {}).items():
                    fgs[k] = fgs.get(k, 0.0) + w * n * 100.0 / mw
            fld['density'] = mix_density(parts)
            fld['bp'] = wavg(bps)
            fld['fp'] = wavg(fps)
            fld['evap'] = wavg(evs)
            fld['Mw'] = wavg(mws)
            _tg = wavg([(w, v) for w, v in tg if v is not None])
            if _tg is not None:
                fld['Tg'] = _tg
            fld['NV'] = 0.0
            for e, v in elems.items():
                fld[e] = round(v / tw, 2)
            for k, v in fgs.items():
                fld[f'fg_{k}'] = round(v / tw, 5)
            fld['OHV'] = round(fld.get('fg_oh', 0.0) * 561.0, 1)
            for k in ('fg_epoxy', 'fg_cooh', 'fg_ester', 'fg_amine', 'fg_amide', 'wax', 'pig'):
                fld.setdefault(k, 0.0)
            prov.update({k: 'tds_carry' for k in
                         ('density', 'bp', 'fp', 'evap', 'Mw', 'Tg', 'OHV') if k in fld})
            prov.update({f'fg_{k}': 'tds_carry' for k in fgs})
            prov.update({e: 'tds_carry' for e in elems})
            prov['func'] = 'tds_carry'
            fld['func'] = 0
            docs = sorted({d for sc, _ in mx['parts'] for d in PURE[sc]['doc']})
            q['chem'] = mx['依据']
            q['mix'] = ' + '.join(f'{sc} {100.0*w/tw:.1f}%' for sc, w in mx['parts'])
            return fld, prov, docs, mx['依据'], q
        p = PURE[key]
        f = _from_pure(key, prov)
        fld.update(f)
        docs += p['doc']
        q['chem'] = p['依据']
        return fld, prov, docs, p['依据'], q
    if mp.get('pid') == 'TIO2-PASTE':
        nv = mp['nv']
        ti = PRODUCTS['TIOXIDE-Rutile']
        car = mp.get('carrier', [])
        fld = dict(NV=nv, pig=round(ti['dry']['TiO2'] * nv / 100.0, 2))
        pr = {'NV': 'name', 'pig': 'tds_carry'}
        if car:
            fld['density'] = mix_density([(nv, ti['dry']['density'])]
                                         + [(100.0 - nv, CARRIER[c]['density']) for c, _ in car])
            pr['density'] = 'tds_carry'
            q['density'] = (f'{nv}% 钛白粉（{ti["dry"]["density"]} g/cm³）+ 载体 '
                            + '、'.join(f'{c} {w}%' for c, w in car) + f' → 混合密度 {fld["density"]}')
        q.update(ti['q'])
        return fld, pr, ti['doc'], mp['依据'], q
    pr = PRODUCTS.get(mp['pid'])
    if not pr:
        return {}, {}, [], '', {}
    docs += pr['doc']
    d = dict(pr['dry'])
    nv = mp.get('nv', d.get('NV', 100.0))
    q.update(pr['q'])
    # —— 本体字段（固体树脂口径，与档案一致）——
    for k in ('Tg', 'Mw', 'func'):
        if k in d:
            fld[k] = d[k]
            prov[k] = 'tds'
    fld['NV'] = nv
    prov['NV'] = 'tds' if nv == d.get('NV') else 'name'
    if 'name' in pr:
        q.setdefault('name', pr['name'])
    # —— 密度/沸点/闪点/挥发速率（逐键处理）——
    # res_solid=True：档案给的是固体树脂口径 → 须按登记载体折算到货物性；
    # 否则档案即到货口径（SDS/TDS 报告的液体产品比重、闪点），直接采用。
    carrier = mp.get('carrier', pr.get('carrier'))
    res_solid = pr.get('res_solid', False)
    diluted = nv < (d.get('NV') if d.get('NV') is not None else 100.0) - 1e-9
    cprops = _carrier_props(carrier) if carrier else None
    key_idx = {'density': 0, 'bp': 1, 'fp': 2, 'evap': 3}
    mix_needed = bool(carrier) and (res_solid or diluted)
    for key in ('density', 'bp', 'fp', 'evap'):
        v = d.get(key)
        if mix_needed:
            if key == 'density':
                if v is None:
                    continue                              # 档案未给树脂比重 → 不折算
                fld['density'] = mix_density([(nv, v)] + cprops[0])
                q['density'] = (f'{nv}% 树脂（档案固体口径比重 {v}）+ 载体 '
                                + '、'.join(f'{c} {w}%' for c, w in carrier)
                                + f' → 体积可加混合 {fld["density"]} g/cm³')
            else:
                cp = list(cprops[key_idx[key]])           # 沸点/闪点/挥发速率由挥发组分（载体）决定
                if not cp:
                    if v is not None and not diluted:
                        fld[key] = v
                        prov[key] = 'tds'
                    continue
                fld[key] = wavg(cp)
                q[key] = ('按登记载体（挥发组分）取值：'
                          + '、'.join(f'{c} {w}%' for c, w in carrier) + f' → {fld[key]}')
            prov[key] = 'tds_carry'
        elif v is not None and not diluted:
            fld[key] = v
            prov[key] = 'sds' if 'SDS' in (pr['q'].get(key, '') + pr['q'].get('density', '')) else 'tds'
            q[key] = pr['q'].get(key) or pr['q'].get('density', '')
    # —— 当量类：档案口径 → 到货基 ——
    # pr['sb'] 列出「按 100% 固体树脂给出」的字段（TDS 标注 mgKOH/g solid、以100%树脂计、羟基含量%），
    # 这些字段按 NV/100 稀释；未列出者视为档案即到货口径（如 NCO%、环氧数、产品酸值）。
    sb = pr.get('sb', ())

    def _as(k, v):
        return v * (nv / 100.0) if k in sb else v
    if 'EEW' in d:
        eew_as = d['EEW'] / (nv / 100.0) if nv > 0 else d['EEW']     # 环氧当量恒按固体树脂登记
        fld['EEW'] = round(eew_as, 1)
        fld['fg_epoxy'] = round(100.0 / eew_as, 5)
        prov['EEW'] = prov['fg_epoxy'] = 'tds' if nv == 100.0 else 'tds_carry'
        q['EEW'] = pr['q'].get('EEW', '') + f' → 到货 EEW={fld["EEW"]} g/eq（{nv}% 固含）'
        if 'OHV' not in d and nv > 0:
            ohv_dry = dgeba_ohv_dry(d['EEW'])
            fld['OHV'] = round(ohv_dry * nv / 100.0, 1)
            fld['fg_oh'] = round(ohv_dry * nv / 56100.0, 5)
            prov['OHV'] = prov['fg_oh'] = 'tds_carry'
            q['OHV'] = (f'DGEBA 同系物：n=(EEW−171.1)/284.4={(d["EEW"]-171.1)/284.4:.2f} → 每分子羟基 n+1，'
                        f'固体羟值 {ohv_dry:.1f} mgKOH/g，按 {nv}% 固含折算 {fld["OHV"]:.1f}')
    for k in ('OHV', 'AV'):
        if k in d:
            asv = _as(k, d[k])
            fld[k] = round(asv, 2)
            key = 'fg_oh' if k == 'OHV' else 'fg_cooh'
            if key not in fld or k == 'AV':
                fld[key] = round(asv / 561.0, 5)
            prov[k] = prov[key] = 'tds_carry' if k in sb else 'tds'
            q[k] = pr['q'].get(k, '') + (f' → 到货 {asv:.2f} mgKOH/g（×{nv / 100.0:.2f}）' if k in sb else '')
    if 'ESO' in d:
        fld['EEW'] = round(1600.0 / _as('ESO', d['ESO']), 1)
        fld['fg_epoxy'] = round(_as('ESO', d['ESO']) / O_XIRANE, 5)
        prov['EEW'] = prov['fg_epoxy'] = 'tds_carry'
    if 'NCO' in d:
        nco_as = _as('NCO', d['NCO'])
        fld['fg_amide'] = round(nco_as / NCO_M, 5)
        prov['fg_amide'] = 'tds_carry'
        q['NCO'] = pr['q'].get('NCO', '') + f' → nco_eq={4202.0/nco_as:.0f} g/eq（到货 NCO {nco_as:.2f}%）'
    if pr.get('groups') and d.get('Mw'):
        # 分子式给定每分子官能团数 → mol/100g（按到货有效物占比折算）
        act = min(1.0, nv / max(d.get('NV', 100.0), 1e-9)) if nv else 1.0
        for k, n in pr['groups'].items():
            fld[f'fg_{k}'] = round(n * 100.0 / d['Mw'] * act, 5)
            prov[f'fg_{k}'] = 'tds_carry'
    if 'OH_pct' in d:
        oh = round(_as('OH_pct', d['OH_pct']) / 17.0, 5)             # wt%OH → mol OH/100g
        fld['fg_oh'] = oh
        fld['OHV'] = round(oh * 561.0, 2)
        prov['fg_oh'] = prov['OHV'] = 'tds_carry'
        if 'acetyl' in d and 'butyryl' in d:
            est = d['acetyl'] / 43.0 + d['butyryl'] / 71.0         # mmol 酯基/g 干树脂
            fld['fg_ester'] = round(est * nv / 1000.0 * 10.0, 5)
            prov['fg_ester'] = 'tds_carry'
    if 'Al' in d and 'fml' not in pr:
        pass
    if 'fml' in pr:
        mw, els = formula_mass(pr['fml'])
        if pr.get('mw_from_formula'):                      # 仅小分子用式量作分子量
            fld['Mw'] = mw
            prov['Mw'] = 'formula'
        for e, v in els.items():
            if e in ('C', 'H', 'O', 'N', 'S', 'Cl'):
                fld[e] = v
                prov[e] = 'formula'
    if mp.get('wax_pct'):
        fld['wax'] = round(nv * mp['wax_pct'] / 100.0, 2)
        prov['wax'] = 'name'
    if mp.get('pig_pct'):
        fld['pig'] = mp['pig_pct']
        prov['pig'] = 'tds'
    if mp.get('role'):
        fld['role'] = mp['role']
        prov['role'] = 'tds'
    if mp.get('rtype'):
        fld['rtype'] = mp['rtype']
        prov['rtype'] = 'sds'
    return fld, prov, docs, mp['依据'], q


def apply(mat, unify=True, use_tds=True, prefer='documented'):
    """把档案层写入原料库，并登记逐字段来源。

    use_tds=False 时**不覆盖任何数值**，只补全 prov 标签（送检组成/公开手册/类别典型值），
    供 A/B 对照与覆盖度审计复用同一套标签。
    prefer 控制当量列与官能团密度列互相矛盾时的换算方向：
      'documented' 有档案支撑的一侧为准（默认）
      'equiv'      EEW/OHV/AV 为准（沿旧机理口径）
      'density'    fg_* 为准（沿旧线性描述符口径）
    返回 (被档案覆盖的 code 列表, {code: {字段: 来源}})。
    """
    prov_all = {}
    changed = []
    if use_tds:
        for code in list(mat.keys()):
            fld, prov, docs, basis, q = tds_fields(code)
            if not fld:
                continue
            m = mat[code]
            m.update(fld)
            is_family = any(v == 'family' for v in prov.values())
            m['数据来源'] = 'TDS族推' if is_family else 'TDS/SDS'
            m['TDS档案'] = docs
            m['TDS依据'] = basis
            m['TDS摘录'] = q
            m['描述符状态'] = '族推断' if is_family else 'TDS实测'
            prov_all[code] = prov
            changed.append(code)
    _label_prior_layers(prov_all, mat)
    if unify:
        unify_equivalents(mat, prov_all, prefer=prefer)
    for code, m in mat.items():
        pv = prov_all.setdefault(code, {})
        for k in CONT_DESC_KEYS:
            pv.setdefault(k, 'typical')
        m['prov'] = pv
        m.setdefault('TDS档案', [])
    if use_tds:
        _merge_lit()
    return changed, prov_all


def _label_prior_layers(prov_all, mat):
    """把送检组成、公开手册两层的历史覆盖登记进 prov（不改变数值）。"""
    try:
        import compo_rules
        import handbook_fixes as HF
    except Exception:
        return
    for code, m in mat.items():
        pv = prov_all.setdefault(code, {})
        for k in compo_rules.OVERRIDES.get(code, {}):
            if k in CONT_DESC_KEYS:
                pv.setdefault(k, 'compo')
        for k in HF.FIXES.get(code, {}):
            if k in CONT_DESC_KEYS:
                pv.setdefault(k, 'handbook')
        if code in HF.PENDING:
            pv.setdefault('NV', 'pending')


CONT_DESC_KEYS = ['NV', 'density', 'Mw', 'EEW', 'AV', 'OHV', 'amine', 'func', 'Tg', 'bp', 'fp',
                  'dD', 'dP', 'dH', 'pol', 'evap', 'C', 'H', 'O', 'N', 'S', 'Cl',
                  'fg_epoxy', 'fg_oh', 'fg_cooh', 'fg_ester', 'fg_amine', 'fg_amide',
                  'fg_arom', 'fg_ether', 'wax', 'pig']


DOCUMENTED = ('tds', 'sds', 'formula', 'tds_carry', 'name')


def _doc(prov, k):
    """该字段的取值是否有档案支撑。"""
    return prov.get(k) in DOCUMENTED


def unify_equivalents(mat, prov_all=None, prefer='documented'):
    """把 EEW/OHV/AV 与 fg_epoxy/fg_oh/fg_cooh 绑定为标准换算（到货状态口径），消除两列互矛盾。

    prefer='documented'：以有档案支撑的一侧为准；两侧都无档案时以当量列为准，
    并把派生侧标为 typical —— 派生值只是内部自洽，不因此获得实测身份。
    prefer='equiv'/'density'：固定以当量列 / 官能团密度列为准（A/B 对照用）。
    """
    prov_all = prov_all if prov_all is not None else {}
    pairs = (('EEW', 'fg_epoxy'), ('OHV', 'fg_oh'), ('AV', 'fg_cooh'), ('amine', 'fg_amine'))
    for code, m in mat.items():
        pv = prov_all.setdefault(code, {})
        for eq_k, fg_k in pairs:
            eq_v, fg_v = m.get(eq_k), m.get(fg_k)
            eq_doc, fg_doc = _doc(pv, eq_k), _doc(pv, fg_k)
            if prefer == 'equiv':
                use_eq = bool(eq_v) or not fg_v
            elif prefer == 'density':
                use_eq = not fg_v
            else:
                use_eq = eq_doc or (bool(eq_v) and not fg_v) or not (fg_doc or fg_v)
            if use_eq and eq_v:
                m[fg_k] = _to_fg(eq_k, eq_v)
                pv[fg_k] = pv[eq_k] if eq_doc else 'typical'
            elif (not use_eq) and fg_v:
                m[eq_k] = _inv(eq_k, fg_v)
                pv[eq_k] = pv[fg_k] if fg_doc else 'typical'
            elif eq_v:
                m[fg_k] = _to_fg(eq_k, eq_v)
                pv[fg_k] = pv[eq_k] if eq_doc else 'typical'
            elif fg_v:
                m[eq_k] = _inv(eq_k, fg_v)
                pv[eq_k] = pv[fg_k] if fg_doc else 'typical'


def _to_fg(eq_k, eq_v):
    if eq_k == 'EEW':
        return round(100.0 / eq_v, 5) if eq_v else 0.0
    return round(eq_v / 561.0, 5)


def _inv(eq_k, fg_v):
    if eq_k == 'EEW':
        return round(100.0 / fg_v, 1) if fg_v else 0.0
    return round(fg_v * 561.0, 1)


def lit_overrides():
    """供 mech_desc 使用的机理当量实测替换表。"""
    return {k: {kk: vv for kk, vv in v.items() if kk != '依据'} for k, v in LIT_TDS.items()}


def _merge_lit():
    try:
        import mech_desc
    except Exception:
        return False
    for src in (LIT_TDS, LIT_FAMILY):
        for code, ov in src.items():
            cur = mech_desc.LIT.setdefault(code, {})
            cur.update({k: v for k, v in ov.items() if k != '依据'})
    return True
