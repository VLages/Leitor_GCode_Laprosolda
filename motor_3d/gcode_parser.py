import re
from .gcode_model import GCodeSegment, GCodeModel

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
    """
    Parser de arquivos GCode para uso no Leitor GCode Laprosolda.

    Comandos suportados:
      G0  - movimento rapido (travel)
      G1  - movimento com extrusao/soldagem (extrude)
      G28 - home (reseta posicao)
      G90 - modo absoluto (padrao)
      G91 - modo relativo
      G92 - define posicao atual (reset de eixo)
    """

    def parse(self, filepath: str) -> GCodeModel:
        model    = GCodeModel()
        x, y, z  = 0.0, 0.0, 0.0
        layer    = 0
        absolute = True

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
                    if absolute:
                        nx = cmd.get('X', x)
                        ny = cmd.get('Y', y)
                        nz = cmd.get('Z', z)
                    else:
                        nx = x + cmd.get('X', 0.0)
                        ny = y + cmd.get('Y', 0.0)
                        nz = z + cmd.get('Z', 0.0)

                    if nz != z:
                        layer += 1

                    if (nx, ny, nz) != (x, y, z):
                        move_type = 'travel' if cmd.code == 'G0' else 'extrude'
                        seg = GCodeSegment(x, y, z, nx, ny, nz, move_type, layer, line_number)
                        model.segments.append(seg)
                        model.layers.setdefault(layer, []).append(seg)

                    x, y, z = nx, ny, nz

        model.bounds = self._calc_bounds(model.segments)
        return model

    def _parse_line(self, line: str):
        line = line.split(';')[0].strip()
        if not line:
            return None

        tokens = line.upper().split()
        if not tokens:
            return None

        code = tokens[0]
        if not re.match(r'^[A-Z]\d+\.?\d*$', code):
            return None

        params = {}
        for token in tokens[1:]:
            match = re.match(r'^([A-Z])(-?\d+\.?\d*)$', token)
            if match:
                params[match.group(1)] = float(match.group(2))

        return ParsedCommand(code, params)

    def _calc_bounds(self, segments):
        if not segments:
            return (0, 0, 0, 0, 0, 0)

        all_points = [seg.start for seg in segments] + [seg.end for seg in segments]
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        zs = [p[2] for p in all_points]

        return (min(xs), min(ys), min(zs),
                max(xs), max(ys), max(zs))
