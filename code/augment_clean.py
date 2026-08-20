# -*- coding: utf-8 -*-
"""Literature-driven recipe augmentation on CLEAN same-process(200/10) pool.
A1 convex-blend recipes (labels = weighted blend of parents + meas. noise)-
   Schiemer2024 component-profile; Scheffe mixture additivity.
A2 bounded constrained perturbation (sparsity/matrix held).
A3 target measurement noise (Bjerrum-style replicate).
HONEST GroupKFold by family; augment generated ONLY from train-fold real rows;
test families strictly excluded from all augmentation.training pipeline.
"""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, mean_absolute_error, accuracy_score
SEED=0; rng=np.random.default_rng(SEED)
m=np.load('../data/master3.npz',allow_pickle=True)
bo=m['batch_o']; o726=bo=='7.26'
Xn=m['Xn_b']; famn=m['fam_n']
Xo=m['Xo_b'][o726]; yTo=m['yT_o'][o726]; yMo=m['yM_o'][o726]; wBo=m['wB_o'][o726]; famo=m['fam_o'][o726]
X=np.vstack([Xo,Xn]); yT=np.concatenate([yTo,m['yT_n']]); yM=np.concatenate([yMo,m['yM_n']])
wB=np.concatenate([wBo,m['wB_n']]); fam=np.concatenate([famo,famn])
keep=[j for j in range(X.shape[1]) if np.std(X[:,j])>1e-9]; X=X[:,keep]; nfeat=X.shape[1]
N=len(X); iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
fzero=(X<1e-9).mean(0); fmin=X.min(0); fmax=X.max(0)
matrix_col=0  # IR190 near-constant

def convex_aug(Xseed_labels, n_new, alpha=2.0, aug_tasks=('T','M','W')):
    Xs=np.array([r for r,_ in Xseed_labels]); labs=[l for _,l in Xseed_labels]
    outX=[]; outL={t:[] for t in aug_tasks}
    nl=len(Xs)
    for _ in range(n_new):
        K=int(rng.integers(2,4)); idx=rng.integers(0,nl,K); w=rng.dirichlet(np.full(K,alpha))
        outX.append((Xs[idx]*w[:,None]).sum(0))
        for t in aug_tasks:
            # keep parents with this target
            sub=[a for a in idx if t in labs[a]]
            if len(sub)==0:
                outL[t].append(np.nan); continue
            yl=np.array([labs[a][t] for a in sub])
            w2=w[[list(idx).index(a) for a in sub]]; w2=w2/w2.sum()
            outL[t].append(float((yl*w2).sum()))
    return np.array(outX), {t:np.array(outL[t]) for t in aug_tasks}

def perturb_aug(Xseed_labels, n_new, eps=0.06, rnd_frac=0.5, aug_tasks=('T','M','W')):
    Xs=np.array([r for r,_ in Xseed_labels]); labs=[l for _,l in Xseed_labels]
    outX=[]; outL={t:[] for t in aug_tasks}; nl=len(Xs)
    for _ in range(n_new):
        row=Xs[rng.integers(0,nl)].copy()
        for j in range(nfeat):
            if fzero[j]>0.6 and rng.random()<rnd_frac: row[j]=0.0
            elif j==matrix_col: row[j]=row[j]*(1+rng.normal(0,0.002))
            elif row[j]>0: row[j]=max(0,row[j]*rng.uniform(1-eps,1+eps))
        row=np.clip(row,fmin*0.5,fmax*1.05)
        outX.append(row)
        for t in aug_tasks:
            sub=[i for i in range(nl) if t in labs[i]]
            outL[t].append(labs[rng.choice(sub)][t] if sub else np.nan)  # single-parent label
    return np.array(outX), {t:np.array(outL[t]) for t in aug_tasks}

def target_noise(y, task, scale):
    y=np.asarray(y,float)
    if task=='T': return y+rng.normal(0,1.4*scale,len(y))
    if task=='M': return y+rng.normal(0,0.22*scale,len(y))
    r=rng.random(len(y)); sh=np.where(r<0.12*scale,-1,np.where(r<0.24*scale,1,0))
    return np.clip(y.astype(int)+sh,2,4).astype(float)

