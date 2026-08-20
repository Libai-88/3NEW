# -*- coding: utf-8 -*-
"""DEFINITIVE same-process champion: train on 7.26(200/10) + new100(200/10) ONLY,
honest GroupKFold by family. This is the model that actually serves the user's
stated scenario (predict new-batch recipes at 200°C/10min). Uses best techniques:
stacking for MEK, gated-mix for T弯, RF for water. Compares against full-data version."""
import numpy as np, warnings, pickle; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor, RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, KFold
from sklearn.metrics import r2_score, mean_absolute_error, accuracy_score
SEED=0
m=np.load('../data/master3.npz',allow_pickle=True)
bo=m['batch_o']; o726=bo=='7.26'; o86=bo=='8.6'
Xn=m['Xn_b']; fam_n=m['fam_n']
# same-process pool = 7.26 + new
Xo=m['Xo_b'][o726]; yo_T=m['yT_o'][o726]; yo_M=m['yM_o'][o726]; yo_W=m['wB_o'][o726]
fam_o=m['fam_o'][o726]
Xo=np.vstack([Xo,Xn]); yT=np.concatenate([yo_T,m['yT_n']]); yM=np.concatenate([yo_M,m['yM_n']])
wB=np.concatenate([yo_W,m['wB_n']]); fam=np.concatenate([fam_o,fam_n])
keep=[j for j in range(Xo.shape[1]) if np.std(Xo[:,j])>1e-9]; X=Xo[:,keep]
N=len(X); iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95)); yMl=yM; yW=yW if False else yM
gk=GroupKFold(5); folds=list(gk.split(X,groups=fam))
print('Same-process pool rows',N,'folds',len(folds))
print('  T rows',iT.sum(),'M rows',iM.sum(),'W rows',iW.sum())

def base(kind,seed=SEED):
    if kind=='et':   return ExtraTreesRegressor(900,random_state=seed,min_samples_leaf=2,max_features=0.6)
    if kind=='rf':   return RandomForestRegressor(900,random_state=seed,min_samples_leaf=2,max_features=0.6)
    if kind=='gbr':  return GradientBoostingRegressor(n_estimators=500,random_state=seed,max_depth=2,learning_rate=0.04)
    if kind=='svr':  return Pipeline([('s',StandardScaler()),('m',SVR(C=25,gamma='scale',epsilon=0.25))])
    if kind=='ridge':return Pipeline([('s',StandardScaler()),('m',Ridge(alpha=6))])
BASE=['et','rf','gbr','svr','ridge']
def mkfold(mask):
    out=[]
    for tr,te in folds:
        trm=tr[np.isin(tr,np.where(mask)[0])]; tem=te[np.isin(te,np.where(mask)[0])]
        if len(trm)>=20 and len(tem)>=3: out.append((trm,tem))
    return out

# ---- MEK stacking (honest) ----
def mek_stack():
    oof=np.full(N,np.nan)
    for tr,te in mkfold(iM):
        Xtr,ytr=X[tr],yMl[tr]
        P=np.column_stack([base(k).fit(Xtr,ytr).predict(X[te]) for k in BASE])
        # meta OOF on train
        ooftr=np.zeros((len(tr),len(BASE)))
        ikf=KFold(5,shuffle=True,random_state=1)
        for a,b in ikf.split(Xtr):
            for k,kind in enumerate(BASE):
                ooftr[b,k]=base(kind).fit(Xtr[a],ytr[a]).predict(Xtr[b])
        meta=Ridge(alpha=2.0).fit(ooftr,ytr)
        oof[te]=meta.predict(P)
    ms=np.isfinite(yMl)&np.isfinite(oof); return r2_score(yMl[ms],oof[ms]),mean_absolute_error(yMl[ms],oof[ms])
# ---- T弯 gated ----
def tbend_gated():
    oof=np.full(N,np.nan)
    for tr,te in mkfold(iT):
        Xtr,ytr=X[tr],yTf[tr]
        ooftr=np.zeros((len(tr),len(BASE)))
        ikf=KFold(5,shuffle=True,random_state=2)
        for a,b in ikf.split(Xtr):
            for k,kind in enumerate(BASE):
                ooftr[b,k]=base(kind).fit(Xtr[a],ytr[a]).predict(Xtr[b])
        err=np.sqrt(((ooftr-ytr[:,None])**2).mean(0)); w=np.clip(1/(err+1e-6),0,10); w/=w.sum()
        P=np.column_stack([base(k).fit(Xtr,ytr).predict(X[te]) for k in BASE])
        oof[te]=(P*w[None,:]).sum(1)
    ms=np.isfinite(yTf)&np.isfinite(oof); return r2_score(yTf[ms],oof[ms]),mean_absolute_error(yTf[ms],oof[ms])
# ---- water RF ----
def water_rf():
    oof=np.full(N,np.nan); 
    for tr,te in mkfold(iW):
        c=RandomForestClassifier(900,random_state=SEED,min_samples_leaf=2,class_weight='balanced_subsample').fit(X[tr],wB[tr].astype(int))
        oof[te]=c.predict(X[te])
    ms=np.isfinite(wB)&np.isfinite(oof)
    return accuracy_score(wB[ms].astype(int),oof[ms]), np.mean(np.abs(wB[ms].astype(int)-oof[ms])<=1)

rm,maf=mek_stack(); print(f'\nMEK (same-process, stacking): R2={rm:.3f} MAE={maf:.3f}')
rt,mab=tbend_gated(); print(f'T弯 (same-process, gated):    R2={rt:.3f} MAE={mab:.3f}')
aw,a1=water_rf(); print(f'水煮 (same-process, RF):       acc={aw:.3f} 1off={a1:.3f}')