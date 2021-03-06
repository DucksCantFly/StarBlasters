from . entity import *
from . asteroid import *
from core.event_manager import *
from core.resource_manager import *
from utils.vector import *
import math
import pygame
import time
from utils import pyganim

class Ship(Entity):

	ACCELERATION = 25
	LASER_COOLDOWN = 0.5
	GUN_DISTANCE = 10

	def __init__(self, ship_controller, gun_controller):
		super(Ship, self).__init__()
		self.__delta = 0
		self.__ship_controller = ship_controller
		self.__gun_controller = gun_controller
		self.__alive = True
		self.__fire = False
		self.set_position((0, 0))
		self.__acceleration = (0, 0)
		self.__velocity = (0, 0)
		self.__glow_phase = 0
		self.__gun_rot = math.pi
		self.__last_laser_fire = 0
		self.__resource_manager = ResourceManager.get_instance()
		self.__blit_laser = None
		self.__laser_texture = self.__resource_manager.get_image("graphics/laser")
		self.set_texture(self.__resource_manager.get_image("graphics/mothership"))
		self.__gun_image = self.__resource_manager.get_image("graphics/mothership_gun")
		self.__glow1 = self.__resource_manager.get_image("graphics/mothership_brightness_2")
		self.__laser_sound = self.__resource_manager.get_sound("sounds/laser")
		self.__death_animation = pyganim.PygAnimation([(self.__resource_manager.get_image("graphics/boom1"),0.12),
			(self.__resource_manager.get_image("graphics/boom2"),0.12),
			(self.__resource_manager.get_image("graphics/boom3"),0.12),
			(self.__resource_manager.get_image("graphics/boom4"),0.12),
			])
		self.__death_animation.play()
		EventManager.get_instance().subscribe("ship_move", self.on_accelerate)
		EventManager.get_instance().subscribe("gun_rotate", self.rotate_gun)
		EventManager.get_instance().subscribe("fire", self.fire)

	def tick(self, dt):
		if not self.__alive:
			return
		self.__glow_phase += dt*5
		self.__velocity = scale_vec(0.95, add_vecs(self.__velocity, scale_vec(dt, self.__acceleration)))
		self.set_position(add_vecs(self.get_position(), self.__velocity))
		if self.__fire:
			self.on_fire()
			self.__fire = False
		if self.check_collision():
			EventManager.get_instance().send("death", True)

		self.__gun_rot += self.__delta * math.pi * dt

	def draw(self, screen, cx, cy):
		if not self.__alive:
			death_pos = add_vecs(self.get_position(), (cx, cy))
			self.__death_animation.blit(screen,death_pos)
			self.__death_animation.loop = False
		else:
			self.draw_ship(screen, cx, cy)
			self.draw_gun(screen, cx, cy)
			self.draw_laser(screen, cx, cy)

	def draw_ship(self, screen, cx, cy):
		pos = add_vecs(self.get_position(), (cx, cy))
		screen.blit(self.get_texture(), pos)
		screen.blit_alpha(self.__glow1, pos, (math.sin(self.__glow_phase)/2+0.5)*255)

	def draw_gun(self, screen, cx, cy):
		angle =self.get_gun_angle()
		rotated_gun = pygame.transform.rotate(self.__gun_image, angle)
		gun_loc = add_vecs(self.get_gun_position(), (cx, cy))
		screen.blit(rotated_gun, gun_loc)

	def draw_laser(self, screen, cx, cy):
		if self.__blit_laser:
			laser_start = 5
			if isinstance(self.__blit_laser, pygame.Rect):
				x, y, width, height = self.__blit_laser
				laser = pygame.Rect(x+cx, y+cy, width, height)
				gun_loc = add_vecs(self.get_gun_position(), (cx, cy))
				distance = min(magnitude(add_vecs(laser.center, scale_vec(-1, gun_loc))), 750)
			else:
				distance = 750
			scaled_laser = pygame.transform.scale(self.__laser_texture, (8, int(distance)))
			rotated_laser = pygame.transform.rotate(scaled_laser, self.get_gun_angle())
			laser_loc = rotated_laser.get_rect()
			laser_radius = self.get_rect().width/2 + laser_start + Ship.GUN_DISTANCE
			laser_loc.center = scale_vec(laser_radius + distance/2, (math.cos(self.__gun_rot), -math.sin(self.__gun_rot)))
			laser_loc.center = add_vecs(laser_loc.center, self.get_ship_center())
			laser_loc.center = add_vecs(laser_loc.center, (cx, cy))
			screen.blit(rotated_laser, laser_loc)
			self.__blit_laser = None

	def kill(self):
		self.__alive = False

	def on_accelerate(self, delta):
		self.__acceleration = scale_vec(Ship.ACCELERATION, delta)

	def rotate_gun(self, delta):
		self.__delta = delta

	def fire(self, event):
		# Set to fire on next tick
		self.__fire = True

	def on_fire(self, arg=None):
		if time.time() < self.__last_laser_fire or not self.__alive:
			return
		self.__last_laser_fire = time.time() + Ship.LASER_COOLDOWN
		self.__laser_sound.play()
		deg = lambda x: 180*x/math.pi - 90
		entities = self.get_scene().get_entities()
		closest = 999999
		hit_asteroid = None
		for asteroid in entities:
			if not(isinstance(asteroid, Asteroid)):
				continue
			a_center = asteroid.get_rect().center
			s_center = self.get_rect().center
			v = add_vecs(a_center, scale_vec(-1, s_center))
			n_v = normalize(v)
			asteroid_radius = asteroid.get_rect().width/2
			a_angle = math.acos(n_v[0])
			if v[1] > 0:
				a_angle = 2*math.pi - a_angle
			theta = math.atan(asteroid_radius/magnitude(v))
			between = [a_angle - theta, a_angle + theta]
			gun_angle = self.__gun_rot % (2*math.pi)
			if between[0] < 0:
				between[0] += 2*math.pi
				test = lambda x: x > between[0] or x < between[1]
			else:
				test = lambda x: between[0] < x < between[1]
			if test(gun_angle) and magnitude(v) < closest:
				closest = magnitude(v)
				hit_asteroid = asteroid
		if hit_asteroid:
			self.__blit_laser = hit_asteroid.get_rect()
			hit_asteroid.split()
		else:
			self.__blit_laser = True

	def check_collision(self):
		entities = self.get_scene().get_entities()
		for asteroid in entities:
			if not(isinstance(asteroid, Asteroid)):
				continue
			a_center = asteroid.get_rect().center
			a_radius = asteroid.get_rect().width/2 - 5*asteroid.get_size()
			s_center = self.get_rect().center
			s_radius = self.get_rect().width/2
			v = add_vecs(a_center, scale_vec(-1, s_center))
			distance = magnitude(v)
			if distance <= a_radius+s_radius:
				return True
		return False

	def get_ship_center(self):
		return add_vecs(self.get_position(), scale_vec(0.5, self.get_texture().get_rect().size))

	def get_gun_angle(self):
		return  self.__gun_rot * 180 / math.pi - 90

	def get_gun_position(self):
		ship_radius = self.get_texture().get_rect().width / 2
		gun_radius = ship_radius + Ship.GUN_DISTANCE
		gun_center = scale_vec(gun_radius, (math.cos(self.__gun_rot), -math.sin(self.__gun_rot)))
		gun_loc = add_vecs(gun_center, scale_vec(-0.5, self.__gun_image.get_rect().size))
		return add_vecs(gun_loc, self.get_ship_center())
