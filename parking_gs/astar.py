"""Traditional occupancy-grid A* for the parking task.

The planner intentionally operates on a 2-D occupancy grid.  It does not use
the previous Hybrid-A* motion primitives; vehicle clearance is checked at each
cell and the resulting polyline is consumed by the existing visualizer.
"""
from dataclasses import asdict
import heapq
import itertools
import math
import time
import numpy as np

from .planner import Vehicle, collision, wrap


_MOVES = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
          (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)),
          (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2)))


def _cell(grid, pose):
    ij = grid.indices(np.asarray([pose[:2]], dtype=float))[0]
    return int(ij[0]), int(ij[1])


def _inside(grid, ij):
    x, y = ij
    return 0 <= y < grid.risk.shape[0] and 0 <= x < grid.risk.shape[1]


def _pose_at(grid, ij, yaw):
    return (grid.bounds[0] + (ij[0] + .5) * grid.resolution,
            grid.bounds[1] + (ij[1] + .5) * grid.resolution, yaw)


def _octile(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def _line_of_sight(a, b, free):
    """Integer-grid supercover check for a safe A* path shortcut."""
    x0, y0 = a; x1, y1 = b
    dx, dy = x1 - x0, y1 - y0
    n = max(abs(dx), abs(dy))
    if n == 0:
        return True
    for i in range(n + 1):
        x = round(x0 + dx * i / n); y = round(y0 + dy * i / n)
        if (x, y) not in free:
            return False
    return True


def plan(start, goal, grid, vehicle=None, max_expansions=120_000, timeout=20.0,
         allow_unknown=False, simplify=False):
    """Plan an 8-connected occupancy-grid path with traditional A*.

    ``start`` and ``goal`` are metric poses.  Unknown cells remain blocked by
    default.  The returned path contains metric poses and is compatible with
    ``control.simulate`` and the browser API.
    """
    vehicle = vehicle or Vehicle()
    start, goal = tuple(map(float, start)), tuple(map(float, goal))
    if len(start) != 3 or len(goal) != 3 or not np.isfinite([start, goal]).all():
        raise ValueError('Poses must be three finite numbers')
    if not allow_unknown:
        # collision() includes unknown cells.  It is the authoritative vehicle
        # footprint check used by execution as well.
        if collision(start, grid, vehicle):
            raise ValueError('Start vehicle footprint is blocked or unknown')
        if collision(goal, grid, vehicle):
            raise ValueError('Goal vehicle footprint is blocked or unknown')

    start_cell, goal_cell = _cell(grid, start), _cell(grid, goal)
    if not _inside(grid, start_cell) or not _inside(grid, goal_cell):
        raise ValueError('Start or goal is outside the map')
    if start_cell == goal_cell:
        return dict(path=[dict(x=start[0], y=start[1], yaw=start[2], direction=1, steer=0.)],
                    planner='astar', expanded=0, seconds=0.0, vehicle=asdict(vehicle),
                    goal=list(goal), position_error=0.0, yaw_error=0.0)

    begin = time.perf_counter()
    counter = itertools.count()
    open_set = [(0.0, next(counter), start_cell)]
    came_from = {}
    g_score = {start_cell: 0.0}
    expanded = 0

    def traversable(ij):
        if not _inside(grid, ij):
            return False
        x, y = ij
        if not allow_unknown and not bool(grid.known[y, x]):
            return False
        # Candidate yaw follows the motion direction. This preserves a
        # conservative body check while remaining a classic grid A*.
        return True

    while open_set and expanded < max_expansions and time.perf_counter() - begin < timeout:
        _, _, current = heapq.heappop(open_set)
        expanded += 1
        if current == goal_cell:
            break
        for dx, dy, step_cost in _MOVES:
            nxt = (current[0] + dx, current[1] + dy)
            if not traversable(nxt):
                continue
            yaw = math.atan2(dy, dx)
            pose = _pose_at(grid, nxt, yaw)
            if collision(pose, grid, vehicle):
                continue
            # Keep diagonal moves from cutting across a one-cell corner.
            if dx and dy and (not traversable((current[0] + dx, current[1]) ) or
                              not traversable((current[0], current[1] + dy))):
                continue
            risk = float(grid.risk[nxt[1], nxt[0]])
            tentative = g_score[current] + step_cost * (1.0 + 1.8 * risk)
            if tentative >= g_score.get(nxt, float('inf')):
                continue
            came_from[nxt] = current
            g_score[nxt] = tentative
            f = tentative + _octile(nxt, goal_cell)
            heapq.heappush(open_set, (f, next(counter), nxt))

    if goal_cell not in came_from:
        raise RuntimeError(f'No A* path within budget: {expanded} expansions, '
                           f'{time.perf_counter() - begin:.2f}s')

    cells = [goal_cell]
    while cells[-1] != start_cell:
        cells.append(came_from[cells[-1]])
    cells.reverse()
    if simplify and len(cells) > 2:
        # A shortcut may cross any free cell, not only cells that happened to
        # be visited by the first A* path.
        free = {(x, y) for y in range(grid.risk.shape[0])
                for x in range(grid.risk.shape[1])
                if traversable((x, y)) and not collision(_pose_at(grid, (x, y), 0.), grid, vehicle)}
        simplified = [cells[0]]
        anchor = 0
        for i in range(2, len(cells)):
            if not _line_of_sight(cells[anchor], cells[i], free):
                simplified.append(cells[i - 1]); anchor = i - 1
        simplified.extend(cells[anchor + 1:])
        cells = simplified

    path = []
    for i, ij in enumerate(cells):
        if i == 0:
            yaw = start[2]
            x, y = start[:2]
        elif i == len(cells) - 1:
            yaw = goal[2]
            x, y = goal[:2]
        else:
            dx = cells[i + 1][0] - cells[i - 1][0]
            dy = cells[i + 1][1] - cells[i - 1][1]
            yaw = math.atan2(dy, dx)
            x, y, _ = _pose_at(grid, ij, yaw)
        path.append(dict(x=float(x), y=float(y), yaw=float(yaw), direction=1, steer=0.))
    return dict(path=path, planner='astar', expanded=expanded,
                seconds=time.perf_counter() - begin, vehicle=asdict(vehicle),
                goal=list(goal), position_error=0.0, yaw_error=0.0)
