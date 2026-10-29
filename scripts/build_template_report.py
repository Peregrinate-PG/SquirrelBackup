#!/usr/bin/env python3
"""Patch the school's retained DOCX template while preserving opaque package parts."""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);args=a.parse_args()
template=ROOT/'resources/实验报告模板.docx'
assert hashlib.sha256(template.read_bytes()).hexdigest()=='3323e15ccfa3445483575fd6b77a1606c8b7c64cbdc30cca69cdea858913a2e0'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS={'w':W,'r':R,'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','a':'http://schemas.openxmlformats.org/drawingml/2006/main','pic':'http://schemas.openxmlformats.org/drawingml/2006/picture'}
def tag(k):return '{'+W+'}'+k
def q(k):return tag(k)
def child(parent,k,**attrs):
 v=parent.find(q(k))
 if v is None:v=E.SubElement(parent,q(k))
 for key,val in attrs.items():v.set(q(key),str(val))
 return v
z=ZipFile(template);parts={n:z.read(n) for n in z.namelist()}
xml=E.fromstring(parts['word/document.xml']);body=xml.find('w:body',NS);outer=body.find('w:tbl',NS);rows=outer.findall('w:tr',NS)
original_sect=E.tostring(body.find('w:sectPr',NS))
def cell(i,j=0):return rows[i].findall('w:tc',NS)[j]
body_p=copy.deepcopy(cell(6).findall('w:p',NS)[1]);h1_p=copy.deepcopy(cell(10).findall('w:p',NS)[1]);h2_p=copy.deepcopy(cell(10).findall('w:p',NS)[4]);title_p=copy.deepcopy(cell(10).findall('w:p',NS)[0]);field_p=copy.deepcopy(cell(1).find('w:p',NS));section_p=copy.deepcopy(cell(13).find('w:p',NS))
inner=copy.deepcopy(cell(10).find('w:tbl',NS))
image_p=copy.deepcopy(xml.xpath('//w:p[w:r/w:drawing]',namespaces=NS)[0])
rel=E.fromstring(parts['word/_rels/document.xml.rels']);ct=E.fromstring(parts['[Content_Types].xml']);additions={};image_id=5000
input_names={'scripts/build_template_report.py','resources/实验报告模板.docx',
             'resources/report-sections.json','docs/01_需求分析说明书.md',
             'docs/02_系统设计文档.md','docs/03_软件测试报告.md'}

def clean_text(s):
 s=re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',s)
 return s.replace('**','').replace('`','')

def para(text,kind='body'):
 proto={'body':body_p,'h1':h1_p,'h2':h2_p,'title':title_p,'field':field_p,'section':section_p}[kind]
 p=copy.deepcopy(proto);pr=p.find(q('pPr'));rr=p.find(q('r'));rp=rr.find(q('rPr')) if rr is not None else None;rp=copy.deepcopy(rp) if rp is not None else E.Element(q('rPr'))
 for c in list(p):
  if c.tag!=q('pPr'):p.remove(c)
 if pr is None:pr=E.SubElement(p,q('pPr'))
 # Template instructional blue is replaced by ordinary black report content.
 child(rp,'color',val='000000')
 for x in pr.findall('.//'+q('color')):x.set(q('val'),'000000')
 if kind in ('h1','h2','title','section'):child(pr,'keepNext')
 # Reserve breathing room at these section openings. LibreOffice ignores
 # pageBreakBefore/keepNext inside the template's long outer table row.
 if text in ('5 项目规划','3 原生界面验证'):child(pr,'spacing',before=960)
 if text in ('4 编译检查与动态内存检查','李想 界面与自动任务'):child(pr,'spacing',before=480)
 if text=='5 性能与兼容性':child(pr,'spacing',before=400)
 if text.startswith('工具生成的内容不能直接代替验证。'):child(pr,'keepLines')
 child(pr,'widowControl',val=1)
 r=E.SubElement(p,q('r'));r.append(rp);t=E.SubElement(r,q('t'));t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=clean_text(text)
 return p

def put(i,paragraphs,j=0,preserve_title=False):
 tc=cell(i,j)
 saved=copy.deepcopy(tc.find('w:p',NS)) if preserve_title else None
 for c in list(tc):
  if c.tag!=q('tcPr'):tc.remove(c)
 if saved is not None:tc.append(saved)
 for p in paragraphs:tc.append(p)
 if len(tc)==1 or tc[-1].tag!=q('p'):tc.append(para(''))

