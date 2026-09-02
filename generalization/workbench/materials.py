# -*- coding: utf-8 -*-
"""
跨体系原料描述符库 (Raw Material Descriptor Library)
覆盖：环氧酚醛体系(文件2) / 有机体系(文件3) / 聚酯体系(文件4)
描述符口径：
  role    : 树脂/固化剂/溶剂/助剂/颜料
  rtype   : 树脂化学类别 (环氧/酚醛/聚酯/乙烯基/丙烯酸/聚氨酯/氨基/其他)
  NV      : 固含 % (按到货状态)
  density : 密度 g/cm3
  Mw      : 分子量 g/mol
  EEW     : 环氧当量 g/eq (按到货状态产品计)
  AV      : 酸值 mg KOH/g
  OHV     : 羟值 mg KOH/g
  amine   : 胺值 mg KOH/g
  func    : 官能度 (每分子活性基团数)
  Tg      : 玻璃化转变温度 °C
  bp      : 沸点 °C
  fp      : 闪点 °C
  dD/dP/dH: Hansen 溶解度参数 MPa^0.5
  pol     : 极性指数
  evap    : 相对挥发速率 (乙酸丁酯=1)
  C/H/O/N/S/Cl : 元素质量分数 %
  fg_*    : 官能团密度 mol/100g (环氧/羟基/羧基/酯基/胺基/酰胺/芳香环/醚键)
  wax     : 蜡含量 %
  pig     : 颜料含量 %
注：树脂/助剂等专有原料的描述符基线为"化学类别典型值+文件信息"估算；
    已送检原料（见 compo_rules.COMPO）由供应商组成覆盖为实证值（固含、角色、
    树脂类型、官能团密度等），其余保留基线估算。组成→描述符的经验规则见 compo_rules。
"""

