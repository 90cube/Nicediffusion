from abc import ABC, abstractmethod

class ModeHandler(ABC):
    @abstractmethod
    def setup(self, container):
        pass
    @abstractmethod
    def activate(self):
        pass
    @abstractmethod
    def deactivate(self):
        pass
    @abstractmethod
    def get_generation_data(self):
        pass 