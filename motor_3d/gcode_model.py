class GCodeSegment:
    """Representa um único segmento de movimento entre dois pontos."""
    def __init__(self, x0, y0, z0, x1, y1, z1, move_type, layer):
        self.start = (x0, y0, z0)
        self.end   = (x1, y1, z1)
        self.type  = move_type   # 'travel' (G0) ou 'extrude' (G1)
        self.layer = layer
 
    def __repr__(self):
        return f"GCodeSegment({self.type}, layer={self.layer}, {self.start} -> {self.end})"
 
 
class GCodeModel:
    """Contém todos os segmentos parseados e metadados do arquivo GCode."""
    def __init__(self):
        self.segments = []    # lista de GCodeSegment
        self.layers   = {}    # dict: z_value (float) -> [GCodeSegment, ...]
        self.bounds   = None  # (xmin, ymin, zmin, xmax, ymax, zmax)
 
    @property
    def layer_count(self):
        return len(self.layers)
 
    @property
    def sorted_z_values(self):
        return sorted(self.layers.keys())
 
    def __repr__(self):
        return (f"GCodeModel({len(self.segments)} segmentos, "
                f"{self.layer_count} camadas, bounds={self.bounds})")
 