# -*- coding: utf-8 -*-
"""
TDS/SDS 覆盖度审计：量化「实测锚定」与「类别典型值填充」的占比
============================================================
对同一套原料库分别在两种状态下统计（MATERIALS_TDS=0/1）：
  A 原料级   —— 每种原料的主导来源（TDS/SDS 实测、送检组成、公开手册、类别典型值）
  B 字段级   —— 32 个描述符字段逐一的来源计数（区分关键化学量与其余字段）
  C 用量加权 —— 按配方实际用量质量折算的来源占比（决定特征空间的可信度），分体系给出
  D 样本级   —— 每个样本的「实测锚定权重」= Σ 组分质量分数 × 该原料关键字段覆盖率

输出：scripts/_tds_coverage.json + 控制台摘要。
"""
import os, sys, json, pickle, copy, importlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WB = os.path.join(HERE, '..', 'workbench')
sys.path.insert(0, WB)
sys.path.insert(0, HERE)

KEY_CHEM = ['NV', 'density', 'Mw', 'EEW', 'AV', 'OHV', 'Tg', 'fg_epoxy', 'fg_oh', 'fg_cooh']
ALL_DESC = ['NV', 'density', 'Mw', 'EEW', 'AV', 'OHV', 'amine', 'func', 'Tg', 'bp', 'fp',
            'dD', 'dP', 'dH', 'pol', 'evap', 'C', 'H', 'O', 'N', 'S', 'Cl',
            'fg_epoxy', 'fg_oh', 'fg_cooh', 'fg_ester', 'fg_amine', 'fg_amide',
            'fg_arom', 'fg_ether', 'wax', 'pig']
DOC_SRC = ('tds', 'sds', 'formula', 'tds_carry', 'name')      # 供应商技术档案实测
ANY_SRC = DOC_SRC + ('compo', 'handbook', 'family')            # 含送检/手册/档案族推断的广义依据
FAMILY_SRC = ('family',)                                       # 档案族推断（牌号未识别，按同族档近似）


def build_library(use_tds):
    """按「合并版数据集」的加工链重建原料库：类别典型值 → 送检组成 → 占位修正 → TDS/SDS。"""
    os.environ['MATERIALS_TDS'] = '0'
    for m in ('materials', 'tds_sds', 'compo_rules', 'mech_desc', 'handbook_fixes'):
        sys.modules.pop(m, None)
    import handbook_fixes as HF
    import tds_sds
    D = pickle.load(open(os.path.join(HERE, '..', 'data', 'merged_data.pkl'), 'rb'))
    mat = {k: copy.deepcopy(v) for k, v in D['full_mat'].items()}   # 已含送检组成层
    _ch, merge, _pd = HF.apply(mat)
    for c in merge:
        mat.pop(c, None)
    tds_sds.apply(mat, use_tds=use_tds)
    for c in merge:
        D['new_mats'] = [x for x in D['new_mats'] if x != c]
    return mat, D


def ensure_prov(mat):
    """为未经 TDS 层加工的库补齐 prov（送检组成/公开手册/类别典型值三档）。"""
    import compo_rules
    import handbook_fixes as HF
    for code, m in mat.items():
        if m.get('prov'):
            continue
        pv = {}
        src = m.get('数据来源') or ''
        if src == 'COMPO_RULES':
            for k in compo_rules.OVERRIDES.get(code, {}):
                pv[k] = 'compo'
        elif src.startswith('handbook'):
            for k in HF.FIXES.get(code, {}):
                if k not in ('依据', '口径'):
                    pv[k] = 'handbook'
        m['prov'] = pv


def dominant(m):
    """原料主导来源。"""
    src = m.get('数据来源') or ''
    if src == 'TDS族推':
        return 'TDS族推'
    if src.startswith('TDS'):
        return 'TDS/SDS实测'
    if src == 'COMPO_RULES':
        return '送检组成'
    if src.startswith('handbook'):
        return '公开手册'
    if src == 'pending_TDS':
        return '待确认'
    return '类别典型值'


