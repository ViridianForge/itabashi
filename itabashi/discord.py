# Itabashi - quick and dirty discord bot
# itabashi_discord.py: discord bot
# Developed by Antonizoon for the Bibliotheca Anonoma
# Further developed by ViridianForge for Chiptunes=WIN
import asyncio
import sys
import regex

import aiohttp
import discord
import websockets
from italib import backoff
from italib import utils

loop = asyncio.get_event_loop()


class DiscordManager:
    def __init__(self, logger, config, event_manager):
        self.logger = logger
        self.config = config
        self.events = event_manager
        #Temp hack - eventually add this as a config option
        self.removeMarkdown = 1
    
        print("Initializing Discord")
        self.dispatch_channels = [config['links'][name]['channels']['discord'] for name in config['links'] if 'discord' in config['links'][name]['channels']]
        # simplifies down to a simple list of IRC chans -> Discord chans
        self.channels = {
            'irc': {},
        }
        for name in config['links']:
            link = config['links'][name]['channels']
            if 'discord' in link and 'irc' in link:
                if link['irc'] not in self.channels['irc']:
                    self.channels['irc'][link['irc']] = []
                if link['discord'] not in self.channels['irc'][link['irc']]:
                    self.channels['irc'][link['irc']].append(link['discord'])

        self.discord_channels = {}

        self.events.register('irc message', self.handle_irc_message)
        self.events.register('irc action', self.handle_irc_action)

        # extract values we use from config
        email = config['modules']['discord']['email']
        password = config['modules']['discord']['password']

        # create a client
        self.client = discord.Client()

        # attach events
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

        # start the discord.py client
        @asyncio.coroutine
        def main_task():
            # guided by https://gist.github.com/Hornwitser/93aceb86533ed3538b6f
            # thanks Hornwitser!
            retry = backoff.ExponentialBackoff()

            # login to Discord
            while True:
                try:
                    yield from self.client.login(email, password)
                except (discord.HTTPException, aiohttp.ClientError):
                    logging.exception("discord.py failed to login, waiting and retrying")
                    yield from asyncio.sleep(retry.delay())
                else:
                    break

            # connect to Discord and reconnect when necessary
            while self.client.is_logged_in:
                if self.client.is_closed:
                    self.client._closed.clear()
                    self.client.http.recreate()

                try:
                    yield from self.client.connect()

                except (discord.HTTPException, aiohttp.ClientError,
                        discord.GatewayNotFound, discord.ConnectionClosed,
                        websockets.InvalidHandshake,
                        websockets.WebSocketProtocolError) as e:
                    if isinstance(e, discord.ConnectionClosed) and e.code == 4004:
                        raise # Do not reconnect on authentication failure
                    logging.exception("discord.py disconnected, waiting and reconnecting")
                    yield from asyncio.sleep(retry.delay())

        # actually start running the client
        asyncio.async(main_task())

    # retrieve channel objects we use to send messages
    @asyncio.coroutine
    def on_ready(self):
        self.logger.debug('Discord -- Logged in as')
        self.logger.debug(self.client.user.name)
        self.logger.debug(self.client.user.id)
        self.logger.debug('------')

        # show all available channels and fill out our internal lists
        self.logger.debug('Available Discord Channels:')
        for channel in self.client.get_all_channels():
            self.logger.debug(' '.join(channel.name).join(channel.id))
            if channel.name in self.dispatch_channels:
                self.discord_channels[channel.name] = channel

        self.logger.debug('------')

        self.events.dispatch('discord ready', {})

    # dispatching messages
    @asyncio.coroutine
    def on_message(self, message):
        # for our watched channels only
        if message.channel.name.lower() in self.dispatch_channels:
            # dispatch all but our own messages
            if str(message.author) != str(self.client.user):
                full_message = [message.clean_content]
                if not full_message[0]:
                    full_message.pop(0)

                #Small call to strip any Discord Markdown from the outgoing message.
                #Things to catch:
                # ~~<text>~~, *<text>*, **<text>**, ***<text>***, __<text>__, __*<text>*__, __**<text>**__, __***<text>***__
                # `<text>`, ```<text>```
                #Possible TODO - Breakout to function in libraries
                if(self.removeMarkdown):
                    #Check for code blocks. These are full line, easy to spot.
                    if(full_message[0][0:2]=='```' and full_message[0][-3:]=='```'):
                         full_message[0] = str.strip(full_message[0],'```')
                    if(full_message[0][0]=='`' and full_message[0][-1]=='`'):
                        full_message[0] = str.strip(full_message[0],'`')
                    #For the rest of Markdown - the markup can appear on any word, or
                    #any set of words.
                    #TODO -  Get this working
                    #strike_through = regex.compile(r'(?<=~~[^~~]+~~)\W+\W+(?=~~[^~~]+~~)')
                    #underline_bold_italics = regex.compile('__\*\*\*.+\*\*\*__')
                    #underline_bold = regex.compile('__\*\*.+\*\*__')
                    #underline = regex.compile('__.+__')
                    #bold_italics = regex.compile('\*\*\*.+\*\*\*')
                    #bold = regex.compile('\*\*.+\*\*')
                    #italics = regex.compile('\*.+\*')
                    #TODO - Convert this into a loop to remove character pairs from full msg
                    #cln_msg = utils.remove_markdown(full_message[0],[pairs])
                    #Cleanse one - strike through - ~~<text>~~
                    cln_msg = utils.remove_markdown(full_message[0],'~~','~~')
                    #Cleanse two - underline bold italics - __***<text>***__
                    cln_msg = utils.remove_markdown(cln_msg,'__***','***__')
                    #Cleanse three - underline bold - __**<text>**__
                    cln_msg = utils.remove_markdown(cln_msg,'__**','**__')
                    #Cleanse four - underline - __<text>__
                    cln_msg = utils.remove_markdown(cln_msg,'__','__')
                    #Cleanse five - bold italics - ***<text>***
                    cln_msg = utils.remove_markdown(cln_msg,'***','***')
                    #Cleanse fix - bold - **<text>**
                    cln_msg = utils.remove_markdown(cln_msg,'**','**')
                    #Cleanse seven - italics - *<text>*
                    cln_msg = utils.remove_markdown(cln_msg,'*','*')

                    #Replace full_message with cleansed message
                    full_message[0] = cln_msg

                for attachment in message.attachments:
                    full_message.append(attachment.get('url', 'No URL for attachment'))
        
                info = {
                    'type': 'message',
                    'service': 'discord',
                    'channel': message.channel,
                    'source': message.author,
                    'message': ' '.join(full_message),
                }

                self.events.dispatch('discord message', info)

    # receiving messages
    def handle_irc_message(self, event):
        for chan in self.channels['irc'].get(str(event['channel'].name), []):
            assembled_message = '**<{}>** {}'.format(event['source'].nick, event['message'])
            asyncio.async(self.client.send_message(self.discord_channels[chan], assembled_message))

    def handle_irc_action(self, event):
        for chan in self.channels['irc'].get(str(event['channel'].name), []):
            assembled_message = '**\\* {}** {}'.format(event['source'].nick, event['message'])
