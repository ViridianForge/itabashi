# Itabashi - quick and dirty discord bot
# itabashi_discord.py: discord bot
# Developed by Antonizoon for the Bibliotheca Anonoma
import asyncio
import sys

import aiohttp
import discord
import websockets
from italib import backoff

loop = asyncio.get_event_loop()


class DiscordManager:
    def __init__(self, logger, config, event_manager):
        self.logger = logger
        self.config = config
        self.events = event_manager
	#Temp hack - eventually add this as a config option
	self.removeMarkdown = 0

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
        self.logger.debug('discord: raw 1')
        if message.channel.name.lower() in self.dispatch_channels:
            self.logger.debug('discord: raw 2')
            # dispatch all but our own messages
            if str(message.author) != str(self.client.user):
                self.logger.debug('discord: raw 3 - dispatching')
                self.logger.debug('discord: raw 4 - clean message' + message.clean_content)
                full_message = [message.clean_content]
                if not full_message[0]:
                    full_message.pop(0)

                #Small call to strip any Discord Markdown from the outgoing message.
                #Things to catch:
                # *<text>*, **<text>**, ***<text>***, __<text>__, __*<text>*__, __**<text>**__, __***<text>***__
                # `<text>`, ```<text>```
                #if(self.removeMarkdown):
                    #Check for code blocks. These are full line, easy to spot.
                    #if(full_message[0][0:2]=='```' && full_message[0][-3:]=='```'):
                    #     full_message[0] = string.strip(full_message[0],'```')
                    #if(full_message[0][0]=='`' && full_message[0][-1]=='`'):
                    #    full_message[0] = string.strip(full_message[0],'`')
                    #For the rest of Markdown - the markup can appear in any word.
                    #fMsgChk = string.split(full_message[0])
                    #newFM = []
                    #for chk in fMsgChk:
                        #Now look for underlines, these can appear anywhere in the message.
                    #    if(chk[0:1]=='__' && chk[-2:]=='__'):
                    #        chk = string.strip(chk,'__')
                        #Now look for the Bold and Italics Patterns
                    #    if(chk[0:1]=='**' && chk[-2:]=='**'):
                    #        chk = string.strip(chk,'**')
                    #    if(chk[0]='*' && chk[-1]='*'):
                    #        chk = string.strip(chk,'*')
                        #Construct new output
                    #    newFM.append(chk)
                    #full_message[0] = ' '.join(newFM)

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
