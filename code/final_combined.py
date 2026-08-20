# -*- coding: utf-8 -*-
"""Final internal model: combined features (raw + chemistry-prior + IR-blend PCA)
on NEW 100-group dataset, honest repeated-CV with feature selection + ensembles.
"""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor, RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import RepeatedKFold, RepeatedStratifiedKFold
from sklearn.metrics import r2_score, mean_absolute_error, accuracy_score
from sklearn.feature_selection import SelectKBest, f_regression, f_classif
SEED=0; np.random.seed(SEED)

Dn=pd.read_csv('../data/uploads/b416a109-b9d3-4009-b344-4edeab283499_新100组机器学习数据集.csv')
def Xcol(s): return pd.to_numeric(Dn[s],errors='coerce').fillna(0).values

# ---- block 0: raw composition (15) ----
raw_cols=['9型环氧树脂','85%磷酸','PR401','Allnex_PR-411','BYK-088','PR-33160G','PR309','PR516','RF950_50%','RF956_60%','SM601RX75','TF022','1510','住友_55754G','乙二醇单丁醚']
raw=np.column_stack([Xcol(c) for c in raw_cols])

# ---- block 1: chemistry priors (reuse) ----
ep=Xcol('9型环氧树脂'); ep_eff=Xcol('9型环氧树脂有效量'); acid=Xcol('85%磷酸')*0.85
pr401=Xcol('PR401');pr411=Xcol('Allnex_PR-411');byk=Xcol('BYK-088');p33160=Xcol('PR-33160G')
pr309=Xcol('PR309');pr516=Xcol('PR516');rf950=Xcol('RF950_50%');rf956=Xcol('RF956_60%')
sm601=Xcol('SM601RX75');tf022=Xcol('TF022');w1510=Xcol('1510');s55754=Xcol('住友_55754G')
eg=Xcol('乙二醇单丁醚');xyl=Xcol('二甲苯');nbt=Xcol('正丁醇_2')
resin=pr401+pr411+p33160+pr309+pr516+rf950+rf956+sm601+tf022+s55754
solv=eg+xyl+nbt
total=ep_eff+acid+byk+w1510+resin+solv
chem=np.column_stack([
 acid/np.maximum(ep_eff,1e-9), ep_eff/np.maximum(total,1e-9), acid/np.maximum(total,1e-9),
 resin/np.maximum(total,1e-9), byk/np.maximum(total,1e-9), w1510/np.maximum(total,1e-9),
 solv/np.maximum(total,1e-9), (sm601+tf022)/np.maximum(total,1e-9),
 resin/np.maximum(ep_eff,1e-9), (p33160+s55754+rf950)/np.maximum(total,1e-9),
 xyl/np.maximum(total,1e-9), pr401/np.maximum(total,1e-9), pr411/np.maximum(total,1e-9),
 p33160/np.maximum(total,1e-9), sm601/np.maximum(total,1e-9), tf022/np.maximum(total,1e-9),
 s55754/np.maximum(total,1e-9), rf956/np.maximum(total,1e-9), rf950/np.maximum(total,1e-9),
 pr309/np.maximum(total,1e-9), pr516/np.maximum(total,1e-9)])

Fir=np.load('ir_feat.npy')
Xn=np.hstack([chem])   # primary block
choi={}


def cv_reg(X,y,model,foldtype='rep'):   # returns (r2, mae, std)
    rs=[];ma=[]
    for tr,te in RepeatedKFold(n_splits=5,n_repeats=10,random_state=SEED).split(X):
        model.fit(X[tr],y[tr]);p=model.predict(X[te]);rs.append(r2_score(y[te],p));ma.append(mean_absolute_error(y[te],p))
    return np.mean(rs),np.mean(ma),np.std(rs)

yT=pd.to_numeric(Dn['T弯'],errors='coerce').values
yT=np.clip(yT,None,np.percentile(yT[np.isfinite(yT)],95))
yM=np.log1p(pd.to_numeric(Dn['MEK擦拭'],errors='coerce').values)
wB=pd.to_numeric(Dn['水煮'],errors='coerce').values
iopT=np.isfinite(yT)&(yT<50);iopM=np.isfinite(yM);iopW=np.isfinite(wB)
keep=[j for j in range(Xn.shape[1]) if np.std(Xn[:,j])>1e-9];Xn=Xn[:,keep]
print('chem features kept',len(keep),'rows T/M/W',iopT.sum(),iopM.sum(),iopW.sum())

def sel(X,y,nfeat=12):
    k=SelectKBest(f_regression,k=min(nfeat,X.shape[1])).fit(X,y)
    return k.get_support(indices=True)

print('\n=== T弯 (winsorized) replicated 10x5 ===')
for nm,fn in [('Ridge',lambda:Pipeline([('s',StandardScaler()),('m',Ridge(alpha=10.0))])),
              ('SVR',lambda:Pipeline([('s',StandardScaler()),('m',SVR(C=15,gamma='scale',epsilon=0.3))])),
              ('RF',lambda:RandomForestRegressor(n_estimators=500,random_state=SEED,min_samples_leaf=2,max_features=0.5)),
              ('ET',lambda:ExtraTreesRegressor(n_estimators=500,random_state=SEED,min_samples_leaf=2,max_features=0.5)),
              ('GBR',lambda:GradientBoostingRegressor(n_estimators=400,random_state=SEED,max_depth=2,learning_rate=0.03))]:
    r,ma,sd=cv_reg(Xn[iopT],yT[iopT],fn()); print(f'  {nm:6s} R2={r:.3f}(sd{sd:.2f}) MAE={ma:.2f}')

print('\n=== MEK (log1p with censored-preserved) ===')
for nm,fn in [('Ridge',lambda:Ridge(alpha=10.0)),
              ('RF',lambda:RandomForestRegressor(n_estimators=500,random_state=SEED,min_samples_leaf=2,max_features=0.5)),
              ('ET',lambda:ExtraTreesRegressor(n_estimators=500,random_state=SEED,min_samples_leaf=2,max_features=0.5)),
              ('GBR',lambda:GradientBoostingRegressor(n_estimators=400,random_state=SEED,max_depth=2,learning_rate=0.03))]:
    r,ma,sd=cv_reg(Xn[iopM],yM[iopM],fn()); print(f'  {nm:6s} R2={r:.3f}(sd{sd:.2f}) MAE={ma:.2f}(log)')

print('\n=== 水煮 classification (chem+ir) ===')
Xc=Xn[iopW]; yw=wB[iopW].astype(int)
for nm,fn in [('LR',lambda:Pipeline([('s',StandardScaler()),('m',LogisticRegression(max_iter=3000))])),
              ('RF',lambda:RandomForestClassifier(n_estimators=500,random_state=SEED,min_samples_leaf=2,class_weight='balanced_subsample')),
              ('GBR',lambda:GradientBoostingClassifier(n_estimators=400,random_state=SEED,max_depth=2,learning_rate=0.05))]:
    ac=[];o1=[]
    for tr,te in RepeatedStratifiedKFold(n_splits=5,n_repeats=10,random_state=SEED).split(Xc,yw):
        m=fn();m.fit(Xc[tr],yw[tr]);p=m.predict(Xc[te]);ac.append(accuracy_score(yw[te],p));o1.append(np.mean(np.abs(yw[te]-p)<=1))
    print(f'  {nm:6s} acc={np.mean(ac):.3f}(sd{np.std(ac):.2f}) +-1off={np.mean(o1):.3f}')