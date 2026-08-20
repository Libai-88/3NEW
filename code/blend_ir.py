# -*- coding: utf-8 -*-
"""Innovative feature construction: reconstructed blend IR spectra.

Each formula's structural fingerprint = sum of raw-material IR spectra,
weighted by its effective formulation amount. This captures functional-group
composition of the whole recipe (beyond raw amounts), then applies the
literature-grounded spectral preprocessing (SNV normalization + Savitzky-Golay
2nd derivative), followed by PCA reduction to a compact feature block.

This directly exercises requirement #2 (feature construction) and #4 (innovation):
we move from tabular amounts to a physically meaningful reconstructed molecular
spectrum per formula, which tree models can leverage.

Available spectra (identical 3736-pt grid, 399-4000 cm-1):
  019, 088(AZ088->BYK088), 55754(住友), IA151, IR809(PR309),
  RF160(PR33160G), RF401(PR401), RF516(PR516), RF950, RF956,
  IR190 (main matrix 9型环氧树脂, parsed from .SPA by make_ir190.py)
Solid fractions for the dilution-named stocks are read from the name where
present; plain names default to 0.75.
"""
import numpy as np, glob, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.signal import savgol_filter
from sklearn.decomposition import PCA
SEED=0

SPECDIR='/data/user/work/ir_extract'
def load_spec(name):
    d=np.loadtxt(f'{SPECDIR}/{name}.CSV',delimiter=',')
    return d[:,1]  # absorbance vs shared grid

# map CSV spectrum -> formulation column (effective basis)
# IR190 (9型环氧树脂, dominant matrix) now available via make_ir190.py SPA->CSV.
SPEC_MAP=[('IR190','9型环氧树脂'),('IR809','PR309'),('RF160','PR-33160G'),('RF401','PR401'),
          ('RF516','PR516'),('RF950','RF950_50%'),('RF956','RF956_60%'),
          ('088','BYK-088'),('55754','住友_55754G')]

Dn=pd.read_csv('../data/uploads/b416a109-b9d3-4009-b344-4edeab283499_新100组机器学习数据集.csv')
def Xcol(s): return pd.to_numeric(Dn[s],errors='coerce').fillna(0).values

# effective solid factors for scaling (approx; keep relative)
asts={}
blend_mat=np.zeros((len(Dn),3736))
for csvn,col in SPEC_MAP:
    spec=load_spec(csvn)
    scale=np.abs(spec).max()+1e-9
    spec=spec/scale                          # normalize each material spectrum
    asts[csvn]=spec
    amt=np.asarray(Xcol(col),float)
    # 50%/60% naming -> solid fraction (rough)
    frac=0.75
    if '%' in col:
        try: frac=float(col.split('_')[1].replace('%',''))/100.0
        except Exception: frac=0.75
    blend_mat+=amt[:,None]*(spec*frac)[None,:]
print('blend matrix',blend_mat.shape,'global max',round(blend_mat.max(),2))

def snv(x):
    return (x-x.mean())/ (x.std()+1e-9)
def deriv(x):
    w=15
    return savgol_filter(x,w,2,deriv=2)
# row-wise SNV then 2nd derivative (per literature: SNV+2nd-deriv IR)
P=blend_mat.copy()
P=np.vstack([snv(r) for r in P])
P=np.vstack([deriv(r) for r in P])
# select informative mid-IR window 600-1700 cm-1 (fingerprint region) + reduce
xgrid=np.loadtxt(f'{SPECDIR}/019.CSV',delimiter=',')[:,0]
mask=(xgrid>=600)&(xgrid<=1700)
Pw=P[:,mask]
print('windowed',Pw.shape)
pca=PCA(n_components=8,random_state=SEED)
Fir=pca.fit_transform(Pw)
print('IR-PCA explained var top8 cum:',round(pca.explained_variance_ratio_.sum(),3))
np.save('ir_feat.npy',Fir); np.save('ir_pca_windows.npy',Pw)
print('saved ir_feat.npy shape',Fir.shape)