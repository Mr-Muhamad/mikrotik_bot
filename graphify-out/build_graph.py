import sys, json
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from graphify.export import to_json
from pathlib import Path

extraction = json.loads(Path('graphify-out/.graphify_extract.json').read_text(encoding='utf-8-sig'))
detection  = json.loads(Path('graphify-out/.graphify_detect.json').read_text(encoding='utf-8-sig'))

G = build_from_json(extraction, root='.', directed=False)
if G.number_of_nodes() == 0:
    print('ERROR: Graph is empty - extraction produced no nodes.')
    raise SystemExit(1)

C = cluster(G)
P = score_all(G, C)
community_labels = {cid: f"Community {cid}" for cid in C}

god_node_list = god_nodes(G)
surprise_list = surprising_connections(G, C)
suggested_questions = suggest_questions(G, C, community_labels)

token_cost = {'input': extraction.get('input_tokens', 0), 'output': extraction.get('output_tokens', 0)}

report_text = generate(
    G=G,
    communities=C,
    cohesion_scores=P,
    community_labels=community_labels,
    god_node_list=god_node_list,
    surprise_list=surprise_list,
    detection_result=detection,
    token_cost=token_cost,
    root='.',
    suggested_questions=suggested_questions
)

Path('graphify-out/knowledge_graph.md').write_text(report_text, encoding='utf-8')
to_json(G, C, 'graphify-out/graph.json', force=True, community_labels=community_labels)
print('Graphify generated: graphify-out/knowledge_graph.md')
