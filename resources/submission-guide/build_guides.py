#!/usr/bin/env python3
"""Build printable HTML and PDF from repository Markdown; no business logic here."""
from pathlib import Path
from html import escape
import re
import sys
import json
import markdown
import fitz
from PIL import Image, ImageDraw
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Spacer, Table, TableStyle, CondPageBreak, KeepTogether, Image as FlowImage
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

ROOT=Path(__file__).resolve().parent
DOCS=ROOT
HTML=DOCS/'html';PDF=DOCS/'pdf';QA=ROOT/'.preflight/doc-qa'
for d in [HTML,PDF,QA]:d.mkdir(parents=True,exist_ok=True)
FONT='/Library/Fonts/Arial Unicode.ttf'
if not Path(FONT).exists():
    raise SystemExit('Chinese font missing: set up a suitable font before rendering PDFs')
pdfmetrics.registerFont(TTFont('CJK',FONT))
base=dict(fontName='CJK',fontSize=10,leading=15.5,wordWrap='CJK',textColor=colors.HexColor('#202833'),spaceAfter=6)
styles={
 'body':ParagraphStyle('body',**base),
 'title':ParagraphStyle('title',fontName='CJK',fontSize=21,leading=30,spaceBefore=5,spaceAfter=20,wordWrap='CJK',textColor=colors.black),
 'h2':ParagraphStyle('h2',fontName='CJK',fontSize=15,leading=23,spaceBefore=14,spaceAfter=9,keepWithNext=False,wordWrap='CJK'),
 'h3':ParagraphStyle('h3',fontName='CJK',fontSize=12,leading=19,spaceBefore=10,spaceAfter=7,keepWithNext=False,wordWrap='CJK'),
 'h4':ParagraphStyle('h4',fontName='CJK',fontSize=10.5,leading=17,spaceBefore=9,spaceAfter=6,keepWithNext=False,wordWrap='CJK'),
 'cell':ParagraphStyle('cell',fontName='CJK',fontSize=8.4,leading=12.5,wordWrap='CJK'),
 'code':ParagraphStyle('code',fontName='CJK',fontSize=8.5,leading=13,wordWrap='CJK',backColor=colors.HexColor('#f3f4f5'),borderPadding=7,spaceAfter=12),
}
css='''body{max-width:900px;margin:48px auto;padding:0 32px;font:16px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#202833}h1{color:#111;font-size:30px;line-height:1.5;margin-bottom:32px}h2{margin-top:36px;font-size:23px}h3{margin-top:24px;font-size:19px}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.65;margin:18px 0}th,td{border:1px solid #dde1e4;padding:8px 10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#edf0f1}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f6;padding:16px}code{font-size:.9em}a{color:#914321}nav{margin-bottom:28px;color:#777}footer{margin-top:44px;color:#777;font-size:12px}@media print{body{margin:0;padding:0;font-size:10pt}nav{display:none}h1,h2,h3,h4{break-after:avoid}tr{break-inside:avoid}thead{display:table-header-group}@page{size:A4;margin:18mm}}'''
def inline(s):
    s=escape(s)
    s=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<link href="\2" color="#914321">\1</link>',s)
    s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1',s)
    s=re.sub(r'`([^`]+)`',r'<font color="#67402c">\1</font>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    return s

def story(text,group_cases=True):
    lines=text.splitlines();out=[];i=0;first=True
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line=='<!-- pagebreak -->':out.append(PageBreak());i+=1;continue
        if group_cases and re.match(r'^#{4,5} TC-',line):
            end=i+1
            while end<len(lines) and not lines[end].startswith('#'):end+=1
            out.append(KeepTogether(story('\n'.join(lines[i:end]),False)));i=end;continue
        picture=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line)
        if picture:
            path=DOCS/picture[2]
            with Image.open(path) as im:w,h=im.size
            scale=min((A4[0]-100)/w,590/h)
            out.append(KeepTogether([FlowImage(str(path),width=w*scale,height=h*scale),Spacer(1,6),Paragraph(inline(picture[1]),styles['cell']),Spacer(1,12)]))
            i+=1;continue
        if line.startswith('```'):

            i+=1;code=[]
            while i<len(lines) and not lines[i].startswith('```'):code.append(escape(lines[i]).replace(' ','&#160;'));i+=1
            out.append(Paragraph('<br/>'.join(code),styles['code']));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',x.replace(' ','')) for x in cells):rows.append(cells)
                i+=1
            width=max(map(len,rows)); rows=[r+['']*(width-len(r)) for r in rows]
            widths=[(A4[0]-100)/width]*width
            if rows[0]==['目录','内容与用途']:widths=[(A4[0]-100)*x for x in [.29,.71]]
            if rows[0]==['编号','层次与名称','实际结果']:widths=[(A4[0]-100)*x for x in [.12,.72,.16]]
            table=Table([[Paragraph(inline(x),styles['cell']) for x in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9edef')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#d6dce0')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#fafafa')])]))
            out.extend([table,Spacer(1,12)]);continue
        m=re.match(r'^(#{1,6})\s+(.*)',line)
        if m:
            level=len(m[1]);key='title' if level==1 and first else 'h2' if level<=2 else 'h3' if level==3 else 'h4'
            if key!='title':
                prev=i-1
                while prev>=0 and not lines[prev].strip():prev-=1
                previous_is_heading=prev>=0 and bool(re.match(r'^#{1,6}\s+',lines[prev].strip()))
                if not previous_is_heading:
                    following=0;scan=i+1
                    while scan<len(lines):
                        candidate=lines[scan].strip()
                        if not candidate:scan+=1;continue
                        if candidate.startswith('#'):following+=1;scan+=1;continue
                        break
                    out.append(CondPageBreak(85+50*following))
            out.append(Paragraph(inline(m[2]),styles[key]));first=False;i+=1;continue
        bullet=re.match(r'^(?:[-*]|\d+\.)\s+(.*)',line)
        if bullet:
            out.append(Paragraph('• '+inline(bullet[1]),styles['body']));i+=1;continue
        paragraph=[line];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|[-*] |\d+\. )',lines[i].strip()):paragraph.append(lines[i].strip());i+=1
        out.append(Paragraph(inline(' '.join(paragraph)),styles['body']))
    return out

def footer(canvas,doc):
    canvas.saveState();canvas.setFont('CJK',8);canvas.setFillColor(colors.HexColor('#777777'))
    canvas.drawString(50,26,'松鼠备份 0.2.0  软件开发综合实验')
    canvas.drawRightString(A4[0]-50,26,str(doc.page));canvas.restoreState()

manifest=[]
for src in sorted(DOCS.glob('[0-9][0-9]_*.md')):
    if len(sys.argv) > 1 and not any(src.name.startswith(prefix) for prefix in sys.argv[1:]):
        continue
    text=src.read_text();name=src.stem;title=text.splitlines()[0].lstrip('# ')
    html=markdown.markdown(text,extensions=['tables','fenced_code'])
    # Generated HTML lives one directory below the Markdown source.
    html=re.sub(r'src="(?![a-z]+:|/|#)([^"]+)"',r'src="../\1"',html)
    html='<style>img{max-width:100%;height:auto}</style>'+html
    (HTML/(name+'.html')).write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'+escape(title)+'</title><style>'+css+'</style><nav><a href="index.html">文档目录</a></nav><main>'+html+'</main><footer>松鼠备份 0.2.0 · 请以源码和测试结果为准</footer></html>')
    pdf=PDF/(name+'.pdf')
    SimpleDocTemplate(str(pdf),pagesize=A4,rightMargin=50,leftMargin=50,topMargin=45,bottomMargin=45,title=title,author='Squirrel Backup course project').build(story(text),onFirstPage=footer,onLaterPages=footer)
    document=fitz.open(pdf);pages=[];bounds=[]
    for index,page in enumerate(document):
        pix=page.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False)
        path=QA/(name+f'-{index+1:02d}.png');pix.save(path);pages.append(path)
        for block in page.get_text('blocks'):
            if block[0]<40 or block[2]>A4[0]-38 or block[1]<30 or block[3]>A4[1]-15:bounds.append(dict(page=index+1,rect=list(block[:4]),text=block[4][:70]))
    manifest.append(dict(name=name,pages=len(pages),bounds_warnings=bounds))
    # Four pages per contact sheet, at their rendered scale.
    for start in range(0,len(pages),4):
        images=[Image.open(p).convert('RGB') for p in pages[start:start+4]]
        w,h=images[0].size;sheet=Image.new('RGB',(2*w,2*h),'#cccccc')
        for j,im in enumerate(images):sheet.paste(im,((j%2)*w,(j//2)*h))
        sheet.save(QA/(name+f'-sheet-{start//4+1:02d}.jpg'),quality=90)
    print(name,len(pages),'pages','bounds warnings',len(bounds))
links=''.join('<li><a href="'+escape(x['name'])+'.html">'+escape(x['name'])+'</a> · <a href="../pdf/'+escape(x['name'])+'.pdf">PDF</a></li>' for x in manifest)
if len(sys.argv) == 1: (HTML/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>松鼠备份文档</title><style>'+css+'</style><h1>松鼠备份课程文档</h1><p><a href="../../presentations/第3组_松鼠备份_答辩.pptx">答辩 PPT</a> · <a href="../../presentations/第3组_松鼠备份_答辩.pdf">答辩 PDF</a></p><p>0.2.0 复核修订版。可编辑源文件在上一级目录。</p><ul>'+links+'</ul>')
if len(sys.argv) > 1 and (QA/'manifest.json').exists():
    existing = json.loads((QA/'manifest.json').read_text())
    updated = {item['name']: item for item in existing + manifest}
    manifest = [updated[name] for name in sorted(updated)]
(QA/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
