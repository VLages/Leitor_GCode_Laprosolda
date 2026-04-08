class GCodeSegment:
    """Representa um unico segmento de movimento entre dois pontos."""
    def __init__(self, x0, y0, z0, x1, y1, z1, move_type, layer, line_number=0):
        self.start       = (x0, y0, z0)
        self.end         = (x1, y1, z1)
        self.type        = move_type   # 'travel' (G0) ou 'extrude' (G1)
        self.layer       = layer
        self.line_number = line_number  # linha original no arquivo GCode

    def __repr__(self):
        return f"GCodeSegment({self.type}, layer={self.layer}, {self.start} -> {self.end})"


class GCodeModel:
    """Contem todos os segmentos parseados e metadados do arquivo GCode."""
    def __init__(self):
        self.segments = []    # lista de GCodeSegment
        self.layers   = {}    # dict: layer_index (int) -> [GCodeSegment, ...]
        self.bounds   = None  # (xmin, ymin, zmin, xmax, ymax, zmax)

    @property
    def layer_count(self):
        return len(self.layers)

    @property
    def sorted_z_values(self):
        return sorted(self.layers.keys())

    @property
    def total_length(self):
        """Comprimento total do percurso em mm."""
        import math
        total = 0.0
        for seg in self.segments:
            dx = seg.end[0] - seg.start[0]
            dy = seg.end[1] - seg.start[1]
            dz = seg.end[2] - seg.start[2]
            total += math.sqrt(dx*dx + dy*dy + dz*dz)
        return total

    def __repr__(self):
        return (f"GCodeModel({len(self.segments)} segmentos, "
                f"{self.layer_count} camadas, bounds={self.bounds})")
