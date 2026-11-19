#!/usr/bin/env python3
"""Targeted XS1 ELF5 frame3 LZ repair and optional experimental ELF output.
Offline only; writes to a regular file. NEVER interacts with a camera.
"""
import sys,collections,hashlib,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stock_parser import load, frames
from codec_v21 import BitReader, read_symbol, distbase, decode
from invert_tables_v21 import invert

ap=argparse.ArgumentParser(description='Reproduce verified XS1 v25 English patch offline; ELF output only with explicit --firmware-output')
ap.add_argument('firmware',type=Path,help='original unmodified stock XS1_110S.elf or official ZIP')
ap.add_argument('manifest',type=Path,help='v21 stock decode_manifest.json')
ap.add_argument('--out',type=Path,default=Path('xs1_v25_patch_validation.json'),help='JSON report')
ap.add_argument('--firmware-output',type=Path,help='Opt-in: write validated experimental modified ELF file (DANGEROUS TO FLASH)')
args=ap.parse_args()
fw=load(args.firmware)
allfr=[(i,n,t1,t2,stream) for seg,i,n,(t1,t2),stream in frames(fw) if seg=='elf5_code' and i<=3]
hist=b''
for i,n,t1,t2,stream in allfr[:-1]:
 r=decode(t1,t2,stream,n,polarity=0,break_flip=1,history=hist)
 assert r['status']=='end' and r['out_len']==n
 hist=(hist+r['bytes'])[-32768:]
frame,n,t1,t2,stream=allfr[-1]
data_n=n
assert frame==3
baseline=decode(t1,t2,stream,n,polarity=0,break_flip=1,history=hist)
assert baseline['status']=='end' and baseline['out_len']==n
expected=baseline['bytes']
bs=''.join(f'{v:08b}' for v in stream)
lc=invert(t1);dc=invert(t2)

def matches_at_distance(context, target, dist):
 if dist<1 or dist>len(context):return False
 if dist>=len(target):return context[-dist:-dist+len(target)]==target if dist!=len(target) else context[-dist:]==target
 for j,b in enumerate(target):
  if b != (context[-dist+j] if j<dist else target[j-dist]):return False
 return True

# Lookup available distance interval encoding choices.
dist_enc={}
for (sym,mid),codes in dc.items():
 try:base,extra=distbase(sym)
 except ValueError:continue
 for delta in range(1<<extra):
  d=base+delta
  code=codes[0]+(format(delta,f'0{extra}b') if extra else '')
  if d not in dist_enc or len(code)<len(dist_enc[d]):dist_enc[d]=code


# Encode actual length bases and extra bits using the existing stock VLC book.
MATCH_BASES=(3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258)
len_enc={}
for (sym,mid),codes in lc.items():
 if sym not in MATCH_BASES:continue
 ex=mid//2
 for delta in range(1<<ex):
  length=sym+delta
  if length<3 or length>258:continue
  code=codes[0]+(format(delta,f'0{ex}b') if ex else '')
  if length not in len_enc or len(code)<len(len_enc[length]):len_enc[length]=code

def encode_fragment(context, target, old_dist):
  """Min-bit dynamic programming for only a damaged original match, no full recompression."""
  target=bytes(target);ctx=bytes(context);N=len(target)
  dp=[(10**12,None)]*(N+1);dp[N]=(0,None)
  for pos in range(N-1,-1,-1):
    b=target[pos];literal=lc.get((b,0),[])
    if literal: dp[pos]=(len(literal[0])+dp[pos+1][0],('literal',1,literal[0]))
    prefix=target[pos:pos+min(N-pos,4)]
    # Consider all short distances, original distance and any nearby 3-byte source match.
    candidates=set(range(1,min(96,len(ctx)+pos)+1));candidates.add(old_dist)
    avail=min(32768,len(ctx)+pos)
    hay=(ctx+target[:pos])[-avail:]
    if len(prefix)>=3:
      q=prefix[:3];at=hay.find(q);hits=[]
      while at>=0:
        d=avail-at
        if d in dist_enc:hits.append(d)
        at=hay.find(q,at+1)
      hits.sort(key=lambda d:(len(dist_enc[d]),d))
      candidates.update(hits[:40])
    for dist in candidates:
      if dist not in dist_enc or dist>avail:continue
      # Candidate match output may overlap its own newly copied bytes.
      maxmatch=0
      while pos+maxmatch<N:
        j=maxmatch
        if j<dist: source=hay[-dist+j]
        else:source=target[pos+j-dist]
        if source != target[pos+j]:break
        maxmatch+=1
      if maxmatch<3:continue
      dbits=dist_enc[dist]
      for size in range(3,maxmatch+1):
        lbits=len_enc.get(size)
        if not lbits:continue
        cost=len(lbits)+len(dbits)+dp[pos+size][0]
        if cost<dp[pos][0]:dp[pos]=(cost,('match',size,lbits+dbits))
    if dp[pos][1] is None:raise RuntimeError(f'cannot encode fragment pos{pos} byte{b}')
  pos=0;bits=[]
  while pos<N:
    kind,size,code=dp[pos][1];bits.append(code);pos+=size
  return ''.join(bits)

