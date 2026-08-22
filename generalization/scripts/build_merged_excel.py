# -*- coding: utf-8 -*-
"""
合并版数据集 Excel 生成：终极版模板结构 + 全部数据
==================================================
- 原料主数据：85 种原料（含新增估算）
- 配方明细：514 样本（373 有标签 + 141 无标签）
- 性能结果：有标签样本的 T弯/MEK/水煮
- 工艺条件：烘烤参数
- 配方级描述符：数值填充（不依赖公式）
- 建模输入：ML-ready 宽表
"""
import pickle, warnings, os
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from materials import CONT_DESC, ALIAS

D = pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'merged_data.pkl'),'rb'))
full_mat = D['full_mat']; new_mats = D['new_mats']
all_samples = D['all_samples']; desc_df = D['desc_df']

def clean_code(code):
    """原始代码 → 清洗代码（应用ALIAS映射）"""
    key = str(code).strip()
    return ALIAS.get(key, key)

# ---------- 样式 ----------
HDR_FILL = PatternFill('solid', fgColor='1F2937')
HDR_FONT = Font(name='Arial', bold=True, color='FFFFFF', size=10)
ZEBRA_1 = PatternFill('solid', fgColor='FFFFFF')
ZEBRA_2 = PatternFill('solid', fgColor='F7F9FC')
KPI_FILL = PatternFill('solid', fgColor='EAF2FF')
GREEN_FILL = PatternFill('solid', fgColor='E3F5EA')
ORANGE_FILL = PatternFill('solid', fgColor='FFF1DE')
THIN = Side(style='thin', color='D9DEE7')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BODY_FONT = Font(name='Arial', size=10)
BOLD_FONT = Font(name='Arial', size=10, bold=True)
TITLE_FONT = Font(name='Arial', size=14, bold=True, color='1F2937')
NOTE_FONT = Font(name='Arial', size=9, color='6B7280')

def style_table(ws, header_row, n_cols, n_rows, kpi_cols=None):
    for c in range(1, n_cols+1):
        cell = ws.cell(header_row, c)
        cell.fill = HDR_FILL; cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BORDER
    for r in range(header_row+1, header_row+n_rows+1):
        fill = ZEBRA_1 if (r-header_row) % 2 == 0 else ZEBRA_2
        for c in range(1, n_cols+1):
            cell = ws.cell(r, c)
            cell.fill = fill; cell.font = BODY_FONT; cell.border = BORDER
            cell.alignment = Alignment(vertical='center', wrap_text=True)
    if kpi_cols:
        for c in kpi_cols:
            for r in range(header_row+1, header_row+n_rows+1):
                ws.cell(r, c).fill = KPI_FILL
                ws.cell(r, c).font = BOLD_FONT

wb = Workbook()

# ================= Sheet1 使用说明 =================
ws = wb.active; ws.title = '使用说明'
ws.column_dimensions['A'].width = 3
ws.column_dimensions['B'].width = 120
lines = [
    ('合并版涂料配方-性能数据集（终极版模板 v3 填充）', ''),
    ('', ''),
    ('一、数据构成', '本文件将现有全部数据源整理并填入终极版模板 v3：'),
    ('', '  · 有标签样本 373 条（环氧酚醛体系，含 T弯/MEK/水煮 实测值）'),
    ('', '  · 无标签配方 141 条（环氧配比方案 112 + 聚酯金黄 29）'),
    ('', '  · 原料主数据 85 种（含按代码模式估算的新原料）'),
    ('', ''),
    ('二、数据来源', '1. 配料测试数据汇总V1.xlsx（有标签）'),
    ('', '2. AI研发26.7.22配比方案.xlsx（无标签-环氧）'),
    ('', '3. 聚酯金黄-AI(1).xlsx（无标签-聚酯）'),
    ('', '4. AI项目原料送检、部分实验数据.xlsx（原料信息）'),
    ('', ''),
    ('三、工作表说明', '1. 原料主数据：85 种原料描述符（新增原料为估算值，标注"估算"）。'),
    ('', '2. 配方明细：514 样本的配方长表（每行=一个组分）。'),
    ('', '3. 性能结果：有标签样本的实测性能。'),
    ('', '4. 工艺条件：烘烤温度/时间等。'),
    ('', '5. 配方级描述符：514×60 特征矩阵（数值，可直接建模）。'),
    ('', '6. 建模输入：宽表，一行=一个样本，特征+目标，可直接导入训练。'),
    ('', ''),
    ('四、使用建议', '1. 建模时按"标签状态"筛选：实测样本用于训练/验证，无标签样本用于预测。'),
    ('', '2. 新增原料请在"原料主数据"补充真实描述符（SDS/TDS），替换估算值。'),
    ('', '3. 用配套 Windows 工作台可一键完成建模与预测。'),
]
r = 1
for text, _ in lines:
    cell = ws.cell(r, 2, text)
    if r == 1:
        cell.font = TITLE_FONT
    elif text.startswith(('一、','二、','三、','四、')):
        cell.font = BOLD_FONT
    else:
        cell.font = BODY_FONT
    cell.alignment = Alignment(vertical='center', wrap_text=True)
    r += 1

