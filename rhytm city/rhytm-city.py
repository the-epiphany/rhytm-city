import pygame
import sys
import os

# Инициализация pygame и звуковой системы
pygame.init()
pygame.mixer.init()  # Нужно для воспроизведения звуков

# Константы размеров окна
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FPS = 60  # Ограничение кадров в секунду

# Музыкальные константы
DEFAULT_BPM = 120  # Темп по умолчанию (удары в минуту)
BEATS_PER_BAR = 4  # Размер такта 4/4
STEPS_PER_BEAT = 4  # Шагов на один удар (шестнадцатые ноты)
STEPS_PER_BAR = 16  # Всего 16 шагов на такт

# Цвета для интерфейса
COLOR_BG = (20, 20, 30)  # Тёмный фон
COLOR_GRID = (50, 50, 70)  # Линии сетки
COLOR_TEXT = (200, 200, 220)  # Основной текст

# Уровни игры - список словарей с параметрами каждого уровня
LEVELS = [
    {
        "name": "Уровень 1: Первый бит",
        "description": "Поставь 3 здания и запусти музыку",
        "target_buildings": 3,
        "target_bars": 4,
        "required_bpm": None,
        "max_volume": None,
    },
    {
        "name": "Уровень 2: Темп",
        "description": "5 зданий, измени BPM на 140",
        "target_buildings": 5,
        "target_bars": 6,
        "required_bpm": 140,
        "max_volume": None,
    },
    {
        "name": "Уровень 3: Баланс громкости",
        "description": "6 зданий, микс ниже 0.70",
        "target_buildings": 6,
        "target_bars": 8,
        "required_bpm": None,
        "max_volume": 0.70,
    },
    {
        "name": "Уровень 4: Быстрый бит",
        "description": "7 зданий, BPM 160, микс < 0.65",
        "target_buildings": 7,
        "target_bars": 8,
        "required_bpm": 160,
        "max_volume": 0.65,
    },
    {
        "name": "Уровень 5: Мастер",
        "description": "Используй все типы + контроль громкости",
        "target_buildings": 8,
        "target_bars": 10,
        "required_bpm": 150,
        "max_volume": 0.60,
    },
]

# Цвета для каждого типа здания
BUILDING_COLORS = {
    "kick": (220, 50, 50),
    "snare": (50, 150, 220),
    "hihat": (220, 220, 50),
    "bass": (150, 50, 220),
    "percussion": (200, 120, 60),
    "fx": (120, 220, 220),
}


class Building:
    """Класс здания - один инструмент."""
    sounds = {}  # Общий словарь звуков для всех зданий

    @classmethod
    def load_sounds(cls):
        """Загружает звуки из папки sounds."""

        files = {
            "kick": "sounds/Navie D Kick 13.wav",
            "snare": "sounds/Navie D Snare 7.wav",
            "hihat": "sounds/Hi Hat - Hit 1.wav",
            "bass": "sounds/808 - Spinz.wav",
            "percussion": "sounds/808 - Spinz.wav",
            "fx": "sounds/Hi Hat - Hit 1.wav"
        }

        for name, path in files.items():
            if os.path.exists(path):
                cls.sounds[name] = pygame.mixer.Sound(path)
                print(f"  + {name}")
            else:
                cls.sounds[name] = None
                print(f"  ✗ {name} не найден")

    def __init__(self, col, row, building_type):
        self.col = col
        self.row = row
        self.type = building_type
        self.color = BUILDING_COLORS.get(building_type, (100, 100, 100))
        self.sound = Building.sounds.get(building_type)

        # Паттерн - 16 шагов (True/False)
        self.pattern = self.make_default_pattern()

        # Простые параметры
        self.volume = 0.7  # Громкость здания (0.0 - 1.0)
        self.muted = False
        self.solo = False

    def make_default_pattern(self):
        """Создаёт паттерн по умолчанию для типа здания."""
        pattern = [False] * 16

        if self.type == "kick":
            # Бочка на каждый удар
            pattern[0] = pattern[4] = pattern[8] = pattern[12] = True

        elif self.type == "snare":
            # Снейр на 2 и 4
            pattern[4] = pattern[12] = True

        elif self.type == "hihat":
            # Хэт каждую восьмую
            for i in range(0, 16, 2):
                pattern[i] = True

        elif self.type == "bass":
            # Бас на 1 и 3
            pattern[0] = pattern[8] = True

        elif self.type == "percussion":
            # Перкуссия на офбитах
            pattern[2] = pattern[6] = pattern[10] = pattern[14] = True

        elif self.type == "fx":
            # FX на начале половин
            pattern[0] = pattern[8] = True

        return pattern

    def should_play(self, step):
        # Проверяет, играть ли на этом шаге
        return self.pattern[step]

    def play(self, any_solo):
        # Воспроизводит звук
        # Если есть соло и это не я, то тогда не играю
        if any_solo and not self.solo:
            return

        # Если замьючен - не играю
        if self.muted:
            return

        # Играем звук с учётом громкости
        if self.sound:
            self.sound.set_volume(self.volume)
            self.sound.play()

    def draw(self, screen, grid):  # Рисует здание на сетке
        x = grid.offset_x + self.col * grid.tile_size
        y = grid.offset_y + self.row * grid.tile_size

        rect = pygame.Rect(x + 4, y + 4, grid.tile_size - 8, grid.tile_size - 8)  # Квадрат здания
        pygame.draw.rect(screen, self.color, rect)
        pygame.draw.rect(screen, (255, 255, 255), rect, 2)


