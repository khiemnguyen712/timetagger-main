"""
Front end implementation in PScript.
"""

from pscript import this_is_js
from pscript.stubs import window, Math, time, perf_counter


if this_is_js():
    dt = window.dt
    utils = window.utils
    dialogs = window.dialogs
    BaseCanvas = window.utils.BaseCanvas
else:
    BaseCanvas = object


SMALLER = 0.85
BUTTON_ROUNDNESS = 4
RECORD_AREA_ROUNDNESS = 4
RECORD_ROUNDNESS = 6
COLORBAND_ROUNDNESS = 4
ANALYSIS_ROUNDNESS = 6

PI = 3.141_592_653_589_793

COLORS = {}

# These get updated when the canvas resizes
FONT = {
    "size": 16,
    "condensed": "Ubuntu Condensed, Arial, sans-serif",
    "wide": "Ubuntu, Arial, sans-serif",
    "mono": "Space Mono, Consolas, Monospace, Courier New",
    "default": "Ubuntu, Arial, sans-serif",
}


def init_module():
    set_width_mode()
    set_colors()
    if window.matchMedia:
        try:
            window.matchMedia("(prefers-color-scheme: dark)").addEventListener(
                "change", set_colors
            )
        except Exception:
            pass  # e.g. Mobile Safari


window.addEventListener("load", init_module)


def set_width_mode():
    # Note that the width modes must match the css classes in _style_embed.scss
    content_div = window.document.getElementById("main-content")
    # Clear
    entries = []
    add = lambda x: entries.push(x)
    content_div.classList.forEach(add)
    for entry in entries:
        if "width-" in entry:
            content_div.classList.remove(entry)
    # Apply
    width_mode = window.simplesettings.get("width_mode")
    content_div.classList.add("width-" + width_mode)


# Also see e.g. https://www.canva.com/colors/color-wheel/
def set_colors():
    # Dark vs light mode
    mode = mode = window.simplesettings.get("darkmode")
    if mode == 1:
        light_mode = True
    elif mode == 2:
        light_mode = False
    else:
        light_mode = True
        if window.matchMedia:
            if window.matchMedia("(prefers-color-scheme: dark)").matches:
                light_mode = False

    # Theme palette
    COLORS.prim1_clr = "#0F2C3E"
    COLORS.prim2_clr = "#A4B0B8"
    COLORS.sec1_clr = "#E6E7E5"
    COLORS.sec2_clr = "#F4F4F4"
    COLORS.acc_clr = "#DEAA22"

    # Grays chosen to work in both light and dark mode
    COLORS.tick_text = "rgba(130, 130, 130, 1)"
    COLORS.tick_stripe1 = COLORS.prim1_clr  # "rgba(130, 130, 130, 0.6)"  # day
    COLORS.tick_stripe2 = "rgba(130, 130, 130, 0.4)"  # major
    COLORS.tick_stripe3 = "rgba(130, 130, 130, 0.08)"  # minor

    if light_mode:
        COLORS.background1 = "rgba(244, 244, 244, 1)"  # == #f4f4f4  - must end in "1)"
        COLORS.top_bg = COLORS.prim1_clr

        COLORS.panel_bg = COLORS.sec1_clr
        COLORS.panel_edge = COLORS.prim1_clr

        COLORS.button_bg = "#FFFFFF"
        COLORS.button_tag_bg = "#FFFFFF"
        COLORS.button_shadow = "rgba(0, 0, 0, 0.3)"

        COLORS.button_text = COLORS.prim1_clr
        COLORS.button_tag_text = COLORS.prim1_clr
        COLORS.button_text_disabled = COLORS.prim2_clr

        COLORS.record_bg = "#FAFAFA"
        COLORS.record_bg_running = "#F9F2E1"
        COLORS.record_text = COLORS.prim1_clr
        COLORS.record_edge = COLORS.panel_edge

        window.document.body.classList.remove("darkmode")

    else:
        # App background (use rgba so the color can be re-used with different alpha)
        COLORS.background1 = "rgba(23, 30, 40, 1)"  # must end in "1)"
        COLORS.top_bg = COLORS.prim1_clr

        COLORS.panel_bg = COLORS.prim1_clr
        COLORS.panel_edge = "#0A1419"

        COLORS.button_bg = "#32373F"
        COLORS.button_tag_bg = "#222A32"
        COLORS.button_shadow = "rgba(0, 0, 0, 0.8)"

        COLORS.button_text = "#A4B0B8"
        COLORS.button_tag_text = "#A4B0B8"
        COLORS.button_text_disabled = "#7F838B"

        COLORS.record_bg = "#32373E"
        COLORS.record_bg_running = "#3B3935"
        COLORS.record_text = "#A4B0B8"
        COLORS.record_edge = "#4B4B4B"

        window.document.body.classList.add("darkmode")


def draw_tag(ctx, tag, x, y):
    """Like fillText, but colors the hashtag in the tag's color."""
    ori_color = ctx.fillStyle
    ctx.fillStyle = window.store.settings.get_color_for_tag(tag)
    ctx.fillText(tag[0], x, y)
    x += ctx.measureText(tag[0]).width
    ctx.fillStyle = ori_color
    ctx.fillText(tag[1:], x, y)


class TimeTaggerCanvas(BaseCanvas):
    """Main class for the time app. Does the layout and acts as the root
    application object.
    """

    def __init__(self, canvas):
        super().__init__(canvas)

        self._now = None

        self._last_picked_widget = None
        self._prefer_show_analytics = False

        self.range = TimeRange(self)

        self.notification_dialog = dialogs.NotificationDialog(self)
        self.menu_dialog = dialogs.MenuDialog(self)
        self.timeselection_dialog = dialogs.TimeSelectionDialog(self)
        self.settings_dialog = dialogs.SettingsDialog(self)
        self.record_dialog = dialogs.RecordDialog(self)
        self.tag_combo_dialog = dialogs.TagComboDialog(self)
        self.tag_dialog = dialogs.TagDialog(self)
        self.report_dialog = dialogs.ReportDialog(self)
        self.tag_preset_dialog = dialogs.TagPresetsDialog(self)
        self.tag_rename_dialog = dialogs.TagRenameDialog(self)
        self.search_dialog = dialogs.SearchDialog(self)
        self.export_dialog = dialogs.ExportDialog(self)
        self.import_dialog = dialogs.ImportDialog(self)
        self.guide_dialog = dialogs.GuideDialog(self)
        self.pomodoro_dialog = dialogs.PomodoroDialog(self)

        # The order here is also the draw-order. Records must come after analytics.
        self.widgets = {
            "AnalyticsWidget": AnalyticsWidget(self),
            "RecordsWidget": RecordsWidget(self),
            "TopWidget": TopWidget(self),
        }

        self.node.addEventListener("blur", self.on_blur)

    def _pick_widget(self, x, y):
        for widget in reversed(self.widgets.values()):
            x1, y1, x2, y2 = widget.rect
            if x1 <= x <= x2:
                if y1 <= y <= y2:
                    return widget

    def notify_once(self, message):
        """Notify the user once (for each session)."""
        cache = self._notification_cache or {}
        self._notification_cache = cache
        if message not in cache:
            cache[message] = True
            self.notification_dialog.open(message, "Notification")

    def now(self):
        if self._now is not None:
            return self._now
        return dt.now()

    def on_resize(self):
        """Perform layout; set sizes of widgets. We can go all responsive here."""

        # Establish the margin. We are relatively close to the edges
        # by default, but introduce more margin on wider screens.
        min_margin = 5
        extra_margin = 0
        if self.w > 800:
            extra_margin = (self.w - 800) * 0.1
        margin = min_margin + extra_margin

        #  Determine width of record area, and margin between records and overview.
        space_to_divide = self.w - margin - margin
        if space_to_divide >= 785:
            margin2 = 40 + extra_margin
            records_width = (space_to_divide - margin2) / 2
        else:
            margin2 = 5
            if self._prefer_show_analytics:
                records_width = 30
            else:
                records_width = (space_to_divide - margin2) - 30

        # Determine splitter positions
        #
        #   | records | | analytics |
        # 0 1         2 3           4 5

        x0 = 0
        x1 = margin
        x2 = x1 + max(0, records_width)
        x3 = x2 + margin2
        x4 = self.w - margin
        x5 = self.w  # noqa

        x1 = self.grid_round(x1)
        x2 = self.grid_round(x2)
        x3 = self.grid_round(x3)
        x4 = self.grid_round(x4)

        y0 = 0
        y1 = self.grid_round(140)
        y3 = self.grid_round(max(y1 + 40, self.h - 15))

        self.widgets["TopWidget"].rect = x0, y0, x5, y1
        self.widgets["RecordsWidget"].rect = x1, y1, x2, y3
        self.widgets["AnalyticsWidget"].rect = x3, y1, x4, y3

        # Determine reference font
        FONT.default = FONT.condensed if self.w < 450 else FONT.wide

    def on_draw(self, ctx):
        # Set current moment as consistent reference for "now"
        self._now = dt.now()

        # Update the range if it is animating
        self.range.animation_update()

        # Clear / draw background
        ctx.clearRect(0, 0, self.w, self.h)
        # ctx.fillStyle = COLORS.background1
        # ctx.fillRect(0, 0, self.w, self.h)

        # Draw icon in bottom right
        if self.w >= 800:
            iconw = 162 if self.w >= 400 else 96
            iconh = iconw / 6
            ctx.drawImage(
                window.document.getElementById("ttlogo_tg"),
                self.w - iconw - 5,
                self.h - iconh - 5,
                iconw,
                iconh,
            )

        # Determine if we are logged in and all is right (e.g. token not expired)
        cantuse = None
        if window.store.get_auth:
            auth = window.store.get_auth()
            if not auth:
                cantuse = "You are logged out."
            elif auth.cantuse:
                cantuse = auth.cantuse

        if cantuse:
            # Meh
            ctx.textAlign = "center"
            ctx.textBaseline = "middle"
            ctx.fillStyle = COLORS.prim1_clr
            utils.fit_font_size(ctx, self.w - 100, FONT.default, cantuse, 30)
            ctx.fillText(cantuse, self.w / 2, self.h / 3)
            # Draw menu and login button
            ctx.save()
            try:
                self.widgets["TopWidget"].on_draw(ctx, True)  # menu only
            finally:
                ctx.restore()
        else:
            # Draw child widgets
            for widget in self.widgets.values():
                ctx.save()
                try:
                    widget.on_draw(ctx)
                finally:
                    ctx.restore()

        self._now = None  # Use real "now" in between draws

    def on_wheel(self, ev):
        w = self._pick_widget(*ev.pos)
        if w is not None:
            return w.on_wheel(ev)

    def on_pointer(self, ev):
        if "down" in ev.type and ev.ntouches == 1:
            self._last_picked_widget = self._pick_widget(*ev.pos)
        for widget in self.widgets.values():
            if widget is self._last_picked_widget:
                widget.on_pointer(ev)
            else:
                widget.on_pointer_outside(ev)

    def on_blur(self, ev):
        for widget in self.widgets.values():
            widget.on_pointer_outside(ev)


# The available scales to view the time at, and the corresponding step sizes
# Search for "Special scale" to see where we have special cases.
SCALES = [
    ("5m", "1m", 8 * 60, ""),
    ("20m", "1m", 35 * 60, ""),
    ("1h", "5m", 1.8 * 3600, ""),
    ("3h", "5m", 3.6 * 3600, ""),
    ("6h", "5m", 8.5 * 3600, ""),  # Kind of the default view
    ("12h", "1h", 15 * 3600, ""),
    ("1D", "1h", 2 * 86400, "Day"),
    ("1W", "1D", 1.7 * 7 * 86400, "Week"),
    # ("3W", "1W", 3.5 * 7 * 86400, "3x7"),
    ("1M", "1M", 5 * 7 * 86400, "Month"),  # all step sizes are awkward here :)
    ("7W", "1W", 9 * 7 * 86400, "7x7"),
    ("3M", "1M", 200 * 86400, "Quarter"),
    ("1Y", "1M", 550 * 86400, "Year"),  # step per quarter of month?
    ("2Y", "1M", 1280 * 86400, ""),
    ("5Y", "1Y", 2737 * 86400, ""),
    ("10Y", "1Y", 5475 * 86400, ""),
    ("20Y", "1Y", 999999999999, ""),
]

# List of intervals for tick marks. The last element is the number of seconds
# between two items, and is used to select an interval based on available pixel space.
# Major interval, minor interval, granularity for tick text, nsecs
INTERVALS = [
    ("1m", "10s", "mm", 60),
    ("2m", "10s", "mm", 120),
    ("5m", "1m", "mm", 300),
    ("10m", "1m", "mm", 600),
    ("30m", "5m", "mm", 1800),
    ("1h", "10m", "mm", 3600),
    ("2h", "15m", "mm", 7200),
    ("6h", "1h", "hh", 21600),
    ("12h", "1h", "hh", 43200),
    ("1D", "3h", "DD", 86400),
    ("2D", "6h", "DD", 172_800),
    ("4D", "1D", "DM", 345_600),
    ("8D", "1D", "DM", 691200),
    # Below numbers are estimates, but that is fine;
    # they are only used to estimate the space between ticks
    ("1M", "5D", "MM", 2_592_000),  # days are a bit weird, ah well ...
    ("3M", "1M", "MM", 7_776_000),
    ("1Y", "1M", "YY", 31_536_000),
    ("1Y", "3M", "YY", 63_072_000),  # weird to show every other year
    ("5Y", "1Y", "YY", 157_680_000),
    ("10Y", "1Y", "YY", 315_360_000),
]


