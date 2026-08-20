# -*- coding: utf-8 -*-
"""Measurement-noise floor diagnosis: near-duplicate recipes on the clean same-
process pool. If identical/near-identical recipes have wildly different labels,
that sets an irremovable R2 ceiling UNLESS labels are measurement replicates
(the training target is real-valued noisy replicate -> floor explains gap).
Reports nearest-neighbor label differences for each task."""
import numpy as np, warnings; warnings.filterwarnings('ignore')
m=np.load('../data/master3.npz',allow_pickle=True)
bo=m['batch_o']; o726=bo=='7.26'
Xn=m['Xn_b']; fam_n=m['fam_n']
Xo=m['Xo_b'][o726]; yo_T=m['yT_o'][o726]; yo_M=m['yM_o'][o726]; yo_W=m['wB_o'][o726]; fam_o=m['fam_o'][o726]
X=np.vstack([Xo,Xn]); yT=np.concatenate([yo_T,m['yT_n']]); yM=np.concatenate([yo_M,m['yM_n']])
wB=np.concatenate([yo_W,m['wB_n']]); fam=np.concatenate([fam_o,m['fam_n']])
iT=np.isfinite(yT)&(yT<50)
N=len(X)
# normalize features to unit scale by max range for recipe-distance
rn=np.ptp(X,0); rn[rn==0]=1; Xn_=X/rn
# brute-force nearest neighbor same-family vs cross-family label diffs
from scipy.spatial.distance import cdist
print('== near-duplicate recipe label consistency (clean same-process pool) ==')
# pick sample pairs within small recipe distance
for task,lab,valid in [('T',yT,iT),('M',yM,np.isfinite(yM)),('W',wB,np.isfinite(wB))]:
    idx=np.where(valid)[0]
    if len(idx)<30:
        print(f'{task}: too few'); continue
    Xs=Xn_[idx]; ys=lab[idx]
    # sample a subsam to keep cdist tractable
    rs=np.random.RandomState(0); sub=rs.choice(len(idx),min(len(idx),60),replace=False)
    subidx=idx[sub]; D=cdist(Xs[sub],Xs)
    np.fill_diagonal(D,np.inf)
    ys_local=ys[sub]  # aligned with D rows
    within=[]; cross=[]
    for a,i0 in enumerate(subidx):
        js=np.argsort(D[a])[:8]
        for jrec in js:
            if abs(ys_local[a]-ys[jrec])<1e-9: continue
            d=D[a,jrec]
            same= fam[i0]==fam[idx[jrec]]
            (within if same else cross).append((d, ys_local[a]-ys[jrec]))
    within.sort(key=lambda t:t[0]); cross.sort(key=lambda t:t[0])
    # average |label diff| among closest 5 same-family pairs
    def avgd(l): return np.mean([abs(v) for _,v in l[:5]]) if l else float('nan')
    w5=avgd(within); c5=avgd(cross)
    # overall: |label diff| between recipes within same family
    print(f'  {task}: nvalid={len(idx)} closest5 same-fam |label diff|={w5:.2f} cross-fam={c5:.2f}')
    if task=='T':
        # T measured in mm; typical spread
        print(f'    T global std(mask-clip)= {np.std(yT[iT]):.2f} mm, close-replicate diff ~> noise floor')
yMv=yM[np.isfinite(yM)]
print('\nMEK model std of target:',float(np.std(yMv)),' (R2 upper bound if noise floor ~ close-diff)')
print('T model std:',float(np.std(yT[iT])))