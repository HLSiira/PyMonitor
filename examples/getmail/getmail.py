#!/usr/bin/env python

# docs/COPYING 2a + DRY: https://github.com/getmail6/getmail6
# Please refer to the git history regarding who changed what and when in this file.

import sys

import os
import os.path
import time
try:
    import ConfigParser
except:
    import configparser as ConfigParser
import poplib
import imaplib
import pprint
from optparse import OptionParser, OptionGroup
import socket
import signal
import errno
import getpass

# Optional gnome-keyring integration
try:
    import gnomekeyring
    import glib
    glib.set_application_name('getmail')
    # And test to see if it's actually available
    if not gnomekeyring.is_available():
        gnomekeyring = None
except ImportError:
    gnomekeyring = None
# Optional Python keyring integration
try:
    import keyring
except ImportError:
    keyring = None

options_bool = (
    'read_all',
    'delete',
    'delivered_to',
    'received',
    'message_log_verbose',
    'message_log_syslog',
    'fingerprint',
)
options_int = (
    'delete_after',
    'delete_bigger_than',
    'max_message_size',
    'max_messages_per_session',
    'max_bytes_per_session',
    'verbose',
)
options_str = (
    'message_log',
)

# Unix only
try:
    import syslog
except ImportError:
    pass

try:
    from getmailcore import __version__, __license__, \
        retrievers, destinations,  filters, logging
    from getmailcore.exceptions import *
    from getmailcore.utilities import eval_bool, logfile, format_params, \
        address_no_brackets, expand_user_vars
except ImportError as o:
    sys.stderr.write('ImportError:  %s\n' % o)
    sys.exit(127)

log = logging.Logger()
log.addhandler(sys.stdout, logging.INFO, maxlevel=logging.INFO)
log.addhandler(sys.stderr, logging.WARNING)

def blurb():
    log.info('getmail version %s\n' % __version__)
    log.info('Copyright (C) 1998-2021 Charles Cazabon and others. '
             'Licensed under %s.\n'%__license__)

defaults = {
    'rcfile' : 'getmailrc',

    'verbose' : 1,
    'read_all' : True,
    'delete' : False,
    'delete_after' : 0,
    'delete_bigger_than' : 0,
    'max_message_size' : 0,
    'max_messages_per_session' : 0,
    'max_bytes_per_session' : 0,
    'delivered_to' : True,
    'received' : True,
    'message_log' : None,
    'message_log_verbose' : False,
    'message_log_syslog' : False,
    'logfile' : None,
    'fingerprint' : False,
}




#######################################
def convert_to_sigint(unused1, unused2):
    """Catch a SIGTERM and raise a SIGINT so getmail exits normally and does
    cleanup if killed with default signal.
    """
    raise KeyboardInterrupt('from signal')

signal.signal(signal.SIGTERM, convert_to_sigint)

