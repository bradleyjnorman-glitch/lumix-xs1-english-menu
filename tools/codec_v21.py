#!/usr/bin/env python3
"""Read-only XS1 v1.1 custom Huffman/LZ decoder, validated across 809 stock frames.
Original stock SHA256 is enforced by stock_parser.py. Does not produce a firmware updater.
"""
import argparse,collections,itertools,json,sys
from pathlib import Path
from stock_parser import load,frames

class BitReader:
 def __init__(self,data,order):
  if order.startswith('reverse4'):data=b''.join(data[i:i+4][::-1] for i in range(0,len(data),4))
  self.data=data;self.total=len(data)*8;self.at=0;self.lsb=order.endswith('lsb')
 def peek(self,n,reverse=False):
  if n<0 or self.at+n>self.total:raise EOFError('stream exhausted')
  v=0
  for i in range(n):
   k=self.at+i;b=self.data[k//8];bit=((b>>(k%8)) if self.lsb else (b>>(7-k%8)))&1
   if reverse:v|=bit<<i
   else:v=v*2+bit
  return v
 def consume(self,n):
  if n<0 or self.at+n>self.total:raise EOFError('consume past input')
  self.at+=n
 def read(self,n,reverse=False):
  x=self.peek(n,reverse);self.consume(n);return x

def read_symbol(t,r,polarity,break_flip,reverse_radix):
 depth=0; node=0; steps=0;control=collections.Counter()
 while steps<40:
  steps+=1;w=t[node];tag=w&3;p=(w>>2)&511;m=(w>>11)&15;hi=w>>15
  if tag==3:return p,m,hi,control
  if tag==0:
   index=r.peek(m,reverse_radix)
   child=p+index
   if child>=len(t):raise ValueError('radix out of table')
   leaf=t[child]
   if leaf&3==3:
    # confirmed 203,052-run relation includes extra_bits in hi and encoded match base.
    extra=((leaf>>11)&15)//2
    consume=hi+(leaf>>15)-extra
    if not (1<=consume<=m):raise ValueError(f'invalid candidate consumed bits {consume}/{m}')
   else:consume=m
   r.consume(consume)
   node=child;control['radix']+=1
  elif tag==1:
   # Candidate two-sided zero/one run code, with polarity/same-bit stop rule.
   side=r.read(1)^polarity
   size=m if side==0 else hi
   index=0
   while index<size-1:
    nxt=r.read(1)
    if nxt==(side^break_flip):break
    index+=1
   node=p+1+(0 if side==0 else m)+index
   if node>=len(t):raise ValueError('linear out of table')
   control['linear']+=1
  else:raise ValueError(f'illegal control tag {tag}')
 raise ValueError('table traversal too deep')

def distbase(sym):
 if sym in (0,1,2,3):return (sym+1,0)
 if sym<6 or (sym-2)%4 not in(0,1):raise ValueError('invalid distance symbol '+str(sym))
 e=(sym-2)//4
 return (1 + (2+sym%2)*(1<<e),e)

def decode(tab1,tab2,stream,expected,order='byte_msb',polarity=0,break_flip=0,reverse_radix=False,extra_reverse=False,cap=None,history=b'',watch=None):
 r=BitReader(stream,order)
 out=bytearray();context=bytearray(history);token_counter=collections.Counter(); prev=[];watch_hits=[]
 max_tokens=cap or expected*2
 for token_index in range(max_tokens):
  try:
   at_start=r.at;out_start=len(out)
   sym,mid,hi,_=read_symbol(tab1,r,polarity,break_flip,reverse_radix)
   token_counter['tokens']+=1
   if sym==256:
    token_counter['end_marker']+=1
    return {'status':'end','out_len':len(out),'expected':expected,'tokens':token_index+1,'at':r.at,
        'padding_bytes':(r.total-r.at+7)//8,'head':out[:24].hex(),'tail':out[-16:].hex(),'counts':dict(token_counter), 'trace':prev,'watch_hits':watch_hits,'bytes':bytes(out)}
   detail={'symbol':sym,'mid':mid}
   if sym<=255 and mid==0:
    out.append(sym);context.append(sym);token_counter['literals']+=1
   elif sym in (3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258):
    e=mid//2
    length=sym+r.read(e,extra_reverse)
    dsym,dm,dhi,_=read_symbol(tab2,r,polarity,break_flip,reverse_radix)
    dbase,de=distbase(dsym)
    dist=dbase+r.read(de,extra_reverse)
    detail.update(length=length,dist=dist,distance_symbol=dsym,distance_extra_bits=de)
    if len(prev)<12:prev.append(('match',token_index,length,dist,dsym,r.at))
    if dist>len(context) or dist<1:raise ValueError(f'bad back-reference dist {dist} at out {len(out)} context {len(context)} token {token_index} after {r.at} bits')
    for _ in range(length):
     b=context[-dist];out.append(b);context.append(b)
    token_counter['matches']+=1;token_counter['expanded_bytes']+=length
   else:raise ValueError(f'bad litlen symbol {sym},mid {mid},hi {hi}')
   if watch is not None and out_start<=watch<len(out):
    watch_hits.append({'token_index':token_index,'out_range':[out_start,len(out)],'bit_range':[at_start,r.at], 'sym':sym, 'kind':'literal' if sym<=255 and mid==0 else 'length_distance', 'value':out[watch], 'detail':detail})
   if len(out)>expected+128:raise ValueError(f'overlong output {len(out)} > expected{expected}')
  except (ValueError,EOFError) as exc:
   return {'status':'error','reason':str(exc),'out_len':len(out),'expected':expected,'tokens':token_index+1,'at':r.at,
           'padding_bytes':(r.total-r.at+7)//8,'head':out[:24].hex(),'counts':dict(token_counter),'trace':prev,'watch_hits':watch_hits,'bytes':bytes(out)}
 return {'status':'cap','out_len':len(out),'tokens':max_tokens,'at':r.at,'head':out[:24].hex(),'counts':dict(token_counter),'trace':prev,'watch_hits':watch_hits,'bytes':bytes(out)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('firmware',type=Path);ap.add_argument('--out',type=Path,default=Path('v21_candidate.json'));args=ap.parse_args()
 src=load(args.firmware);samples={idx:(d,t[0],t[1],stream) for seg,idx,d,t,stream in frames(src) if seg=='elf5_code' and idx in (0,5,220,279)}
 cases={}
 for idx,(d,t1,t2,stream) in samples.items():
  arr=[]
  for order,pol,break_flip,radix_flip,extra_rev in itertools.product(('byte_msb','byte_lsb','reverse4_msb','reverse4_lsb'),(0,1),(0,1),(False,True),(False,True)):
   res=decode(t1,t2,stream,d,order,pol,break_flip,radix_flip,extra_rev)
   cfg={'order':order,'polarity':pol,'break_flip':break_flip,'radix_reverse':radix_flip,'extra_reverse':extra_rev}
   arr.append({**cfg,**res})
  # pick meaningful cases: avoid ranking invalid backrefs as if valid
  arr.sort(key=lambda a:(a['status']!='end' or a['out_len']!=d, a['status']!='end',abs(a['out_len']-d),-a['at']))
  cases[str(idx)]={'expected':d,'stream_bytes':len(stream),'top':arr[:12], 'status_counts':dict(collections.Counter(x['status'] for x in arr))}
  print('FRAME',idx,'expected',d,'status counts',cases[str(idx)]['status_counts'])
  for x in arr[:4]:print(' ',x['status'], x.get('reason',''), 'out',x['out_len'],'at',x['at'],'mode',(x['order'],x['polarity'],x['break_flip'],x['radix_reverse'],x['extra_reverse']),'first',x['head'],'tokens',x['counts'].get('tokens'))
 args.out.write_text(json.dumps({'warning':'EXPERIMENTAL TOKEN DECODER, DO NOT USE AS FIRMWARE','cases':cases},indent=2)+'\n')
