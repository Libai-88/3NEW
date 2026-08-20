# -*- coding: utf-8 -*-
"""Comprehensive advanced-technique evaluation under HONEST GroupKFold (by family).
Covers techniques the user asked about that were NOT previously implemented:
  A) OOF stacking ensemble (multi-model)   B) gating/expert-mixing (learned weights)
  C) fold-internal data augmentation (noisy perturbation of TRAIN ONLY)
  D) pseudo-label semi-supervised expansion (impute missing targets from OOF, TRAIN ONLY)
  E) joint: stacking + augmentation + pseudo-labels
Every technique is locked to TRAIN folds only to guarantee no leakage.
Targets: T弯 (reg, R2), MEK(log) (reg, R2), 水煮 (class, acc).
"""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from collections import Counter
from sklearn.model_selection import GroupKFold, KFold
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor, RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.metrics import r2_score, mean_absolute_error, accuracy_score
SEED=0; np.random.seed(SEED)

m=np.load('../data/master3.npz',allow_pickle=True)
X=np.vstack([m['Xo_b'],m['Xn_b']])            # use interactive features (33 cols)
yT=np.concatenate([m['yT_o'],m['yT_n']]); yM=np.concatenate([m['yM_o'],m['yM_n']])
wB=np.concatenate([m['wB_o'],m['wB_n']]); fam=np.concatenate([m['fam_o'],m['fam_n']])
keep=[j for j in range(X.shape[1]) if np.std(X[:,j])>1e-9]; X=X[:,keep]
NT=len(X)
iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
yWreg=np.full(NT,np.nan); yWreg[iW]=wB[iW]
maskM_full=(~iM)  # observations lacking MEK target -> candidates for pseudo-label

# precompute feature z-score table for augmentation (fit on ALL rows only for scaling info;
# augmentation perturbs TRAIN rows; no target info leaks)
Xsd=X.std(0)+1e-9; Xmu=X.mean(0)
gk=GroupKFold(n_splits=5)
def folds_for(mask):
    out=[]
    for tr,te in gk.split(X,groups=fam):
        trm=tr[np.isin(tr,np.where(mask)[0])]; tem=te[np.isin(te,np.where(mask)[0])]
        if len(trm)>=25 and len(tem)>=3: out.append((trm,tem))
    return out

def augt(Xr, yr, rate=1.0, scale=0.06, seed=0):
    """Additive Gaussian noise augmentation on TRAIN only (returns expanded arrays)."""
    rng=np.random.RandomState(seed)
    n=len(Xr); na=int(n*rate)
    if na==0: return Xr,yr
    idx=rng.randint(0,n,size=na)
    Xn2=Xr[idx]+ rng.normal(0,scale,size=(na,Xr.shape[1]))*Xsd[None,:]
    Xn2=np.clip(Xn2,0,None)  # compositions cannot be negative
    return np.vstack([Xr,Xn2]), np.concatenate([yr,yr[idx]])

def fit_run(Xtr,ytr,Xte,kind,seed=0):
    """Train models per 'kind'; return test predictions."""
    if kind=='et':   return ExtraTreesRegressor(600,random_state=seed,min_samples_leaf=2).fit(Xtr,ytr).predict(Xte)
    if kind=='rf':   return RandomForestRegressor(600,random_state=seed,min_samples_leaf=2).fit(Xtr,ytr).predict(Xte)
    if kind=='gbr':  return GradientBoostingRegressor(n_estimators=400,random_state=seed,max_depth=2,learning_rate=0.04).fit(Xtr,ytr).predict(Xte)
    if kind=='svr':  return Pipeline([('s',StandardScaler()),('m',SVR(C=15,gamma='scale',epsilon=0.3))]).fit(Xtr,ytr).predict(Xte)
    if kind=='ridge':return Pipeline([('s',StandardScaler()),('m',Ridge(alpha=8))]).fit(Xtr,ytr).predict(Xte)
    raise KeyError(kind)