class TimeRange:
    """Object to keep track of the time range."""

    def __init__(self, canvas):
        self._canvas = canvas

        # The animate variable is normally None. During animation, it is a tuple
        self._animate = None

        # Init time to the current full day
        self._t1 = dt.floor(self._canvas.now(), "1D")
        self._t2 = dt.add(self._t1, "1D")
        self._t1, self._t2 = self.get_snap_range()  # snap non-animated

    def get_today_range(self):
        """Get the sensible range for "today"."""
        # Get settings
        today_snap_offset = window.simplesettings.get("today_snap_offset")
        today_end_offset = window.simplesettings.get("today_end_offset")
        # Get some reference data
        now = self._canvas.now()
        current_t1, current_t2 = self.get_target_range()
        # The math
        t1_actual = dt.floor(now, "1D")
        t1 = dt.add(t1_actual, today_snap_offset) if today_snap_offset else t1_actual
        # If it's after midnight, we might still be in the previous offset day.
        if t1 > now:
            t1 = dt.add(t1, "-1D")
        t2 = dt.add(t1, "1D")
        t2 = dt.add(t2, today_end_offset) if today_end_offset else t2
        # Toggle to a full day (0h-24h) if the range already matches.
        if t1 == current_t1 and t2 == current_t2:
            t1 = t1_actual
            t2 = dt.add(t1, "1D")
        return t1, t2

    def get_range(self):
        """Get the current time range (as a 2-element tuple, in seconds)."""
        return self._t1, self._t2

    def get_target_range(self):
        """Get the target range (where we're animating to). If no animation
        is in effect, this returns the same as get_range().
        """
        if self._animate is not None:
            (
                t1_old,
                t2_old,
                t1_new,
                t2_new,
                animation_time,
                animation_end,
                snap,
            ) = self._animate
            return t1_new, t2_new
        else:
            return self._t1, self._t2

    def set_range(self, t1, t2):
        """Set the time range to the target t1 and t2, canceling any animation in progress."""
        assert t1 < t2
        self._t1, self._t2 = t1, t2
        self._animate = None
        self._canvas.update()

    def animate_range(self, t1, t2, animation_time=None, snap=True):
        """Animate the time range to the target t1 and t2, over the given animation time."""
        # Going from high scale to low (or reverse) takes longer
        if animation_time is None:
            nsecs1, nsecs2 = t2 - t1, self._t2 - self._t1
            factor = max(nsecs1, nsecs2) / min(nsecs1, nsecs2)
            animation_time = 0.3 + 0.1 * Math.log(factor)

        animation_end = self._canvas.now() + animation_time  # not rounded to seconds!
        self._animate = self._t1, self._t2, t1, t2, animation_time, animation_end, snap
        self._canvas.update()

    def animation_update(self):
        """Set new range for the current animation (if there is one)."""
        if self._animate is None:
            return

        (
            t1_old,
            t2_old,
            t1_new,
            t2_new,
            animation_time,
            animation_end,
            snap,
        ) = self._animate
        now = self._canvas.now()

        if now >= animation_end:
            # Done animating
            self._t1, self._t2 = t1_new, t2_new
            self._animate = None
            if snap:
                self.snap()  # Will animate to aligned range if not already aligned
        else:
            # Interpolate the transition
            f = (animation_end - now) / animation_time
            # Scale the f-factor exponentially with the scaling of the time
            nsecs_old = t2_old - t1_old
            nsecs_new = t2_new - t1_new
            x = Math.log(2 + nsecs_old) / Math.log(2 + nsecs_new)
            x = x**2  # Otherwise higher scaler animate slower
            f = f**x
            # Linear animation, or slower towards the end?
            # f = f ** 2
            self._t1 = f * t1_old + (1 - f) * t1_new
            self._t2 = f * t2_old + (1 - f) * t2_new
        self._canvas.update()

    def snap(self):
        """Snap to an aligned time range."""
        t1, t2 = self.get_target_range()
        t3, t4 = self.get_snap_range()
        if not (t1 == t3 and t2 == t4):
            self.animate_range(t3, t4)

    # Get range information

    def get_snap_range(self, scalestep=0):
        """Get the scale-aligned range that is closest to the current target range."""
        t3, t4, _ = self._get_snap_range(scalestep)
        return t3, t4

    def get_snap_seconds(self, rel_scale=0):
        """Get the nsecs for one step and the total range for the nearest
        snap range (or next/previous).
        """
        t1, t2, res = self._get_snap_range(rel_scale)
        nsecs_full = t2 - t1
        nsecs_step = dt.add(t1, res) - t1
        return nsecs_step, nsecs_full

    def _get_snap_range(self, scalestep=0):
        """Get the scale-aligned range that is closest to the current target range."""
        t1, t2 = self.get_target_range()
        nsecs = t2 - t1

        # First determine nearest scale
        for i in range(len(SCALES)):
            ran, res, max_nsecs, _ = SCALES[i]
            if nsecs < max_nsecs:
                break

        # Select scale
        scale_index = i + scalestep
        scale_index = max(0, min(len(SCALES) - 1, scale_index))
        ran, res, _, _ = SCALES[scale_index]

        # Short-circuit to avoid weirdness around summer/wintertime transitions
        if dt.round(t1, res) == t1 and dt.add(t1, ran) == t2:
            return t1, t2, res

        # Round
        t5 = 0.5 * (t1 + t2)  # center
        t3 = 0.5 * (t5 + dt.add(t5, "-" + ran))  # unrounded t3
        t3 = dt.round(t3, res)
        t4 = dt.add(t3, ran)
        return t3, t4, res

    def get_ticks(self, npixels):
        """Get the major and minor tick positions,
        based on the available space and current time-range.
        """
        PSCRIPT_OVERLOAD = False  # noqa

        t1, t2 = self.get_range()
        nsecs = t2 - t1

        # We use a cache with 1 entry, so if the "tick-args" are the
        # same as last time, the result is re-used.
        cache_key = str((t1, t2, npixels))
        if not self._cache_tick_data:
            self._cache_tick_data = {}
        if cache_key == self._cache_tick_data.key:
            return self._cache_tick_data.result
        else:
            self._cache_tick_data.key = cache_key

        # Determine interval - distance between ticks depends on total size;
        # if there is a lot of space, its ugly to have loads of ticks
        pixelref = 4
        min_distance = pixelref * (npixels / pixelref) ** 0.5
        min_interval = nsecs * min_distance / npixels
        for i in range(len(INTERVALS)):
            delta, minor_delta, granularity, interval = INTERVALS[i]
            if interval > min_interval:
                break

        # Select minor scale from next level if we are close to it.
        # This results in a smoother transition, as minor and major ticks alternate jumps.
        if i < len(INTERVALS) - 1:
            if (interval - min_interval) / interval < 0.125:  # 0.25 is too soon
                minor_delta = INTERVALS[i + 1][1]

        # When within hour range, deal with the summer- to winter-time transtion.
        # There is a duplicate hour, which needs special care to make it ticked.
        # For the winter- to summer-time transition there is a missing hour,
        # which is handled just fine.
        check_summertime_transition = "h" in delta or "m" in delta

        # Special scale for week zoom-levels, since days align to day-of-month.
        # When this is a week-view (range and res both include "W") we floor to
        # week boundaries, and make sure that the delta is 7D.
        for i in range(len(SCALES)):
            ran, res, max_nsecs, _ = SCALES[i]
            if nsecs < max_nsecs:
                break
        if ran.indexOf("W") >= 0 and res.indexOf("W") >= 0:
            delta = "1W"
            minor_delta = "1W"

        # Define ticks
        ticks = []
        minor_ticks = []
        maxi = min(2 * npixels / min_distance, 99)
        t = dt.floor(t1 - 0.1 * nsecs, delta)
        iter = -1
        while iter < maxi:  # just to be safe
            iter += 1
            pix_pos = (t - t1) * npixels / nsecs
            ticks.push((pix_pos, t))
            # Determine delta. The +1s and then floor is to take care
            # of the transition from wintertime to summertime.
            # Even then, t_new may still not advance for ios somehow (see #73).
            t_new = dt.floor(dt.add(t + 1, delta), delta)
            if t_new <= t:
                t_new = dt.add(t, delta)
            # Minor ticks
            t_minor = dt.add(t, minor_delta)
            iter_minor = -1
            while iter_minor < 20 and (t_new - t_minor) > 0:
                iter_minor += 1
                pix_pos = (t_minor - t1) * npixels / nsecs
                minor_ticks.push((pix_pos, t_minor))
                t_minor_new = dt.add(t_minor, minor_delta)
                if t_minor_new <= t_minor:
                    break  # failsafe
                t_minor = t_minor_new
            # Summertime transition?
            if check_summertime_transition and (t_new - t) > interval * 1.1:
                tc = dt.floor(t_new, "1D")
                for i in range(5):
                    tb = tc + 3600
                    tc = dt.add(tc, "1h")
                    if tc != tb:
                        # Add ticks at sumertime transition
                        tick_times = [tb] if t_new == tc else [tb, tc]
                        for tick_time in tick_times:
                            pix_pos = (tick_time - t1) * npixels / nsecs
                            ticks.push((pix_pos, tc))
                        # Add minor ticks at duplicate hour
                        d_minor = dt.add(t_new, minor_delta) - t_new
                        t_minor = tb + d_minor
                        iter_minor = -1
                        while iter_minor < 20 and t_minor < tc:
                            iter_minor += 1
                            pix_pos = (t_minor - t1) * npixels / nsecs + 3
                            minor_ticks.push((pix_pos, t_minor))
                            t_minor += d_minor
                        break
            # prepare for next
            if (t - t2) > 0:
                break
            t = t_new

        self._cache_tick_data.result = ticks, minor_ticks, granularity
        return self._cache_tick_data.result

    def get_stat_period(self):
        """Get the time period over which to display stats, given the current range."""
        # At some point we used get_snap_range(), so that the type of
        # record is a direct snap-hint. But it makes the animation from a large
        # nsecs to a small very slow, because a lot of stats will be drawn.
        t1, t2 = self.get_range()
        nsecs = t2 - t1

        if nsecs < 2 * 86400:
            return None, ""  # Don't draw stats, but records!

        for i in range(len(SCALES)):
            ran, res, max_nsecs, name = SCALES[i]
            if name and nsecs < max_nsecs:
                break

        # Special scale for the month level. There is no sensible res
        # for this level. The step-size is also 1M because nothing else
        # aligns. But we want the visible/clickable sections in the
        # record stats to be weeks (days is too many, months does not
        # allow zooming in).
        if ran == "1M":
            res = "1W"

        return res, name

    def get_context_header(self):
        """Get the text to provide context for the current range."""

        t1, t2 = self.get_range()
        nsecs = t2 - t1

        t2 -= 1

        day1 = dt.time2str(t1).split("T")[0]
        day2 = dt.time2str(t2).split("T")[0]

        # Get friendly stuff that we can display
        weekday1, weekday2 = dt.get_weekday_shortname(t1), dt.get_weekday_shortname(t2)
        monthname1, monthname2 = dt.get_month_shortname(t1), dt.get_month_shortname(t2)
        year1, month1, monthday1 = dt.get_year_month_day(t1)
        year2, month2, monthday2 = dt.get_year_month_day(t2)
        is_week_range = abs(nsecs - 86400 * 7) <= 4000  # var for summer/wintertime

        if day1 == day2:
            # Within a single day - finest granularity for the header
            header = f"{weekday1} {monthday1}  {monthname1} {year1}"
        elif day1[:7] == day2[:7]:
            # Within a single month
            if nsecs <= 86400 * 3:
                # Just 3 days - show weekdays
                header = f"{weekday1} {monthday1} - {weekday2} {monthday2}  {monthname1} {year1}"
            elif is_week_range and dt.is_first_day_of_week(t1):
                # Exactly a calender week
                wn = dt.get_weeknumber(t1)
                header = f"Week {wn}  {monthday1}-{monthday2}  {monthname1} {year1}"
            elif nsecs <= 86400 * 14:
                # Less than half a month
                header = f"{monthday1} - {monthday2}  {monthname1} {year1}"
            else:
                header = f"{monthname1}  {year1}"
        elif day1[:4] == day2[:4]:
            # Within a single year
            if is_week_range and dt.is_first_day_of_week(t1):
                # Exactly a calender week
                wn = dt.get_weeknumber(t1)
                header = f"Week {wn}  {monthname1} / {monthname2} {year1}"
            elif nsecs < 30 * 86400:
                # Less than one month
                header = f"{monthname1} / {monthname2}  {year1}"
            else:
                # Multi month
                header = f"{year1}"
                if day1[5:] == "01-01" and day2[5:] == "12-31":
                    pass
                elif day1[5:] == "01-01" and day2[5:] == "03-31":
                    header = f"Q1  {year1}"
                elif day1[5:] == "04-01" and day2[5:] == "06-30":
                    header = f"Q2  {year1}"
                elif day1[5:] == "07-01" and day2[5:] == "09-30":
                    header = f"Q3  {year1}"
                elif day1[5:] == "10-01" and day2[5:] == "12-31":
                    header = f"Q4  {year1}"
                else:
                    header = f"{monthname1} - {monthname2}  {year1}"
        else:
            # Multi-year
            if is_week_range and dt.is_first_day_of_week(t1):
                wn = dt.get_weeknumber(t1)
                header = f"Week {wn}  {monthname1} {year1} / {monthname2} {year2}"
            elif nsecs < 30 * 86400:  # Less than one month
                header = f"{monthname1} {year1} / {monthname2} {year2}"
            elif nsecs < 367 * 86400:  # Less than a year
                header = f"{monthname1} {year1} - {monthname2} {year2}"
            else:
                header = f"{year1} - {year2}"

        return header


class Widget:
    """Base Widget class."""

    def __init__(self, canvas):
        self._canvas = canvas
        self.rect = 0, 0, 0, 0  # (x1, y1, x2, y2) - Layout is done by the canvas
        self.on_init()

    def update(self):
        """Invoke a new draw."""
        self._canvas.update()

    def on_init(self):
        pass

    def on_wheel(self, ev):
        pass

    def on_pointer(self, ev):
        pass

    def on_pointer_outside(self, ev):
        pass

    def on_draw(self, ctx):
        pass

    def _draw_button(self, ctx, x, y, given_w, h, text, action, tt, options):
        PSCRIPT_OVERLOAD = False  # noqa

        # Set and collect options
        opt = {
            "font": FONT.default,
            "ref": "topleft",
            "color": COLORS.button_text,
            "padding": 7,
            "space": 5,
            "body": COLORS.button_bg,
        }
        opt.update(options)

        if text.toUpperCase:  # is string
            texts = [text]
        else:
            texts = list(text)

        # Measure texts
        texts2 = []
        widths = []
        fonts = []
        fontsize = int(0.5 * h)
        if given_w:
            fontsize = min(fontsize, int(0.6 * given_w))
        for i in range(len(texts)):
            text = texts[i]
            if len(text) == 0:
                continue
            elif text.startswith("fas-"):
                text = text[4:]
                font = fontsize + "px FontAwesome"
            else:
                font = fontsize + "px " + opt.font
            ctx.font = font
            width = ctx.measureText(text).width
            texts2.push(text)
            fonts.push(font)
            widths.push(width)

        # Determine width
        needed_w = sum(widths) + 2 * opt.padding + opt.space * (len(widths) - 1)
        if given_w:
            w = given_w
            # scale = min(1, given_w / needed_w)
        else:
            w = needed_w
            # scale = 1

        # Determine bounding box
        if opt.ref.indexOf("right") >= 0:
            x2 = x
            x1 = x2 - w
        elif opt.ref.indexOf("center") >= 0:
            x1 = x - w / 2
            x2 = x + w / 2
        else:
            x1 = x
            x2 = x1 + w
        #
        if opt.ref.indexOf("bottom") >= 0:
            y2 = y
            y1 = y2 - h
        elif opt.ref.indexOf("middle") >= 0:
            y1 = y - h / 2
            y2 = y + h / 2
        else:
            y1 = y
            y2 = y1 + h

        # Register the button and tooltip
        ob = {"button": True, "action": action}
        self._picker.register(x1, y1, x2, y2, ob)
        hover = self._canvas.register_tooltip(x1, y1, x2, y2, tt, "below")

        # Draw button body and its shadow
        rn = BUTTON_ROUNDNESS
        if opt.body:
            ctx.fillStyle = opt.body
            for i in range(2):
                ctx.beginPath()
                ctx.arc(x1 + rn, y1 + rn, rn, 1.0 * PI, 1.5 * PI)
                ctx.arc(x2 - rn, y1 + rn, rn, 1.5 * PI, 2.0 * PI)
                ctx.arc(x2 - rn, y2 - rn, rn, 0.0 * PI, 0.5 * PI)
                ctx.arc(x1 + rn, y2 - rn, rn, 0.5 * PI, 1.0 * PI)
                ctx.closePath()
                if i == 0:
                    ctx.shadowBlur = 5 if hover else 2.5
                    ctx.shadowColor = COLORS.button_shadow
                    ctx.shadowOffsetY = 1.75
                else:
                    ctx.shadowBlur = 0
                    ctx.shadowOffsetY = 0
                ctx.fill()
        elif hover:
            ctx.fillStyle = "rgba(255,255,255,0.1)"
            ctx.beginPath()
            ctx.arc(x1 + rn, y1 + rn, rn, 1.0 * PI, 1.5 * PI)
            ctx.arc(x2 - rn, y1 + rn, rn, 1.5 * PI, 2.0 * PI)
            ctx.arc(x2 - rn, y2 - rn, rn, 0.0 * PI, 0.5 * PI)
            ctx.arc(x1 + rn, y2 - rn, rn, 0.5 * PI, 1.0 * PI)
            ctx.closePath()
            ctx.fill()

        # Get starting x
        x = x1 + opt.padding + 0.5 * (w - needed_w)

        # Draw the text on top
        ctx.textBaseline = "middle"
        ctx.textAlign = "left"
        ctx.fillStyle = opt.color
        for i in range(len(texts2)):
            text, width, font = texts2[i], widths[i], fonts[i]
            ctx.font = font
            if text.startsWith("#"):
                draw_tag(ctx, text, x, 0.5 * (y1 + y2))
            else:
                ctx.fillText(text, x, 0.5 * (y1 + y2))
            x += width + opt.space

        return w


