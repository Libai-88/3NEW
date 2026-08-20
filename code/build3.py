# -*- coding: utf-8 -*-
"""build3: raw-amount aligned features (signal-preserving) across O+N.
Chemical-consistent units: PAeff (effective acid), epoxy_eff, raw amounts for
comparable components. Tests the pivotal orig->new generalization.
"""
import pickle, os
import numpy as np, pandas as pd, glob

OUT='../data'
d726='../data/uploads/40438680-5bc2-4054-b4c1-81a2b7a0f6f6_7.26配料测试汇总(2).xlsx'
d86 ='../data/uploads/acc88872-1e81-437a-b4cf-bc6fdf92809c_8.6配料测试汇总.xlsx'
dnew='../data/uploads/b416a109-b9d3-4009-b344-4edeab283499_新100组机器学习数据集.csv'

CMPS=['IR190(9型环氧树脂36%固含）','RF401(PR401)','RF160(PR33160G)','IR809 55%(PR309 稀释55%)',
 'RF516（PR516）','RF950（PR8219-50）','RF956（PR8219-65）','RH601（SM601RX75)','住友55754G',
 '1510蜡25%工作液','AZ088（BYK088)','外加正丁醇','补加混合液（乙二醇单丁醚：二甲苯=2:1）','10%磷酸']
CNAME=['IR190','RF401','RF160','IR809','RF516','RF950','RF956','RH601','S55754','W1510','AZ088','nBtOH','Mix','PA']
frames=[]
for fn,sheet,b,temp,minu in [(d726,'Sheet1','7.26',200,10),(d86,'8.6配料测试汇总','8.6',205,17)]:
    df=pd.read_excel(fn,sheet_name=sheet); df=df.iloc[1:].reset_index(drop=True)
    df['batch']=b; df['bake_temp']=temp; df['bake_min']=minu; frames.append(df)
Do=pd.concat(frames,ignore_index=True)
Xo=Do[CMPS].apply(pd.to_numeric,errors='coerce').fillna(0.0).astype(float); Xo.columns=CNAME
def num(s):
    out=pd.to_numeric(s,errors='coerce'); plus=s.astype(str).str.strip().str.replace(r'\+$','',regex=True)
    out2=pd.to_numeric(plus,errors='coerce'); return np.where(np.isnan(out)&~np.isnan(out2),out2,out)
yT_o=np.asarray(num(Do['T弯(mm)']),dtype=float); mek_o=np.asarray(num(Do['MEK擦拭(次)']),dtype=float)
cens_o=(Do['MEK擦拭(次)'].astype(str).str.strip().str.contains(r'\+',na=False)).values
yM_o=np.log1p(mek_o)   # preserve NaN for missing
wB_o=np.asarray(num(Do['水煮（等级）']),dtype=float)
batch_o=Do['batch'].values; fam_o=batch_o+'_'+Do['配方ID'].astype(str).str.split('-').str[0].astype(str)

Dn=pd.read_csv(dnew)
def Xcol(src): return pd.to_numeric(Dn[src],errors='coerce').fillna(0).values
Xn=pd.DataFrame()
Xn['IR190']=Xcol('9型环氧树脂'); Xn['RF401']=Xcol('PR401'); Xn['RF160']=Xcol('PR-33160G')
Xn['IR809']=Xcol('PR309')        # new PR309: treat as effective -> scale to 55% stock (IR809=PR309/0.55)
Xn['IR809']=Xn['IR809']/0.55
Xn['RF516']=Xcol('PR516'); Xn['RF950']=Xcol('RF950_50%'); Xn['RF956']=Xcol('RF956_60%')
Xn['RH601']=Xcol('SM601RX75'); Xn['S55754']=Xcol('住友_55754G'); Xn['W1510']=Xcol('1510')
Xn['AZ088']=Xcol('BYK-088'); Xn['PR411']=Xcol('Allnex_PR-411'); Xn['TF022']=Xcol('TF022')
Xn['PAeff']=Xcol('85%磷酸')*0.85
Xn['nBtOH']=Xcol('正丁醇_2'); Xn['Mix']=0.0
yT_n=pd.to_numeric(Dn['T弯'],errors='coerce').values; mek_n=pd.to_numeric(Dn['MEK擦拭'],errors='coerce').values
yM_n=np.log1p(mek_n)
cens_n=np.zeros(len(Dn),bool)
wB_n=pd.to_numeric(Dn['水煮'],errors='coerce').values
batch_n=np.array(['new']*len(Dn)); fam_n=np.array(['new_%02d'%i for i in range(len(Dn))])

# -------- common raw schema + feature builder --------
COMMON=['IR190','RF401','RF160','IR809','RF516','RF950','RF956','RH601','S55754','W1510','AZ088','PR411','TF022','nBtOH','Mix']
def build_raw_o():
    X=pd.DataFrame(0.0,index=np.arange(len(Xo)),columns=COMMON)
    for c in CNAME[:-1]: X[c]=Xo[c].values
    return X, Xo['PA'].values*0.10
def build_raw_n():
    X=Xn[COMMON].copy()
    return X, Xn['PAeff'].values   # new: 85%磷酸 already *0.85 => PAeff
RAW_o,PAo=build_raw_o()
RAW_n,PAn=build_raw_n()
def feats(X_sub,PAeff,bake,use_inter=False):
    A=X_sub.values.astype(float); cols=list(X_sub.columns)
    epi=cols.index('IR190'); ep=A[:,epi]; epeff=ep*0.36
    tot=A.sum(axis=1)+PAeff
    Radd=tot-A[:,epi]; acid_ep=PAeff/np.maximum(epeff,1e-9)
    out=[A.copy(),
         (PAeff/np.maximum(tot,1e-9))[:,None],
         epeff[:,None],
         (Radd/tot)[:,None],
         acid_ep[:,None]]
    if use_inter:
        xk={c:cols.index(c) for c in ['RF160','RF516','RF950','RF956','RH601']}
        xn=list(xk.keys())
        for a in range(len(xn)):
            for b in range(a+1,len(xn)):
                i,j=xk[xn[a]],xk[xn[b]]
                out.append((A[:,i]*A[:,j]/np.maximum(tot,1e-9))[:,None])
    if bake is not None: out.append(bake)
    return np.hstack(out)
bo=np.hstack([np.hstack([Do['bake_temp'].values[:,None],Do['bake_min'].values[:,None]]),
              (Do['bake_temp'].values*Do['bake_min'].values)[:,None],np.sqrt(Do['bake_min'].values)[:,None]])
bn=np.hstack([np.zeros((len(Dn),2))+np.array([[200.0,10.0]]), np.full((len(Dn),1),2000.0), np.full((len(Dn),1),np.sqrt(10.0))])
Xo_f=feats(RAW_o,PAo,bo)
Xn_f=feats(RAW_n,PAn,bn)
Xn_f_b=feats(RAW_n,PAn,bn,use_inter=True); Xo_f_b=feats(RAW_o,PAo,bo,use_inter=True)

np.savez(OUT+'/master3.npz', Xo=Xo_f, Xn=Xn_f, Xo_b=Xo_f_b, Xn_b=Xn_f_b,
  yT_o=yT_o,yT_n=yT_n,yM_o=yM_o,yM_n=yM_n,mek_o=mek_o,mek_n=mek_n,cens_o=cens_o,cens_n=cens_n,
  wB_o=wB_o,wB_n=wB_n,batch_o=batch_o,batch_n=batch_n,fam_o=fam_o,fam_n=fam_n)
No=Xo_f.shape[1]; print('nfeatures=',No,'inter=',Xo_f_b.shape[1])