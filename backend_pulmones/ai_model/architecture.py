import torch
import torch.nn as nn

class MiniUNet(nn.Module):
    """
    Arquitectura U-Net reducida coincidente con los pesos de modelo_entrenado.pth.
    Capas: enc1 (Conv2d 1->16), pool, up, dec1 (Conv2d 16->1), sigmoid.
    """
    def __init__(self):
        super(MiniUNet, self).__init__()
        self.enc1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.dec1 = nn.Conv2d(16, 1, kernel_size=3, padding=1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x1 = torch.relu(self.enc1(x))
        x_pool = self.pool(x1)
        x_up = self.up(x_pool)
        out = self.sigmoid(self.dec1(x_up))
        return out

def get_model(weights_path: str = None):
    """
    Instancia MiniUNet y carga los pesos exportados desde Colab.
    """
    model = MiniUNet()
    
    if weights_path:
        try:
            state_dict = torch.load(weights_path, map_location=torch.device('cpu'))
            model.load_state_dict(state_dict)
            print(f"🧠 Pesos cargados correctamente desde {weights_path}")
        except Exception as e:
            print(f"⚠️ Advertencia: No se pudieron cargar los pesos. Error: {e}")
            
    model.eval()
    return model