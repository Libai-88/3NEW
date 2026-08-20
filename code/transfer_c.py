# -*- coding: utf-8 -*-
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, mean_absolute_error
SEED=0
m=np.load('master3.npz',allow_pickle=True)
Xo,Xn=m['Xo'],m['Xn'];X=np.vstack([Xo,Xn])
yT=np.concatenate([m['yT_o'],m['yT_n']]);yM=np.concatenate([m['yM_o'],m['yM_n']])
bak=np.concatenate([np.zeros(len(Xo)),np.ones(len(Xn))])
keep=[j for j in range(X.shape[1]) if np.std(X[:,j])>1e-9];X=X[:,keep]
iT=np.isfinite(yT)&(yT<50);iM=np.isfinite(yM)
famall=np.concatenate([m['fam_o'],m['fam_n']])
def models():
    return [('ET',lambda:ExtraTreesRegressor(n_estimators=400,random_state=SEED,min_samples_leaf=2)),
            ('RF',lambda:RandomForestRegressor(n_estimators=400,random_state=SEED,min_samples_leaf=2)),
            ('GBR',lambda:GradientBoostingRegressor(n_estimators=300,random_state=SEED,max_depth=3,learning_rate=0.04)),
            ('SVR',lambda:Pipeline([('s',StandardScaler()),('m',SVR(C=12,gamma='scale',max_iter=8000))]))]
print('=== B) Leave-new-regime-out (train orig 371, test new 100) TRUE transfer ===')
def guarded(f,trs,te,mtg):
    mk,tg=mtg
    trs2=trs[np.isin(trs,np.where(mk)[0])]; te2=te[np.isin(te,np.where(mk)[0])]
    if len(te2)<5 or len(trs2)<10: return None
    mod=f();mod.fit(X[trs2],tg[trs2]);p=mod.predict(X[te2])
    return (r2_score(tg[te2],p),mean_absolute_error(tg[te2],p))
for lbl,(mk,tg) in [('MEK',(iM,yM)),('T弯',(iT,yT))]:
    tr=np.where((bak==0)&mk)[0]; te=np.where((bak==1)&mk)[0]
    if len(te)<5: continue
    for nm,f in models():
        mod=f();mod.fit(X[tr],tg[tr]);p=mod.predict(X[te])
        print(f'  {lbl} {nm:5s} O->new R2={r2_score(tg[te],p):+.3f} MAE={mean_absolute_error(tg[te],p):.2f}')
print('\n=== C) GroupKFold-by-family across O+N ===')
gkal=GroupKFold(n_splits=5)
for lbl,(mk,tg) in [('MEK',(iM,yM)),('T弯',(iT,yT))]:
    for nm,f in models():
        r=[];ma=[]
        for tr,te in gkal.split(X,None,famall):
            res=guarded(f,tr,te,(mk,tg))
            if res: r.append(res[0]);ma.append(res[1])
        if r: print(f'  {lbl} {nm:5s} groupCV R2={np.mean(r):+.3f}(sd{np.std(r):.2f}) MAE={np.mean(ma):.2f}')