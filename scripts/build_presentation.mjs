import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL,fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const modules=process.env.ARTIFACT_NODE_MODULES;
if(!modules)throw new Error('Set ARTIFACT_NODE_MODULES to the supplied artifact runtime modules.');
const {Presentation,PresentationFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool',{paths:[modules]})).href);
const root=path.resolve(process.env.SQUIRREL_ROOT||path.join(path.dirname(fileURLToPath(import.meta.url)),'..'));
const build=path.resolve(process.env.PPT_BUILD_DIR||path.join(root,'.preflight/ppt-build'));
await fs.mkdir(build,{recursive:true});
const summary=JSON.parse(await fs.readFile(path.join(root,'test-results/summary.json')));
const gui=JSON.parse(await fs.readFile(path.join(root,'test-results/gui-selftest.json')));
const p=Presentation.create({slideSize:{width:1280,height:720}});
const C={paper:'#F7F6F2',ink:'#222D32',muted:'#667274',accent:'#AC4B30',teal:'#386B6C',line:'#B8C2C1',white:'#FFFFFF'};
const font='PingFang SC';const notes=[];
function text(s,value,x,y,w,h,size=28,color=C.ink,bold=false,align='left'){
 const v=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 v.text=value;v.text.style={typeface:font,fontSize:size,bold,color,alignment:align,verticalAlignment:'top',wrap:"square",lineSpacing:1.18,insets:0};return v;
}
function line(s,x,y,w,color=C.line){s.shapes.add({geometry:'line',position:{left:x,top:y,width:w,height:0},line:{fill:color,width:1.2}});}
function slide(title,note,dark=false){
 const s=p.slides.add();s.background.fill=dark?C.ink:C.paper;
 if(title)text(s,title,64,45,1148,70,44,dark?C.white:C.ink,true);
 if(p.slides.items.length>1)text(s,String(p.slides.items.length).padStart(2,'0'),1175,661,45,28,19,dark?'#CCD4D2':C.muted,false,'right');
 s.speakerNotes.text=note;notes.push({title:title||'松鼠备份',note});return s;
}
function box(s,label,x,y,w,h,color=C.paper,size=26){
 const v=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:color,line:{fill:C.teal,width:1.5}});
 v.text=label;v.text.style={typeface:font,fontSize:size,color:C.ink,alignment:'center',verticalAlignment:'middle',insets:12,lineSpacing:1.16};return v;
}
function arrow(s,a,b,from='right',to='left'){
 return s.shapes.connect(a,b,{kind:'straight',fromSide:from,toSide:to,line:{fill:C.teal,width:2},tail:{type:'triangle',width:'sm',length:'sm'}});
}
async function img(s,file,x,y,w,h){const b=await fs.readFile(path.join(root,file));return s.images.add({blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:'松鼠备份 0.2.0 真实应用离屏运行状态',fit:'contain',position:{left:x,top:y,width:w,height:h}});}
function table(s,rows,widths,x,y,heights,size=25){
 const t=s.tables.add({rows:rows.length,columns:widths.length,left:x,top:y,width:widths.reduce((a,b)=>a+b),height:heights.reduce((a,b)=>a+b),columnWidths:widths,values:rows});
 t.borders.assign({fill:C.line,width:.8});
 t.cells.block({row:0,column:0,rowCount:rows.length,columnCount:widths.length}).assign({fill:C.paper,textStyle:{typeface:font,fontSize:size,color:C.ink,alignment:'left'},margins:{left:14,right:14,top:10,bottom:10},anchor:'center'});
 for(let r=0;r<rows.length;r++){t.rows[r].height=heights[r];for(let c=0;c<widths.length;c++){
 const cell=t.getCell(r,c);cell.text.style={typeface:font,fontSize:size,bold:r===0,color:r===0?C.white:C.ink,alignment:'left',verticalAlignment:'middle'};cell.fill=r===0?C.ink:C.paper;
 }}return t;
}
let s=slide('', '10秒。杨梦宇：我们第3组的项目是松鼠备份，目标是把本机目录保存成可验证、可安全恢复的归档。当前演示版本为0.2.0，使用C++核心与macOS原生界面。',true);
text(s,'松鼠备份',72,154,1100,110,78,C.white,true);
text(s,'Squirrel Backup  0.2.0',77,280,1000,60,34,'#B7C9C5');
text(s,'软件开发综合实验 · 第3组',77,393,1120,50,29,'#E4B29B');
text(s,'杨梦宇  2023150901002  组长\n郭畅     2023040904017\n李想     2023150901012',78,505,1060,142,25,C.white);
s=slide('本地目录备份与恢复','20秒。杨梦宇：从一个目录生成单个备份文件，再恢复到新目录。可选六类筛选、压缩和密码保护。自动任务定时创建完整快照，也能轮询目录变化。已有备份与恢复目录不会被覆盖。截图来源：docs/screenshots/01-backup-completed.png，后台调用真实AppKit操作处理流程，未操作系统文件选择器。');
text(s,'目录 → 归档 → 新目录',64,151,1120,55,34,C.accent,true);
text(s,'保留软硬链接、FIFO\n以及基础文件元数据',65,245,430,104,29);
text(s,'路径、类型、名称、时间、\n大小、UID组合筛选',65,377,430,104,29);
text(s,'定时快照与目录变化检测\n按任务保留最近N份',65,509,430,104,29);
await img(s,'docs/screenshots/01-backup-completed.png',580,206,627,459);
s=slide('共享核心与模块职责','25秒。杨梦宇：GUI和CLI都调用BackupService，调度器也复用它。扫描、归档格式、压缩、密码封装分开承担职责。Operation传入停止标志和进度回调，工作线程不直接修改AppKit控件。对应源码：include/squirrel/backup.h、src/service.cpp、src/scheduler.cpp、src/gui.mm；完整UML见docs/uml/SquirrelBackup.mdj。');
const guiBox=box(s,'Cocoa GUI',76,168,244,76),cliBox=box(s,'CLI',76,281,244,76),schedule=box(s,'Scheduler\n定时 / 轮询',76,394,244,98);
const service=box(s,'BackupService\nbackup / inspect / restore',418,273,423,120,'#E5EEEB',29);
arrow(s,guiBox,service);arrow(s,cliBox,service);arrow(s,schedule,service);
const scan=box(s,'FileScanner\n扫描与筛选',939,149,264,84),archive=box(s,'ArchiveWriter\nArchiveReader',939,268,264,105,C.paper,23),codec=box(s,'HuffmanCodec\n分块压缩',939,408,264,84),crypto=box(s,'CryptoEnvelope\n摘要 / 认证加密',939,527,264,84);
arrow(s,service,scan);arrow(s,service,archive);arrow(s,archive,codec,'bottom','top');arrow(s,service,crypto);
text(s,'Operation：协作取消与阶段进度',416,469,457,82,27,C.teal,true);
text(s,'C++17 · macOS 13.0 arm64 · Apple Clang 14.0.3',65,636,1075,32,22,C.muted);
s=slide('归档格式与算法选择','20秒。郭畅：SQBK是外层封装，SQTREE描述目录树。Huffman按1MiB分块处理，压缩没有收益就保存原始块，单符号和空块单独处理。密码保护使用系统库完成PBKDF2、AES和HMAC，项目实现封装与边界检查，不把系统密码算法说成自研。源码：src/archive.cpp、src/huffman.cpp、src/crypto.cpp；依赖声明：THIRD_PARTY.md。');
table(s,[['部分','实现','依赖'],['文件树归档','自定义SQBK / SQTREE\n明确长度、类型与结束标志','项目实现'],['Huffman压缩','1 MiB分块；收益不足回退原始块','项目实现'],['密码封装','PBKDF2 + AES-256-CBC\nHMAC-SHA256认证','CommonCrypto\nSecurity']],[215,610,320],65,159,[55,112,105,124],25);
text(s,'先压缩，再加密；恢复时先认证，再解密',68,591,1120,50,31,C.accent,true);
s=slide('安全恢复与停止操作','25秒。郭畅：恢复先完成验证，再写私有暂存目录，恢复元数据后以不覆盖方式发布。错误密码、畸形路径和取消都应清理暂存，不留下貌似完成的目录。0.2.0增加阶段取消和发布前源目录复查；读取后的变化仍可能发生，所以它不等于文件系统原子快照。源码：src/service.cpp、src/archive.cpp、src/scanner.cpp；回归：tests/core_test.cpp。');
text(s,'恢复路径',66,155,1100,40,29,C.accent,true);
const steps=['认证与校验','私有目录解包','恢复元数据','不覆盖发布'];const nodes=steps.map((v,i)=>box(s,v,66+i*293,223,255,89,i===3?'#E5EEEB':C.paper,27));
for(let i=0;i<3;i++)arrow(s,nodes[i],nodes[i+1]);
text(s,'失败或取消：清理暂存，保留原备份',66,362,1130,52,33,C.teal,true);
line(s,66,449,1140);
text(s,'停止检查进入扫描、分块读写、元数据与发布前阶段。\n备份发布前重新扫描，发现源目录变化则拒绝发布。',66,488,1140,115,29);
text(s,'能力边界：不提供多文件事务快照或断电持久性保证',66,632,1120,34,22,C.muted);
s=slide('当前版本测试结果','25秒。李想：97是命名自动测试用例数量，四层相加为97，Sanitizer重复执行不额外计数。GUI53项是内部断言，单独报告。新旧版本明文与加密的双向恢复共4种组合通过。20小时定时和watch联合测试尚在运行，最终数值以报告刷新为准；系统选择器仍需人工检查。来源：test-results/summary.json、gui-selftest.json、compatibility-020.json、sanitize-020.log。');
text(s,`${summary.passed} / ${summary.total}`,65,155,485,126,85,C.accent,true);
text(s,'命名自动测试通过',69,291,470,44,30);
text(s,'ASan / UBSan复测通过\n旧版与新版双向恢复：4种组合',69,388,480,110,25);
table(s,[['测试层次','通过'],['单元测试','52'],['CLI集成','21'],['异常归档与并发','18'],['工作流回归','6']],[470,140],604,162,[51,65,65,65,65],25);
text(s,'另有53项GUI内部断言；系统文件选择器仍待人工验收。',69,562,1135,42,25);
text(s,'20小时持续测试正在运行，未记为通过。',69,615,1135,40,25,C.muted);
s=slide('三人职责与复核安排','20秒。李想：按文件与恢复、格式与算法、界面与任务分配，每人30个相对工作量点，均承担代码、测试、文档与演示。这里是接手与复核安排，不把自动生成或自动执行内容写成个人已完成工作。实际贡献以三人确认和后续提交记录为准。来源：docs/07_三人分工与协作方案.md。');
table(s,[['成员','主责模块','配套工作'],['杨梦宇','扫描、筛选、安全恢复、CLI','需求与用例、文件测试'],['郭畅','归档、Huffman、密码封装','设计与类图、算法测试'],['李想','GUI、自动任务、构建发布','测试汇总、动态建模']],[205,565,375],65,157,[56,96,96,96],26);
text(s,'每人30点：实现14 + 测试5 + 文档建模5 + 复核演示6',65,548,1140,52,28,C.accent,true);
text(s,'交叉复核：杨梦宇 → 郭畅 → 李想 → 杨梦宇',65,618,1140,40,25,C.muted);
s=slide('答辩前推进计划','15秒。李想：以10月29日为起点安排接手复现、真实界面验收、材料复核和排练，11月18日答辩。甘特图是后续计划，尚未发生的日期不写成完成记录。在线Git仓库需要成员账号完成发布，个人证书各自完成。来源：课程9.pdf第38至40页，docs/planning/后续计划.csv及docs/10_学习证书办理说明.md。');
const gx=367,gy=225,unit=39,rows=[['接手与复现',0,3],['界面与边界验收',3,5],['文档与模型复核',8,4],['演示与答辩排练',12,5],['最终检查与提交准备',17,3]];
for(const [label,day]of[['10/29',0],['11/1',3],['11/6',8],['11/10',12],['11/15',17],['11/18',20]]){text(s,label,gx+day*unit-28,161,88,40,23,C.muted);s.shapes.add({geometry:'line',position:{left:gx+day*unit,top:211,width:0,height:359},line:{fill:'#DDE2DF',width:1}});}
for(let i=0;i<rows.length;i++){const[label,start,duration]=rows[i];text(s,label,67,gy+i*70,283,43,26);s.shapes.add({geometry:'rect',position:{left:gx+start*unit,top:gy+i*70+5,width:duration*unit-5,height:30},fill:C.teal,line:{fill:'none',width:0}});}
text(s,'2026年11月18日上午答辩；当日23:59前提交成电慕课',66,618,1150,40,26,C.accent,true);
s=slide('现场演示：验证后恢复到新目录','20秒。杨梦宇：现场从准备好的独立数据目录开始，展示备份、验证、恢复和原文件哈希比对，再展示错误密码与任务保留、停止。不会使用个人真实文件。PPT讲解控制3分钟，现场操作7分钟，提交视频不超过2分钟。程序尚不支持网络、增量、系统守护与重启续跑。截图来源：docs/screenshots/03-restored.png，真实应用离屏状态。');
await img(s,'docs/screenshots/03-restored.png',64,161,731,535);
text(s,'1  创建加密备份\n\n2  验证并恢复\n\n3  检查错误密码\n\n4  展示任务保留与停止',835,181,390,375,27);
text(s,'本地完整备份\n暂不支持网络、增量与后台常驻',835,583,380,85,22,C.muted);
const speech=JSON.parse(await fs.readFile(path.join(root,'presentations/讲稿数据.json')));
for(let i=0;i<speech.length;i++) {
 const source=notes[i].note;
 notes[i].note=`${speech[i].speaker}，约${speech[i].seconds}秒。\n\n${speech[i].text}\n\n备查说明（不朗读）：${source}`;
 p.slides.items[i].speakerNotes.text=notes[i].note;
}
await fs.writeFile(path.join(build,'演示讲稿.md'),'# 松鼠备份三分钟讲稿\n\n总计约180秒；实际朗读后微调。\n\n'+notes.map((x,i)=>`## 第${i+1}页 ${x.title} · ${speech[i].speaker} · ${speech[i].seconds}秒\n\n${speech[i].text}\n`).join('\n'));
await (await PresentationFile.exportPptx(p)).save(path.join(build,'candidate.pptx'));
for(const [i,s]of p.slides.items.entries()){
 const name=`slide-${String(i+1).padStart(2,'0')}`;
 await fs.writeFile(path.join(build,name+'.png'),new Uint8Array(await (await p.export({slide:s,format:'png',scale:1})).arrayBuffer()));
 await fs.writeFile(path.join(build,name+'.layout.json'),await (await s.export({format:'layout'})).text());
}
console.log(JSON.stringify({candidate:path.join(build,'candidate.pptx'),slides:p.slides.items.length,font},null,2));
