from textual.screen import Screen
from textual.widgets import Static

class HealthScreen(Screen):
    def compose(self):
        yield Static("Health — Coming in Task 11")
