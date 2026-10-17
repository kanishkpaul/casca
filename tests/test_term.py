import io

from casca import term


class Tty(io.StringIO):
    def isatty(self):
        return True


def test_no_color_and_pipes_get_no_colour(monkeypatch):
    monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    assert term.color_system("auto", Tty()) is None
    monkeypatch.delenv("NO_COLOR")
    assert term.color_system("auto", io.StringIO()) is None
    assert term.color_system("always", io.StringIO()) in ("256", "truecolor")


def test_light_terminals_get_the_light_palette(monkeypatch):
    monkeypatch.setenv("CASCA_THEME", "light")
    assert term.polarity() == "light" and term.PALETTES["light"]["ui_accent"] != term.PALETTES["dark"]["ui_accent"]


def test_identity_comes_from_the_kit():
    assert term.IDENTITY["glyph"] == "⬡" and "CASCA" not in term.IDENTITY["banner"]