class Sequencer:
    """
    Секвенсер - управляет ритмом и воспроизведением.
    Отсчитывает такты и шаги, чтобы все инструменты играли синхронно.
    """

    def __init__(self, bpm):
        self.bpm = bpm
        self.playing = False  # Играет музыка или на паузе

        # Вычисляет, сколько времени занимает один шаг
        # Формула: 60 секунд / BPM / количество шагов в одном ударе
        self.step_time = 60.0 / bpm / STEPS_PER_BEAT
        self.timer = 0.0  # Накопитель времени

        # Текущая позиция воспроизведения
        self.current_step = 0  # От 0 до 15
        self.current_bar = 0  # Номер текущего такта

    def start(self):
        # Запускает воспроизведение с начала
        self.playing = True
        self.current_step = 0
        self.current_bar = 0
        self.timer = 0.0

    def stop(self):
        # Останавливает воспроизведение
        self.playing = False

    def update(self, dt):
        """
        Обновляет таймер секвенсера.
        dt - время с прошлого кадра в секундах.
        Возвращает True, если наступил новый шаг
        """
        if not self.playing:
            return False

        # Накапливает время
        self.timer += dt

        # Если набралось достаточно времени - переходим на следующий шаг
        if self.timer >= self.step_time:
            self.timer -= self.step_time  # Сбрасываем таймер

            self.current_step += 1  # Увеличиваем номер шага

            # Если закончился такт - начинает новый
            if self.current_step >= 16:
                self.current_step = 0
                self.current_bar += 1

            return True  # Сообщает, что наступил новый шаг

        return False

    def set_bpm(self, bpm):
        # Изменяет темп и пересчитывает длительность шага
        self.bpm = bpm
        self.step_time = 60.0 / bpm / STEPS_PER_BEAT


