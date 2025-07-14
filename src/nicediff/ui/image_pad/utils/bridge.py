import json
from nicegui import ui

class CanvasBridge:
    def __init__(self):
        self.handlers = {}
    def register_handler(self, event_type, handler):
        self.handlers[event_type] = handler
    def send_to_canvas(self, command, data):
        ui.run_javascript(f'window.canvasManager.{command}({json.dumps(data)})')
    def receive_from_canvas(self, event_type, data):
        if event_type in self.handlers:
            self.handlers[event_type](data) 