MAT = {
    # ================= 环氧树脂 =================
    'IR190': dict(role='树脂', rtype='环氧', NV=36, density=1.00, Mw=1400, EEW=2640, AV=0.5, OHV=30, amine=0, func=2, Tg=70, bp=250, fp=100, dD=18.5, dP=6.0, dH=8.5, pol=3.0, evap=0.0, C=72, H=7, O=20, N=0, S=0, Cl=0, fg_epoxy=0.038, fg_oh=0.018, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.4, fg_ether=0.15, wax=0, pig=0),
    'IR809': dict(role='树脂', rtype='环氧', NV=55, density=1.02, Mw=1200, EEW=1600, AV=0.5, OHV=35, amine=0, func=2, Tg=65, bp=250, fp=100, dD=18.3, dP=6.2, dH=8.8, pol=3.1, evap=0.0, C=71, H=7, O=21, N=0, S=0, Cl=0, fg_epoxy=0.062, fg_oh=0.021, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.38, fg_ether=0.16, wax=0, pig=0),
    '住友55754G': dict(role='树脂', rtype='环氧', NV=100, density=1.15, Mw=1000, EEW=950, AV=0.3, OHV=40, amine=0, func=2, Tg=75, bp=300, fp=150, dD=18.8, dP=6.0, dH=8.2, pol=3.0, evap=0.0, C=73, H=7, O=19, N=0, S=0, Cl=0, fg_epoxy=0.105, fg_oh=0.024, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.42, fg_ether=0.15, wax=0, pig=0),
    'IR191': dict(role='树脂', rtype='环氧', NV=36, density=1.00, Mw=1400, EEW=2650, AV=0.5, OHV=30, amine=0, func=2, Tg=70, bp=250, fp=100, dD=18.5, dP=6.0, dH=8.5, pol=3.0, evap=0.0, C=72, H=7, O=20, N=0, S=0, Cl=0, fg_epoxy=0.038, fg_oh=0.018, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.4, fg_ether=0.15, wax=0, pig=0),
    'IR170': dict(role='树脂', rtype='环氧', NV=50, density=1.02, Mw=1300, EEW=1800, AV=0.5, OHV=32, amine=0, func=2, Tg=68, bp=250, fp=100, dD=18.4, dP=6.1, dH=8.6, pol=3.0, evap=0.0, C=72, H=7, O=20, N=0, S=0, Cl=0, fg_epoxy=0.056, fg_oh=0.019, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.4, fg_ether=0.15, wax=0, pig=0),
    'IR877': dict(role='树脂', rtype='环氧', NV=60, density=1.03, Mw=1200, EEW=1500, AV=0.5, OHV=35, amine=0, func=2, Tg=66, bp=250, fp=100, dD=18.3, dP=6.2, dH=8.7, pol=3.1, evap=0.0, C=71, H=7, O=21, N=0, S=0, Cl=0, fg_epoxy=0.067, fg_oh=0.021, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.38, fg_ether=0.16, wax=0, pig=0),
    'IR909': dict(role='树脂', rtype='环氧', NV=60, density=1.03, Mw=1200, EEW=1500, AV=0.5, OHV=35, amine=0, func=2, Tg=66, bp=250, fp=100, dD=18.3, dP=6.2, dH=8.7, pol=3.1, evap=0.0, C=71, H=7, O=21, N=0, S=0, Cl=0, fg_epoxy=0.067, fg_oh=0.021, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.38, fg_ether=0.16, wax=0, pig=0),
    'IR557': dict(role='树脂', rtype='环氧', NV=60, density=1.03, Mw=1200, EEW=1500, AV=0.5, OHV=35, amine=0, func=2, Tg=66, bp=250, fp=100, dD=18.3, dP=6.2, dH=8.7, pol=3.1, evap=0.0, C=71, H=7, O=21, N=0, S=0, Cl=0, fg_epoxy=0.067, fg_oh=0.021, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.38, fg_ether=0.16, wax=0, pig=0),
    'R170M': dict(role='树脂', rtype='环氧', NV=60, density=1.03, Mw=1200, EEW=1500, AV=0.5, OHV=35, amine=0, func=2, Tg=66, bp=250, fp=100, dD=18.3, dP=6.2, dH=8.7, pol=3.1, evap=0.0, C=71, H=7, O=21, N=0, S=0, Cl=0, fg_epoxy=0.067, fg_oh=0.021, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.38, fg_ether=0.16, wax=0, pig=0),
    'IR868': dict(role='树脂', rtype='环氧', NV=60, density=1.03, Mw=1200, EEW=1500, AV=0.5, OHV=35, amine=0, func=2, Tg=66, bp=250, fp=100, dD=18.3, dP=6.2, dH=8.7, pol=3.1, evap=0.0, C=71, H=7, O=21, N=0, S=0, Cl=0, fg_epoxy=0.067, fg_oh=0.021, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.38, fg_ether=0.16, wax=0, pig=0),
    'IR842': dict(role='树脂', rtype='环氧', NV=60, density=1.03, Mw=1200, EEW=1500, AV=0.5, OHV=35, amine=0, func=2, Tg=66, bp=250, fp=100, dD=18.3, dP=6.2, dH=8.7, pol=3.1, evap=0.0, C=71, H=7, O=21, N=0, S=0, Cl=0, fg_epoxy=0.067, fg_oh=0.021, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.38, fg_ether=0.16, wax=0, pig=0),
    '40%50177': dict(role='树脂', rtype='环氧', NV=40, density=1.01, Mw=1300, EEW=2400, AV=0.5, OHV=32, amine=0, func=2, Tg=68, bp=250, fp=100, dD=18.4, dP=6.1, dH=8.6, pol=3.0, evap=0.0, C=72, H=7, O=20, N=0, S=0, Cl=0, fg_epoxy=0.042, fg_oh=0.019, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.4, fg_ether=0.15, wax=0, pig=0),
    '杜邦-FT960': dict(role='树脂', rtype='环氧', NV=50, density=1.02, Mw=1300, EEW=1800, AV=0.5, OHV=32, amine=0, func=2, Tg=68, bp=250, fp=100, dD=18.4, dP=6.1, dH=8.6, pol=3.0, evap=0.0, C=72, H=7, O=20, N=0, S=0, Cl=0, fg_epoxy=0.056, fg_oh=0.019, fg_cooh=0.001, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.4, fg_ether=0.15, wax=0, pig=0),
    # ================= 酚醛固化剂 =================
    'RF401': dict(role='固化剂', rtype='酚醛', NV=60, density=1.08, Mw=900, EEW=0, AV=1, OHV=280, amine=0, func=3, Tg=70, bp=300, fp=120, dD=19.5, dP=7.0, dH=10.0, pol=3.5, evap=0.0, C=74, H=6, O=18, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.165, fg_cooh=0.002, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.6, fg_ether=0.05, wax=0, pig=0),
    'RF160': dict(role='固化剂', rtype='酚醛', NV=60, density=1.08, Mw=1100, EEW=0, AV=1, OHV=320, amine=0, func=4, Tg=78, bp=300, fp=120, dD=19.5, dP=7.0, dH=10.0, pol=3.5, evap=0.0, C=74, H=6, O=18, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.188, fg_cooh=0.002, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.65, fg_ether=0.05, wax=0, pig=0),
    'RF516': dict(role='固化剂', rtype='酚醛', NV=60, density=1.08, Mw=1000, EEW=0, AV=1, OHV=300, amine=0, func=3.5, Tg=74, bp=300, fp=120, dD=19.5, dP=7.0, dH=10.0, pol=3.5, evap=0.0, C=74, H=6, O=18, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.177, fg_cooh=0.002, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.62, fg_ether=0.05, wax=0, pig=0),
    'RF950': dict(role='固化剂', rtype='酚醛', NV=50, density=1.07, Mw=800, EEW=0, AV=1, OHV=233, amine=0, func=3, Tg=65, bp=300, fp=120, dD=19.5, dP=7.0, dH=10.0, pol=3.5, evap=0.0, C=74, H=6, O=18, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.137, fg_cooh=0.002, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.58, fg_ether=0.05, wax=0, pig=0),
    'RF956': dict(role='固化剂', rtype='酚醛', NV=65, density=1.09, Mw=850, EEW=0, AV=1, OHV=303, amine=0, func=3, Tg=68, bp=300, fp=120, dD=19.5, dP=7.0, dH=10.0, pol=3.5, evap=0.0, C=74, H=6, O=18, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.178, fg_cooh=0.002, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.60, fg_ether=0.05, wax=0, pig=0),
    'RH601': dict(role='固化剂', rtype='酚醛', NV=75, density=1.10, Mw=950, EEW=0, AV=1, OHV=350, amine=0, func=3, Tg=70, bp=300, fp=120, dD=19.5, dP=7.0, dH=10.0, pol=3.5, evap=0.0, C=74, H=6, O=18, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.206, fg_cooh=0.002, fg_ester=0.01, fg_amine=0, fg_amide=0, fg_arom=0.60, fg_ether=0.05, wax=0, pig=0),
    # ================= 聚酯树脂 =================
    'RJ173M': dict(role='树脂', rtype='聚酯', NV=60, density=1.10, Mw=3000, EEW=0, AV=8, OHV=60, amine=0, func=2, Tg=40, bp=300, fp=150, dD=18.0, dP=7.0, dH=9.0, pol=3.2, evap=0.0, C=66, H=8, O=26, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.035, fg_cooh=0.005, fg_ester=0.35, fg_amine=0, fg_amide=0, fg_arom=0.3, fg_ether=0.05, wax=0, pig=0),
    'RJ561': dict(role='树脂', rtype='聚酯', NV=60, density=1.10, Mw=3000, EEW=0, AV=8, OHV=60, amine=0, func=2, Tg=40, bp=300, fp=150, dD=18.0, dP=7.0, dH=9.0, pol=3.2, evap=0.0, C=66, H=8, O=26, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.035, fg_cooh=0.005, fg_ester=0.35, fg_amine=0, fg_amide=0, fg_arom=0.3, fg_ether=0.05, wax=0, pig=0),
    'RJ183': dict(role='树脂', rtype='聚酯', NV=60, density=1.10, Mw=3000, EEW=0, AV=8, OHV=60, amine=0, func=2, Tg=40, bp=300, fp=150, dD=18.0, dP=7.0, dH=9.0, pol=3.2, evap=0.0, C=66, H=8, O=26, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.035, fg_cooh=0.005, fg_ester=0.35, fg_amine=0, fg_amide=0, fg_arom=0.3, fg_ether=0.05, wax=0, pig=0),
    'RJ362': dict(role='树脂', rtype='聚酯', NV=60, density=1.10, Mw=3000, EEW=0, AV=8, OHV=60, amine=0, func=2, Tg=40, bp=300, fp=150, dD=18.0, dP=7.0, dH=9.0, pol=3.2, evap=0.0, C=66, H=8, O=26, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.035, fg_cooh=0.005, fg_ester=0.35, fg_amine=0, fg_amide=0, fg_arom=0.3, fg_ether=0.05, wax=0, pig=0),
    # ================= 乙烯基树脂 =================
    'TF100': dict(role='树脂', rtype='乙烯基', NV=25, density=1.08, Mw=20000, EEW=0, AV=0.5, OHV=20, amine=0, func=1, Tg=55, bp=200, fp=80, dD=17.5, dP=6.0, dH=7.0, pol=2.8, evap=0.0, C=55, H=7, O=5, N=0, S=0, Cl=30, fg_epoxy=0, fg_oh=0.012, fg_cooh=0.001, fg_ester=0.02, fg_amine=0, fg_amide=0, fg_arom=0.1, fg_ether=0.02, wax=0, pig=0),
    'TF022': dict(role='树脂', rtype='乙烯基', NV=25, density=1.08, Mw=20000, EEW=0, AV=0.5, OHV=20, amine=0, func=1, Tg=55, bp=200, fp=80, dD=17.5, dP=6.0, dH=7.0, pol=2.8, evap=0.0, C=55, H=7, O=5, N=0, S=0, Cl=30, fg_epoxy=0, fg_oh=0.012, fg_cooh=0.001, fg_ester=0.02, fg_amine=0, fg_amide=0, fg_arom=0.1, fg_ether=0.02, wax=0, pig=0),
    # ================= 丙烯酸树脂 =================
    'AS400': dict(role='树脂', rtype='丙烯酸', NV=50, density=1.05, Mw=15000, EEW=0, AV=5, OHV=50, amine=0, func=1, Tg=45, bp=250, fp=100, dD=17.8, dP=6.5, dH=8.5, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.030, fg_cooh=0.003, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0.25, fg_ether=0.05, wax=0, pig=0),
    'RX170-140': dict(role='树脂', rtype='丙烯酸', NV=50, density=1.05, Mw=15000, EEW=0, AV=5, OHV=50, amine=0, func=1, Tg=45, bp=250, fp=100, dD=17.8, dP=6.5, dH=8.5, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.030, fg_cooh=0.003, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0.25, fg_ether=0.05, wax=0, pig=0),
    'AL525': dict(role='树脂', rtype='丙烯酸', NV=50, density=1.05, Mw=15000, EEW=0, AV=5, OHV=50, amine=0, func=1, Tg=45, bp=250, fp=100, dD=17.8, dP=6.5, dH=8.5, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.030, fg_cooh=0.003, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0.25, fg_ether=0.05, wax=0, pig=0),
    'AL710': dict(role='树脂', rtype='丙烯酸', NV=50, density=1.05, Mw=15000, EEW=0, AV=5, OHV=50, amine=0, func=1, Tg=45, bp=250, fp=100, dD=17.8, dP=6.5, dH=8.5, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.030, fg_cooh=0.003, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0.25, fg_ether=0.05, wax=0, pig=0),
    'AL800': dict(role='树脂', rtype='丙烯酸', NV=50, density=1.05, Mw=15000, EEW=0, AV=5, OHV=50, amine=0, func=1, Tg=45, bp=250, fp=100, dD=17.8, dP=6.5, dH=8.5, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.030, fg_cooh=0.003, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0.25, fg_ether=0.05, wax=0, pig=0),
    'IA800': dict(role='树脂', rtype='丙烯酸', NV=50, density=1.05, Mw=15000, EEW=0, AV=5, OHV=50, amine=0, func=1, Tg=45, bp=250, fp=100, dD=17.8, dP=6.5, dH=8.5, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.030, fg_cooh=0.003, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0.25, fg_ether=0.05, wax=0, pig=0),
    'IA8000': dict(role='树脂', rtype='丙烯酸', NV=50, density=1.05, Mw=15000, EEW=0, AV=5, OHV=50, amine=0, func=1, Tg=45, bp=250, fp=100, dD=17.8, dP=6.5, dH=8.5, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.030, fg_cooh=0.003, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0.25, fg_ether=0.05, wax=0, pig=0),
    'IA151': dict(role='树脂', rtype='丙烯酸', NV=50, density=1.05, Mw=15000, EEW=0, AV=5, OHV=50, amine=0, func=1, Tg=45, bp=250, fp=100, dD=17.8, dP=6.5, dH=8.5, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.030, fg_cooh=0.003, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0.25, fg_ether=0.05, wax=0, pig=0),
    'IA893': dict(role='树脂', rtype='丙烯酸', NV=50, density=1.05, Mw=15000, EEW=0, AV=5, OHV=50, amine=0, func=1, Tg=45, bp=250, fp=100, dD=17.8, dP=6.5, dH=8.5, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.030, fg_cooh=0.003, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0.25, fg_ether=0.05, wax=0, pig=0),
    # ================= 溶剂 =================
    'TM004': dict(role='溶剂', rtype='其他', NV=0, density=0.90, Mw=118.2, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-70, bp=171, fp=60, dD=16.0, dP=5.1, dH=12.3, pol=3.1, evap=0.07, C=61, H=12, O=27, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.85, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0.85, wax=0, pig=0),
    '正丁醇': dict(role='溶剂', rtype='其他', NV=0, density=0.81, Mw=74.1, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-90, bp=117.7, fp=35, dD=15.8, dP=5.7, dH=15.8, pol=3.9, evap=0.44, C=65, H=14, O=22, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=1.35, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0, wax=0, pig=0),
    '二甲苯': dict(role='溶剂', rtype='其他', NV=0, density=0.86, Mw=106.2, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-48, bp=139, fp=25, dD=17.8, dP=1.0, dH=3.1, pol=2.5, evap=0.7, C=90, H=10, O=0, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=1.0, fg_ether=0, wax=0, pig=0),
    '补加混合液': dict(role='溶剂', rtype='其他', NV=0, density=0.89, Mw=114.2, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-63, bp=160, fp=48, dD=16.6, dP=3.7, dH=9.2, pol=2.9, evap=0.28, C=71, H=11, O=18, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.57, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0.33, fg_ether=0.57, wax=0, pig=0),
    'TZ161': dict(role='溶剂', rtype='其他', NV=0, density=0.97, Mw=132.2, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-80, bp=146, fp=42, dD=15.6, dP=5.6, dH=9.8, pol=3.4, evap=0.34, C=55, H=9, O=36, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0.76, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0.76, wax=0, pig=0),
    'TZ425': dict(role='溶剂', rtype='其他', NV=0, density=1.09, Mw=160, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-60, bp=210, fp=100, dD=16.5, dP=6.5, dH=7.5, pol=3.0, evap=0.02, C=50, H=7, O=43, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0.62, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0.62, wax=0, pig=0),
    'TZ240': dict(role='溶剂', rtype='其他', NV=0, density=0.88, Mw=116.2, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-78, bp=126, fp=22, dD=15.8, dP=3.7, dH=6.3, pol=2.8, evap=1.0, C=62, H=10, O=28, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0.86, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0.86, wax=0, pig=0),
    'TT444': dict(role='溶剂', rtype='其他', NV=0, density=0.80, Mw=72.1, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-86, bp=79.6, fp=-9, dD=16.0, dP=9.0, dH=5.1, pol=4.7, evap=3.8, C=67, H=11, O=22, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0, wax=0, pig=0),
    'TT066': dict(role='溶剂', rtype='其他', NV=0, density=0.95, Mw=98.1, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-32, bp=155.6, fp=44, dD=17.8, dP=6.3, dH=5.1, pol=4.2, evap=0.3, C=73, H=10, O=16, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0, wax=0, pig=0),
    'TM982': dict(role='溶剂', rtype='其他', NV=0, density=0.92, Mw=90.1, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-96, bp=120, fp=32, dD=15.6, dP=6.3, dH=11.6, pol=3.6, evap=0.65, C=53, H=11, O=36, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=1.11, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=1.11, wax=0, pig=0),
    'TM024': dict(role='溶剂', rtype='其他', NV=0, density=0.96, Mw=162.2, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-68, bp=231, fp=100, dD=16.0, dP=7.0, dH=10.0, pol=3.4, evap=0.01, C=59, H=11, O=30, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.62, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0.62, wax=0, pig=0),
    'TM221': dict(role='溶剂', rtype='其他', NV=0, density=0.90, Mw=118.2, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-70, bp=171, fp=60, dD=16.0, dP=5.1, dH=12.3, pol=3.1, evap=0.07, C=61, H=12, O=27, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.85, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0.85, wax=0, pig=0),
    'TZ221': dict(role='溶剂', rtype='其他', NV=0, density=0.90, Mw=118.2, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-70, bp=171, fp=60, dD=16.0, dP=5.1, dH=12.3, pol=3.1, evap=0.07, C=61, H=12, O=27, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.85, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0.85, wax=0, pig=0),
    # ================= 助剂 =================
    'AZ088': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=5000, EEW=0, AV=10, OHV=30, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.5, dH=8.5, pol=3.2, evap=0.0, C=65, H=9, O=25, N=1, S=0, Cl=0, fg_epoxy=0, fg_oh=0.018, fg_cooh=0.006, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'BYK104': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=5000, EEW=0, AV=30, OHV=20, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.5, dH=8.5, pol=3.2, evap=0.0, C=60, H=9, O=30, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.012, fg_cooh=0.018, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'AC040': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'AZ135': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'AZ306': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'AZ551': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'BYK306': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'FL208': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'FL208S': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'FL815C': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'RA009': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'RA083': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    'RA824': dict(role='助剂', rtype='其他', NV=100, density=1.00, Mw=3000, EEW=0, AV=5, OHV=40, amine=0, func=0, Tg=20, bp=300, fp=150, dD=17.5, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=65, H=9, O=25, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.024, fg_cooh=0.003, fg_ester=0.20, fg_amine=0, fg_amide=0.05, fg_arom=0.2, fg_ether=0.1, wax=0, pig=0),
    '1510蜡': dict(role='助剂', rtype='其他', NV=25, density=0.90, Mw=400, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-10, bp=350, fp=200, dD=16.0, dP=0.5, dH=0.5, pol=0.5, evap=0.0, C=85, H=15, O=0, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0, wax=25, pig=0),
    '10%磷酸': dict(role='助剂', rtype='其他', NV=10, density=1.05, Mw=98, EEW=0, AV=570, OHV=0, amine=0, func=3, Tg=-50, bp=100, fp=0, dD=20.0, dP=15.0, dH=20.0, pol=5.0, evap=0.3, C=0, H=3, O=65, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0.57, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0, wax=0, pig=0),
    '3%气硅': dict(role='助剂', rtype='其他', NV=3, density=1.00, Mw=60, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=-50, bp=100, fp=0, dD=18.0, dP=8.0, dH=10.0, pol=3.0, evap=0.5, C=0, H=0, O=50, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0, wax=0, pig=0),
    '20%CAB': dict(role='助剂', rtype='其他', NV=20, density=0.95, Mw=30000, EEW=0, AV=2, OHV=10, amine=0, func=0, Tg=100, bp=250, fp=100, dD=18.0, dP=6.0, dH=8.0, pol=3.0, evap=0.0, C=55, H=7, O=38, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0.006, fg_cooh=0.001, fg_ester=0.30, fg_amine=0, fg_amide=0, fg_arom=0, fg_ether=0.3, wax=0, pig=0),
    # ================= 颜料/浆料 =================
    'RY460': dict(role='颜料', rtype='其他', NV=100, density=4.0, Mw=200, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=0, bp=500, fp=300, dD=20.0, dP=10.0, dH=8.0, pol=3.0, evap=0.0, C=10, H=0, O=20, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0.5, fg_ether=0, wax=0, pig=100),
    'RY075N': dict(role='颜料', rtype='其他', NV=100, density=4.0, Mw=200, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=0, bp=500, fp=300, dD=20.0, dP=10.0, dH=8.0, pol=3.0, evap=0.0, C=10, H=0, O=20, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0.5, fg_ether=0, wax=0, pig=100),
    'RY078': dict(role='颜料', rtype='其他', NV=100, density=4.0, Mw=200, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=0, bp=500, fp=300, dD=20.0, dP=10.0, dH=8.0, pol=3.0, evap=0.0, C=10, H=0, O=20, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0, fg_amine=0, fg_amide=0, fg_arom=0.5, fg_ether=0, wax=0, pig=100),
    '35.7%白浆': dict(role='颜料', rtype='其他', NV=35.7, density=1.8, Mw=200, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=0, bp=300, fp=150, dD=19.0, dP=8.0, dH=7.0, pol=3.0, evap=0.0, C=20, H=2, O=40, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0.1, fg_amine=0, fg_amide=0, fg_arom=0.2, fg_ether=0.1, wax=0, pig=35.7),
    '14.28%炭黑浆料': dict(role='颜料', rtype='其他', NV=14.28, density=1.2, Mw=200, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=0, bp=300, fp=150, dD=19.0, dP=8.0, dH=7.0, pol=3.0, evap=0.0, C=80, H=2, O=10, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0.1, fg_amine=0, fg_amide=0, fg_arom=0.5, fg_ether=0, wax=0, pig=14.28),
    '日本151-PVC': dict(role='颜料', rtype='其他', NV=100, density=1.5, Mw=200, EEW=0, AV=0, OHV=0, amine=0, func=0, Tg=0, bp=300, fp=150, dD=19.0, dP=8.0, dH=7.0, pol=3.0, evap=0.0, C=50, H=5, O=20, N=0, S=0, Cl=0, fg_epoxy=0, fg_oh=0, fg_cooh=0, fg_ester=0.1, fg_amine=0, fg_amide=0, fg_arom=0.3, fg_ether=0.1, wax=0, pig=100),
}

