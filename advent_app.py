import asyncio
import datetime
import time

from datetime import datetime
from freezegun import freeze_time
from PIL import ImageFont

import app_runner
from lmae.core import Stage
from lmae.app import App
from lmae.actor import Rectangle, StillImage, Text


class AdventApp(App):
    """
    Display the number of days until Christmas weather
    """

    # noinspection PyTypeChecker
    def __init__(self, refresh_time: int = 60):
        super().__init__()
        self.stage: Stage = None
        self.actors = list()
        self.pre_render_callback = None
        self.refresh_time = refresh_time
        self.big_font = ImageFont.truetype("fonts/Roboto/Roboto-Light.ttf", 15)
        self.counter_label = Text(font=self.big_font, name="counter", position=(8, 2))
        self.small_font = ImageFont.truetype("fonts/teeny-tiny-pixls-font/TeenyTinyPixls-o2zo.ttf", 5)
        self.line_1_label = Text(font=self.small_font, name="line_1_text", position=(9, 18), text="days",
                                 color=(192, 192, 192, 255))
        self.line_2_label = Text(font=self.small_font, name="line_2_text", position=(7, 25), text="until",
                                 color=(192, 192, 192, 255))
        self.tree_image = StillImage(name="tree", position=(37, 0))
        self.tree_image.set_from_file('images/pixel-tree-22x32-alpha.png')
        self.days_until_christmas = 0
        self.hours_until_christmas = 0
        self.minutes_until_christmas = 0
        self.is_christmas = False

        self.lights_locations: list[tuple[int, int]] = list()
        self.lights_list: list[Rectangle] = list()
        self.find_the_tree_lights()

    def find_the_tree_lights(self):
        pil_image = self.tree_image.image
        offset = self.tree_image.position
        self.lights_locations.clear()
        for y in range(0, self.tree_image.size[1]):
            for x in range(0, self.tree_image.size[0]):
                pixel_color = pil_image.getpixel((x, y))
                if pixel_color == (255, 255, 255) or pixel_color == (255, 255, 255, 255):
                    self.lights_locations.append((x + offset[0], y + offset[1]))

        self.logger.debug(f"Found {len(self.lights_locations)} lights on tree")

        self.lights_list.clear()
        light_ctr = 0
        for location in self.lights_locations:
            light_ctr = light_ctr + 1
            light = Rectangle(name=f"Light_{light_ctr}", position=location, size=(0, 0), color=(192, 192, 255, 255))
            self.lights_list.append(light)

    def compose_view(self):
        self.stage = Stage(matrix=self.matrix, matrix_options=self.matrix_options)
        self.stage.actors.extend((self.line_1_label, self.line_2_label, self.counter_label, self.tree_image))
        self.stage.actors.extend(self.lights_list)

    def update_countdown(self):
        current_datetime = datetime.now()
        current_day = current_datetime.day
        current_month = current_datetime.month
        current_year = current_datetime.year
        self.logger.debug(f"Current date: {current_year:04}-{current_month:02}-{current_day:02}")
        self.is_christmas = current_month == 12 and current_day == 25
        christmas_has_passed = current_month == 12 and current_day > 25
        self.logger.debug(f"Has Christmas passed this year already? {'yes' if christmas_has_passed else 'no'}")

        christmas_datetime = datetime(current_year + 1 if christmas_has_passed else current_year, 12, 25, 0, 0)
        self.logger.debug(f"Date of Christmas: {christmas_datetime.year:04}-"
                          f"{christmas_datetime.month:02}-{christmas_datetime.day:02}")

        christmas_delta = christmas_datetime - current_datetime
        days_until = christmas_delta.days
        if christmas_delta.seconds > 0:
            days_until = days_until + 1
        self.days_until_christmas = days_until
        if self.days_until_christmas <= 1:
            self.hours_until_christmas = 23 - current_datetime.hour
            self.minutes_until_christmas = 60 - current_datetime.minute
        self.logger.debug(f"Counted {self.days_until_christmas} days until Christmas")

    @staticmethod
    def format_epoch_time(timestamp):
        timestamp_format = "%H:%M:%S"
        if timestamp is str:
            timestamp = float(timestamp)
        return time.strftime(timestamp_format, time.localtime(timestamp))

    def update_view(self):
        self.counter_label.set_text(str(self.days_until_christmas))
        self.counter_label.show()
        self.line_2_label.set_text("until")
        if self.is_christmas:
            self.counter_label.hide()
            self.line_1_label.set_text("Merry")
            self.line_2_label.set_text("")
        elif self.days_until_christmas == 1:
            if self.hours_until_christmas < 1:
                if self.minutes_until_christmas == 1:
                    self.line_1_label.set_text("min")
                else:
                    self.line_1_label.set_text("mins")
                self.counter_label.set_text(str(self.minutes_until_christmas))
            else:
                if self.hours_until_christmas == 1:
                    self.line_1_label.set_text("hour")
                else:
                    self.line_1_label.set_text("hours")
                self.counter_label.set_text(str(self.hours_until_christmas))
        else:  # days
            self.line_1_label.set_text("days")

        if len(self.counter_label.text) <= 1:
            self.counter_label.set_position((12, 2))
        else:
            self.counter_label.set_position((8, 2))

    def prepare(self):
        self.compose_view()

    async def run(self):
        await super().run()
        self.logger.debug("Run started")
        # self.compose_view()
        max_frame_rate = 20
        min_time_per_frame = 1.0 / max_frame_rate

        try:
            while self.running:
                # get updated day count
                self.update_countdown()

                # update the view
                self.update_view()
                if self.stage.needs_render:
                    self.stage.render_frame()

                # wait 15 minutes
                waiting = True
                wait_start = time.time()
                self.logger.debug(f"Waiting {self.refresh_time / 60} minutes to refresh day count")
                last_time = time.perf_counter()
                while waiting and self.running:
                    current_time = time.time()
                    elapsed_time = current_time - wait_start
                    self.update_view()
                    # self.stage.needs_render = True  # have to force this for some reason
                    self.stage.render_frame()
                    waiting = elapsed_time < self.refresh_time

                    # calculate the frame rate and render that
                    render_end_time = time.perf_counter()

                    # if we are rendering faster than max frame rate, slow down
                    elapsed_render_time = render_end_time - last_time
                    if elapsed_render_time < min_time_per_frame:
                        sleep_time = min_time_per_frame - elapsed_render_time
                        # self.logger.debug(f"Sleeping for {sleep_time}")
                        await asyncio.sleep(sleep_time)
                    else:
                        # gotta yield control, with minimal sleep amount
                        await asyncio.sleep(min_time_per_frame/10.0)

                    # mark the timestamp
                    last_time = time.perf_counter()

        finally:
            self.logger.debug("Run stopped")


# get environment variables
app_runner.app_setup()
advent_app = AdventApp()
advent_app.set_matrix(app_runner.matrix, options=app_runner.matrix_options)
app_runner.start_app(advent_app)
