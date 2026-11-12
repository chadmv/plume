"""Pieces both viewer windows draw with: the viewport's textures, the banners over the viewport, the
backgrounds (`B`), and the ImPlot context the numbers strip needs."""

import numpy as np
import OpenGL.GL as gl
from imgui_bundle import imgui, implot

from plume.recipe.schema import LookSettings
from plume.view.viewport import DARK_BACKGROUND

ERROR_COLOR = (0.75, 0.12, 0.12, 0.9)
NOTE_COLOR = (0.55, 0.45, 0.1, 0.85)
BACKGROUND_NAMES = ("neutral", "grass", "dark")
TEXT_ROW_PX = 18


def background_hex(look: LookSettings, index: int) -> str:
    """The recipe's neutral or grass background, or the dark gray, by `B`'s index."""
    return (look.backgrounds.neutral, look.backgrounds.grass, DARK_BACKGROUND)[index]


class Textures:
    """One OpenGL texture per viewport pane, refilled from RGBA8 images."""

    def __init__(self, panes: int = 2):
        self.ids: list[int | None] = [None] * panes

    def upload(self, pane: int, image: np.ndarray) -> None:
        if self.ids[pane] is None:
            self.ids[pane] = int(gl.glGenTextures(1))
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.ids[pane])
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.ids[pane])
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        height, width = image.shape[:2]
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                        np.ascontiguousarray(image))

    def image(self, pane: int, width: float, height: float) -> None:
        """Draws the pane's texture as an ImGui image (a black pixel until one is uploaded)."""
        if self.ids[pane] is None:
            self.upload(pane, np.zeros((1, 1, 4), dtype=np.uint8))
        imgui.image(imgui.ImTextureRef(self.ids[pane]), imgui.ImVec2(width, height))

    def delete(self) -> None:
        textures = [texture for texture in self.ids if texture is not None]
        if textures:
            gl.glDeleteTextures(textures)
        self.ids = [None] * len(self.ids)


def draw_text_lines(draw_list, origin, lines: list[str]) -> float:
    """White lines in the viewport's top left; returns the y below them."""
    white = imgui.get_color_u32(imgui.ImVec4(1.0, 1.0, 1.0, 0.95))
    for row, text in enumerate(lines):
        draw_list.add_text(imgui.ImVec2(origin.x + 8, origin.y + 6 + row * TEXT_ROW_PX), white, text)
    return origin.y + 6 + len(lines) * TEXT_ROW_PX + 4


def draw_banners(draw_list, origin, width: int, y: float, banners: list[tuple[tuple, str]]) -> None:
    """Colored boxes of wrapped text, one under another from `y`."""
    white = imgui.get_color_u32(imgui.ImVec4(1.0, 1.0, 1.0, 0.95))
    for color, text in banners:
        text_size = imgui.calc_text_size(text, wrap_width=width - 32)
        draw_list.add_rect_filled(imgui.ImVec2(origin.x + 8, y),
                                  imgui.ImVec2(origin.x + 24 + text_size.x, y + text_size.y + 8),
                                  imgui.get_color_u32(imgui.ImVec4(*color)))
        draw_list.add_text(imgui.get_font(), imgui.get_font_size(), imgui.ImVec2(origin.x + 16, y + 4), white, text,
                           wrap_width=width - 32)
        y += text_size.y + 12


def start_plotting() -> None:
    """Creates the ImPlot context (the numbers strip); call once after the window opens."""
    implot.create_context()


def stop_plotting() -> None:
    implot.destroy_context()
