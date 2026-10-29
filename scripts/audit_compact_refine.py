"""Audit downloaded CI evidence independently of the mapping driver's results."""
import argparse,collections,csv,hashlib,json,math,re
from pathlib import Path
import check_mapping as m


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args(); evidence=args.evidence.resolve()
    mapped=evidence/'build/compact_refinement/map'
    results=json.loads((mapped/'results.json').read_text())
    assert results['status']=='complete'
    for path,sha in results['source_sha256'].items():assert m.digest(m.ROOT/path)==sha,path
    lib=mapped/'library_pruned.lib'
    _,areas,seq=m.prepare_library(lib.read_text())
    reference_predictions=[int(v,16) for v in (m.ROOT/'model/agreement/reference_int8.hex').read_text().split()]
    def read(path):
        with path.open() as f:return list(csv.DictReader(f))
    references={'compact':'build/compact_refinement/rtl.csv',
                'int8x4':'build/compact_refinement/baseline4_all.csv','int8x2':'build/scorepipe.csv'}
    for row in results['rows']:
        name=row['design'];reference=evidence/references[name]
        assert m.digest(reference)==row['reference_sha256']
        traces=[r for r in read(reference) if 1078<=int(r['sample'])<1437]
        assert len(traces)==359 and {int(r['sample']) for r in traces}==set(range(1078,1437))
        replay=mapped/f'{name}.replay.csv'
        assert read(replay)==traces and m.digest(replay)==row['mapped_replay_sha256']
        four=mapped/f'{name}.icarus.csv'
        selection=row['four_state_indices']
        assert row['four_state_frames']==len(selection)
        assert m.digest(four)==row['four_state_sha256']
        assert read(four)==[r for r in traces if int(r['sample']) in selection]
        for r in traces:assert int(r['prediction'])==reference_predictions[int(r['sample'])]
        cells=json.loads((mapped/f'{name}.json').read_text())['modules']['flexmac_mapped']['cells']
        counts=collections.Counter(v['type'] for v in cells.values())
        assert set(counts)<=areas.keys()
        assert len(cells)==row['mapped_cells']
        assert math.isclose(sum(areas[k]*n for k,n in counts.items()),row['area_um2'],abs_tol=1e-6)
        assert math.isclose(sum(areas[k]*n for k,n in counts.items() if k in seq),row['sequential_area_um2'],abs_tol=1e-6)
        assert m.digest(mapped/f'{name}.v')==row['netlist_sha256']
        assert m.digest(mapped/f'{name}.gates.v')==row['gate_model_sha256']
        for tag in ('pass','common'):
            metrics=m.parse_sta((mapped/f'{name}_{tag}.sta.log').read_text())
            assert metrics['setup_met'] and metrics['hold_met']
            period=float(re.search(r'create_clock -name clk -period ([0-9.]+)',(mapped/f'{name}_{tag}.sdc').read_text())[1])
            assert abs(period-row['setup_period_pass_ns' if tag=='pass' else 'common_period_ns'])<1e-6
        cycles=[int(r.get('cycles',r.get('command_to_valid_cycles')))-int(r.get('input_gaps',10 if int(r['sample'])%11==0 else 0)) for r in traces]
        assert math.isclose(sum(cycles)/359,row['mean_cycles'],abs_tol=1e-9)
        assert max(cycles)==row['worst_cycles']
        assert math.isclose(row['mean_cycles']*row['setup_period_pass_ns'],row['mean_latency_ns'],abs_tol=1e-6)
        if name=='compact':
            for r,n in zip(traces,cycles):
                k=int(r['exact_classes']);assert n==253+(10+33*k if k else 0)
                assert int(r['fallback'])==bool(k)
    rows={r['design']:r for r in results['rows']};c=rows['compact']
    baseline_checks={}
    for name in ('int8x2','int8x4'):
        b=rows[name]
        baseline_checks[name]={
            'candidate_area_change_percent':100*(c['area_um2']/b['area_um2']-1),
            'candidate_mean_latency_change_percent':100*(c['mean_latency_ns']/b['mean_latency_ns']-1),
            'candidate_worst_latency_change_percent':100*(c['worst_cycles']*c['setup_period_pass_ns']/(b['worst_cycles']*b['setup_period_pass_ns'])-1),
            'baseline_dominates_candidate':b['area_um2']<=c['area_um2'] and b['mean_latency_ns']<=c['mean_latency_ns']}
    audit={'status':'passed','source_commit':results['source_commit'],
        'source_hashes_checked':len(results['source_sha256']),'library_pruned_sha256':m.digest(lib),
        'compiled_calibration_frames_per_design':359,
        'four_state_frames_per_design':{r['design']:r['four_state_frames'] for r in results['rows']},
        'source_results_sha256':m.digest(mapped/'results.json'),
        'comparisons':baseline_checks,'limitations':'Data/code audit of executed CI; no formal sequential proof, power measurement, layout or fresh held-out evaluation.'}
    target=m.ROOT/'docs/data/compact_refinement/audit.json';m.save(target,json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()