#######################################
def go(configs, idle):
    """Main code.

    Returns True if all goes well, False if any error condition occurs.
    """
    blurb() # needed by docs/COPYING 2c
    summary = []
    errorexit = False
    idling = False

    if len(configs) > 1 and idle:
        log.info('more than one config file given with --idle, ignoring\n')
        idle = False

    for (configfile, retriever, _filters, destination, options) in configs:
        if options['read_all'] and not options['delete']:
            if idle:
                # This is a nonsense combination of options; every time the
                # server returns from IDLE, all messages will be re-retrieved.
                log.error('%s: IDLE, read_all, and not delete - bad '
                          'combination, skipping\n'
                          % retriever)
                continue
            else:
                # Slightly less nonsensical, but still weird.
                log.warning('%s: read_all and not delete -- all messages will '
                            'be retrieved each time getmail is run\n'
                            % retriever)

        oplevel = options['verbose']
        logverbose = options['message_log_verbose']
        now = int(time.time())
        msgs_retrieved = 0
        bytes_retrieved = 0
        msgs_skipped = 0
        if options['message_log_syslog']:
            syslog.openlog('getmail', 0, syslog.LOG_MAIL)
        try:
            if not idling:
                log.info('%s:\n' % retriever)
                logline = 'Initializing %s:' % retriever
                if options['logfile'] and logverbose:
                    options['logfile'].write(logline)
                if options['message_log_syslog'] and logverbose:
                    syslog.syslog(syslog.LOG_INFO, logline)
                retriever.initialize(options)
                destination.retriever_info(retriever)
                # session ready for idling
                idling = idle

            for mailbox in retriever.mailboxes:
                if mailbox:
                    # For POP this is None and uninteresting
                    log.debug('  checking mailbox %s ...\n'
                              % mailbox.encode('utf-8'))
                try:
                    retriever.select_mailbox(mailbox)
                except getmailMailboxSelectError as o:
                    errorexit = True
                    log.info('  mailbox %s not selectable (%s) - verify the '
                                'mailbox exists and you have sufficient '
                                'permissions\n' % (mailbox.encode('utf-8'), o))
                    continue
                nummsgs = len(retriever)
                fmtlen = len(str(nummsgs))
                for (msgnum, msgid) in enumerate(retriever):
                    log.debug('  message %s ...\n' % msgid)
                    msgnum += 1
                    retrieve = False
                    reason = 'seen'
                    delete = False
                    timestamp = retriever.oldmail.get(msgid, None)
                    size = retriever.getmsgsize(msgid)
                    info = ('msg %*d/%*d (%d bytes)'
                            % (fmtlen, msgnum, fmtlen, nummsgs, size))
                    logline = '%s msgid %s' % (info, msgid)
                    if options['read_all'] or timestamp is None:
                        retrieve = True
                    if (options['max_message_size']
                            and size > options['max_message_size']):
                        retrieve = False
                        reason = 'oversized'
                    if (options['max_bytes_per_session']
                            and (bytes_retrieved + size)
                                > options['max_bytes_per_session']):
                        retrieve = False
                        reason = 'would surpass max_bytes_per_session'
                    try:
                        if retrieve:
                            try:
                                msg = retriever.getmsg(msgid)
                            except (getmailRetrievalError,getmailConfigurationError) as o:
                                # Check if xoauth2 token was expired
                                # (Exchange Online only)
                                if 'AccessTokenExpired' in str(o):
                                    log.warn('Retrieval error: %s\n' % o)
                                    idling = False
                                    break
                                errorexit = True
                                log.error(
                                    'Retrieval error: %s\n'
                                    'Server for %s is broken; '
                                    'offered message %s but failed to provide it.  '
                                    'Please notify the administrator of the '
                                    'server.  Skipping message...\n'
                                    % (o, retriever, msgid)
                                )
                                continue
                            msgs_retrieved += 1
                            bytes_retrieved += size
                            if oplevel > 1:
                                info += (' from <%s>'
                                         % address_no_brackets(msg.sender))
                                if msg.recipient is not None:
                                    info += (' to <%s>'
                                             % address_no_brackets(msg.recipient))
                            logline += (' from <%s>'
                                        % address_no_brackets(msg.sender))
                            if msg.recipient is not None:
                                logline += (' to <%s>'
                                            % address_no_brackets(msg.recipient))

                            for mail_filter in _filters:
                                log.debug('    passing to filter %s\n'
                                          % mail_filter)
                                msg = mail_filter.filter_message(msg, retriever)
                                if msg is None:
                                    log.debug('    dropped by filter %s\n'
                                              % mail_filter)
                                    info += (' dropped by filter %s'
                                             % mail_filter)
                                    logline += (' dropped by filter %s'
                                                % mail_filter)
                                    retriever.delivered(msgid)
                                    break

                            if msg is not None:
                                r = destination.deliver_message(msg,
                                    options['delivered_to'], options['received'])
                                log.debug('    delivered to %s\n' % r)
                                info += ' delivered'
                                if oplevel > 1:
                                    info += (' to %s' % r)
                                logline += (' delivered to %s' % r)
                                retriever.delivered(msgid)
                            if options['delete']:
                                delete = True
                        else:
                            logline += ' not retrieved (%s)' % reason
                            msgs_skipped += 1
                            log.debug('    not retrieving (timestamp %s)\n'
                                      % timestamp)
                            if oplevel > 1:
                                info += ' not retrieved (%s)' % reason

                        if (options['delete_after'] and timestamp
                                and (now - timestamp) / 86400
                                    >= options['delete_after']):
                            log.debug(
                                '    older than %d days (%s seconds), will delete\n'
                                % (options['delete_after'], (now - timestamp))
                            )
                            delete = True

                        if options['delete'] and timestamp:
                            log.debug('    will delete\n')
                            delete = True

                        if (options['delete_bigger_than']
                                and size > options['delete_bigger_than']):
                            log.debug('    bigger than %d, will delete\n'
                                      % options['delete_bigger_than'])
                            delete = True

                        if not retrieve and timestamp is None:
                            # We haven't retrieved this message.  Don't delete it.
                            log.debug('    not yet retrieved, not deleting\n')
                            delete = False

                        if delete:
                            retriever.delmsg(msgid)
                            log.debug('    deleted\n')
                            info += ', deleted'
                            logline += ', deleted'

                    except getmailDeliveryError as o:
                        errorexit = True
                        log.error('Delivery error (%s)\n' % o)
                        info += ', delivery error (%s)' % o
                        if options['logfile']:
                            options['logfile'].write('Delivery error (%s)' % o)
                        if options['message_log_syslog']:
                            syslog.syslog(syslog.LOG_ERR,
                                          'Delivery error (%s)' % o)

                    except getmailFilterError as o:
                        errorexit = True
                        log.error('Filter error (%s)\n' % o)
                        info += ', filter error (%s)' % o
                        if options['logfile']:
                            options['logfile'].write('Filter error (%s)' % o)
                        if options['message_log_syslog']:
                            syslog.syslog(syslog.LOG_ERR,
                                          'Filter error (%s)' % o)

                    if (retrieve or delete or oplevel > 1):
                        log.info('  %s\n' % info)
                    if options['logfile'] and (retrieve or delete or logverbose):
                        options['logfile'].write(logline)
                    if options['message_log_syslog'] and (retrieve or delete
                                                          or logverbose):
                        syslog.syslog(syslog.LOG_INFO, logline)

                    if (options['max_messages_per_session']
                            and msgs_retrieved >=
                            options['max_messages_per_session']):
                        log.debug('hit max_messages_per_session (%d), breaking\n'
                            % options['max_messages_per_session'])
                        if oplevel > 1:
                            log.info('  max messages per session (%d)\n'
                                     % options['max_messages_per_session'])
                        raise StopIteration('max_messages_per_session %d'
                                            % options['max_messages_per_session'])

        except StopIteration:
            pass

        except KeyboardInterrupt as o:
            log.warning('%s: user aborted\n' % configfile)
            if options['logfile']:
                options['logfile'].write('user aborted')

        except socket.timeout as o:
            errorexit = True
            retriever.abort()
            if type(o) == tuple and len(o) > 1:
                o = o[1]
            log.error('%s: timeout (%s)\n' % (configfile, o))
            if options['logfile']:
                options['logfile'].write('timeout error (%s)' % o)

        except (poplib.error_proto, imaplib.IMAP4.abort) as o:
            errorexit = True
            retriever.abort()
            log.error('%s: protocol error (%s)\n' % (configfile, o))
            if options['logfile']:
                options['logfile'].write('protocol error (%s)' % o)

        except socket.gaierror as o:
            errorexit = True
            retriever.abort()
            if type(o) == tuple and len(o) > 1:
                o = o[1]
            log.error('%s: error resolving name (%s)\n' % (configfile, o))
            if options['logfile']:
                options['logfile'].write('gaierror error (%s)' % o)

        except socket.error as o:
            errorexit = True
            retriever.abort()
            if type(o) == tuple and len(o) > 1:
                o = o[1]
            log.error('%s: socket error (%s)\n' % (configfile, o))
            if options['logfile']:
                options['logfile'].write('socket error (%s)' % o)

        except getmailCredentialError as o:
            errorexit = True
            retriever.abort()
            log.error('%s: credential/login error (%s)\n' % (configfile, o))
            if options['logfile']:
                options['logfile'].write('credential/login error (%s)' % o)

        except getmailLoginRefusedError as o:
            retriever.abort()
            log.error('%s: login refused error (%s)\n' % (configfile, o))
            if options['logfile']:
                options['logfile'].write('login refused error (%s)' % o)

        except getmailOperationError as o:
            errorexit = True
            retriever.abort()
            log.error('%s: operation error (%s)\n' % (configfile, o))
            if options['logfile']:
                options['logfile'].write('getmailOperationError error (%s)' % o)
            if options['message_log_syslog']:
                syslog.syslog(syslog.LOG_ERR,
                              'getmailOperationError error (%s)' % o)

        summary.append(
            (retriever, msgs_retrieved, bytes_retrieved, msgs_skipped)
        )

        if idle:
            log.info('  %d messages (%d bytes) retrieved, %d skipped from %s\n'
                     % (msgs_retrieved, bytes_retrieved, msgs_skipped, retriever))
        else:
            log.info('  %d messages (%d bytes) retrieved, %d skipped\n'
                     % (msgs_retrieved, bytes_retrieved, msgs_skipped))
        if options['logfile'] and logverbose:
            options['logfile'].write(
                '  %d messages (%d bytes) retrieved, %d skipped\n'
                % (msgs_retrieved, bytes_retrieved, msgs_skipped)
            )
        log.debug('retriever %s finished\n' % retriever)
        try:
            if idle and not retriever.supports_idle:
                log.info('--idle given, but server does not support IDLE\n')
                idle = False

            if idle and not errorexit:
                # TODO
                # Okay, so what should really happen here is that when go_idle
                # returns, getmail should use the *existing* connection to check
                # for new messages and then call go_idle again once that is
                # done. The current code layout doesn't lend itself very well to
                # that since the message download code is coupled with the
                # connection setup/teardown code.
                #
                # Therefore, we do a bit of a hack.
                # We add the current config back into configs, so that when the
                # main for loop over configs runs again, it will find the same
                # config again, and thus download the new messages and then go
                # back to IDLEing. Since the return value of go_idle changes the
                # value of idling, a failed connection will cause it to become
                # False, which will make the main go() loop reconnect, which is
                # what we want.
                # Expunge and close the mailbox to  prevent the same messages
                # being pulled again in some configurations.
                try:
                    retriever.close_mailbox()
                except imaplib.IMAP4.abort as o:
                    # Treat "abort" exception as temporary failure
                    log.info('%s: session aborted during close_mailbox (%s)\n'
                             % (configfile, o))
                    idling = False
                try:
                    if idling:
                        idling = retriever.go_idle(idle)
                    # Returned from idle
                    retriever.set_new_timestamp()
                    configs.append(configs[0])
                    continue
                except KeyboardInterrupt as o:
                    # Because configs isn't appended to, this just means we'll
                    # quit, which is presumably what the user wanted
                    # The newline is to clear the ^C shown in terminal
                    log.info('\n')
                    pass
                except socket.error as o:
                    if o.errno != errno.ECONNRESET:
                        # Something unexpected happened
                        raise
                    #pass
                    # Just exit after a reset connection.

            retriever.quit()
        except getmailOperationError as o:
            errorexit = True
            log.debug('%s: operation error during quit (%s)\n'
                      % (configfile, o))
            if options['logfile']:
                options['logfile'].write('%s: operation error during quit (%s)'
                                         % (configfile, o))

    if sum([i for (unused, i, unused, unused) in summary]) and oplevel > 1:
        log.info('Summary:\n')
        for (retriever, msgs_retrieved, bytes_retrieved, unused) in summary:
            log.info('Retrieved %d messages (%s bytes) from %s\n'
                     % (msgs_retrieved, bytes_retrieved, retriever))

    return (not errorexit)