class TopWidget(Widget):
    """Widget with menu, buttons, and time header."""

    def on_init(self):
        self._picker = utils.Picker()
        self._button_pressed = None
        self._current_scale = {}
        self._sync_feedback_xy = 0, 0, 0

        # Periodically draw the sync feedback icon. Make sure to do it via requestAnimationFrame
        window.setInterval(
            window.requestAnimationFrame, 100, self._draw_sync_feedback_callback
        )

        # For navigation with keys. Listen to canvas events, and window events (in
        # case canvas does not have focus), but don't listen for events from dialogs.
        window.addEventListener("keydown", self._on_key, 0)
        self._canvas.node.addEventListener("keydown", self._on_key, 0)

    def on_draw(self, ctx, menu_only=False):
        self._picker.clear()
        x1, y1, x2, y2 = self.rect
        avail_width = x2 - x1
        avail_height = y2 - y1

        # Guard for small screen space during resize
        if avail_width < 50 or avail_height < 20:
            return

        y4 = y2  # noqa - bottom
        y2 = y1 + 60
        y3 = y2 + 16

        h = 40
        margin = 8 if avail_width < 900 else 20

        # Top band background
        ctx.fillStyle = COLORS.top_bg
        ctx.fillRect(0, 0, x2, 60)

        # Draw icon in top-right
        icon_margin = 8
        icon_size = (y2 - y1) - 2 * icon_margin

        if icon_size:
            ctx.drawImage(
                window.document.getElementById("ttlogo_sl"),
                x2 - icon_size - icon_margin,
                y1 + icon_margin,
                icon_size,
                icon_size,
            )

        # Always draw the menu button
        self._draw_menu_button(ctx, x1, y1, x2, y2)

        # If menu-only, also draw login, then exit
        if menu_only:
            self._draw_button(
                ctx,
                0.5 * (x1 + x2),
                y3,
                None,
                h,
                "Login",
                "login",
                "",
                {"ref": "topcenter"},
            )
            return

        # Draw some more inside dark banner
        self._draw_header_text(ctx, x1 + 85, y1, x2 - 55, y2)

        now_scale, now_clr = self._get_now_scale()
        if now_scale != "1D" or window.simplesettings.get("today_snap_offset"):
            now_clr = COLORS.button_text

        # Draw buttons below the dark banner
        # We go from the center to the sides
        xc = (x1 + x2) / 2

        # Move a bit to the right on smaller screens
        xc += min(h, max(0, 800 - avail_width) * 0.18)

        # Draw up-down arrows
        ha = 0.75 * h
        yc = y3 + h / 2
        center_margin = -margin / 2
        if avail_width > 315:
            updown_w = self._draw_button(
                ctx,
                xc,
                yc - 2.5,
                h,
                ha,
                "fas-\uf077",
                "nav_backward",
                "Step backward [↑/pageUp]",
                {"ref": "bottomcenter"},
            )
            updown_w = self._draw_button(
                ctx,
                xc,
                yc + 2.5,
                h,
                ha,
                "fas-\uf078",
                "nav_forward",
                "Step forward [↓/pageDown]",
                {"ref": "topcenter"},
            )
            center_margin = updown_w / 2 + 3

        # -- move to the left

        x = xc - center_margin

        if avail_width > 400:
            x -= self._draw_button(
                ctx,
                x,
                y3,
                h,
                h,
                "fas-\uf010",
                "nav_zoom_" + self._current_scale["out"],
                "Zoom out [←]",
                {"ref": "ropright"},
            )
        x -= margin

        nav_width = ha

        x -= self._draw_button(
            ctx,
            x,
            y3,
            nav_width,
            h,
            "fas-\uf073",  # ["fas-\uf073", "fas-\uf0d7"],
            "nav_menu",
            "Select time range [t]",
            {"ref": "topright"},
        )

        if avail_width > 510:
            x -= 3
            x -= self._draw_button(
                ctx,
                x,
                y3,
                None,
                h,
                "Today",
                "nav_snap_today",  # "nav_snap_now" + now_scale,
                "Snap to today [d]",  # "Snap to now [Home]",
                {"ref": "topright", "color": now_clr, "font": FONT.condensed},
            )
        x -= margin

        self._draw_tracking_buttons(ctx, x, y3, h)

        # -- move to the right

        x = xc + center_margin

        if avail_width > 400:
            x += self._draw_button(
                ctx,
                x,
                y3,
                h,
                h,
                "fas-\uf00e",
                "nav_zoom_" + self._current_scale["in"],
                "Zoom in [→]",
                {"ref": "ropleft"},
            )
        x += margin

        x += self._draw_button(
            ctx,
            x,
            y3,
            None,
            h,
            ["fas-\uf15c", "Report" if avail_width > 490 else ""],
            "report",
            "Show report [r]",
            {"ref": "topleft", "font": FONT.condensed},
        )
        x += margin

        x += self._draw_button(
            ctx,
            x,
            y3,
            None,
            h,
            ["fas-\uf05a"],
            "guide",
            "Show guide [i]",
            {"ref": "topleft"},
        )

        if (
            dt.time_since_app_loaded() > 4
            and window.store.records.put_count < 5
            and not self._canvas.guide_dialog.initialized
        ):
            # Help new users find the guide
            y_balloon = y3 + h / 2
            ctx.strokeStyle = COLORS.acc_clr
            ctx.lineWidth = 3
            ctx.beginPath()
            ctx.moveTo(x + 5, y_balloon)
            ctx.lineTo(x + 35, y_balloon)
            ctx.stroke()
            text = "Handy guide!"
            options = {"ref": "middleleft", "color": "#000", "body": COLORS.acc_clr}
            self._draw_button(ctx, x + 30, y_balloon, None, 30, text, "", "", options)

    def _draw_menu_button(self, ctx, x1, y1, x2, y2):
        if window.store.__name__.startswith("Demo"):
            text = "Demo"
        elif window.store.__name__.startswith("Sandbox"):
            text = "Sandbox"
        else:
            text = ""

        sync_radius = 9
        yoffset = -6 if len(text) else 0

        d = (y2 - y1) / 2
        y = y1 + d
        x = x1 + d

        opt = {
            "body": False,
            "padding": 4,
            "ref": "centermiddle",
            "color": COLORS.sec2_clr,
        }
        dx = self._draw_button(
            ctx, x, y + yoffset, None, 48, "fas-\uf0c9", "menu", "", opt
        )

        # Draw title
        if text:
            ctx.textAlign = "center"
            ctx.textBaseline = "bottom"
            ctx.font = "12px " + FONT.default
            ctx.fillStyle = COLORS.acc_clr
            ctx.fillText(text, x, y2 - 8)

        self._draw_sync_feedback(ctx, x + d + 4, y, sync_radius)
        return d + dx + 2 * sync_radius + 4

    def _draw_sync_feedback(self, ctx, x1, y1, radius):
        self._sync_feedback_xy = x1, y1, radius
        return self._draw_sync_feedback_work(ctx)

    def _draw_sync_feedback_callback(self):
        ctx = self._canvas.node.getContext("2d")
        self._draw_sync_feedback_work(ctx, False)

    def _draw_sync_feedback_work(self, ctx, register=True):
        PSCRIPT_OVERLOAD = False  # noqa

        if window.document.hidden:
            return

        x, y, radius = self._sync_feedback_xy

        state = window.store.state

        # Get factor 0..1
        factor = window.store.sync_time
        factor = max(0, (factor[1] - dt.now()) / (factor[1] - factor[0] + 0.0001))
        factor = max(0, 1 - factor)

        ctx.lineWidth = 2.5
        color_circle = "rgba(255, 255, 255, 0.15)"
        color_progress = "rgba(255, 255, 255, 0.25)"
        color_text = COLORS.prim2_clr
        if state == "error" or state == "warning":
            color_text = "#f99"

        # Clear bg
        ctx.beginPath()
        ctx.arc(x, y, radius + ctx.lineWidth, 0, 2 * PI)
        ctx.fillStyle = COLORS.top_bg
        ctx.fill()

        # Outline
        ctx.beginPath()
        ctx.arc(x, y, radius, 0, 2 * PI)
        ctx.strokeStyle = color_circle
        ctx.stroke()

        # Progress
        ref_angle = -0.5 * PI
        ctx.beginPath()
        ctx.arc(x, y, radius, ref_angle, ref_angle + factor * 2 * PI)
        ctx.strokeStyle = color_progress
        ctx.stroke()

        # Draw indicator icon - rotating when syncing
        M = dict(
            pending="\uf067",  # uf067 uf055
            sync="\uf2f1",
            ok="\uf00c",  # uf560 uf560 uf00c
            warning="\uf071",
            error="\uf12a",
        )
        text = M.get(state, "\uf1eb")
        if text:
            ctx.save()
            try:
                ctx.translate(x, y)
                if state == "sync":
                    ctx.rotate(((0.5 * time()) % 1) * 2 * PI)
                ctx.font = radius * 1.1 + "px FontAwesome"
                ctx.textBaseline = "middle"
                ctx.textAlign = "center"
                ctx.fillStyle = color_text
                ctx.fillText(text, 0, 0)
            finally:
                ctx.restore()

        # Register tiny sync button
        if register:
            ob = {"button": True, "action": "dosync", "help": ""}
            self._picker.register(
                x - radius - 1, y - radius - 1, x + radius + 1, y + radius + 1, ob
            )

        return 2 * radius

    def _draw_tracking_buttons(self, ctx, x, y, h):
        PSCRIPT_OVERLOAD = False  # noqa

        now = self._canvas.now()

        start_tt = "Start recording [s]"
        stop_tt = "Stop recording [x]"

        # Define stop summary
        running_summary = ""
        records = window.store.records.get_running_records()
        has_running = False
        running_tag_color = None
        if len(records) > 0:
            has_running = True
            running_summary = "Timers running"
            if len(records) == 1:
                running_tags = window.store.records.tags_from_record(records[0])
                if len(running_tags) == 1:
                    running_tag_color = window.store.settings.get_color_for_tag(
                        running_tags[0]
                    )
                tagz = running_tags.join(" ")
                stop_tt += " " + tagz
                if window.simplesettings.get("show_stopwatch"):
                    running_summary = dt.duration_string(now - records[0].t1, True)
                    pomo = self._canvas.pomodoro_dialog.time_left()
                    if pomo:
                        running_summary = pomo + " | " + running_summary
                else:
                    running_summary = "Timer running"

        x0 = x

        self._update_favicon(has_running)

        # Start & stop button
        if has_running:
            dx = self._draw_button(
                ctx,
                x,
                y,
                h,
                h,
                "fas-\uf04d",
                "record_stopall",
                stop_tt,
                {
                    "ref": "topright",
                    "font": FONT.condensed,
                    "color": running_tag_color if running_tag_color else COLORS.acc_clr,
                },
            )
            x -= dx + 3
            dx = self._draw_button(
                ctx,
                x,
                y,
                h,
                h,
                "fas-\uf04b",
                "record_start",
                start_tt,
                {"ref": "topright", "font": FONT.condensed},
            )
            x -= dx
        else:
            # This but takes more space, but there it no stop but. So no reason
            # to reduce size when avail_width is low.
            dx = self._draw_button(
                ctx,
                x,
                y,
                None,
                h,
                ["fas-\uf04b", "Record"],
                "record_start",
                start_tt,
                {"ref": "topright", "font": FONT.condensed},
            )
            x -= dx

            if dt.time_since_app_loaded() > 3 and window.store.records.put_count == 0:
                # Help new users find the record button (can test this in the sandbox)
                x_balloon = x + 0.5 * dx
                ctx.strokeStyle = COLORS.acc_clr
                ctx.lineWidth = 3
                ctx.beginPath()
                ctx.moveTo(x_balloon, y + 40)
                ctx.lineTo(x_balloon, y + 80)
                ctx.stroke()
                text = "Press to start tracking time!"
                options = {"ref": "topleft", "color": "#000", "body": COLORS.acc_clr}
                self._draw_button(ctx, x, y + 70, None, 30, text, "", "", options)

        # Pomodoro button
        if window.simplesettings.get("pomodoro_enabled"):
            x -= 3
            dx = self._draw_button(
                ctx,
                x,
                y,
                None,
                h,
                "fas-\uf2f2",
                "pomo",
                "Show Pomodoro dialog",
                {"ref": "topright", "font": FONT.condensed},
            )
            x -= dx

        # Draw summary text
        ctx.textBaseline = "top"
        ctx.textAlign = "center"
        ctx.font = "12px " + FONT.default
        ctx.fillStyle = COLORS.prim2_clr
        ctx.fillText(running_summary, (x0 + x) / 2, y + h + 5)

        return x0 - x

    def _update_favicon(self, recording):
        if self._favicon_recording == recording:
            return
        self._favicon_recording = recording
        link = window.document.querySelector("link[rel~='icon']")
        extra = "_dot" if recording else ""
        link.href = "timetagger192_sf" + extra + ".png"

    def _get_now_scale(self):
        t1, t2 = self._canvas.range.get_range()  # get_snap_range()
        nsecs = t2 - t1
        now = self._canvas.now()

        # Select closest scale
        for i in range(len(SCALES)):
            ran, res, max_nsecs, _ = SCALES[i]
            if nsecs < max_nsecs:
                break
        i = min(len(SCALES) - 1, i)

        zoom_in_scale = SCALES[max(0, i - 1)][0]
        zoom_out_scale = SCALES[min(len(SCALES) - 1, i + 1)][0]

        # Overload for "sensible" scales
        now_scale = SCALES[i][0]
        if nsecs > 180 * 86400:
            now_scale = "1Y"

        # Are we currently on one of the reference scales?
        now_clr = COLORS.button_text
        t1_now = dt.floor(now, now_scale)
        if t1 == t1_now and t2 == dt.add(t1_now, now_scale):
            now_clr = COLORS.button_text_disabled

        # Store for later
        self._current_scale["now"] = now_scale
        self._current_scale["in"] = zoom_in_scale
        self._current_scale["out"] = zoom_out_scale

        return now_scale, now_clr

    def _draw_header_text(self, ctx, x1, y1, x2, y2):
        header = self._canvas.range.get_context_header() + " "  # margin

        x3 = (x2 + x1) / 2
        dy = (y2 - y1) / 2
        y3 = y1 + dy

        # Draw header
        ctx.textBaseline = "middle"
        ctx.textAlign = "center"
        #
        size = utils.fit_font_size(ctx, x2 - x1, FONT.default, header, 34)
        text1, _, text2 = header.partition("  ")
        if len(text2) == 0:
            # One part
            ctx.fillStyle = COLORS.sec2_clr
            ctx.fillText(header, x3, y3)
        elif size < 20:
            # Two parts below each-other
            size = utils.fit_font_size(ctx, x2 - x1, FONT.default, text2, 20)
            ctx.fillStyle = COLORS.acc_clr
            ctx.fillText(text1 + " ", x3, y3 - dy / 2.5)
            ctx.fillStyle = COLORS.sec2_clr
            ctx.fillText(text2, x3, y3 + dy / 2.5)
        else:
            # Two parts next to each-other
            text1 += "  "
            w1 = ctx.measureText(text1).width
            w2 = ctx.measureText(text2).width
            w = w1 + w2
            ctx.textAlign = "left"
            ctx.fillStyle = COLORS.acc_clr
            ctx.fillText(text1, x3 - w / 2, y3)
            ctx.fillStyle = COLORS.sec2_clr
            ctx.fillText(text2, x3 - w / 2 + w1, y3)

    def on_pointer(self, ev):
        x, y = ev.pos[0], ev.pos[1]
        if "down" in ev.type:
            picked = self._picker.pick(x, y)
            if picked is not None and picked.button:
                self._button_pressed = picked
                self.update()
        elif "up" in ev.type:
            self.update()
            pressed = self._button_pressed
            self._button_pressed = None
            picked = self._picker.pick(x, y)
            if pressed is not None and picked is not None:
                if picked.action == pressed.action:
                    self._handle_button_press(picked.action)

    def _on_key(self, e):
        if e.ctrlKey or e.metaKey or e.altKey:
            return  # don't fight with the browser
        #
        elif e.key.lower() == "f":
            self._handle_button_press("search")
        elif e.key.lower() == "backspace":
            self._handle_button_press("select_none")
        #
        elif e.key.lower() == "arrowup" or e.key.lower() == "pageup":
            self._handle_button_press("nav_backward")
        elif e.key.lower() == "arrowdown" or e.key.lower() == "pagedown":
            self._handle_button_press("nav_forward")
        elif e.key.lower() == "arrowleft":
            self._handle_button_press("nav_zoom_" + self._current_scale["out"])
        elif e.key.lower() == "arrowright":
            self._handle_button_press("nav_zoom_" + self._current_scale["in"])
        elif e.key.lower() == "n" or e.key.lower() == "home" or e.key.lower() == "end":
            self._handle_button_press("nav_snap_now" + self._current_scale["now"])
        #
        elif e.key.lower() == "d":
            self._handle_button_press("nav_snap_today")
        elif e.key.lower() == "w":
            self._handle_button_press("nav_snap_now1W")
        elif e.key.lower() == "m":
            self._handle_button_press("nav_snap_now1M")
        elif e.key.lower() == "q":
            self._handle_button_press("nav_snap_now3M")
        elif e.key.lower() == "y":
            self._handle_button_press("nav_snap_now1Y")
        elif e.key.lower() == "t":
            self._handle_button_press("nav_menu")
        #
        elif e.key.lower() == "s":
            if e.shiftKey:
                self._handle_button_press("record_resume")
            else:
                self._handle_button_press("record_start")
        elif e.key.lower() == "x":
            self._handle_button_press("record_stopall")
        elif e.key.lower() == "r":
            self._handle_button_press("report")
        elif e.key.lower() == "i":
            self._handle_button_press("guide")
        else:
            return
        e.preventDefault()

    def _handle_button_press(self, action):
        now = self._canvas.now()

        if action == "menu":
            self._canvas.menu_dialog.open()

        elif action == "search":
            self._canvas.search_dialog.open()

        elif action == "login":
            window.location.href = "../login"

        elif action == "dosync":
            if window.store.state in ("warning", "error"):
                last_error = window.store.last_error or "Unknown sync error"
                self._canvas.notification_dialog.open(last_error, "Sync error")
            else:
                msg = "This button shows the sync status. The current status is <b>OK</b>!"
                msg += "<br><br>The app and server continiously exchange updates. "
                msg += "When something is wrong, this button will change, "
                msg += "and you can then click it to get more info."
                self._canvas.notification_dialog.open(msg, "Sync status")
                # Also sync now
                window.store.sync_soon(0.2)

        elif action == "report":
            self._canvas.report_dialog.open()

        elif action == "guide":
            self._canvas.guide_dialog.open()

        elif action == "pomo":
            self._canvas.pomodoro_dialog.open()

        elif action.startswith("record_"):
            # A time tracking action
            if action == "record_start":
                record = window.store.records.create(now, now)
                self._canvas.record_dialog.open("Start", record, self.update)
            elif action == "record_new":
                record = window.store.records.create(now - 1800, now)
                self._canvas.record_dialog.open("New", record, self.update)
            elif action == "record_resume":
                record = window.store.records.create(now, now)
                records = window.store.records.get_running_records()
                if not records:
                    records = window.store.records.get_records(
                        now - 7 * 86400, now
                    ).values()
                    records.sort(key=lambda r: r.t2)
                if records:
                    prev_record = records[-1]
                    record.ds = prev_record.ds
                self._canvas.record_dialog.open("Start", record, self.update)
            elif action == "record_stop":
                records = window.store.records.get_running_records()
                if len(records) > 0:
                    record = records[0]
                    record.t2 = max(record.t1 + 2, now)
                    self._canvas.record_dialog.open("Stop", record, self.update)
            elif action == "record_stopall":
                records = window.store.records.get_running_records()
                for record in records:
                    record.t2 = max(record.t1 + 2, now)
                    window.store.records.put(record)
                if window.simplesettings.get("pomodoro_enabled"):
                    self._canvas.pomodoro_dialog.stop()

        elif action.startswith("nav_"):
            # A navigation action
            if action.startswith("nav_snap_"):
                res = action.split("_")[-1]
                t1, t2 = self._canvas.range.get_target_range()
                if res == "today":
                    t1, t2 = self._canvas.range.get_today_range()
                elif res.startswith("now"):
                    res = res[3:]
                    if len(res) == 0:
                        nsecs = t2 - t1
                        t1 = now - nsecs / 2
                        t2 = now + nsecs / 2
                    else:
                        t1 = dt.floor(now, res)
                        t2 = dt.add(t1, res)
                else:
                    t_ref = now if (t1 <= now <= t2) else (t2 + t1) / 2
                    t1 = dt.floor(t_ref, res)
                    t2 = dt.add(t1, res)
                self._canvas.range.animate_range(t1, t2)
            elif action.startswith("nav_zoom_"):
                t1, t2 = self._canvas.range.get_target_range()
                res = action.split("_")[-1]
                now_is_in_range = t1 <= now <= t2
                if res == "-1" or res == "+1":
                    if res == "-1":
                        t1, t2 = self._canvas.range.get_snap_range(-1)
                    else:
                        t1, t2 = self._canvas.range.get_snap_range(+1)
                    if now_is_in_range:
                        t1, t2 = now - 0.5 * (t2 - t1), now + 0.5 * (t2 - t1)
                else:
                    t_ref = now if (t1 <= now <= t2) else (t2 + t1) / 2
                    t1 = dt.floor(t_ref, res)
                    t2 = dt.add(t1, res)
                self._canvas.range.animate_range(t1, t2)
            elif action == "nav_backward" or action == "nav_forward":
                t1, t2 = self._canvas.range.get_target_range()
                nsecs = t2 - t1
                if nsecs < 80000:
                    if action == "nav_backward":
                        self._canvas.range.animate_range(t1 - nsecs, t1, None, False)
                    else:
                        self._canvas.range.animate_range(t2, t2 + nsecs, None, False)
                else:
                    res = self._current_scale["now"]
                    if action == "nav_backward":
                        res = "-" + res
                    t1 = dt.add(t1, res)
                    t2 = dt.add(t2, res)
                    self._canvas.range.animate_range(t1, t2, None, False)
            elif action == "nav_menu":
                self._canvas.timeselection_dialog.open()

        elif action.startswith("select_"):
            # A selection action
            if action == "select_none":
                self._canvas.widgets.AnalyticsWidget.unselect_all_tags()


