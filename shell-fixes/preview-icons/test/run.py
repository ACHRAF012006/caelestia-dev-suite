import argparse,os,secrets,subprocess,tempfile,shutil
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--shell',type=Path,required=True);args=parser.parse_args()
test=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='render-check-') as tmp:
 shell=Path(tmp)/'shell'
 shutil.copytree(args.shell,shell,ignore=shutil.ignore_patterns('plugin','assets','translations','.git'))
 (shell/'shell.qml').write_text((test/'shell.qml').read_text())
 env=dict(os.environ,QML2_IMPORT_PATH=str(Path.home()/'.local/lib/qt6/qml')+':'+str(shell),QT_QPA_PLATFORM='wayland',RENDER_PROBE_TOKEN=secrets.token_hex(16),RENDER_PROBE_IMAGE=str(test/'native.png'),XDG_CONFIG_HOME=tmp+'/config',XDG_STATE_HOME=tmp+'/state',XDG_CACHE_HOME=tmp+'/cache')
 p=subprocess.run(['quickshell','-p',str(shell),'--no-color'],env=env,text=True,capture_output=True,timeout=40)
 output=p.stdout+p.stderr
 (test/'native.log').write_text(output)
 if p.returncode or 'RENDER_PASS' not in output or 'RENDER_FAIL' in output or 'target not found' in output or 'ReferenceError' in output:
  print(output);raise SystemExit('Render check failed')
 from PySide6.QtGui import QImage
 image=QImage(str(test/'native.png'))
 if image.isNull():raise SystemExit('Preview screenshot is missing')
 for left,top,right,bottom in ((35,70,175,130),(231,21,277,67),(231,101,277,147)):
  pixels=[image.pixelColor(x,y) for x in range(left,right) for y in range(top,bottom)]
  visible=sum(min(c.red(),c.green(),c.blue())<220 and c.alpha()>100 for c in pixels)
  if visible<100:raise SystemExit('An icon or preview rendered no visible pixels')
  if left==35:
   red=sum(c.red()>180 and c.green()<100 and c.blue()<160 for c in pixels)
   if red/len(pixels)<.95:raise SystemExit('Live preview rendered black or incorrect pixels')
 print('PASS: owned live frames, four preview reopen cycles, missing icon fallback and recovery, tinted icon hide/show; no invalid PipeWire targets.')
