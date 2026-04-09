import re
import math
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
        # Inicializamos como None para capturar a primeira posição real
        x, y, z  = None, None, None
        absolute = True
        
        # Dicionário para mapear alturas Z para índices de camada (0, 1, 2...)
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
                    # Se for o primeiro movimento e as variáveis forem None, 
                    # pegamos os valores do comando ou assumimos 0
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

                    # --- Lógica de Camada Corrigida ---
                    # Mapeia cada altura Z única para uma camada específica
                    if nz not in z_to_layer:
                        z_to_layer[nz] = current_layer_idx
                        current_layer_idx += 1
                    
                    target_layer = z_to_layer[nz]

                    if (nx, ny, nz) != (x, y, z):
                        move_type = 'travel' if cmd.code == 'G0' else 'extrude'
                        seg = GCodeSegment(x, y, z, nx, ny, nz, move_type, target_layer, line_number)
                        model.segments.append(seg)
                        model.layers.setdefault(target_layer, []).append(seg)

                    x, y, z = nx, ny, nz

        model.bounds = self._calc_bounds(model.segments)

        # No final do método parse, logo antes de 'return model'
        # Definimos o tamanho total e o espaçamento
        grid_size = 500  # Tamanho total em mm
        spacing = 10     # Espaçamento entre linhas (ajustado para dividir bem 500)
        half_size = grid_size // 2

        # O intervalo vai de -250 a +250 para totalizar 500mm
        grid_range = range(-half_size, half_size + spacing, spacing)

        grid = []
        # Gerando linhas verticais (paralelas ao eixo Y)
        for x in grid_range:
            grid.append(GCodeSegment(x, -half_size, 0, x, half_size, 0, 'travel', -1))
            
        # Gerando linhas horizontais (paralelas ao eixo X)
        for y in grid_range:
            grid.append(GCodeSegment(-half_size, y, 0, half_size, y, 0, 'travel', -1))

        model.grid_segments = grid

        return model

    def _parse_line(self, line: str, last_command: str = None):
        line = line.split(';')[0].strip()
        if not line: return None

        tokens = line.upper().split()
        first_token = tokens[0]
        
        # 1. Normalização de comandos (G00 -> G0, G01 -> G1)
        # Usamos regex para capturar a letra e o número, ignorando zeros à esquerda
        match_cmd = re.match(r'^([A-Z])0*(\d+)$', first_token)
        
        if match_cmd:
            code = f"{match_cmd.group(1)}{match_cmd.group(2)}"
            start_idx = 1
        elif last_command and any(first_token.startswith(c) for c in "XYZ"):
            # Suporte a comandos omitidos (Modais)
            code = last_command
            start_idx = 0
        else:
            # Se não for G/M e não for modal, pode ser um comando não suportado
            code = first_token
            start_idx = 1

        params = {}
        # RegEx aprimorado para capturar Letra + Número (incluindo sinais e pontos)
        pattern = re.compile(r'([A-Z])([-+]?\d*\.?\d+)')
        
        # Processa os tokens de parâmetros
        text_to_parse = " ".join(tokens[start_idx:])
        for m in pattern.finditer(text_to_parse):
            params[m.group(1)] = float(m.group(2))

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