r=BitReader(stream,'byte_msb')
newout=bytearray(); newparts=[]; repairs=[];original_tokens=0
while True:
 at=r.at;out_start=len(newout)
 sym,mid,hi,_=read_symbol(t1,r,0,1,False)
 if sym==256:
  newparts.append(bs[at:r.at]);break
 if sym<=255 and mid==0:
  newout.append(sym);newparts.append(bs[at:r.at])
 else:
  extra=mid//2
  length=sym+r.read(extra)
  distbegin=r.at
  dsym,_,_,_=read_symbol(t2,r,0,1,False)
  base,de=distbase(dsym)
  dist=base+r.read(de)
  segment=expected[out_start:out_start+length]
  oldbits=bs[at:r.at]
  if out_start==4324:
   assert length==9 and dist==1
   # previously tested 9-byte match = four zeroes + one English bit + four zeroes.
   code=lambda table,s,m:table[(s,m)][0]
   newbits=code(lc,4,1)+code(dc,0,0)+code(lc,1,0)+code(lc,4,1)+code(dc,6,0)+'0'
   thisout=bytearray(segment);thisout[4328-out_start]=1
   assert len(newbits)==33
   newparts.append(newbits)
   newout.extend(thisout)
   repairs.append({'offset':out_start,'reason':'English bit','old_dist':dist,'new_dist':None,'bit_delta':len(newbits)-len(oldbits)})
  else:
   ctx=hist+newout
   # Simulate the original LZ match in the already-modified history.
   copyctx=bytearray(ctx);sim=bytearray()
   for _ in range(length):
    q=copyctx[-dist];copyctx.append(q);sim.append(q)
   if sim == segment:
    newout.extend(segment);newparts.append(oldbits)
   else:
    # Search for a same-length match to the exact desired bytes anywhere in the 32K history.
    avail=min(32768,len(ctx));candidates=[]
    # Nonoverlapping matches: use C-accelerated substring search.
    target=bytes(segment);cbytes=bytes(ctx)
    # limit window to last 32768 before output position
    hay=cbytes[-avail:]
    idx=hay.find(target)
    while idx!=-1:
     d=avail-idx
     if d in dist_enc:candidates.append((len(dist_enc[d]),d))
     idx=hay.find(target,idx+1)
    for d in range(1,min(avail,length-1)+1):
     if d in dist_enc and matches_at_distance(ctx,target,d):candidates.append((len(dist_enc[d]),d))
    if candidates:
     _,chosen=min(candidates)
     newbits=bs[at:distbegin]+dist_enc[chosen]
     method='redirect distance '+str(chosen)
    else:
     newbits=encode_fragment(ctx,segment,dist)
     chosen=None
     method='re-encode damaged match'
    newparts.append(newbits)
    newout.extend(segment)
    repairs.append({'offset':out_start,'length':length,'original_dist':dist,'replacement_dist':chosen,'method':method,'bit_delta':len(newbits)-len(oldbits)})
 original_tokens+=1
 assert len(newout)<=n
assert len(newout)==n
wanted=bytearray(expected);wanted[4328]=1
assert newout==wanted,(len(newout),sum(x!=y for x,y in zip(newout,wanted)))
newbits=''.join(newparts)
print('repairs',len(repairs),'bits orig len',r.at,'bits new len',len(newbits),'old capacity',len(bs),'unused',len(bs)-len(newbits))
print('repair records',repairs[:80])
if len(newbits)>len(bs):raise RuntimeError(f'ENCODED BIT OVERFLOW by {len(newbits)-len(bs)} bits')
newbits=newbits.ljust(len(bs),'0')
patchedstream=int(newbits,2).to_bytes(len(stream),'big')
proof=decode(t1,t2,patchedstream,n,polarity=0,break_flip=1,history=hist)
print('decoded',proof['status'],'len',proof['out_len'],'unused',proof['padding_bytes'])
assert proof['status']=='end' and proof['out_len']==n
actual=proof['bytes'];diff=[i for i,(x,y) in enumerate(zip(actual,expected)) if x!=y]
print('diff',diff[:60],'count',len(diff))
assert diff==[4328] and actual[4328]==1
print('SUCCESS: exact-one-byte difference in frame3, no changed bytes elsewhere in frame3')

# Package integrity/decoder equivalence proof stays in RAM; NEVER save firmware.
import json,struct
from stock_parser import SEGMENTS,frames
elf5_base=[base for seg,base,size,total in SEGMENTS if seg=='elf5_code'][0]
at=elf5_base
for j in range(4):
 mode,decoded,padded,t1size,t2size=struct.unpack_from('<IIIHH',fw,at)
 if j==3:
  stream_off=at+16+t1size+t2size
  assert fw[stream_off:stream_off+padded]==stream
  assert padded==len(patchedstream)
  break
 at+=16+padded+t1size+t2size
