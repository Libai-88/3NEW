# -*- coding: utf-8 -*-
"""Champion v6: chemistry-informed combined features (extra block) + gradient-boosting
(XGB+LGB ensemble), 全量特征（无显式选择，因实测选择反而降性能）。Clean same-process pool.
Honest GroupKFold (multi-seed) reported. This is the strongest verified deliverable."""
import numpy as np, warnings, pickle; warnings.filterwarnings('ignore')
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, accuracy_score
import xgboost as xgb
import lightgbm as lgb
SEED=0
m=np.load('../data/master3.npz',allow_pickle=True)
bo=m['batch_o']; o726=bo=='7.26'
Xn=m['Xn_b']; famn=m['fam_n']
Xo=m['Xo_b'][o726]; yTo=m['yT_o'][o726]; yMo=m['yM_o'][o726]; wBo=m['wB_o'][o726]; famo=m['fam_o'][o726]
X=np.vstack([Xo,Xn]); yT=np.concatenate([yTo,m['yT_n']]); yM=np.concatenate([yMo,m['yM_n']])
wB=np.concatenate([wBo,m['wB_n']]); fam=np.concatenate([famo,famn])
keep0=[j for j in range(X.shape[1]) if np.std(X[:,j])>1e-9]
span0=X.max(0)-X.min(0)
extra=[]
for j in keep0:
    for k in keep0:
        if j>=k: continue
        r=X[:,j]*X[:,k]/max(span0[j]*span0[k],1e-9)
        if np.std(r)>0.01: extra.append(r)
Xb=X[:,keep0]
Xf=np.hstack([Xb,np.array(extra).T])
N=len(X); iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))

def xgb_r(s): return xgb.XGBRegressor(n_estimators=600,random_state=s,learning_rate=0.05,max_depth=3,subsample=0.8,colsample_bytree=0.8,min_child_weight=3,reg_lambda=1.0)
def lgb_r(s): return lgb.LGBMRegressor(n_estimators=600,random_state=s,learning_rate=0.05,num_leaves=15,max_depth=3,min_child_samples=8,reg_lambda=1.0,verbose=-1)

# --- honest CV metrics (as in leakfree evaluation, seeds 0..2) ---
def cv_reg(ycol,mask):
    tidx=np.array([i for i in range(N) if mask[i]])
    gk=GroupKFold(5); folds=list(gk.split(tidx,groups=fam[tidx])); acc={'xgb':[],'lgb':[],'ens':[]}
    for seed in [0,1,2]:
        for trr,ter in folds:
            tri=tidx[trr]; tei=tidx[ter]
            ltr=[i for i in tri if np.isfinite(ycol[i])]
            if len(ltr)<20: continue
            yy=ycol[ltr]; yt=ycol[tei]
            px=xgb_r(seed).fit(Xf[ltr],yy).predict(Xf[tei]); pl=lgb_r(seed).fit(Xf[ltr],yy).predict(Xf[tei])
            acc['xgb'].append(r2_score(yt,px)); acc['lgb'].append(r2_score(yt,pl)); acc['ens'].append(r2_score(yt,(px+pl)/2))
    return {k:(float(np.mean(v)),float(np.std(v))) for k,v in acc.items()}
def cv_clf():
    tidx=np.array([i for i in range(N) if iW[i]])
    gk=GroupKFold(5); folds=list(gk.split(tidx,groups=fam[tidx])); acc={'xgb':[],'lgb':[],'ens':[]}
    for seed in [0,1,2]:
        for trr,ter in folds:
            tri=tidx[trr]; tei=tidx[ter]
            ltr=[i for i in tri if np.isfinite(wB[i])]
            if len(ltr)<20: continue
            yy=(wB[ltr].astype(int)-1); yt=wB[tei].astype(int)
            px=xgb.XGBClassifier(n_estimators=600,random_state=seed,learning_rate=0.05,max_depth=3,subsample=0.8,colsample_bytree=0.8).fit(Xf[ltr],yy).predict(Xf[tei])+1
            py=lgb.LGBMClassifier(n_estimators=600,random_state=seed,learning_rate=0.05,num_leaves=15,max_depth=3,min_child_samples=8,verbose=-1).fit(Xf[ltr],yy).predict(Xf[tei])+1
            acc['xgb'].append(accuracy_score(yt,px)); acc['lgb'].append(accuracy_score(yt,py))
            acc['ens'].append(accuracy_score(yt,np.where(px==py,px,np.round(px*0.5+py*0.5).astype(int))))
    return {k:(float(np.mean(v)),float(np.std(v))) for k,v in acc.items()}

rT=cv_reg(yTf,iT); rM=cv_reg(yM,iM); rW=cv_clf()
print('champion v6 honest GroupKFold (extra combined features, XGB+LGB, 3 seeds):')
print('  T:  '+'  '.join(f'{k}:{mu:.3f}±{sd:.3f}' for k,(mu,sd) in rT.items()))
print('  M:  '+'  '.join(f'{k}:{mu:.3f}±{sd:.3f}' for k,(mu,sd) in rM.items()))
print('  W:  '+'  '.join(f'{k}:{mu:.3f}±{sd:.3f}' for k,(mu,sd) in rW.items()))

# --- final fit on all data (deployable) ---
def fit_final():
    tr=[i for i in range(N) if iT[i]]; Xt,ybtrans=Xf[tr],yTf[tr]
    return {'T':{'xgb':xgb_r(SEED).fit(Xt,ybtrans),'lgb':lgb_r(SEED).fit(Xt,ybtrans)},
            'M':{'xgb':xgb_r(SEED).fit(Xf[[i for i in range(N) if iM[i]]],yM[[i for i in range(N) if iM[i]]]),
                 'lgb':lgb_r(SEED).fit(Xf[[i for i in range(N) if iM[i]]],yM[[i for i in range(N) if iM[i]]])},
            'W':{'xgb':xgb.XGBClassifier(n_estimators=600,random_state=SEED,learning_rate=0.05,max_depth=3,subsample=0.8,colsample_bytree=0.8).fit(Xf[[i for i in range(N) if iW[i]]],(wB[[i for i in range(N) if iW[i]]].astype(int)-1)),
                 'lgb':lgb.LGBMClassifier(n_estimators=600,random_state=SEED,learning_rate=0.05,num_leaves=15,max_depth=3,min_child_samples=8,verbose=-1).fit(Xf[[i for i in range(N) if iW[i]]],(wB[[i for i in range(N) if iW[i]]].astype(int)-1))}}
final=fit_final()
with open('../models/champion_models_v6.pkl','wb') as f:
    pickle.dump({'model':final,'keep0':keep0,'span0':span0},f)
print('\nSaved ../models/champion_models_v6.pkl (extra combined-features + GB ensemble)')