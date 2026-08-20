# -*- coding: utf-8 -*-
"""Simpler stacking for 水煮 classification: honest GroupKFold."""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.model_selection import GroupKFold, KFold
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
SEED=0; np.random.seed(SEED)
m=np.load('../data/master3.npz',allow_pickle=True)
X=np.vstack([m['Xo_b'],m['Xn_b']]); wB=np.concatenate([m['wB_o'],m['wB_n']]); fam=np.concatenate([m['fam_o'],m['fam_n']])
keep=[j for j in range(X.shape[1]) if np.std(X[:,j])>1e-9]; X=X[:,keep]
iW=np.isfinite(wB); yw=wB[iW].astype(int); Xw=X[iW]; famw=fam[iW]
NT=yw.shape[0]
gk=GroupKFold(5); folds=list(gk.split(Xw,groups=famw))
BASE=['rf','gbr','et']
def mkind(kind,seed=0):
    if kind=='rf': return RandomForestClassifier(500,random_state=seed,min_samples_leaf=2,class_weight='balanced_subsample')
    if kind=='gbr':return GradientBoostingClassifier(n_estimators=250,random_state=seed,max_depth=2,learning_rate=0.05)
    if kind=='et': return ExtraTreesClassifier(500,random_state=seed,min_samples_leaf=2,class_weight='balanced_subsample')
def proba_align(estimator,Xp):
    p=estimator.predict_proba(Xp); cs=estimator.classes_
    out=np.zeros((len(Xp),5))
    for j,c in enumerate(cs): out[:,int(c)-1]=p[:,j]
    return out
def scr(y,p): return accuracy_score(y,p), np.mean(np.abs(y-p)<=1)

# 1 baseline RF
oofb=np.full(NT,-1)
for tr,te in folds:
    oofb[te]=mkind('rf').fit(Xw[tr],yw[tr]).predict(Xw[te])
print('1) baseline RF    acc=%.3f 1off=%.3f'%scr(yw,oofb))

# 2 stacked (3 base models, OOF prob -> logistic meta)
oofs=np.full(NT,-1)
K=len(BASE)
for tr,te in folds:
    Xtr,ytr=Xw[tr],yw[tr]
    # inner OOF prob on train
    oof_tr=np.zeros((len(tr),5*K))
    for k,kind in enumerate(BASE):
        ikf=KFold(3,shuffle=True,random_state=k)
        for tr2,te2 in ikf.split(Xtr):
            est=mkind(kind,k); est.fit(Xtr[tr2],ytr[tr2])
            oof_tr[te2,k*5:k*5+5]=proba_align(est,Xtr[te2])
    # fit meta
    meta=LogisticRegression(max_iter=2000,C=0.5).fit(oof_tr,ytr)
    # test proba
    Pte=np.zeros((len(te),5*K))
    for k,kind in enumerate(BASE):
        est=mkind(kind,k); est.fit(Xtr,ytr)
        Pte[:,k*5:k*5+5]=proba_align(est,Xw[te])
    oofs[te]=meta.predict(Pte)
print('2) stacking(3base) acc=%.3f 1off=%.3f'%scr(yw,oofs))

# 3 soft voting (uniform avg of base proba)
oofv=np.full(NT,-1)
for tr,te in folds:
    Pte=np.zeros((len(te),5))
    for kind in BASE:
        cl=mkind(kind).fit(Xw[tr],yw[tr])
        Pte+=proba_align(cl,Xw[te])
    oofv[te]=np.argmax(Pte,axis=1)+1
print('3) soft voting     acc=%.3f 1off=%.3f'%scr(yw,oofv))