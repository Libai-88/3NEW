# -*- coding: utf-8 -*-
"""Champion v7 (new current best): extra combined-features + strongest arch
(T=gate, M=ridge-stack, W=lgb) on full clean same-process pool. Deployable.
Reports the reliable multi-seed ceiling that the honest experiments establish."""
import numpy as np, warnings, pickle, time; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, accuracy_score
import xgboost as xgb
import lightgbm as lgb
SEED=0; t0=time.time()
m=np.load('../data/master3.npz',allow_pickle=True)
bo=m['batch_o']; o726=bo=='7.26'
Xn=m['Xn_b']; fam_n=m['fam_n']
Xo=m['Xo_b'][o726]; yo_T=m['yT_o'][o726]; yo_M=m['yM_o'][o726]; yo_W=m['wB_o'][o726]; fam_o=m['fam_o'][o726]
Xo=np.vstack([Xo,Xn]); yT=np.concatenate([yo_T,m['yT_n']]); yM=np.concatenate([yo_M,m['yM_n']])
wB=np.concatenate([yo_W,m['wB_n']]); fam=np.concatenate([fam_o,m['fam_n']])
keep=[j for j in range(Xo.shape[1]) if np.std(Xo[:,j])>1e-9]
span0=Xo.max(0)-Xo.min(0); extra=[]
for j in keep:
    for k in keep:
        if j>=k: continue
        r=Xo[:,j]*Xo[:,k]/max(span0[j]*span0[k],1e-9)
        if np.std(r)>0.01: extra.append(r)
Xb=Xo[:,keep]; Xe=np.hstack([Xb,np.array(extra).T])
N=len(Xb); iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
BASE=['et','rf','xgb','lgb']
def bk(kind,s=SEED):
    if kind=='et': return ExtraTreesRegressor(500,random_state=s,n_jobs=-1,min_samples_leaf=2,max_features=0.6)
    if kind=='rf': return RandomForestRegressor(500,random_state=s,n_jobs=-1,min_samples_leaf=2,max_features=0.6)
    if kind=='xgb': return xgb.XGBRegressor(n_estimators=500,random_state=s,learning_rate=0.05,max_depth=3,n_jobs=-1,subsample=0.8,colsample_bytree=0.8)
    return lgb.LGBMRegressor(n_estimators=500,random_state=s,learning_rate=0.05,num_leaves=15,max_depth=3,verbose=-1,n_jobs=-1)

# fit full-data gated model for T
tr=np.array([i for i in range(N) if iT[i]]); Xtr,ytr=Xe[tr],yTf[tr]
oof=np.zeros((len(tr),len(BASE)))
gid=KFold(5,shuffle=True,random_state=SEED+1)
for a,b in gid.split(Xtr):
    for kd,kind in enumerate(BASE): oof[b,kd]=bk(kind).fit(Xtr[a],ytr[a]).predict(Xtr[b])
err=np.sqrt(((oof-ytr[:,None])**2).mean(0)); w=np.clip(1/(err+1e-6),0,10); w/=w.sum()
tmods=[bk(k).fit(Xtr,ytr) for k in BASE]
# full-data stacked model for M
trm=np.array([i for i in range(N) if iM[i]]); XM,yMv=Xe[trm],yM[trm]
oofM=np.zeros((len(trm),len(BASE)))
gid2=KFold(5,shuffle=True,random_state=SEED+1)
for a,b in gid2.split(XM):
    for kd,kind in enumerate(BASE): oofM[b,kd]=bk(kind).fit(XM[a],yMv[a]).predict(XM[b])
metaM=Ridge(alpha=2.0).fit(oofM,yMv); mmods=[bk(k).fit(XM,yMv) for k in BASE]
# full-data lgb classifier for W
trw=np.array([i for i in range(N) if iW[i]])
wclf=lgb.LGBMClassifier(n_estimators=500,random_state=SEED,learning_rate=0.05,num_leaves=15,max_depth=3,verbose=-1,n_jobs=-1).fit(Xe[trw],(wB[trw].astype(int)-1))

# reliable ceiling (from arch_extra_fast 3-seed): T gate 0.417, M gate 0.366, W lgb 0.429
print(f'champion v7 built in {time.time()-t0:.0f}s  (extra feat {Xe.shape[1]})')
print('Reliable multi-seed ceiling (from honest 3-seed GroupKFold same-fold):')
print('  T弯 gate=0.417  M gate=0.366  W lgb acc=0.429')
with open('../models/champion_models_v7.pkl','wb') as f:
    pickle.dump({'T':{'w':w,'models':tmods,'type':'gate'},'M':{'models':mmods,'meta':metaM,'type':'stack'},
                 'W':{'model':wclf,'type':'lgb'},'keep0':keep,'span0':span0,'extra_idx':np.arange(len(keep),Xe.shape[1])},f)
print('Saved ../models/champion_models_v7.pkl')
# smoke test predict
x=Xe[0]
PT=np.column_stack([mk.predict(x.reshape(1,-1)) for mk in tmods]); print('T pred',round(float((PT*w[None,:]).sum(1)[0]),2))
PM=np.column_stack([mk.predict(x.reshape(1,-1)) for mk in mmods]); print('M pred',round(float(metaM.predict(PM)[0]),2))
print('W pred',int(wclf.predict(x.reshape(1,-1))[0]+1))