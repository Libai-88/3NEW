# -*- coding: utf-8 -*-
"""External generalization validation v2 with proper RDKit chemical descriptors.

Dataset: PolySol homopolymer solubility (1,818 real polymer-solvent pairs).
Task: classify solubility (1/0). Direct analog of MEK solvent-resistance + water-boil.
Features: monomer descriptors + solvent descriptors + MACCS/Morgan fingerprints
          and Monomer\xd7Solvent interaction (product) rows.
Protocols:
  A) RepeatedStratifiedKFold random split -> optimistic upper bound (allows leakage)
  B) GroupKFold by polymer -> TRUE generalization to never-seen polymers
  C) GroupKFold by monomer-class (implicitly grouped by chemistry type)
"""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from rdkit import Chem
from rdkit.Chem import Descriptors, MACCSkeys, AllChem, rdFingerprintGenerator
from rdkit.Chem import DataStructs
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, GradientBoostingClassifier
from sklearn.model_selection import GroupKFold, RepeatedStratifiedKFold
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
SEED=0

# ---------- featurization ----------
_desc_names = [n for n in Descriptors._descList]
def mol_desc(mol):
    out=[]
    for name,_ in _desc_names[:60]:  # robust subset to avoid 3D/Stereo failures
        try: out.append(getattr(Descriptors,name)(mol))
        except Exception: out.append(np.nan)
    return np.nan_to_num(np.array(out),nan=0.0)

def get_fp(mol,kind='morgan'):
    if kind=='morgan':
        fp=AllChem.GetMorganFingerprintAsBitVect(mol,2,nBits=2048)
    else:
        fp=MACCSkeys.GenMACCSKeys(mol)
    arr=np.zeros((1,),dtype=np.float64); DataStructs.ConvertToNumpyArray(fp,arr)
    return arr
def get_morgan_arr(mol,nBits=2048):
    fp=AllChem.GetMorganFingerprintAsBitVect(mol,2,nBits=nBits)
    a=np.zeros((2048,),dtype=np.float64); DataStructs.ConvertToNumpyArray(fp,a); return a

def featurize(smiles_list):
    ds=[]; fr=[]
    for sm in smiles_list:
        mol=Chem.MolFromSmiles(sm)
        if mol is None:
            ds.append(np.zeros(60)); fr.append(np.zeros(2048)); continue
        ds.append(mol_desc(mol)); fr.append(get_morgan_arr(mol))
    D=np.vstack(ds); F=np.vstack(fr)
    # constant-waste col filter
    keepD=[j for j in range(D.shape[1]) if np.nanstd(D[:,j])>1e-9]
    keepF=[j for j in range(F.shape[1]) if F[:,j].sum()>0]
    return D[:,keepD], F[:,keepF]

def main():
    df=pd.read_csv('polysol_homopolymer.csv',sep=';')
    y=df['solvent_characteristic'].values.astype(int)
    print('PolySol:',len(df),'pos',(y==1).sum(),'neg',(y==0).sum(),flush=True)
    # de-dup SMILES
    us=set(df['mono_smiles']).union(set(df['solvent_smiles']))
    us=[s for s in us if isinstance(s,str) and s]
    uf=featurize(us)
    sm_to_mor={s:uf[1][i] for i,s in enumerate(us)}
    sm_to_desc={s:uf[0][i] for i,s in enumerate(us)}
    # build joint sample matrix
    Dm=np.vstack([sm_to_desc.get(s,np.zeros(uf[0].shape[1])) for s in df['mono_smiles']])
    Fm=np.vstack([sm_to_mor.get(s,np.zeros(uf[1].shape[1])) for s in df['mono_smiles']])
    Ds=np.vstack([sm_to_desc.get(s,np.zeros(uf[0].shape[1])) for s in df['solvent_smiles']])
    Fs=np.vstack([sm_to_mor.get(s,np.zeros(uf[1].shape[1])) for s in df['solvent_smiles']])
    X=np.hstack([Dm,Ds,Dm*Ds,Fm,Fs])
    print('X dim:',X.shape[1],flush=True)
    polys=df['polymer'].values; groups=np.unique(polys,return_inverse=True)[1]

    def run(name,model,X,y,groups=None,kw_model=None):
        if groups is None:
            acc=[];auc=[]
            for tr,te in RepeatedStratifiedKFold(n_splits=5,n_repeats=3,random_state=SEED).split(X,y):
                m=kw_model()
                m.fit(X[tr],y[tr]); p=m.predict(X[te])
                acc.append(accuracy_score(y[te],p))
                if len(np.unique(y[te]))>1: auc.append(roc_auc_score(y[te],m.predict_proba(X[te])[:,1]))
            print(f'  {name:7s} randomCV acc={np.mean(acc):.3f} auc={np.mean(auc):.3f}',flush=True)
        else:
            acc=[];gk=GroupKFold(n_splits=5)
            for tr,te in gk.split(X,y,groups):
                m=kw_model()
                m.fit(X[tr],y[tr]); p=m.predict(X[te])
                acc.append(accuracy_score(y[te],p))
            print(f'  {name:7s} GroupK(poly) acc={np.mean(acc):.3f} (std {np.std(acc):.3f})',flush=True)

    def LR(): return LogisticRegression(max_iter=3000)
    def RFb(): return RandomForestClassifier(n_estimators=300,random_state=SEED,min_samples_leaf=2,n_jobs=-1)
    def ETb(): return ExtraTreesClassifier(n_estimators=300,random_state=SEED,min_samples_leaf=2,n_jobs=-1)

    print('\n=== A) random split 5x3 CV (upper bound) ===',flush=True)
    for nm,fn in [('LogReg',LR),('RF',RFb)]:
        run(nm,None,X,y,None,kw_model=fn)

    print('\n=== B) GroupKFold by polymer (true unseen generalization) ===',flush=True)
    for nm,fn in [('LogReg',LR),('RF',RFb),('ET',ETb)]:
        run(nm,None,X,y,groups,kw_model=fn)

if __name__=='__main__': main()