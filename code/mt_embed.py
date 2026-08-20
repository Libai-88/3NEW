# -*- coding: utf-8 -*-
"""Final sprint on SAME-PROCESS pool (277 rows). MT embedding for T弯 + ordinal water."""
import numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import ExtraTreesRegressor, RandomForestClassifier
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, accuracy_score, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
SEED=0
m=np.load('../data/master3.npz',allow_pickle=True)
bo=m['batch_o']; o726=bo=='7.26'
Xn=m['Xn_b']; fam_n=m['fam_n']
Xo=m['Xo_b'][o726]; yo_T=m['yT_o'][o726]; yo_M=m['yM_o'][o726]; yo_W=m['wB_o'][o726]; fam_o=m['fam_o'][o726]
Xo=np.vstack([Xo,Xn]); yT=np.concatenate([yo_T,m['yT_n']]); yM=np.concatenate([yo_M,m['yM_n']])
wB=np.concatenate([yo_W,m['wB_n']]); fam=np.concatenate([fam_o,fam_n])
keep=[j for j in range(Xo.shape[1]) if np.std(Xo[:,j])>1e-9]; X=Xo[:,keep]
N=len(X); iT=np.isfinite(yT)&(yT<50); iM=np.isfinite(yM); iW=np.isfinite(wB)
yTf=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
gk=GroupKFold(5); folds=list(gk.split(X,groups=fam))
def mkfold(mask):
    out=[]
    for tr,te in folds:
        trm=tr[np.isin(tr,np.where(mask)[0])]; tem=te[np.isin(te,np.where(mask)[0])]
        if len(trm)>=20 and len(tem)>=3: out.append((trm,tem))
    return out

def build_mt_embed(tr):
    ri=np.array(tr)
    Xr=X[ri]
    cols=[np.where(iM[ri],yM[ri],np.nan), np.where(iW[ri],wB[ri],np.nan)]
    emb=[]
    for yc in cols:
        ok=~np.isnan(yc)
        if ok.sum()<20: emb.append(np.zeros(len(ri))); continue
        e=ExtraTreesRegressor(400,random_state=SEED,min_samples_leaf=2).fit(Xr[ok],yc[ok])
        emb.append(e.predict(Xr))
    return ri, np.column_stack(emb)

def tbend(do_emb):
    oof=np.full(N,np.nan)
    for tr,te in mkfold(iT):
        use=np.array([i for i in tr if iT[i]])
        ytr=yTf[use]
        if do_emb:
            ri=tr[np.array([True]*len(tr))]
            _,emb=build_mt_embed(ri)
            mapp={int(r):j for j,r in enumerate(ri)}
            rows=[mapp[int(u)] for u in use]
            Xtr=np.hstack([X[use],emb[rows]])
        else:
            Xtr=X[use]
        mdl=ExtraTreesRegressor(800,random_state=SEED,min_samples_leaf=2).fit(Xtr,ytr)
        oof[te]=mdl.predict(X[te])
    ms=np.isfinite(yTf)&np.isfinite(oof); return r2_score(yTf[ms],oof[ms]),mean_absolute_error(yTf[ms],oof[ms])

print('=== T弯, same-process pool ===')
r0,m0=tbend(False); print(f'  ET plain       R2={r0:.3f} MAE={m0:.3f}')
try:
    r1,m1=tbend(True);  print(f'  ET +MT-emb    R2={r1:.3f} MAE={m1:.3f}')
except Exception as e:
    print('  MT-emb err',e)

print('\n=== 水煮 ===== same-process pool ===')
def water_rf():
    oof=np.full(N,np.nan)
    for tr,te in mkfold(iW):
        use=np.array([i for i in tr if iW[i]])
        c=RandomForestClassifier(700,random_state=SEED,min_samples_leaf=2,class_weight='balanced_subsample').fit(X[use],wB[use].astype(int))
        oof[te]=c.predict(X[te])
    ms=np.isfinite(wB)&np.isfinite(oof)
    return accuracy_score(wB[ms].astype(int),oof[ms]), np.mean(np.abs(wB[ms].astype(int)-oof[ms])<=1)
def water_ord():
    oof=np.full(N,np.nan)
    for tr,te in mkfold(iW):
        use=np.array([i for i in tr if iW[i]])
        r=Pipeline([('s',StandardScaler()),('m',Ridge(alpha=5))]).fit(X[use],wB[use])
        p=np.clip(r.predict(X[te]),1,4); oof[te]=np.round(p)
    ms=np.isfinite(wB)&np.isfinite(oof)
    return accuracy_score(wB[ms].astype(int),oof[ms]), np.mean(np.abs(wB[ms].astype(int)-oof[ms])<=1)
wrf,w1f=water_rf(); wo,w1o=water_ord()
print(f'  water RF            acc={wrf:.3f} 1off={w1f:.3f}')
print(f'  water ordinal(Ridge) acc={wo:.3f} 1off={w1o:.3f}')