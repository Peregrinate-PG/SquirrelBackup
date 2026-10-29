import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL,fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url),modules=process.env.ARTIFACT_NODE_MODULES;
if(!modules)throw new Error('Set ARTIFACT_NODE_MODULES to the supplied artifact runtime modules.');
const {Presentation,PresentationFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool',{paths:[modules]})).href);
const root=path.resolve(process.env.SQUIRREL_ROOT||path.join(path.dirname(fileURLToPath(import.meta.url)),'..'));
const build=path.resolve(process.env.PPT_BUILD_DIR||path.join(root,'.preflight/ppt-build'));
await fs.mkdir(build,{recursive:true});
const summary=JSON.parse(await fs.readFile(path.join(root,'test-results/summary.json')));
const p=Presentation.create({slideSize:{width:1280,height:720}});
const C={paper:'#F6F5F0',ink:'#243A40',muted:'#6F807D',orange:'#B96C43',gold:'#B89A62',teal:'#47776F',line:'#D4DDD7',pale:'#E7EDE6',white:'#FFFFFF',navy:'#20393E'};
const font='PingFang SC',numberFont='Avenir Next',notes=[];
function shape(s,geometry,x,y,w,h,fill='none',stroke='none',sw=0){return s.shapes.add({geometry,position:{left:x,top:y,width:w,height:h},fill,line:{fill:stroke,width:sw}});}
function text(s,value,x,y,w,h,size=26,color=C.ink,bold=false,align='left',face=font){
 const v=shape(s,'textbox',x,y,w,h);v.text=value;v.text.style={typeface:face,fontSize:size,bold,color,alignment:align,verticalAlignment:'top',wrap:'square',lineSpacing:1.13,insets:0};return v;
}
function ln(s,x,y,w,color=C.line,thick=1){return shape(s,'line',x,y,w,0,'none',color,thick);}
function vertical(s,x,y,h,color=C.line,thick=1){return shape(s,'line',x,y,0,h,'none',color,thick);}
function curve(s,x,y,w,h,commands,color,width=1){return s.shapes.add({geometry:'custom',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:color,width},customPaths:[{width:w,height:h,commands}]});}
function backdrop(s,dark=false){
 s.background.fill=dark?C.navy:C.paper;
 const c=dark?'#375459':'#E1E7DE';
 for(let i=0;i<7;i++)curve(s,1014+i*18,0,250-i*16,185+i*13,[{moveTo:{x:0,y:0}},{cubicBezTo:{x1:20,y1:85+i*6,x2:100-i*2,y2:80+i*10,x:240-i*16,y:175+i*13}}],c,.8);
 ln(s,0,0,1280,C.gold,2);
}
function slide(title,section,note,dark=false){
 const s=p.slides.add();backdrop(s,dark);
 if(title){text(s,title,62,47,1080,66,43,dark?C.white:C.ink,true);ln(s,62,126,1156,dark?'#476064':C.line);ln(s,62,126,57,C.gold,3);}
 if(section)text(s,section,820,18,397,25,16,dark?'#B5C6C3':C.muted,false,'right');
 const i=p.slides.items.length;
 if(i>1){text(s,String(i).padStart(2,'0'),1135,667,43,28,22,dark?'#DDE6E0':C.teal,false,'right',numberFont);text(s,'/ 11',1187,674,44,22,14,dark?'#A2B9B4':C.muted);}
 notes.push({title:title||'松鼠备份',note});return s;
}
function icon(s,name,x,y,size=46,color=C.teal){
 const k=size/48,l=(a,b,c,d)=>{const ox=Math.min(a,c),oy=Math.min(b,d),w=Math.max(Math.abs(c-a)*k,.1),h=Math.max(Math.abs(d-b)*k,.1);return curve(s,x+ox*k,y+oy*k,w,h,[{moveTo:{x:(a-ox)*k,y:(b-oy)*k}},{lineTo:{x:(c-ox)*k,y:(d-oy)*k}}],color,2.3*k);};
 const r=(a,b,w,h,g='roundRect')=>shape(s,g,x+a*k,y+b*k,w*k,h*k,'none',color,2.3*k);
 if(name==='folder'){r(5,14,38,29);l(5,14,5,8);l(5,8,21,8);l(21,8,27,14);}
 if(name==='archive'){r(8,6,32,37);r(4,4,40,9,'rect');l(19,24,29,24);l(19,28,29,28);}
 if(name==='lock'){r(10,21,28,22);r(16,6,16,21);l(24,29,24,35);}
 if(name==='clock'){r(5,5,38,38,'ellipse');l(24,12,24,24);l(24,24,33,29);}
 if(name==='check'){r(4,4,40,40,'ellipse');l(13,24,21,32);l(21,32,35,16);}
 if(name==='layers'){r(13,5,29,24);r(6,16,29,25);}
 if(name==='tree'){r(17,3,14,12,'rect');r(3,34,14,11,'rect');r(31,34,14,11,'rect');l(24,15,24,26);l(10,26,38,26);l(10,26,10,34);l(38,26,38,34);}
 if(name==='file'){r(10,4,29,40,'rect');l(17,15,31,15);l(17,23,31,23);l(17,31,26,31);}
 if(name==='stop'){r(5,5,38,38,'ellipse');r(17,17,14,14,'rect');}
}
function node(s,title,detail,x,y,w,h,{fill=C.white,color=C.ink,accent=C.teal}={}){
 const n=shape(s,'roundRect',x,y,w,h,fill,C.line,1);n.adjustmentList=[{name:'adj',formula:'val 7000'}];shape(s,'rect',x,y+13,3,h-26,accent);
 text(s,title,x+20,y+15,w-40,40,24,color,true);if(detail)text(s,detail,x+20,y+57,w-40,h-61,19,color===C.white?'#C3D3CF':C.muted);return n;
}
async function img(s,file,x,y,w,h){const b=await fs.readFile(path.join(root,file));return s.images.add({blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:'松鼠备份真实应用运行截图',fit:'contain',position:{left:x,top:y,width:w,height:h}});}
function table(s,rows,widths,x,y,heights,size=24){
 const t=s.tables.add({rows:rows.length,columns:widths.length,left:x,top:y,width:widths.reduce((a,b)=>a+b),height:heights.reduce((a,b)=>a+b),columnWidths:widths,values:rows});
 t.borders.assign({fill:C.line,width:.65});t.cells.block({row:0,column:0,rowCount:rows.length,columnCount:widths.length}).assign({fill:C.paper,textStyle:{typeface:font,fontSize:size,color:C.ink,alignment:'left'},margins:{left:18,right:18,top:10,bottom:10},anchor:'center'});
 for(let r=0;r<rows.length;r++){t.rows[r].height=heights[r];for(let c=0;c<widths.length;c++){const cell=t.getCell(r,c);cell.text.style={typeface:font,fontSize:size,bold:r===0,color:r===0?C.teal:C.ink,alignment:'left',verticalAlignment:'middle'};cell.fill=r===0?C.pale:C.paper;}}return t;
}

