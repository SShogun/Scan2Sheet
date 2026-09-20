from __future__ import annotations
import argparse,json,platform,re,subprocess,time,unicodedata,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import cv2,numpy as np
from PIL import Image
from backend.app.ocr import _ocr_image,_preprocess_image
from tests.generate_ocr_fixtures import ensure_fixtures
FIXTURE_ROOT=ROOT/'tests'/'ocr_fixtures'; DEFAULT_OUTPUT=ROOT/'artifacts'/'benchmarks'/'current.json'
def normalize_text(value,*,words=False):
    value=unicodedata.normalize('NFKC',value).replace('\r\n','\n').replace('\r','\n').strip()
    if words:return ' '.join(value.split())
    lines=[re.sub(r'[ \t]+',' ',line).strip() for line in value.split('\n')]
    return '\n'.join(line for line in lines if line)
def edit_distance(reference,hypothesis):
    previous=list(range(len(hypothesis)+1))
    for i,ref_item in enumerate(reference,1):
        current=[i]
        for j,hyp_item in enumerate(hypothesis,1): current.append(min(previous[j-1]+(ref_item!=hyp_item),previous[j]+1,current[j-1]+1))
        previous=current
    return previous[-1]
def error_rate(reference,hypothesis): return 0.0 if not reference and not hypothesis else (1.0 if not reference else edit_distance(reference,hypothesis)/len(reference))
def quality_measurements(image_path):
    gray=cv2.imread(str(image_path),cv2.IMREAD_GRAYSCALE); p05,p95=np.percentile(gray,[5,95]); return {'laplacian_variance':round(float(cv2.Laplacian(gray,cv2.CV_64F).var()),6),'mean_intensity':round(float(np.mean(gray)),6),'intensity_stddev':round(float(np.std(gray)),6),'p05':round(float(p05),6),'p95':round(float(p95),6),'dynamic_range':round(float(p95-p05),6)}
def tesseract_version(): return subprocess.run(['tesseract','--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0].strip()
def run_benchmark(output_path=DEFAULT_OUTPUT,*,kind='current-regression',git_commit='working-tree'):
    ensure_fixtures(); manifest=json.loads((FIXTURE_ROOT/'manifest.json').read_text()); results=[]
    for item in manifest['fixtures']:
        image_path=FIXTURE_ROOT/item['fixture']; original=Image.open(image_path); started=time.perf_counter(); processed=_preprocess_image(original); ocr_text,conf=_ocr_image(processed); ms=(time.perf_counter()-started)*1000
        ref_chars=normalize_text(item['ground_truth_text']); hyp_chars=normalize_text(ocr_text); ref_words=normalize_text(item['ground_truth_text'],words=True).split(); hyp_words=normalize_text(ocr_text,words=True).split(); normalized=normalize_text(ocr_text,words=True)
        hits={k:normalize_text(v,words=True) in normalized for k,v in item['important_fields'].items()}
        results.append({'fixture':item['fixture'],'fixture_sha256':item['sha256'],'category':item['category'],'ocr_text':ocr_text,'normalized_ocr_text':hyp_chars,'cer':round(error_rate(ref_chars,hyp_chars),6),'wer':round(error_rate(ref_words,hyp_words),6),'important_field_hits':hits,'important_field_accuracy':round(sum(hits.values())/len(hits),6),'ocr_confidence_current':round(float(conf),6),'processing_ms':round(ms,3),'quality_measurements':quality_measurements(image_path)})
    payload={'benchmark_schema':1,'benchmark_kind':kind,'git_commit':git_commit,'ground_truth_review':manifest['review_status'],'normalization':'NFKC; normalized line endings; trim; collapse horizontal whitespace; WER collapses all whitespace; case and punctuation preserved','important_field_hit_definition':'Expected public fixture field value occurs exactly in whitespace-normalized raw OCR text; no fuzzy matching.','environment':{'python':platform.python_version(),'opencv':cv2.__version__,'tesseract':tesseract_version()},'fixtures':results}; output_path.parent.mkdir(parents=True,exist_ok=True); output_path.write_text(json.dumps(payload,indent=2)+'\n'); return payload
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT); p.add_argument('--kind',default='current-regression'); p.add_argument('--git-commit',default='working-tree'); a=p.parse_args(); r=run_benchmark(a.output,kind=a.kind,git_commit=a.git_commit)
    for f in r['fixtures']: print(f['category'],f"CER={f['cer']:.6f}",f"WER={f['wer']:.6f}",f"fields={f['important_field_accuracy']:.6f}",f"confidence={f['ocr_confidence_current']:.1f}",f"ms={f['processing_ms']:.1f}")
