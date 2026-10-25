#!/usr/bin/env python3
"""Fail-closed LEMMIQ V2.12 source updater.
Runs in Windows CMD as: py -3 APPLY_V2.12.py --repo C:/Users/pc/LEMMIQ --dry-run
No destructive schema changes, no edits to v28.py, Q earning rules or USDT withdrawal logic.
"""
from __future__ import annotations
import argparse
import datetime
from pathlib import Path
import re
import shutil
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / 'payload'
VERSION = '2.12.0'

class Incompatible(RuntimeError): pass

def require(value, message):
    if not value: raise Incompatible(message)

def insert_once(txt, marker, content, label):
    if content.strip() in txt: return txt
    require(txt.count(marker) == 1, f'{label}: missing or ambiguous anchor: {marker[:45]}')
    return txt.replace(marker, content + marker, 1)

def patch_main(txt):
    require('app = FastAPI(title="LEMMIQ Server"' in txt, 'main.py: unexpected FastAPI constructor')
    pattern=r'(app\s*=\s*FastAPI\(title="LEMMIQ Server",\s*version=")[^"]+("\))'
    txt,n=re.subn(pattern,lambda m:m.group(1)+VERSION+m.group(2),txt,count=1)
    require(n==1,'main.py: version anchor not found')
    txt,n=re.subn(r'("version":\s*")[\d.]+("\s*,)',lambda m:m.group(1)+VERSION+m.group(2),txt)
    require(n>=1, 'main.py: health/app-config version not found')
    new='''# ---------------- LEMMIQ V2.12 — Q AI Image Generation ----------------
from .v212_image_gen import register_v212_images
register_v212_images(app, current_user, get_db, push, msg_json, push_tokens, unread_count_for_user)

'''
    if 'register_v212_images(app,' not in txt:
        txt=insert_once(txt,'# ---------------- LEMMIQ V2 WEB / PWA ----------------',new,'main.py image router')
    return txt

def patch_q_feature(txt):
    if '"Q_IMAGE": "Q Create Image"' not in txt:
        txt=insert_once(txt,'    "Q_VISION": "Q Vision",','    "Q_IMAGE": "Q Create Image",\n', 'Q feature catalog')
    if '"Q_IMAGE": 0.00' not in txt:
        txt=insert_once(txt,'    "Q_VISION": 2.00,','    "Q_IMAGE": 0.00,  # Disabled monetisation until admin sets price; feature flag is separately OFF\n','Q price defaults')
    return txt

def patch_index(txt):
    if '/web/v212_image_gen.css' not in txt:
        txt=insert_once(txt,'</head>','  <link rel="stylesheet" href="/web/v212_image_gen.css?v=2.12.0">\n','PWA CSS')
    if '/web/v212_image_gen.js' not in txt:
        txt=insert_once(txt,'</body>','  <script src="/web/v212_image_gen.js?v=2.12.0" defer></script>\n','PWA JS')
    return txt

def patch_sw(txt):
    require('const CACHE = ' in txt, 'SW: cannot locate existing cache')
    txt,n=re.subn(r'const CACHE\s*=\s*"[^"]+";', 'const CACHE = "lemmiq-v212-shell-1";', txt, count=1)
    require(n==1,'SW cache mismatch')
    if '/web/v212_image_gen.js' not in txt:
        txt=insert_once(txt,'  "/web/manifest.webmanifest",',
          '  "/web/v212_image_gen.js?v=2.12.0",\n  "/web/v212_image_gen.css?v=2.12.0",\n','SW asset list')
    if '"/v212"' not in txt:
        txt=insert_once(txt,'const API_PREFIXES=[','', 'SW API list')
        txt=txt.replace('const API_PREFIXES=[','const API_PREFIXES=["/v212",',1)
    return txt

def patch_gradle(txt):
    pattern=r'(?m)^(\s*versionCode\s*=\s*)(\d+)(\s*)$'
    hits=re.findall(pattern,txt)
    require(len(hits)==1,'Android gradle versionCode mismatch')
    current=int(hits[0][1]);require(current<=62,f'Existing versionCode {current} is newer than V2.12 package 62')
    txt=re.sub(pattern,lambda m: m.group(1)+'62'+m.group(3),txt,count=1)
    pattern=r'(?m)^(\s*versionName\s*=\s*)"[^"]+"(\s*)$'
    txt,n=re.subn(pattern,lambda m:m.group(1)+'"2.12.0"'+m.group(2),txt,count=1)
    require(n==1,'Android versionName mismatch')
    return txt