# task -> its label key within label tuple
def run_task(task, ycol, mask, model_kind, base_n_aug=2500, alpha=2.0, use_noise=True):
    # build label tuple per row having that target
    rows=[] # (Xrow, {T,M,W: label})
    for i in range(N):
        if not mask[i]: continue
        li={}
        if iT[i]: li['T']=(yTf[i] if task=='T' else 0.0)
        # store real label only for target task (others may be missing)
        if iM[i]: li['M']=yM[i]
        if iW[i]: li['W']=wB[i]
        if task in li: rows.append((X[i], li))
    rowarr=[r for r,_ in rows]; lbls=[l for _,l in rows]
    oof_real=np.full(N,np.nan); oof_aug=np.full(N,np.nan)
    gk=GroupKFold(5); 
    tr_idx=np.array([i for i in range(N) if mask[i]])
    folds=list(gk.split(tr_idx,groups=fam[tr_idx]))
    for trr,ter in folds:
        tri=tr_idx[trr]; tei=tr_idx[ter]  # real row indices in train/test
        # labeled train rows for task
        ltr=[i for i in tri if (task in lbls_map(i))]
        if len(ltr)<20: continue
        Xtr=X[ltr]; ytr=np.array([lbls_map(i)[task] for i in ltr])
        # --- build augmented from Xtr (full label tuples of train real rows) ---
        seed=[(X[i],lbls_map(i)) for i in ltr]
        n_cv=int(base_n_aug*0.5) if task!='W' else 0
        n_pt=int(base_n_aug*0.5) if task!='W' else base_n_aug
        Xc,Lc=convex_aug(seed,n_cv,alpha)
        Xp,Lp=perturb_aug(seed,n_pt)
        Xa= Xp if n_cv==0 else np.vstack([Xc,Xp])
        ya0= Lp[task] if n_cv==0 else np.concatenate([Lc[task],Lp[task]])
        ok=np.isfinite(ya0)
        Xa=Xa[ok]; ya0=ya0[ok]
        if use_noise: ya=target_noise(ya0,task,0.9)
        else: ya=ya0
        Xall=np.vstack([Xtr,Xa]); yall=np.concatenate([ytr,ya])
        # ---- plain ----
        if task!='W':
            bp=ExtraTreesRegressor(900,random_state=SEED,min_samples_leaf=2).fit(Xtr,ytr)
            bf=ExtraTreesRegressor(900,random_state=SEED,min_samples_leaf=2).fit(Xall,yall)
            oof_real[tei]=bp.predict(X[tei]); oof_aug[tei]=bf.predict(X[tei])
        else:
            bp=RandomForestClassifier(900,random_state=SEED,min_samples_leaf=2,class_weight='balanced_subsample').fit(Xtr,ytr.astype(int))
            bf=RandomForestClassifier(900,random_state=SEED,min_samples_leaf=2,class_weight='balanced_subsample').fit(Xall,yall.astype(int))
            oof_real[tei]=bp.predict(X[tei]); oof_aug[tei]=bf.predict(X[tei])
    yv=ycol  # array over rows
    ms=np.isfinite(yv)&np.isfinite(oof_real)&np.isfinite(oof_aug)
    if task in ('T','M'):
        r0=r2_score(yv[ms],oof_real[ms]); ra=r2_score(yv[ms],oof_aug[ms])
        m0=mean_absolute_error(yv[ms],oof_real[ms]); ma=mean_absolute_error(yv[ms],oof_aug[ms])
        return r0,ra,m0,ma
    else:
        a0=accuracy_score(yv[ms].astype(int),np.round(oof_real[ms])); 
        aa=accuracy_score(yv[ms].astype(int),np.round(oof_aug[ms]))
        return a0,aa,0,0
# helper map
_lblmap={i:{'T':(yTf[i] if iT[i] else None),'M':(yM[i] if iM[i] else None),'W':(wB[i] if iW[i] else None)} for i in range(N)}
def lbls_map(i): 
    return {k:v for k,v in _lblmap[i].items() if v is not None}

for task,ycol,mask in [('W',wB,iW)]:
    r0,ra,m0,ma=run_task(task,ycol,mask,'ET')
    tag='R2' if task!='W' else 'acc'
    print(f'[{task}]  real-only {tag}={r0:.3f} (MAE {m0:.3f}) | real+aug {tag}={ra:.3f} (MAE {ma:.3f})  {(ra-r0):+.3f}')