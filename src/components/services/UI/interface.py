from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding
from datetime import datetime

# Importe sua lógica aqui
# from src.components.user.user import evove

class EvoveInterface(App):
    """Uma interface responsiva para o sistema Evove."""
    
    CSS = """
    Screen {
        background: #1a1b26;
    }

    #process-view {
        height: 20%;
        border: double $accent;
        content-align: center middle;
        background: #24283b;
        color: white;
        text-style: bold;
    }

    #buffer-view {
        height: 20%;
        border: tall $secondary;
        content-align: center middle;
        font-size: 150%;
    }

    #bottom-row {
        height: 60%;
    }

    #keypad-view {
        width: 40%;
        border: round $primary;
        content-align: center middle;
    }

    #log-view {
        width: 60%;
        border: round $success;
        padding: 1;
    }

    .highlight { color: #e0af68; }
    .success { color: #9ece6a; }
    """

    # Atributo reativo: quando o buffer muda, a tela atualiza sozinha
    buffer = ""

    def compose(self) -> ComposeResult:
        """Estrutura da tela."""
        yield Header(show_clock=True)
        yield Static("⚪ (Aguardando) -> ... -> ⭐ (...)", id="process-view")
        yield Static("801 - 2 - 50_", id="buffer-view")
        
        with Horizontal(id="bottom-row"):
            yield Static(self.get_phone_ascii(), id="keypad-view")
            yield Static("LOGS DO SISTEMA\n---\nPronto para entrada...", id="log-view")
        
        yield Footer()

    def get_phone_ascii(self):
        return (
            "┌───┬───┬───┐\n"
            "│ 1 │ 2 │ 3 │\n"
            "├───┼───┼───┤\n"
            "│ 4 │ 5 │ 6 │\n"
            "├───┼───┼───┤\n"
            "│ 7 │ 8 │ 9 │\n"
            "├───┼───┼───┤\n"
            "│ * │ 0 │ # │\n"
            "└───┴───┴───┘"
        )

    def on_key(self, event):
        """Gerencia as teclas sem precisar de readchar."""
        if event.key.isdigit():
            self.buffer += event.key
        elif event.key == "backspace":
            self.buffer = self.buffer[:-1]
        elif event.key == "escape":
            self.exit()

        self.update_ui()

    def update_ui(self):
        """Atualiza os textos das 'janelas'."""
        # Aqui você chamaria seu parse_buffer(self.buffer)
        formatted_buffer = self.buffer + "_" # Simulação simples
        
        self.query_one("#buffer-view").update(f"[b][yellow]{formatted_buffer}[/][/]")
        self.query_one("#log-view").update(f"Buffer Raw: {self.buffer}\nTeclas: {len(self.buffer)}")

if __name__ == "__main__":
    app = EvoveInterface()
    app.run()