let s=slide('','','项目版本0.2.0。来源：VERSION、README.md。',true);
text(s,'软件开发综合实验',64,48,650,40,23,'#B5C9C3');text(s,'松鼠备份',62,186,685,115,81,C.white,true);
text(s,'本地文件备份与恢复',67,316,660,60,35,'#CDDDD4');ln(s,67,405,83,C.gold,3);text(s,'SQUIRREL BACKUP',67,433,620,47,26,'#B4C8C2',false,'left',numberFont);
shape(s,'roundRect',876,185,278,292,'#2B474C','#54716C',1);shape(s,'roundRect',821,220,278,292,'#36534F','#69887A',1);shape(s,'roundRect',766,255,278,292,'#E6E7D8');shape(s,'roundRect',766,232,110,48,'#E6E7D8');
icon(s,'archive',841,315,116,C.teal);ln(s,821,459,172,'#B7C4B5',2);shape(s,'ellipse',1001,455,94,94,C.orange);icon(s,'check',1024,478,48,C.white);text(s,'0.2.0',1058,549,155,38,25,'#B5C9C3',false,'left',numberFont);
ln(s,66,591,1147,'#4A615E');text(s,'第 3 组',67,615,110,36,23,'#CFB98E');text(s,'杨梦宇   2023150901002   组长',217,609,700,31,21,'#E0E8E2');text(s,'郭畅       2023040904017',217,644,500,31,21,'#E0E8E2');text(s,'李想   2023150901012',753,644,470,31,21,'#E0E8E2');

