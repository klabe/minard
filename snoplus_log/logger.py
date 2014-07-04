import logging
import logging.handlers
from flask import Flask, request
app = Flask(__name__)
from datetime import datetime
from redis import Redis
import json
from os.path import join

redis = Redis()

_ALLOWED = ['L2', 'ECA']

# apparently logging.NOTSET does not mean to
# process every message, but to defer to a parent
# logger. If we set every logger to logging.NOTSET,
# the effective level is determined by the root
# logger. So, here, we set that to 0.
# see https://docs.python.org/2/library/logging.html#logging.Logger.setLevel
logging.getLogger().setLevel(0)

def get_logger(name):
    """Returns the logger for `name`."""
    if name not in _ALLOWED:
        raise NameError('logger name {name} not in allowed list'.format(name=name))

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    filename = join('/var/log/snoplus', name + '.log')
    logger.setLevel(logging.NOTSET)
    handler = logging.handlers.RotatingFileHandler(filename, maxBytes=5e6, backupCount=10)
    handler.setLevel(logging.NOTSET)
    logger.addHandler(handler)

    return logger

@app.route('/', methods=['POST'])
def log():
    """
    Log a message to disk and optionally set an alarm. The POST request
    should have the arguments 'name', 'level', and 'message'. If the
    argument 'notify' is present or level >= 3, the message will trigger an
    alarm.
    """
    name = request.form['name']

    if name not in _ALLOWED:
        return 'unknown program {name}'.format(name), 400

    logger = get_logger(name)

    lvl = int(request.form['level'])
    msg = request.form['message']

    # log it to disk
    logger.log(lvl,msg)

    if 'notify' in request.form or lvl >= 3:
        # post to redis
        id = redis.incr('/alarms/count') - 1

        alarm = {'id'     : id,
                 'level'  : lvl,
                 'message': msg,
                 'time'   : datetime.now().isoformat()}

        redis.setex('/alarms/{id}'.format(id=id), json.dumps(alarm), 24*60*60)

    return 'ok\n'

if __name__ == '__main__':
    # just for testing
    app.run(port=50001,debug=True)