# 别名映射（同一原料的不同写法）
# 组成经验补全：对已送检原料，用 compo_rules 的组成证据覆盖类别典型值基线
import os as _os, sys as _sys
_pth = _os.path.dirname(_os.path.abspath(__file__))
if _pth not in _sys.path:
    _sys.path.insert(0, _pth)
from compo_rules import apply as _compo_apply
_compo_apply(MAT)

# 供应商 TDS/SDS 实测层（优先级最高）：把「类别典型值」替换为该到货牌号的实测值。
# 关闭：环境变量 MATERIALS_TDS=0（A/B 对照实验用）
if _os.environ.get('MATERIALS_TDS', '1') != '0':
    from tds_sds import apply as _tds_apply
    _tds_apply(MAT)

ALIAS = {
    'tf100': 'TF100', 'IR809 55%': 'IR809', 'IR809': 'IR809',
    'IR809 55%(PR309 稀释55%)': 'IR809',
    'RF950（PR8219-50）': 'RF950', 'RF956（PR8219-65）': 'RF956',
    'RF160(PR33160G)': 'RF160', 'RF401(PR401)': 'RF401',
    'RF516（PR516）': 'RF516', 'RH601（SM601RX75)': 'RH601',
    '住友55754G': '住友55754G', '1510蜡25%工作液': '1510蜡',
    'AZ088（BYK088)': 'AZ088', '10%磷酸': '10%磷酸',
    '补加混合液（乙二醇单丁醚：二甲苯=2:1）': '补加混合液',
    'IR190(9型环氧树脂36%固含）': 'IR190',
    '外加正丁醇': '正丁醇', '正丁醇': '正丁醇',
    'RX170\n-140': 'RX170-140', 'RX170-140': 'RX170-140',
    '40%50177': '40%50177', '杜邦-FT960': '杜邦-FT960',
    '35.7%白浆-新': '35.7%白浆', '35.7%白浆-209': '35.7%白浆',
    '35.7%\n白浆-209': '35.7%白浆', '35.7%\n白浆-新': '35.7%白浆',
    '35.7%白浆（25.3.7）': '35.7%白浆',
    '14.28%-炭黑浆料': '14.28%炭黑浆料', '14.28%\n-炭黑浆料': '14.28%炭黑浆料',
    '14.28%炭黑浆料': '14.28%炭黑浆料',
    'BYK-306': 'BYK306', 'BYK306': 'BYK306',
    '10%AC040': 'AC040',
}

CONT_DESC = ['NV','density','Mw','EEW','AV','OHV','amine','func','Tg','bp','fp',
             'dD','dP','dH','pol','evap','C','H','O','N','S','Cl',
             'fg_epoxy','fg_oh','fg_cooh','fg_ester','fg_amine','fg_amide','fg_arom','fg_ether',
             'wax','pig']
ROLES = ['树脂','固化剂','溶剂','助剂','颜料']
RTYPES = ['环氧','酚醛','聚酯','乙烯基','丙烯酸','聚氨酯','氨基','其他']
