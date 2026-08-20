# -*- coding: utf-8 -*-
"""LOO (leave-one-OUT cross-validation) on the SAME-PROCESS pool (7.26+new100, 200/10).
Two honest variants, compared against the reported GroupKFold champion:
 (A) Leave-one-RECORD-out (plain sample LOO): leaks within-family near-duplicates -> expected UPPER bound, reveals if 'correlated-with-labels' is only carried by family repeats.
 (B) Leave-one-FAMILY-out: strictly honest (no within-family leak), the record-level limit of what features can explain when the recipe combination is genuinely unseen.
Reports R2 / acc, and labels which variant leaks."""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error, accuracy_score
m=np.load('../data/master3.npz',allow_pickle=True)
bo=m['batch_o']; o726=bo=='7.26'
Xn=m['Xn_b']; fam_n=m['fam_n']
Xo=m['Xo_b'][o726]; yo_T=m['yT_o'][o726]; yo_M=m['yM_o'][o726]; yo_W=m['wB_o'][o726]; fam_o=m['fam_o'][o726]
Xo=np.vstack([Xo,Xn]); yT=np.concatenate([yo_T,m['yT_n']]); yM=np.concatenate([yo_M,m['yM_n']])
wB=np.concatenate([yo_W,m['wB_n']]); fam=np.concatenate([fam_o,fam_n])
keep=[j for j in range(Xo.shape[1]) if np.std(Xo[:,j])>1e-9]; X=Xo[:,keep]
N=len(X); iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
regR=RandomForestRegressor(500,random_state=0,min_samples_leaf=2,n_jobs=-1)
regE=RandomForestRegressor(300,random_state=0,min_samples_leaf=4,n_jobs=-1)  # more stable, anti-overfit
ridge=Pipeline([('s',StandardScaler()),('m',Ridge(alpha=3.0))])

def record_loo(yval,mask):
    idx=np.where(mask)[0]; pred=np.full(len(idx),np.nan)
    for k,i in enumerate(idx):
        tr=np.delete(idx,k)
        mdl=RandomForestRegressor(300,random_state=0,min_samples_leaf=4,n_jobs=-1).fit(X[tr],yval[tr])
        pred[k]=mdl.predict(X[i:i+1])[0]
    ok=np.full(len(yval),False); ok[idx]=True
    return r2_score(yval[idx],pred), mean_absolute_error(yval[idx],pred)

def family_loo(yval,mask):
    idx=np.where(mask)[0]; fam_of=np.array([fam[i] for i in idx])
    pred=np.full(len(idx),np.nan)
    for f in np.unique(fam_of):
        te=idx[fam_of==f]; tr=idx[fam_of!=f]
        mdl=RandomForestRegressor(300,random_state=0,min_samples_leaf=4,n_jobs=-1).fit(X[tr],yval[tr])
        pred[np.isin(idx,te)] = mdl.predict(X[te])
    return r2_score(yval[idx],pred), mean_absolute_error(yval[idx],pred)

def clf_loo(yval,mask):
    idx=np.where(mask)[0]; fam_of=np.array([fam[i] for i in idx])
    yv=(yval-np.floor(np.nanmin(yval))).astype(int)
    # record-level
    pred=np.full(len(idx),np.nan)
    for k,i in enumerate(idx):
        tr=np.delete(idx,k)
        mdl=RandomForestClassifier(300,random_state=0,min_samples_leaf=2,n_jobs=-1).fit(X[tr],yv[tr])
        pred[k]=mdl.predict(X[i:i+1])[0]
    accR=accuracy_score(yv[idx],pred)
    # family-level
    pf=np.full(len(idx),np.nan)
    for f in np.unique(fam_of):
        te=idx[fam_of==f]; tr=idx[fam_of!=f]
        mdl=RandomForestClassifier(300,random_state=0,min_samples_leaf=2,n_jobs=-1).fit(X[tr],yv[tr])
        pf[np.isin(idx,te)]=mdl.predict(X[te])
    accF=accuracy_score(yv[idx],pf)
    return accR,accF

print(f'pool N={N}  T={iT.sum()} M={iM.sum()} W={iW.sum()}  n_feat={X.shape[1]}  families={len(np.unique(fam))}')
print('\n[record LOO = WITH within-family leak -> optimistic UPPER bound]')
for t,ycol in [('T',yTf),('M',yM)]:
    mask=np.isfinite(ycol)&(ycol<50) if t=='T' else np.isfinite(ycol)
    rv,av=record_loo(ycol,mask)
    print(f'  {t} record-LOO R2={rv:.3f} MAE={av:.3f}')
print('\n[family LOO = NO within-family leak -> honest, recipe truly unseen]')
for t,ycol in [('T',yTf),('M',yM)]:
    mask=np.isfinite(ycol)&(ycol<50) if t=='T' else np.isfinite(ycol)
    rv,av=family_loo(ycol,mask)
    print(f'  {t} family-LOO R2={rv:.3f} MAE={av:.3f}')
accR,accF=clf_loo(wB,iW)
print(f'\n  W record-LOO acc={accR:.3f} | family-LOO acc={accF:.3f}   (GroupKFold champion acc=0.434)')
print('\n(refs: GroupKFold champion  MEK R2=0.444 T R2=0.461 W acc=0.434)')