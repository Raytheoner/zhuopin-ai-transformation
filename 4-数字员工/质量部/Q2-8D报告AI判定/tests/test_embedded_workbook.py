import io
import pytest
import openpyxl
from q2_8d_verdict.embedded_workbook import read_cached_cells, EmbeddedReadError

def test_cached_text_types_and_empty_string():
    w=openpyxl.Workbook();s=w.active;s['A1']='12345678901234567890';s['B1']=7;s['A2']='=not a formula';s['A2'].data_type='s'
    b=io.BytesIO();w.save(b)
    rows=read_cached_cells(b.getvalue(),'embedded.xlsx')
    assert rows[0].value=='12345678901234567890' and rows[0].value_type=='text'
    assert any(r.value=='=not a formula' for r in rows)
    assert any(r.value==7 and r.value_type=='number' for r in rows)

def test_uncached_formula_cannot_be_zero():
    w=openpyxl.Workbook();w.active['A1']='=1+2';b=io.BytesIO();w.save(b)
    with pytest.raises(EmbeddedReadError,match='cache'):read_cached_cells(b.getvalue(),'a.xlsx')

@pytest.mark.parametrize('blob',[b'bad',b'\xd0\xcf\x11\xe0'+b'\x00'*32])
def test_corruption_is_not_no_records(blob):
    with pytest.raises(EmbeddedReadError):read_cached_cells(blob,'a.bin')
