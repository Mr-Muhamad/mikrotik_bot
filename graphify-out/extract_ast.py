import sys, json
from graphify.extract import collect_files, extract
from pathlib import Path

if __name__ == '__main__':
    code_files = []
    detect = json.loads(Path('graphify-out/.graphify_detect.json').read_text(encoding='utf-8-sig'))
    for f in detect.get('files', {}).get('code', []):
        code_files.extend(collect_files(Path(f)) if Path(f).is_dir() else [Path(f)])

    if code_files:
        result = extract(code_files, cache_root=Path('.'))
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"AST: {len(result['nodes'])} nodes, {len(result['edges'])} edges")
    else:
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}, ensure_ascii=False), encoding='utf-8')
        print("No code files - skipping AST extraction")

    Path('graphify-out/.graphify_semantic.json').write_text(json.dumps({'nodes':[],'edges':[],'hyperedges':[],'input_tokens':0,'output_tokens':0}), encoding='utf-8')

    ast = json.loads(Path('graphify-out/.graphify_ast.json').read_text(encoding='utf-8-sig'))
    sem = json.loads(Path('graphify-out/.graphify_semantic.json').read_text(encoding='utf-8-sig'))

    seen = {n['id'] for n in ast['nodes']}
    merged_nodes = list(ast['nodes'])
    for n in sem['nodes']:
        if n['id'] not in seen:
            merged_nodes.append(n)
            seen.add(n['id'])

    merged_edges = ast['edges'] + sem['edges']
    merged_hyperedges = sem.get('hyperedges', [])
    merged = {
        'nodes': merged_nodes,
        'edges': merged_edges,
        'hyperedges': merged_hyperedges,
        'input_tokens': sem.get('input_tokens', 0),
        'output_tokens': sem.get('output_tokens', 0),
    }
    Path('graphify-out/.graphify_extract.json').write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding='utf-8')
    total = len(merged_nodes)
    edges = len(merged_edges)
    print(f"Merged: {total} nodes, {edges} edges ({len(ast['nodes'])} AST + {len(sem['nodes'])} semantic)")
