#Odl
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv

class PointerGNN(nn.Module):
    """
    Графовая нейросеть с указателем (Pointer Network) для последовательного выбора узлов.
    Вход: Data.x (features), Data.edge_index, Data.batch
    Выход: логиты вероятностей выбора каждого узла [batch_size, num_nodes]
    """
    def __init__(self, in_channels: int, hidden_channels: int):
        super().__init__()
        # Два графовых сверточных слоя
        self.conv1 = GCNConv(in_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        # Линейный указатель
        self.pointer = nn.Linear(hidden_channels, 1)

    def forward(self, data):
        x, edge_index, batch = data.x, data.edge_index, data.batch
        # Графовые слои
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.5, training=self.training)
        x = self.conv2(x, edge_index)

        # Линейный слой выдаёт логиты для каждого узла
        scores = self.pointer(x).squeeze()  # shape: [total_nodes]

        # Разбиваем на батчи: предполагаем одинаковое число узлов на граф
        batch_size = batch.max().item() + 1
        num_nodes = scores.size(0) // batch_size
        scores = scores.view(batch_size, num_nodes)

        return scores  # shape: [batch_size, num_nodes]
