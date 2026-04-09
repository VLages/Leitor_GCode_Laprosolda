from .matrix import *


class Camera:
    def __init__(self, width, height, position=None):
        if position is None:
            position = [0, 0, -50]

        self.WIDTH  = width
        self.HEIGHT = height

        self.position = np.array([*position, 1.0])

        # Vetores de orientação — definidos externamente pelo viewer orbital
        self.forward = np.array([0, 0, 1, 1])
        self.up      = np.array([0, 1, 0, 1])
        self.right   = np.array([1, 0, 0, 1])

        self.h_fov = math.pi / 3
        self.v_fov = self.h_fov * (height / width)

        self.near_plane  = 0.01
        self.far_plane   = 10000

    def camera_matrix(self):
        # Usa diretamente os vetores definidos pelo viewer.
        # NÃO recalcula a partir de ângulos internos — isso é responsabilidade
        # do viewer orbital, que chama _update_camera_position() antes de cada frame.
        return self.translate_matrix() @ self.rotate_matrix()

    def translate_matrix(self):
        x, y, z, _ = self.position
        return np.array([
            [ 1,  0,  0, 0],
            [ 0,  1,  0, 0],
            [ 0,  0,  1, 0],
            [-x, -y, -z, 1]
        ], dtype=np.float64)

    def rotate_matrix(self):
        rx, ry, rz, _ = self.right
        fx, fy, fz, _ = self.forward
        ux, uy, uz, _ = self.up
        return np.array([
            [rx, ux, fx, 0],
            [ry, uy, fy, 0],
            [rz, uz, fz, 0],
            [ 0,  0,  0, 1]
        ], dtype=np.float64)