def field_prov(mat, code):
    pv = mat[code].get('prov') or {}
    return {k: pv.get(k, 'typical') for k in ALL_DESC}


def coverage(mat):
    """字段级与原料级覆盖统计。"""
    ensure_prov(mat)
    n = len(mat)
    by_src = {}
    field_doc = {k: 0 for k in ALL_DESC}
    field_fam = {k: 0 for k in ALL_DESC}
    field_any = {k: 0 for k in ALL_DESC}
    key_doc = {k: 0 for k in KEY_CHEM}
    per_code = {}
    for code in mat:
        by_src[dominant(mat[code])] = by_src.get(dominant(mat[code]), 0) + 1
        fp = field_prov(mat, code)
        per_code[code] = fp
        for k in ALL_DESC:
            if fp[k] in DOC_SRC:
                field_doc[k] += 1
            if fp[k] in FAMILY_SRC:
                field_fam[k] += 1
            if fp[k] in ANY_SRC:
                field_any[k] += 1
        for k in KEY_CHEM:
            if fp[k] in DOC_SRC:
                key_doc[k] += 1
    nf = n * len(ALL_DESC)
    return dict(n_materials=n, by_material_source=by_src,
                field_documented=field_doc, key_chem_documented=key_doc,
                field_ratio_doc=round(sum(field_doc.values()) / nf, 4),
                field_ratio_family=round(sum(field_fam.values()) / nf, 4),
                field_ratio_any=round(sum(field_any.values()) / nf, 4),
                field_documented_any=field_any,
                field_ratio_key=round(sum(key_doc.values()) / (n * len(KEY_CHEM)), 4),
                per_code=per_code)


def mass_weighted(mat, D):
    """按配方用量质量加权的来源占比 + 样本级实测锚定权重。"""
    tot = {k: 0.0 for k in ['TDS/SDS实测', 'TDS族推', '送检组成', '公开手册', '类别典型值', '待确认']}
    by_sys = {}
    sample_anchor = {}
    key_cov = {c: (sum(1 for k in KEY_CHEM if mat[c]['prov'].get(k, 'typical') in DOC_SRC) / len(KEY_CHEM))
               if c in mat else 0.0 for c in mat}
    for s in D['all_samples']:
        comp = s['组分']
        w = {c: float(a) for c, a in comp.items() if float(a) > 0}
        t = sum(w.values())
        if t <= 0:
            continue
        sysn = s['体系']
        d = by_sys.setdefault(sysn, {k: 0.0 for k in tot})
        anchor = 0.0
        for c, a in w.items():
            code = c
            if code not in mat:
                from CoatingModelWorkbench import canon
                code = canon(str(c).strip())
            if code not in mat:
                continue
            f = a / t
            src = dominant(mat[code])
            tot[src] += a
            d[src] += a
            anchor += f * key_cov[code]
        sample_anchor[s['样本ID']] = round(anchor, 4)
        by_sys[sysn]['_total'] = by_sys[sysn].get('_total', 0.0) + t
    grand = sum(tot.values())
    return dict(mass_share_by_source={k: round(v / grand, 4) for k, v in tot.items()},
                mass_share_total=round(grand, 1),
                by_system={s: {k: round(v / d['_total'], 4) for k, v in d.items() if k != '_total'}
                           for s, d in by_sys.items()},
                sample_anchor=sample_anchor,
                key_chem_mass_coverage=round(sum(v * key_cov.get(c, 0.0)
                                                 for c, v in _code_mass(D, mat).items()
                                                 if c in mat) / max(sum(_code_mass(D, mat).values()), 1e-9), 4))


def _code_mass(D, mat):
    from CoatingModelWorkbench import canon
    m = {}
    for s in D['all_samples']:
        for c, a in s['组分'].items():
            code = c if c in mat else canon(str(c).strip())
            if code in mat:
                m[code] = m.get(code, 0.0) + float(a)
    return m


