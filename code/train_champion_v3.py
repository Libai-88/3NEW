# -*- coding: utf-8 -*-
"""Champion v3: best-performing architecture per target (honest GroupKFold evidence):
  - MEK  : OOF-stacking (5 base models + Ridge meta) — best R²=0.541
  - T弯  : gating (inverse-error weighted ensemble of 5 bases) — best R²=0.387
  - 水煮 : baseline RF — stacking/voting both degrade
The package exports .predict(X) per target + the base estimators for interpretability.
"""
import numpy as np, warnings, pickle; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor, RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.linear_model import Ridge
SEED=0
m=np.load('../data/master3.npz',allow_pickle=True)
X=np.vstack([m['Xo_b'],m['Xn_b']])
yT=np.concatenate([m['yT_o'],m['yT_n']])
yM=np.concatenate([m['yM_o'],m['yM_n']])
wB=np.concatenate([m['wB_o'],m['wB_n']])
fam=np.concatenate([m['fam_o'],m['fam_n']])
keep=[j for j in range(X.shape[1]) if np.std(X[:,j])>1e-9]; X=X[:,keep]
iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
NT=len(X)

def base(kind):
    if kind=='et':   return ExtraTreesRegressor(600,random_state=SEED,min_samples_leaf=2)
    if kind=='rf':   return RandomForestRegressor(600,random_state=SEED,min_samples_leaf=2)
    if kind=='gbr':  return GradientBoostingRegressor(n_estimators=400,random_state=SEED,max_depth=2,learning_rate=0.04)
    if kind=='svr':  return Pipeline([('s',StandardScaler()),('m',SVR(C=15,gamma='scale',epsilon=0.3))])
    if kind=='ridge':return Pipeline([('s',StandardScaler()),('m',Ridge(alpha=8))])
BASE=['et','rf','gbr','svr','ridge']

# --- fit MEK stacking meta on ALL labeled data using 5-fold OOF ---
from sklearn.model_selection import KFold
def oof_base(mask, yarr):
    oof=np.zeros((mask.sum(),len(BASE)))
    for k,kind in enumerate(BASE):
        ikf=KFold(5,shuffle=True,random_state=k)
        Xm=X[mask]; ym=yarr[mask]
        for tr,te in ikf.split(Xm):
            est=base(kind); est.fit(Xm[tr],ym[tr]); oof[te,k]=est.predict(Xm[te])
    return oof

# MEK stacking: fit meta on full data OOF
Mmask=iM; My=yM[iM]; Mx=X[iM]
M_oof=np.zeros((Mmask.sum(),len(BASE)))
for k,kind in enumerate(BASE):
    ikf=KFold(5,shuffle=True,random_state=k)
    for tr,te in ikf.split(Mx):
        est=base(kind); est.fit(Mx[tr],My[tr]); M_oof[te,k]=est.predict(Mx[te])
meta_mek=Ridge(alpha=2.0).fit(M_oof,My)
# final base models fit on all labeled data
mek_bases={k:base(k).fit(Mx,My) for k in BASE}

def predict_mek(Xp):
    P=np.column_stack([mek_bases[k].predict(Xp) for k in BASE])
    return meta_mek.predict(P)

# --- T弯 gating: train all 5 bases, compute global weights from OOF errors ---
Tmask=iT; Ty=yTf[iT]; Tx=X[iT]
T_oof=np.zeros((Tmask.sum(),len(BASE)))
for k,kind in enumerate(BASE):
    ikf=KFold(5,shuffle=True,random_state=k)
    for tr,te in ikf.split(Tx):
        est=base(kind); est.fit(Tx[tr],Ty[tr]); T_oof[te,k]=est.predict(Tx[te])
err=np.sqrt(((T_oof-Ty[:,None])**2).mean(0))
w=np.clip(1.0/(err+1e-6),0,10); w/=w.sum()
tbend_bases={k:base(k).fit(Tx,Ty) for k in BASE}
def predict_tbend(Xp):
    P=np.column_stack([tbend_bases[k].predict(Xp) for k in BASE])
    return (P*w[None,:]).sum(1)

# --- 水煮 RF baseline (stacking degrades) ---
Wmask=iW; Wy=wB[iW].astype(int); Wx=X[iW]
wb_clf=RandomForestClassifier(700,random_state=SEED,min_samples_leaf=2,class_weight='balanced_subsample').fit(Wx,Wy)
from sklearn.ensemble import ExtraTreesRegressor
wb_reg=ExtraTreesRegressor(700,random_state=SEED,min_samples_leaf=2).fit(Wx,wB[iW])

# --- package ---
import collections
c=collections.Counter(Wy)
model={'T_bases':tbend_bases,'T_weights':w,
       'MEK_bases':mek_bases,'MEK_meta':meta_mek,
       'WB_RF':wb_clf,'WB_reg':wb_reg,
       'feat_keep':keep,
       'meta':{'class_balance':dict(c),
               'MEK_bases':BASE,'T_bases':BASE}}
with open('../models/champion_models_v3.pkl','wb') as f: pickle.dump(model,f)
print('saved champion_models_v3.pkl')

# sanity: in-sample-ish check (not OOF, just to verify pipeline)
print('MEK in-sample R2 approx', round(float(__import__('sklearn.metrics').metrics.r2_score(My, predict_mek(Mx))),3))
print('T弯 in-sample R2 approx', round(float(__import__('sklearn.metrics').metrics.r2_score(Ty, predict_tbend(Tx))),3))