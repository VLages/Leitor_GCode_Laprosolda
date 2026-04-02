from .matrix import *

class Camera:
    def __init__(self, width, height, position=None):
        if position is None:
            position = [0, 0, -50]

        self.WIDTH  = width
        self.HEIGHT = height

        self.position = np.array([*position, 1.0])
        self.forward  = np.array([0, 0, 1, 1])
        self.up       = np.array([0, 1, 0, 1])
        self.right    = np.array([1, 0, 0, 1])

        self.h_fov = math.pi / 3
        self.v_fov = self.h_fov * (height / width)

        self.near_plane    = 0.1
        self.far_plane     = 100
        self.moving_speed  = 0.3
        self.rotation_speed = 0.015

        self.anglePitch = 0
        self.angleYaw   = 0
        self.angleRoll  = 0

    def camera_yaw(self, angle):
        self.angleYaw += angle

    def camera_pitch(self, angle):
        self.anglePitch += angle

    def axiiIdentity(self):
        self.forward = np.array([0, 0, 1, 1])
        self.up      = np.array([0, 1, 0, 1])
        self.right   = np.array([1, 0, 0, 1])

    def camera_update_axii(self):
        rotate = rotate_x(self.anglePitch) @ rotate_y(self.angleYaw)
        self.axiiIdentity()
        self.forward = self.forward @ rotate
        self.right   = self.right   @ rotate
        self.up      = self.up      @ rotate

    def camera_matrix(self):
        self.camera_update_axii()
        return self.translate_matrix() @ self.rotate_matrix()

    def translate_matrix(self):
        x, y, z, w = self.position
        return np.array([
            [1,  0,  0, 0],
            [0,  1,  0, 0],
            [0,  0,  1, 0],
            [-x, -y, -z, 1]
        ])

    def rotate_matrix(self):
        rx, ry, rz, w = self.right
        fx, fy, fz, w = self.forward
        ux, uy, uz, w = self.up
        return np.array([
            [rx, ux, fx, 0],
            [ry, uy, fy, 0],
            [rz, uz, fz, 0],
            [0,  0,  0,  1]
        ])