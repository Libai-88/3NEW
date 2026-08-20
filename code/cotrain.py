# -*- coding: utf-8 -*-
"""HONEST co-training regression: exploit 'has-recipe-missing-target' samples.
Per fold: train model on labeled rows, pseudo-label the training-fold rows that
lack THIS target, add high-confidence ones, retrain, evaluate on held-out test.
Test fold labels are NEVER used for pseudo-labeling or training.
Compare co-training vs baseline under leakage-free repeated CV."""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_absolute_error
from collections import Counter
SEED=0
m=np.load('../data/master3.npz',allow_pickle=True)
X=np.vstack([m['Xo_b'],m['Xn_b']])
yT=np.concatenate([m['yT_o'],m['yT_n']]); yM=np.concatenate([m['yM_o'],m['yM_n']])
batch=np.concatenate([m['batch_o'],m['batch_n']]); fam=np.concatenate([m['fam_o'],m['fam_n']])
keep=[j for j in range(X.shape[1]) if np.std(X[:,j])>1e-9]; X=X[:,keep]
N=len(X)
iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))

# ---- CLEAN implementation ----
def co_reg_clean(task, n_pseudo_rounds=2, keep_frac=0.5):
    yok = iT if task=='T' else iM
    y = yTf if task=='T' else yM
    oof=np.full(N,np.nan)
    for tr,te in KFold(5,shuffle=True,random_state=SEED).split(X):
        li=np.array([i for i in tr if yok[i] and np.isfinite(y[i])])
        ui_list=[i for i in tr if not yok[i]]
        # fit members once to get stable uncertainty
        member=[ExtraTreesRegressor(150,random_state=SEED+i,max_features=0.6,min_samples_leaf=2).fit(X[li],y[li]) for i in range(5)]
        pseudo={}
        cur=ui_list[:]
        for rnd in range(n_pseudo_rounds):
            if len(cur)<2: break
            P=np.vstack([mm.predict(X[cur]) for mm in member])
            unc=P.std(0); mu=P.mean(0)
            order=np.argsort(unc)  # low std first = confident
            nkeep=max(1,int(np.ceil(len(cur)*keep_frac)))
            pool=order[:nkeep]
            for j in pool:
                pseudo[int(cur[j])]=float(mu[j])
            # drop selected
            sel=set(int(cur[j]) for j in pool)
            cur=[i for i in cur if i not in sel]
        # final training set = labeled + pseudo
        idx=list(li)+list(pseudo.keys())
        ytr=np.array([y[i] for i in idx])
        okmask=np.isfinite(ytr)
        idx=np.array(idx)[okmask]; ytr=ytr[okmask]
        Xtr=X[idx]
        final=ExtraTreesRegressor(700,random_state=SEED,min_samples_leaf=2,max_features=0.6).fit(Xtr,ytr)
        oof[te]=final.predict(X[te])
    ms=np.isfinite(y)&np.isfinite(oof)
    return r2_score(y[ms],oof[ms]), mean_absolute_error(y[ms],oof[ms]), int(len(li)), len(pseudo)

# baseline (no co-training) for fairness
def baseline(task):
    yok=iT if task=='T' else iM; y=yTf if task=='T' else yM
    oof=np.full(N,np.nan)
    for tr,te in KFold(5,shuffle=True,random_state=SEED).split(X):
        li=np.array([i for i in tr if yok[i]])
        est=ExtraTreesRegressor(700,random_state=SEED,min_samples_leaf=2,max_features=0.6).fit(X[li],y[li])
        oof[te]=est.predict(X[te])
    ms=np.isfinite(y)&np.isfinite(oof)
    return r2_score(y[ms],oof[ms]), mean_absolute_error(y[ms],oof[ms])

for task in ['T','M']:
    r0,ma0=baseline(task)
    r1,ma1,nlab,npseudo=co_reg_clean(task)
    print(f'[{task}] baseline R2={r0:.3f} MAE={ma0:.3f}  |  co-train R2={r1:.3f} MAE={ma1:.3f}  (pseudo-added N={npseudo})')