# ================= Sheet2 体系配置 =================
ws = wb.create_sheet('体系配置')
sys_headers = ['体系名称','固化机制','典型树脂类型','目标属性','单位','方向','数据类型','适用标准/说明']
ws.append(sys_headers)
sys_rows = [
    ('环氧酚醛','环氧-酚醛缩合','环氧/酚醛','T弯','mm','越低越好','连续','杯突/弯曲试验'),
    ('环氧酚醛','环氧-酚醛缩合','环氧/酚醛','MEK擦拭','次','越高越好','计数','MEK溶剂擦拭'),
    ('环氧酚醛','环氧-酚醛缩合','环氧/酚醛','水煮等级','级','越低越好','等级','1-5级水煮'),
    ('环氧配比方案','环氧-酚醛缩合','环氧/酚醛','T弯','mm','越低越好','连续','弯曲试验'),
    ('环氧配比方案','环氧-酚醛缩合','环氧/酚醛','MEK擦拭','次','越高越好','计数','MEK溶剂擦拭'),
    ('聚酯金黄','羟基-氨基树脂','聚酯','T弯','mm','越低越好','连续','弯曲试验'),
    ('聚酯金黄','羟基-氨基树脂','聚酯','MEK擦拭','次','越高越好','计数','MEK溶剂擦拭'),
    ('有机','羟基-氨基树脂','丙烯酸/乙烯基/环氧','T弯','mm','越低越好','连续','弯曲试验'),
    ('有机','羟基-氨基树脂','丙烯酸/乙烯基/环氧','MEK擦拭','次','越高越好','计数','MEK溶剂擦拭'),
    ('聚氨酯','羟基-异氰酸酯','聚酯/丙烯酸/聚氨酯','T弯','mm','越低越好','连续','弯曲试验'),
    ('聚氨酯','羟基-异氰酸酯','聚酯/丙烯酸/聚氨酯','MEK擦拭','次','越高越好','计数','MEK溶剂擦拭'),
    ('丙烯酸','自由基聚合/羟基-氨基','丙烯酸','T弯','mm','越低越好','连续','弯曲试验'),
    ('丙烯酸','自由基聚合/羟基-氨基','丙烯酸','MEK擦拭','次','越高越好','计数','MEK溶剂擦拭'),
    ('环氧胺','环氧-胺加成','环氧','T弯','mm','越低越好','连续','弯曲试验'),
    ('环氧胺','环氧-胺加成','环氧','MEK擦拭','次','越高越好','计数','MEK溶剂擦拭'),
]
for row in sys_rows:
    ws.append(list(row))