def patch_android_ui(txt):
    # Inject within the known Chat() scope. Markers are checked as anchors before writing.
    if 'var showAiImageV212 by remember(c.id)' not in txt:
        txt=insert_once(txt,'    var settings by remember{mutableStateOf(false)}',
             '    var showAiImageV212 by remember(c.id){mutableStateOf(false)}\n','Android Chat image state')
    if 'V212ImageDialog(chatId=c.id' not in txt:
        txt=insert_once(txt,'    vm.chatSummary?.let{s->ChatSummaryDialog(s){vm.clearChatSummary()}}',
          '    if(showAiImageV212) V212ImageDialog(chatId=c.id, onClose={showAiImageV212=false},\n' +
          '        onSent={vm.open(c)})\n','Android image dialog')
    if 'showAiImageV212=true' not in txt:
        txt=insert_once(txt,'TextButton({videoPicker.launch("video/*");showAttach=false}){Text("🎬 Video")}',
          'TextButton({showAiImageV212=true;showAttach=false}){Text("🎨 Q Image")}\n                                ',
          'Android attachments menu')
    if 'var showQImageV212 by remember' not in txt:
        txt=insert_once(txt,'    var showVisionHistory by remember{mutableStateOf(false)}',
          '    var showQImageV212 by remember{mutableStateOf(false)}\n','Android Q image state')
    if 'V212ImageDialog(onClose={showQImageV212=false}' not in txt:
        txt=insert_once(txt,'    val qChargingOn=vm.qFeatureCatalog.any{it.charging_enabled}',
          '    if(showQImageV212) V212ImageDialog(onClose={showQImageV212=false}, onSent={vm.refreshAgent()})\n',
          'Android Q dialog')
    if 'showQImageV212=true' not in txt:
        new='''        item{
            Card(Modifier.fillMaxWidth().padding(horizontal=20.dp),shape=RoundedCornerShape(20.dp)){
                Row(Modifier.fillMaxWidth().padding(16.dp),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text("Q Create Image",fontWeight=FontWeight.Bold,fontSize=17.sp)
                        Text("Prompt Q to create an image; review before sharing.",fontSize=11.sp,color=Muted)
                    }
                    TextButton(onClick={showQImageV212=true}){Text("🎨 Create")}
                }
            }
        }

'''
        txt=insert_once(txt,'        item{\n            val pending=vm.qHome?.q_to_q?.pending_count ?: 0',new,'Android Q image card')
    return txt

PATCHES={
 'backend/app/main.py':patch_main,
 'backend/app/v2105_q_features.py':patch_q_feature,
 'backend/web/index.html':patch_index,
 'backend/web/sw.js':patch_sw,
 'android/app/build.gradle.kts':patch_gradle,
 'android/app/src/main/java/com/lemmiq/app/LemmiqApp.kt':patch_android_ui,
}

COPY_FILES=[
 'backend/app/v212_image_gen.py',
 'backend/web/v212_image_gen.js',
 'backend/web/v212_image_gen.css',
 'android/app/src/main/java/com/lemmiq/app/V212ImageGen.kt',
]

def prepare(repo):
    require(repo.is_dir(),'LEMMIQ repository directory not found')
    require((repo/'backend/app/v28.py').is_file(),'Repository lacks Q wallet baseline v28.py')
    edits={}
    for path, fn in PATCHES.items():
        target=repo/path
        require(target.is_file(),f'Missing required file {path}')
        old=target.read_text(encoding='utf-8')
        new=fn(old)
        if new!=old:edits[path]=new.encode('utf-8')
    for path in COPY_FILES:
        src=PAYLOAD/path;require(src.is_file(),f'Package missing {path}')
        target=repo/path
        if target.exists():
            old=target.read_bytes();require(old==src.read_bytes(), f'Refusing overwrite existing modified {path}')
        else:edits[path]=src.read_bytes()
    return edits

def apply(repo, changes):
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=repo/f'BACKUP_BEFORE_V212_{stamp}.zip'
    with ZipFile(backup,'w',ZIP_DEFLATED) as z:
        for path in sorted(changes):
            target=repo/path
            if target.exists():z.write(target,arcname=path)
    # All preflight/transform checks were done prior to touching any repo file.
    written=[]
    try:
        for path, content in changes.items():
            target=repo/path
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(content);written.append(path)
    except Exception:
        with ZipFile(backup) as z:
            for path in written:
                target=repo/path
                if path in z.namelist():target.write_bytes(z.read(path))
                elif target.exists():target.unlink()
        raise
    return backup

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',default=r'C:\Users\pc\LEMMIQ')
    p.add_argument('--dry-run',action='store_true')
    args=p.parse_args();repo=Path(args.repo)
    try:
        edits=prepare(repo)
        print(f'V2.12 compatibility preflight passed: {len(edits)} changes')
        for item in edits:print(' ',item)
        if args.dry_run:
            print('DRY RUN complete: no files changed')
        elif edits:
            print('Updated successfully; backup:',apply(repo,edits))
            print('Next: inspect git diff, build Android, test, then commit/push')
        else:print('Already applied; no source files changed')
    except Incompatible as e:
        print('STOP — compatibility check failed:',e,file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
