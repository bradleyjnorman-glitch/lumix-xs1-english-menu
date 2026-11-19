#!/usr/bin/env python3
"""Verified Panasonic XS1 v1.1 firmware loader and VLC frame parser.

Rejects all input images except the exact original Panasonic SHA-256.
"""
import argparse, hashlib, io, json, struct, zipfile, random
from collections import Counter
from pathlib import Path

EXPECTED='5c1324098d4e456764eae117e31c5b007ea4efafb4a38fed6b5f82d4356f354b'
SEGMENTS=[
 ('elf3_code',0x003c0314,0x001512d4,0x001dcd00),
 ('elf4_code',0x0051163c,0x000c2978,0x0013d180),
 ('elf5_code',0x005d4028,0x006b79a0,0x00d81b80),
 ('elf5_data',0x00c8b9c8,0x0001a480,0x00035e00),
]

def load(p):
 b=Path(p).read_bytes()
 if zipfile.is_zipfile(io.BytesIO(b)):
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   names=[n for n in z.namelist() if n.rsplit('/',1)[-1].lower()=='xs1_110s.elf']
   if len(names)!=1:raise ValueError('expected one XS1_110S.elf inside ZIP')
   b=z.read(names[0])
 if hashlib.sha256(b).hexdigest()!=EXPECTED:
  raise ValueError('stock firmware SHA-256 mismatch; refusing to analyse')
 return b

