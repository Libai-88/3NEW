# -*- coding: utf-8 -*-
"""Champion v5: best architectures (MEK stacking, T gated-mix, W RF) trained on
CLEAN same-process pool (7.26+new, 200/10) WITH literature convex-blend augmentation.
This is the strongest honest deliverable. Honest GroupKFold metrics reported."""
import numpy as np, warnings, pickle; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor, RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, KFold
from sklearn.metrics import r2_score, mean_absolute_error, accuracy_score
SEED=0; rng=np.random.default_rng(SEED)
m=np.load('../data/master3.npz',allow_pickle=True)
bo=m['batch_o']; o726=bo=='7.26'
Xn=m['Xn_b']; famn=m['fam_n']
Xo=m['Xo_b'][o726]; yTo=m['yT_o'][o726]; yMo=m['yM_o'][o726]; wBo=m['wB_o'][o726]; famo=m['fam_o'][o726]
Xo=np.vstack([Xo,Xn]); yT=np.concatenate([yTo,m['yT_n']]); yM=np.concatenate([yMo,m['yM_n']])
wB=np.concatenate([wBo,m['wB_n']]); fam=np.concatenate([famo,famn])
keep=[j for j in range(Xo.shape[1]) if np.std(Xo[:,j])>1e-9]; X=Xo[:,keep]
N=len(X); iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
_lbl={i:{'T':(yTf[i] if iT[i] else None),'M':(yM[i] if iM[i] else None),'W':(wB[i] if iW[i] else None)} for i in range(N)}
def lmap(i): return {k:v for k,v in _lbl[i].items() if v is not None}

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
    return np.array(ox),O

def aug_train(task,tr,ytr,L=0.6):
    seed=[(X[i],lmap(i)) for i in tr if task in lmap(i)]
    if not seed: return X[list(tr)],np.array(ytr)
    Xa,O=convex_aug(seed,int(L*len(seed))); okv=np.isfinite(np.array(O[task],float))
    if okv.sum()==0: return X[list(tr)],np.array(ytr)
    return np.vstack([X[list(tr)],Xa[okv]]), np.concatenate([np.array(ytr),np.array(O[task],float)[okv]])

def base(kind,seed=SEED):
    if kind=='et':   return ExtraTreesRegressor(900,random_state=seed,min_samples_leaf=2,max_features=0.6)
    if kind=='rf':   return RandomForestRegressor(900,random_state=seed,min_samples_leaf=2,max_features=0.6)
    if kind=='gbr':  return GradientBoostingRegressor(n_estimators=500,random_state=seed,max_depth=2,learning_rate=0.04)
    if kind=='svr':  return Pipeline([('s',StandardScaler()),('m',SVR(C=25,gamma='scale',epsilon=0.25))])
    if kind=='ridge':return Pipeline([('s',StandardScaler()),('m',Ridge(alpha=6))])
BASE=['et','rf','gbr','svr','ridge']

def train_T():
    tr=[i for i in range(N) if iT[i]]; Xb,yb=aug_train('T',tr,[yTf[i] for i in tr])
    an=[base(k) for k in BASE]
    mm=[a.fit(Xb,yb) for a in an]
    # gated weights from CV
    ikf=KFold(5,shuffle=True,random_state=2); ooftr=np.zeros((len(Xb),len(BASE)))
    for a_,b_ in ikf.split(Xb):
        for k in range(len(BASE)): ooftr[b_,k]=base(BASE[k]).fit(Xb[a_],yb[a_]).predict(Xb[b_])
    err=np.sqrt(((ooftr-yb[:,None])**2).mean(0)); w=np.clip(1/(err+1e-6),0,10); w/=w.sum()
    return {'models':mm,'w':w,'kind':'gated'}

def train_M():
    tr=[i for i in range(N) if iM[i]]; Xb,yb=aug_train('M',tr,[yM[i] for i in tr])
    an=[base(k) for k in BASE]
    mm=[a.fit(Xb,yb) for a in an]
    ikf=KFold(5,shuffle=True,random_state=1); ooftr=np.zeros((len(Xb),len(BASE)))
    for a_,b_ in ikf.split(Xb):
        for k in range(len(BASE)): ooftr[b_,k]=base(BASE[k]).fit(Xb[a_],yb[a_]).predict(Xb[b_])
    meta=Ridge(alpha=2.0).fit(ooftr,yb)
    return {'models':mm,'meta':meta,'kind':'stack'}

def train_W():
    tr=[i for i in range(N) if iW[i]]; ytr=wB[tr].astype(int)
    c=RandomForestClassifier(900,random_state=SEED,min_samples_leaf=2,class_weight='balanced_subsample').fit(X[tr],ytr)
    return {'model':c,'kind':'rf'}

mT=train_T(); mM=train_M(); mW=train_W()
with open('../models/champion_models_v5.pkl','wb') as f:
    pickle.dump({'T':mT,'M':mM,'W':mW,'keep_idx':keep},f)

def pred_T(obj,x): obj['models']
import numpy as _np
def predict_one(mp):
    T=mp['T']; M=mp['M']; W=mp['W']
    def pt(x):
        x=x.reshape(1,-1)
        P=_np.column_stack([mk.predict(x) for mk in T['models']])
        return float((P*T['w'][None,:]).sum(1)[0])
    def pm(x):
        x=x.reshape(1,-1)
        P=_np.column_stack([mk.predict(x) for mk in M['models']])
        return float(M['meta'].predict(P)[0])
    def pw(x): return int(W['model'].predict(x.reshape(1,-1))[0])
    return pt,pm,pw
with open('../models/champion_models_v5.pkl','rb') as f:
    mp=pickle.load(f)
pt,pm,pw=predict_one(mp)

# honest CV metrics (as computed by aug_bestarch)
print('Saved champion_models_v5.pkl (best-arch + literature aug, clean same-process pool)')
print('  Honest GroupKFold (best-arch on clean pool, from aug_bestarch):')
print('    T弯 gated +aug  R2=0.460   (best-arch baseline 0.461)')
print('    MEK stack +aug  R2=0.452   (best-arch baseline 0.444)')
print('   水煮 RF   +aug  acc=0.405   (RF baseline 0.434; aug hurts, keep no-aug=0.434)')
print('  Model kinds: T=gated-mix, M=5-base OOF-stack, W=RF')
print('  Target: reg R2>=0.85, clf acc>=0.95  -> NOT reachable on current data')