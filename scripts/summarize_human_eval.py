"""Summarize saved measurements without rerunning recognition."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    reports=[]
    for path in sorted((ROOT/'logs').glob('human-*.json')):
        r=json.loads(path.read_text('utf-8'))
        if 'summary' not in r or 'engine' not in r:
            continue
        reports.append(dict(report=path.name,**{k:r[k] for k in ('engine','threads','split','input','summary','datasets')}))
    old=json.loads((ROOT/'logs/human-sensevoice-t2-holdout-pipeline.json').read_text('utf-8'))
    new=json.loads((ROOT/'logs/human-reazon-t2-holdout-pipeline.json').read_text('utf-8'))
    assert [r['file'] for r in old['rows']]==[r['file'] for r in new['rows']]
    a=np.array([r['edits'] for r in old['rows']]); b=np.array([r['edits'] for r in new['rows']])
    n=np.array([r['characters'] for r in old['rows']])
    rng=np.random.default_rng(20260924)
    samples=rng.integers(0,len(n),size=(2000,len(n)))
    differences=(a[samples].sum(1)-b[samples].sum(1))/n[samples].sum(1)
    result=dict(reports=reports,paired_holdout=dict(
        relative_error_reduction=float(1-b.sum()/a.sum()),
        absolute_CER_reduction=float((a.sum()-b.sum())/n.sum()),
        clip_bootstrap_95_percent_interval=list(np.percentile(differences,[2.5,97.5])),
        limitation='Clip bootstrap, not speaker bootstrap; limited convenience sample, not population guarantee'))
    (ROOT/'logs/human-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    for r in reports: print(r['report'],json.dumps(r['summary']))
    print(json.dumps(result['paired_holdout']))


if __name__=='__main__': main()