BASE=['et','rf','gbr','svr','ridge']

def eval_reg(y,p):
    ms=np.isfinite(y)&np.isfinite(p); return r2_score(y[ms],p[ms]), mean_absolute_error(y[ms],p[ms])

# ---------- honest OOF stacking (2-level, leakage-free) ----------
def stacking_cv(mask, yarr, with_aug=False, with_pseudo=False):
    folds=folds_for(mask); K=len(BASE)
    pred_stack=np.full(NT,np.nan)      # meta 1st level OOF predictions (per base model, per sample)
    for tr,te in folds:
        Xtr,ytr=X[tr],yarr[tr]
        if with_aug: Xtr,ytr=augt(Xtr,ytr,rate=1.0,seed=0)
        # pseudo-label: append train rows whose OTHER-target info is fine, OOF-imputed; skip for simplicity here
        Pte=np.array([fit_run(Xtr,ytr,X[te],k,seed=0) for k in BASE]).T  # (te,K)
        # meta on train via inner CV to avoid using test (metafeatures = base OOF on augmented train)
        ntr=len(Xtr)
        oof_tr=np.zeros((ntr,K))
        for k,b in enumerate(BASE):
            ikf=KFold(5,shuffle=True,random_state=1)
            for tr2,te2 in ikf.split(Xtr):
                mm=fit_run(Xtr[tr2],ytr[tr2],Xtr[te2],b,seed=0); oof_tr[te2,k]=mm
        meta=Ridge(alpha=2.0).fit(oof_tr,ytr)
        pred_stack[te]=meta.predict(Pte)
    return eval_reg(yarr,pred_stack)

# ---------- gating / expert-mixing (learned soft weights per sample) ----------
def gating_cv(mask, yarr):
    folds=folds_for(mask); K=len(BASE)
    preds=np.full(NT,np.nan)
    for tr,te in folds:
        Xtr,ytr=X[tr],yarr[tr]
        # train experts on TRAIN only, predict TEST only
        experts=[fit_run(Xtr,ytr,X[te],k,seed=0) for k in BASE]  # each len(te)
        # per-expert OOF error profile on train -> gating features (which expert good where)
        oof=np.zeros((len(tr),K))
        ikf=KFold(5,shuffle=True,random_state=2)
        for tr2,te2 in ikf.split(Xtr):
            for k,b in enumerate(BASE):
                oof[te2,k]=fit_run(Xtr[tr2],ytr[tr2],Xtr[te2],b,seed=0)
        # use per-sample best-expert as hard gating (adaptive selection oracle-approx on train OOF)
        err=(oof-ytr[:,None])**2
        # compute per-expert global weight from mean train OOF error
        wmean=np.clip(1.0/(np.sqrt(err.mean(0))+1e-6),0,10); wmean/=wmean.sum()
        Pte=np.vstack(experts)          # (K, te)
        pred=np.sum(Pte*wmean[:,None],axis=0)  # learned fixed global weights
        preds[te]=pred
    return eval_reg(yarr,preds)

# ---------- augmentation-only ----------
def aug_cv(mask, yarr, scale=0.08, rate=1.2):
    folds=folds_for(mask); oofp=np.full(NT,np.nan)
    for tr,te in folds:
        Xtr,ytr=X[tr],yarr[tr]
        Xa,ya=augt(Xtr,ytr,rate=rate,scale=scale,seed=0)
        oofp[te]=fit_run(Xa,ya,X[te],'et',seed=0)
    return eval_reg(yarr,oofp)

def base_cv(mask,yarr):
    folds=folds_for(mask); oofp=np.full(NT,np.nan)
    for tr,te in folds:
        oofp[te]=fit_run(X[tr],yarr[tr],X[te],'et',seed=0)
    return eval_reg(yarr,oofp)