n_sys = len(sys_rows)
style_table(ws, 1, len(sys_headers), n_sys, kpi_cols=[1,4,5,6,7])
for i, w in enumerate([14,20,22,14,8,12,10,24], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = 'A2'

# ================= Sheet3 原料主数据 =================
ws = wb.create_sheet('原料主数据')
mat_headers = ['原料代码','原料名称','所属体系','角色','树脂类型','SMILES','描述符状态',
               '固含NV(%)','密度(g/cm³)','分子量(g/mol)',
               '环氧当量EEW(g/eq)','酸值AV(mgKOH/g)','羟值OHV(mgKOH/g)','胺值(mgKOH/g)','官能度',
               'Tg(℃)','沸点(℃)','闪点(℃)','Hansen δD','Hansen δP','Hansen δH','极性指数','相对挥发速率',
               'C(%)','H(%)','O(%)','N(%)','S(%)','Cl(%)',
               '环氧基(mol/100g)','羟基(mol/100g)','羧基(mol/100g)','酯基(mol/100g)','胺基(mol/100g)',
               '酰胺(mol/100g)','芳香环(mol/100g)','醚键(mol/100g)','蜡含量(%)','颜料含量(%)','数据来源','备注']
ws.append(mat_headers)
names = {'IR190':'9型环氧树脂36%固含','IR809':'环氧树脂55%固含','住友55754G':'住友环氧树脂','RF401':'酚醛固化剂PR401',
         'RF160':'酚醛固化剂PR33160G','RF516':'酚醛固化剂PR516','RF950':'酚醛固化剂PR8219-50','RF956':'酚醛固化剂PR8219-65',
         'RH601':'酚醛固化剂SM601RX75','1510蜡':'1510蜡25%工作液','AZ088':'分散剂BYK088','正丁醇':'正丁醇',
         '补加混合液':'乙二醇单丁醚:二甲苯=2:1','10%磷酸':'磷酸10%水溶液','TF100':'乙烯基树脂','TM004':'乙二醇丁醚',
         'AS400':'丙烯酸树脂','RX170-140':'丙烯酸树脂','40%50177':'环氧树脂40%固含','IR877':'环氧树脂','RJ173M':'聚酯树脂',
         'RJ561':'聚酯树脂','RY460':'黄色颜料','AC040':'助剂','BYK104':'分散剂BYK104','IR909':'环氧树脂','R170M':'环氧树脂',
         'IR557':'环氧树脂','TF022':'乙烯基树脂','TM221':'乙二醇丁醚','IR868':'环氧树脂','RY075N':'黄色颜料','AZ135':'助剂',
         '35.7%白浆':'白色颜料浆35.7%','14.28%炭黑浆料':'炭黑浆料14.28%','3%气硅':'气相二氧化硅3%','20%CAB':'CAB溶液20%',
         '杜邦-FT960':'环氧树脂','AL525':'丙烯酸树脂','AL710':'丙烯酸树脂','AZ306':'助剂','AZ551':'助剂','BYK306':'流平剂',
         'FL208':'助剂','FL208S':'助剂','FL815C':'助剂','IA151':'丙烯酸树脂','IA893':'丙烯酸树脂','IR842':'环氧树脂',
         'RA009':'助剂','RA083':'助剂','RA824':'助剂','RJ183':'聚酯树脂','RJ362':'聚酯树脂','日本151-PVC':'颜料浆',
         'TZ161':'PMA溶剂','TZ425':'DBE溶剂','TZ240':'醋酸丁酯','TT444':'丁酮','TT066':'环己酮','TM982':'PM溶剂',
         'TM024':'二乙二醇单丁醚','TZ221':'乙二醇丁醚','RY078':'黄色颜料','AL800':'丙烯酸树脂','IA800':'丙烯酸树脂',
         'IA8000':'丙烯酸树脂','10%AC040':'AC040 10%'}
for code, d in full_mat.items():
    is_new = code in new_mats
    row = [code, names.get(code, code), '多体系', d['role'], d['rtype'], '', '专有估算' if is_new else '已计算']
    for k in ['NV','density','Mw','EEW','AV','OHV','amine','func','Tg','bp','fp','dD','dP','dH','pol','evap',
              'C','H','O','N','S','Cl','fg_epoxy','fg_oh','fg_cooh','fg_ester','fg_amine','fg_amide','fg_arom','fg_ether','wax','pig']:
        row.append(d[k])
    row.append('估算' if is_new else '类别典型值/文件信息')
    row.append('')
    ws.append(row)
n_mat = len(full_mat)
style_table(ws, 1, len(mat_headers), n_mat, kpi_cols=[8,11,12,13,14,15,30,31,32,33,34,35,36,37])
widths = [16,20,10,8,9,14,10,10,10,11,12,12,12,11,8,8,9,9,9,9,9,10,8,8,8,8,8,8,10,10,10,10,10,10,10,10,9,9,14,20]
for i, w in enumerate(widths, 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = 'A2'

# ================= Sheet3 配方明细 =================
ws = wb.create_sheet('配方明细')
det_headers = ['样本ID','系列','体系','原料代码','用量(g)','角色','树脂类型','标签状态']
ws.append(det_headers)
det_rows = 0
for s in all_samples:
    for code, amt in s['组分'].items():
        ccode = clean_code(code)
        d = full_mat.get(ccode)
        if d is None: continue
        ws.append([s['样本ID'], s['系列'], s['体系'], ccode, round(float(amt),4), d['role'], d['rtype'], s['标签状态']])
        det_rows += 1
style_table(ws, 1, len(det_headers), det_rows, kpi_cols=[4])
for i, w in enumerate([14,12,16,10,8,9,10], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = 'A2'

# ================= Sheet4 性能结果 =================
ws = wb.create_sheet('性能结果')
perf_headers = ['样本ID','体系','目标属性','测试值','单位','标签状态','标签来源','测试条件']
ws.append(perf_headers)
perf_rows = 0
for s in all_samples:
    if s['标签状态'] != '实测': continue
    cond = f"{s['烘烤温度']}℃ {s['烘烤时间']}min" if s['烘烤温度'] else ''
    for tgt, val, unit in [('T弯', s['T弯'], 'mm'), ('MEK擦拭', s['MEK'], '次'), ('水煮等级', s['水煮'], '级')]:
        if val is not None and not (isinstance(val, float) and np.isnan(val)):
            ws.append([s['样本ID'], s['体系'], tgt, round(float(val),4), unit, '实测', '实验室', cond])
            perf_rows += 1
style_table(ws, 1, len(perf_headers), perf_rows, kpi_cols=[4])
for i, w in enumerate([14,12,12,10,8,10,10,18], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = 'A2'

# ================= Sheet5 工艺条件 =================
ws = wb.create_sheet('工艺条件')
proc_headers = ['样本ID','体系','烘烤温度(℃)','烘烤时间(min)','标签状态']
ws.append(proc_headers)
proc_rows = 0
for s in all_samples:
    ws.append([s['样本ID'], s['体系'], s['烘烤温度'], s['烘烤时间'], s['标签状态']])
    proc_rows += 1
style_table(ws, 1, len(proc_headers), proc_rows)
for i, w in enumerate([14,12,12,12,10], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = 'A2'

# ================= Sheet6 配方级描述符 =================
ws = wb.create_sheet('配方级描述符')
ser_map = {s['样本ID']: s['系列'] for s in all_samples}
fd_headers = ['样本ID','系列','体系','标签状态'] + list(desc_df.columns[2:])
ws.append(fd_headers)
for _, row in desc_df.iterrows():
    ws.append([row['样本ID'], ser_map.get(row['样本ID'], ''), row['体系'], '实测' if row['样本ID'] in {s['样本ID'] for s in all_samples if s['标签状态']=='实测'} else '无标签'] + [round(float(v),6) if isinstance(v,(int,float)) else v for v in row[2:]])
n_fd = len(desc_df)
style_table(ws, 1, len(fd_headers), n_fd, kpi_cols=[5,6,7])
for i, w in enumerate([14,10,12,10] + [10]*len(desc_df.columns[2:]), 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = 'D2'

# ================= Sheet7 建模输入 =================
ws = wb.create_sheet('建模输入')
mi_headers = ['样本ID','系列','体系','标签状态','T弯实测','MEK实测','水煮实测'] + list(desc_df.columns[2:])
ws.append(mi_headers)
lab_map = {s['样本ID']: s for s in all_samples}
for _, row in desc_df.iterrows():
    sid = row['样本ID']
    s = lab_map.get(sid, {})
    t_w = s.get('T弯'); m_w = s.get('MEK'); z_w = s.get('水煮')
    status = '实测' if s.get('标签状态') == '实测' else '无标签'
    ws.append([sid, ser_map.get(sid, ''), row['体系'], status,
               round(float(t_w),4) if t_w is not None else '', 
               round(float(m_w),4) if m_w is not None else '',
               round(float(z_w),4) if z_w is not None else ''] + [round(float(v),6) if isinstance(v,(int,float)) else v for v in row[2:]])
n_mi = len(desc_df)
style_table(ws, 1, len(mi_headers), n_mi, kpi_cols=[5,6,7])
for i, w in enumerate([14,10,12,10,10,10,10] + [10]*len(desc_df.columns[2:]), 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = 'H2'

# ================= Sheet8 数据字典 =================
ws = wb.create_sheet('数据字典')
dict_headers = ['字段名','所属工作表','类型','单位','口径说明','示例']
ws.append(dict_headers)
dict_rows = [
    ('样本ID','配方明细/性能结果/工艺条件/配方级描述符/建模输入','文本','-','全局唯一，关联各表','D1-1'),
    ('系列','配方明细/配方级描述符/建模输入','文本','-','配方系列/家族（如D1、R01），用于系列目标编码建模','D1'),
    ('体系','配方明细/性能结果','文本','-','化学体系类别：环氧酚醛/环氧-配比方案/聚酯金黄','环氧酚醛'),
    ('原料代码','原料主数据/配方明细','文本','-','原料唯一编码，与原料主数据一致','IR190'),
    ('用量','配方明细','数值','g','该组分在样本中的质量份','66.0'),
    ('角色','原料主数据/配方明细','枚举','-','树脂/固化剂/溶剂/助剂/颜料','树脂'),
    ('树脂类型','原料主数据/配方明细','枚举','-','环氧/酚醛/聚酯/乙烯基/丙烯酸/聚氨酯/其他','环氧'),
    ('标签状态','配方明细/性能结果/工艺条件/建模输入','枚举','-','实测/无标签/伪标签/推荐测试','实测'),
    ('T弯实测','建模输入','数值','mm','杯突/弯曲试验结果（越低越好）','17.415'),
    ('MEK实测','建模输入','数值','次','MEK溶剂擦拭次数（越高越好，封顶300）','9'),
    ('水煮实测','建模输入','数值','级','水煮等级1-5（越低越好）','4'),
    ('固含NV','原料主数据','数值','%','按到货状态的固体含量','36'),
    ('密度','原料主数据','数值','g/cm³','原料密度','1.00'),
    ('分子量','原料主数据','数值','g/mol','数均分子量（树脂可为典型值）','1400'),
    ('环氧当量EEW','原料主数据','数值','g/eq','含1mol环氧基的到货产品质量','2640'),
    ('酸值AV','原料主数据','数值','mgKOH/g','中和1g样品游离酸所需KOH','0.5'),
    ('羟值OHV','原料主数据','数值','mgKOH/g','中和1g样品羟基所需KOH','30'),
    ('Tg','原料主数据','数值','℃','玻璃化转变温度','70'),
    ('Hansen δD/δP/δH','原料主数据','数值','MPa^0.5','Hansen溶解度参数三分量','18.5/6.0/8.5'),
    ('C/H/O/N/S/Cl','原料主数据','数值','%','元素质量分数','72/7/20/0/0/0'),
    ('环氧基/羟基/羧基/酯基/胺基/酰胺/芳香环/醚键','原料主数据','数值','mol/100g','官能团密度','0.038'),
    ('树脂/固化剂/溶剂/助剂/颜料占比','配方级描述符','数值','-','各角色质量分数','0.72'),
    ('加权固含等','配方级描述符','数值','-','按质量分数加权的原料描述符','36.5'),
    ('环氧基密度等','配方级描述符','数值','mol/100g','每100g配方的官能团摩尔数','0.05'),
    ('烘烤温度/时间','工艺条件','数值','℃/min','固化工艺参数','205/17'),
]
for row in dict_rows:
    ws.append(list(row))
n_dict = len(dict_rows)
style_table(ws, 1, len(dict_headers), n_dict)
for i, w in enumerate([34,34,8,12,46,14], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = 'A2'

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '合并版数据集.xlsx')
wb.save(out)
print('saved:', out)
print(f"原料 {n_mat} 种, 配方明细 {det_rows} 行, 性能 {perf_rows} 行, 描述符 {n_fd} 样本×{len(desc_df.columns)-2} 特征")
