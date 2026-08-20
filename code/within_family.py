# -*- coding: utf-8 -*-
"""Decoupling bottleneck: within-family interpolation R2 vs cross-family R2.
If within-family (interpolating a family's own gradient scan) is HIGH, the model
has capacity and the gap is pure extrapolation/coverage. If within-family is also
LOW, signal is intrinsically weak. Honest: within-family uses train on other folds
of SAME family members is that sample overlap; instead we measure pure in-family
fit via a K-fold on rows within each large family (R01..R06). This tells us the
attainable ceiling given data spread is NOT sampling-limited."""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
m=np.load('../data/master3.npz',allow_pickle=True)
o726=m['batch_o']=='7.26'
Xn=m['Xn_b']; fam_n=m['fam_n']
Xo=m['Xo_b'][o726]; yTo=m['yT_o'][o726]; yMo=m['yM_o'][o726]; famo=m['fam_o'][o726]
X=np.vstack([Xo,Xn]); yT=np.concatenate([yTo,m['yT_n']]); yM=np.concatenate([yMo,m['yM_n']]); fam=np.concatenate([famo,fam_n])
keep=[j for j in range(X.shape[1]) if np.std(X[:,j])>1e-9]; X=X[:,keep]
iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
def within(task,lab,val):
    idx=np.where(val)[0]
    fams_i={}; 
    for i in idx: fams_i.setdefault(fam[i],[]).append(i)
    big=[v for v in fams_i.values() if len(v)>=8]
    r2s=[]
    for v in big:
        if len(v)<8: continue
        gk=KFold(4,shuffle=True,random_state=0)
        for tr,te in gk.split(v):
            trr=[v[a] for a in tr]; tee=[v[a] for a in te]
            et=ExtraTreesRegressor(700,random_state=0,min_samples_leaf=2).fit(X[trr],lab[trr])
            vt=np.isfinite(lab[tee])
            if vt.sum()>=2: r2s.append(r2_score(lab[tee][vt],et.predict(X[tee][vt])))
    r2s=[x for x in r2s if np.isfinite(x)]
    print(f'  {task}: WITHIN-family interpolation R2 = {np.mean(r2s):.3f}±{np.std(r2s):.3f} (n={len(r2s)}), vs cross-family ~0.37-0.42')
    return np.mean(r2s)
print('== within-family (gradient-scan interpolation) vs cross-family ==')
within('T',yTf,iT)
within('M',yM,iM)
print('\nInterpret: if within>>cross => capacity exists, gap is extrapolation/coverage.')