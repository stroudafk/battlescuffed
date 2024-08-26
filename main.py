import os
import random
import copy

import discord
from discord.ext import commands
from utils import *

my_secret = os.environ['DISCORD_BOT']

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

description = '''Battleship'''

## set up game's guild environment
# check if a category exists. if yes, check if channels exist. if no to either, create them and set up permissions

bot = commands.Bot(command_prefix='?', description = description, intents = intents)
client = discord.Client(intents=intents)

# game stated
game_state = GameState()

# game players
player_a = Player()
player_a.ships_placed = [False] * MAX_SHIPS
player_a.ships = []
player_a.fleet = copy.deepcopy(INITIAL_BOARD)
player_a.opponent_view = copy.deepcopy(INITIAL_BOARD)

player_b = Player()
player_b.ships_placed = [False] * MAX_SHIPS
player_b.ships = []
player_b.fleet = copy.deepcopy(INITIAL_BOARD)
player_b.opponent_view = copy.deepcopy(INITIAL_BOARD)

# converts a 2D list into a string for discord
def stringify_board(board):
  # apparrently discord trims prefixed whitespace, so we use a black square tile and all light mode users can suck it :P
  fleet_string = ':black_large_square:'
  
  for col in range(0,len(COLUMN_HEADERS)):
    fleet_string += COLUMN_HEADERS[col]

  fleet_string += '\n'
  
  for row in range(0,len(board)):
    fleet_string += ROW_HEADERS[row]
    for tile in range(0,len(board[row])):
      fleet_string += board[row][tile]
    fleet_string += '\n'
  return fleet_string

@bot.event
async def on_ready():
  print(f'{bot.user} is connected to your server')

  ## Create game space in guild ##

  # if discord.utils.get(ctx.guild.categories, name='battleship') == None:
  #   await ctx.guild.create_category('battleship')
  
  
@bot.command(name='join', help='Join or start a game of battleship')
async def join(ctx):

  # makes sure all right roles exist and permissions are as expected
  # TODO: add 'doctor' command that fixes environment without creating a game (or disturbing a game?)
  await guild_setup(ctx)
  
  if game_state.in_progress == True:
    await ctx.send('There is already a game in progress.')
    return
    
  if game_state.in_progress == False and len(game_state.players) == 0:
    # add player to list of players
    game_state.players.append(ctx.author.id)
    player_a.id = ctx.author.id

    await set_role_a(ctx, player_a)
    
    await ctx.send(f'{ctx.author.mention} has joined the game as Captain A. Waiting for Captain B...')
    
  elif game_state.in_progress == False and len(game_state.players) == 1:
    if ctx.author.id == game_state.players[0]:
      await ctx.send(f'{ctx.author.mention} has already joined the game.')
      return

    # add player to list of playersk
    game_state.players.append(ctx.author.id)
    player_b.id = ctx.author.id

    await set_role_b(ctx, player_b)

    # choose who goes first (should I move this to place?)
    game_state.player_turn = random.choice(game_state.players)

    # mention the player who goes first
    first_player = await bot.fetch_user(game_state.player_turn)
    await ctx.send(f'{ctx.author.mention} has joined the game as Captain B. Captain {first_player.mention} goes first.')
    game_state.in_progress = True


@bot.command(name='place', help='Place a ship on the board')
async def place(ctx):
  if game_state.in_progress == False:
    await ctx.send('No game in progress :(')
    return
  
  if ctx.author.id not in game_state.players:
    return
    
  player = player_a if ctx.author.id == player_a.id else player_b

  valid_placement = await validate_placement(ctx,player,game_state)
  
  if valid_placement == False:
    return

  args = ctx.message.content.split()
  ship_size = int(args[1])
  orientation = args[2].upper()
  row = letter_to_num(args[3])
  col = int(args[4])-1
  invalid_placement = False
  
  player.ships_placed[ship_size-1] = True

  if ship_size == 1:
    orientation = 'V'

  ship_coords = []
  
  while ship_size > 0:
    if orientation == 'V':
      player.fleet[row][col] = VERT_SHIP_TILE
      ship_coords.append((row,col))
      row += 1
      ship_size -= 1
    elif orientation == 'H':
      player.fleet[row][col] = HORI_SHIP_TILE
      col += 1
      ship_size -= 1

  player.ships.append(ship_coords)

  if len(player_a.ships) == MAX_SHIPS and len(player_b.ships) == MAX_SHIPS:
    game_state.phase = BATTLE
  
  ## add logic to print in the correct categories later
  # a = await bot.fetch_user(player_a.id)
  # await ctx.send(f'{a.mention}')
  # await ctx.send(stringify_board(player_a.fleet))

  # b = await bot.fetch_user(player_b.id)
  # await ctx.send(f'{b.mention}')
  # await ctx.send(stringify_board(player_b.fleet))

  await ctx.send(stringify_board(player.fleet))

# @bot.command(name='challenge', help='Challenge another player to a game of battleship')
# async def challenge(ctx):
#   await ctx.send('@ has challenged @ to a game of battleship! Do you accept?')

@bot.command(name='peek', help='Peek at your fleet.')
async def peek(ctx):
  
  if ctx.author.id not in game_state.players:
    return
    
  player = player_a if ctx.author.id == player_a.id else player_b
  opponent = player_b if ctx.author.id == player_a.id else player_a
  output = ''

  for row in range(0, game_state.board_rows):
    output += ROW_HEADERS[row]
    for col in range(0, game_state.board_cols):
      if player.opponent_view[row][col] == HIT_TILE:
        output += HIT_TILE
      else:
        output += player.fleet[row][col]

    output += '\n'

  await ctx.send(output)

@bot.command(name='fire', help='Guess a co-ordinate to sink your opponent\'s ships.\n Ex. ?fire e4')
async def fire(ctx):      
  if ctx.author.id not in game_state.players:
    return
  if ctx.author.id != game_state.player_turn:
    await ctx.send(f'It\'s the other player\'s turn.')  
    return
    
  if game_state.phase == PLAN:
    await ctx.send('One or more players still has ships left to place.')
    return
      
    
  row = ctx.message.content[-2]
  row = letter_to_num(row)
  
  col = int(ctx.message.content[-1]) -1

  print(f'Firing at {row+1} {col}')

  player = None
  opponent = None

  if ctx.author.id == player_a.id:
    player = player_a
    opponent = player_b
  else:
    player = player_b
    opponent = player_a
    
  output = ''
  if opponent.fleet[row][col] == ':ocean:':
    output = 'Miss!\n'
    opponent.opponent_view[row][col] = MISS_TILE
    output += stringify_board(opponent.opponent_view)
    game_state.player_turn = opponent.id
  else:
    output = 'Hit!\n'
    opponent.opponent_view[row][col] = HIT_TILE
    output += stringify_board(opponent.opponent_view)

  await ctx.send(output)
  

bot.run(my_secret)