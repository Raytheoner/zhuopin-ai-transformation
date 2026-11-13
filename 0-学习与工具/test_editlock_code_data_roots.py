"""Actual shared-lock loader code must remain in its checkout, with shared data elsewhere."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import pytest

SOURCE=Path(__file__).with_name('工具-共享文档编辑锁.py')

@pytest.fixture
def isolated_loader(tmp_path,monkeypatch):
    checkout=tmp_path/'checkout';shared=tmp_path/'shared'
    tools=checkout/'0-学习与工具';shared_tools=shared/'0-学习与工具'
    tools.mkdir(parents=True);shared_tools.mkdir(parents=True)
    source=tools/'工具-共享文档编辑锁.py';source.write_bytes(SOURCE.read_bytes())
    local=tools/'工具-密钥扫描lint.py';canonical=shared_tools/local.name
    canonical.write_text('raise RuntimeError("shared data root must never provide executable criterion")\n',encoding='utf8')
    def query(argv,**kwargs):
        assert argv[0]=='git' and argv[-3:]==['rev-parse','--path-format=absolute','--git-common-dir']
        assert Path(kwargs['cwd'])==tools
        return subprocess.CompletedProcess(argv,0,str(shared/'.git')+'\n','')
    # Only the readonly root-discovery syscall is substituted during module import.
    with monkeypatch.context() as ctx:
        ctx.setattr(subprocess,'run',query)
        spec=importlib.util.spec_from_file_location('editlock_root_fixture',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.REPO_ROOT==shared
    return module,local,canonical

def test_checkout_criterion_is_independent_of_shared_data_root(isolated_loader):
    module,local,_=isolated_loader
    assert module._CREDENTIAL_LINT_SCRIPT==local
    local.write_text('MARKER="checkout-criterion"\n',encoding='utf8')
    before=list(sys.path)
    assert module._load_credential_lint_module().MARKER=='checkout-criterion'
    assert sys.path==before

@pytest.mark.parametrize('kind',['missing','invalid'])
def test_missing_or_invalid_checkout_criterion_never_falls_back(isolated_loader,kind):
    module,local,canonical=isolated_loader
    canonical.write_text('MARKER="unsafe-shared-fallback"\n',encoding='utf8')
    if kind=='invalid':local.write_text('def broken(:\n',encoding='utf8')
    expected=FileNotFoundError if kind=='missing' else SyntaxError
    before=list(sys.path)
    with pytest.raises(expected):module._load_credential_lint_module()
    assert sys.path==before
