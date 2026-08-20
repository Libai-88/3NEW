# -*- coding: utf-8 -*-
"""Explore W-grade coupling to continuous T/M: ordinal structure & how much a
continuous signal (EMBED from T/M as auxiliary) can lift classification, using
leak-free within-fold embeddings (aux targets = T,M). Also ordinal classifier.
This is a legitimate signal-coupling direction previously under-explored."""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor, RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score
from scipy.stats import spearmanr
m=np.load('../data/master3.npz',allow_pickle=True)
o726=m['batch_o']=='7.26'
Xn=m['Xn_b']; fam_n=m['fam_n']
Xo=m['Xo_b'][o726]; yTo=m['yT_o'][o726]; yMo=m['yM_o'][o726]; wo=m['wB_o'][o726]; famo=m['fam_o'][o726]
X=np.vstack([Xo,Xn]); yT=np.concatenate([yTo,m['yT_n']]); yM=np.concatenate([yMo,m['yM_n']]); wB=np.concatenate([wo,m['wB_n']]); fam=np.concatenate([famo,fam_n])
iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
# coupling between W grade and continuous target (on joint-valid samples)
joint=iT&iM&iW
if joint.sum()>20:
    rT=spearmanr(wB[joint],yT[joint]).statistic; rM=spearmanr(wB[joint],yM[joint]).statistic
    print(f'Spearman W-grade vs T={rT:.3f}, W vs MEK(log)={rM:.3f}  (joint n={joint.sum()})')
# per-grade mean of T and M (check monotonic ordinal structure)
for g in [2,3,4]:
    ms=joint&(wB==g)
    print(f'  grade{g}: meanT={np.mean(yT[ms]):.2f} meanM={np.mean(yM[ms]):.2f}  (n={ms.sum()})')
# ordinal classifier baseline vs RF, leak-free
def run(withemb):
    Xe=X
    rfc=[]; rfo=[]
    gk=GroupKFold(5); folds=list(gk.split(np.arange(len(wB)),groups=fam))
    for tr,te in folds:
        trm=tr[np.isin(tr,np.where(iW)[0])]; tem=te[np.isin(te,np.where(iW)[0])]
        if len(trm)<20 or len(tem)<3: continue
        Xtr=Xe[trm]; ytr=wB[trm].astype(int); Xte=Xe[tem]; yte=wB[tem].astype(int)
        if withemb:
            # embed from M continuous target (train fold only)
            mm=[i for i in trm if iM[i] and iW[i]]
            if len(mm)>=20:
                em=ExtraTreesRegressor(600,random_state=0,min_samples_leaf=2).fit(Xe[np.array(mm)],yM[np.array(mm)]).predict(Xe[trm])
                Xtr=np.hstack([Xtr,em[:,None]])
                Xte=np.hstack([Xte,em[:,None]])
        c=RandomForestClassifier(700,random_state=0,min_samples_leaf=2,class_weight='balanced_subsample').fit(Xtr,ytr)
        rfc.append(accuracy_score(yte,c.predict(Xte)))
    return np.mean(rfc)
print('\n=== W-grade classification (leak-free GroupKFold) ===')
print(f'RF plain acc={run(False):.3f}')
print(f'RF + MEK-embed acc={run(True):.3f}')