def main():
    mat_old, D = build_library(False)
    mat_new, _ = build_library(True)
    cov_old, cov_new = coverage(mat_old), coverage(mat_new)
    mw_old, mw_new = mass_weighted(mat_old, D), mass_weighted(mat_new, D)
    out = dict(materials=len(mat_new),
               before=dict(material=cov_old['by_material_source'], field_ratio_doc=cov_old['field_ratio_doc'],
                           field_ratio_family=cov_old['field_ratio_family'],
                           field_ratio_any=cov_old['field_ratio_any'],
                           field_ratio_key=cov_old['field_ratio_key'],
                           key_chem_documented=cov_old['key_chem_documented'],
                           mass_share=mw_old['mass_share_by_source'],
                           mass_share_by_system=mw_old['by_system'],
                           key_chem_mass_coverage=mw_old['key_chem_mass_coverage']),
               after=dict(material=cov_new['by_material_source'], field_ratio_doc=cov_new['field_ratio_doc'],
                          field_ratio_family=cov_new['field_ratio_family'],
                          field_ratio_any=cov_new['field_ratio_any'],
                          field_ratio_key=cov_new['field_ratio_key'],
                          key_chem_documented=cov_new['key_chem_documented'],
                          mass_share=mw_new['mass_share_by_source'],
                          mass_share_by_system=mw_new['by_system'],
                          key_chem_mass_coverage=mw_new['key_chem_mass_coverage']),
               per_field_delta={k: dict(before=cov_old['field_documented'][k],
                                        after=cov_new['field_documented'][k],
                                        n_materials=cov_new['n_materials']) for k in ALL_DESC},
               tds_codes=sorted([c for c, m in mat_new.items()
                                 if (m.get('数据来源') or '').startswith('TDS')]),
               pending_codes={c: _pend(c) for c in sorted(mat_new)
                              if not (mat_new[c].get('数据来源') or '').startswith('TDS')},
               sample_anchor_before=mw_old['sample_anchor'], sample_anchor_after=mw_new['sample_anchor'])
    dst = os.path.join(HERE, '_tds_coverage.json')
    json.dump(out, open(dst, 'w'), ensure_ascii=False, indent=1)
    print(f'原料 {out["materials"]} 种 | TDS/SDS 覆盖 {len(out["tds_codes"])} 种')
    print('主导来源（原料数）    前:', cov_old['by_material_source'], ' 后:', cov_new['by_material_source'])
    print(f'字段级有据可依占比（含送检组成/公开手册）：{cov_old["field_ratio_any"]:.3f} → {cov_new["field_ratio_any"]:.3f}')
    print(f'字段级 TDS/SDS 实测占比：{cov_old["field_ratio_doc"]:.3f} → {cov_new["field_ratio_doc"]:.3f} | '
          f'家族推断 {cov_new["field_ratio_family"]:.3f} | '
          f'关键化学量 {cov_old["field_ratio_key"]:.3f} → {cov_new["field_ratio_key"]:.3f}')
    print('用量加权来源占比 前:', mw_old['mass_share_by_source'])
    print('                后:', mw_new['mass_share_by_source'])
    for s in mw_new['by_system']:
        print(f'  {s}: 前 {mw_old["by_system"].get(s)}')
        print(f'  {" " * len(s)}  后 {mw_new["by_system"].get(s)}')
    a_old = np.mean(list(mw_old['sample_anchor'].values()))
    a_new = np.mean(list(mw_new['sample_anchor'].values()))
    print(f'样本级关键字段实测锚定权重（均值）：{a_old:.3f} → {a_new:.3f}')
    print(f'写出 {dst}')


def _pend(code):
    try:
        import tds_sds
        return tds_sds.PENDING.get(code, '档案未覆盖（类别典型值/送检组成）')
    except Exception:
        return ''


if __name__ == '__main__':
    main()
