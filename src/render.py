from pathlib import Path

from .graph import label
from .png import render_png


def to_mermaid(graph):
    """Преобразовать граф в текст диаграммы Mermaid."""
    ids = {node: f'n{i}' for i, node in enumerate(graph.order)}
    lines = ['flowchart LR']
    for node, identifier in ids.items():
        lines.append(f'    {identifier}["{label(node)}"]')
    for parent, children in graph.edges.items():
        for child in children:
            lines.append(f'    {ids[parent]} --> {ids[child]}')
    return '\n'.join(lines)


def save_graph(graph, output):
    """Сохранить Mermaid и PNG одного графа."""
    path = Path(output)
    path.with_suffix('.mmd').write_text(
        to_mermaid(graph) + '\n', encoding='utf-8')
    render_png(graph, path)