class Grid:
    # Сетка города

    def __init__(self):
        self.cols = 12
        self.rows = 8
        self.tile_size = 64

        # Центрируем сетку
        self.offset_x = (WINDOW_WIDTH - self.cols * self.tile_size) // 2
        self.offset_y = (WINDOW_HEIGHT - self.rows * self.tile_size) // 2

    def get_cell(self, mouse_x, mouse_y):
        # Возвращает клетку по координатам мыши
        # Проверяет, попадает ли мышь в сетку
        if (self.offset_x <= mouse_x < self.offset_x + self.cols * self.tile_size and
                self.offset_y <= mouse_y < self.offset_y + self.rows * self.tile_size):
            col = (mouse_x - self.offset_x) // self.tile_size
            row = (mouse_y - self.offset_y) // self.tile_size
            return (col, row)

        return None

    def draw(self, screen):   # Рисует линии сетки
        # Вертикальные линии
        for col in range(self.cols + 1):
            x = self.offset_x + col * self.tile_size
            pygame.draw.line(screen, COLOR_GRID,
                             (x, self.offset_y),
                             (x, self.offset_y + self.rows * self.tile_size))

        for row in range(self.rows + 1):     # Горизонтальные линии
            y = self.offset_y + row * self.tile_size
            pygame.draw.line(screen, COLOR_GRID,
                             (self.offset_x, y),
                             (self.offset_x + self.cols * self.tile_size, y))