def frames(b):
 for seg,base,size,expected_output in SEGMENTS:
  at=base;end=base+size;index=0;outtotal=0
  while at<end:
   if at+16>end:raise ValueError('short frame header')
   mode,decoded,padded,t1,t2=struct.unpack_from('<IIIHH',b,at)
   total=16+padded+t1+t2
   if mode!=2 or decoded<=0 or padded%128 or t1%4 or t2%4 or total<=16 or at+total>end:
    raise ValueError(f'invalid frame {seg} {index}')
   codebooks=[]
   for off,num in ((at+16,t1//4),(at+16+t1,t2//4)):
    codebooks.append(struct.unpack_from(f'<{num}I',b,off))
   yield seg,index,decoded,codebooks,b[at+16+t1+t2:at+total]
   at+=total;index+=1;outtotal+=decoded
  if at!=end or outtotal!=expected_output:raise ValueError('segment totals mismatch')

def candidate_tokens(tab,stream,bit_order,unary_bit,max_tokens=25000):
 # Deliberately simplified candidate: flag 0 = h-bit index, flag 1 = unary run,
 # flag 3 = symbol. No LZ distance/backref support. Used ONLY as negative control.
 bits=[]
 for v in stream:
  bits.extend((v>>k)&1 for k in (range(7,-1,-1) if bit_order=='MSB' else range(8)))
 at=0;output=[]
 for _ in range(max_tokens):
  index=0
  for _ in range(32):
   if index>=len(tab):return output,at,'out_of_table'
   w=tab[index];flag=w&3
   if flag==3:
    sym=(w>>2)&511;output.append(sym)
    if sym==256:return output,at,'candidate_256'
    break
   base=(w&0x7ff)>>2;depth=w>>15
   if flag==0:
    if at+depth>len(bits):return output,at,'input_exhausted'
    v=0
    for z in range(depth):
     if bit_order=='MSB':v=(v<<1)|bits[at]
     else:v|=bits[at]<<z
     at+=1
    index=base+v
   elif flag==1:
    count=0
    while count<depth:
     if at>=len(bits):return output,at,'input_exhausted'
     bit=bits[at];at+=1
     if bit!=unary_bit:break
     count+=1
    index=base+1+count
   else:return output,at,'unknown_record'
  else:return output,at,'too_many_branch_steps'
 return output,at,'token_cap'

def audit(b):
 total_frames=0;tables=0;entries=0;controls=0;terminal=0
 tags=Counter();root_records=Counter();forward=0;self_refs=[]
 invalid_refs=[];ctrl_by_table=Counter();marker256=0
 tag0_power_window_valid=0;tag1_linear_window_valid=0;tag1_power_window_invalid=0
 shuffled_controls=0;shuffled_forward=0;rng=random.Random(1818)
 target=None;smallest=None
 for seg,idx,expected,(t1,t2),stream in frames(b):
  total_frames+=1
  for codebook_i,tab in enumerate((t1,t2)):
   tables+=1;entries+=len(tab)
   shuffled=list(tab);rng.shuffle(shuffled)
   for j,w in enumerate(shuffled):
    if w&3!=3:
     shuffled_controls+=1
     if ((w&0x7ff)>>2)>j:shuffled_forward+=1
   if len(tab)<1:raise ValueError('empty codebook')
   ctrl_in_this=0
   for j,w in enumerate(tab):
    flag=w&3;tags[flag]+=1
    if flag==3:
     terminal+=1
     if codebook_i==0 and ((w>>2)&511)==256:marker256+=1
     continue
    controls+=1;ctrl_in_this+=1
    target_ix=(w&0x7ff)>>2
    if target_ix>=len(tab):invalid_refs.append((seg,idx,codebook_i,j,hex(w),target_ix,len(tab)))
    width=w>>15
    if flag==0 and target_ix+(1<<width)<=len(tab):tag0_power_window_valid+=1
    if flag==1 and target_ix+width+1<=len(tab):tag1_linear_window_valid+=1
    if flag==1 and target_ix+(1<<width)>len(tab):tag1_power_window_invalid+=1
    if target_ix>j:forward+=1
    else:self_refs.append((seg,idx,codebook_i,j,hex(w),target_ix))
    if j==0:root_records[(codebook_i,flag,w>>15)]+=1
   ctrl_by_table[(codebook_i,ctrl_in_this)]+=1
  if seg=='elf5_code' and idx==279:target=(expected,t1,t2,stream)
  if seg=='elf5_code' and idx==5:smallest=(expected,t1,t2,stream)
 if invalid_refs:raise ValueError(f'control ref out of range: {invalid_refs[0]}')
 # Keep stage-one probe constrained to 2 bits orders x 2 possible unary polarities.
 negative=[]
 for idx,frame in ((5,smallest),(279,target)):
  expected,t1,t2,stream=frame
  for order in ('MSB','LSB'):
   for unarybit in (0,1):
    tok,at,status=candidate_tokens(t1,stream,order,unarybit)
    at_addr=0x208c if idx==279 else None
    at_target=tok[at_addr:at_addr+16] if at_addr is not None else []
    negative.append(dict(frame=idx,bit_order=order,unary_bit=unarybit,
       candidate_tokens=len(tok),expected_output_bytes=expected,
       consumed_bits=at,input_bits=len(stream)*8,status=status,
       first_12_symbols=tok[:12],language_check_candidate_bytes=at_target))
 return dict(source_sha256=EXPECTED,frame_count=total_frames,codebook_count=tables,
     table_word_count=entries,record_low_bits=dict(tags),
     candidate_terminal_count=terminal,candidate_control_count=controls,
     candidate_control_refs_in_bounds=controls-len(invalid_refs),
     candidate_control_refs_forward=forward,
     control_refs_forward_after_fixed_seed_table_shuffle=shuffled_forward,
     shuffled_control_count=shuffled_controls,
     flag0_power_of_two_window_fits=tag0_power_window_valid,
     flag1_linear_window_fits=tag1_linear_window_valid,
     flag1_power_of_two_window_fails=tag1_power_window_invalid,
     nonforward_control_records=len(self_refs),
     nonforward_records_by_type={
       'table_root':sum(j==0 for _,_,_,j,_,_ in self_refs),
       'nonroot':sum(j>0 for _,_,_,j,_,_ in self_refs)},
     nonroot_exception=[dict(segment=s,frame=i,table=t,index=j,word=w,candidate_reference=p)
                        for s,i,t,j,w,p in self_refs if j>0],
     candidate_256_leaf_count=marker256,
     root_codebook_control_forms=[dict(table=t,flag=f,high_value=h,count=n)
       for (t,f,h),n in sorted(root_records.items())],
     small_table_elf5_frame5=[f'0x{x:08x}' for x in smallest[2]],
     candidate_decode_negative_controls=negative,
     verdict='TABLE CONTROL REFERENCE INVARIANT VERIFIED; DECODER UNPROVEN; NO VALID APPLICATION OUTPUT')

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('firmware',type=Path)
 ap.add_argument('--out',type=Path,default=Path('xs1_v18_results.json'))
 args=ap.parse_args()
 result=audit(load(args.firmware));args.out.write_text(json.dumps(result,indent=2)+'\n')
 print('total frames:',result['frame_count'], 'controls:',result['candidate_control_count'])
 print('candidate control refs in bounds:',result['candidate_control_refs_in_bounds'])
 print('candidate control refs forward:',result['candidate_control_refs_forward'])
 print('non-root exception:',result['nonroot_exception'])
 print(result['verdict'])

if __name__=='__main__':main()
