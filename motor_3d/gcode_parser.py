import re 
import math
from collections import namedtuple
from .gcode_model import GCodeSegment, GCodeModel

# OTIMIZAÇÃO: Compilação única de RegEx (Corta o gargalo de O(2L) para O(1))
CMD_PATTERN = re.compile(r'^([A-Z])0*(\d+)$')
PARAM_PATTERN = re.compile(r'([A-Z])([-+]?\d*\.?\d+)')

# OTIMIZAÇÃO: Estrutura ultraleve para o grid (Corta o gargalo de memória O(G))
GridSegment = namedtuple('GridSegment', ['start', 'end'])

class ParsedCommand:
    """Resultado do parse de uma unica linha de GCode."""
    def __init__(self, code, params):
        self.code   = code
        self.params = params

    def get(self, key, default=None):
        return self.params.get(key, default)

    def __repr__(self):
        return f"ParsedCommand({self.code}, {self.params})"


class GCodeParser:
    def parse(self, filepath: str, grid_w=500, grid_d=500) -> GCodeModel:
        model    = GCodeModel()
        x, y, z  = None, None, None
        absolute = True
        
        z_to_layer = {} 
        current_layer_idx = 0

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line_number, raw_line in enumerate(f, start=1):
                cmd = self._parse_line(raw_line)
                if cmd is None:
                    continue

                if cmd.code == 'G90':
                    absolute = True
                    continue
                elif cmd.code == 'G91':
                    absolute = False
                    continue
                elif cmd.code == 'G28':
                    x, y, z = 0.0, 0.0, 0.0
                    continue
                elif cmd.code == 'G92':
                    if 'X' in cmd.params: x = cmd.params['X']
                    if 'Y' in cmd.params: y = cmd.params['Y']
                    if 'Z' in cmd.params: z = cmd.params['Z']
                    continue
                
                elif cmd.code in ('G0', 'G1'):
                    if not any(k in cmd.params for k in 'XYZ'):
                        continue
                    if x is None: x = cmd.get('X', 0.0)
                    if y is None: y = cmd.get('Y', 0.0)
                    if z is None: z = cmd.get('Z', 0.0)

                    if absolute:
                        nx = cmd.get('X', x)
                        ny = cmd.get('Y', y)
                        nz = cmd.get('Z', z)
                    else:
                        nx = x + cmd.get('X', 0.0)
                        ny = y + cmd.get('Y', 0.0)
                        nz = z + cmd.get('Z', 0.0)

                    if nz not in z_to_layer:
                        z_to_layer[nz] = current_layer_idx
                        current_layer_idx += 1
                    
                    target_layer = z_to_layer[nz]

                    if (nx, ny, nz) != (x, y, z):
                        move_type = 'travel' if cmd.code == 'G0' else 'extrude'
                        seg = GCodeSegment(x, y, z, nx, ny, nz, move_type, target_layer, line_number)
                        model.segments.append(seg)
                        model.layers.setdefault(target_layer, []).append(seg)

                        # --- OTIMIZAÇÃO: Cálculo incremental da distância O(1) ---
                        dx = nx - x
                        dy = ny - y
                        dz = nz - z
                        model.total_length += math.sqrt(dx*dx + dy*dy + dz*dz)
                        # ---------------------------------------------------------

                    x, y, z = nx, ny, nz

        spacing = 10
        grid = []
        half_w = grid_w // 2
        half_d = grid_d // 2
        
        # Grid usando NamedTuple para gastar menos memória
        for x in range(-half_w, half_w + spacing, spacing):
            for y in range(-half_d, half_d, spacing):
                grid.append(GridSegment((x, y, 0), (x, y + spacing, 0)))
                
        for y in range(-half_d, half_d + spacing, spacing):
            for x in range(-half_w, half_w, spacing):
                grid.append(GridSegment((x, y, 0), (x + spacing, y, 0)))

        model.grid_segments = grid
        model.bounds = self._calc_bounds(model.segments)
        return model

    def _parse_line(self, line: str, last_command: str = None):
        line = line.split(';')[0].strip()
        if not line: return None

        tokens = line.upper().split()
        first_token = tokens[0]
        
        match_cmd = CMD_PATTERN.match(first_token)
        
        if match_cmd:
            code = f"{match_cmd.group(1)}{match_cmd.group(2)}"
            start_idx = 1
        elif last_command and any(first_token.startswith(c) for c in "XYZ"):
            code = last_command
            start_idx = 0
        else:
            code = first_token
            start_idx = 1

        params = {}
        text_to_parse = " ".join(tokens[start_idx:])
        for m in PARAM_PATTERN.finditer(text_to_parse):
            params[m.group(1)] = float(m.group(2))

        return ParsedCommand(code, params)

    def _calc_bounds(self, segments):
        extrude_segs = [s for s in segments if s.type == 'extrude']
        if not extrude_segs:
            return (0, 0, 0, 0, 0, 0)

        # OTIMIZAÇÃO: Extração direta de Xs, Ys e Zs sem duplicar os arrays
        xs = [s.start[0] for s in extrude_segs] + [s.end[0] for s in extrude_segs]
        ys = [s.start[1] for s in extrude_segs] + [s.end[1] for s in extrude_segs]
        zs = [s.start[2] for s in extrude_segs] + [s.end[2] for s in extrude_segs]

        return (min(xs), min(ys), min(zs),
                max(xs), max(ys), max(zs))