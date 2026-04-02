import re
from .gcode_model import GCodeSegment, GCodeModel
 
class ParsedCommand:
    """Resultado do parse de uma única linha de GCode."""
    def __init__(self, code, params):
        self.code   = code    # ex: 'G0', 'G1', 'G28', 'M104'
        self.params = params  # dict: {'X': 10.0, 'Y': 5.0, ...}
 
    def get(self, key, default=None):
        return self.params.get(key, default)
 
    def __repr__(self):
        return f"ParsedCommand({self.code}, {self.params})"
 
 
class GCodeParser:
    """
    Parser de arquivos GCode para uso no Leitor GCode Laprosolda.
 
    Comandos suportados:
      G0  — movimento rápido (travel)
      G1  — movimento com extrusão/soldagem (extrude)
      G28 — home (reseta posição)
      G90 — modo absoluto (padrão)
      G91 — modo relativo
      G92 — define posição atual (reset de eixo)
    """
 
    def parse(self, filepath: str) -> GCodeModel:
        model    = GCodeModel()
        x, y, z  = 0.0, 0.0, 0.0
        layer    = 0
        absolute = True   # G90 = absoluto (padrão), G91 = relativo
 
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for raw_line in f:
                cmd = self._parse_line(raw_line)
                if cmd is None:
                    continue
 
                # ── Controle de modo de posicionamento ──────────────────────
                if cmd.code == 'G90':
                    absolute = True
                    continue
                elif cmd.code == 'G91':
                    absolute = False
                    continue
 
                # ── Home: volta tudo a zero ──────────────────────────────────
                elif cmd.code == 'G28':
                    x, y, z = 0.0, 0.0, 0.0
                    continue
 
                # ── Reset de coordenadas (G92) ───────────────────────────────
                elif cmd.code == 'G92':
                    if 'X' in cmd.params: x = cmd.params['X']
                    if 'Y' in cmd.params: y = cmd.params['Y']
                    if 'Z' in cmd.params: z = cmd.params['Z']
                    continue
 
                # ── Movimentos G0 e G1 ───────────────────────────────────────
                elif cmd.code in ('G0', 'G1'):
                    if absolute:
                        nx = cmd.get('X', x)
                        ny = cmd.get('Y', y)
                        nz = cmd.get('Z', z)
                    else:
                        nx = x + cmd.get('X', 0.0)
                        ny = y + cmd.get('Y', 0.0)
                        nz = z + cmd.get('Z', 0.0)
 
                    # Detecta mudança de camada pelo eixo Z
                    if nz != z:
                        layer += 1
 
                    # Cria segmento apenas se houve deslocamento
                    if (nx, ny, nz) != (x, y, z):
                        move_type = 'travel' if cmd.code == 'G0' else 'extrude'
                        seg = GCodeSegment(x, y, z, nx, ny, nz, move_type, layer)
                        model.segments.append(seg)
                        model.layers.setdefault(nz, []).append(seg)
 
                    x, y, z = nx, ny, nz
 
        model.bounds = self._calc_bounds(model.segments)
        return model

    def _parse_line(self, line: str):
        """
        Converte uma linha de texto GCode em um ParsedCommand.
        Retorna None para linhas vazias, comentários ou comandos sem letra de código.
        """
        # Remove comentário (tudo após ';') e espaços extras
        line = line.split(';')[0].strip()
        if not line:
            return None
 
        # Separa tokens (ex: ['G1', 'X10.5', 'Y3.0', 'Z0.2', 'F3000'])
        tokens = line.upper().split()
        if not tokens:
            return None
 
        # Primeiro token deve ser o código do comando (ex: G1, M104)
        code = tokens[0]
        if not re.match(r'^[A-Z]\d+\.?\d*$', code):
            return None
 
        # Parseia os parâmetros restantes (ex: X10.5 → {'X': 10.5})
        params = {}
        for token in tokens[1:]:
            match = re.match(r'^([A-Z])(-?\d+\.?\d*)$', token)
            if match:
                params[match.group(1)] = float(match.group(2))
 
        return ParsedCommand(code, params)
 
    def _calc_bounds(self, segments):
        """Calcula o bounding box de todos os segmentos."""
        if not segments:
            return (0, 0, 0, 0, 0, 0)
 
        all_points = [seg.start for seg in segments] + [seg.end for seg in segments]
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        zs = [p[2] for p in all_points]
 
        return (min(xs), min(ys), min(zs),
                max(xs), max(ys), max(zs))