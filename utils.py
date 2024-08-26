import os
import random
import copy

import discord
from discord.ext import commands

# game constants
COLUMN_HEADERS = [':one:'':two:',':three:',':four:',':five:',':six:',':seven:',':eight:',':nine:',':keycap_ten:']
ROW_HEADERS = [':regional_indicator_a:', ':regional_indicator_b:', ':regional_indicator_c:', ':regional_indicator_d:', ':regional_indicator_e:', ':regional_indicator_f:', ':regional_indicator_g:', ':regional_indicator_h:', ':regional_indicator_i:', ':regional_indicator_j:']

INITIAL_BOARD = [
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:'],
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:'],
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:'],
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:'],
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:'],
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:'],
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:'],
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:'], 
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:'],
  [':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:',':ocean:']
]

MAX_SHIPS = 3

# game piece strings 
MISS_TILE = ':white_circle:'
HIT_TILE = ':boom:'
SUNK_TILE = ':black_medium_small_square:'
HORI_SHIP_TILE = ':cruise_ship:'
VERT_SHIP_TILE = ':ship:'

# game phases
PLAN = 0
BATTLE = 1

# game classes
class Player:
  id = None
  score = 0
  ships_sunk = 0
  ships_placed = None
  ships = None
  fleet = None
  opponent_view = None

class Ship:
  tiles = None
  sunken = False

class GameState:
  in_progress = False
  players = []
  player_turn = None
  round_winner = None
  board_rows = len(INITIAL_BOARD[0])
  board_cols = len(INITIAL_BOARD)
  phase = PLAN

# util methods
# returns the equivalent row index as an integer
def letter_to_num(letter):
  if letter.upper() == 'A':
    return 0
  elif letter.upper() == 'B':
    return 1
  elif letter.upper() == 'C':
    return 2
  elif letter.upper() == 'D':
    return 3
  elif letter.upper() == 'E':
    return 4
  elif letter.upper() == 'F':
    return 5
  elif letter.upper() == 'G':
    return 6
  elif letter.upper() == 'H':
    return 7
  elif letter.upper() == 'I':
    return 8
  elif letter.upper() == 'J':
    return 9
  else:
    return -1


async def guild_setup(ctx):
  # making sure the right roles exist
  roles = ["Captain A", "Captain B"]
  for role in roles:
    fetched_role = discord.utils.get(ctx.guild.roles, name=role)
    if fetched_role is None:
      created_role = await ctx.guild.create_role(name=role)
      print(f'Role {role} has been created.')
    else:
      print(f'Role {role} already exists.')

###
  category_name = 'battleship'
  channel_names = ['captain-a', 'captain-b']
  role_names = ['Captain A', 'Captain B']

  # move this under the permission setting on line 108 to more logically group the category setup
  category = discord.utils.get(ctx.guild.categories, name=category_name)

  # Set permissions for everyone to view the category
  overwrites_category = {
      ctx.guild.default_role: discord.PermissionOverwrite(view_channel=True),
  }

  if category is None:
      category = await ctx.guild.create_category(category_name, overwrites=overwrites_category, position=0)
  else:
      await category.edit(overwrites=overwrites_category)

  for channel_name, role_name in zip(channel_names, role_names):
      channel = discord.utils.get(category.text_channels, name=channel_name)
      role = discord.utils.get(ctx.guild.roles, name=role_name)

      overwrites_channel = {
          ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
          role: discord.PermissionOverwrite(view_channel=True),
      }

      if channel is None:
          # The channel doesn't exist, so create it
          channel = await ctx.guild.create_text_channel(channel_name, category=category, overwrites=overwrites_channel)
      else:
          # The channel exists, modify its permissions
          await channel.edit(overwrites=overwrites_channel)

  # Check if the spectator channel exists within the category
  spectator_channel = discord.utils.get(category.text_channels, name='spectator')

  # Create the spectator channel if it doesn't exist
  if spectator_channel is None:
      spectator_channel = await ctx.guild.create_text_channel('spectator', category=category)

  # Set up overwrites for the Captain A and Captain B roles
  role_a = discord.utils.get(ctx.guild.roles, name='Captain A')
  role_b = discord.utils.get(ctx.guild.roles, name='Captain B')

  overwrites = {
      role_a: discord.PermissionOverwrite(view_channel=False),  # Captain A can't view the channel
      role_b: discord.PermissionOverwrite(view_channel=False)  # Captain B can't view the channel
  }
  await spectator_channel.edit(overwrites=overwrites)

#add captain A/ player A role
async def set_role_a(ctx, player_a):
  # first, remove existing captain a
  role_a = discord.utils.get(ctx.guild.roles, name='Captain A')
  for member in role_a.members:
    await member.remove_roles(role_a)

  member_a = await ctx.guild.fetch_member(player_a.id)
  await member_a.add_roles(role_a)


#add captain B role
async def set_role_b(ctx, player_b):  
  #remove any previous captains
  role_b = discord.utils.get(ctx.guild.roles, name='Captain B')
  for member in role_b.members:
    await member.remove_roles(role_b)

  member_b = await ctx.guild.fetch_member(player_b.id)
  await member_b.add_roles(role_b)


async def validate_placement(ctx, player, game_state):
  args = ctx.message.content.split()
  if len(args) != 5:
    await ctx.send('Try *?place* with the following format \n ?place <ship_size> <orientation> <row> <column>')
    return

  ship_size = int(args[1])
  orientation = args[2].upper()
  row = letter_to_num(args[3])
  col = int(args[4])-1
  invalid_placement = False

  if row == -1:
    await ctx.send('Invalid row.')
    invalid_placement = True

  if player.ships_placed[ship_size - 1] == True:
    await ctx.send('You have already placed a ship of this size.')
    invalid_placement = True

  if orientation not in ['H', 'HORI', 'HORIZONTAL', 'V', 'VERT', 'VERTICAL']:
    await ctx.send('Orientation options for:\n horizontal - h hori or horizontal\nvertical- v vert or vertical')
    invalid_placement = True

  if orientation in ['V', 'VERT', 'VERTICAL']:
    orientation = 'V'
  elif orientation in ['H', 'HORI', 'HORIZONTAL']:
    orientation = 'H'

  if orientation == 'V' and (col > game_state.board_cols or row < 0 or game_state.board_rows < row + ship_size - 1):
    await ctx.send('That vertical placement is off the board!')
    invalid_placement = True
  elif orientation == 'H' and (row > game_state.board_rows or col < 0 or game_state.board_cols < col + ship_size - 1):
    await ctx.send('That horizontal placement is off the board!')
    invalid_placement = True

  if invalid_placement == True:
    return False
  # me, 9 months later, unsure of why I don't return true for valid placement. ran out of time?