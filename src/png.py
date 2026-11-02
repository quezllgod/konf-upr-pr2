import json
import struct
import zlib
from itertools import pairwise
from pathlib import Path

from .errors import AppError
from .graph import label

FONT = json.loads(Path(__file__).with_name('font.json').read_text())
MAX_IMAGE_NODES = 150
ORIGIN = 0
X_INDEX = 0
TITLE = "npm dependencies - variant 14"


class Canvas:
    def __init__(self, width, height):
        """Инициализировать объект."""
        self.width, self.height = width, height
        self.pixels = bytearray([255]) * (width * height * 3)

    def dot(self, x, y, color):
        """Закрасить пиксель в пределах изображения."""
        if ORIGIN <= x < self.width and ORIGIN <= y < self.height:
            index = (y * self.width + x) * 3
            self.pixels[index:index + 3] = bytes(color)

    def line(self, x, y, end_x, end_y, color):
        """Нарисовать отрезок между двумя точками."""
        steps = max(abs(end_x - x), abs(end_y - y), 1)
        for step in range(steps + 1):
            self.dot(round(x + (end_x - x) * step / steps),
                     round(y + (end_y - y) * step / steps), color)

    def text(self, x, y, text):
        """Вывести строку встроенным растровым шрифтом."""
        for character in text:
            for row, bits in enumerate(FONT.get(character, FONT['?'])):
                for column in range(9):
                    if bits & (1 << column):
                        self.dot(x + column, y + row, (25, 40, 65))
            x += 9

    def box(self, x, y, width, text):
        """Нарисовать узел с рамкой и подписью."""
        for row in range(y, y + 40):
            for column in range(x, x + width):
                self.dot(column, row, (234, 242, 255))
        for start, end in [((x, y), (x + width, y)),
                           ((x, y + 40), (x + width, y + 40)),
                           ((x, y), (x, y + 40)),
                           ((x + width, y), (x + width, y + 40))]:
            self.line(*start, *end, (65, 100, 170))
        self.text(x + 10, y + 10, text)

    def save(self, path):
        """Закодировать и сохранить изображение PNG."""
        row_size = self.width * 3
        raw = b''.join(b'\0' + self.pixels[i:i + row_size]
                       for i in range(0, len(self.pixels), row_size))
        header = struct.pack('!IIBBBBB', self.width, self.height,
                             8, 2, 0, 0, 0)
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header)
                         + chunk(b'IDAT', zlib.compress(raw))
                         + chunk(b'IEND', b''))


def chunk(kind, data):
    """Сформировать блок PNG с контрольной суммой CRC32."""
    checksum = zlib.crc32(kind + data) & 0xffffffff
    return struct.pack('!I', len(data)) + kind + data + struct.pack(
        '!I', checksum)


def layout(graph):
    """Разместить узлы по глубине и порядку обхода."""
    width = max(180, max(len(label(n)) for n in graph.order) * 9 + 24)
    positions, rows = {}, {}
    for node in graph.order:
        depth = graph.depths[node]
        row = rows.get(depth, 0)
        positions[node] = (30 + depth * (width + 70), 65 + row * 85)
        rows[depth] = row + 1
    return width, positions, rows


def arrow(canvas, start, end, width):
    """Нарисовать направленное ребро между узлами."""
    x, y = start[0] + width, start[1] + 20
    tx, ty = end[0], end[1] + 20
    bend = x + 25
    color = (110, 125, 150)
    if tx <= start[X_INDEX]:
        bottom = max(start[1], end[1]) + 55
        points = [(x, y), (bend, y), (bend, bottom),
                  (tx - 15, bottom), (tx - 15, ty), (tx, ty)]
    else:
        points = [(x, y), (bend, y), (bend, ty), (tx, ty)]
    for first, last in pairwise(points):
        canvas.line(*first, *last, color)
    canvas.line(tx, ty, tx - 7, ty - 4, color)
    canvas.line(tx, ty, tx - 7, ty + 4, color)


def render_png(graph, path):
    """Сохранить растровое представление графа."""
    if len(graph.order) > MAX_IMAGE_NODES:
        raise AppError('PNG: более 150 узлов, уменьшите --max-depth.')
    width, positions, rows = layout(graph)
    image_width = max(x for x, _ in positions.values()) + width + 45
    canvas = Canvas(max(image_width, len(TITLE) * 9 + 60),
                    95 + max(rows.values()) * 85)
    canvas.text(30, 20, TITLE)
    for parent, children in graph.edges.items():
        for child in children:
            arrow(canvas, positions[parent], positions[child], width)
    for node in graph.order:
        canvas.box(*positions[node], width, label(node))
    canvas.save(path)
