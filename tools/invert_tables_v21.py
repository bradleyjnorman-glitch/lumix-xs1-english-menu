#!/usr/bin/env python3
"""Inverse only of verified XS1 stock Huffman lookup tables (offline)."""
from collections import defaultdict
from codec_v21 import BitReader,read_symbol

def invert(table):
 codes=defaultdict(set)
 stack=[(0,'')]
 while stack:
  idx,prefix=stack.pop()
  if len(prefix)>64:raise ValueError('unexpected long code')
  w=table[idx];tag=w&3;p=(w>>2)&511;m=(w>>11)&15;top=w>>15
  if tag==3:
   codes[(p,m)].add(prefix);continue
  if tag==0:
   for j in range(1<<m):
    ch=table[p+j];bits=format(j,'0'+str(m)+'b') if m else ''
    if ch&3==3:
     ex=((ch>>11)&15)//2
     take=top+(ch>>15)-ex
     assert 1<=take<=m,(idx,hex(w),p+j,hex(ch),take)
     leafsym=(ch>>2)&511;leafmid=(ch>>11)&15
     codes[(leafsym,leafmid)].add(prefix+bits[:take])
    else:stack.append((p+j,prefix+bits))
  elif tag==1:
   for j in range(m):
    bits='0'+('0'*j)+('1' if j<m-1 else '')
    stack.append((p+1+j,prefix+bits))
   for j in range(top):
    bits='1'+('1'*j)+('0' if j<top-1 else '')
    stack.append((p+1+m+j,prefix+bits))
  else:raise ValueError('unexpected')
 return {k:sorted(v,key=lambda x:(len(x),x)) for k,v in codes.items()}

def sample_checks(table):
 codebooks=invert(table)
 mismatches=[]
 for (sym,mid),codes in codebooks.items():
  for code in codes:
   dat=(code+'0'*96);data=int(dat[:(len(dat)//8)*8],2).to_bytes(len(dat)//8,'big')
   br=BitReader(data,'byte_msb')
   out=read_symbol(table,br,0,1,False)
   if (out[0],out[1])!=(sym,mid) or br.at!=len(code):
    mismatches.append((sym,mid,code,out[0],out[1],br.at))
 return codebooks,mismatches
