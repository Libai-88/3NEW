# -*- coding: utf-8 -*-
"""Final honest verification: real-only vs real+literature-aug on clean same-process pool.
Reports true generalization delta for each task (GroupKFold by family)."""
import numpy as np, warnings, json; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor, RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, accuracy_score
SEED=0; rng=np.random.default_rng(SEED)
m=np.load('../data/master3.npz',allow_pickle=True)
bo=m['batch_o']; o726=bo=='7.26'
Xn=m['Xn_b']; famn=m['fam_n']
Xo=m['Xo_b'][o726]; yTo=m['yT_o'][o726]; yMo=m['yM_o'][o726]; wBo=m['wB_o'][o726]; famo=m['fam_o'][o726]
X=np.vstack([Xo,Xn]); yT=np.concatenate([yTo,m['yT_n']]); yM=np.concatenate([yMo,m['yM_n']])
wB=np.concatenate([wBo,m['wB_n']]); fam=np.concatenate([famo,famn])
keep=[j for j in range(X.shape[1]) if np.std(X[:,j])>1e-9]; X=X[:,keep]
N=len(X); iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
_lblmap={i:{'T':(yTf[i] if iT[i] else None),'M':(yM[i] if iM[i] else None),'W':(wB[i] if iW[i] else None)} for i in range(N)}
def lmap(i): return {k:v for k,v in _lblmap[i].items() if v is not None}

def convex_aug(seed,n,alpha=2.0):
    Xs=np.array([r for r,_ in seed]); labs=[l for _,l in seed]; O={t:[] for t in ('T','M','W')}; ox=[]
    for _ in range(n):
        K=int(rng.integers(2,4)); idx=rng.integers(0,len(Xs),K); w=rng.dirichlet(np.full(K,alpha))
        ox.append((Xs[idx]*w[:,None]).sum(0))
        for t in ('T','M','W'):
            sub=[a for a in idx if t in labs[a]]
            if not sub: O[t].append(np.nan)
            else:
                ww=w[[list(idx).index(a) for a in sub]]; O[t].append(float((np.array([labs[a][t] for a in sub])*ww).sum()/ww.sum()))
    return np.array(ox),{t:np.array(O[t],float) for t in O}

def gamma(task):
    gk=GroupKFold(5); tidx=np.array([i for i in range(N) if mask(task)[i]])
    folds=list(gk.split(tidx,groups=fam[tidx]))
    real=[]; augx=[]
    for trr,ter in folds:
        tri=tidx[trr]; tei=tidx[ter]
        ltr=[i for i in tri if task in lmap(i)]
        if len(ltr)<20: continue
        Xtr=X[ltr]; ytr=np.array([lmap(i)[task] for i in ltr])
        seed=[(X[i],lmap(i)) for i in ltr]
        m_r=ExtraTreesRegressor(900,random_state=SEED,min_samples_leaf=2).fit(Xtr,ytr)
        real.append(r2_score(Y(task)[tei],m_r.predict(X[tei])))
        Xa,O=convex_aug(seed,int(0.6*len(ltr))); ok=np.isfinite(O[task]); Xa=Xa[ok]; ya=O[task][ok]
        m_a=ExtraTreesRegressor(900,random_state=SEED,min_samples_leaf=2).fit(np.vstack([Xtr,Xa]),np.concatenate([ytr,ya]))
        augx.append(r2_score(Y(task)[tei],m_a.predict(X[tei])))
    return np.mean(real),np.mean(augx)

def gamma_clf():
    gk=GroupKFold(5); tidx=np.array([i for i in range(N) if iW[i]])
    folds=list(gk.split(tidx,groups=fam[tidx])); real=[]; augx=[]
    for trr,ter in folds:
        tri=tidx[trr]; tei=tidx[ter]
        ltr=[i for i in tri if 'W' in lmap(i)]
        if len(ltr)<20: continue
        Xtr=X[ltr]; ytr=np.array([lmap(i)['W'] for i in ltr]).astype(int)
        m_r=RandomForestClassifier(900,random_state=SEED,min_samples_leaf=2,class_weight='balanced_subsample').fit(Xtr,ytr)
        real.append(accuracy_score(wB[tei].astype(int),m_r.predict(X[tei])))
        seed=[(X[i],lmap(i)) for i in ltr]
        Xa,O=convex_aug(seed,int(0.6*len(ltr))); ok=np.isfinite(O['W']); Xa=Xa[ok]; ya=O['W'][ok].astype(int)
        m_a=RandomForestClassifier(900,random_state=SEED,min_samples_leaf=2,class_weight='balanced_subsample').fit(np.vstack([Xtr,Xa]),np.concatenate([ytr,ya]))
        augx.append(accuracy_score(wB[tei].astype(int),m_a.predict(X[tei])))
    return np.mean(real),np.mean(augx)

def mask(t): return {'T':iT,'M':iM,'W':iW}[t]
def Y(t): return {'T':yTf,'M':yM,'W':wB}[t]

res={}
for t in ('T','M'):
    r,a=gamma(t); res[t]={'real':round(r,3),'aug':round(a,3),'delta':round(a-r,3)}
r,a=gamma_clf(); res['W']={'real':round(r,3),'aug':round(a,3),'delta':round(a-r,3)}
print(json.dumps(res,ensure_ascii=False,indent=2))
with open('../results/final_matrix.json','w') as f: json.dump(res,f,ensure_ascii=False,indent=2)
print('Targets: reg R2>=0.85, clf acc>=0.95')