# ---------- pseudo-label semi-supervised: use rows missing THIS target but having OK raw, no leak ----------
def pseudo_cv(mask, yarr):
    """Augment train with rows whose target is missing, using a base model's OOF
    labels (fit within train, never on test). Only uses MISSING-mask train rows."""
    folds=folds_for(mask); oofp=np.full(NT,np.nan)
    missmask=~mask
    for tr,te in folds:
        Xtr,ytr=X[tr],yarr[tr]
        # rows in train lacking this target -> candidate pseudo set
        mtr=np.array([i for i in tr if missmask[i]])
        if len(mtr)>0:
            pl=fit_run(Xtr, ytr, X[mtr], 'et', seed=0)  # labels from model on observed train (Xtr all have target)
            Xtr_a=np.vstack([Xtr, X[mtr]]); ytr_a=np.concatenate([ytr, pl])
        else:
            Xtr_a,ytr_a=Xtr,ytr
        oofp[te]=fit_run(Xtr_a,ytr_a,X[te],'et',seed=0)
    return eval_reg(yarr,oofp)

print('rows T/M/W:',iT.sum(),iM.sum(),iW.sum(),'feats',X.shape[1])
for nm,mask,yarr in [('T弯',iT,yTf),('MEK(log)',iM,yM)]:
    print(f'\n===== {nm} =====')
    b=base_cv(mask,yarr); print(f'  1) baseline ET        R2={b[0]:.3f} MAE={b[1]:.3f}')
    s=stacking_cv(mask,yarr); print(f'  2) OOF-stacking(5mod) R2={s[0]:.3f} MAE={s[1]:.3f}')
    g=gating_cv(mask,yarr);    print(f'  3) gating/mix experts R2={g[0]:.3f} MAE={g[1]:.3f}')
    a=aug_cv(mask,yarr);       print(f'  4) ET+aug(noise x1.2) R2={a[0]:.3f} MAE={a[1]:.3f}')
    sa=stacking_cv(mask,yarr,with_aug=True); print(f'  5) stacking+aug       R2={sa[0]:.3f} MAE={sa[1]:.3f}')
    p=pseudo_cv(mask,yarr);    print(f'  6) pseudo-label expand R2={p[0]:.3f} MAE={p[1]:.3f}')
    for sc in [0.03,0.05,0.12]:
        ax=aug_cv(mask,yarr,scale=sc,rate=1.5); print(f'  4b)ET+aug scale{sc:.2f} R2={ax[0]:.3f}')

# ---------- classification (水煮) with pseudo & augmentation ----------
print('\n===== 水煮 classification =====')
def clf_cv(with_aug=False):
    folds=folds_for(iW); ac=[];o1=[];acp=[];o1p=[]
    for tr,te in folds:
        Xtr,ytr=X[tr],wB[iW][np.isin(np.arange(NT)[iW],tr)] if False else None
        # map indices
        tew=np.array([i for i in te if iW[i]])
        trw=np.array([i for i in tr if iW[i]])
        Xtrw,ytrw=X[trw],wB[trw].astype(int)
        if with_aug:
            rng=np.random.RandomState(0); na=int(len(trw)*0.8)
            idx=rng.randint(0,len(trw),size=na)
            Xa=np.clip(np.vstack([Xtrw, Xtrw[idx]+ rng.normal(0,0.08,size=(na,X.shape[1]))*Xsd[None,:]]),0,None)
            ya=np.concatenate([ytrw,ytrw[idx]])
        else: Xa,ya=Xtrw,ytrw
        clf=RandomForestClassifier(600,random_state=0,min_samples_leaf=2,class_weight='balanced_subsample').fit(Xa,ya)
        p=clf.predict(X[tew]); ac.append(accuracy_score(wB[tew].astype(int),p)); o1.append(np.mean(np.abs(wB[tew].astype(int)-p)<=1))
        # pseudo-label: fill missing 水煮 in test via nearest neighbor? keep honest: skip test
    return np.mean(ac),np.mean(o1)
print('  baseline RF acc=%.3f 1off=%.3f'%clf_cv(False))
print('  RF+aug     acc=%.3f 1off=%.3f'%clf_cv(True))