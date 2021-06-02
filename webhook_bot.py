#! /usr/bin/python3

# -*- coding: utf-8 -*-

import telebot
from telebot import types
from pyzabbix import ZabbixAPI
import cherrypy
import time
import config

WEBHOOK_HOST = config.WEBHOOK_HOST
WEBHOOK_PORT = config.WEBHOOK_PORT
WEBHOOK_LISTEN = config.WEBHOOK_LISTEN
WEBHOOK_SSL_CERT = config.WEBHOOK_SSL_CERT
WEBHOOK_SSL_PRIV = config.WEBHOOK_SSL_PRIV
WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/%s/" % (config.token)

zab_server = config.zab_server
user = config.user
password = config.password


class WebhookServer(object):
    @cherrypy.expose
    def index(self):
        if 'content-length' in cherrypy.request.headers and \
                        'content-type' in cherrypy.request.headers and \
                        cherrypy.request.headers['content-type'] == 'application/json':
            length = int(cherrypy.request.headers['content-length'])
            json_string = cherrypy.request.body.read(length).decode("utf-8")
            update = telebot.types.Update.de_json(json_string)
            # Эта функция обеспечивает проверку входящего сообщения
            bot.process_new_updates([update])
            return ''
        else:
            raise cherrypy.HTTPError(403)
        
bot = telebot.TeleBot(config.token)

def get_problem(zab_server,user,password):
    zapi = ZabbixAPI(zab_server)
    zapi.login(user, password)

    # Get a list of all issues (AKA tripped triggers)
    triggers = zapi.trigger.get(only_true=1,
                                skipDependent=1,
                                monitored=1,
                                active=1,
                                output='extend',
                                expandDescription=1,
                                selectHosts=['host'],
                                )

    # Do another query to find out which issues are Unacknowledged
    unack_triggers = zapi.trigger.get(only_true=1,
                                      skipDependent=1,
                                      monitored=1,
                                      active=1,
                                      output='extend',
                                      expandDescription=1,
                                      selectHosts=['host'],
                                      withLastEventUnacknowledged=1,
                                      )
    unack_trigger_ids = [t['triggerid'] for t in unack_triggers]
    for t in triggers:
        t['unacknowledged'] = True if t['triggerid'] in unack_trigger_ids \
            else False

    # Print a list containing only "tripped" triggers
    res = ''
    for t in triggers:
        if int(t['value']) == 1:
            res = res + '*{0}* - _{1}_ {2}\n'.format(t['hosts'][0]['host'],t['description'],'(Unack)' if t['unacknowledged'] else '')
                  
    return res

    
@bot.message_handler(commands=["start"])
def cmd_start(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button = types.KeyboardButton('Get current problem')
    keyboard.add(button)
    bot.send_message(message.chat.id,'Press to "Get current problem" button',reply_markup = keyboard)
@bot.message_handler(regexp="Get current problem")
def cmd_get_problem(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button = types.KeyboardButton('Get current problem')
    keyboard.add(button)
    bot.send_message(message.chat.id,get_problem(zab_server,user,password),parse_mode='Markdown',reply_markup = keyboard)

bot.remove_webhook()
time.sleep(5)
# Set webhook
bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH)#,certificate=open(WEBHOOK_SSL_CERT, 'r'))

# Start cherrypy server
cherrypy.config.update({
    'server.socket_host': WEBHOOK_LISTEN,
    'server.socket_port': WEBHOOK_PORT,
    'server.ssl_module': 'builtin',
    'server.ssl_certificate': WEBHOOK_SSL_CERT,
    'server.ssl_private_key': WEBHOOK_SSL_PRIV
})

cherrypy.quickstart(WebhookServer(), WEBHOOK_URL_PATH, {'/': {}})
