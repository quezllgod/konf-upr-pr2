"""Обратные зависимости в пределах построенного графа."""
from .errors import AppError

NAME_INDEX = 0


def reverse_edges(graph):
    """Развернуть каждое ребро, сохранив порядок родителей."""
    reverse = {node: [] for node in graph.order}
    for parent, children in graph.edges.items():
        for child in children:
            reverse[child].append(parent)
    return reverse


def reverse_dependencies(graph, target, max_depth=10):
    """Найти всех потребителей целевого имени итеративным DFS."""
    starts = [node for node in graph.order if node[NAME_INDEX] == target]
    if not starts:
        raise AppError(f'Пакет {target} не найден в области анализа.')
    visited = reverse_walk(reverse_edges(graph), starts, max_depth)
    return [node for node in visited if node not in starts]


def reverse_walk(edges, starts, max_depth):
    """Обойти обратные рёбра, повторяя узел лишь при меньшей глубине."""
    best = {}
    unseen_depth = max_depth + 1
    stack = [(node, 0) for node in reversed(starts)]
    while stack:
        node, depth = stack.pop()
        if best.get(node, unseen_depth) <= depth:
            continue
        best[node] = depth
        if depth < max_depth:
            stack.extend((parent, depth + 1)
                         for parent in reversed(edges[node]))
    return list(best)
