from dataclasses import dataclass, field

from .errors import AppError

MAX_NODES = 1000


@dataclass
class Graph:
    root: tuple
    edges: dict = field(default_factory=dict)
    order: list = field(default_factory=list)
    depths: dict = field(default_factory=dict)


def label(node):
    """Преобразовать узел (имя, версия) в подпись."""
    return '@'.join(node)


def build_graph(repository, name, version, max_depth=10):
    """Построить ограниченный по глубине граф итеративным DFS."""
    root = (name, version)
    graph = Graph(root)
    stack = [(root, 0)]
    expanded = {}
    while stack:
        node, depth = stack.pop()
        if node not in graph.edges:
            if len(graph.edges) >= MAX_NODES:
                raise AppError(f'Лимит графа: {MAX_NODES} узлов.')
            graph.edges[node] = []
            graph.order.append(node)
        graph.depths[node] = min(depth, graph.depths.get(node, depth))
        if depth >= max_depth or expanded.get(node, max_depth) <= depth:
            continue
        expanded[node] = depth
        children = []
        for child, specifier in repository.dependencies(*node):
            child_node = (child, repository.resolve(child, specifier))
            if child_node not in children:
                children.append(child_node)
        graph.edges[node] = children
        stack.extend((child, depth + 1) for child in reversed(children))
    return graph


def describe_graph(graph):
    """Сформировать текст обхода и рёбер графа."""
    lines = ['DFS: ' + ' -> '.join(map(label, graph.order))]
    for node in graph.order:
        children = ', '.join(map(label, graph.edges[node]))
        lines.append(f'{label(node)}: {children or "(нет раскрытых рёбер)"}')
    return '\n'.join(lines)