class RecordsWidget(Widget):
    """Widget that draws the records, ticks, handles record
    manipulation, and timeline navigation.
    """

    def on_init(self):
        self._picker = utils.Picker()

        # Stuff related to records
        self._selected_record = None
        self._can_interact_with_records = False
        self._record_times = {}  # For snapping

        # Stuff related to interaction
        self._interaction_mode = 0
        self._dragging_new_record = None  # None or [t1, t2]
        self._last_pointer_down_event = None

        self._arrow_state = 0, 0  # last_timestamp, last_alpha
        self._last_scale_scroll = 0
        self._last_trans_scroll = 0
        self._pointer_pos = {}
        self._pointer_startpos = {}
        self._pointer_startrange = 0, 0
        self._pointer_inertia = []  # track last n move events

    def on_draw(self, ctx):
        x1, y1, x2, y2 = self.rect
        self._picker.clear()

        # Guard for small screen space during resize
        if y2 - y1 < 20:
            return

        # If too little space, only draw button to expand
        if x2 - x1 <= 50:
            width = 30
            x3, x4 = 0, width
            height = max(200, 0.33 * (y2 - y1))
            y3, y4 = (y1 + y2) / 2 - height / 2, (y1 + y2) / 2 + height / 2
            self._picker.register(
                x3, y3, x4, y4, {"button": True, "action": "showrecords"}
            )
            hover = self._canvas.register_tooltip(x3, y3, x4, y4, "")
            ctx.beginPath()
            ctx.moveTo(x3, y3)
            ctx.lineTo(x4, y3 + width)
            ctx.lineTo(x4, y4 - width)
            ctx.lineTo(x3, y4)
            ctx.fillStyle = COLORS.tick_stripe2
            ctx.fill()
            ctx.textAlign = "center"
            ctx.textBaseline = "middle"
            ctx.fillStyle = COLORS.tick_text if hover else COLORS.prim1_clr
            ctx.font = FONT.size + "px " + FONT.default
            for i, c in enumerate("Records"):
                ctx.fillText(c, (x3 + x4) / 2, (y3 + y4) / 2 + (i - 3) * 18)
            return

        x3 = self._canvas.grid_round(x1 + 64)
        x4 = self._canvas.grid_round(x3 + 50)

        # Draw background of "active region"
        if self._dragging_new_record:
            ctx.fillStyle = COLORS.acc_clr
        else:
            ctx.fillStyle = COLORS.panel_bg
        ctx.fillRect(x3, y1, x4 - x3, y2 - y1)
        self._timeline_bounds = x3, x4, y1, y2

        # Draw animated arrow indicator
        self._draw_arrow(ctx, x1, y1, x2, y2, x3, x4)

        self._help_text = ""

        self._draw_ticks(ctx, x3, y1, x4, y2)
        self._draw_edge(ctx, x3, y1, x4, y2)
        self._draw_record_area(ctx, x3, x4, x2, y1, y2)
        ctx.clearRect(0, 0, x2, y1 - 33)
        self._draw_top_and_bottom_cover(ctx, x1, x3, x4, x2, y1 - 50, y1, 0.333)
        self._draw_top_and_bottom_cover(ctx, x1, x3, x4, x2, y2, self._canvas.h, -0.02)

        # Draw drag-text
        if self._dragging_new_record:
            ctx.textAlign = "left"
            ctx.textBaseline = "bottom"
            ctx.font = 1.2 * FONT.size + "px " + FONT.default
            ctx.fillStyle = COLORS.prim2_clr
            ctx.fillText("⬋ drag to create new record", x4, y1 - 2)

        # Draw title text
        if self._canvas.w > 800:
            text1 = "Timeline"
            ctx.textAlign = "left"
            ctx.textBaseline = "top"
            ctx.font = "bold " + (FONT.size * 1.4) + "px " + FONT.mono
            ctx.fillStyle = COLORS.prim2_clr
            ctx.fillText(text1, x1 + 10, 75)
            # ctx.font = (FONT.size * 0.9) + "px " + FONT.default
            # ctx.fillStyle = COLORS.prim2_clr
            # ctx.fillText(self._help_text, 10, 90)

    def _draw_arrow(self, ctx, x1, y1, x2, y2, x3, x4):
        """Draw arrow to indicate that the timeline can be dragged.
        To avoid sudden appearance we animate fade-in and out.
        """

        min_alpha = 0.0
        max_alpha = 0.1
        animation_speed_in_seconds = 0.5

        # Register empty tooltip so we can detect mouse over
        hover = self._canvas.register_tooltip(x3, y1, x4, y2, "")
        show_arrow = hover or self._interaction_mode

        # Determine arrow alpha
        now = self._canvas.now()
        delta_t = (now - self._arrow_state[0]) if self._arrow_state[0] else 0.001
        delta_a = delta_t * (max_alpha - min_alpha) / animation_speed_in_seconds
        if show_arrow:
            new_alpha = min(max_alpha, self._arrow_state[1] + delta_a)
        else:
            new_alpha = max(min_alpha, self._arrow_state[1] - delta_a)
        if new_alpha != self._arrow_state[1]:
            self.update()
            self._arrow_state = now, new_alpha
        else:
            self._arrow_state = 0, new_alpha  # mark zero time

        # Draw arrow
        if new_alpha and (x2 - x4) > 20:
            ctx.font = ((x2 - x4) * 0.9) + "px FontAwesome"
            ctx.textAlign = "center"
            ctx.textBaseline = "middle"
            ctx.fillStyle = "rgba(128,128,128," + new_alpha + ")"
            ctx.fillText("\uf338", (x2 + x4) / 2, (y1 + y2) / 2)

    def _draw_edge(self, ctx, x1, y1, x2, y2):
        def drawstrokerect(lw):
            rn = RECORD_AREA_ROUNDNESS + lw
            ctx.beginPath()
            ctx.arc(x2 - rn + lw, y1 + rn - lw, rn, 1.5 * PI, 2.0 * PI)
            ctx.arc(x2 - rn + lw, y2 - rn + lw, rn, 0.0 * PI, 0.5 * PI)
            ctx.arc(x1 + rn - lw, y2 - rn + lw, rn, 0.5 * PI, 1.0 * PI)
            ctx.arc(x1 + rn - lw, y1 + rn - lw, rn, 1.0 * PI, 1.5 * PI)
            ctx.closePath()
            ctx.stroke()

        lw = 3
        ctx.lineWidth = lw
        ctx.strokeStyle = COLORS.background1
        drawstrokerect(1.0 * lw)
        ctx.strokeStyle = COLORS.panel_edge
        drawstrokerect(0.0 * lw)

    def _draw_top_and_bottom_cover(self, ctx, x1, x2, x3, x4, y1, y2, stop):
        grd1 = ctx.createLinearGradient(x1, y1, x1, y2)
        grd2 = ctx.createLinearGradient(x1, y1, x1, y2)
        # grd3 = ctx.createLinearGradient(x1, y1, x1, y2)
        color1 = COLORS.background1
        color2 = color1.replace("1)", "0.0)")
        color4 = color1.replace("1)", "0.7)")
        if stop > 0:
            grd1.addColorStop(0.0, color2)
            grd1.addColorStop(stop, color1)
            grd1.addColorStop(1.0, color2)
            grd2.addColorStop(0.0, color2)
            grd2.addColorStop(stop, color1)
            grd2.addColorStop(1.0, color4)
        else:
            grd1.addColorStop(0.0, color2)
            grd1.addColorStop(1 + stop, color1)
            grd1.addColorStop(1.0, color1)
            grd2.addColorStop(0.0, color4)
            grd2.addColorStop(1 + stop, color1)
            grd2.addColorStop(1.0, color1)
        ctx.fillStyle = grd1
        ctx.fillRect(0, y1, x4, y2 - y1)
        ctx.fillStyle = grd2
        ctx.fillRect(x2, y1, x4 - x2, y2 - y1 - 2)

    def _draw_ticks(self, ctx, x1, y1, x2, y2):
        PSCRIPT_OVERLOAD = False  # noqa
        t1, t2 = self._canvas.range.get_range()

        # Determine deltas
        npixels = y2 - y1  # number if logical pixels we can use
        nsecs = t2 - t1  # Number of seconds in our range

        # Define ticks
        ticks, minor_ticks, granularity = self._canvas.range.get_ticks(npixels)

        # Prepare for drawing ticks
        ctx.fillStyle = COLORS.tick_text
        ctx.font = (SMALLER * FONT.size) + "px " + FONT.default
        ctx.textBaseline = "middle"
        ctx.textAlign = "right"

        # Get time representation
        time_repr = window.simplesettings.get("time_repr")
        if time_repr == "auto":
            time_repr = "24h"
            x = window.Date().toLocaleTimeString().toLowerCase()
            if "am" in x or "pm" in x:
                time_repr = "ampm"

        # Draw tick texts
        for pos, t in ticks:
            text = dt.time2localstr(t)
            year, month, monthday = dt.get_year_month_day(t)
            if granularity == "mm":
                text = text[11:16]
                h = int(text[:2])
                if text == "00:00":
                    text = dt.get_weekday_shortname(t) + " " + monthday
                    if monthday == 1:
                        text += " " + dt.get_month_shortname(t)
                    text += "  12h" if time_repr == "ampm" else "  0h"
                elif time_repr == "ampm":  # am/pm is so weird!
                    if h == 0:
                        text = "12" + text[2:] + " am"
                    elif h < 12:
                        text = h + text[2:] + " am"
                    elif h == 12:
                        text = "12" + text[2:] + " pm"
                    else:  # if h >= 13:
                        text = (h - 12) + text[2:] + " pm"
            elif granularity == "hh":
                text = text[11:13].lstrip("0") + "h"
                if text == "h":
                    text = dt.get_weekday_shortname(t) + " " + monthday
                    if monthday == 1:
                        text += " " + dt.get_month_shortname(t)
                    text += "  0h"
            elif granularity == "DD":
                text = dt.get_weekday_shortname(t) + " " + monthday
                if monthday == 1:
                    text += " " + dt.get_month_shortname(t)
            elif granularity == "DM":
                text = monthday + " " + dt.get_month_shortname(t)
                if monthday == 1 and month == 1:
                    text += " " + year
            elif granularity == "MM":
                text = dt.get_month_shortname(t)
                if month == 1:  # i.e. Januari
                    text += " " + year
            elif granularity == "YY":
                text = str(year)
            ctx.fillText(text, x1 - 4, pos + y1, x1 - 3)

        # Draw tick stripes
        ctx.strokeStyle = COLORS.tick_stripe2
        ctx.lineWidth = 1
        ctx.beginPath()
        for pos, text in ticks:
            ctx.moveTo(x1, pos + y1, True)
            ctx.lineTo(x2, pos + y1, True)
        ctx.stroke()

        # Draw minor tick stripes
        ctx.strokeStyle = COLORS.tick_stripe3
        ctx.lineWidth = 1
        ctx.beginPath()
        for pos, text in minor_ticks:
            ctx.moveTo(x1, pos + y1, True)
            ctx.lineTo(x2, pos + y1, True)
        ctx.stroke()

        # Draw snap feedback
        t1_snap, t2_snap = self._canvas.range.get_snap_range()
        y1_snap = y1 + (t1_snap - t1) * npixels / nsecs  # can be negative!
        y2_snap = y1 + (t2_snap - t1) * npixels / nsecs
        ctx.fillStyle = "rgba(127,127,127,0.2)"
        if y1_snap > y1:
            ctx.fillRect(x1, y1, x2 - x1, y1_snap - y1)
        if y2_snap < y2:
            ctx.fillRect(x1, y2_snap, x2 - x1, y2 - y2_snap)

    def _draw_record_area(self, ctx, x1, x2, x3, y1, y2):
        t1, t2 = self._canvas.range.get_range()

        # Determine whether to draw records or stats, and how many
        npixels = y2 - y1
        nsecs = t2 - t1
        pps = npixels / nsecs
        stat_period, stat_name = self._canvas.range.get_stat_period()

        # Draw records or stats
        if stat_period is None:
            self._can_interact_with_records = True
            # Draw day boundaries
            t3 = dt.floor(t1, "1D")
            t4 = dt.add(dt.floor(t2, "1D"), "1D")
            ctx.lineWidth = 2.5
            ctx.strokeStyle = COLORS.tick_stripe2
            ctx.beginPath()
            while t3 <= t4:
                y = y1 + (t3 - t1) * pps
                ctx.moveTo(x1, y)
                ctx.lineTo(x2, y)
                t3 = dt.add(t3, "1D")
            ctx.stroke()
            # Draw records themselves
            self._draw_records(ctx, x1, x2, x3, y1, y2)
        else:
            # self._help_text = "click on a " + stat_name + " to zoom"
            self._can_interact_with_records = False
            t3 = dt.floor(t1, stat_period)
            while t3 < t2:
                t4 = dt.add(t3, stat_period)
                y3 = y1 + (t3 - t1) * pps
                y4 = y1 + (t4 - t1) * pps
                self._picker.register(
                    x1, y3, x3, y4, {"statrect": True, "t1": t3, "t2": t4}
                )
                hover = self._canvas.register_tooltip(x1, y3, x3, y4, "")
                # self._draw_stats(ctx, t3, t4, x1+10, y3, x3-10, y4, stat_period, hover)
                self._draw_stats(ctx, t3, t4, x2, y3, x3, y4, stat_period, hover)
                ctx.lineWidth = 1.2
                ctx.strokeStyle = COLORS.tick_stripe1
                ctx.beginPath()
                ctx.moveTo(x1, y3)
                ctx.lineTo(x3, y3)
                ctx.stroke()
                t3 = t4
            # Put border around
            rn = RECORD_AREA_ROUNDNESS
            ctx.beginPath()
            ctx.arc(x3 - rn, y1 + rn, rn, 1.5 * PI, 2.0 * PI)
            ctx.arc(x3 - rn, y2 - rn, rn, 0.0 * PI, 0.5 * PI)
            ctx.arc(x2 + rn, y2 - rn, rn, 0.5 * PI, 1.0 * PI)
            ctx.arc(x2 + rn, y1 + rn, rn, 1.0 * PI, 1.5 * PI)
            ctx.closePath()
            ctx.lineWidth = 3
            ctx.strokeStyle = COLORS.prim1_clr
            ctx.stroke()

        # Draw drag-new-record feedback
        if self._dragging_new_record:
            if self._dragging_new_record[0] > 0:
                dt1, dt2 = self._dragging_new_record
                dt1, dt2 = min(dt1, dt2), max(dt1, dt2)
                dy1 = y1 + (dt1 - t1) * pps
                dy2 = y1 + (dt2 - t1) * pps
                ctx.fillStyle = "rgba(127, 127, 127, 0.5)"
                rn = RECORD_ROUNDNESS
                ctx.beginPath()
                ctx.arc(x2 - rn, dy1 + rn, rn, 1.5 * PI, 2.0 * PI)
                ctx.arc(x2 - rn, dy2 - rn, rn, 0.0 * PI, 0.5 * PI)
                ctx.arc(x1 + rn, dy2 - rn, rn, 0.5 * PI, 1.0 * PI)
                ctx.arc(x1 + rn, dy1 + rn, rn, 1.0 * PI, 1.5 * PI)
                ctx.closePath()
                ctx.fill()

        # Draw "now" - also if drawing stats
        t = self._canvas.now()
        y = y1 + (t - t1) * pps
        ctx.strokeStyle = COLORS.record_text
        ctx.lineWidth = 3  # Pretty thick so it sticks over other edges like week bounds
        ctx.setLineDash([4, 4])
        ctx.lineDashOffset = t % 8
        ctx.beginPath()
        ctx.moveTo(x1, y)
        ctx.lineTo(x2, y)
        ctx.stroke()
        ctx.setLineDash([])
        ctx.lineDashOffset = 0

    def _draw_records(self, ctx, x1, x2, x3, y1, y2):
        PSCRIPT_OVERLOAD = False  # noqa

        y0, y3 = y1 - 50, self._canvas.h
        t1, t2 = self._canvas.range.get_range()
        # now = self._canvas.now()

        # Get range, in seconds and pixels for the time range
        npixels = y2 - y1  # number if logical pixels we can use
        nsecs = t2 - t1

        # Get whether we're "snapped". If so we'll align our horizontal lines
        t1_snap, t2_snap = self._canvas.range.get_snap_range()
        self._round_top_bottom = t1 == t1_snap and t2 == t2_snap

        # We will actually draw a larger range, because we show some of the future and past
        t1 -= (y1 - y0) * nsecs / npixels
        t2 += (y3 - y2) * nsecs / npixels
        nsecs = t2 - t1
        npixels = y3 - y0

        # Select all records in this range. Sort so that smaller records are drawn on top.
        records = window.store.records.get_records(t1, t2).values()

        # if len(records) > 0:
        #     self._help_text = "click a record to edit it"

        # Sort records by size, so records cannot be completely overlapped by another
        # Or ... by t2, which works better when the labels are made to overlap in a cluster,
        # see the distance = ref_distance - ... below
        # records.sort(key=lambda r: r.t1 - (now if (r.t1 == r.t2) else r.t2))
        records.sort(key=lambda r: -r.t2)

        # Prepare by collecting stuff per record, and determine selected record
        self._record_times = {}
        positions_map = {}
        selected_record = None
        for record in records:
            self._record_times[record.key] = record.t1, record.t2
            if self._selected_record is not None:
                if record.key == self._selected_record[0].key:
                    selected_record = record
            pos = self._determine_record_preferred_pos(
                record, t1, y0, y1, y2, npixels, nsecs
            )
            positions_map[record.key] = pos

        # Organise position objects in a list, and initialize each as a cluster
        positions = positions_map.values()
        positions.sort(key=lambda r: r.pref)
        clusters = []
        for pos in positions:
            if pos.visible:
                clusters.push([pos])

        # Iteratively merge clusters
        ref_distance = 40 + 8
        for iter in range(5):  # while-loop with max 5 iters, just in case
            # Try merging clusters if they're close. Do this from back to front,
            # so we can merge multiple together in one pass
            merged_a_cluster = False
            for i in range(len(clusters) - 2, -1, -1):
                pos1 = clusters[i][-1]
                pos2 = clusters[i + 1][0]
                if pos2.y - pos1.y < ref_distance:
                    merged_a_cluster = True
                    cluster = []
                    cluster.extend(clusters.pop(i))
                    cluster.extend(clusters.pop(i))
                    clusters.insert(i, cluster)
            # If no clusters merged, we're done
            if merged_a_cluster is False:
                break
            # Reposition the elements in each cluster. The strategy for setting
            # positions depends on whether the cluster is near the top/bottom.
            for cluster in clusters:
                distance = ref_distance - min(20, 0.7 * len(cluster))
                if cluster[0].visible == "top":
                    ref_y = cluster[0].y
                    for i, pos in enumerate(cluster):
                        pos.y = ref_y + i * distance
                elif cluster[-1].visible == "bottom":
                    ref_y = cluster[-1].y - (len(cluster) - 1) * distance
                    for i, pos in enumerate(cluster):
                        pos.y = ref_y + i * distance
                else:
                    # Get reference y
                    ref_y = 0.5 * (cluster[0].pref + cluster[-1].pref)
                    # We might still push records over the edge, prevent this
                    first_y = ref_y + (0 + 0.5 - len(cluster) / 2) * distance
                    last_y = ref_y + (len(cluster) - 0.5 - len(cluster) / 2) * distance
                    if first_y < y1 + 20:
                        ref_y += (y1 + 20) - first_y
                    elif last_y > y2 - 20:
                        ref_y -= last_y - (y2 - 20)
                    # Set positions
                    for i, pos in enumerate(cluster):
                        pos.y = ref_y + (i + 0.5 - len(cluster) / 2) * distance

        # Draw records
        for record in records:
            pos = positions_map[record.key]
            self._draw_one_record(
                ctx, record, t1, x1, x2, x3, y0, y1, y2, npixels, nsecs, pos.y
            )

        # Draw the selected record, again, and with extra stuff to allow
        # manipulating it. This is mostly for the timeline
        # representation. Though we also re-draw the representation
        # next to the timeline to make its shadow thicker :)
        if selected_record is not None:
            record = selected_record
            pos = positions_map[record.key]
            self._draw_one_record(
                ctx, record, t1, x1, x2, x3, y0, y1, y2, npixels, nsecs, pos.y
            )
            self._draw_selected_record_extras(
                ctx, record, t1, x1, x2, x3, y0, y1, y2, npixels, nsecs
            )

    def _determine_record_preferred_pos(self, record, t1, y0, y1, y2, npixels, nsecs):
        PSCRIPT_OVERLOAD = False  # noqa
        now = self._canvas.now()
        t2_or_now = now if (record.t1 == record.t2) else record.t2

        # Get position of record in timeline
        ry1 = y0 + npixels * (record.t1 - t1) / nsecs
        ry2 = y0 + npixels * (t2_or_now - t1) / nsecs

        # Get margin for making space for record before its visible
        npixels_record = max(0, ry2 - ry1)
        visible_margin = min(npixels_record, 40)

        # Determine preferred position
        pref = y = (ry1 + ry2) / 2
        visible = "main"
        if y < y1 + 20:
            y = y1 + 20
            visible = "top"
            if ry2 < y1:
                # Start claiming space before it is visible
                y -= 2 * (y1 - ry2)
                if ry2 < y1 - visible_margin:
                    visible = ""
        elif y > y2 - 20:
            y = y2 - 20
            visible = "bottom"
            if ry1 > y2:
                # Start claiming space before it is visible
                y += 2 * (ry1 - y2)
                if ry1 > y2 + visible_margin:
                    visible = ""

        return {"pref": pref, "y": y, "visible": visible}

    def _draw_one_record(
        self, ctx, record, t1, x1, x4, x6, y0, y1, y2, npixels, nsecs, yy
    ):
        PSCRIPT_OVERLOAD = False  # noqa
        grid_round = self._canvas.grid_round
        now = self._canvas.now()
        t2_or_now = now if (record.t1 == record.t2) else record.t2

        # Define all x's
        #
        #
        #     x1 x2  x3 x4   x5                   x6
        #                     ____________________     ty1
        # ry1  |  ____  |    /                    \
        #      | /    \ |    \____________________/
        #      | |    | |                              ty2
        #      | |    | |
        #      | \____/ |
        # ry2  |        |

        x2 = x1 + 8
        x3 = x4
        x5 = x4 + 25

        # Set record description y positions
        ty1 = yy - 20
        ty2 = yy + 20

        # Get tag info, and determine if this record is selected in the overview
        tags, ds_parts = utils.get_tags_and_parts_from_string(record.ds)
        if len(tags) == 0:
            tags = ["#untagged"]
        tags_selected = True
        selected_tags = self._canvas.widgets.AnalyticsWidget.selected_tags
        if len(selected_tags):
            if not all([tag in tags for tag in selected_tags]):
                tags_selected = False
        if self._dragging_new_record:
            tags_selected = False

        # # Determine wheter this record is selected in the timeline
        # selected_in_timeline = False
        # if self._selected_record is not None:
        #     if record.key == self._selected_record[0].key:
        #         selected_in_timeline = True

        # Get position in pixels
        ry1 = y0 + npixels * (record.t1 - t1) / nsecs
        ry2 = y0 + npixels * (t2_or_now - t1) / nsecs
        if ry1 > ry2:
            ry1, ry2 = ry2, ry1  # started timer, then changed time offset
        # Round to pixels? Not during interaction to avoid jumps!
        if self._round_top_bottom:
            ry1 = grid_round(ry1)
            ry2 = grid_round(ry2)

        # Define inset and outset bump (for running records)
        inset, outset = 0, 0
        is_running = False
        if record.t1 == record.t2:
            inset, outset = 0, 16
            is_running = True

        # Define roundness and how much each slab moves outward
        rn = RECORD_ROUNDNESS
        rnb = COLORBAND_ROUNDNESS
        rne = min(min(0.5 * (ry2 - ry1), rn), rnb)  # for in timeline

        timeline_only = ry2 < y1 or ry1 > y2

        # Make the timeline-part clickable - the pick region is increased if needed
        ry1_, ry2_ = ry1, ry2
        if ry2 - ry1 < 16:
            ry1_, ry2_ = 0.5 * (ry1 + ry2) - 8, 0.5 * (ry1 + ry2) + 8
        self._picker.register(
            x2, ry1_, x3, ry2_, {"recordrect": True, "region": 0, "record": record}
        )
        tt_text = tags.join(" ") + "\n(click to make draggable)"
        hover_timeline = self._canvas.register_tooltip(
            x2, ry1, x3, ry2 + outset, tt_text, "mouse"
        )

        # Make description part clickable - the pick region is increased if needed
        if not timeline_only:
            d = {
                "button": True,
                "action": "editrecord",
                "help": "",
                "key": record.key,
            }
            self._picker.register(x5, ty1, x6, ty2, d)
            tt_text = tags.join(" ") + "\n(Click to edit)"
            hover_description = self._canvas.register_tooltip(x5, ty1, x6, ty2, tt_text)

        # Cast a shadow if hovering
        if hover_timeline and self._selected_record is None:
            ctx.beginPath()
            ctx.arc(x2 + rne, ry2 - rne, rne, 0.5 * PI, 1.0 * PI)
            ctx.arc(x2 + rne, ry1 + rne, rne, 1.0 * PI, 1.5 * PI)
            ctx.lineTo(x3, 0.5 * (ry1 + ry2))
            ctx.closePath()
            ctx.shadowBlur = 6
            ctx.shadowColor = "rgba(0, 0, 0, 0.8)"  # COLORS.button_shadow
            ctx.fill()
            ctx.shadowBlur = 0
        elif hover_description:
            ctx.beginPath()
            ctx.arc(x5 + rn, ty2 - rn, rn, 0.5 * PI, 1.0 * PI)
            ctx.arc(x5 + rn, ty1 + rn, rn, 1.0 * PI, 1.5 * PI)
            ctx.arc(x6 - rn, ty1 + rn, rn, 1.5 * PI, 2.0 * PI)
            ctx.arc(x6 - rn, ty2 - rn, rn, 2.0 * PI, 2.5 * PI)
            ctx.closePath()
            ctx.shadowBlur = 5
            ctx.shadowColor = COLORS.button_shadow
            ctx.fill()
            ctx.shadowBlur = 0

        # Draw record representation
        path = utils.RoundedPath()
        if timeline_only:
            path.addVertex(x2, ry2, rne)
            path.addVertex(x2, ry1, rne)
            path.addVertex(x3, ry1, rne)
            path.addVertex(x3, ry2, rne)
        else:
            path.addVertex(x2, ry2, rne)
            path.addVertex(x2, ry1, rne)
            path.addVertex(x4, ry1, 4)
            path.addVertex(x5, ty1, 4)
            path.addVertex(x6, ty1, rn)
            path.addVertex(x6, ty2, rn)
            path.addVertex(x5, ty2, 4)
            path.addVertex(x4, ry2, 4)
        path = path.toPath2D()
        ctx.fillStyle = COLORS.record_bg_running if is_running else COLORS.record_bg
        ctx.fill(path)

        ctx.strokeStyle = COLORS.record_edge
        ctx.lineWidth = 1.2

        # Draw coloured edge
        tagz = tags.join(" ")
        tagz = self._canvas.widgets.AnalyticsWidget.tagzmap.get(tagz, tagz)
        colors = [
            window.store.settings.get_color_for_tag(tag) for tag in tagz.split(" ")
        ]
        # Width and xpos
        ew = 8 / len(colors) ** 0.5
        ew = max(ew, rnb)
        ex = x2
        # First band
        ctx.fillStyle = colors[0]
        ctx.beginPath()
        ctx.arc(x2 + rne, ry2 - rne, rne, 0.5 * PI, 1.0 * PI)
        ctx.arc(x2 + rne, ry1 + rne, rne, 1.0 * PI, 1.5 * PI)
        ctx.lineTo(x2 + ew, ry1)
        ctx.lineTo(x2 + ew, ry2)
        ctx.closePath()
        ctx.fill()
        # Remaining bands
        for color in colors[1:]:
            ex += ew  # + 0.15  # small offset creates subtle band
            ctx.fillStyle = color
            ctx.fillRect(ex, ry1, ew, ry2 - ry1)

        # Set back bg color, and draw the record edge
        ctx.fillStyle = COLORS.record_bg_running if is_running else COLORS.record_bg
        ctx.stroke(path)

        # Running records have a small outset
        if is_running:
            x1f, x2f = x2 + (x3 - x2) / 3, x3 - (x3 - x2) / 3
            ctx.beginPath()
            ctx.moveTo(x2f, ry2 - inset)
            ctx.arc(x2f - rn, ry2 + outset - rn, rn, 0.0 * PI, 0.5 * PI)
            ctx.arc(x1f + rn, ry2 + outset - rn, rn, 0.5 * PI, 1.0 * PI)
            ctx.lineTo(x1f, ry2 - inset)
            ctx.fill()
            ctx.stroke()
            if int(now) % 2 == 1:
                ctx.fillStyle = COLORS.prim1_clr
                ctx.beginPath()
                ctx.arc(0.5 * (x2 + x3), ry2 + outset / 2, 4, 0, 2 * PI)
                ctx.fill()
            self._picker.register(
                x1f,
                ry2,
                x2f,
                ry2 + outset,
                {"recordrect": True, "region": 0, "record": record},
            )

        # The marker that indicates whether the record has been modified
        if record.st == 0:
            ctx.textAlign = "center"
            ctx.fillStyle = COLORS.record_edge
            ctx.fillText("+", 0.5 * (x2 + x3), 0.5 * (ry1 + ry2))

        # The rest is for the description part
        if timeline_only:
            return

        text_ypos = ty1 + 0.55 * (ty2 - ty1)

        ctx.font = (SMALLER * FONT.size) + "px " + FONT.default
        ctx.textBaseline = "middle"
        faded_clr = COLORS.prim2_clr

        # Draw duration text
        duration = record.t2 - record.t1
        if duration > 0:
            duration_text = dt.duration_string(duration, False)
            duration_sec = ""
        else:
            duration = now - record.t1
            duration_text, duration_sec = dt.duration_string(duration, 2)
        ctx.fillStyle = COLORS.record_text if tags_selected else faded_clr
        ctx.textAlign = "right"
        ctx.fillText(duration_text, x5 + 30, text_ypos)
        if duration_sec:
            ctx.fillStyle = faded_clr
            ctx.textAlign = "left"
            ctx.fillText(duration_sec, x5 + 30 + 1, text_ypos)

        # Show desciption
        ctx.font = (SMALLER * FONT.size) + "px " + FONT.default
        ctx.textAlign = "left"
        max_x = x6 - 4
        space_width = ctx.measureText(" ").width + 2
        x = x5 + 55
        ctx.fillStyle = COLORS.record_text if tags_selected else faded_clr
        for part in ds_parts:
            if part.startswith("#"):
                texts = [part]
            else:
                texts = part.split(" ")
            for text in texts:
                if len(text) == 0:
                    continue
                if x > max_x:
                    continue
                new_x = x + ctx.measureText(text).width + space_width
                if new_x <= max_x:
                    if tags_selected and text.startswith("#"):
                        draw_tag(ctx, text, x, text_ypos)
                    else:
                        ctx.fillText(text, x, text_ypos, max_x - x)
                else:
                    ctx.fillText("…", x, text_ypos, max_x - x)
                x = new_x

    def _draw_selected_record_extras(
        self, ctx, record, t1, x1, x4, x6, y0, y1, y2, npixels, nsecs, yy
    ):
        PSCRIPT_OVERLOAD = False  # noqa

        grid_round = self._canvas.grid_round
        is_running = record.t1 == record.t2

        # Add another x
        x2 = x1 + 8
        x3 = x4
        x5 = x4 + 25  # noqa

        # Get position in pixels
        ry1 = y0 + npixels * (record.t1 - t1) / nsecs
        ry2 = y0 + npixels * (record.t2 - t1) / nsecs
        if record.t1 == record.t2:
            ry2 = y0 + npixels * (self._canvas.now() - t1) / nsecs
        if ry1 > ry2:
            ry1, ry2 = ry2, ry1
        ry1 = grid_round(ry1)
        ry2 = grid_round(ry2)

        # Prepare for drawing
        ctx.lineWidth = 1
        ctx.textBaseline = "middle"
        ctx.textAlign = "center"
        ctx.font = (0.85 * FONT.size) + "px " + FONT.condensed

        # Prepare for drawing flaps
        inset = min(28, max(1, (ry2 - ry1) ** 0.5))
        outset = 30 - inset  # inset + outset = grab height
        rn = grid_round(RECORD_ROUNDNESS)

        shadow_inset = 8
        x1f, x2f = x2 + rn, x3 - rn

        # Disable tooltip at the flaps
        self._canvas.register_tooltip(x1f, ry1 - outset - 1, x2f, ry1 + inset + 1, None)
        self._canvas.register_tooltip(x1f, ry2 - inset - 1, x2f, ry2 + outset + 1, None)

        # The record itself can be used to drag whole thing - if not running
        if record.t1 < record.t2:
            ob = {"recordrect": True, "region": 3, "record": record}
            self._picker.register(x2, ry1, x3, ry2, ob)

        # Flap above to drag t1 - always present
        if True:
            # Picking
            ob = {"recordrect": True, "region": 1, "record": record}
            self._picker.register(x1f, ry1 - outset - 1, x2f, ry1 + inset + 1, ob)
            # Draw flap
            ctx.beginPath()
            ctx.moveTo(x1f, ry1 + inset)
            ctx.arc(x1f + rn, ry1 - outset + rn, rn, 1.0 * PI, 1.5 * PI)
            ctx.arc(x2f - rn, ry1 - outset + rn, rn, 1.5 * PI, 2.0 * PI)
            ctx.lineTo(x2f, ry1 + inset)
            ctx.fillStyle = COLORS.record_bg_running if is_running else COLORS.record_bg
            ctx.fill()
            ctx.strokeStyle = COLORS.record_edge
            ctx.stroke()
            # Shadow line
            ctx.beginPath()
            for y in [ry1 + inset]:
                ctx.moveTo(x1f + shadow_inset, y)
                ctx.lineTo(x2f - shadow_inset, y)
            ctx.strokeStyle = COLORS.record_edge
            ctx.stroke()
            # Text
            timetext = dt.time2localstr(record.t1)[11:16]
            ctx.fillStyle = COLORS.record_text
            ctx.fillText(timetext, 0.5 * (x1f + x2f), ry1 + (inset - outset) / 2)

        # Flap below to drag t2 - only present if not running
        if record.t1 < record.t2:
            # Picking
            ob = {"recordrect": True, "region": 2, "record": record}
            self._picker.register(x1f, ry2 - inset - 1, x2f, ry2 + outset + 1, ob)
            # Draw flap
            ctx.beginPath()
            ctx.moveTo(x2f, ry2 - inset)
            ctx.arc(x2f - rn, ry2 + outset - rn, rn, 0.0 * PI, 0.5 * PI)
            ctx.arc(x1f + rn, ry2 + outset - rn, rn, 0.5 * PI, 1.0 * PI)
            ctx.lineTo(x1f, ry2 - inset)
            ctx.fillStyle = COLORS.record_bg
            ctx.fill()
            ctx.strokeStyle = COLORS.record_edge
            ctx.stroke()
            # Shadow line
            ctx.beginPath()
            for y in [ry2 - inset]:
                ctx.moveTo(x1f + shadow_inset, y)
                ctx.lineTo(x2f - shadow_inset, y)
            ctx.strokeStyle = COLORS.record_edge
            ctx.stroke()
            # Text
            timetext = dt.time2localstr(record.t2)[11:16]
            ctx.fillStyle = COLORS.record_text
            ctx.fillText(timetext, 0.5 * (x1f + x2f), ry2 + (outset - inset) / 2)

        # Draw durarion on top
        if False:  # (ry2 - ry1) / 3 > 12:
            duration = record.t2 - record.t1
            duration = duration if duration > 0 else (self._canvas.now() - record.t1)
            if x2 - x1 < 90:
                duration_text = dt.duration_string(duration, False)
                ctx.fillText(duration_text, 0.5 * (x1 + 18 + x2), 0.5 * (ry1 + ry2))
            else:
                duration_text = dt.duration_string(duration, True)
                ctx.fillText(duration_text, 0.5 * (x1 + x2), 0.5 * (ry1 + ry2))

    def _draw_stats(self, ctx, t1, t2, x1, y1, x2, y2, stat_period, hover):
        # Determine header for this block
        t = 0.5 * (t1 + t2)
        if stat_period == "1Y":
            text = str(dt.get_year_month_day(t)[0])
        elif stat_period == "3M":
            quarters = "Q1 Q1 Q1 Q2 Q2 Q2 Q3 Q3 Q3 Q4 Q4 Q4 Q4".split(" ")
            month_index = dt.get_year_month_day(t)[1] - 1
            text = quarters[month_index]  # defensive programming
        elif stat_period == "1M":
            text = dt.get_month_shortname(t)
        elif stat_period == "1W":
            i = dt.get_weeknumber(t)
            text = f"W{i:02.0f}"
        elif stat_period == "1D":
            text = dt.get_weekday_shortname(t)
        else:
            text = ""

        # Get stats for the given time range
        stats_dict = window.store.records.get_stats(t1, t2)
        selected_tags = self._canvas.widgets.AnalyticsWidget.selected_tags

        # Collect per-tag. Also filter selected.
        tag_stats = {}
        sumcount_full = 0
        sumcount_nominal = 0
        sumcount_selected = 0
        for tagz, count in stats_dict.items():
            # Get tags list, tags2 filters out the secondary tags
            tags1 = tagz.split(" ")
            tags2 = []
            for tag in tags1:
                info = window.store.settings.get_tag_info(tag)
                if info.get("priority", 1) <= 1:
                    tags2.push(tag)
            # Update sums
            sumcount_full += count * len(tags2)
            sumcount_nominal += count
            # Filter selected (mind to test against tags1 here)
            if len(selected_tags):
                if not all([tag in tags1 for tag in selected_tags]):
                    continue
            sumcount_selected += count
            for tag in tags2:
                tag_stats[tag] = tag_stats.get(tag, 0) + count

        # Turn stats into tuples and sort.
        stats_list = [(tag, count) for tag, count in tag_stats.items()]
        stats_list.sort(key=lambda x: -x[1])

        # Calculate dimensions
        fullwidth = x2 - x1  # * (sumcount_full / (t2 - t1)) # ** 0.5
        fullheight = (y2 - y1) * (sumcount_full / (t2 - t1))  # ** 0.5

        # Darken the colors for free days.
        if stat_period == "1D":
            workdays_setting = window.simplesettings.get("workdays")
            is_free_day = (text == "Sat" and workdays_setting == 2) or (
                text == "Sun" and workdays_setting >= 1
            )
            if is_free_day:
                ctx.fillStyle = COLORS.button_text_disabled
                ctx.fillRect(x1, y1, fullwidth, y2 - y1)

        # Show amount of time spend on each tag
        x = x1
        for i in range(len(stats_list)):
            tag, count = stats_list[i]
            width = fullwidth * count / sumcount_full
            ctx.fillStyle = window.store.settings.get_color_for_tag(tag)
            ctx.fillRect(x, y1, width, (y2 - y1))
            x += width  # Next

        # Desaturate the colors by overlaying a semitransparent rectangle.
        # Actually, we use two, as an indicator for the total spent time.
        ctx.fillStyle = COLORS.background1.replace("1)", "0.7)")
        ctx.fillRect(x1, y1, fullwidth, y2 - y1)
        ctx.fillStyle = COLORS.background1.replace("1)", "0.5)")
        ctx.fillRect(x1, y1 + fullheight, fullwidth, y2 - y1 - fullheight)

        bigfontsize = min(FONT.size * 2, (y2 - y1) / 3)
        bigfontsize = max(FONT.size, bigfontsize)
        ymargin = (y2 - y1) / 20

        # Draw big text in stronger color if it is the timerange containing today

        # Draw duration at the left
        if not stat_period == "1D" or sumcount_nominal > 0 or not is_free_day:
            ctx.fillStyle = COLORS.prim1_clr if hover else COLORS.prim2_clr
            fontsizeleft = bigfontsize * (0.7 if selected_tags else 0.9)
            ctx.font = f"{fontsizeleft}px {FONT.default}"
            ctx.textBaseline = "bottom"
            ctx.textAlign = "left"
            duration_text = dt.duration_string(sumcount_selected, False)
            if selected_tags:
                duration_text += " / " + dt.duration_string(sumcount_nominal, False)
            ctx.fillText(duration_text, x1 + 10, y2 - ymargin)

        # Draw time-range indication at the right
        isnow = t1 < self._canvas.now() < t2
        ctx.fillStyle = COLORS.prim1_clr if isnow else COLORS.prim2_clr
        ctx.font = f"bold {bigfontsize}px {FONT.default}"
        ctx.textBaseline = "bottom"
        ctx.textAlign = "right"
        ctx.fillText(text, x2 - 10, y2 - ymargin)

    def on_wheel(self, ev):
        """Handle wheel event.
        Trackpads usually have buildin inertia (by the OS), so it makese sense
        to use precise scrolling. For mouse wheel, the usual scroll amount
        is 48 units. Throttling breaks the trackpad inertia. But makes scaling
        a bit sensitive, so we do throttle scaling.
        """
        if len(ev.modifiers) == 0 and ev.vscroll != 0:
            self._scroll_trans(ev, ev.vscroll)
        elif len(ev.modifiers) == 0 and ev.hscroll != 0:
            self._scroll_scale(ev, ev.hscroll)
        elif len(ev.modifiers) == 1 and ev.modifiers[0] == "Shift":
            self._scroll_scale(ev, ev.vscroll)
        return True

    def _scroll_trans(self, ev, direction):
        # Get current range and step
        t1, t2 = self._canvas.range.get_range()
        tt1, tt2 = self._canvas.range.get_target_range()
        nsecs_step, nsecs_total = self._canvas.range.get_snap_seconds(0)
        # Apply
        step = 0.15 * nsecs_total * direction / 48
        self._canvas.range.set_range((t1 + tt1) / 2, (t2 + tt2) / 2)
        self._last_trans_scroll = time()
        self._canvas.range.animate_range(tt1 + step, tt2 + step)

    def _scroll_scale(self, ev, direction):
        # Throttle scrolling in scale
        if abs(direction) < 20 or time() - self._last_scale_scroll < 0.6:
            return
        self._last_scale_scroll = time()
        # Select reference pos and time - implicit throttle by not using target_range
        y = (ev.pos[1] - self.rect[1]) / (self.rect[3] - self.rect[1])
        t1, t2 = self._canvas.range.get_range()
        nsecs_before = t2 - t1
        # Determine scaling
        nsecs_step, nsecs_after = self._canvas.range.get_snap_seconds(
            -1 if direction < 0 else 1
        )
        # Apply
        t1 = t1 + (y * nsecs_before - y * nsecs_after)
        t2 = t1 + nsecs_after
        self._canvas.range.animate_range(t1, t2)

    def _pointer_interaction_reset(self):
        self._pointer_startrange = self._canvas.range.get_range()
        for key, pos in self._pointer_pos.items():
            self._pointer_startpos[key] = pos

    def on_pointer_outside(self, ev):
        if self._dragging_new_record is not None:
            self._dragging_new_record = None
            self.update()
        if self._selected_record is not None:
            self._selected_record = None
            self.update()

    def _selected_record_updated(self):
        if self._selected_record is not None:
            record = self._selected_record[0]
            record = window.store.records.get_by_key(record.key)
            self._selected_record = record, 0, self._canvas.now()
        self.update()

    def on_pointer(self, ev):
        """Determine what kind of interaction mode we're in, and then dispatch
        to either navigation handling or record interaction handling.
        """
        PSCRIPT_OVERLOAD = False  # noqa

        x, y = ev.pos[0], ev.pos[1]

        on_timeline = (
            x > self._timeline_bounds[0]
            and x < self._timeline_bounds[1]
            and y > self._timeline_bounds[2]
            and y < self._timeline_bounds[3]
        )

        # Get range in time and pixels
        t1, t2 = self._canvas.range.get_range()
        _, y1, _, y2 = self.rect
        npixels = y2 - y1
        nsecs = t2 - t1

        # Get current pos
        t = t1 + (y - y1) * nsecs / npixels

        # Handle new record creation via dragging.
        # This mode takes over all other behavior.
        if self._dragging_new_record:
            if "down" in ev.type:
                self._last_pointer_down_event = ev
                if on_timeline:
                    self._dragging_new_record = [t, t]
                    self.update()
                    return
                else:
                    self._dragging_new_record = None
                    pass  # Don't return, this can be the start of a normal drag
            elif "move" in ev.type:
                if self._dragging_new_record[0] > 0:
                    self._dragging_new_record[1] = t
                    self.update()
                return
            elif "up" in ev.type:
                if self._dragging_new_record[0] > 0:
                    dt1, dt2 = self._dragging_new_record
                    dt1, dt2 = min(dt1, dt2), max(dt1, dt2)
                    self._dragging_new_record = [0, 0]
                    if abs(y - self._last_pointer_down_event.pos[1]) > 4:
                        record = window.store.records.create(dt1, dt2)
                        self._canvas.record_dialog.open("New", record, self.update)
                        self._dragging_new_record = None
                self.update()
                return

        # Determine when to transition from one mode to another
        last_interaction_mode = self._interaction_mode
        if "down" in ev.type:
            if self._interaction_mode == 0 and ev.ntouches == 1:
                self._interaction_mode = 1  # mode undecided
                self._last_pointer_down_event = ev
                self.update()
            else:  # multi-touch -> tick-widget-behavior-mode
                self._interaction_mode = 2
        elif "move" in ev.type:
            if self._interaction_mode == 1:
                downx, downy = self._last_pointer_down_event.pos
                if Math.sqrt((x - downx) ** 2 + (y - downy) ** 2) > 10:
                    self._interaction_mode = 2  # tick-widget-behavior-mode
        elif "up" in ev.type:
            if "mouse" in ev.type or ev.ntouches == 0:
                self._interaction_mode = 0

        # Things that trigger on a pointer down if we have not entered tick-behavior-mode yet.
        # These are starts of a drag operation not related to timeline navigation.
        if self._interaction_mode != 2 and "down" in ev.type:
            picked = self._picker.pick(x, y)
            if picked is not None:
                if picked.recordrect and picked.region:
                    # Initiate record drag
                    self._selected_record = [picked.record, picked.region, t]
                    self._interaction_mode = 0
                    self.update()
                    return

        # Things that only trigger if we did not move the mouse too much
        if last_interaction_mode == 1 and "up" in ev.type:
            picked = self._picker.pick(x, y)
            if picked is None:
                # Initiate create-via-drag?
                if on_timeline:
                    self._dragging_new_record = [0, 0]  # 0 means wait for press
                    self.update()
                    return
            else:
                if picked.statrect:
                    # A stat rectangle
                    self._canvas.range.animate_range(picked.t1, picked.t2)
                elif picked.recordrect and not picked.region:
                    # Select a record
                    self._selected_record = [picked.record, 0, t]
                elif picked.button is True:
                    # A button was pressed
                    self._handle_button_press(picked.action, picked)
                self.update()
                return

        # Dispatch to navigation handler?
        if last_interaction_mode == 2 or self._interaction_mode == 2:
            if self._last_pointer_down_event is not None:
                self.on_pointer_navigate(self._last_pointer_down_event)
                self._last_pointer_down_event = None
            self.on_pointer_navigate(ev)

        # Dispatch to record interaction?
        if self._interaction_mode == 0:
            if self._can_interact_with_records is False:
                pass  # self._selected_record = None
            else:
                self._on_pointer_handle_record_interaction(ev)

    def _on_pointer_handle_record_interaction(self, ev):
        PSCRIPT_OVERLOAD = False  # noqa

        y = ev.pos[1]

        # Get range in time and pixels
        t1, t2 = self._canvas.range.get_range()
        _, y1, _, y2 = self.rect
        npixels = y2 - y1
        nsecs = t2 - t1

        # Get current pos
        t = t1 + (y - y1) * nsecs / npixels
        tround = 1
        secspernpixels = 10 * nsecs / npixels
        if secspernpixels > 100:
            tround = 300  # 5 min
        elif secspernpixels > 60:
            tround = 60  # 1 min

        def snap_t1(record):
            PSCRIPT_OVERLOAD = False  # noqa
            for key in self._record_times.keys():
                if key == record.key:
                    continue
                t1, t2 = self._record_times[key]
                if t2 - 2.5 * secspernpixels <= record.t1 <= t2 + tround * 0.5:
                    record.t1 = t2
                    return True
            else:
                record.t1 = Math.round(record.t1 / tround) * tround

        def snap_t2(record):
            PSCRIPT_OVERLOAD = False  # noqa
            for key in self._record_times.keys():
                if key == record.key:
                    continue
                t1, t2 = self._record_times[key]
                if t1 - tround * 0.5 <= record.t2 <= t1 + 2.5 * secspernpixels:
                    record.t2 = t1
                    return True
            else:
                record.t2 = Math.round(record.t2 / tround) * tround

        # Dragging the selected record
        if self._selected_record is not None:
            if "move" in ev.type or "up" in ev.type:
                if self._selected_record[1] > 0:
                    # Prepare
                    tstart = self._selected_record[2]
                    tdelta = t - tstart  # how much we have moved
                    record = self._selected_record[0].copy()
                    isrunning = record.t1 == record.t2
                    if isrunning:
                        record.t2 = self._canvas.now()
                    # Move
                    if self._selected_record[1] == 1 or self._selected_record[1] == 3:
                        record.t1 += tdelta
                    if self._selected_record[1] == 2 or self._selected_record[1] == 3:
                        record.t2 += tdelta
                    # Snap
                    if self._selected_record[1] == 1:
                        snap_t1(record)
                    elif self._selected_record[1] == 2:
                        snap_t2(record)
                    elif self._selected_record[1] == 3:
                        dt = record.t2 - record.t1
                        if not snap_t1(record) and snap_t2(record):
                            record.t1 = record.t2 - dt
                        else:
                            record.t2 = record.t1 + dt
                    # Finish
                    if self._selected_record[1] == 1:
                        record.t1 = min(record.t2 - 2, record.t1)
                    else:
                        record.t2 = max(record.t1 + 2, record.t2)
                    if isrunning:
                        record.t1 = min(record.t1, self._canvas.now())
                        record.t2 = record.t1
                    if not window.store.is_read_only:
                        window.store.records.put(record)
                    if "up" in ev.type:
                        self._selected_record[1] = 0
                    self.update()
                elif "up" in ev.type:  # -> self._selected_record[1] == 0:
                    # Disable when clicking elsewhere
                    self._selected_record = None
                    self.update()

    def on_pointer_navigate(self, ev):
        """Handle mouse or touch event for navigation."""
        PSCRIPT_OVERLOAD = False  # noqa

        y = ev.pos[1]

        if "down" in ev.type:
            self._pointer_inertia = []
            for key, pos in ev.touches.items():
                self._pointer_pos[key] = pos
            self._pointer_interaction_reset()
            self.update()  # with mouse down, header is different
        elif len(self._pointer_pos.keys()) == 0:
            return
        elif "mouse_move" == ev.type:  # MOUSE
            key = ev.touches.keys()[0]
            if 1 in ev.buttons:  # also if 2 is *also* down
                # Determine how much "time" the pointer has moved
                t1, t2 = self._pointer_startrange
                dy = self._pointer_startpos[key][1] - y
                nsecs = t2 - t1
                npixels = self.rect[3] - 30 - 5
                dsecs = nsecs * dy / npixels  # relative to start pos
                # Inertia
                self._pointer_inertia.push((dsecs, perf_counter()))
                while len(self._pointer_inertia) > 10:
                    self._pointer_inertia.pop(0)
                # Set it, and set new ref
                self._canvas.range.set_range(t1 + dsecs, t2 + dsecs)
                self._pointer_pos[key] = ev.pos
            elif 2 in ev.buttons:
                # Select reference position and time
                _, y1, _, y2 = self.rect
                ref_y = (self._pointer_startpos[key][1] - y1) / (y2 - y1)
                t1, t2 = self._pointer_startrange
                nsecs_before = t2 - t1
                # Determine scaling
                factor = 4
                dy = self._pointer_startpos[key][1] - y
                npixels = self.rect[3] - 30 - 5
                nsecs_after = nsecs_before * 2 ** (factor * dy / npixels)
                # Apply
                t1 = t1 + ref_y * (nsecs_before - nsecs_after)
                t2 = t1 + nsecs_after
                self._canvas.range.set_range(t1, t2)
                self._pointer_pos[key] = ev.pos
        elif "touch_move" == ev.type:  # TOUCH
            for key, pos in ev.touches.items():
                if key in self._pointer_pos:
                    self._pointer_pos[key] = pos
            # Calculate avg position and spread
            avg_pos1, std_pos1 = utils.positions_mean_and_std(
                self._pointer_startpos.values()
            )
            avg_pos2, std_pos2 = utils.positions_mean_and_std(
                self._pointer_pos.values()
            )
            # Calculate how to change the range
            t1, t2 = self._pointer_startrange
            nsecs_before = nsecs_after = t2 - t1
            npixels = self.rect[3] - 30 - 5
            if len(self._pointer_pos.keys()) > 1:
                factor = 9
                dy = std_pos1[1] - std_pos2[1]
                nsecs_after = nsecs_before * 2 ** (factor * dy / npixels)
            if True:
                dy = avg_pos1[1] - avg_pos2[1]
                dsecs = nsecs_after * dy / npixels
                # Inertia
                self._pointer_inertia.push((dsecs, perf_counter()))
                while len(self._pointer_inertia) > 10:
                    self._pointer_inertia.pop(0)
            # Apply
            mo_seconds = nsecs_after - nsecs_before
            t1 -= 0.5 * mo_seconds
            t2 += 0.5 * mo_seconds
            self._canvas.range.set_range(t1 + dsecs, t2 + dsecs)
        elif "up" in ev.type:
            for key in ev.touches.keys():
                self._pointer_pos.pop(key)
                self._pointer_startpos.pop(key)
            if len(self._pointer_pos.keys()) > 0:
                self._pointer_interaction_reset()
            else:
                # Finish the interaction - maybe apply inertia
                t1_begin, t2_begin = self._pointer_startrange
                t1_end, t2_end = self._canvas.range.get_range()
                already_panned = 0.5 * (t1_end + t2_end) - 0.5 * (t1_begin + t2_begin)
                if len(self._pointer_inertia) > 1:
                    for i in range(2, len(self._pointer_inertia) + 1):
                        ddsec = (
                            self._pointer_inertia[-1][0] - self._pointer_inertia[-i][0]
                        )
                        dtime = (
                            self._pointer_inertia[-1][1] - self._pointer_inertia[-i][1]
                        )
                        if dtime > 0.4:
                            break
                        if dtime > 0.02:
                            dsecs = 0.5 * ddsec / dtime
                            if already_panned > 0:
                                dsecs = min(dsecs, already_panned)
                            else:
                                dsecs = max(dsecs, already_panned)
                            t1, t2 = self._canvas.range.get_target_range()
                            self._canvas.range.animate_range(t1 + dsecs, t2 + dsecs)
                            return
                # If no inertia, snap
                self._canvas.range.snap()
                self.update()

    def _handle_button_press(self, action, picked):
        now = self._canvas.now()
        if action == "showrecords":
            self._canvas._prefer_show_analytics = False
            self._canvas.on_resize()
            self.update()
        elif action.startswith("zoom_"):
            t1, t2 = self._canvas.range.get_target_range()
            res = action.split("_")[-1]
            now_is_in_range = t1 <= now <= t2
            if res == "-1" or res == "+1":
                if res == "-1":
                    t1, t2 = self._canvas.range.get_snap_range(-1)
                else:
                    t1, t2 = self._canvas.range.get_snap_range(+1)
                if now_is_in_range:
                    t1, t2 = now - 0.5 * (t2 - t1), now + 0.5 * (t2 - t1)
            else:
                t_ref = now if (t1 <= now <= t2) else (t2 + t1) / 2
                t1 = dt.floor(t_ref, res)
                t2 = dt.add(t1, res)
            self._canvas.range.animate_range(t1, t2)
        elif action.startswith("step_"):
            t1, t2 = self._canvas.range.get_target_range()
            nsecs = t2 - t1
            if action == "step_backward":
                self._canvas.range.animate_range(t1 - nsecs, t1)
            else:
                self._canvas.range.animate_range(t2, t2 + nsecs)
        elif action == "editrecord":
            record = window.store.records.get_by_key(picked.key)
            self._canvas.record_dialog.open(
                "Edit", record, self._selected_record_updated
            )
        elif action == "editcurrentrecord":
            # The button for the currently selected record
            if self._selected_record:
                record = self._selected_record[0]  # before-drag!
                record = window.store.records.get_by_key(record.key)
                self._canvas.record_dialog.open(
                    "Edit", record, self._selected_record_updated
                )


