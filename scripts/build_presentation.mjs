// Local editable OOXML fallback. The managed Artifact Tool runtime is unavailable on this Mac.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const build=path.join(root,'.preflight/ppt-build');
const out=path.join(root,'presentations');
fs.mkdirSync(build,{recursive:true});fs.mkdirSync(out,{recursive:true});
const summary=JSON.parse(fs.readFileSync(path.join(root,'test-results/summary.json')));
const unit=Number(fs.readFileSync(path.join(root,'test-results/unit.xml'),'utf8').match(/<testsuites[^>]*tests="(\d+)"/)[1]);
const integration=JSON.parse(fs.readFileSync(path.join(root,'test-results/integration.json'))).length;
const security=JSON.parse(fs.readFileSync(path.join(root,'test-results/security.json'))).length;
const count=unit+integration+security;
const C={paper:'F7F6F2',ink:'222D32',muted:'687375',accent:'B8512F',white:'FFFFFF',rule:'D6DDDC',pale:'EDEEE8'};
const font='Arial Unicode MS';
const slides=[];
function slide(title,note,{dark=false}={}){
 const s={title,note,bg:dark?C.ink:C.paper,elements:[]};slides.push(s);
 if(title)text(s,title,64,48,1152,70,44,dark?C.white:C.ink,true);
 if(slides.length>1)text(s,String(slides.length),1175,665,40,24,17,dark?'A9B1B1':C.muted);
 return s;
}
function text(s,value,x,y,w,h,size=26,color=C.ink,bold=false){s.elements.push({kind:'text',text:value,x,y,w,h,size,color,bold});}
function table(s,rows,widths,x,y,rowHeights,size=24){s.elements.push({kind:'table',rows,widths,x,y,w:widths.reduce((a,b)=>a+b),h:rowHeights.reduce((a,b)=>a+b),rowHeights,size});}
function image(s,file,x,y,w,h){s.elements.push({kind:'image',file,x,y,w,h});}
let s=slide('', '建议 15 秒。介绍课程项目与平台。成员 A/B/C 为建议分工角色，演示前替换为真实姓名。强调这是本机可运行初版，不承诺未验收的平台。',{dark:true});
text(s,'松鼠备份',64,135,580,100,68,C.white,true);
text(s,'Squirrel Backup',68,246,560,55,35,'C9CFCC');
text(s,'软件开发综合实验',68,326,560,42,27,'E5AE94');
text(s,'macOS 原生应用\nC++17 业务核心 · GUI 与 CLI',68,394,540,100,26,C.white);
text(s,'三人协作方案与项目演示',68,597,550,36,21,'BBC4C1');
image(s,'docs/screenshots/page-0.png',650,148,576,421.33);
s=slide('已实现的本地备份功能','建议 25 秒。A 介绍基本闭环及文件类型和筛选，B 补充算法。实时是元数据轮询，不是内核事件或无限实时保证。依赖库和限制在后续页面明确。');
text(s,'基础流程',65,150,520,44,32,C.accent,true);
text(s,'目录树备份与安全还原\n完整性检查与内容查看\n已有目标拒绝覆盖',65,215,540,190,30);
text(s,'文件与选项',680,150,520,44,32,C.accent,true);
text(s,'软硬链接、FIFO、基础元数据\n路径／类型／名字／时间／尺寸／UID 筛选\n自定义打包、Huffman、密码保护',680,215,530,200,26);
text(s,'自动任务',65,450,520,44,32,C.accent,true);
text(s,'定时完整快照、任务内保留与淘汰\n轮询变化检测，稳定后自动备份',65,515,1135,100,28);
s=slide('一个 C++ 核心服务两个入口','建议 25 秒。A 说明 CLI 与 GUI 不是两套复制的备份逻辑。此页为文字化模块说明，不是 UML 图。说明备份先扫描、再打包压缩、再封装，恢复先验证，再写私有暂存，最后不覆盖发布。');
text(s,'入口',64,150,235,45,32,C.accent,true);
text(s,'Cocoa GUI\n命令行 CLI',64,222,250,130,32);
text(s,'核心接口',390,150,460,45,32,C.accent,true);
text(s,'BackupService\nbackup · inspect · restore\nScheduler 复用同一核心',390,222,760,155,30);
text(s,'备份',64,445,230,40,29,C.accent,true);
text(s,'扫描与筛选 → 树记录／分块压缩 → 摘要或密码封装 → 发布',285,443,920,86,25);
text(s,'恢复',64,555,230,40,29,C.accent,true);
text(s,'验证与解密 → 私有目录解包 → 元数据恢复 → 新目录发布',285,553,920,58,25);
text(s,'macOS 15.7.9 · Apple Clang 17 · Makefile · VS Code',65,632,1090,32,22,C.muted);
s=slide('算法选择与库使用边界','建议 25 秒。B 解释自研打包与 Huffman，以及先压缩后加密。密码方案使用系统库，不宣称自研 AES；按教师规则说明扩展分可能折半。GUI 也使用系统框架。');
table(s,[['功能','实现方式','依赖申报'],['打包／解包','自定义 SQBK / SQTREE 格式','本项目实现'],['压缩／解压','分块 Huffman，收益不足存原始块','本项目实现'],['密码保护','AES-256-CBC + PBKDF2 + HMAC','CommonCrypto / Security'],['图形界面','macOS 原生控件与后台任务','Cocoa / AppKit']],[205,565,370],68,154,[52,76,76,76,76],23);
text(s,'先压缩后加密；加密备份先认证、后解密。系统库使用如实写入报告。',68,570,1135,70,24,C.muted);
s=slide('测试结果与验证范围',`建议 25 秒。C 解释 ${count} 项是命名测试用例数量，12 项是 GUI 内部动作断言，不能混加。持续运行只有十分钟，不是整夜稳定性证明。文件选择器与真实点击还需要人工验收。十分钟稳定运行与变异输入数字来自初版记录；本轮 72 项包含新增调度回归。`);
text(s,`${count} / ${count}`,65,150,530,120,86,C.accent,true);
text(s,'自动测试用例通过',72,276,450,50,30);
text(s,'git 本地版本管理\nclang-format + cpplint 代码规范',72,348,450,80,22,C.muted);
table(s,[['测试层次','数量'],['GoogleTest 单元测试',String(unit)],['CLI 集成测试',String(integration)],['畸形归档与并发测试',String(security)]],[470,180],560,157,[52,72,72,72],24);
text(s,'另有 12 项 GUI 内部动作断言、Sanitizer 检查\n60 秒变异测试约 15.8 万次输入；十分钟任务完成 275 份快照',70,443,1140,110,26);
text(s,'真实点击、文件选择器、跨机器兼容性仍待人工验收。',70,590,1140,52,23,C.muted);
s=slide('三人各负责实现、测试与文档','建议 30 秒。用角色代号说明建议分工，各 30 点，约各三分之一；不是已发生贡献。A 文件与恢复，B 格式与算法，C 界面与自动任务。公共接口一起评审，三人都要能独立构建和演示。');
table(s,[['成员','技术主责','配套工作'],['A','扫描筛选、安全恢复、CLI','需求与用例、模块测试'],['B','归档格式、Huffman、密码封装','设计与类图、算法测试'],['C','GUI、自动任务、集成发布','测试汇总、动态建模']],[130,565,445],70,160,[55,98,98,98],24);
text(s,'推进计划：接手复现 → 模块复核 → 手工建模、人工验收与演示',70,522,1140,34,21,C.muted);
text(s,'每人 30 个计划工作量点：代码 14 + 测试 5 + 文档建模 5 + 复核演示 6',70,566,1140,60,24,C.accent);
text(s,'角色代号请替换姓名学号；实际完成情况另行登记。',70,630,1120,30,19,C.muted);
s=slide('现场演示以安全恢复为主线','建议 25 秒。A 操作基础流程，B 补充压缩加密，C 展示自动任务和测试。演示使用 scripts/demo.sh 的独立副本，恢复目标必须是新目录。不要备份真实个人文件或在截图中展示密码。');
text(s,'1  选择演示源目录，创建新备份\n\n2  验证内容并恢复到新目录\n\n3  展示错误密码与不覆盖保护\n\n4  启动自动任务，检查保留份数',65,168,575,400,27);
image(s,'docs/screenshots/page-1.png',662,167,560,409.63);
text(s,'GUI 离屏预览；真实文件选择器需现场复核',670,597,550,40,18,C.muted);
s=slide('初版边界与下一轮验收','建议 10 秒。简要说明已知边界与接下来三人各自承担的验收。源码、可执行程序和构建脚本已经具备。UML 按指导手工完成，PPT 为本轮提供的可编辑初稿；个人信息、视频和证书由本人补充。',{dark:true});
text(s,'接下来',65,160,500,50,34,'E5AE94',true);
text(s,'完成真实 GUI 操作与手工 UML\n填写姓名、学号和真实贡献\n共同排练并录制课程演示视频',65,240,1120,210,31,C.white);
text(s,'当前限制',65,502,500,45,27,'E5AE94',true);
text(s,'任务需保持进程运行；暂不支持网盘、增量、完整 ACL 与后台常驻。',65,566,1140,70,25,'D2D9D6');
const NS={p:'http://schemas.openxmlformats.org/presentationml/2006/main',a:'http://schemas.openxmlformats.org/drawingml/2006/main',r:'http://schemas.openxmlformats.org/officeDocument/2006/relationships'};
const e=v=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const emu=v=>Math.round(v*9525);
const wrap=(name,body)=>`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><${name} xmlns:p="${NS.p}" xmlns:a="${NS.a}" xmlns:r="${NS.r}">${body}</${name}>`;
const group='<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>';
const fill=c=>`<a:solidFill><a:srgbClr val="${c}"/></a:solidFill>`;
const pos=t=>`<a:xfrm><a:off x="${emu(t.x)}" y="${emu(t.y)}"/><a:ext cx="${emu(t.w)}" cy="${emu(t.h)}"/></a:xfrm>`;
function paragraphs(value,size,color,bold=false){return value.split('\n').map(line=>`<a:p><a:pPr algn="l"><a:lnSpc><a:spcPts val="${Math.round(size*1.42*75)}"/></a:lnSpc><a:buNone/></a:pPr><a:r><a:rPr lang="zh-CN" sz="${Math.round(size*75)}" b="${bold?1:0}">${fill(color)}<a:latin typeface="${font}"/><a:ea typeface="${font}"/><a:cs typeface="${font}"/></a:rPr><a:t xml:space="preserve">${e(line)}</a:t></a:r><a:endParaRPr lang="zh-CN" sz="${Math.round(size*75)}"/></a:p>`).join('');}
function textbox(t,id){return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="Text ${id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>${pos(t)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"><a:noAutofit/></a:bodyPr><a:lstStyle/>${paragraphs(t.text,t.size,t.color,t.bold)}</p:txBody></p:sp>`;}
function nativeTable(t,id){const rows=t.rows.map((r,index)=>`<a:tr h="${emu(t.rowHeights[index])}">${r.map(cell=>`<a:tc><a:txBody><a:bodyPr wrap="square"/><a:lstStyle/>${paragraphs(cell,t.size,index?C.ink:C.white,index===0)}</a:txBody><a:tcPr marL="114300" marR="114300" marT="76200" marB="76200" anchor="ctr"><a:lnB w="6350">${fill(C.rule)}<a:prstDash val="solid"/></a:lnB>${fill(index?(index%2?C.white:C.pale):C.ink)}</a:tcPr></a:tc>`).join('')}</a:tr>`).join('');return `<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="${id}" name="Editable table ${id}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="${emu(t.x)}" y="${emu(t.y)}"/><a:ext cx="${emu(t.w)}" cy="${emu(t.h)}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>${t.widths.map(w=>`<a:gridCol w="${emu(w)}"/>`).join('')}</a:tblGrid>${rows}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>`;}
function picture(t,id,rid){return `<p:pic><p:nvPicPr><p:cNvPr id="${id}" name="Product preview ${id}" descr="松鼠备份应用离屏预览"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="${rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr>${pos(t)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>`;}
const parts=new Map();const put=(name,value)=>parts.set(name,Buffer.from(value));
const rels=items=>`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${items.map(([id,type,target])=>`<Relationship Id="${id}" Type="${NS.r}/${type}" Target="${target}"/>`).join('')}</Relationships>`;
for(let i=0;i<slides.length;i++){
 const s=slides[i];let id=2;let rel=[['rId1','slideLayout','../slideLayouts/slideLayout1.xml'],['rId2','notesSlide',`../notesSlides/notesSlide${i+1}.xml`]];let objs='';
 for(const t of s.elements){if(t.kind==='text')objs+=textbox(t,id++);else if(t.kind==='table')objs+=nativeTable(t,id++);else {const name=`image-${i+1}-${id}.png`,rid=`rId${rel.length+1}`;parts.set('ppt/media/'+name,fs.readFileSync(path.join(root,t.file)));rel.push([rid,'image','../media/'+name]);objs+=picture(t,id++,rid);}}
 put(`ppt/slides/slide${i+1}.xml`,wrap('p:sld',`<p:cSld name="${e(s.title||'松鼠备份')}"><p:bg><p:bgPr>${fill(s.bg)}<a:effectLst/></p:bgPr></p:bg><p:spTree>${group}${objs}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>`));
 put(`ppt/slides/_rels/slide${i+1}.xml.rels`,rels(rel));
 const note={text:s.note+`\n依据：项目源码；test-results/summary.json、unit.xml、integration.json、security.json；docs/07_三人分工与协作方案.md。截图为应用自身离屏预览。`,x:40,y:100,w:640,h:700,size:18,color:C.ink};
 put(`ppt/notesSlides/notesSlide${i+1}.xml`,wrap('p:notes',`<p:cSld><p:spTree>${group}<p:sp><p:nvSpPr><p:cNvPr id="2" name="Speaker notes"/><p:cNvSpPr/><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/> <p:txBody><a:bodyPr/><a:lstStyle/>${paragraphs(note.text,18,C.ink)}</p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>`));
 put(`ppt/notesSlides/_rels/notesSlide${i+1}.xml.rels`,rels([['rId1','notesMaster','../notesMasters/notesMaster1.xml'],['rId2','slide',`../slides/slide${i+1}.xml`]]));
}
const clrMap='<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>';
put('ppt/slideMasters/slideMaster1.xml',wrap('p:sldMaster',`<p:cSld name="Squirrel Master"><p:spTree>${group}</p:spTree></p:cSld>${clrMap}<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId2"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>`));
put('ppt/slideMasters/_rels/slideMaster1.xml.rels',rels([['rId1','theme','../theme/theme1.xml'],['rId2','slideLayout','../slideLayouts/slideLayout1.xml']]));
put('ppt/slideLayouts/slideLayout1.xml',wrap('p:sldLayout',`<p:cSld name="Blank"><p:spTree>${group}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>`).replace('<p:sldLayout ','<p:sldLayout type="blank" preserve="1" '));
put('ppt/slideLayouts/_rels/slideLayout1.xml.rels',rels([['rId1','slideMaster','../slideMasters/slideMaster1.xml']]));
put('ppt/notesMasters/notesMaster1.xml',wrap('p:notesMaster',`<p:cSld><p:spTree>${group}</p:spTree></p:cSld>${clrMap}<p:notesStyle/>`));
put('ppt/notesMasters/_rels/notesMaster1.xml.rels',rels([['rId1','theme','../theme/theme1.xml']]));
const scheme=Object.entries({dk1:C.ink,lt1:C.white,dk2:C.muted,lt2:C.paper,accent1:C.accent,accent2:'547A6D',accent3:'A88A51',accent4:'4E6C88',accent5:'92718E',accent6:'7A8C55',hlink:C.accent,folHlink:'804026'}).map(([k,v])=>`<a:${k}><a:srgbClr val="${v}"/></a:${k}>`).join('');
put('ppt/theme/theme1.xml',`<?xml version="1.0" encoding="UTF-8"?><a:theme xmlns:a="${NS.a}" name="Squirrel"><a:themeElements><a:clrScheme name="Squirrel">${scheme}</a:clrScheme><a:fontScheme name="Squirrel"><a:majorFont><a:latin typeface="${font}"/><a:ea typeface="${font}"/><a:cs typeface="${font}"/></a:majorFont><a:minorFont><a:latin typeface="${font}"/><a:ea typeface="${font}"/><a:cs typeface="${font}"/></a:minorFont></a:fontScheme><a:fmtScheme name="Squirrel"><a:fillStyleLst>${fill(C.white).repeat(3)}</a:fillStyleLst><a:lnStyleLst>${`<a:ln w="12700">${fill(C.ink)}<a:prstDash val="solid"/></a:ln>`.repeat(3)}</a:lnStyleLst><a:effectStyleLst>${'<a:effectStyle><a:effectLst/></a:effectStyle>'.repeat(3)}</a:effectStyleLst><a:bgFillStyleLst>${fill(C.paper).repeat(3)}</a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>`);
put('ppt/presentation.xml',wrap('p:presentation',`<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:notesMasterIdLst><p:notesMasterId r:id="rId${slides.length+2}"/></p:notesMasterIdLst><p:sldIdLst>${slides.map((_,i)=>`<p:sldId id="${256+i}" r:id="rId${i+2}"/>`).join('')}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/>`));
put('ppt/_rels/presentation.xml.rels',rels([['rId1','slideMaster','slideMasters/slideMaster1.xml'],...slides.map((_,i)=>[`rId${i+2}`,'slide',`slides/slide${i+1}.xml`]),[`rId${slides.length+2}`,'notesMaster','notesMasters/notesMaster1.xml']]));
put('_rels/.rels',`<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${NS.r}/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="${NS.r}/extended-properties" Target="docProps/app.xml"/></Relationships>`);
put('docProps/core.xml',`<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>松鼠备份课程演示</dc:title><dc:creator>Squirrel Backup course project</dc:creator><dc:description>八页可编辑演示，含讲者备注和建议三人分工</dc:description></cp:coreProperties>`);
put('docProps/app.xml',`<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Squirrel Backup Presentation Builder</Application><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Slides>${slides.length}</Slides><Notes>${slides.length}</Notes></Properties>`);
const types=[['/ppt/presentation.xml','application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'],['/ppt/slideMasters/slideMaster1.xml','application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml'],['/ppt/slideLayouts/slideLayout1.xml','application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml'],['/ppt/theme/theme1.xml','application/vnd.openxmlformats-officedocument.theme+xml'],['/ppt/notesMasters/notesMaster1.xml','application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml'],['/docProps/core.xml','application/vnd.openxmlformats-package.core-properties+xml'],['/docProps/app.xml','application/vnd.openxmlformats-officedocument.extended-properties+xml'],...slides.flatMap((_,i)=>[[`/ppt/slides/slide${i+1}.xml`,'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'],[`/ppt/notesSlides/notesSlide${i+1}.xml`,'application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml']])];
put('[Content_Types].xml',`<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>${types.map(([p,t])=>`<Override PartName="${p}" ContentType="${t}"/>`).join('')}</Types>`);
const manifest={width:1280,height:720,font,slides};
fs.writeFileSync(path.join(build,'slides.json'),JSON.stringify(manifest,null,2));
const partsDir=path.join(build,'parts');fs.rmSync(partsDir,{recursive:true,force:true});
for(const [name,data] of parts){const target=path.join(partsDir,name);fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,data);}
const finalPath=path.join(out,'松鼠备份_三分钟演示.pptx');
execFileSync('python3',['-c','from pathlib import Path; from zipfile import ZipFile, ZIP_DEFLATED; import sys; r=Path(sys.argv[1]); z=ZipFile(sys.argv[2],"w",ZIP_DEFLATED); [z.write(p,p.relative_to(r).as_posix()) for p in sorted(r.rglob("*")) if p.is_file()]; z.close()',partsDir,finalPath]);
fs.writeFileSync(path.join(out,'演示讲稿.md'),'# 松鼠备份演示讲稿\n\n'+slides.map((s,i)=>`## 第 ${i+1} 页 ${s.title||'松鼠备份'}\n\n${s.note}\n`).join('\n'));
console.log(finalPath);
