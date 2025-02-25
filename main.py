import pygame
import pygame.mixer
import random
import time
import math
import os
import threading

# Constants
CELL_SIZE = 30
GRID_WIDTH = 30  # Reduced grid width
GRID_HEIGHT = 30  # Reduced grid height
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
PLAYER_SPEED = CELL_SIZE
COOLDOWN_TIME = 0.1
DEATH_COLOR = (255, 55, 55)
DEATH_SCREEN_COLOR = (255, 0, 0)
DEATH_SCREEN_TEXT_COLOR = (255, 255, 255)
FPS = 30


# Directions for DFS
DIRECTIONS = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # Up, Right, Down, Left


class Maze:
    def __init__(self):
        self.grid = self.init_grid()
        self.endpoint_pos = self.generate_maze()

    @staticmethod
    def init_grid():
        grid = [[1 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        for y in range(1, GRID_HEIGHT, 2):
            for x in range(1, GRID_WIDTH, 2):
                grid[y][x] = 0  # Open space
        return grid

    def carve_passages_from(self, cx, cy):
        stack = [(cx, cy)]
        visited = set()
        visited.add((cx, cy))

        while stack:
            (cx, cy) = stack[-1]
            directions = DIRECTIONS[:]
            random.shuffle(directions)
            carved = False

            for direction in directions:
                nx, ny = cx + direction[0] * 2, cy + direction[1] * 2
                if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT and (nx, ny) not in visited and self.grid[ny][nx] == 0:
                    wall_x, wall_y = cx + direction[0], cy + direction[1]
                    self.grid[wall_y][wall_x] = 0  # Remove the wall
                    self.grid[ny][nx] = 0
                    stack.append((nx, ny))
                    visited.add((nx, ny))
                    carved = True
                    break

            if not carved:
                stack.pop()

    def generate_maze(self):
        start_x, start_y = 1, 1  # Start in the first open cell
        self.carve_passages_from(start_x, start_y)

        # Find all the dead ends in the maze
        dead_ends = []
        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                if self.grid[y][x] == 0:  # Check if it's an open space
                    count = sum(self.grid[y + dy][x + dx] == 0 for dx, dy in DIRECTIONS)
                    if count == 1:  # If it's a dead end
                        dead_ends.append((x, y))

        # Choose a random dead end to place the exit
        random.shuffle(dead_ends)
        exit_pos = None
        for x, y in dead_ends:
            if abs(x - start_x) > 2 or abs(y - start_y) > 2:
                exit_pos = (x, y)
                break

        # If no suitable dead end is found, choose a random open space
        if exit_pos is None:
            exit_pos = random.choice([(x, y) for y in range(1, GRID_HEIGHT - 1) for x in range(1, GRID_WIDTH - 1) if self.grid[y][x] == 0])

        # Set exit in the grid
        self.grid[exit_pos[1]][exit_pos[0]] = 0
        return exit_pos
    
class Player:
    def __init__(self, maze):
        self.position = [CELL_SIZE, CELL_SIZE]
        self.direction = [0, 0]
        self.last_move_time = time.time()
        self.reached_endpoint = False
        self.maze = maze

    def move(self):
        current_time = time.time()
        if current_time - self.last_move_time >= COOLDOWN_TIME:
            new_x = self.position[0] + self.direction[0]
            new_y = self.position[1] + self.direction[1]
            grid_x, grid_y = new_x // CELL_SIZE, new_y // CELL_SIZE
            if 0 <= grid_x < GRID_WIDTH and 0 <= grid_y < GRID_HEIGHT and self.maze.grid[grid_y][grid_x] == 0:
                self.position[0] = new_x
                self.position[1] = new_y
                self.last_move_time = current_time
                if (grid_x, grid_y) == self.maze.endpoint_pos:
                    self.reached_endpoint = True  # Set flag if the player reaches the endpoint

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.direction = [0, -PLAYER_SPEED]
            elif event.key == pygame.K_DOWN:
                self.direction = [0, PLAYER_SPEED]
            elif event.key == pygame.K_LEFT:
                self.direction = [-PLAYER_SPEED, 0]
            elif event.key == pygame.K_RIGHT:
                self.direction = [PLAYER_SPEED, 0]
        elif event.type == pygame.KEYUP:
            if event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
                self.direction = [0, 0]

    def reset(self):
        self.position = [CELL_SIZE, CELL_SIZE]
        self.reached_endpoint = False

class Death:
    def __init__(self, maze, player):
        self.maze = maze
        self.player = player
        self.position = self.spawn_faraway()
        self.move_interval = 5.0
        self.speed_increase = 0.1
        self.moving = True
        self.lock = threading.Lock()
        self.start_movement_thread()

    def spawn_faraway(self):
        while True:
            x, y = self.maze.endpoint_pos
            while True:
                try:
                    x += random.choice([-1, 0, 1])
                    y += random.choice([-1, 0, 1])
                    if (
                        0 <= x < len(self.maze.grid[0]) and
                        0 <= y < len(self.maze.grid) and
                        self.maze.grid[y][x] == 0 and
                        abs(x - self.player.position[0] // CELL_SIZE) > 5 and
                        abs(y - self.player.position[1] // CELL_SIZE) > 5
                    ):
                        return x, y
                except IndexError:
                    continue

    def move_towards_player(self):
        while self.moving:
            try:
                player_x = self.player.position[0] // CELL_SIZE
                player_y = self.player.position[1] // CELL_SIZE

                with self.lock:
                    if self.position[0] < player_x:
                        self.position = (self.position[0] + 1, self.position[1])
                    elif self.position[0] > player_x:
                        self.position = (self.position[0] - 1, self.position[1])
                    if self.position[1] < player_y:
                        self.position = (self.position[0], self.position[1] + 1)
                    elif self.position[1] > player_y:
                        self.position = (self.position[0], self.position[1] - 1)

                time.sleep(self.move_interval)
                self.move_interval = max(0.1, self.move_interval - self.speed_increase)

                if self.check_collision():
                    self.moving = False
                    return True
            except Exception as e:
                print(f"An error occurred: {e}")
                self.moving = False
                return False
        return False

    def check_collision(self):
        with self.lock:
            return self.position == (self.player.position[0] // CELL_SIZE, self.player.position[1] // CELL_SIZE)

    def start_movement_thread(self):
        movement_thread = threading.Thread(target=self.move_towards_player)
        movement_thread.daemon = True
        movement_thread.start()

class WallPhantom:
    def __init__(self):
        self.x = random.randint(0, GRID_WIDTH - 1)
        self.y = random.randint(0, GRID_HEIGHT - 1)
        self.visible = False
        self.last_move_time = 0

    def appear(self):
        self.x = random.randint(0, GRID_WIDTH - 1)
        self.y = random.randint(0, GRID_HEIGHT - 1)
        self.visible = True
        self.last_move_time = time.time()

    def disappear(self):
        self.visible = False

    def check_collision(self, player_position):
        return (self.x, self.y) == (player_position[0] // CELL_SIZE, player_position[1] // CELL_SIZE)

    def update(self):
        pass


class Game:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Order of the Orderless')
        self.clock = pygame.time.Clock()
        self.maze = Maze()
        self.player = Player(self.maze)
        self.death = Death(self.maze, self.player)
        self.init_enemies()
        self.shake_factor = 0
        self.fullscreen = False
        self.running = True

        self.enemy_spawn_timer = 0
        self.enemy_spawn_interval = 35

        self.jumpscare_duration = 0.5
        self.jumpscare_timer = 0
        self.jumpscare_active = False

        self.jumpscare_sound = pygame.mixer.Sound(os.path.join("SFX", "phantomJump1.mp3"))
        self.death_sound = pygame.mixer.Sound(os.path.join("SFX", "phantomJump2.mp3"))
        self.music_loaded = False
        pygame.mixer.music.load(os.path.join("SFX", "ambience.mp3"))
        pygame.mixer.music.set_volume(0.5)

        self.blackout_duration = 0.2
        self.blackout_timer = 0
        self.blackout_active = False
        self.base_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        # Cooldown variables
        self.cooldown_active = False
        self.cooldown_timer = 0
        self.cooldown_duration = 5
        self.in_menu = True

        # Total time variable
        self.total_time = 0  
        self.game_mode_selected = False
        self.game_mode = None

        self.level = 0
        self.timer_running = True
        self.death_occurred = False

        self.e_key_held_time = 0
        self.e_key_down = False
        self.E_HOLD_TIME = 3

        self.fade_in = True
        self.fade_alpha = 0
        self.fade_last_time = time.time()
        self.fade_interval = 1

    def show_death_screen(self):
        self.death_occurred = True
        self.reset(due_to_death=True)
        self.in_menu = True

        pygame.mixer.music.stop()
        self.death_sound.play()

        self.screen.fill(DEATH_SCREEN_COLOR)
        font = pygame.font.SysFont(None, 36)
        text = font.render("Death caught up to you", True, DEATH_SCREEN_TEXT_COLOR)
        text_rect = text.get_rect(center=(SCREEN_WIDTH * CELL_SIZE // 2, SCREEN_HEIGHT * CELL_SIZE // 2))
        self.screen.blit(text, text_rect)
        pygame.display.flip()
        pygame.time.wait(2000)

    def run(self):
        while self.running:
            if self.in_menu:
                self.main_menu()
            else:

                if not self.music_loaded:
                    pygame.mixer.music.play(loops=-1)
                    self.music_loaded = True
               
                self.handle_events()
                self.player.move()
                self.update_wallPhantoms()
                self.update_shake_factor()
                self.update_camera()

                if self.check_for_enemy_encounter():
                    self.jumpscare_active = True
                    self.jumpscare_timer = 0

                if self.death.check_collision():
                    self.show_death_screen()
                
                if self.jumpscare_active:
                    self.jumpscare_timer += 1
                    if self.jumpscare_timer >= self.jumpscare_duration * 30:
                        self.jumpscare_active = False
                        self.jumpscare_timer = 0
                
                if self.blackout_active:
                    self.blackout_timer += 1
                    if self.blackout_timer >= self.blackout_duration * 30:
                        self.blackout_active = False
                        self.blackout_timer = 0
                
                self.render()
                self.clock.tick(30)
                if self.timer_running:
                    self.total_time += 1
                
        pygame.quit()

    def main_menu(self):
        title_font = pygame.font.Font(None, int(60 * SCREEN_WIDTH / 800))  # Scale font size based on screen width
        title_text = title_font.render("Order of the Orderless", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4))

        button_width = int(200 * SCREEN_WIDTH / 800)  # Scale button width based on screen width
        button_height = int(100 * SCREEN_HEIGHT / 600)  # Scale button height based on screen height

        start_button_rect = pygame.Rect(SCREEN_WIDTH // 2 - button_width // 2, SCREEN_HEIGHT // 2 - button_height // 2, button_width, button_height)
        quit_button_rect = pygame.Rect(SCREEN_WIDTH // 2 - button_width // 2, SCREEN_HEIGHT // 2 + button_height // 2 + 50, button_width, button_height)

        while self.in_menu:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.in_menu = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        self.in_menu = False
                    elif event.key == pygame.K_F11:
                        # Toggle full screen mode on F11 key press
                        self.fullscreen = not self.fullscreen
                        if self.fullscreen:
                            screen_info = pygame.display.Info()
                            screen_width = screen_info.current_w
                            screen_height = screen_info.current_h
                            self.screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
                        else:
                            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if start_button_rect.collidepoint(event.pos):
                        self.show_game_modes()
                    elif quit_button_rect.collidepoint(event.pos):
                        self.running = False
                        self.in_menu = False

            if self.fullscreen:
                screen_width, screen_height = self.screen.get_width(), self.screen.get_height()
            else:
                screen_width, screen_height = SCREEN_WIDTH, SCREEN_HEIGHT

            self.screen.fill((0, 0, 0))

            # Draw title
            self.screen.blit(title_text, title_rect)

            font = pygame.font.Font(None, int(36 * SCREEN_WIDTH / 800))  # Scale font size based on screen width

            # Draw Start Game button outline
            pygame.draw.rect(self.screen, (255, 255, 255), start_button_rect, 2)
            start_text = font.render("Start Game", True, (255, 255, 255))
            self.screen.blit(start_text, (start_button_rect.centerx - start_text.get_width() // 2,
                                        start_button_rect.centery - start_text.get_height() // 2))

            # Draw Quit button outline
            pygame.draw.rect(self.screen, (255, 255, 255), quit_button_rect, 2)
            quit_text = font.render("Quit", True, (255, 255, 255))
            self.screen.blit(quit_text, (quit_button_rect.centerx - quit_text.get_width() // 2,
                                        quit_button_rect.centery - quit_text.get_height() // 2))

            pygame.display.flip()

    def show_game_modes(self):
        title_font = pygame.font.Font(None, 60)
        title_text = title_font.render("Select Game Mode", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 1.9, SCREEN_HEIGHT // 4))


        normal_button_rect = pygame.Rect(100, SCREEN_HEIGHT // 2 - 50, 300, 100)
        desperate_button_rect = pygame.Rect(450, SCREEN_HEIGHT // 2 - 50, 300, 100)

        while self.in_menu:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.in_menu = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        self.in_menu = False
                    elif event.key == pygame.K_F11:
                        # Toggle full screen mode on F11 key press
                        self.fullscreen = not self.fullscreen
                        if self.fullscreen:
                            screen_info = pygame.display.Info()
                            screen_width = screen_info.current_w
                            screen_height = screen_info.current_h
                            self.screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
                        else:
                            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if normal_button_rect.collidepoint(event.pos):
                        self.in_menu = False
                        self.start_game("Normal")
                    elif desperate_button_rect.collidepoint(event.pos):
                        self.in_menu = False
                        self.start_game("Desperate")
                
                if self.fullscreen:
                    screen_width, screen_height = self.screen.get_width(), self.screen.get_height()
                else:
                    screen_width, screen_height = SCREEN_WIDTH, SCREEN_HEIGHT

            self.screen.fill((0, 0, 0))
            font = pygame.font.Font(None, 36)

            self.screen.blit(title_text, title_rect)

            # Draw Normal mode button
            pygame.draw.rect(self.screen, (0, 255, 0), normal_button_rect)
            normal_text = font.render("Normal Survival Mode", True, (255, 255, 255))
            self.screen.blit(normal_text, (normal_button_rect.centerx - normal_text.get_width() // 2,
                                        normal_button_rect.centery - normal_text.get_height()))

            # Draw Desperate mode button
            pygame.draw.rect(self.screen, (255, 0, 0), desperate_button_rect)
            desperate_text = font.render("Desperate Survival Mode", True, (255, 255, 255))
            self.screen.blit(desperate_text, (desperate_button_rect.centerx - desperate_text.get_width() // 2,
                                            desperate_button_rect.centery - desperate_text.get_height()))

            pygame.display.flip()

    def start_game(self, mode):
        self.in_menu = False
        if mode == "Normal":
            self.game_mode = "Normal"
        elif mode == "Desperate":
            self.game_mode = "Desperate"
        self.reset()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_F11:
                    # Toggle full screen mode on F11 key press
                    self.fullscreen = not self.fullscreen
                    if self.fullscreen:
                        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                elif event.key == pygame.K_RETURN and self.player.reached_endpoint:
                    self.reset()
                elif event.key == pygame.K_e and self.game_mode == "Normal":
                    if not self.cooldown_active:
                        self.e_key_down = True
                        self.e_key_held_time = time.time()

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_e:
                    self.e_key_down = False
                    self.e_key_held_time = 0

            self.player.handle_event(event)
        
        # Check if "E" key has been held for the required time
        if self.e_key_down and (time.time() - self.e_key_held_time >= self.E_HOLD_TIME):
            if not self.cooldown_active:
                # Hide all wallPhantoms
                for wallPhantom in self.wallPhantoms:
                    wallPhantom.disappear()
                # Start cooldown timer
                self.cooldown_active = True
                self.cooldown_timer = 0
                self.e_key_down = False  # Reset the e_key_down flag
                self.e_key_held_time = 0  # Reset the e_key_held_time



    def teleport_player(self):
        # Get player's current grid position
        player_grid_x = self.player.position[0] // CELL_SIZE
        player_grid_y = self.player.position[1] // CELL_SIZE

        # Define directions for movement
        directions = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # Up, Right, Down, Left

        # Randomly shuffle directions to randomize teleportation direction
        random.shuffle(directions)

        for distance in range(10, 21):  # Check distances from 10 to 20 cells away
            for direction in directions:
                dx, dy = direction
                new_x = player_grid_x + dx * distance
                new_y = player_grid_y + dy * distance

                # Check if the new position is within the bounds of the grid
                if 0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT:
                    # Check if the new position is a passage/white cell
                    if self.maze.grid[new_y][new_x] == 0:
                        # Calculate the screen position of the new cell
                        new_screen_x = new_x * CELL_SIZE
                        new_screen_y = new_y * CELL_SIZE

                        # Teleport the player to the new position
                        self.player.position = [new_screen_x, new_screen_y]
                        return  # Exit the method once a valid teleportation position is found

        # If no suitable white cell found in the specified range, find the closest one
        min_distance = float('inf')
        closest_x, closest_y = None, None

        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.maze.grid[y][x] == 0:  # Check if the cell is a white cell
                    # Calculate the distance from the player
                    distance = abs(x - player_grid_x) + abs(y - player_grid_y)
                    if distance < min_distance:
                        min_distance = distance
                        closest_x, closest_y = x, y

        # Teleport the player to the closest white cell found
        if closest_x is not None and closest_y is not None:
            new_screen_x = closest_x * CELL_SIZE
            new_screen_y = closest_y * CELL_SIZE
            self.player.position = [new_screen_x, new_screen_y]


    def check_for_enemy_encounter(self):
        for wallPhantom in self.wallPhantoms:
            if wallPhantom.visible and wallPhantom.check_collision(self.player.position):
                # Teleport the player after collision
                #self.teleport_player()
                # Handle jump scare and blackout effect
                self.jumpscare_active = True
                self.blackout_active = True
                wallPhantom.disappear()
                return True
        return False


    def init_enemies(self):
        self.wallPhantoms = [WallPhantom() for _ in range(255)]

    def reset(self, due_to_death=False):
        if due_to_death:
            self.level = 0
        else:
            self.level += 1

        # Reset maze
        self.maze = Maze()
        
        self.player.maze = self.maze  # Update player's maze reference
        self.player.reset()

        self.init_enemies()  # Reinitialize enemies
        self.timer_running = True

    def update_wallPhantoms(self):
        # Skip wallPhantom spawning if cooldown is active
        if not self.cooldown_active:
            self.enemy_spawn_timer += 1

            # Check if it's time to spawn a new wallPhantom
            if self.enemy_spawn_timer >= self.enemy_spawn_interval:
                self.enemy_spawn_timer = 0  # Reset the timer

                # Loop through random positions to find a suitable spawn location
                while True:
                    random_x = random.randint(1, GRID_WIDTH - 2)  # Exclude walls
                    random_y = random.randint(1, GRID_HEIGHT - 2)  # Exclude walls

                    # Check if the position is in an open space (white cell), not on player's position, and not in walls
                    if self.maze.grid[random_y][random_x] == 0 and (
                            random_x, random_y) != (
                            self.player.position[0] // CELL_SIZE, self.player.position[1] // CELL_SIZE):
                        # Spawn wallPhantom at the open space
                        for wallPhantom in self.wallPhantoms:
                            if not wallPhantom.visible:
                                wallPhantom.x = random_x
                                wallPhantom.y = random_y
                                wallPhantom.appear()
                                break  # Spawned wallPhantom, exit loop
                        break  # Exit while loop once wallPhantom is spawned

        # Update cooldown timer
        if self.cooldown_active:
            self.cooldown_timer += 1
            if self.cooldown_timer >= self.cooldown_duration * 30:  # Convert cooldown duration to frames (assuming 30 FPS)
                self.cooldown_active = False  # Cooldown expired

        # Check for collision with player and handle jump scare
        for wallPhantom in self.wallPhantoms:
            if wallPhantom.visible and wallPhantom.check_collision(self.player.position):
                # Handle jump scare and blackout effect
                self.jumpscare_active = True
                self.blackout_active = True
                wallPhantom.disappear()

                # Teleport the player after collision
                self.teleport_player()

    def update_shake_factor(self):
        if any(wallPhantom.visible for wallPhantom in self.wallPhantoms):
            min_distance = min(
                math.sqrt(
                    (self.player.position[0] - wallPhantom.x * CELL_SIZE) ** 2 + (
                                self.player.position[1] - wallPhantom.y * CELL_SIZE) ** 2)
                for wallPhantom in self.wallPhantoms if wallPhantom.visible)
        else:
            min_distance = float('inf')

        if min_distance != 0:  # Check if min_distance is not zero
            self.shake_factor = min(0.5, 0.05 / min_distance)
        else:
            self.shake_factor = 0.5  # Default shake factor when min_distance is zero

    def update_camera(self):
        self.camera_x = max(0, min(self.player.position[0] // CELL_SIZE - SCREEN_WIDTH // (2 * CELL_SIZE),
                                   GRID_WIDTH - SCREEN_WIDTH // CELL_SIZE))
        self.camera_y = max(0, min(self.player.position[1] // CELL_SIZE - SCREEN_HEIGHT // (2 * CELL_SIZE),
                                   GRID_HEIGHT - SCREEN_HEIGHT // CELL_SIZE))

    def render(self):
        self.base_surface.fill((0, 0, 0))

        if not self.blackout_active:
            
            self.draw_grid(5)  # LINE OF SIGHT RADIUS
            self.draw_player()
            self.draw_arrow()
            self.draw_death()
            
            
            if self.player.reached_endpoint:
                self.timer_running = False
                self.base_surface.fill((0, 0, 0))
                font = pygame.font.Font(None, 36)
                text = font.render(f"Press Enter to move onto LVL{self.level + 1}" , True, (255, 255, 255))
                text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
                self.base_surface.blit(text, text_rect)
            
            if self.jumpscare_active:
                self.jumpscare_effect()
            
            if self.blackout_active:
                self.blackout_effect()
            
            self.draw_timer()
        
        # Scale the base surface to the current screen resolution
        scaled_surface = pygame.transform.scale(self.base_surface, self.screen.get_size())
        self.screen.blit(scaled_surface, (0, 0))
        
        pygame.display.flip()

    def draw_death(self):
        x = self.death.position[0] * CELL_SIZE - self.camera_x * CELL_SIZE
        y = self.death.position[1] * CELL_SIZE - self.camera_y * CELL_SIZE
        pygame.draw.rect(self.base_surface, DEATH_COLOR, (x, y, CELL_SIZE, CELL_SIZE))

    def draw_timer(self):
        font = pygame.font.Font(None, 36)
  
        # Convert total time to hours, minutes, and seconds
        hours = self.total_time // (30 * 60 * 60)  # 30 FPS, 60 seconds, 60 minutes
        minutes = (self.total_time // (30 * 60)) % 60
        seconds = (self.total_time // 30) % 60
            
        # Format the time as HH:MM:SS
        time_text = font.render("{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds), True, (255, 255, 255))
        time_rect = time_text.get_rect()
        
        # Create a box for the timer
        timer_box_width = time_rect.width + 20  # Add some padding
        timer_box_height = time_rect.height + 10
        timer_box_rect = pygame.Rect((SCREEN_WIDTH - timer_box_width) // 2 + 50, 30, timer_box_width, timer_box_height)
        
        # Draw timer box
        pygame.draw.rect(self.base_surface, (0, 0, 0), timer_box_rect)
        pygame.draw.rect(self.base_surface, (255, 255, 255), timer_box_rect, 2)
        
        # Position timer within the timer box
        time_rect.centerx = timer_box_rect.centerx
        time_rect.top = timer_box_rect.top + 5
        
        # Blit timer to the base surface
        self.base_surface.blit(time_text, time_rect)
        
        # Create a box for the level counter
        level_box_width = 120  # Adjust as needed
        level_box_height = time_rect.height + 10
        level_box_rect = pygame.Rect(timer_box_rect.left - level_box_width - 10, 30, level_box_width, level_box_height)
        
        # Draw level counter box
        pygame.draw.rect(self.base_surface, (0, 0, 0), level_box_rect)
        pygame.draw.rect(self.base_surface, (255, 255, 255), level_box_rect, 2)
        
        # Render level counter
        font = pygame.font.Font(None, 36)
        level_text = font.render("LVL {:03d}".format(self.level), True, (255, 255, 255))
        level_rect = level_text.get_rect()
        
        # Position level counter within the level counter box
        level_rect.centerx = level_box_rect.centerx
        level_rect.top = level_box_rect.top + 5
        
        # Blit level counter to the base surface
        self.base_surface.blit(level_text, level_rect)

    def draw_grid(self, sight_radius):
        player_grid_x = self.player.position[0] // CELL_SIZE
        player_grid_y = self.player.position[1] // CELL_SIZE
        endpoint_pos = self.maze.endpoint_pos

        # Placeholder for endpoint position to draw it last
        endpoint_to_draw = None

        for y in range(SCREEN_HEIGHT // CELL_SIZE):
            for x in range(SCREEN_WIDTH // CELL_SIZE):
                grid_x = x + self.camera_x
                grid_y = y + self.camera_y
                distance = math.sqrt((grid_x - player_grid_x) ** 2 + (grid_y - player_grid_y) ** 2)

                if 0 <= grid_x < GRID_WIDTH and 0 <= grid_y < GRID_HEIGHT and distance <= sight_radius:
                    if (grid_x, grid_y) == endpoint_pos:
                        endpoint_to_draw = (x, y)
                    else:
                        if self.maze.grid[grid_y][grid_x] == 1:
                            color = (0, 0, 0)
                        elif self.maze.grid[grid_y][grid_x] == 0:
                            color = (255, 255, 255)
                        pygame.draw.rect(self.base_surface, color, (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        # Draw wall phantoms
        for wallPhantom in self.wallPhantoms:
            if wallPhantom.visible:
                wx = wallPhantom.x * CELL_SIZE - self.camera_x * CELL_SIZE
                wy = wallPhantom.y * CELL_SIZE - self.camera_y * CELL_SIZE
                pulsate = (math.sin(time.time() * 5) + 1) * 0.5
                color = (100 * pulsate, 0, 0)
                pygame.draw.rect(self.base_surface, color, (wx, wy, CELL_SIZE, CELL_SIZE))

        # Draw endpoint last
        if endpoint_to_draw:
            ex, ey = endpoint_to_draw
            color = (0, 255, 0)  # Green color for endpoint
            pygame.draw.rect(self.base_surface, color, (ex * CELL_SIZE, ey * CELL_SIZE, CELL_SIZE, CELL_SIZE))


    def draw_player(self):
        screen_x = self.player.position[0] - self.camera_x * CELL_SIZE
        screen_y = self.player.position[1] - self.camera_y * CELL_SIZE
        pygame.draw.rect(self.base_surface, (255, 0, 0), (screen_x, screen_y, CELL_SIZE, CELL_SIZE))

    def draw_arrow(self):
        dx = self.maze.endpoint_pos[0] * CELL_SIZE - self.player.position[0]
        dy = self.maze.endpoint_pos[1] * CELL_SIZE - self.player.position[1]
        angle = math.atan2(dy, dx)

        max_distance = math.sqrt(GRID_WIDTH ** 2 + GRID_HEIGHT ** 2) * CELL_SIZE
        nearby_enemies = [wallPhantom for wallPhantom in self.wallPhantoms if wallPhantom.visible and math.sqrt(
            (self.player.position[0] - wallPhantom.x * CELL_SIZE) ** 2 + (
                        self.player.position[1] - wallPhantom.y * CELL_SIZE) ** 2) <= 20 * CELL_SIZE]
        spin_factor = sum(
            max_distance - math.sqrt((self.player.position[0] - wallPhantom.x * CELL_SIZE) ** 2 + (
                        self.player.position[1] - wallPhantom.y * CELL_SIZE) ** 2) for wallPhantom in
            nearby_enemies) / 3
        spin_speed = 0.005 * len(nearby_enemies)

        if self.shake_factor > 0:
            angle += self.shake_factor * math.sin(time.time() * 5)

        angle += spin_factor * math.sin(time.time() * spin_speed)

        x = self.player.position[0] - self.camera_x * CELL_SIZE + CELL_SIZE // 2
        y = self.player.position[1] - self.camera_y * CELL_SIZE + CELL_SIZE // 2
        length = CELL_SIZE // 2
        target_x = x + length * math.cos(angle)
        target_y = y + length * math.sin(angle)
        pygame.draw.line(self.base_surface, (255, 255, 0), (x, y), (target_x, target_y), 3)
        pygame.draw.polygon(self.base_surface, (255, 255, 0), ((target_x, target_y),
                                                            (target_x - 8 * math.cos(angle + math.pi / 6),
                                                                target_y - 8 * math.sin(angle + math.pi / 6)),
                                                            (target_x - 8 * math.cos(angle - math.pi / 6),
                                                                target_y - 8 * math.sin(angle - math.pi / 6))))

    def jumpscare_effect(self):
        pygame.mixer.music.stop()
        self.jumpscare_sound.play()
        # Instant red screen at the beginning
        if self.jumpscare_timer < 30:  # Duration of instant red screen (1 second at 30 FPS)
            alpha = 255
        else:
            # Smoothly fade out the red screen
            alpha = max(0, 255 - int((self.jumpscare_timer - 30) * 255 / 60))  # Linear fade-out (2 seconds at 30 FPS)

        jumpscare_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        jumpscare_surface.fill((255, 0, 0, alpha))
        self.base_surface.blit(jumpscare_surface, (0, 0))
        pygame.mixer.music.play(loops=-1)


    def blackout_effect(self):
        # Draw continuous blackout effect for 3 seconds after jumpscare
        if self.blackout_active:
            alpha = min(128, int(self.blackout_timer * 128 / 90))  # Linear fade-in (90 frames at 30 FPS)
        else:
            alpha = 0

        blackout_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        blackout_surface.fill((0, 0, 0, alpha))
        self.screen.blit(blackout_surface, (0, 0))

        # Increment blackout timer
        if self.blackout_active:
            self.blackout_timer += 1

        # Deactivate blackout effect after 3 seconds
        if self.blackout_timer >= 90 and self.blackout_active:  # 3 seconds at 30 FPS
            self.blackout_active = False
            self.blackout_timer = 0

if __name__ == "__main__":
    Game().run()
    