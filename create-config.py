#!/usr/bin/env python3
# create a config file for use with itabashi
from __future__ import print_function
import getpass
import json
import sys

from slugify import slugify

import italib
from italib.utils import is_ok, GuiManager

# using custom format
config = {
    'version': italib.CURRENT_CONFIG_VERSION,
    'modules': {
        'discord': {},
        'irc': {},
    },
    'links': [
        # each channel-channel link is added one-by-one
    ],
}

gui = GuiManager()

# irc config
print("~=~ IRC Configuration ~=~")
config['modules']['irc']['nickname'] = input('Nickname: ')
config['modules']['irc']['server'] = input('Server: ')
config['modules']['irc']['tls'] = is_ok('Use TLS/SSL? [y] ', True)

if config['modules']['irc']['tls']:
    default_port = 6697
    config['modules']['irc']['tls_verify'] = is_ok('Verify TLS/SSL? [y] ', True)
else:
    default_port = 6667

if is_ok('Identify with NickServ password? [n] ', False):
    config['modules']['irc']['nickserv_password'] = input('NickServ Password: ')

config['modules']['irc']['port'] = gui.get_number('Port: [{}] '.format(default_port), None, default_port, True, False)

# discord config
print("\n~=~ Discord Configuration ~=~")
config['modules']['discord']['token'] = input('Discord - Bot Token: ')

# link config
print('\n~=~ Link Configuration ~=~')
print('To ignore a specific type of link, simply hit enter without specifying a name')
links = {}
while True:
    name = input('Link Name: ').strip()
    slug = slugify(name)
    log = is_ok('Log this link? [n] ', False)
    # TODO - Somehow note in config process that the hash in discord channel names is ignored.
    discord_chan = input('Discord Channel: ').strip()
    irc_chan = input('IRC Channel: ').strip()

    rem_md = is_ok('Strip Markdown from mesages before sending to IRC? [y] ', True)

    if slug in links:
        overwrite = is_ok('Link with that name already exists, overwrite existing link [y]? ', True)
        if overwrite:
            ...
        else:
            print('Skipping link')
            continue

    if not (discord_chan and irc_chan):
        print('You need to have one Discord channel and one IRC channel to link together')
        continue

    if log:
        print('Logging link')
    else:
        print('Will not log link')

    links[slug] = {
        'name': name,
        'log': log,
        'rem_md': rem_md,
        'channels': {
            'discord': discord_chan,
            'irc': irc_chan,
        },
    }

    another_link = is_ok('Setup another link [n]? ', False)
    if another_link:
        print('') # newline between links
    else:
        break

config['links'] = links

# write out config
with open('config.json', 'w') as f:
    json.dump([config], f, indent=2, sort_keys=True)

print('Config file has been dumped to config.json')