class AnalyticsWidget(Widget):
    """Widget that draws the analytics, and handles corresponding interaction."""

    def on_init(self):
        self._interaction_mode = 0
        self._picker = utils.Picker()
        self.selected_tags = []
        self._need_more_drawing_flag = False
        self._time_at_last_draw = 0
        self._time_since_last_draw = 0
        self._npixels_each = 0
        self._target_scroll_offset = 0
        self._scroll_offset = 0
        self.tagzmap = {}  # public map of tagz -> tagz
        self._tag_bars_dict = {}  # tagz -> bar-info

    def on_draw(self, ctx):
        x1, y1, x2, y2 = self.rect

        # Guard for small screen space during resize
        if y2 - y1 < 20:
            return

        # return self._draw_test_grid(ctx)

        self._picker.clear()

        # If too little space, only draw button to expand
        if x2 - x1 <= 50:
            width = 30
            x3, x4 = self._canvas.w - width, self._canvas.w
            height = max(220, 0.33 * (y2 - y1))
            y3, y4 = (y1 + y2) / 2 - height / 2, (y1 + y2) / 2 + height / 2
            self._picker.register(
                x3, y3, x4, y4, {"button": True, "action": "showanalytics"}
            )
            hover = self._canvas.register_tooltip(x3, y3, x4, y4, "")
            ctx.beginPath()
            ctx.moveTo(x4, y3)
            ctx.lineTo(x3, y3 + width)
            ctx.lineTo(x3, y4 - width)
            ctx.lineTo(x4, y4)
            ctx.fillStyle = COLORS.tick_stripe2
            ctx.fill()
            ctx.textAlign = "center"
            ctx.textBaseline = "middle"
            ctx.fillStyle = COLORS.tick_text if hover else COLORS.prim1_clr
            ctx.font = FONT.size + "px " + FONT.default
            for i, c in enumerate("Overview"):
                ctx.fillText(c, (x3 + x4) / 2, (y3 + y4) / 2 + (i - 4) * 18)
            return

        self._help_text = ""

        # Process _time_at_last_draw, and set _time_since_last_draw
        time_now = time()
        if self._time_since_last_draw > 0:
            self._time_since_last_draw = time_now - self._time_at_last_draw
        else:
            self._time_since_last_draw = 0
        self._time_at_last_draw = time_now

        self._need_more_drawing_flag = False

        self._draw_stats(ctx, x1, y1, x2, y2)

        if self._need_more_drawing_flag:
            self._time_since_last_draw = 1
            self.update()
        else:
            self._time_since_last_draw = 0

        # Draw title text
        if self._canvas.w > 800:
            text1 = "Overview"
            ctx.textAlign = "right"
            ctx.textBaseline = "top"
            ctx.font = "bold " + (FONT.size * 1.4) + "px " + FONT.mono
            ctx.fillStyle = COLORS.prim2_clr
            ctx.fillText(text1, x2 - 10, 75)
            # ctx.font = (FONT.size * 0.9) + "px " + FONT.default
            # ctx.fillStyle = COLORS.prim2_clr
            # ctx.fillText(self._help_text, x2 - 10, 90)

    def _draw_test_grid(self, ctx):
        x1, y1, x2, y2 = self.rect

        grid_round = self._canvas.grid_round
        x1, x2, x3 = grid_round(x1), grid_round((x1 + x2) / 2), grid_round(x2)
        y1, y2, y3 = grid_round(y1), grid_round((y1 + y2) / 2), grid_round(y2)

        ctx.strokeStyle = "#000"
        ctx.lineWidth = 1
        for i in range((x2 - x1) / 2):
            ctx.moveTo(x1 + i * 2, y1)
            ctx.lineTo(x1 + i * 2, y3)
        ctx.stroke()
        for i in range((y2 - y1) / 2):
            ctx.moveTo(x1, y2 + i * 2)
            ctx.lineTo(x3, y2 + i * 2)
        ctx.stroke()

    def _draw_stats(self, ctx, x1, y1, x2, y2):
        PSCRIPT_OVERLOAD = False  # noqa

        # Reset times for all elements. The one that are still valid
        # will get their time set.
        for bar in self._tag_bars_dict.values():
            bar.t = 0

        # Get stats for the current time range
        t1, t2 = self._canvas.range.get_range()
        stats = window.store.records.get_stats(t1, t2)
        self._hours_in_range = int((t2 - t1) / 3600 + 0.499)

        # Get per-tag info, for tooltips
        self._time_per_tag = {}
        for tagz, t in stats.items():
            tags = tagz.split(" ")
            for tag in tags:
                self._time_per_tag[tag] = self._time_per_tag.get(tag, 0) + t

        # Determine priorities
        priorities = {}
        for tagz in stats.keys():
            tags = tagz.split(" ")
            for tag in tags:
                info = window.store.settings.get_tag_info(tag)
                priorities[tag] = info.get("priority", 0) or 1

        # Get better names (order of tags in each tag combo)
        name_map = utils.get_better_tag_order_from_stats(
            stats, self.selected_tags, False, priorities
        )

        # We keep a public tagzmap on this widget
        self.tagzmap.update(name_map)

        # Replace the stats with the updated names
        new_stats = {}
        for tagz1, tagz2 in name_map.items():
            new_stats[tagz2] = stats[tagz1]

        # Get selected tagz
        selected_tagz = ""
        if len(self.selected_tags) > 0:
            selected_tagz = self.selected_tags.join(" ")

        # Update the tag bars - add missing entries
        for tagz, t in new_stats.items():
            key = tagz
            if key in self._tag_bars_dict:
                self._tag_bars_dict[key].t = t
            else:
                self._tag_bars_dict[tagz] = {
                    "key": key,
                    "tagz": tagz,
                    "subtagz": tagz[len(selected_tagz) :].lstrip(" "),
                    "t": t,
                    "target_height": 0,
                    "target_width": 0,
                    "height": 0,
                    "width": 0,
                }

        # Determine targets
        if len(self.selected_tags) > 0:
            tagz = sorted(self.selected_tags).join(" ")
            info = window.store.settings.get_tag_info(tagz)
            self._current_targets = info.targets
        else:
            self._current_targets = {}

        # Get list of bars, and sort
        bars = self._tag_bars_dict.values()
        utils.order_stats_by_duration_and_name(bars)

        # Calculate available height for all the bars, plus space to show the total
        if len(self.selected_tags) > 0:
            header_bar_slots = 2
        else:
            header_bar_slots = 1
        avail_height1 = (y2 - y1) - 8 - 4  # bit extra to prevent FP hiding

        # Set _npixels_each (number of pixels per bar)
        npixels_each_min_max = 30, 60
        npixels_each = avail_height1 / (len(bars) + header_bar_slots)
        npixels_each = max(npixels_each, npixels_each_min_max[0])
        npixels_each = min(npixels_each, npixels_each_min_max[1])
        self._npixels_each = self._slowly_update_value(self._npixels_each, npixels_each)

        # Get vertical bounds of the space for the bars
        y_top = y1 + self._npixels_each * header_bar_slots
        y_bottom = y2 - 8
        avail_height2 = y_bottom - y_top

        # From that we can derive how many bars we can show, and the max scroll offset.
        n_bars = int(avail_height2 / self._npixels_each)
        max_scroll_offset = max(0, (len(bars) - n_bars) * self._npixels_each)
        self._target_scroll_offset = min(max_scroll_offset, self._target_scroll_offset)
        self._scroll_offset = self._slowly_update_value(
            self._scroll_offset, self._target_scroll_offset
        )

        # Calculate right base edge. Note that the bars will go beyond it
        x3 = x2 - 10 - 2

        # Three resolve passes: target size, real size, positioning
        for bar in bars:
            self._resolve_target_dimensions(bar, x3 - x1, self._npixels_each)
        for bar in bars:
            self._resolve_real_dimensions(bar)
        y = y_top - self._scroll_offset
        for bar in bars:
            self._resolve_positions(bar, x1, x3, y)
            y += bar.height

        # Check what bars to not draw, i.e. how many we're missing in view.
        n_hidden1 = n_hidden2 = 0
        drawn_bars = bars.copy()
        height_missing = 20
        while len(drawn_bars) > 1 and drawn_bars[0].y1 < y_top:
            drawn_bars.pop(0)
            n_hidden1 += 1
        while len(drawn_bars) > 1 and drawn_bars[-1].y2 > y_bottom:
            drawn_bars.pop(-1)
            n_hidden2 += 1

        # Get statistics
        total_time = 0
        overview_y2 = y_top
        if len(drawn_bars):
            overview_y2 = drawn_bars[-1].y2 + 8
        if n_hidden1 > 0 or n_hidden2 > 0:
            overview_y2 = max(overview_y2, y2)
        for bar in bars:
            total_time += bar.t

        # Prepare some more
        self._running_tagz = []
        for record in window.store.records.get_running_records():
            self._running_tagz.append(
                window.store.records.tags_from_record(record).join(" ")
            )

        # Draw all visible bars
        self._draw_container(ctx, total_time, x1, y1, x3, overview_y2)
        for bar in drawn_bars:
            self._draw_one_bar(ctx, bar)
        if n_hidden1 > 0:
            self._draw_placeholder_for_hidden_bars(
                ctx, x1 + 10, x1 + 50, y_top, y_top + height_missing, n_hidden1
            )
        if n_hidden2 > 0:
            ymiss = overview_y2 - 8
            self._draw_placeholder_for_hidden_bars(
                ctx, x1 + 10, x1 + 50, ymiss - height_missing, ymiss, n_hidden2
            )

        # # Determine help text
        # if self._maxlevel > 0:
        #     if len(self.selected_tags) == 0:
        #         self._help_text = "click a tag to filter"
        #     else:
        #         self._help_text = "click more tags to filter more"

    def _slowly_update_value(self, current, target):
        PSCRIPT_OVERLOAD = False  # noqa
        delta = target - current
        snap_limit = 1.5  # How close the value must be to just set it
        speed = 0.20  # The fraction of delta to apply. Smooth vs snappy.
        if self._time_since_last_draw > 0:
            speed = min(0.8, 12 * self._time_since_last_draw)
        if abs(delta) > snap_limit:
            self._need_more_drawing_flag = True
            return current + delta * speed
        else:
            return target

    def _resolve_target_dimensions(self, bar, width, height):
        PSCRIPT_OVERLOAD = False  # noqa

        # Bars start with zero width and height, growing to their full size,
        # but when they disappear, they only diminish in height.
        bar.target_width = width
        if bar.t == 0:
            bar.target_height = 0
        else:
            bar.target_height = height

    def _resolve_real_dimensions(self, bar, height_limit=None):
        PSCRIPT_OVERLOAD = False  # noqa

        # Set actual dimensions
        bar.height = self._slowly_update_value(bar.height, bar.target_height)
        bar.width = self._slowly_update_value(bar.width, bar.target_width)

        # Limit height
        if height_limit is not None and bar.height > height_limit + 0.1:
            bar.height = height_limit

        # Delete this one?
        if bar.t == 0 and bar.height < 5:
            self._tag_bars_dict.pop(bar.key)
            self._need_more_drawing_flag = True

    def _resolve_positions(self, bar, x1, x2, y):
        PSCRIPT_OVERLOAD = False  # noqa

        bar.x1 = x1 + 10
        bar.x2 = x1 + 10 + bar.width

        bar.y1 = y
        bar.y2 = y + bar.height

    def _draw_container(self, ctx, total_time, x1, y1, x2, y2):
        PSCRIPT_OVERLOAD = False  # noqa

        t1, t2 = self._canvas.range.get_range()
        npixels = self._npixels_each

        # Roundness
        rn = min(ANALYSIS_ROUNDNESS, npixels / 2)
        rnb = min(COLORBAND_ROUNDNESS, npixels / 2)

        # Draw front
        ctx.lineWidth = 2
        ctx.strokeStyle = COLORS.panel_edge
        ctx.fillStyle = COLORS.panel_bg
        path = window.Path2D()
        path.arc(x2 - rn, y1 + rn, rn, 1.5 * PI, 2.0 * PI)
        path.arc(x2 - rn, y2 - rn, rn, 0.0 * PI, 0.5 * PI)
        path.arc(x1 + rnb, y2 - rnb, rnb, 0.5 * PI, 1.0 * PI)
        path.arc(x1 + rnb, y1 + rnb, rnb, 1.0 * PI, 1.5 * PI)
        path.closePath()
        ctx.fill(path)
        ctx.stroke(path)

        ymid = y1 + 0.55 * npixels
        x_ref_duration = x2 - 30 + 10  # right side of minute
        x_ref_labels = x1 + 11  # start of labels
        but_height = min(30, 0.8 * npixels)

        # Get duration text
        duration = dt.duration_string(total_time, False)

        # Draw content

        ctx.textBaseline = "middle"

        if len(self.selected_tags) == 0:
            # -- Top row
            tx, ty = x_ref_labels, ymid
            # Show total
            ctx.font = FONT.size + "px " + FONT.default
            ctx.fillStyle = COLORS.record_text
            ctx.textAlign = "left"
            ctx.fillText("Total", tx, ty)
            ctx.textAlign = "right"
            ctx.fillText(duration, x_ref_duration, ty)
        else:
            # -- Top row
            tx, ty = x_ref_labels, ymid - 2
            # Show buttons
            opt = {"ref": "leftmiddle"}
            tx += 6 + self._draw_button(
                ctx, tx, ty, None, but_height, " ← ", "select:", "Back to overview", opt
            )
            if len(self.selected_tags) == 1:
                tx += 12 + self._draw_button(
                    ctx,
                    tx,
                    ty,
                    None,
                    but_height,
                    "fas-\uf02b",
                    "configure_tag:" + self.selected_tags[0],
                    "Configure tag",
                    opt,
                )
            else:
                tx += 12 + self._draw_button(
                    ctx,
                    tx,
                    ty,
                    None,
                    but_height,
                    "fas-\uf02c",
                    "configure_tags:" + self.selected_tags.join(" "),
                    "Configure tag combo",
                    opt,
                )
            # Snow tags
            opt = {
                "ref": "leftmiddle",
                "color": COLORS.button_tag_text,
                "body": COLORS.button_tag_bg,
                "padding": min(7, (x2 - x1) / 100),
            }
            for tag in self.selected_tags:
                tt = "Click to remove from filter"
                tx += 12 + self._draw_button(
                    ctx, tx, ty, None, but_height, tag, "unselect:" + tag, tt, opt
                )
            # Show total duration
            ctx.textAlign = "right"
            ctx.fillStyle = COLORS.record_text
            ctx.fillText(duration, x_ref_duration, ty)
            # -- Row for target
            tx, ty = x_ref_labels, ymid - 2 + npixels * 0.85

            # Select the target that best matches the current time range
            best_target = None
            free_days_per_week = window.simplesettings.get("workdays")
            free_hours_in_range = dt.get_free_hours_in_range(t1, t2, free_days_per_week)
            work_hours_in_range = self._hours_in_range - free_hours_in_range
            for period in ["day", "week", "month", "year"]:
                target_hours = self._current_targets.get(period, 0)
                if target_hours <= 0:
                    continue

                # hours in period -> "day": 24, "week": 168, "month": 720, "year": 8760
                if period == "day":
                    work_hours_in_period = 24
                elif period == "week":
                    work_hours_in_period = 168 - free_days_per_week * 24
                elif period == "month":  # ~4.33 weeks in a month
                    work_hours_in_period = 720 - free_days_per_week * 24 * 4.33
                elif period == "year":
                    work_hours_in_period = 8760 - free_days_per_week * 24 * 52

                factor = work_hours_in_range / work_hours_in_period
                if factor > 0.93 or not best_target:
                    best_target = {
                        "period": period,
                        "factor": factor,
                        "hours": target_hours,
                    }
                else:
                    break
            # Show target info
            ctx.font = FONT.size + "px " + FONT.default
            ctx.textAlign = "left"
            ctx.fillStyle = COLORS.prim2_clr
            if best_target:
                done_this_period = total_time
                target_this_period = 3600 * best_target.hours * best_target.factor
                prefix = "" if 0.93 < best_target.factor < 1.034 else "~ "
                if target_this_period > 0:
                    perc = 100 * done_this_period / target_this_period
                    ctx.fillText(
                        f"{best_target.period} target at {prefix}{perc:0.0f}%",
                        tx,
                        ty,
                    )
                else:
                    ctx.fillText("No target", tx, ty)
                left = target_this_period - done_this_period
                left_s = dt.duration_string(abs(left), False)
                left_prefix = "left" if left >= 0 else "over"
                ctx.textAlign = "right"
                ctx.fillText(
                    f"{left_prefix}: {prefix}{left_s}",
                    x_ref_duration,
                    ty,
                )
            else:
                ctx.fillText("No target", tx, ty)

    def _draw_placeholder_for_hidden_bars(self, ctx, x1, x2, y1, y2, n_hidden):
        PSCRIPT_OVERLOAD = False  # noqa

        # Offset the bubble by a bit
        x1 -= 2
        x2 -= 2
        y1 -= 2
        y2 -= 2

        npixels = self._npixels_each

        # Roundness
        rn = min(ANALYSIS_ROUNDNESS, npixels / 2)
        rnb = min(COLORBAND_ROUNDNESS, npixels / 2)

        # Draw front
        ctx.lineWidth = 1.2
        ctx.strokeStyle = COLORS.record_edge
        ctx.fillStyle = COLORS.record_bg
        path = window.Path2D()
        path.arc(x2 - rn, y1 + rn, rn, 1.5 * PI, 2.0 * PI)
        path.arc(x2 - rn, y2 - rn, rn, 0.0 * PI, 0.5 * PI)
        path.arc(x1 + rnb, y2 - rnb, rnb, 0.5 * PI, 1.0 * PI)
        path.arc(x1 + rnb, y1 + rnb, rnb, 1.0 * PI, 1.5 * PI)
        path.closePath()
        ctx.fill(path)

        # Draw edge
        ctx.stroke(path)

        ymid = y1 + 0.5 * (y2 - y1)

        # Draw number hidden
        ctx.font = "14px " + FONT.default
        ctx.textAlign = "left"
        ctx.fillStyle = COLORS.prim1_clr
        ctx.fillText(f"+ {n_hidden}", x1 + 11, ymid)

    def _draw_one_bar(self, ctx, bar):
        PSCRIPT_OVERLOAD = False  # noqa

        t1, t2 = self._canvas.range.get_range()
        x1, x2 = bar.x1, bar.x2
        y1, y2 = bar.y1, bar.y2
        npixels = Math.round(min(y2 - y1, self._npixels_each))

        # Get whether the current tag combi corresponds to the currently running record.
        # The clock only ticks per second if now is within range, so we don't show seconds unless we can.
        is_running = bar.tagz in self._running_tagz
        show_secs = is_running and (t1 < self._canvas.now() < t2)

        # Roundness
        rn = min(ANALYSIS_ROUNDNESS, npixels / 2)
        rnb = min(COLORBAND_ROUNDNESS, npixels / 2)

        # Draw front
        ctx.lineWidth = 1.2
        ctx.strokeStyle = COLORS.record_edge
        ctx.fillStyle = COLORS.record_bg_running if is_running else COLORS.record_bg
        path = window.Path2D()
        path.arc(x2 - rn, y1 + rn, rn, 1.5 * PI, 2.0 * PI)
        path.arc(x2 - rn, y2 - rn, rn, 0.0 * PI, 0.5 * PI)
        path.arc(x1 + rnb, y2 - rnb, rnb, 0.5 * PI, 1.0 * PI)
        path.arc(x1 + rnb, y1 + rnb, rnb, 1.0 * PI, 1.5 * PI)
        path.closePath()
        ctx.fill(path)

        # Clicking the bar itself opens the selection of all tags on the bar
        self._picker.register(
            x1,
            y1,
            x2,
            y2,
            {"button": True, "action": "select:" + bar.tagz},
        )

        ymid = y1 + 0.55 * npixels
        x_ref_duration = x2 - 30  # right side of minute
        x_ref_labels = x1 + 30  # start of labels
        but_height = min(30, 0.8 * npixels)

        # Draw coloured edge
        colors = [
            window.store.settings.get_color_for_tag(tag) for tag in bar.tagz.split(" ")
        ]
        # Width and xpos
        ew = 8 / len(colors) ** 0.5
        ew = max(ew, rnb)
        ex = x1
        # First band
        ctx.fillStyle = colors[0]
        ctx.beginPath()
        ctx.arc(x1 + rnb, y2 - rnb, rnb, 0.5 * PI, 1.0 * PI)
        ctx.arc(x1 + rnb, y1 + rnb, rnb, 1.0 * PI, 1.5 * PI)
        ctx.lineTo(x1 + ew, y1)
        ctx.lineTo(x1 + ew, y2)
        ctx.closePath()
        ctx.fill()
        # Remaining bands
        for color in colors[1:]:
            ex += ew  # + 0.15  # small offset creates subtle band
            ctx.fillStyle = color
            ctx.fillRect(ex, y1, ew, y2 - y1)
        ex += ew
        # That coloured region is also a button
        action = "configure_tag:" if len(colors) == 1 else "configure_tags:"
        self._picker.register(
            x1,
            y1,
            ex,
            y2,
            {"button": True, "action": action + bar.tagz},
        )
        tt_text = "Color for " + bar.tagz + "\n(Click to change color)"
        hover = self._canvas.register_tooltip(
            x1,
            y1,
            ex,
            y2,
            tt_text,
        )
        if hover:
            ctx.beginPath()
            ctx.arc(x1 + rnb, y2 - rnb - 0.6, rnb, 0.5 * PI, 1.0 * PI)
            ctx.arc(x1 + rnb, y1 + rnb - 0.6, rnb, 1.0 * PI, 1.5 * PI)
            ctx.lineTo(ex, y1)
            ctx.lineTo(ex, y2)
            ctx.closePath()
            ctx.stroke()

        # Draw edge
        ctx.stroke(path)

        # Draw more, or are we (dis)appearing?
        if bar.height < 25:
            return

        # Get duration text
        if show_secs:
            duration_text, duration_sec = dt.duration_string(bar.t, 2)
        else:
            duration_text = dt.duration_string(bar.t, False)
            duration_sec = ""

        # Draw content

        ctx.textBaseline = "middle"

        # Draw one row
        tx, ty = x_ref_labels, ymid - 2
        # Draw duration
        ctx.font = FONT.size + "px " + FONT.default
        ctx.textAlign = "right"
        ctx.fillStyle = COLORS.record_text
        ctx.fillText(duration_text, x_ref_duration, ty)
        if duration_sec:
            ctx.textAlign = "left"
            ctx.fillStyle = COLORS.prim2_clr
            ctx.fillText(duration_sec, x_ref_duration + 1, ty)
        # Draw tags
        tags = [tag for tag in bar.subtagz.split(" ")]
        opt = {
            "ref": "leftmiddle",
            "color": COLORS.button_tag_text,
            "body": COLORS.button_tag_bg,
            "padding": min(7, (x2 - x1) / 100),
        }
        for tag in tags:
            ctx.textAlign = "left"
            ctx.font = FONT.size + "px " + FONT.default
            ctx.fillStyle = COLORS.record_text
            if not tag:  # no tagz
                text = "General"
                ctx.fillText(text, tx, ty)
                tx += ctx.measureText(text).width + 12
            elif tag in self.selected_tags:
                text = tag
                draw_tag(ctx, text, tx, ty)
                tx += ctx.measureText(text).width + 12
            else:
                tt = dt.duration_string(self._time_per_tag.get(tag, 0))
                tt += " in total"
                tt += "\n(Click to filter)"
                tx += 12 + self._draw_button(
                    ctx, tx, ty, None, but_height, tag, "select:" + tag, tt, opt
                )

    def unselect_all_tags(self):
        self.selected_tags = []
        self._tag_bars_dict = {}  # trigger animation
        self.update()

    def on_pointer(self, ev):
        x, y = ev.pos[0], ev.pos[1]

        last_interaction_mode = self._interaction_mode
        if "down" in ev.type:
            if self._interaction_mode == 0 and ev.ntouches == 1:
                self._interaction_mode = 1  # mode undecided
                self._last_pointer_down_event = ev
                self.update()
            else:  # multi-touch -> tick-widget-behavior-mode
                self._interaction_mode = 2
        elif "move" in ev.type:
            if self._interaction_mode == 1:
                downx, downy = self._last_pointer_down_event.pos
                if Math.sqrt((x - downx) ** 2 + (y - downy) ** 2) > 10:
                    self._last_pointer_move_event = self._last_pointer_down_event
                    self._interaction_mode = 2  # tick-widget-behavior-mode
        elif "up" in ev.type:
            if "mouse" in ev.type or ev.ntouches == 0:
                self._interaction_mode = 0

        if last_interaction_mode == 1 and "up" in ev.type:
            # Clicks
            picked = self._picker.pick(x, y)
            if picked is None or picked == "":
                pass
            elif picked.button:
                if picked.action == "showanalytics":
                    self._canvas._prefer_show_analytics = True
                    self._canvas.on_resize()
                    self.update()
                elif picked.action == "report":
                    self._canvas.report_dialog.open()
                elif picked.action.startswith("select:"):
                    _, _, tagz = picked.action.partition(":")
                    if tagz:
                        for tag in tagz.split(" "):
                            if tag not in self.selected_tags:
                                self.selected_tags.push(tag)
                    else:
                        self.selected_tags = []
                    self._tag_bars_dict = {}  # trigger animation
                elif picked.action.startswith("unselect:"):
                    _, _, tagz = picked.action.partition(":")
                    if tagz:
                        for tag in tagz.split(" "):
                            if tag in self.selected_tags:
                                self.selected_tags.remove(tag)
                    self._tag_bars_dict = {}  # trigger animation
                elif picked.action.startswith("configure_tag:"):
                    _, _, tagz = picked.action.partition(":")
                    self._canvas.tag_dialog.open(tagz, self.update)
                elif picked.action.startswith("configure_tags:"):
                    _, _, tagz = picked.action.partition(":")
                    self._canvas.tag_combo_dialog.open(tagz, self.update)
                self.update()

        if self._interaction_mode == 2 and "move" in ev.type:
            dy = self._last_pointer_move_event.pos[1] - y
            self._last_pointer_move_event = ev
            self._target_scroll_offset = max(0, self._target_scroll_offset + dy)
            self.update()

    def on_wheel(self, ev):
        """Handle wheel event."""
        if len(ev.modifiers) == 0 and ev.vscroll != 0:
            self._target_scroll_offset = max(0, self._target_scroll_offset + ev.vscroll)
            self.update()
        return True


if __name__ == "__main__":
    import pscript

    pscript.script2js(
        __file__, target=__file__[:-3] + ".js", namespace="front", module_type="simple"
    )
