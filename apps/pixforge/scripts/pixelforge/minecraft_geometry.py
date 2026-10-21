"""Original, dependency-free model-space geometry for the 1.20.1 preview."""
import math


NORMALS = {'north': (0, 0, -1), 'south': (0, 0, 1), 'west': (-1, 0, 0),
           'east': (1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0)}
IDENTITY = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))


def add(a, b):
    return tuple(x+y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def mul(a, scale):
    return tuple(x*scale for x in a)


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def unit(value):
    length = math.sqrt(dot(value, value))
    return mul(value, 1 / length) if length > 1e-12 else (0., 1., 0.)


def apply(matrix, vector):
    return tuple(dot(row, vector) for row in matrix)


def transpose(matrix):
    return tuple(zip(*matrix))


def product(left, right):
    return tuple(tuple(dot(row, col) for col in zip(*right)) for row in left)


def rotation(axis, degrees):
    theta = math.radians(degrees)
    c, s = math.cos(theta), math.sin(theta)
    if axis == 'x':
        return ((1., 0., 0.), (0., c, -s), (0., s, c))
    if axis == 'y':
        return ((c, 0., s), (0., 1., 0.), (-s, 0., c))
    return ((c, -s, 0.), (s, c, 0.), (0., 0., 1.))


def xyz(angles):
    return product(product(rotation('x', angles[0]), rotation('y', angles[1])), rotation('z', angles[2]))


def block_rotation(x=0, y=0):
    return product(rotation('y', -y), rotation('x', -x))


def facing(normal):
    return max(NORMALS, key=lambda name: dot(NORMALS[name], normal))


def quad(direction, start, end):
    x, y, z = start
    X, Y, Z = end
    return {'north': [(X, Y, z), (X, y, z), (x, y, z), (x, Y, z)],
            'south': [(x, Y, Z), (x, y, Z), (X, y, Z), (X, Y, Z)],
            'west': [(x, Y, z), (x, y, z), (x, y, Z), (x, Y, Z)],
            'east': [(X, Y, Z), (X, y, Z), (X, y, z), (X, Y, z)],
            'up': [(x, Y, z), (x, Y, Z), (X, Y, Z), (X, Y, z)],
            'down': [(x, y, Z), (x, y, z), (X, y, z), (X, y, Z)]}[direction]


def default_uv(direction, start, end):
    x, y, z = start
    X, Y, Z = end
    return {'down': [x, 16-Z, X, 16-z], 'up': [x, z, X, Z],
            'north': [16-X, 16-Y, 16-x, 16-y], 'south': [x, 16-Y, X, 16-y],
            'west': [z, 16-Y, Z, 16-y], 'east': [16-Z, 16-Y, 16-z, 16-y]}[direction]


FACE_BASIS = {'south': IDENTITY, 'east': rotation('y', 90), 'west': rotation('y', -90),
              'north': rotation('y', 180), 'up': rotation('x', -90), 'down': rotation('x', 90)}


def uv_lock(rect, angle, direction, transform):
    """Re-express a face's UV frame after a quarter-turn block-state rotation."""
    target = facing(apply(transform, NORMALS[direction]))
    lock = product(product(transpose(FACE_BASIS[direction]), transpose(transform)), FACE_BASIS[target])
    def uv_point(u, v):
        p = apply(lock, (u/16-.5, v/16-.5, -.5))
        return (16*(p[0]+.5), 16*(p[1]+.5))
    a, b = uv_point(rect[0], rect[1]), uv_point(rect[2], rect[3])
    sign = lambda n: (n > 1e-8) - (n < -1e-8)
    u = (a[0], b[0]) if sign(rect[2]-rect[0]) == sign(b[0]-a[0]) else (b[0], a[0])
    v = (a[1], b[1]) if sign(rect[3]-rect[1]) == sign(b[1]-a[1]) else (b[1], a[1])
    vector = apply(lock, (math.cos(math.radians(angle)), math.sin(math.radians(angle)), 0.))
    quarter = math.floor(math.degrees(math.atan2(vector[1], vector[0])) / 90 + .5)
    return [u[0], v[0], u[1], v[1]], (-quarter * 90) % 360


def face_uv(rect, angle=0):
    u, v, U, V = rect
    result = [(u/16, v/16), (u/16, V/16), (U/16, V/16), (U/16, v/16)]
    index = angle // 90
    return result[index:] + result[:index]


def element_point(point, transform):
    if not transform:
        return tuple(point)
    p = sub(point, transform['origin'])
    if transform.get('rescale', False):
        axis = 'xyz'.index(transform['axis'])
        cosine = math.cos(math.radians(22.5 if abs(transform['angle'])==22.5 else 45.))
        p = tuple(value if i == axis else value / cosine for i, value in enumerate(p))
    return add(apply(rotation(transform['axis'], transform['angle']), p), transform['origin'])


def display_transform(point, definition, context):
    """ItemRenderer's centered model, hand mirroring and ItemTransform order."""
    display = definition.get('display', {})
    key = context
    if context.endswith('_lefthand') and context not in display:
        key = context.replace('_lefthand', '_righthand')
    settings = display.get(key, {})
    left = context.endswith('_lefthand')
    angles = list(settings.get('rotation', [0., 0., 0.]))
    right = list(settings.get('right_rotation', [0., 0., 0.]))
    if left:
        angles[1], angles[2] = -angles[1], -angles[2]
        right[1], right[2] = -right[1], -right[2]
    p = apply(xyz(right), sub(point, (8., 8., 8.)))
    scale = settings.get('scale', (1., 1., 1.))
    p = tuple(value * max(-4., min(4., factor)) for value, factor in zip(p, scale))
    p = apply(xyz(angles), p)
    translation = [max(-80., min(80., n)) for n in settings.get('translation', (0., 0., 0.))]
    if left:
        translation[0] *= -1
    return add(p, translation)


def display_normal(normal, definition, context):
    """Transform the baked normal with the inverse transpose of the item pose."""
    origin = display_transform((8., 8., 8.), definition, context)
    columns = [sub(display_transform(add((8., 8., 8.), n), definition, context), origin)
               for n in ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))]
    determinant = dot(columns[0], cross(columns[1], columns[2]))
    if abs(determinant) < 1e-12:
        return unit(normal)
    cofactors = (cross(columns[1], columns[2]), cross(columns[2], columns[0]), cross(columns[0], columns[1]))
    return unit(tuple(sum(normal[j]*cofactors[j][i]/determinant for j in range(3)) for i in range(3)))


def baked_face(element, direction, data, row=None):
    row = row or {}
    transform = block_rotation(row.get('x', 0), row.get('y', 0))
    points = [element_point(p, element.get('rotation')) for p in quad(direction, element['from'], element['to'])]
    points = [add(apply(transform, sub(p, (8., 8., 8.))), (8., 8., 8.)) for p in points]
    normal = unit(cross(sub(points[1], points[0]), sub(points[2], points[0])))
    rect, angle = data.get('uv', default_uv(direction, element['from'], element['to'])), data.get('rotation', 0)
    if row.get('uvlock', False):
        rect, angle = uv_lock(rect, angle, direction, transform)
    return points, face_uv(rect, angle), normal, facing(normal)
