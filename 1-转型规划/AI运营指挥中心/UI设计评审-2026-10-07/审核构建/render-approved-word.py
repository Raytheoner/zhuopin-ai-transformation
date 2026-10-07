from pathlib import Path
import os, runpy, sys, tempfile

repo=Path('C:/Dev/zhuopin-ai')
lo=repo/'.tmp/lo1008/App/libreoffice/program'
native=Path('C:/Users/Paul Shao/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin')
renderer=Path('C:/Users/Paul Shao/.codex/plugins/cache/openai-primary-runtime/documents/26.905.11957/skills/documents/render_docx.py')
assert (lo/'soffice.exe').is_file()
assert (native/'pdfinfo.exe').is_file()
assert (native/'pdftoppm.exe').is_file()
tmp=repo/'.tmp/portal-ui-preview-1007/qa/render-tmp-1008'
tmp.mkdir(parents=True,exist_ok=True)
os.environ['PATH']=str(lo)+os.pathsep+str(native)+os.pathsep+os.environ.get('PATH','')
os.environ['TEMP']=os.environ['TMP']=str(tmp)
tempfile.tempdir=str(tmp)
docx=Path(__file__).resolve().parents[1]/'智能门户UI设计审核稿.docx'
out=sys.argv[1] if len(sys.argv)>1 else str(repo/'.tmp/portal-ui-preview-1007/qa/word-render-reproduction')
sys.argv=[str(renderer),str(docx),'--output_dir',out,'--emit_pdf','--verbose']
runpy.run_path(str(renderer),run_name='__main__')
