# -*- coding: utf-8 -*-
"""Pseudo Active Learning: simulate 'only k experiments budget'. 
From current model on labeled pool, use uncertainty (bag std) + diversity (farthest
from solved) to rank candidate UNLABELED recipes, pick TOP k, and simulate their
real labels become available (they're already in our data with real labels).
Measure test R2 gain from adding AL-selected vs random-selected vs uncertainty-only.
This is a DEMO of experiment prioritization (not a model-booster here, since we
already have all labels — but it validates WHICH recipes matter most)."""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
SEED=0; np.random.seed(SEED)
m=np.load('../data/master3.npz',allow_pickle=True)
Xo=m['Xo_b']; Xn=m['Xn_b']; yTo=m['yT_o']; yTn=m['yT_n']; yMo=m['yM_o']; yMn=m['yM_n']
keep=[j for j in range(Xo.shape[1]) if np.std(np.vstack([Xo,Xn])[:,j])>1e-9]
Xo=Xo[:,keep]; Xn=Xn[:,keep]
ioT=np.isfinite(yTo)&(yTo<50); ioT2=ioT&(np.isfinite(yTo))
# focus: build model on OLD labeled, then actively select from NEW unlabeled pool
# we then EVALUATE selected recipes' real labels vs test on remaining new
Xold=Xo[ioT]; yold=np.clip(yTo[ioT],None,np.percentile(yTo[np.isfinite(yTo)],95))
# new labeled pool to pick from
okn=np.isfinite(yTn)&(yTn<50)
XnT=Xn[okn]; ynT=yTn[okn]
XnT=XnT[:60]; ynT=ynT[:60]  # keep 60 as candidate pool, 40 as held-out test
print('old model rows',Xold.shape[0],'new candidate pool',XnT.shape[0])

def bag_uncert(Xtr,ytr,Xte,predict=True):
    member=[ExtraTreesRegressor(300,random_state=SEED+i,min_samples_leaf=2).fit(Xtr,ytr) for i in range(6)]
    P=np.vstack([mm.predict(Xte) for mm in member])
    return P.mean(0), P.std(0)  # mu, unc

# split candidate pool: 40 train-avail (pretend we can query), 20 test
from itertools import combinations
def simulate(strategy,k=5,reps=30):
    """Randomly split candidate pool into budget-avail (nq) and label-test. Actively
    pick k from avail pool, reveal their real labels, retrain old+k, eval on test."""
    gains=[]
    nq=20; ntest=XnT.shape[0]-nq
    for rep in range(reps):
        perm=np.random.permutation(XnT.shape[0])
        q=perm[:nq]; t=perm[nq:]
        Xq,yq=XnT[q],ynT[q]; Xt,yt=XnT[t],ynT[t]
        mu,unc=bag_uncert(Xold,yold,Xq)
        # distances from old solved space
        D=((Xq[:,None,:]-Xold[None,:,:])**2).sum(2).min(1)
        rank_unc=np.argsort(unc)[::-1]            # highest uncertainty first
        rank_rand=np.random.permutation(nq)
        # far = most distant from solved (exploration)
        rank_far=np.argsort(D)[::-1]
        # AL combo: uncertainty * diversity (far)
        comb=unc*D; rank_comb=np.argsort(comb)[::-1]
        chosen={'unc':rank_unc[:k],'rand':rank_rand[:k],'far':rank_far[:k],'comb':rank_comb[:k]}
        res={}
        for nm,ids in chosen.items():
            Xtr2=np.vstack([Xold,Xq[ids]]); ytr2=np.concatenate([yold,yq[ids]])
            mdl=ExtraTreesRegressor(700,random_state=SEED,min_samples_leaf=2).fit(Xtr2,ytr2)
            pr=mdl.predict(Xt); res[nm]=r2_score(yt,pr)
        # baseline: old-only (no new experiment)
        mdl0=ExtraTreesRegressor(700,random_state=SEED,min_samples_leaf=2).fit(Xold,yold)
        res['base_old']=r2_score(yt,mdl0.predict(Xt))
        gains.append(res)
    return {k:float(np.mean([g[k] for g in gains])) for k in gains[0]}

res=simulate('unc',k=5,reps=20)
print('\n=== Pseudo-AL on T弯: avg test R2 after adding k=5 experiments ===')
for k,v in res.items(): print(f'  {k:9s} R2={v:.3f}')
# interpret: which strategy gives best uplift vs base_old
best=max([(k,v) for k,v in res.items() if k!='base_old'],key=lambda x:x[1])
print(f'\n>>> best strategy {best[0]} R2={best[1]:.3f} (base_old={res["base_old"]:.3f})')