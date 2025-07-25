import pygame

from components.scrolling_text import ScrollingText
from core import runtime_globals
from core.constants import *
from core.utils.module_utils import get_module
from core.utils.pygame_utils import blit_with_cache, blit_with_shadow, get_font, sprite_load_percent


PAGE_MARGIN = int(16 * UI_SCALE)

class WindowStatus:
    """Handles the detailed pet status pages with optimized performance and caching."""

    def __init__(self, pet):
        """Initialize pet data and pre-load sprites."""
        self.pet = pet
        scale = UI_SCALE
        self.font_large = get_font(int(40 * UI_SCALE))
        self.font_small = get_font(int(30 * UI_SCALE))
        self.right_align_x = int(SCREEN_WIDTH - (20 * scale))

        self.scrolling_name = ScrollingText(
                self.font_large.render(self.pet.name, True, FONT_COLOR_DEFAULT),
                max_width=int((162 * UI_SCALE)),
                speed=1
            )
        self.scrolling_stage = ScrollingText(
            self.font_small.render(f"{STAGES[self.pet.stage]}", True, FONT_COLOR_DEFAULT),
            max_width=int((98 * UI_SCALE)),
            speed=1
        )

        # Pre-scale pet sprite
        self.pet_sprite = pygame.transform.scale(runtime_globals.pet_sprites[pet][0], (PET_ICON_SIZE, PET_ICON_SIZE))

        # Pre-load sprites once
        self.sprites = self.load_sprites()

        # Caching
        self._last_cache = None
        self._last_cache_key = None

    @classmethod
    def load_sprites(cls):
        """Loads status icons once and reuses them instead of reloading every draw call."""
        sprite_paths = {
            "age": AGE_ICON_PATH, "weight": WEIGHT_ICON_PATH, "module": MODULE_ICON_PATH,
            "version": VERSION_ICON_PATH, "mistakes": MISTAKES_ICON_PATH, "battle": BATTLE_ICON_PATH,
            "jogress": JOGRESS_ICON_PATH, "special": SPECIAL_ICON_PATH, "traited": TRAITED_ICON_PATH,
            "shiny": SHINY_ICON_PATH, "shook": SHOOK_ICON_PATH, "overfeed": OVERFEED_ICON_PATH,
            "sick": SICK_ICON_PATH, "sleep Dist.": SLEEP_DISTURBANCES_ICON_PATH,
            "heart_empty": HEART_EMPTY_ICON_PATH, "heart_half": HEART_HALF_ICON_PATH,
            "heart_full": HEART_FULL_ICON_PATH, "energy_bar": ENERGY_BAR_ICON_PATH,
            "energy_bar_back": ENERGY_BAR_BACK_ICON_PATH, "level": LEVEL_ICON_PATH, "exp": EXP_ICON_PATH,
        }
        # Use sprite_load_percent for all icons, scale to MENU_ICON_SIZE height, keep proportions
        return {
            key: sprite_load_percent(path, percent=(MENU_ICON_SIZE / SCREEN_HEIGHT) * 100, keep_proportion=True, base_on="height")
            for key, path in sprite_paths.items()
        }

    def set_pet(self, pet):
        """Call this when the viewed pet changes."""
        self.pet = pet
        self.scrolling_name = ScrollingText(
            self.font_large.render(self.pet.name, True, FONT_COLOR_DEFAULT),
            max_width=int((162 * UI_SCALE)),
            speed=1
        )
        self.scrolling_stage = ScrollingText(
            self.font_small.render(f"{STAGES[self.pet.stage]}", True, FONT_COLOR_DEFAULT),
            max_width=int((98 * UI_SCALE)),
            speed=1
        )
        self.pet_sprite = pygame.transform.scale(runtime_globals.pet_sprites[pet][0], (PET_ICON_SIZE, PET_ICON_SIZE))
        self._last_cache = None
        self._last_cache_key = None

    def draw_page(self, surface, page_number):
        """Draws the requested page, using cache if possible.
        On page 1, scrolling name and stage are always updated and redrawn every frame.
        """
        cache_key = (
            id(self.pet),  # Unique per pet object
            page_number,
            UI_SCALE,
            SCREEN_WIDTH,
            SCREEN_HEIGHT
        )
        if self._last_cache_key != cache_key or self._last_cache is None:
            # Redraw and cache
            page_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            draw_methods = {1: self.draw_page_1, 2: self.draw_page_2, 3: self.draw_page_3, 4: self.draw_page_4}
            if page_number in draw_methods:
                draw_methods[page_number](page_surface)
            self._last_cache = page_surface
            self._last_cache_key = cache_key

        # Blit cached static content
        #surface.blit(self._last_cache, (0, 0))
        blit_with_cache(surface, self._last_cache, (0, 0))

        # On page 1, always update and redraw scrolling name and stage
        if page_number == 1:
            spacing = int(30 * UI_SCALE)
            self.scrolling_name.update()
            self.scrolling_name.draw(surface, (int(75 * UI_SCALE), PAGE_MARGIN))
            self.scrolling_stage.update()
            self.scrolling_stage.draw(surface, (int(139 * UI_SCALE), PAGE_MARGIN + spacing))

    def draw_page_1(self, surface: pygame.Surface) -> None:
        """Draws page 1: Basic pet info (name, stage, age, weight, module, version)."""
        spacing = int(30 * UI_SCALE)
        blit_with_shadow(surface, self.pet_sprite, (PAGE_MARGIN, PAGE_MARGIN))

        #self.scrolling_name.update()
        #self.scrolling_name.draw(surface, (int(75 * UI_SCALE), PAGE_MARGIN))

        blit_with_shadow(surface, self.font_small.render(f"Stage:", True, FONT_COLOR_DEFAULT), (int(75 * UI_SCALE), PAGE_MARGIN + spacing))
        #self.scrolling_stage.update()
        #self.scrolling_stage.draw(surface, (int(139 * UI_SCALE), PAGE_MARGIN + spacing))
        
        pygame.draw.line(surface, FONT_COLOR_DEFAULT, (0, PAGE_MARGIN + PET_ICON_SIZE + spacing), (SCREEN_WIDTH, PAGE_MARGIN + PET_ICON_SIZE + spacing), 2)

        # Icons and labels
        labels = ["age", "weight", "module", "version"]
        values = [f"{self.pet.age}A", f"{self.pet.weight}g", self.pet.module, f"Ver.{self.pet.version}"]

        for i, label in enumerate(labels):
            y_pos = PAGE_MARGIN + (spacing * 3) + i * spacing
            blit_with_shadow(surface, self.sprites[label], (int(10 * UI_SCALE), y_pos))
            blit_with_shadow(surface, self.font_small.render(f"{label.capitalize()}:", True, FONT_COLOR_DEFAULT), (int(40 * UI_SCALE), y_pos))

            value_surf = self.font_small.render(values[i], True, FONT_COLOR_DEFAULT)
            value_x = self.right_align_x - value_surf.get_width()
            blit_with_shadow(surface, value_surf, (value_x, y_pos))

    def draw_page_2(self, surface: pygame.Surface) -> None:
        """Draws page 2: Hunger, strength, level, exp, and compact status for all rulesets, with icons for level, exp, and mistakes."""
        distance = int(37 * UI_SCALE)
        module = get_module(self.pet.module)

        # Hunger
        blit_with_shadow(surface, self.font_small.render("Hunger:", True, FONT_COLOR_DEFAULT), (PAGE_MARGIN, PAGE_MARGIN))
        self.draw_hearts(surface, int(SCREEN_WIDTH - (110 * UI_SCALE)), PAGE_MARGIN + int(5 * UI_SCALE), self.pet.hunger)

        # Strength
        blit_with_shadow(surface, self.font_small.render("Strength:", True, FONT_COLOR_DEFAULT), (PAGE_MARGIN, PAGE_MARGIN + distance))
        self.draw_hearts(surface, int(SCREEN_WIDTH - (110 * UI_SCALE)), PAGE_MARGIN + distance + int(5 * UI_SCALE), self.pet.strength)

        # Level and Experience (on the same line, with icons)
        level_exp_y = PAGE_MARGIN + distance * 2
        icon_spacing = int(40 * UI_SCALE)
        icon_y = level_exp_y - int(2 * UI_SCALE)
        # Level icon and value
        blit_with_shadow(surface, self.sprites["level"], (PAGE_MARGIN, icon_y))
        level_text = self.font_small.render(f"Lv: {getattr(self.pet, 'level', '-')}", True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, level_text, (PAGE_MARGIN + icon_spacing, level_exp_y))
        # Exp icon and value
        exp_icon_x = PAGE_MARGIN + icon_spacing * 2
        exp_val = getattr(self.pet, 'exp', getattr(self.pet, 'experience', '-'))
        exp_text = self.font_small.render(f"EXP: {exp_val}", True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, exp_text, (exp_icon_x + icon_spacing, level_exp_y))

        # Condition hearts or mistakes (next line, with icon for mistakes)
        y_pos = PAGE_MARGIN + distance * 3
        if getattr(module, "use_condition_hearts", False):
            blit_with_shadow(surface, self.font_small.render("Condition:", True, FONT_COLOR_DEFAULT), (PAGE_MARGIN, y_pos))
            self.draw_hearts(surface, int(SCREEN_WIDTH - (110 * UI_SCALE)), y_pos + int(5 * UI_SCALE), getattr(self.pet, "condition_hearts", 0))
        else:
            mistakes = getattr(self.pet, "mistakes", 0)
            blit_with_shadow(surface, self.sprites["mistakes"], (PAGE_MARGIN, y_pos))
            mistakes_text = self.font_small.render(f"Mistakes: {mistakes}", True, FONT_COLOR_DEFAULT)
            blit_with_shadow(surface, mistakes_text, (PAGE_MARGIN + icon_spacing, y_pos))

        # Sleep disturbances, overfeed, sick (all on the same line, with icons)
        y_pos2 = PAGE_MARGIN + distance * 4
        icon_spacing = int(80 * UI_SCALE)
        x_icon = PAGE_MARGIN

        # Sleep Disturbances
        blit_with_shadow(surface, self.sprites["sleep Dist."], (x_icon, y_pos2))
        sleep_dist = getattr(self.pet, "sleep_disturbances", 0)
        sleep_text = self.font_small.render(str(sleep_dist), True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, sleep_text, (x_icon + int(32 * UI_SCALE), y_pos2))

        # Overfeed
        x_icon += icon_spacing
        blit_with_shadow(surface, self.sprites["overfeed"], (x_icon, y_pos2))
        overfeed = getattr(self.pet, "overfeed", 0)
        overfeed_text = self.font_small.render(str(overfeed), True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, overfeed_text, (x_icon + int(32 * UI_SCALE), y_pos2))

        # Sick
        x_icon += icon_spacing
        blit_with_shadow(surface, self.sprites["sick"], (x_icon, y_pos2))
        sick = getattr(self.pet, "injuries", 0)
        sick_text = self.font_small.render(str(sick), True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, sick_text, (x_icon + int(32 * UI_SCALE), y_pos2))

        # Can Battle and Can Jogress (on the same line, compact)
        y_pos3 = PAGE_MARGIN + distance * 5
        can_battle = "Y" if getattr(self.pet, "can_battle", lambda: False)() else "N"
        can_jogress = "Y" if getattr(self.pet, "jogress_avaliable", False) else "N"
        battle_jogress_text = f"Battle: {can_battle}   Jogress: {can_jogress}"
        blit_with_shadow(surface, self.font_small.render(battle_jogress_text, True, FONT_COLOR_DEFAULT), (PAGE_MARGIN, y_pos3))

    def draw_dmc_stats(self, surface, distance):
        """Draws DMC-specific stats (mistakes, sleep disturbances, sickness)."""
        labels = ["mistakes", "sleep Dist.", "overfeed", "sick"]
        values = [self.pet.mistakes, self.pet.sleep_disturbances, self.pet.overfeed, self.pet.injuries]

        for i, label in enumerate(labels):
            y_pos = PAGE_MARGIN + (distance * (2 + i))
            blit_with_shadow(surface, self.sprites[label], (int(10 * UI_SCALE), y_pos))
            blit_with_shadow(surface, self.font_small.render(label.capitalize() + ":", True, FONT_COLOR_DEFAULT), (int(40 * UI_SCALE), y_pos))
            blit_with_shadow(surface, self.font_small.render(str(values[i]), True, FONT_COLOR_DEFAULT), (self.right_align_x, y_pos))

    def draw_penc_stats(self, surface, distance):
        """Draws PenC-specific stats (condition hearts, jogress, battle availability)."""
        blit_with_shadow(surface, self.font_small.render("Condition:", True, FONT_COLOR_DEFAULT), (PAGE_MARGIN, PAGE_MARGIN + (distance * 2)))
        self.draw_hearts(surface, int(SCREEN_WIDTH - (110 * UI_SCALE)), PAGE_MARGIN + (distance * 2) + int(5 * UI_SCALE), self.pet.condition_hearts)

        labels = ["jogress", "battle"]
        values = [self.pet.jogress_avaliable, self.pet.can_battle()]
        yes_no_values = ["Y" if v else "N" for v in values]

        for i, label in enumerate(labels):
            y_pos = PAGE_MARGIN + (distance * (3 + i))
            blit_with_shadow(surface, self.sprites[label], (int(10 * UI_SCALE), y_pos))
            blit_with_shadow(surface, self.font_small.render(label.capitalize() + ":", True, FONT_COLOR_DEFAULT), (int(40 * UI_SCALE), y_pos))
            blit_with_shadow(surface, self.font_small.render(yes_no_values[i], True, FONT_COLOR_DEFAULT), (self.right_align_x, y_pos))    

        y_pos = PAGE_MARGIN + (distance * (5))
        blit_with_shadow(surface, self.sprites["sick"], (int(10 * UI_SCALE), y_pos))
        blit_with_shadow(surface, self.font_small.render("Sick" + ":", True, FONT_COLOR_DEFAULT), (int(40 * UI_SCALE), y_pos))
        blit_with_shadow(surface, self.font_small.render(str(self.pet.injuries), True, FONT_COLOR_DEFAULT), (self.right_align_x, y_pos))  

    def draw_dmx_stats(self, surface, distance):
        """Draws DMX-specific stats (level, mistakes, sickness)."""
        labels = ["level", "exp", "mistakes", "sick"]
        values = [self.pet.level, self.pet.experience, self.pet.mistakes, self.pet.injuries]

        for i, label in enumerate(labels):
            y_pos = PAGE_MARGIN + (distance * (2 + i))
            blit_with_shadow(surface, self.sprites[label], (int(10 * UI_SCALE), y_pos))
            blit_with_shadow(surface, self.font_small.render(label.capitalize() + ":", True, FONT_COLOR_DEFAULT), (int(40 * UI_SCALE), y_pos))
            blit_with_shadow(surface, self.font_small.render(str(values[i]), True, FONT_COLOR_DEFAULT), (self.right_align_x, y_pos))

    def draw_page_3(self, surface: pygame.Surface) -> None:
        """
        Draws page 3: Effort, power, DP bar, battles, and win rates.
        """
        distance = int(37 * UI_SCALE)
        y = PAGE_MARGIN

        # Effort
        effort_label = self.font_small.render("Effort:", True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, effort_label, (PAGE_MARGIN, y))
        self.draw_hearts(surface, int(SCREEN_WIDTH - (110 * UI_SCALE)), y + int(5 * UI_SCALE), self.pet.effort, factor=2)

        # Power
        y += distance
        power_label = self.font_small.render("Power:", True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, power_label, (PAGE_MARGIN, y))

        power_value = self.pet.get_power()
        power_color = FONT_COLOR_DEFAULT if power_value == self.pet.power else (0, 255, 0)
        power_text = self.font_small.render(str(power_value), True, power_color)
        blit_with_shadow(surface, power_text, (self.right_align_x - power_text.get_width(), y))

        # DP (energy bar)
        y += distance
        dp_label = self.font_small.render("DP:", True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, dp_label, (PAGE_MARGIN, y))
        self.draw_energy_bar(surface, SCREEN_WIDTH, y, self.pet.dp, self.pet.energy)

        # Battles
        y += distance
        battles_label = self.font_small.render("Battles:", True, FONT_COLOR_DEFAULT)
        battles_value = self.font_small.render(f"{self.pet.battles}/{self.pet.totalBattles}", True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, battles_label, (PAGE_MARGIN, y))
        blit_with_shadow(surface, battles_value, (self.right_align_x - battles_value.get_width(), y))

        # Win rates
        y += distance
        stage_win_rate = (self.pet.win * 100 // self.pet.battles) if self.pet.battles > 0 else 0
        total_win_rate = (self.pet.totalWin * 100 // self.pet.totalBattles) if self.pet.totalBattles > 0 else 0

        win_stage_label = self.font_small.render("Win Rate:", True, FONT_COLOR_DEFAULT)
        win_total_label = self.font_small.render("Win Rate T.:", True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, win_stage_label, (PAGE_MARGIN, y))
        blit_with_shadow(surface, win_total_label, (PAGE_MARGIN, y + distance))

        win_stage_value = self.font_small.render(f"{stage_win_rate}%", True, FONT_COLOR_DEFAULT)
        win_total_value = self.font_small.render(f"{total_win_rate}%", True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, win_stage_value, (self.right_align_x - win_stage_value.get_width(), y))
        blit_with_shadow(surface, win_total_value, (self.right_align_x - win_total_value.get_width(), y + distance))


    def draw_page_4(self, surface: pygame.Surface) -> None:
        """
        Draws page 4: Evolution time, sleep/wake times, poop/feed times, and flags.
        """
        distance = int(37 * UI_SCALE)
        y = PAGE_MARGIN

        def format_seconds(seconds: int) -> str:
            if seconds > 0:
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                return f"{hours:02}:{minutes:02}"
            return "00:00"

        # Evolution time
        evolution_label = self.font_small.render("Evolution:", True, FONT_COLOR_DEFAULT)
        if self.pet.time >= 0 and self.pet.evolve:
            evolution_seconds = (self.pet.time * 60) - (self.pet.timer // 30)
            evolution_text = format_seconds(evolution_seconds) if evolution_seconds > 0 else "00:00"
        else:
            evolution_text = ""
        evolution_value = self.font_small.render(evolution_text, True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, evolution_label, (PAGE_MARGIN, y))
        blit_with_shadow(surface, evolution_value, (self.right_align_x - evolution_value.get_width(), y))

        # Sleeps
        y += distance
        sleeps_label = self.font_small.render("Sleeps:", True, FONT_COLOR_DEFAULT)
        sleeps_value = self.font_small.render(self.pet.sleeps, True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, sleeps_label, (PAGE_MARGIN, y))
        blit_with_shadow(surface, sleeps_value, (self.right_align_x - sleeps_value.get_width(), y))

        # Wakes (currently fixed at 00:00)
        y += distance
        wakes_label = self.font_small.render("Wakes:", True, FONT_COLOR_DEFAULT)
        wakes_value = self.font_small.render(self.pet.wakes, True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, wakes_label, (PAGE_MARGIN, y))
        blit_with_shadow(surface, wakes_value, (self.right_align_x - wakes_value.get_width(), y))

        # Poop Time
        y += distance
        poop_label = self.font_small.render("Poop Time:", True, FONT_COLOR_DEFAULT)
        poop_seconds = (self.pet.poop_timer * 60) - (self.pet.timer // 30 % (self.pet.poop_timer * 60))
        poop_text = format_seconds(poop_seconds)
        poop_value = self.font_small.render(poop_text, True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, poop_label, (PAGE_MARGIN, y))
        blit_with_shadow(surface, poop_value, (self.right_align_x - poop_value.get_width(), y))

        # Feed Time
        y += distance
        feed_label = self.font_small.render("Feed Time:", True, FONT_COLOR_DEFAULT)
        feed_seconds = (self.pet.hunger_loss * 60) - (self.pet.timer // 30 % (self.pet.hunger_loss * 60))
        feed_text = format_seconds(feed_seconds)
        feed_value = self.font_small.render(feed_text, True, FONT_COLOR_DEFAULT)
        blit_with_shadow(surface, feed_label, (PAGE_MARGIN, y))
        blit_with_shadow(surface, feed_value, (self.right_align_x - feed_value.get_width(), y))

        # Flags
        y += distance
        flags_label = self.font_small.render("Flags:", True, FONT_COLOR_DEFAULT)
        flags_value = self.font_small.render("", True, FONT_COLOR_DEFAULT)  # Empty placeholder
        blit_with_shadow(surface, flags_label, (PAGE_MARGIN, y))
        blit_with_shadow(surface, flags_value, (self.right_align_x - flags_value.get_width(), y))

        current_x = PAGE_MARGIN + int(70 * UI_SCALE)
        flag_y = y + int(5 * UI_SCALE)

        # Draw flag icons if present, spacing them horizontally by 24 pixels
        for flag_name in ["special", "shook", "traited", "shiny"]:
            if getattr(self.pet, flag_name, False):
                blit_with_shadow(surface, self.sprites[flag_name], (current_x, flag_y))
                current_x += int(24 * UI_SCALE)


    def draw_hearts(self, surface: pygame.Surface, x: int, y: int, value: int, factor: int = 1) -> None:
        """
        Draws heart icons to represent hunger, strength, or effort.
        Displays full, half, or empty hearts based on the `value` and `factor`.
        """
        total_hearts = 4
        heart_spacing = int(24 * UI_SCALE)

        heart_full = self.sprites["heart_full"]
        heart_half = self.sprites["heart_half"]
        heart_empty = self.sprites["heart_empty"]

        for i in range(total_hearts):
            heart_x = x + i * heart_spacing
            heart_threshold = (i + 1) * factor
            half_threshold = i * factor + (factor / 2)

            if value >= heart_threshold:
                blit_with_shadow(surface, heart_full, (heart_x, y))
            elif value >= half_threshold:
                blit_with_shadow(surface, heart_half, (heart_x, y))
            else:
                blit_with_shadow(surface, heart_empty, (heart_x, y))

    def draw_energy_bar(self, surface: pygame.Surface, x: int, y: int, value: int, max_value: int) -> None:
        """
        Draws the DP energy bar showing current energy `value` out of `max_value`.
        The bar consists of multiple blocks with background and filled blocks.
        """
        
        max_energy = max(1, max_value)  # Prevent division by zero
        visible_blocks = 13
        block_spacing = int(2 * UI_SCALE)
        block_width = self.sprites["energy_bar"].get_width()

        # Calculate how many blocks to fill
        if value <= 0:
            filled_blocks = 0
        elif value >= max_energy:
            filled_blocks = visible_blocks
        else:
            # Scale value proportionally to the number of visible blocks
            filled_blocks = ((value - 1) * visible_blocks) // (max_energy - 1) + 1

        # Draw background of the energy bar (offset for border effect)
        #surface.blit(self.sprites["energy_bar_back"], ((x - 5) - (visible_blocks * (block_width + block_spacing) * UI_SCALE), y + int(4 * UI_SCALE)))

        # Draw filled energy blocks
        for i in range(filled_blocks):
            bar_x = (x - 5) - (i + 1) * (block_width + block_spacing)
            #surface.blit(self.sprites["energy_bar"], (bar_x, y + int(5 * UI_SCALE)))
            blit_with_cache(surface, self.sprites["energy_bar"], (bar_x, y + int(5 * UI_SCALE)))
