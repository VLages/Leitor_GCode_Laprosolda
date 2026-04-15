import math 
import numpy as np

class Projection:
    def __init__(self, camera, width, height):
        NEAR   = camera.near_plane
        FAR    = camera.far_plane
        RIGHT  = math.tan(camera.h_fov / 2)
        LEFT   = -RIGHT
        TOP    = math.tan(camera.v_fov / 2)
        BOTTOM = -TOP

        m00 = 2 / (RIGHT - LEFT)
        m11 = 2 / (TOP - BOTTOM)
        m22 = (FAR + NEAR) / (FAR - NEAR)
        m32 = -2 * NEAR * FAR / (FAR - NEAR)

        self.projection_matrix = np.array([
            [m00, 0,   0,   0],
            [0,   m11, 0,   0],
            [0,   0,   m22, 1],
            [0,   0,   m32, 0]
        ])

        HW = width  // 2
        HH = height // 2
        self.to_screen_matrix = np.array([
            [HW, 0,   0, 0],
            [0,  -HH, 0, 0],
            [0,  0,   1, 0],
            [HW, HH,  0, 1]
        ])