s=slide('汇报目录','汇报结构','结构参考用户提供的自然保护地PPT，仅借鉴目录与页眉层次。');
for(const [i,title,detail,ico,color]of [[1,'功能与使用','备份、验证、恢复与自动任务','folder',C.teal],[2,'设计与实现','共享核心、归档算法与安全恢复','tree',C.orange],[3,'验证与协作','分层测试、职责分工与版本演进','check',C.teal]]){
 const y=198+(i-1)*145;text(s,String(i).padStart(2,'0'),66,y-4,112,72,49,color,false,'left',numberFont);text(s,title,211,y,820,48,33,color,true);text(s,detail,213,y+58,860,38,25,C.muted);icon(s,ico,1125,y+16,53,color);if(i<3)ln(s,211,y+113,974);
}

s=slide('本地目录的备份与恢复','01  功能与使用','截图：docs/screenshots/desktop/21-neutral-backup.png。功能对应docs/01与include/squirrel/backup.h。');
const featureRows=[['file','保留文件结构','文件、空目录、软硬链接与 FIFO'],['layers','组合筛选','路径、类型、名称、时间、大小、UID'],['lock','压缩与密码保护','分块压缩，备份文件独立验证']];
for(let i=0;i<featureRows.length;i++){const [ico,title,body]=featureRows[i],y=185+i*133;icon(s,ico,65,y+2,42,i===1?C.orange:C.teal);text(s,title,126,y,390,42,28,C.ink,true);text(s,body,126,y+49,387,65,22,C.muted);}
shape(s,'roundRect',554,176,656,451,C.white,C.line,1);await img(s,'docs/screenshots/desktop/21-neutral-backup.png',567,187,630,419);
for(const [i,v]of ['源目录','备份文件','恢复目录'].entries()){text(s,v,85+i*167,615,150,37,22,C.teal,true);if(i<2)ln(s,211+i*167,632,31,C.gold,2);}

s=slide('自动任务与快照保留','01  功能与使用','src/scheduler.cpp。桌面G07/G08/G09真实验证定时3秒、保留2份、目录变化和停止。');
icon(s,'clock',66,182,49);text(s,'定时备份',139,185,435,45,31,C.ink,true);text(s,'按设定间隔创建完整快照',140,243,450,42,24,C.muted);icon(s,'layers',696,182,49,C.orange);text(s,'目录变化检测',771,185,440,45,31,C.ink,true);text(s,'轮询目录，变化稳定后再备份',772,243,443,65,24,C.muted);vertical(s,641,179,124);ln(s,66,337,1150);
text(s,'保留最近 2 份',66,375,540,50,32,C.teal,true);text(s,'每次启动使用独立任务目录',67,434,580,40,24,C.muted);
[['01','已淘汰',C.muted],['02','保留',C.teal],['03','最新快照',C.orange]].forEach(([n,t,c],i)=>{let x=642+i*184;icon(s,'archive',x+26,377,63,c);text(s,n,x+36,458,82,45,29,c,false,'left',numberFont);text(s,t,x,514,158,35,21,c,false,'center');if(i<2)ln(s,x+112,410,57,C.line,2);});
shape(s,'rect',66,580,1150,52,C.pale);text(s,'停止任务后，已完成快照继续保留',88,589,1103,38,25,C.teal,true);

s=slide('一套核心，连接三种入口','02  设计与实现','src/service.cpp、scanner.cpp、archive.cpp、scheduler.cpp、gui.mm；Makefile、.clang-format、scripts/check_style.py。');
const xs=[65,466,866];[['Cocoa GUI','原生图形界面'],['CLI','命令行操作'],['Scheduler','定时与变化检测']].forEach((r,i)=>node(s,...r,xs[i],172,350,103));
node(s,'BackupService','backup   /   inspect   /   restore',384,325,512,110,{fill:C.navy,color:C.white,accent:C.gold});for(const x of xs)vertical(s,x+175,275,26,C.teal,1.6);ln(s,240,301,801,C.teal,1.6);vertical(s,640,301,24,C.teal,1.6);
vertical(s,640,435,31,C.teal,1.6);ln(s,201,466,879,C.teal,1.6);
[['FileScanner','扫描与筛选'],['Archive','目录树读写'],['HuffmanCodec','分块压缩'],['CryptoEnvelope','密码封装']].forEach((r,i)=>{vertical(s,201+i*293,466,25,C.teal,1.6);node(s,...r,65+i*293,491,270,101);});
ln(s,65,621,1150);text(s,'C++17   /   macOS arm64   /   Apple Clang 14.0.3',65,636,740,32,20,C.muted);text(s,'Git   +   cpplint',918,636,297,32,20,C.teal,true,'right');