def table(data):
 n=len(data[0]);t=E.Element(q('tbl'));pr=copy.deepcopy(inner.find(q('tblPr')))
 child(pr,'tblW',w=9480,type='dxa');child(pr,'tblLayout',type='fixed')
 oldb=pr.find(q('tblBorders'))
 if oldb is not None:pr.remove(oldb)
 pr.append(copy.deepcopy(outer.find('w:tblPr/w:tblBorders',NS)));t.append(pr)
 grid=E.SubElement(t,q('tblGrid'))
 if n==3 and data[0][0]=='编号':weights=[.13,.23,.64]
 elif n==3:weights=[.24,.38,.38]
 elif n==4 and data[0][1]=='关键属性':weights=[.20,.23,.39,.18]
 elif n==4:weights=[.25,.14,.14,.47]
 elif n==6:weights=[.22,.18,.18,.14,.14,.14]
 else:weights=[1/n]*n
 widths=[round(9480*w/sum(weights)) for w in weights];widths[-1]=9480-sum(widths[:-1])
 for w in widths:E.SubElement(grid,q('gridCol')).set(q('w'),str(w))
 for ri,values in enumerate(data):
  tr=E.SubElement(t,q('tr'));trp=E.SubElement(tr,q('trPr'));child(trp,'cantSplit')
  if ri==0:child(trp,'tblHeader')
  for ci,txt in enumerate(values):
   tc=E.SubElement(tr,q('tc'));tcp=E.SubElement(tc,q('tcPr'));child(tcp,'tcW',w=widths[ci],type='dxa');child(tcp,'vAlign',val='center')
   margins=child(tcp,'tcMar')
   for side in ('left','right'):child(margins,side,w=90,type='dxa')
   if ri==0:child(tcp,'shd',val='clear',fill='F2F6F7')
   p=para(txt);pp=p.find(q('pPr'));ind=child(pp,'ind',firstLine=0,firstLineChars=0);child(pp,'spacing',before=60,after=60,line=300,lineRule='auto')
   child(pp,'jc',val='left')
   if ri==0:
    child(p.find('w:r/w:rPr',NS),'b');child(pp,'keepNext')
   tc.append(p)
 return t

