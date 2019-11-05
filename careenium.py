import arcade
import pymunk
import math
from functools import lru_cache
import random
import timeit

SCALE = 5
GRID = 16
SCREEN_WIDTH = int(16 * SCALE * GRID)
SCREEN_HEIGHT = int(9 * SCALE * GRID)

SCREEN_TITLE = 'Careenium'

MODES = ['Circle', 'Pipe', 'Box', 'Static']

GAME_MODES = ['Gravity', 'Setup', 'No Gravity']

FRICTION = 0.95


class PhysicsSprite(arcade.Sprite):
    def __init__(self, pymunk_shape, filename):
        super().__init__(filename, center_x=pymunk_shape.body.position.x, center_y=pymunk_shape.body.position.y)
        self.pymunk_shape = pymunk_shape


class CircleSprite(PhysicsSprite):
    def __init__(self, pymunk_shape, filename):
        super().__init__(pymunk_shape, filename)
        self.width = pymunk_shape.radius * 2
        self.height = pymunk_shape.radius * 2


class BoxSprite(PhysicsSprite):
    def __init__(self, pymunk_shape, filename, width, height):
        super().__init__(pymunk_shape, filename)
        self.width = width
        self.height = height


class Careenium(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)

        arcade.set_background_color((80, 120, 132))

        self.space = pymunk.Space()
        self.space.gravity = (0.0, -900.0)
        self.space.sleep_time_threshold = 100

        self.sprite_list: arcade.SpriteList[PhysicsSprite] = arcade.SpriteList()

        self.shape_being_dragged = None  # if a shape is being moved it will be stored here
        self.shape_a = None  # if two bodies are being tethered they will be stored here
        self.shape_b = None
        self.shape_a_connection_point = None
        self.shape_b_connection_point = None
        self.v_point = None
        self.point_pair = None
        self.joints = []
        self.joint_objects = None
        self.walls = []
        self.wall_objects = None
        self.pipes = []
        self.mouse_down = False
        self.grid = False
        self.snapping = False
        self.mouse_pos = 0, 0
        self.mouse_button = None
        self.joints = []

        self.game_mode = 0
        self.draw_time = 0
        self.processing_time = 0

        self.creation_mode = 0
        self.create_walls()
        self.tick = 0

    def rr(self, val):
        if self.grid:
            return (val + (GRID // 2)) // GRID * GRID
        else:
            return val

    def mode_switcher(self):
        if self.game_mode == 0:
            self.space.gravity = (0.0, -900.0)
            self.space.damping = 0.95
        if self.game_mode == 1:
            self.space.gravity = (0.0, 0.0)
            self.space.damping = 0
        if self.game_mode == 2:
            self.space.gravity = (0.0, 0.0)
            self.space.damping = 1

    def delete_object(self, obj):
        if type(obj.shape) in [pymunk.shapes.Circle, pymunk.shapes.Poly]:
            for sprite in self.sprite_list:
                if sprite.pymunk_shape == obj.shape:
                    sprite.kill()
                    for joint in self.joints:
                        if sprite.pymunk_shape.body in [joint.a, joint.b]:
                            self.joints.remove(joint)
                            self.space.remove(joint)
                    for pipe in self.pipes:
                        if pipe.pymunk_shape == obj.shape:
                            self.pipes.remove(pipe)
        if type(obj.shape) is pymunk.shapes.Segment:
            self.walls.remove(obj.shape)
            self.create_walls()
        self.space.remove(obj.shape, obj.shape.body)

    def create_walls(self):
        self.wall_objects = arcade.ShapeElementList()
        for wall in self.walls:
            curr_wall = arcade.create_line(start_x=wall.a.x, start_y=wall.a.y, end_x=wall.b.x, end_y=wall.b.y, color=arcade.color.WHITE, line_width=2)
            self.wall_objects.append(curr_wall)

    def create_joints(self):
        self.joint_objects = arcade.ShapeElementList()
        for joint in self.joints:
            curr_joint = arcade.create_line(start_x=joint.a.local_to_world(joint.anchor_a).x, start_y=joint.a.local_to_world(joint.anchor_a).y, end_x=joint.b.local_to_world(joint.anchor_b).x, end_y=joint.b.local_to_world(joint.anchor_b).y, color=arcade.color.RED, line_width=2)
            self.joint_objects.append(curr_joint)

    def on_draw(self):
        arcade.start_render()

        draw_start_time = timeit.default_timer()

        self.sprite_list.draw()
        self.wall_objects.draw()
        if self.joint_objects:
            self.create_joints()
            self.joint_objects.draw()
        if self.point_pair and self.mouse_down and self.point_pair != self.mouse_pos:
            if self.mouse_button == 4:
                arcade.draw_line(color=arcade.color.GREEN, start_x=self.point_pair[0], start_y=self.point_pair[1], end_x=self.mouse_pos[0], end_y=self.mouse_pos[1], line_width=2)
            elif self.mouse_button == 1 and self.creation_mode < 4:
                arcade.draw_line(color=arcade.color.RED, start_x=self.point_pair[0], start_y=self.point_pair[1], end_x=self.mouse_pos[0], end_y=self.mouse_pos[1], line_width=2)
            elif self.mouse_button == 1:
                arcade.draw_line(color=arcade.color.BLUE, start_x=self.point_pair[0], start_y=self.point_pair[1], end_x=self.mouse_pos[0], end_y=self.mouse_pos[1], line_width=2)

        output = f"Processing time: {self.processing_time:.3f}"
        arcade.draw_text(output, 20, SCREEN_HEIGHT - 20, arcade.color.WHITE)

        output = f"Drawing time: {self.draw_time:.3f}"
        arcade.draw_text(output, 20, SCREEN_HEIGHT - 40, arcade.color.WHITE)
        arcade.draw_text(text=f"{GAME_MODES[self.game_mode]}", start_x=400, start_y=32, color=arcade.color.WHITE, font_size=16, align='right')

        arcade.draw_text(text=f"{MODES[self.creation_mode]}", start_x=20, start_y=32, color=arcade.color.WHITE, font_size=16, align='right')

        if self.grid:
            arcade.draw_point(x=self.rr(self.mouse_pos[0]), y=self.rr(self.mouse_pos[1]),  color=(156, 32, 32, 255), size=10)

        self.draw_time = timeit.default_timer() - draw_start_time

    def make_box(self, x, y):
        size = GRID * 2
        mass = 12.0
        moment = pymunk.moment_for_box(mass, (size, size))
        body = pymunk.Body(mass, moment)
        body.position = pymunk.Vec2d(x, y)
        shape = pymunk.Poly.create_box(body, (size, size))
        shape.friction = FRICTION
        self.space.add(body, shape)
        sprite = BoxSprite(shape, "images/boxCrate.png", width=size, height=size)
        self.sprite_list.append(sprite)

    def make_static(self, x, y):
        size = GRID * 2
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(x, y)
        shape = pymunk.Poly.create_box(body, (size, size))
        shape.friction = FRICTION
        shape.elasticity = 1.0
        self.space.add(body, shape)
        sprite = BoxSprite(shape, "images/boxCrate_double.png", width=size, height=size)
        self.sprite_list.append(sprite)

    def make_circle(self, x, y, v=(0, 0)):
        size = (GRID * 3) // 2 - (random.randint(0, 2) / 2)
        mass = 12.0 + (random.random() * 2)
        moment = pymunk.moment_for_circle(mass, 0, size, (0, 0))
        body = pymunk.Body(mass, moment)
        body.position = pymunk.Vec2d(x + random.randint(-2, 2), y + random.randint(-2, 2))
        body.angle = random.randint(0, 359)
        body.angular_velocity = random.randint(-20, 20)
        body.velocity = v
        shape = pymunk.Circle(body, size, pymunk.Vec2d(0, 0))
        shape.friction = FRICTION
        shape.elasticity = 0.3
        self.space.add(body, shape)
        sprite = CircleSprite(shape, f"images/hudPlayer_{random.choice(['beige', 'blue', 'green', 'pink', 'yellow'])}.png")
        self.sprite_list.append(sprite)

    def make_pipe(self, x, y):
        size = (GRID * 2) // 2 + (GRID // 8)
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pymunk.Vec2d(x, y)
        shape = pymunk.Circle(body, size, pymunk.Vec2d(0, 0))
        shape.friction = FRICTION
        shape.elasticity = 0.3

        self.space.add(body, shape)
        sprite = CircleSprite(shape, "images/pipe.png")
        self.sprite_list.append(sprite)
        self.pipes.append(sprite)

    def make_pin_joint(self, x, y):
        shape_selected = self.get_shape(x, y)
        if shape_selected is None:
            self.shape_a = None
            self.shape_b = None
            self.point_pair = None
            return
        if self.shape_a is None:
            self.point_pair = self.rr(x), self.rr(y)
            self.shape_a = shape_selected
            self.shape_a_connection_point = self.shape_a.shape.body.world_to_local((self.rr(x), self.rr(y)))
        elif self.shape_b is None:
            if self.shape_a.shape != shape_selected.shape:
                self.shape_b = shape_selected
                self.shape_b_connection_point = self.shape_b.shape.body.world_to_local((self.rr(x), self.rr(y)))
                joint = pymunk.PinJoint(self.shape_a.shape.body, self.shape_b.shape.body, self.shape_a_connection_point, self.shape_b_connection_point)
                self.space.add(joint)
                self.joints.append(joint)
                self.create_joints()
            self.shape_a = None
            self.shape_b = None
            self.point_pair = None

    def make_pivot_joint(self, x, y):
        shape_selected = self.get_shape(x, y)
        if shape_selected is None:
            self.shape_a = None
            self.shape_b = None
            self.point_pair = None
            return
        if self.shape_a is None:
            self.point_pair = self.rr(x), self.rr(y)
            self.shape_a = shape_selected
        elif self.shape_b is None:
            if self.shape_a.shape != shape_selected.shape:
                self.shape_b = shape_selected
                joint = pymunk.PivotJoint(self.shape_a.shape.body, self.shape_b.shape.body, (self.shape_a.shape.body.position.x - self.shape_b.shape.body.position.x, self.shape_a.shape.body.position.y - self.shape_b.shape.body.position.y))
                self.space.add(joint)
                self.joints.append(joint)
                self.create_joints()
            self.shape_a = None
            self.shape_b = None
            self.point_pair = None

    def make_line(self, x, y):
        if self.point_pair is None:
            self.point_pair = self.rr(x), self.rr(y)
        elif self.point_pair != self.mouse_pos:
            body = pymunk.Body(body_type=pymunk.Body.STATIC)
            shape = pymunk.Segment(body, self.point_pair, self.mouse_pos, 1.0)
            shape.friction = FRICTION
            shape.elasticity = 0.95
            self.space.add(body, shape)
            self.walls.append(shape)
        self.create_walls()

    def get_shape(self, x, y):
        shape_list = self.space.point_query((x, y), 2, pymunk.ShapeFilter())
        if shape_list:
            return shape_list[0]
        return None

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        self.mouse_button = button
        cur_shape = self.get_shape(x, y)

        if button == 1:
            if modifiers in [0, 16]:
                if self.get_shape(x, y) is None:
                    if self.creation_mode == 0:
                        self.point_pair = self.rr(x), self.rr(y)
                        self.mouse_down = True
                    elif self.creation_mode == 1:
                        self.make_pipe(self.rr(x), self.rr(y))
                    elif self.creation_mode == 2:
                        self.make_box(self.rr(x), self.rr(y))
                    elif self.creation_mode == 3:
                        self.make_static(self.rr(x), self.rr(y))
                else:
                    self.shape_being_dragged = cur_shape
            else:
                if cur_shape:
                    self.delete_object(cur_shape)

        elif button == 4:
            if cur_shape:
                self.make_pin_joint(self.rr(x), self.rr(y))
                self.mouse_down = True
            else:
                self.make_line(self.rr(x), self.rr(y))
                self.mouse_down = True

    def on_mouse_release(self, x, y, button, modifiers):
        if self.mouse_down:
            if button == 1 and self.creation_mode == 0:
                self.make_circle(self.point_pair[0], self.point_pair[1], v=((self.point_pair[0] - self.rr(x)) * 5, (self.point_pair[1] - self.rr(y)) * 5))
            if button == 4 and self.get_shape(x, y):
                self.make_pin_joint(x, y)
            elif button == 4:
                self.make_line(x, y)
        self.point_pair = None
        self.shape_being_dragged = None
        self.mouse_down = False
        self.shape_a = None
        self.shape_b = None
        self.shape_a_connection_point = None
        self.shape_b_connection_point = None

    def on_mouse_motion(self, x, y, dx, dy):
        if self.snapping:
            if self.point_pair:
                if abs(self.rr(x) - self.point_pair[0]) < abs(self.rr(y) - self.point_pair[1]):
                    self.mouse_pos = self.point_pair[0], self.rr(y)
                else:
                    self.mouse_pos = self.rr(x), self.point_pair[1]
        else:
            self.mouse_pos = self.rr(x), self.rr(y)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if (scroll_y > 0 and self.creation_mode < len(MODES) - 1) or self.creation_mode > 0 > scroll_y:
            self.creation_mode += scroll_y

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.SPACE:
            self.grid = not self.grid
        if symbol == arcade.key.LSHIFT or arcade.key.RSHIFT:
            self.snapping = True
        if symbol == arcade.key.UP and self.game_mode < len(MODES) - 1:
            self.game_mode += 1
            self.mode_switcher()
        if symbol == arcade.key.DOWN and 0 < self.game_mode:
            self.game_mode -= 1
            self.mode_switcher()

    def on_key_release(self, symbol: int, modifiers: int):
        if symbol == arcade.key.LSHIFT or arcade.key.RSHIFT:
            self.snapping = False

    def on_update(self, delta_time):
        start_time = timeit.default_timer()
        if not self.game_mode == 1:
            self.tick += 1

            if self.tick % 60 == 0:
                for pipe in self.pipes:
                    self.make_circle(x=pipe.pymunk_shape.body.position.x, y=pipe.pymunk_shape.body.position.y)

        self.space.step(1 / 80.0)

        if self.shape_being_dragged is not None:
            self.shape_being_dragged.shape.body.position = self.mouse_pos
            self.shape_being_dragged.shape.body.velocity = 0, 0

        for sprite in self.sprite_list:
            sprite.center_x = sprite.pymunk_shape.body.position.x
            sprite.center_y = sprite.pymunk_shape.body.position.y
            sprite.angle = math.degrees(sprite.pymunk_shape.body.angle)
            if sprite.pymunk_shape.body.position.y < -100:
                cur_shape = self.get_shape(sprite.pymunk_shape.body.position.x, sprite.pymunk_shape.body.position.y)
                self.delete_object(cur_shape)

        self.processing_time = timeit.default_timer() - start_time


if __name__ == '__main__':
    window = Careenium(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    arcade.run()