s=slide('归档封装与算法选择','02  设计与实现','src/archive.cpp、huffman.cpp、crypto.cpp、THIRD_PARTY.md。Huffman自研，PBKDF2/AES/HMAC调用CommonCrypto与Security。');
text(s,'SQBK',66,174,330,67,47,C.teal,true,'left',numberFont);text(s,'备份文件封装',254,189,440,40,25,C.muted);shape(s,'roundRect',65,258,539,333,C.pale,C.line,1);text(s,'SQTREE  目录树',91,282,465,42,29,C.ink,true);
[['类型 / 路径','文件元数据'],['数据块','长度与编码'],['结束标志','完整性校验']].forEach((r,i)=>{const y=355+i*67;icon(s,i===0?'tree':i===1?'layers':'check',93,y,31,C.teal);text(s,r[0],145,y-1,221,36,23,C.ink,true);text(s,r[1],363,y,207,34,21,C.muted);if(i<2)ln(s,145,y+44,420);});
[['01','分块压缩','Huffman 按 1 MiB 编码\n压缩收益不足时保留原始块'],['02','密码保护','PBKDF2 派生密钥\nAES-256-CBC 与 HMAC-SHA256'],['03','处理顺序','备份先压缩、再加密\n恢复先认证、再解密']].forEach(([n,t,b],i)=>{const y=182+i*150;text(s,n,662,y-5,78,52,36,i===1?C.orange:C.teal,false,'left',numberFont);text(s,t,755,y,450,43,29,C.ink,true);text(s,b,756,y+52,453,77,23,C.muted);});
ln(s,66,619,1150);text(s,'自定义归档格式与 Huffman 编码',66,635,630,33,20,C.teal);text(s,'密码原语使用系统库',830,635,385,33,20,C.muted,false,'right');

s=slide('恢复流程与取消处理','02  设计与实现','src/service.cpp、archive.cpp及tests/core_test.cpp。真实桌面G05/G06/G09/G10覆盖不覆盖、错误密码、取消与退出。');
[['lock','认证与校验','确认密码和归档完整性'],['archive','暂存目录解包','在独立目录写入数据'],['file','恢复元数据','恢复权限、时间与链接'],['check','发布新目录','完整结果一次性可见']].forEach(([ico,t,b],i)=>{let x=66+i*294;icon(s,ico,x,185,47,i===3?C.orange:C.teal);text(s,String(i+1).padStart(2,'0'),x+67,183,72,54,36,C.muted,false,'left',numberFont);text(s,t,x,270,270,46,28,C.ink,true);text(s,b,x,331,268,67,22,C.muted);if(i<3)ln(s,x+156,208,104,C.line,2);});
ln(s,66,428,1150);icon(s,'stop',67,473,52,C.orange);text(s,'取消请求进入各处理阶段',142,471,1070,43,29,C.ink,true);text(s,'扫描、分块读写、元数据与发布前均检查取消标志',143,529,1000,39,24,C.muted);shape(s,'rect',144,594,5,39,C.gold);text(s,'清理未完成暂存，保留已发布的备份',169,596,1030,41,26,C.teal,true);

s=slide('分层测试与桌面验收','03  验证与协作','test-results/summary.json、gui-selftest.json、gui-desktop-acceptance.json、compatibility-020.json、sanitize-020.log。97不包含另外53项内部断言或12项桌面场景。');
text(s,String(summary.passed),66,170,405,142,109,C.teal,true,'left',numberFont);text(s,'项命名自动测试通过',69,322,468,45,29,C.ink,true);text(s,'ASan / UBSan 复测通过\n新旧版本双向恢复通过',70,399,470,96,25,C.muted);
table(s,[['测试层次','用例'],['单元测试','52'],['CLI 集成','21'],['异常归档与并发','18'],['工作流回归','6']],[452,152],609,180,[51,62,62,62,62],24);ln(s,67,552,1148);
[['53','GUI 内部断言'],['12','桌面操作场景'],['4','新旧版恢复组合']].forEach(([n,l],i)=>{let x=67+i*394;text(s,n,x,577,105,62,46,i===1?C.orange:C.teal,true,'left',numberFont);text(s,l,x+115,592,278,44,23,C.ink);});

