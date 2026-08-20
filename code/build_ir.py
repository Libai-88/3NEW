# -*- coding: utf-8 -*-
"""Build IR blend features: weighted blend absorbance spectrum per formulation.
Maps confidently-identified raw-material spectra to formulation components.
Saves blend_feats.npz (X_ir, col_names) and reports coverage.
"""
import pandas as pd, numpy as np, glob, os

IRDIR='/data/user/work/ir'
# component column in excel -> (spectrum file stem, order)
MAP = {
 'IR190': ('IR190', 0), 'RF401':('RF401',1), 'RF160':('RF160',2),
 'IR809': ('IR809', 3), 'RF516':('RF516',4), 'RF950':('RF950',5),
 'RF956': ('RF956', 6), 'RH601':('RH601',7), '55754':('55754',8),
 'AZ088': ('AZ088', 9),
}

def load_spectrum(fname):
    d=np.loadtxt(fname, delimiter=',')
    wn=d[:,0]; val=d[:,1]
    # transmittance(%) -> absorbance
    val=np.clip(val, 1e-6, None)
    A=-np.log10(val/100.0)
    return wn, A

# load all spectra on a common grid
grid=None; spec={}
csvs=[f for f in glob.glob(os.path.join(IRDIR,'*.CSV'))]
# prefer nested ones? use base dir files only (all 108344 = same grid)
for f in csvs:
    stem=os.path.basename(f)[:-4]
    wn,A=load_spectrum(f)
    if grid is None: grid=wn
    if not np.allclose(grid,wn): print('GRID MISMATCH',stem); continue
    spec[stem]=A
print('available spectra:', sorted(spec.keys()), 'grid len', len(grid))

# save spectrum refs for PCA basis
# Build per-component blend for every formulation
f86='../data/uploads/acc88872-1e81-437a-b4cf-bc6fdf92809c_8.6配料测试汇总.xlsx'
f726='../data/uploads/40438680-5bc2-4054-b4c1-81a2b7a0f6f6_7.26配料测试汇总(2).xlsx'
colmap={
 'IR190':'IR190(9型环氧树脂36%固含）','RF401':'RF401(PR401)','RF160':'RF160(PR33160G)',
 'IR809':'IR809 55%(PR309 稀释55%)','RF516':'RF516（PR516）','RF950':'RF950（PR8219-50）',
 'RF956':'RF956（PR8219-65）','RH601':'RH601（SM601RX75)','55754':'住友55754G','AZ088':'AZ088（BYK088)'}

frames=[]
for fn,sheet,bt in [(f726,'Sheet1','7.26'),(f86,'8.6配料测试汇总','8.6')]:
    df=pd.read_excel(fn,sheet_name=sheet)
    df=df.iloc[1:].reset_index(drop=True)   # same filter as build_dataset
    df['batch']=bt; frames.append(df)
D=pd.concat(frames,ignore_index=True)

# build blend absorbances (amount-weighted, only mapped comps)
n=len(D); K=len(grid)
blend=np.zeros((n,K))
cover=np.zeros(n)
for comp,(stem,od) in MAP.items():
    if stem not in spec: print('no spectrum',stem); continue
    amt=pd.to_numeric(D[colmap[comp]],errors='coerce').fillna(0).values
    blend+=amt[:,None]*spec[stem][None,:]
    cover+= (amt>0).astype(float)
print('rows with 0 mapped components used:', (cover==0).sum())
# standardize (each row unit norm is impossible w/ IR190 dominates; use zscore per wavelength across samples)
# Instead: center per wavelength, then SVD (PCA)
blend_c=blend-blend.mean(axis=0,keepdims=True)
U,S,Vt=np.linalg.svd(blend_c, full_matrices=False)
expl=S**2/np.sum(S**2)
cum=np.cumsum(expl)
npc=int(np.argmax(cum>=0.99)+1)
print('PCA: 99% variance at',npc,'components. top5 expl:',np.round(expl[:6],4))
# fraction of rows having each mapped comp spectrum present
print('col coverage (spectrum present for comp):', sorted(spec.keys()))

np.savez('../data/blend_feats.npz',
         X_ir=U[:,:npc],           # (n, npc) scores
         expl=expl[:npc],
         grid=grid, blend=blend)
print('saved blend_feats.npz shape', U[:,:npc].shape)