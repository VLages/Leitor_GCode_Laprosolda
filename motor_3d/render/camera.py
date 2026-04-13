import numpy as np
import math

class Camera:
    def __init__(self, width, height):
        # Dimensões da tela
        self.WIDTH  = width
        self.HEIGHT = height

        # 1. Parâmetros Orbitais (Referência para o Laprosolda)
        # O alvo (target) é o ponto onde a câmera sempre estará olhando (o centro do grid)
        self.target = np.array([0.0, 0.0, 0.0])
        self.distance = 600.0  # Distância da câmera até o objeto
        self.yaw = math.radians(-45)  # Rotação horizontal
        self.pitch = math.radians(30) # Rotação vertical (inclinação)

        # 2. Atributos de Projeção
        self.near_plane = 0.01
        self.far_plane  = 10000
        self.h_fov = math.pi / 3
        self.v_fov = self.h_fov * (height / width)

        # 3. Posição da Câmera (será calculada a partir dos ângulos)
        self.position = np.array([0.0, 0.0, 0.0, 1.0])
        self.update_position()

    def update_position(self):
        """Calcula a posição X, Y, Z no sistema Z-UP (CAD)."""
        # Matemática esférica para posicionar a câmera ao redor do target
        # Z representa a altura
        x = self.target[0] + self.distance * math.cos(self.pitch) * math.sin(self.yaw)
        y = self.target[1] + self.distance * math.cos(self.pitch) * math.cos(self.yaw)
        z = self.target[2] + self.distance * math.sin(self.pitch)
        
        self.position = np.array([x, y, z, 1.0])

    def camera_matrix(self):
        """Gera a matriz de visualização LookAt (Z-UP)."""
        # Vetor para onde a câmera aponta
        forward = self.target - self.position[:3]
        norm_f = np.linalg.norm(forward)
        forward = forward / norm_f if norm_f > 1e-6 else np.array([0, 1, 0])
            
        # Define o "Céu" como o eixo Z positivo
        world_up = np.array([0, 0, 1]) 
        
        # Vetor Lateral (Right)
        right = np.cross(world_up, forward)
        norm_r = np.linalg.norm(right)
        right = right / norm_r if norm_r > 1e-6 else np.array([1, 0, 0])
            
        # Vetor Vertical Real da Câmera (Up)
        up = np.cross(forward, right)
        
        # Matriz de Rotação (LookAt)
        R = np.array([
            [right[0],   up[0],   forward[0], 0],
            [right[1],   up[1],   forward[1], 0],
            [right[2],   up[2],   forward[2], 0],
            [0,          0,       0,          1]
        ])
        
        # Matriz de Translação
        x, y, z = self.position[:3]
        T = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [-x, -y, -z, 1]
        ])
        
        return T @ R