s=slide('模块分工与交叉复核','03  验证与协作','docs/07_三人分工与协作方案.md。此表描述均衡主责，历史作者以真实Git记录为准。');
table(s,[['成员','主责模块','配套工作'],['杨梦宇','扫描、筛选、安全恢复、CLI','需求与用例、文件测试'],['郭畅','归档、Huffman、密码封装','设计与类图、算法测试'],['李想','GUI、自动任务、构建发布','测试汇总、动态建模']],[187,555,412],66,184,[58,93,93,93],25);ln(s,67,570,1148);text(s,'共同复核',66,596,190,41,28,C.teal,true);
['代码与接口','恢复结果','文档与演示'].forEach((v,i)=>{icon(s,'check',313+i*297,598,32,i===1?C.orange:C.teal);text(s,v,360+i*297,598,237,38,24,C.ink);});

s=slide('版本演进与开发记录','03  验证与协作','Git真实提交：69a2839(00:06)、dbde327(10:10)、b2b5bb9(12:56)、49300b7(17:24)、ba711cf(19:30)，均为2026-10-29。甘特条表示同类提交首末记录的区间。基线00:06–01:25，修复10:10–12:56，验证13:10–17:24，文档16:04–19:30。');
[['0.1.0','备份与恢复基线'],['0.1.1','恢复权限、变化检测'],['0.2.0','取消、进度与回归']].forEach(([v,t],i)=>{let x=66+i*393;text(s,v,x,170,275,64,43,i===2?C.orange:C.teal,true,'left',numberFont);text(s,t,x,242,370,40,25,C.ink);if(i<2)ln(s,x+229,200,118,C.line,2);});
ln(s,66,311,1150);text(s,'开发记录甘特图',66,337,600,45,28,C.ink,true);text(s,'10 / 29',992,342,220,35,22,C.muted,false,'right',numberFont);
const gx=294,gy=424,unit=43;for(const hour of [0,4,8,12,16,20]){const x=gx+hour*unit;vertical(s,x,412,217,C.line,.8);text(s,String(hour).padStart(2,'0')+':00',x-24,382,87,27,17,C.muted,false,'left',numberFont);}
[['程序基线',.1,1.43,C.teal],['修复与增强',10.17,12.93,C.teal],['测试与封装',13.17,17.4,C.orange],['文档与协作',16.07,19.5,C.gold]].forEach(([label,start,end,c],i)=>{const y=gy+i*52;text(s,label,66,y-2,209,39,24,C.ink);shape(s,'roundRect',gx+start*unit,y+3,(end-start)*unit,23,c);});

s=slide('现场演示','03  验证与协作','截图：docs/screenshots/desktop/23-neutral-restored.png。操作顺序参见docs/06。本页结束三分钟讲解，随后按课程安排实际操作。');
shape(s,'roundRect',65,171,748,457,C.white,C.line,1);await img(s,'docs/screenshots/desktop/23-neutral-restored.png',78,183,722,433);
[['01','创建加密备份'],['02','验证并恢复'],['03','检查错误密码'],['04','任务保留与停止']].forEach(([n,t],i)=>{let y=190+i*98;text(s,n,856,y-5,70,45,30,i===2?C.orange:C.teal,false,'left',numberFont);text(s,t,935,y,280,46,27,C.ink,true);if(i<3)ln(s,934,y+65,275);});text(s,'备份可验证，恢复有依据',856,601,363,42,25,C.teal,true);

const speech=JSON.parse(await fs.readFile(path.join(root,'presentations/讲稿数据.json')));
if(speech.length!==p.slides.items.length)throw new Error('Speech count differs from slide count');
for(let i=0;i<speech.length;i++)p.slides.items[i].speakerNotes.text=`${speech[i].speaker}，约${speech[i].seconds}秒。\n\n${speech[i].text}\n\n资料来源：${notes[i].note}`;
await fs.writeFile(path.join(build,'演示讲稿.md'),'# 松鼠备份三分钟讲稿\n\n共11页，计划180秒，包含切页与停顿。\n\n'+notes.map((x,i)=>`## 第${i+1}页 ${x.title} · ${speech[i].speaker} · ${speech[i].seconds}秒\n\n${speech[i].text}\n`).join('\n'));
await (await PresentationFile.exportPptx(p)).save(path.join(build,'candidate.pptx'));
for(const [i,s]of p.slides.items.entries()){const name=`slide-${String(i+1).padStart(2,'0')}`;await fs.writeFile(path.join(build,name+'.png'),new Uint8Array(await (await p.export({slide:s,format:'png',scale:1})).arrayBuffer()));await fs.writeFile(path.join(build,name+'.layout.json'),await (await s.export({format:'layout'})).text());}
console.log(JSON.stringify({candidate:path.join(build,'candidate.pptx'),slides:p.slides.items.length,fonts:[font,numberFont]},null,2));