class Game:
    # Главный класс игры

    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Ритм-город")
        self.clock = pygame.time.Clock()
        self.running = True

        # Компоненты игры
        self.grid = Grid()
        self.sequencer = Sequencer(DEFAULT_BPM)
        self.buildings = []

        # UI
        self.font = pygame.font.Font(None, 28)
        self.font_small = pygame.font.Font(None, 22)

        # Выбор типа здания
        self.selected_type = "kick"

        # Редактор
        self.selected_building = None

        # Буфер для копирования
        self.copied_pattern = None

        # Система уровней
        self.current_level_index = 0
        self.level = LEVELS[0]
        self.bars_playing = 0  # Сколько тактов проиграли
        self.level_completed = False

        # RMS - средний уровень громкости
        self.current_rms = 0.0

        # Выгружаем звуки
        Building.load_sounds()
        # Мини инструкция для игрока
        print("\n=== РИТМ-ГОРОД ===")
        print(f"Текущий уровень: {self.level['name']}")
        print(f"Цель: {self.level['description']}")
        print("\nУправление:")
        print("  1-6: выбрать тип здания")
        print("  ЛКМ: поставить/выбрать здание")
        print("  ПКМ: удалить здание")
        print("  SPACE: старт/пауза")
        print("  +/-: изменить BPM")
        print("  UP/DOWN: громкость выбранного здания")
        print("  M: мьют, S: соло")
        print("  ESC: закрыть редактор")
        print("  N: следующий уровень (если пройден)\n")

    def next_level(self):
        # Переход на следующий уровень
        self.current_level_index += 1

        if self.current_level_index >= len(LEVELS):
            print("\n🎉 ВЫ ПРОШЛИ ВСЕ УРОВНИ! ПОЗДРАВЛЯЕМ!")
            self.current_level_index = len(LEVELS) - 1  # Остаётся на последнем
            return

        # Загружает новый уровень
        self.level = LEVELS[self.current_level_index]
        self.level_completed = False
        self.bars_playing = 0

        # Очищает карту
        self.buildings = []
        self.selected_building = None

        # Останавливает музыку
        self.sequencer.stop()

        print(f"\n Уровень пройден!")
        print(f"Новый уровень: {self.level['name']}")
        print(f"Цель: {self.level['description']}\n")

    def check_level_goals(self):
        # Проверяет выполнение целей уровня
        if self.level_completed:
            return

        # Проверяет количество зданий
        if len(self.buildings) < self.level['target_buildings']:
            return

        # Проверяет BPM (если требуется)
        if self.level['required_bpm'] is not None:
            if self.sequencer.bpm != self.level['required_bpm']:
                return

        # Проверяет уровень громкости (если нужно)
        if self.level['max_volume'] is not None:
            if self.current_rms > self.level['max_volume']:
                return

        # Проверяет сколько тактов проиграли
        if self.bars_playing >= self.level['target_bars']:
            self.level_completed = True
            print(f"\n🎉 УРОВЕНЬ ПРОЙДЕН! Нажми N для следующего уровня\n")

    def calculate_rms(self):
        """
        Вычисляет средний уровень громкости микса (RMS).
        RMS = Root Mean Square, показывает общую громкость всех активных инструментов.
        """
        if not self.buildings:
            return 0.0

        # Суммирует громкости всех незаглушенных зданий
        total = 0.0
        count = 0

        for b in self.buildings:
            if not b.muted:
                total += b.volume
                count += 1

        if count == 0:
            return 0.0

        # Средняя громкость умножается на коэффициент от количества источников
        # Чем больше инструментов играет одновременно, тем выше общая громкость
        avg = total / count
        rms = avg * (count / 6.0)  # Нормализуем на максимум 6 инструментов

        return min(1.0, rms)  # Ограничиваем максимум единицей

    def find_building(self, col, row):
        """Ищет здание на клетке."""
        for b in self.buildings:
            if b.col == col and b.row == row:
                return b
        return None

    def handle_events(self):
        # Обработка событий
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # Клики мыши
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos

                # Левая кнопка
                if event.button == 1:
                    # Сначала проверяет, не кликнули ли по редактору
                    if self.selected_building:
                        if self.click_on_editor(mx, my):
                            continue

                    # Клик по сетке
                    cell = self.grid.get_cell(mx, my)
                    if cell:
                        col, row = cell
                        building = self.find_building(col, row)

                        if building:
                            # Открывает редактор
                            self.selected_building = building
                        else:
                            # Ставит новое здание
                            new_building = Building(col, row, self.selected_type)
                            self.buildings.append(new_building)
                            print(f"Поставили {self.selected_type}")

                # Правая кнопка - удалить
                if event.button == 3:
                    cell = self.grid.get_cell(mx, my)
                    if cell:
                        col, row = cell
                        building = self.find_building(col, row)
                        if building:
                            self.buildings.remove(building)
                            if self.selected_building == building:
                                self.selected_building = None
                            print(f"Удалили {building.type}")

            # Клавиши
            if event.type == pygame.KEYDOWN:
                # Выбор типа
                if event.key == pygame.K_1:
                    self.selected_type = "kick"
                elif event.key == pygame.K_2:
                    self.selected_type = "snare"
                elif event.key == pygame.K_3:
                    self.selected_type = "hihat"
                elif event.key == pygame.K_4:
                    self.selected_type = "bass"
                elif event.key == pygame.K_5:
                    self.selected_type = "percussion"
                elif event.key == pygame.K_6:
                    self.selected_type = "fx"

                # Воспроизведение
                elif event.key == pygame.K_SPACE:
                    if self.sequencer.playing:
                        self.sequencer.stop()
                    else:
                        self.sequencer.start()

                # BPM
                elif event.key == pygame.K_MINUS:
                    new_bpm = max(60, self.sequencer.bpm - 10)
                    self.sequencer.set_bpm(new_bpm)
                elif event.key == pygame.K_EQUALS:
                    new_bpm = min(200, self.sequencer.bpm + 10)
                    self.sequencer.set_bpm(new_bpm)

                # Мьют/Соло
                elif event.key == pygame.K_m:
                    if self.selected_building:
                        self.selected_building.muted = not self.selected_building.muted
                elif event.key == pygame.K_s:
                    if self.selected_building:
                        self.selected_building.solo = not self.selected_building.solo

                # Громкость выбранного здания
                elif event.key == pygame.K_UP:
                    if self.selected_building:
                        self.selected_building.volume = min(1.0, self.selected_building.volume + 0.1)
                        print(f"Громкость {self.selected_building.type}: {self.selected_building.volume:.1f}")
                elif event.key == pygame.K_DOWN:
                    if self.selected_building:
                        self.selected_building.volume = max(0.0, self.selected_building.volume - 0.1)
                        print(f"Громкость {self.selected_building.type}: {self.selected_building.volume:.1f}")

                # Закрыть редактор
                elif event.key == pygame.K_ESCAPE:
                    self.selected_building = None

                # Следующий уровень (если пройден)
                elif event.key == pygame.K_n:
                    if self.level_completed:
                        self.next_level()

    def click_on_editor(self, mx, my):
        # Обрабатывает клик по редактору паттерна. Возвращает True если попали
        panel_y = WINDOW_HEIGHT - 140

        if my < panel_y:
            return False

        building = self.selected_building

        # Кнопки управления
        btn_y = panel_y + 10

        # Очистить
        if WINDOW_WIDTH - 420 <= mx <= WINDOW_WIDTH - 320 and btn_y <= my <= btn_y + 25:
            building.pattern = [False] * 16
            return True

        # Заполнить
        if WINDOW_WIDTH - 310 <= mx <= WINDOW_WIDTH - 210 and btn_y <= my <= btn_y + 25:
            building.pattern = [True] * 16
            return True

        # Копировать
        if WINDOW_WIDTH - 200 <= mx <= WINDOW_WIDTH - 100 and btn_y <= my <= btn_y + 25:
            self.copied_pattern = building.pattern.copy()
            return True

        # Вставить
        if WINDOW_WIDTH - 90 <= mx <= WINDOW_WIDTH - 10 and btn_y <= my <= btn_y + 25:
            if self.copied_pattern:
                building.pattern = self.copied_pattern.copy()
            return True

        # Клик по шагам
        step_y = panel_y + 70
        for i in range(16):
            step_x = 50 + i * 65
            if step_x <= mx <= step_x + 60 and step_y <= my <= step_y + 50:
                building.pattern[i] = not building.pattern[i]
                return True

        return False

    def update(self):
        # Обновление логики игры каждый кадр
        dt = self.clock.get_time() / 1000.0  # Время с прошлого кадра в секундах

        # Пересчитываем RMS на каждом кадре
        self.current_rms = self.calculate_rms()

        # Обновление секвенсера (проверяем, не пора ли следующий шаг)
        new_step = self.sequencer.update(dt)

        # Если наступил новый шаг - воспроизводит звуки
        if new_step:
            self.play_step()

            # Если это начало нового такта (шаг 0) - увеличиваем счётчик тактов
            if self.sequencer.current_step == 0 and self.sequencer.playing:
                self.bars_playing += 1
                self.check_level_goals()  # Проверяем цели уровня

    def play_step(self):
        # Проигрывает все звуки для текущего шага
        step = self.sequencer.current_step

        # Проверяется, есть ли соло-здания (если есть - играют только они)
        any_solo = any(b.solo for b in self.buildings)

        # Проходим по всем зданиям
        for building in self.buildings:
            # Если на этом шаге здание должно играть - запускаем звук
            if building.should_play(step):
                building.play(any_solo)

    def draw(self):
        # Отрисовка
        self.screen.fill(COLOR_BG)

        # Сетка
        self.grid.draw(self.screen)

        # Здания
        for building in self.buildings:
            building.draw(self.screen, self.grid)

        # HUD
        self.draw_hud()

        # Панель уровня
        self.draw_level_panel()

        # Редактор паттерна
        if self.selected_building:
            self.draw_editor()

        pygame.display.flip()

    def draw_hud(self):
        # Рисует верхнюю панель
        # Фон панели
        pygame.draw.rect(self.screen, (30, 30, 45), (0, 0, WINDOW_WIDTH, 80))
        pygame.draw.line(self.screen, (60, 60, 80), (0, 80), (WINDOW_WIDTH, 80), 2)

        # Выбранный тип
        # Проверяем, что тип существует (на случай если был chord)
        if self.selected_type not in BUILDING_COLORS:
            self.selected_type = "kick"

        text = self.font.render(f"Строим: {self.selected_type.upper()}",
                                True, BUILDING_COLORS[self.selected_type])
        self.screen.blit(text, (20, 15))

        hint = self.font_small.render("1-6: выбрать тип", True, (150, 150, 170))
        self.screen.blit(hint, (20, 45))

        # BPM
        bpm_text = self.font.render(f"BPM: {self.sequencer.bpm}", True, COLOR_TEXT)
        self.screen.blit(bpm_text, (400, 15))

        bpm_hint = self.font_small.render("+/- изменить", True, (150, 150, 170))
        self.screen.blit(bpm_hint, (400, 45))

        # Статус
        if self.sequencer.playing:
            status = "> ИГРАЕТ"
            color = (50, 255, 100)
        else:
            status = "|| ПАУЗА"
            color = (120, 120, 140)

        status_text = self.font.render(status, True, color)
        self.screen.blit(status_text, (650, 15))

        status_hint = self.font_small.render("SPACE: старт/пауза", True, (150, 150, 170))
        self.screen.blit(status_hint, (650, 45))

        # Счётчик
        count = self.font.render(f"Зданий: {len(self.buildings)}", True, COLOR_TEXT)
        self.screen.blit(count, (950, 15))

        if self.sequencer.playing:
            bar = self.font_small.render(f"Такт {self.sequencer.current_bar + 1}",
                                         True, (150, 150, 170))
            self.screen.blit(bar, (950, 45))

        # RMS индикатор
        rms_x = 20
        rms_y = 90
        rms_width = 200
        rms_height = 16

        # Фон
        pygame.draw.rect(self.screen, (50, 50, 60), (rms_x, rms_y, rms_width, rms_height))

        # Заполнение по уровню RMS
        fill_width = int(rms_width * self.current_rms)

        # Цвет в зависимости от уровня
        if self.current_rms < 0.6:
            rms_color = (50, 255, 100)  # Зелёный
        elif self.current_rms < 0.8:
            rms_color = (255, 200, 50)  # Жёлтый
        else:
            rms_color = (255, 80, 80)  # Красный

        if fill_width > 0:
            pygame.draw.rect(self.screen, rms_color, (rms_x, rms_y, fill_width, rms_height))

        # Рамка
        pygame.draw.rect(self.screen, (150, 150, 170), (rms_x, rms_y, rms_width, rms_height), 2)

        # Текст
        rms_label = self.font_small.render(f"RMS: {self.current_rms:.2f}", True, COLOR_TEXT)
        self.screen.blit(rms_label, (rms_x + rms_width + 10, rms_y - 2))

    def draw_level_panel(self):
        # Рисует панель с информацией об уровне
        # Панель справа
        panel_x = WINDOW_WIDTH - 350
        panel_y = 120
        panel_w = 330
        panel_h = 200

        # Фон
        pygame.draw.rect(self.screen, (35, 35, 50),
                         (panel_x, panel_y, panel_w, panel_h))
        pygame.draw.rect(self.screen, (70, 70, 90),
                         (panel_x, panel_y, panel_w, panel_h), 2)

        # Заголовок уровня
        title = self.font.render(self.level['name'], True, (200, 200, 220))
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        # Описание
        desc = self.font_small.render(self.level['description'], True, (150, 150, 170))
        self.screen.blit(desc, (panel_x + 10, panel_y + 40))

        # Цели
        y = panel_y + 70

        # Цель 1: Количество зданий
        buildings_ok = len(self.buildings) >= self.level['target_buildings']
        icon1 = "+" if buildings_ok else "-"
        color1 = (50, 255, 100) if buildings_ok else (200, 200, 220)
        goal1 = self.font_small.render(
            f"{icon1} Зданий: {len(self.buildings)}/{self.level['target_buildings']}",
            True, color1
        )
        self.screen.blit(goal1, (panel_x + 10, y))

        # Цель 2: BPM (если требуется)
        y += 25
        if self.level['required_bpm'] is not None:
            bpm_ok = self.sequencer.bpm == self.level['required_bpm']
            icon2 = "+" if bpm_ok else "-"
            color2 = (50, 255, 100) if bpm_ok else (200, 200, 220)
            goal2 = self.font_small.render(
                f"{icon2} BPM: {self.sequencer.bpm}/{self.level['required_bpm']}",
                True, color2
            )
            self.screen.blit(goal2, (panel_x + 10, y))
            y += 25

        # Цель 3: RMS (если требуется)
        if self.level['max_volume'] is not None:
            rms_ok = self.current_rms <= self.level['max_volume']
            icon3 = "+" if rms_ok else "-"
            color3 = (50, 255, 100) if rms_ok else (200, 200, 220)
            goal3 = self.font_small.render(
                f"{icon3} RMS ≤ {self.level['max_volume']:.2f} ({self.current_rms:.2f})",
                True, color3
            )
            self.screen.blit(goal3, (panel_x + 10, y))
            y += 25

        # Цель 4: Такты
        bars_ok = self.bars_playing >= self.level['target_bars']
        icon4 = "+" if bars_ok else "-"
        color4 = (50, 255, 100) if bars_ok else (200, 200, 220)
        goal4 = self.font_small.render(
            f"{icon4} Тактов: {self.bars_playing}/{self.level['target_bars']}",
            True, color4
        )
        self.screen.blit(goal4, (panel_x + 10, y))
        y += 30

        # Статус завершения
        if self.level_completed:
            status = self.font.render(" ПРОЙДЕН!", True, (50, 255, 100))
            self.screen.blit(status, (panel_x + 10, y))

            hint = self.font_small.render("Нажми N для след. уровня", True, (150, 150, 170))
            self.screen.blit(hint, (panel_x + 10, y + 30))
        else:
            status = self.font_small.render("Выполни все цели...", True, (150, 150, 170))
            self.screen.blit(status, (panel_x + 10, y))

    def draw_editor(self):
        """Рисует редактор паттерна."""
        panel_y = WINDOW_HEIGHT - 140
        building = self.selected_building

        # Фон
        pygame.draw.rect(self.screen, (35, 35, 50),
                         (0, panel_y, WINDOW_WIDTH, 140))
        pygame.draw.line(self.screen, (70, 70, 90),
                         (0, panel_y), (WINDOW_WIDTH, panel_y), 3)

        # Заголовок
        title = self.font.render(f"Редактор: {building.type.upper()}",
                                 True, building.color)
        self.screen.blit(title, (20, panel_y + 10))

        # Статус
        status_parts = []
        if building.muted:
            status_parts.append("MUTE")
        if building.solo:
            status_parts.append("SOLO")
        status_parts.append(f"Vol: {building.volume:.1f}")

        status = self.font_small.render(" | ".join(status_parts),
                                        True, (255, 200, 50))
        self.screen.blit(status, (250, panel_y + 13))

        # Кнопки управления паттерном
        buttons = [
            ("Копировать", WINDOW_WIDTH - 210, (80, 150, 200)),
            ("Вставить", WINDOW_WIDTH - 100, (200, 150, 80))
        ]

        for text, x, color in buttons:
            rect = pygame.Rect(x, panel_y + 10, 90, 25)
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)

            label = self.font_small.render(text, True, (255, 255, 255))
            label_rect = label.get_rect(center=rect.center)
            self.screen.blit(label, label_rect)

        # Подсказка
        hint = self.font_small.render("M: mute | S: solo | UP/DOWN: громкость | ESC: закрыть",
                                      True, (150, 150, 170))
        self.screen.blit(hint, (20, panel_y + 40))

        # 16 шагов паттерна
        for i in range(16):
            x = 50 + i * 65
            y = panel_y + 70

            # Выбираем цвет шага
            if building.pattern[i]:
                color = building.color  # Активный шаг - цветом инструмента
            else:
                color = (60, 60, 75)  # Неактивный шаг - серый

            # Подсвечиваем текущий шаг при воспроизведении
            if self.sequencer.playing and self.sequencer.current_step == i:
                pygame.draw.rect(self.screen, (255, 255, 100),
                                 (x - 3, y - 3, 66, 56), 3)

            # Рисуем квадрат шага
            rect = pygame.Rect(x, y, 60, 50)
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, (150, 150, 170), rect, 2)

            # Номер шага (1-16)
            num_color = (0, 0, 0) if building.pattern[i] else (120, 120, 140)
            num = self.font_small.render(str(i + 1), True, num_color)
            num_rect = num.get_rect(center=rect.center)
            self.screen.blit(num, num_rect)

    def run(self):
        """Главный цикл игры."""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


# Запуск
if __name__ == "__main__":
    game = Game()

    game.run()