candidate=bytearray(fw)
candidate[stream_off:stream_off+len(stream)]=patchedstream
file_byte_diff=sum(a!=b for a,b in zip(fw,candidate))
assert len(candidate)==len(fw)
print('IN-MEMORY candidate compressed stream offset',hex(stream_off),'modified compressed bytes',file_byte_diff)

# A back-reference can only see 32,768 previous bytes; the exact one-byte
# change falls outside the frame's outgoing history window.
original_history=(hist+baseline['bytes'])[-32768:]
patched_history=(hist+proof['bytes'])[-32768:]
assert patched_history==original_history
print('PASS: the next frame receives the exact same 32,768-byte history')

# Verify that each input and table in the other 808 frames is bit-identical.
# This, plus identical history and deterministic decoding, proves their outputs
# remain identical, without spending minutes doing a redundant Python decode.
manifest=json.loads(args.manifest.read_text())
records={(rec['seg'],rec['frame']):rec for rec in manifest['frames']}
changed_frames=[];frame_count=0
for old,new in zip(frames(fw),frames(candidate)):
 seg,i,decoded,tables,stream0=old
 seg1,i1,decoded1,tables1,stream1=new
 assert (seg,i,decoded,tables)==(seg1,i1,decoded1,tables1)
 assert (seg,i) in records and records[(seg,i)]['decoded']==decoded
 if stream0!=stream1:
  changed_frames.append((seg,i))
 assert (seg,i)==('elf5_code',3) or stream0==stream1
 frame_count+=1
assert frame_count==809 and changed_frames==[('elf5_code',3)]
print('PASS: all 809 compressed frame headers/tables checked; 808 unchanged streams')

# Additional independent witness: decode the first following frame using the
# corrected frame's outgoing LZ history and compare to the v21 stock hash.
nextframe=next((n,tab,stream4) for seg,i,n,tab,stream4 in frames(candidate) if (seg,i)==('elf5_code',4))
n4,tab,stream4=nextframe
following=decode(tab[0],tab[1],stream4,n4,polarity=0,break_flip=1,history=patched_history)
assert following['status']=='end' and following['out_len']==n4
assert hashlib.sha256(following['bytes']).hexdigest()==records[('elf5_code',4)]['output_sha256']
print('PASS: independent frame4 decoder witness matches original SHA256')

# Negative control: change a bit inside patched frame and demand a mismatch.
corrupted=bytearray(patchedstream);corrupted[100]^=0x80
negative=decode(t1,t2,bytes(corrupted),data_n,polarity=0,break_flip=1,history=hist)
assert negative['status']!='end' or negative['bytes']!=proof['bytes']
print('PASS: corrupted compressed stream detected')

vold=bytes(candidate[0x200084:0x200086]);candidate[0x200084:0x200086]=bytes.fromhex('0114')
assert vold==bytes.fromhex('0113')
result={'phase':'v25','stock_firmware_sha256':hashlib.sha256(fw).hexdigest(),
  'candidate_sha256_in_memory_only':hashlib.sha256(candidate).hexdigest(),
  'target_frame':{'segment':'elf5_code','index':3,'stream_file_offset':hex(stream_off),
    'original_stream_size':len(stream),'patched_stream_size':len(patchedstream),
    'packed_bytes_changed':file_byte_diff,'decoded_bytes_changed':[4328],
    'decoded_target_runtime':'0x804f3724','target_before':0,'target_after':1,
    'unused_padded_bytes':proof['padding_bytes'],'token_repairs':repairs},
  'frame_structure_checks':frame_count,'changed_compressed_frames':changed_frames,
  'outgoing_32768_byte_LZ_history_preserved':True,
  'following_frame4_stock_output_sha256_verified':True,
  'bit_flip_negative_control_rejected':True,
  'version_field':{'file_offset':'0x200084','stock_be':vold.hex(),
       'candidate_be':'0114','meaning':'passes one version comparison ONLY; not installation approval'},
  'output':'Exact firmware candidate physically tested on one Japanese DMC-XS1; other cameras untested'}
args.out.write_text(json.dumps(result,indent=2)+'\n')
print('SUCCESS: single decoded-byte patch, all frame structures validated, no later-frame change possible')

if args.firmware_output:
    assert hashlib.sha256(candidate).hexdigest()=='d4ccf2473d498901015cdbc89dd6f59affa821ea50a649af3dad2128fea3316c', 'Not identical to v22 audited candidate'
    assert args.firmware_output.resolve()!=args.firmware.resolve(), 'Refusing overwrite stock'
    args.firmware_output.parent.mkdir(parents=True,exist_ok=True)
    args.firmware_output.write_bytes(candidate)
    print('EXPERIMENTAL CANDIDATE WRITTEN:',args.firmware_output)