#######################################
def main():
    try:
        parser = OptionParser(version='%%prog %s' % __version__)
        parser.add_option(
            '-g', '--getmaildir',
            dest='getmaildir', action='store',
            help='look in DIR for config/data files', metavar='DIR'
        )
        parser.add_option(
            '-r', '--rcfile',
            dest='rcfile', action='append', default=[],
            help='load configuration from FILE (may be given multiple times)',
            metavar='FILE'
        )
        parser.add_option(
            '--dump',
            dest='dump_config', action='store_true', default=False,
            help='dump configuration and exit (debugging)'
        )
        parser.add_option(
            '--trace',
            dest='trace', action='store_true', default=False,
            help='print extended trace information (extremely verbose)'
        )
        parser.add_option(
            '-i', '--idle',
            dest='idle', action='store', default='',
            help='maintain connection and listen for new messages in FOLDER. '
                 'Only applies if a single rc file is given with a connection '
                 'to an IMAP server that supports the IDLE command',
            metavar='FOLDER'
        )
        if gnomekeyring:
            parser.add_option(
                '--store-password-in-gnome-keyring',
                dest='store_gnome_keyring', action='store_true', default=False,
                help='store the POP/IMAP password in the Gnome keyring'
            )
        if keyring:
            parser.add_option(
                '--store-password-in-keyring',
                dest='store_keyring', action='store_true', default=False,
                help='store the POP/IMAP password using the Python keyring package'
            )
        overrides = OptionGroup(
            parser, 'Overrides',
            'The following options override those specified in any '
                'getmailrc file.'
        )
        overrides.add_option(
            '-v', '--verbose',
            dest='override_verbose', action='count',
            help='operate more verbosely (may be given multiple times)'
        )
        overrides.add_option(
            '--fingerprint',
            dest='override_fingerprint', action='store_true',
            help='show SSL/TLS fingerprint and connection information'
        )
        overrides.add_option(
            '-q', '--quiet',
            dest='override_verbose', action='store_const',
            const=0,
            help='operate quietly (only report errors)'
        )
        overrides.add_option(
            '-d', '--delete',
            dest='override_delete', action='store_true',
            help='delete messages from server after retrieving'
        )
        overrides.add_option(
            '-l', '--dont-delete',
            dest='override_delete', action='store_false',
            help='do not delete messages from server after retrieving'
        )
        overrides.add_option(
            '-a', '--all',
            dest='override_read_all', action='store_true',
            help='retrieve all messages'
        )
        overrides.add_option(
            '-n', '--new',
            dest='override_read_all', action='store_false',
            help='retrieve only unread messages'
        )
        parser.add_option_group(overrides)

        (options, args) = parser.parse_args(sys.argv[1:])
        if args:
            raise getmailOperationError('unknown argument(s) %s ; try --help'
                                        % args)

        if options.trace:
            log.clearhandlers()

        if not options.rcfile:
            options.rcfile.append(defaults['rcfile'])

        s = ''
        for attr in dir(options):
            if attr.startswith('_'):
                continue
            if s:
                s += ','
            s += '%s="%s"' % (attr, pprint.pformat(getattr(options, attr)))
        log.debug('parsed options:  %s\n' % s)

        if options.getmaildir is None:
            getmaildir_type = 'Default'
            xdg_config = os.environ.get('XDG_CONFIG_HOME', os.path.join(os.environ["HOME"], ".config"))
            getmaildir_xdg = os.path.join(xdg_config, 'getmail')
            getmaildir_home = os.path.join(os.environ["HOME"], ".getmail")
            if os.path.exists(getmaildir_xdg):
                getmaildir = getmaildir_xdg
            elif os.path.exists(getmaildir_home):
                getmaildir = getmaildir_home
            else:
                raise getmailOperationError('Could not find the getmail configuration directory.  mkdir ~/.config/getmail/ or specify an alternate directory with the --getmaildir option.')
        else:
            getmaildir_type = 'Specified'
            getmaildir = expand_user_vars(options.getmaildir)
        if not os.path.exists(getmaildir):
            raise getmailOperationError(
                '%s config/data dir "%s" does not exist - create '
                'or specify alternate directory with --getmaildir option'
                % (getmaildir_type, getmaildir)
            )
        if not os.path.isdir(getmaildir):
            raise getmailOperationError(
                '%s config/data dir "%s" is not a directory - fix '
                'or specify alternate directory with --getmaildir option'
                % (getmaildir_type, getmaildir)
            )
        if not os.access(getmaildir, os.W_OK):
            raise getmailOperationError(
                '%s config/data dir "%s" is not writable - fix permissions '
                'or specify alternate directory with --getmaildir option'
                % (getmaildir_type, getmaildir)
            )

        configs = []
        for filename in options.rcfile:
            path = os.path.join(os.path.expanduser(getmaildir),
                                filename)
            log.debug('processing rcfile %s\n' % path)
            if not os.path.exists(path):
                raise getmailOperationError('configuration file %s does '
                                            'not exist' % path)
            elif not os.path.isfile(path):
                raise getmailOperationError('%s is not a file' % path)
            f = open(path, 'r')
            config = {
                'verbose' : defaults['verbose'],
                'read_all' : defaults['read_all'],
                'delete' : defaults['delete'],
                'delete_after' : defaults['delete_after'],
                'delete_bigger_than' : defaults['delete_bigger_than'],
                'max_message_size' : defaults['max_message_size'],
                'max_messages_per_session' :
                    defaults['max_messages_per_session'],
                'max_bytes_per_session' :
                    defaults['max_bytes_per_session'],
                'delivered_to' : defaults['delivered_to'],
                'received' : defaults['received'],
                'logfile' : defaults['logfile'],
                'message_log' : defaults['message_log'],
                'message_log_verbose' : defaults['message_log_verbose'],
                'message_log_syslog' : defaults['message_log_syslog'],
                'fingerprint' : defaults['fingerprint'],
            }
            # Python's ConfigParser .getboolean() couldn't handle booleans in
            # the defaults. Submitted a patch; they fixed it a different way.
            # But for the extant, unfixed versions, an ugly hack....
            parserdefaults = config.copy()
            for (key, value) in parserdefaults.items():
                if type(value) == bool:
                    parserdefaults[key] = str(value)

            try:
                configparser = ConfigParser.RawConfigParser(parserdefaults)
                try:
                    configparser.read_file(f)
                except AttributeError:
                    configparser.readfp(f)
                f.close()
                for option in options_bool:
                    log.debug('  looking for option %s ... ' % option)
                    if configparser.has_option('options', option):
                        log.debug('got "%s"'
                                  % configparser.get('options', option))
                        try:
                            config[option] = configparser.getboolean(
                                'options', option
                            )
                            log.debug('-> %s' % config[option])
                        except ValueError:
                            raise getmailConfigurationError(
                                'configuration file %s incorrect (option %s '
                                'must be boolean, not %s)'
                                % (path, option,
                                   configparser.get('options', option))
                            )
                    else:
                        log.debug('not found')
                    log.debug('\n')

                for option in options_int:
                    log.debug('  looking for option %s ... ' % option)
                    if configparser.has_option('options', option):
                        log.debug(
                            'got "%s"' % configparser.get('options', option)
                        )
                        try:
                            config[option] = configparser.getint('options',
                                                                 option)
                            log.debug('-> %s' % config[option])
                        except ValueError:
                            raise getmailConfigurationError(
                                'configuration file %s incorrect (option %s '
                                'must be integer, not %s)'
                                % (path, option,
                                   configparser.get('options', option))
                            )
                    else:
                        log.debug('not found')
                    log.debug('\n')

                # Message log file
                for option in options_str:
                    log.debug('  looking for option %s ... ' % option)
                    if configparser.has_option('options', option):
                        log.debug('got "%s"'
                                  % configparser.get('options', option))
                        config[option] = configparser.get('options', option)
                        log.debug('-> %s' % config[option])
                    else:
                        log.debug('not found')
                    log.debug('\n')
                if config['message_log']:
                    try:
                        config['logfile'] = logfile(config['message_log'])
                    except IOError as o:
                        raise getmailConfigurationError(
                            'error opening message_log file %s (%s)'
                            % (config['message_log'], o)
                        )

                # Clear out the ConfigParser defaults before processing further
                # sections
                configparser._defaults = {}

                # Retriever
                log.debug('  getting retriever\n')
                retriever_type = configparser.get('retriever', 'type')
                log.debug('    type="%s"\n' % retriever_type)
                retriever_func = getattr(retrievers, retriever_type)
                if not callable(retriever_func):
                    raise getmailConfigurationError(
                        'configuration file %s specifies incorrect '
                        'retriever type (%s)'
                        % (path, retriever_type)
                    )
                retriever_args = {
                    'getmaildir' : getmaildir,
                    'configparser' : configparser,
                }
                for (name, value) in configparser.items('retriever'):
                    if name in ('type', 'configparser'):
                        continue
                    if name == 'password':
                        log.debug('    parameter %s=*\n' % name)
                    else:
                        log.debug('    parameter %s="%s"\n' % (name, value))
                    retriever_args[name] = value
                log.debug('    instantiating retriever %s with args %s\n'
                          % (retriever_type, format_params(retriever_args)))
                try:
                    retriever = retriever_func(**retriever_args)
                    log.debug('    checking retriever configuration for %s\n'
                              % retriever)
                    retriever.checkconf()
                except getmailOperationError as o:
                    log.error('Error initializing retriever: %s\n' % o)
                    continue

                # Retriever is okay.  Check if user wants us to store the
                # password in a Gnome keyring for future use.
                if (gnomekeyring and options.store_gnome_keyring or
                   keyring and options.store_keyring):
                    # Need to get the password first, if the user hasn't put
                    # it in the rc file.
                    if retriever.conf.get('password', None) is not None:
                        password = retriever.conf['password']
                    elif retriever.conf.get('password_command', None):
                        # Retrieve from an arbitrary external command
                        password = retriever.run_password_command()
                    else:
                        password = getpass.getpass('Enter password for %s: ' % str(retriever))

                    if options.store_keyring:
                        keyring.set_password(
                            retriever.conf['server']
                            ,retriever.conf['username']
                            ,password)
                        log.info('Stored password in Python keyring.  Exiting.\n')
                    else:
                        gnomekeyring.set_network_password_sync(
                            # keyring=None, user, domain=None, server, object=None,
                            # protocol, authtype=None, port=0
                            None, retriever.conf['username'], None,
                            retriever.conf['server'], None, retriever.received_with,
                            None, 0, password
                        )
                        log.info('Stored password in Gnome keyring.  Exiting.\n')
                        if keyring:
                            log.info('... but Gnome keyring will not be used as you have Python keyring installed.\n')
                    raise SystemExit()

                # Destination
                log.debug('  getting destination\n')
                destination_type = configparser.get('destination', 'type')
                log.debug('    type="%s"\n' % destination_type)
                destination_func = getattr(destinations, destination_type)
                if not callable(destination_func):
                    raise getmailConfigurationError(
                        'configuration file %s specifies incorrect destination '
                        'type (%s)'
                        % (path, destination_type)
                    )
                destination_args = {'configparser' : configparser}
                for (name, value) in configparser.items('destination'):
                    if name in ('type', 'configparser'):
                        continue
                    if name == 'password':
                        log.debug('    parameter %s=*\n' % name)
                    else:
                        log.debug('    parameter %s="%s"\n' % (name, value))
                    destination_args[name] = value
                log.debug('    instantiating destination %s with args %s\n'
                          % (destination_type, format_params(destination_args)))
                destination = destination_func(**destination_args)

                # Filters
                log.debug('  getting filters\n')
                _filters = []
                filtersections =  [
                    section.lower() for section in configparser.sections()
                    if section.lower().startswith('filter')
                ]
                filtersections.sort()
                for section in filtersections:
                    log.debug('    processing filter section %s\n' % section)
                    filter_type = configparser.get(section, 'type')
                    log.debug('      type="%s"\n' % filter_type)
                    filter_func = getattr(filters, filter_type)
                    if not callable(filter_func):
                        raise getmailConfigurationError(
                            'configuration file %s specifies incorrect filter '
                            'type (%s)'
                            % (path, filter_type)
                        )
                    filter_args = {'configparser' : configparser}
                    for (name, value) in configparser.items(section):
                        if name in ('type', 'configparser'):
                            continue
                        if name == 'password':
                            log.debug('    parameter %s=*\n' % name)
                        else:
                            log.debug('    parameter %s="%s"\n' % (name, value))
                        filter_args[name] = value
                    log.debug('      instantiating filter %s with args %s\n'
                              % (filter_type, format_params(filter_args)))
                    mail_filter = filter_func(**filter_args)
                    _filters.append(mail_filter)

            except ConfigParser.NoSectionError as o:
                raise getmailConfigurationError(
                    'configuration file %s missing section (%s)' % (path, o)
                )
            except ConfigParser.NoOptionError as o:
                raise getmailConfigurationError(
                    'configuration file %s missing option (%s)' % (path, o)
                )
            except (ConfigParser.DuplicateSectionError,
                    ConfigParser.InterpolationError,
                    ConfigParser.MissingSectionHeaderError,
                    ConfigParser.ParsingError) as o:
                raise getmailConfigurationError(
                    'configuration file %s incorrect (%s)' % (path, o)
                )
            except getmailConfigurationError as o:
                raise getmailConfigurationError(
                    'configuration file %s incorrect (%s)' % (path, o)
                )

            # Apply overrides from commandline
            for option in ('read_all', 'delete', 'verbose', 'fingerprint'):
                val = getattr(options, 'override_%s' % option)
                if val is not None:
                    log.debug('overriding option %s from commandline %s\n'
                              % (option, val))
                    config[option] = val

            if config['verbose'] > 2:
                config['verbose'] = 2

            if not options.trace and config['verbose'] == 0:
                log.clearhandlers()
                log.addhandler(sys.stderr, logging.WARNING)

            configs.append((os.path.basename(filename), retriever, _filters,
                            destination, config.copy()))

        if options.dump_config:
            # Override any "verbose = 0" in the config file
            log.clearhandlers()
            log.addhandler(sys.stdout, logging.INFO, maxlevel=logging.INFO)
            log.addhandler(sys.stderr, logging.WARNING)
            blurb()
            for (filename, retriever, _filters, destination, config) in configs:
                log.info('getmail configuration:\n')
                log.info('  getmail version %s\n' % __version__)
                log.info('  Python version %s\n' % sys.version)
                log.info('  retriever:  ')
                retriever.showconf()
                if _filters:
                    for _filter in _filters:
                        log.info('  filter:  ')
                        _filter.showconf()
                log.info('  destination:  ')
                destination.showconf()
                log.info('  options:\n')
                for name in sorted(config.keys()):
                    log.info('    %s : %s\n' % (name, config[name]))
                log.info('\n')
            sys.exit()

        # Go!
        success = go(configs, options.idle)
        if not success:
            raise SystemExit(127)

    except KeyboardInterrupt:
        log.warning('Operation aborted by user (keyboard interrupt)\n')
        sys.exit(0)
    except getmailConfigurationError as o:
        log.error('Configuration error: %s\n' % o)
        sys.exit(2)
    except getmailOperationError as o:
        log.error('Error: %s\n' % o)
        sys.exit(3)
    except Exception as o:
        log.critical(
            '\nException: please read docs/BUGS and include the '
            'following information in any bug report:\n\n'
        )
        log.critical('  getmail version %s\n' % __version__)
        log.critical('  Python version %s\n\n' % sys.version)
        log.critical('Unhandled exception follows:\n')
        (exc_type, value, tb) = sys.exc_info()
        import traceback
        tblist = (traceback.format_tb(tb, None)
                  + traceback.format_exception_only(exc_type, value))
        if type(tblist) != list:
            tblist = [tblist]
        for line in tblist:
            log.critical('  %s\n' % line.rstrip())
        log.critical('\nPlease also include configuration information '
                     'from running getmail\n')
        log.critical('with your normal options plus "--dump".\n')
        sys.exit(4)

#######################################
if __name__ == '__main__':
    main()
