# -*- coding: utf-8 -*-
"""Diagnose WHY cross-batch R2 is so negative. Possibilities:
 (A) new100 recipes sit far outside 7.26 feature region (novel formulations) -> extrapolation, not noise
 (B) label scale/distribution shifts between batches (measurement recalibration)
 (C) features overlap but relationship truly absent -> no transferable skill
Checks: feature-space nearest-neighbor distance, label distribution overlap."""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.preprocessing import StandardScaler
m=np.load('../data/master3.npz',allow_pickle=True)
o726=np.where(m['batch_o']=='7.26')[0]
Xo=m['Xo_b'][o726]; yo_T=m['yT_o'][o726]; yo_M=m['yM_o'][o726]; yo_W=m['wB_o'][o726]
Xn=m['Xn_b']; yn_T=m['yT_n']; yn_M=m['yM_n']; yn_W=m['wB_n']
keep=[j for j in range(Xo.shape[1]) if np.std(Xo[:,j])>1e-9]
X_tr=Xo[:,keep]; X_te=Xn[:,keep]
sc=StandardScaler().fit(np.vstack([X_tr,X_te])); Ztr=sc.transform(X_tr); Zte=sc.transform(X_te)
# nearest neighbor distance (train->each test), in std units
from scipy.spatial import cKDTree
t=cKDTree(Ztr)
d,idx=t.query(Zte,k=1)
d999=np.percentile(d,99); seg='EXTRA/interpolation region'; ov=(d<1.5).mean()
print(f'train rows={len(Ztr)} test rows={len(Zte)}  n_feat={Ztr.shape[1]}')
print(f'NN dist: med={np.median(d):.2f} p90={np.percentile(d,90):.2f} p99={d999:.2f} std units')
print(f'fraction of test within 1.5 std of a train recipe = {ov:.3f}  ({(ov<0.5 and "MANY ARE NOVEL FORMULAS" if ov<0.5 else "strong recipe overlap")})')
# label distribution overlap
for lab_t,lab_n,name in [(yo_T,yn_T,'T'),(yo_M,yn_M,'M'),(yo_W,yn_W,'W')]:
    a=lab_t[np.isfinite(lab_t)&(lab_t<50)] if name=='T' else lab_t[np.isfinite(lab_t)]
    b=lab_n[np.isfinite(lab_n)&(lab_n<50)] if name=='T' else lab_n[np.isfinite(lab_n)]
    print(f'{name}: 7.26 mean={a.mean():.2f} std={a.std():.2f} n={len(a)} | new100 mean={b.mean():.2f} std={b.std():.2f} n={len(b)} | delta={b.mean()-a.mean():+.2f}')
# within the 1.5-std-overlap test rows only, does label correlate w/ nearest label?
tlabs={'T':yo_T,'M':yo_M}; nlabels={'T':yn_T,'M':yn_M}
for name in ['T','M']:
    tl=tlabs[name]; nl=nlabels[name]
    dT=np.abs(yo_T[idx]-yn_T)  # |train-neighbor T - test T|
    mask=np.isfinite(dT)&(dT<50)&np.isfinite(yn_T)&(yn_T<50)&(d<1.5)
    ey=yo_T[idx][mask]
    tgt=yn_T[mask]
    if name=='M':
        mask=np.isfinite(yo_M[idx])&np.isfinite(yn_M)&(d<1.5); ey=yo_M[idx][mask]; tgt=yn_M[mask]
    if len(tgt)>10:
        # correlation & R2 of "predict=neighbor-label"
        r=np.corrcoef(ey,tgt)[0,1]
        r2=1-np.sum((ey-tgt)**2)/np.sum((tgt-tgt.mean())**2)
        print(f'{name} [overlap test rows only]: corr(neighbor-label,test-label)={r:.3f} R2(predict=neighbor)={r2:.3f} n={len(tgt)}')