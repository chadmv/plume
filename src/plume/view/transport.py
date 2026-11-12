"""The transport (spec V3): the playhead over a run's kept frames (or a sheet's frames), play and pause,
stepping, speed, loop, and the bar that shows them with the scrub slider. Shared by the recipe window and
the sheet-only window.

Playback steps whole frames at the frames' own fps times the speed; frames that were not kept are skipped,
never interpolated. While a live run is still landing frames, a playing playhead follows the newest.
"""

from imgui_bundle import imgui

SPEEDS = (0.25, 0.5, 1.0, 2.0)


class Transport:
    """The playhead and the play state between window updates."""

    def __init__(self):
        self.playhead = 0
        self.playing = True
        self.speed = 1.0
        self.loop = True
        self.play_clock_s = 0.0

    def restart(self) -> None:
        """A new simulation: back to its first frame."""
        self.playhead = 0
        self.play_clock_s = 0.0

    def advance(self, dt_s: float, kept: list[int], fps: float, live: bool) -> None:
        """Moves the playhead by `dt_s` of wall time over the `kept` frames; `live`: frames are still
        landing."""
        if not kept:
            return
        if live:
            if self.playing:
                self.playhead = kept[-1]  # a live run's playhead follows the newest frame
            return
        if not self.playing:
            return
        self.play_clock_s += dt_s * self.speed
        frame_s = 1.0 / fps
        while self.play_clock_s >= frame_s:
            self.play_clock_s -= frame_s
            later = [frame for frame in kept if frame > self.playhead]
            if later:
                self.playhead = later[0]
            elif self.loop:
                self.playhead = kept[0]
            else:
                self.playing = False
                self.play_clock_s = 0.0
                break

    def step_to(self, where: str, kept: list[int]) -> None:
        """`first`, `last`, `next` or `previous` kept frame; pauses."""
        if not kept:
            return
        self.playing = False
        if where == "first":
            self.playhead = kept[0]
        elif where == "last":
            self.playhead = kept[-1]
        elif where == "next":
            self.playhead = next((frame for frame in kept if frame > self.playhead), kept[-1])
        else:
            self.playhead = next((frame for frame in reversed(kept) if frame < self.playhead), kept[0])

    def scrub_to(self, frame: int, kept: list[int]) -> None:
        """The latest kept frame at or before `frame` (else the first); pauses."""
        if not kept:
            return
        earlier = [index for index in kept if index <= frame]
        self.playhead = earlier[-1] if earlier else kept[0]
        self.playing = False

    def keys(self, io, kept: list[int]) -> None:
        """Space plays and pauses; `,` and `.` step, with Shift the first and last frame."""
        pressed = imgui.is_key_pressed
        if pressed(imgui.Key.space, False):
            self.playing = not self.playing
        if pressed(imgui.Key.comma):
            self.step_to("first" if io.key_shift else "previous", kept)
        if pressed(imgui.Key.period):
            self.step_to("last" if io.key_shift else "next", kept)

    def draw(self, frames: int, kept: list[int], progress: float, status: str, scrub_limit: int) -> None:
        """The bar: play, step buttons, speed, loop, the progress bar with `status`, and the scrub slider
        (held at or before `scrub_limit`, the last frame that has landed)."""
        if imgui.button("Pause" if self.playing else "Play"):
            self.playing = not self.playing
        for label, where in (("|<", "first"), ("<", "previous"), (">", "next"), (">|", "last")):
            imgui.same_line()
            if imgui.button(label):
                self.step_to(where, kept)
        imgui.same_line()
        imgui.set_next_item_width(90)
        if imgui.begin_combo("speed", f"{self.speed:g}x"):
            for speed in SPEEDS:
                if imgui.selectable(f"{speed:g}x", speed == self.speed)[0]:
                    self.speed = speed
            imgui.end_combo()
        imgui.same_line()
        _, self.loop = imgui.checkbox("loop", self.loop)
        imgui.same_line()
        imgui.progress_bar(progress, imgui.ImVec2(200, 0), status)
        imgui.set_next_item_width(-1)
        changed, frame = imgui.slider_int("##scrub", self.playhead, 0, max(frames - 1, 0), "frame %d")
        if changed:
            self.scrub_to(min(frame, max(scrub_limit, 0)), kept)
