from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseModelAdapter(ABC):
    """
    Abstract interface for local model execution runtimes.
    Ensures the main application is completely decoupled from backend specifics (Ollama, PyTorch/Laya).
    """

    @abstractmethod
    def load(self) -> None:
        """Load the model weights into memory/device."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Unload the model and release GPU VRAM and system memory."""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if the model is currently resident in memory/GPU."""
        pass

    @abstractmethod
    def get_resource_usage(self) -> Dict[str, Any]:
        """Query currently consumed VRAM, RAM, and device info."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform a quick operational health check."""
        pass