def figure(path,caption):
 global image_id
 path=ROOT/'docs'/path;assert path.exists(),path
 input_names.add(path.relative_to(ROOT).as_posix())
 image_id+=1;rid=f'rIdSquirrel{image_id}';name=f'word/media/squirrel-{image_id}.png';additions[name]=path.read_bytes()
 E.SubElement(rel,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',Id=rid,Type=R+'/image',Target='media/'+Path(name).name)
 if not ct.xpath('//*[local-name()="Default"][@Extension="png"]'):
  E.SubElement(ct,'{http://schemas.openxmlformats.org/package/2006/content-types}Default',Extension='png',ContentType='image/png')
 p=copy.deepcopy(image_p);pp=child(p,'pPr');child(pp,'ind',firstLine=0,firstLineChars=0);child(pp,'jc',val='center');child(pp,'keepNext')
 for n in list(p):
  if n.tag!=q('pPr') and not n.findall('.//w:drawing',NS):p.remove(n)
 w,h=Image.open(path).size;scale=min(6.40*914400/w,7.15*914400/h);cx,cy=round(w*scale),round(h*scale)
 for n in p.findall('.//wp:extent',NS)+p.findall('.//a:xfrm/a:ext',NS):n.set('cx',str(cx));n.set('cy',str(cy))
 for n in p.findall('.//a:blip',NS):n.set('{'+R+'}embed',rid)
 for n in p.findall('.//wp:docPr',NS):n.set('id',str(image_id));n.set('name',caption);n.set('descr',caption)
 for n in p.findall('.//pic:cNvPr',NS):n.set('id',str(image_id));n.set('name',Path(name).name)
 c=para(caption);cp=c.find(q('pPr'));child(cp,'ind',firstLine=0,firstLineChars=0);child(cp,'jc',val='center')
 return [p,c]

def markdown(s):
 out=[];lines=s.splitlines();i=0
 while i<len(lines):
  line=lines[i].strip();i+=1
  if not line:continue
  if line.startswith('# '):continue
  if line.startswith('!['):
   m=re.match(r'!\[(.*?)\]\((.*?)\)',line);out+=figure(m[2],m[1]);continue
  if line.startswith('|'):
   data=[]
   while True:
    if not re.fullmatch(r'[| :\-]+',line):data.append([x.strip() for x in line.strip('|').split('|')])
    if i>=len(lines) or not lines[i].strip().startswith('|'):break
    line=lines[i].strip();i+=1
   out.append(table(data));out.append(para(''));continue
  if line.startswith('##'):out.append(para(line.lstrip('#').strip(),'h1' if line.startswith('## ') else 'h2'))
  else:out.append(para(line))
 return out

put(0,[para('小组：3','field')]);put(0,[para('组长与组员信息','field')],1)
for i,(name,number) in enumerate([('杨梦宇','2023150901002'),('郭畅','2023040904017'),('李想','2023150901012')],1):
 put(i,[para(('组长姓名：' if i==1 else '组员姓名：')+name,'field')]);put(i,[para('学号：'+number,'field')],1)
profile=json.loads((ROOT/'resources/submission-readiness.json').read_text())
put(4,[para('一、实验室名称：'+profile['laboratory'],'section')])
put(5,[para('二、实验项目名称：文件备份软件 松鼠备份','section')])
put(7,[para('本项目实现macOS上的目录树备份与恢复，提供原生GUI与CLI两种入口，共用C++核心。归档采用自定义格式，Huffman压缩由项目实现；密码加密与认证调用系统CommonCrypto/Security。'),para('选做功能包括软硬链接与FIFO、基础元数据、六类筛选、打包压缩、密码加密、图形界面、定时任务、目录变化检测与任务内保留策略。设备节点、socket、网络备份、增量备份和系统守护未实现。'),para('交付包含源代码、构建脚本、程序、UML可编辑模型、需求与设计文档、测试证据、报告和答辩材料。0.2.0加入协作取消、阶段进度和发布前源目录复查。运行结果按实际测试记录填写。')],preserve_title=True)
put(8,[para('开发与测试平台为macOS 13.0、Apple Silicon arm64。使用Apple Clang 14.0.3、Command Line Tools、make、git、GoogleTest和Python；GUI使用Cocoa/AppKit。UML模型由StarUML 7.1.1后台读取验证，报告采用课程原DOCX模板。')],preserve_title=True)
for row,name in [(10,'01_需求分析说明书.md'),(11,'02_系统设计文档.md'),(12,'03_软件测试报告.md')]:
 put(row,markdown((ROOT/'docs'/name).read_text()),preserve_title=True)
end={int(k):v for k,v in json.loads((ROOT/'resources/report-sections.json').read_text()).items()}
for row,items in end.items():put(row,[para(t,k) for k,t in items],preserve_title=True)
# Remove only cover spacer paragraphs, retaining all institutional text and formatting.
for index in [15,14,13]:
 p=body[index]
 if p.tag==q('p') and not p.xpath('.//w:t/text()',namespaces=NS):body.remove(p)
after_imprint=False
for p in list(body):
 if p.tag!=q('p'):continue
 text=''.join(p.xpath('.//w:t/text()',namespaces=NS))
 if text=='电 子 科 技 大 学':break
 if after_imprint and not text:body.remove(p)
 if text=='电子科技大学教务处制表':after_imprint=True
for p in body.findall(q('p')):
 if ''.join(p.xpath('.//w:t/text()',namespaces=NS))=='电 子 科 技 大 学':child(child(p,'pPr'),'pageBreakBefore')
# Word requires a trailing paragraph after a table. The template gives this
# empty marker a 22 pt font, which can create an entirely blank last page.
tail=outer.getnext()
if tail is not None and tail.tag==q('p') and not tail.xpath('.//w:t/text()',namespaces=NS):
 tailpr=child(tail,'pPr');child(tailpr,'spacing',before=0,after=0,line=20,lineRule='exact')
 child(child(tailpr,'rPr'),'sz',val=2)
# Keep the template's explicit line spacing instead of snapping substituted CJK
# font metrics to multiples of its 15.6 pt document grid during PDF rendering.
for p in xml.findall('.//w:p',NS):child(child(p,'pPr'),'snapToGrid',val=0)
# Keep the final short sections and the three module reflections together,
# followed by the intact blank grading/signature row.
for index in (13,15,16,17):child(child(rows[index],'trPr'),'cantSplit')
assert E.tostring(body.find('w:sectPr',NS))==original_sect
parts['word/document.xml']=E.tostring(xml,encoding='UTF-8',xml_declaration=True,standalone=True)
parts['word/_rels/document.xml.rels']=E.tostring(rel,encoding='UTF-8',xml_declaration=True,standalone=True)
parts['[Content_Types].xml']=E.tostring(ct,encoding='UTF-8',xml_declaration=True,standalone=True)
parts.update(additions);args.output.parent.mkdir(parents=True,exist_ok=True)
with ZipFile(args.output,'w',ZIP_DEFLATED) as out:
 for name,data in parts.items():out.writestr(name,data)
allowed={'word/document.xml','word/_rels/document.xml.rels','[Content_Types].xml'}
with ZipFile(args.output) as out:
 unchanged=[name for name in z.namelist() if name not in allowed]
 assert all(z.read(name)==out.read(name) for name in unchanged)
qa={'template_sha256':hashlib.sha256(template.read_bytes()).hexdigest(),'preserved_parts':len(unchanged),
    'edited_parts':sorted(allowed),'new_media':len(additions),'sections_unchanged':True}
args.output.with_suffix('.preservation.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
inputs={'schema':1,'docx_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),
        'input_files':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(input_names)},
        'profile_fields':{'laboratory':profile['laboratory']}}
args.output.with_suffix('.inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2)+'\n')
print(args.output);print(json.dumps(qa,ensure_ascii=False))
